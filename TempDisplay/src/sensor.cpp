// sensor.cpp - опрос датчика без блокировки loop().
//  SHT40  - свой код на Wire по даташиту SHT4x (Docs/SHT4x_Datasheet.pdf, v6): команда -> ожидание по millis() ->
//           чтение 6 байт с проверкой CRC. Высокая повторяемость (0xFD, tMEAS,h до 8.3 мс).
//           Прогрев (опция, config.h HEATER_*): при влажности от HEATER_RH_ON - команда 0x2F (110 мВт, 1 с + измерение),
//           результат выбрасывается, затем HEATER_COOLDOWN_S измерения не берутся (температура важнее).
//  DS18B20 - DallasTemperature в асинхронном режиме: запуск преобразования, через DS18B20_CONV_MS - чтение.
// Шина I2C - I2C_CLOCK_HZ (провод до улицы).
#include "sensor.h"
#include "settings.h"
#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// SHT4x: адреса (разд. 1, варианты исполнения), команды (табл. 8), время (табл. 4), CRC (табл. 7), пересчёт (4.6)
#define SHT_ADDR_A          0x44     // SHT40-AD1B
#define SHT_ADDR_B          0x45     // SHT40-BD1B
#define SHT_CMD_MEAS_HIGH   0xFD     // T и RH, высокая повторяемость
#define SHT_CMD_HEAT_110_1S 0x2F     // нагреватель 110 мВт на 1 с, измерение перед выключением
#define SHT_MEAS_MS         10UL     // tMEAS,h - до 8.3 мс
#define SHT_HEAT_MS         1100UL   // tHeater (длинный импульс) - до 1 с + измерение
#define SHT_RESP_LEN        6        // T[2] CRC RH[2] CRC
#define SHT_RESP_T          0        // ответ: T - старший, младший байт, CRC
#define SHT_RESP_RH         3        //                  RH - старший, младший байт, CRC
#define SHT_WORD_LEN        2        // слово данных перед своим CRC
#define SHT_CRC_POLY        0x31     // x^8 + x^5 + x^4 + 1
#define SHT_CRC_INIT        0xFF
#define SHT_FULL_SCALE      65535L   // 2^16 - 1
#define SHT_T_SPAN_C10      1750L    // T = -45 + 175 * S / (2^16 - 1), °C (в десятых)
#define SHT_T_OFFS_C10      450
#define SHT_RH_SPAN         125L     // RH = -6 + 125 * S / (2^16 - 1), %
#define SHT_RH_OFFS         6
#define RH_MAX              100

namespace {
enum class Sht : uint8_t { Idle, Measuring, Heating };

OneWire           s_ow(PIN_ONEWIRE);
DallasTemperature s_ds(&s_ow);

SensorKind s_kind = SensorKind::None;
bool       s_fresh;
bool       s_dsWaiting;              // DS18B20: идёт преобразование
Sht        s_sht = Sht::Idle;        // SHT40: ждём результат измерения / импульса нагрева
uint8_t    s_shtAddr;
int16_t    s_tempC10;
uint8_t    s_hum;
uint8_t    s_tries;                  // повторов текущего измерения
bool       s_failed;                 // последнее измерение пропало
bool       s_retryWait;              // ждём паузу перед повтором (с s_tCmd)
uint16_t   s_errReads;               // неудачных чтений с включения
uint16_t   s_errLost;                // пропавших измерений с включения
uint32_t   s_tPoll;                  // время последнего запуска измерения / поиска
uint32_t   s_tCmd;                   // время команды SHT40 / запуска преобразования DS18B20 / неудачного чтения
bool       s_started;                // был хотя бы один запуск (первый - сразу после старта)
bool       s_heated;                 // был импульс нагревателя (s_tHeat действителен)
uint32_t   s_tHeat;                  // конец последнего импульса

bool cooling(uint32_t now) { return s_heated && now - s_tHeat < HEATER_COOLDOWN_S * 1000UL; }

uint8_t crc8(const uint8_t* p, uint8_t n)
{
    uint8_t crc = SHT_CRC_INIT;
    while (n--) {
        crc ^= *p++;
        for (uint8_t i = 0; i < 8; i++) crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ SHT_CRC_POLY) : (uint8_t)(crc << 1);
    }
    return crc;
}

bool shtProbe(uint8_t addr)
{
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;           // датчик ответил ACK на свой адрес
}

bool shtCommand(uint8_t cmd)
{
    Wire.beginTransmission(s_shtAddr);
    Wire.write(cmd);
    return Wire.endTransmission() == 0;
}

bool shtRead(int16_t& tC10, uint8_t& rh)
{
    uint8_t b[SHT_RESP_LEN];
    if (Wire.requestFrom(s_shtAddr, (uint8_t)SHT_RESP_LEN) != SHT_RESP_LEN) return false;
    for (uint8_t i = 0; i < SHT_RESP_LEN; i++) b[i] = (uint8_t)Wire.read();
    if (crc8(b + SHT_RESP_T, SHT_WORD_LEN) != b[SHT_RESP_T + SHT_WORD_LEN]
        || crc8(b + SHT_RESP_RH, SHT_WORD_LEN) != b[SHT_RESP_RH + SHT_WORD_LEN]) return false;
    const uint16_t st  = (uint16_t)b[SHT_RESP_T] << 8 | b[SHT_RESP_T + 1];
    const uint16_t srh = (uint16_t)b[SHT_RESP_RH] << 8 | b[SHT_RESP_RH + 1];
    tC10 = (int16_t)(((int32_t)st * SHT_T_SPAN_C10 + SHT_FULL_SCALE / 2) / SHT_FULL_SCALE) - SHT_T_OFFS_C10;
    const int32_t h = ((int32_t)srh * SHT_RH_SPAN + SHT_FULL_SCALE / 2) / SHT_FULL_SCALE - SHT_RH_OFFS;
    rh = h < 0 ? 0 : h > RH_MAX ? RH_MAX : (uint8_t)h;           // даташит 4.6: ограничить 0..100 %
    return true;
}

bool detect()
{
    s_sht = Sht::Idle;
    if (shtProbe(SHT_ADDR_A))      { s_shtAddr = SHT_ADDR_A; s_kind = SensorKind::Sht40; return true; }
    if (shtProbe(SHT_ADDR_B))      { s_shtAddr = SHT_ADDR_B; s_kind = SensorKind::Sht40; return true; }
    s_ds.begin();
    if (s_ds.getDeviceCount() > 0) {
        s_ds.setResolution(DS18B20_RESOLUTION);
        s_ds.setWaitForConversion(false);
        s_kind = SensorKind::Ds18b20;
        return true;
    }
    s_kind = SensorKind::None;
    return false;
}

void store(int16_t tC10)
{
    s_tempC10 = tC10;
    s_tries   = 0;
    s_failed  = false;
    s_fresh   = true;
}

// Неудачное чтение: повтор после паузы (SHT_RETRY_MS / DS18B20_RETRY_MS); после SENSOR_RETRIES повторов
// измерение пропало (до следующего периода)
void fail(uint32_t now)
{
    if (s_errReads < UINT16_MAX) s_errReads++;
    if (s_tries < SENSOR_RETRIES) {
        s_tries++;
        s_retryWait = true;
        s_tCmd = now;
        return;
    }
    s_tries  = 0;
    s_failed = true;
    if (s_errLost < UINT16_MAX) s_errLost++;
}

// Запуск измерения: SHT40 - команда, DS18B20 - преобразование (результат - через DS18B20_CONV_MS)
void measure(uint32_t now)
{
    if (s_kind == SensorKind::Ds18b20) {
        s_ds.requestTemperatures();
        s_dsWaiting = true;
        s_tCmd = now;
    } else if (shtCommand(SHT_CMD_MEAS_HIGH)) {
        s_sht  = Sht::Measuring;
        s_tCmd = now;
    } else {
        fail(now);
    }
}

// SHT40: результат команды готов?
void shtFinish(uint32_t now)
{
    const uint32_t wait = s_sht == Sht::Heating ? SHT_HEAT_MS : SHT_MEAS_MS;
    if (now - s_tCmd < wait) return;
    int16_t t;
    uint8_t rh;
    const bool ok = shtRead(t, rh);
    const bool heat = s_sht == Sht::Heating;
    s_sht = Sht::Idle;
    if (heat) {                                   // измерение с нагревом - не используется
        s_tHeat  = now;
        s_heated = true;
        if (!ok && s_errReads < UINT16_MAX) s_errReads++;
    } else if (ok) {
        s_hum = rh;
        store(t);
    } else {
        fail(now);
    }
}
}  // namespace

namespace Sensor {
void begin()
{
    Wire.begin();
    Wire.setClock(I2C_CLOCK_HZ);
#ifdef WIRE_TIMEOUT                                // MiniCore: включается флагом -DWIRE_TIMEOUT (platformio.ini)
    Wire.setWireTimeout(I2C_TIMEOUT_US, true);     // залипшая шина на длинном проводе - ошибка, а не зависание
#endif
    detect();
}

void update(uint32_t now, uint8_t pollS, bool heater)
{
    if (s_kind == SensorKind::Sht40 && s_sht != Sht::Idle) { shtFinish(now); return; }

    if (s_retryWait) {                             // пауза перед повтором
        if (now - s_tCmd < (s_kind == SensorKind::Ds18b20 ? DS18B20_RETRY_MS : SHT_RETRY_MS)) return;
        s_retryWait = false;
        measure(now);
        return;
    }

    // DS18B20: дождаться конца преобразования
    if (s_dsWaiting) {
        if (now - s_tCmd < DS18B20_CONV_MS) return;
        s_dsWaiting = false;
        const float t = s_ds.getTempCByIndex(0);   // -127: нет ответа на шине или CRC блокнота не сошлась
        if (t == DEVICE_DISCONNECTED_C) fail(now);
        else                            store((int16_t)lroundf(t * 10.0f));
        return;
    }

    if (s_started && now - s_tPoll < (uint32_t)pollS * 1000UL) return;
    s_started = true;
    s_tPoll   = now;

    switch (s_kind) {
        case SensorKind::None:                    // не найден при включении - не ищем
            break;
        case SensorKind::Sht40:
            if (cooling(now)) break;              // после нагрева показания не берём
            if (heater && s_hum >= HEATER_RH_ON && s_tempC10 < HEATER_MAX_T_C10
                && (!s_heated || now - s_tHeat >= HEATER_INTERVAL_S * 1000UL)) {
                if (shtCommand(SHT_CMD_HEAT_110_1S)) { s_sht = Sht::Heating; s_tCmd = now; break; }
                if (s_errReads < UINT16_MAX) s_errReads++;   // нагрев не начался - обычное измерение
            }
            measure(now);
            break;
        case SensorKind::Ds18b20:
            measure(now);
            break;
    }
}

bool takeFresh()
{
    const bool f = s_fresh;
    s_fresh = false;
    return f;
}

SensorKind kind()        { return s_kind; }
bool       failed()      { return s_failed; }
uint16_t   errReads()    { return s_errReads; }
uint16_t   errLost()     { return s_errLost; }
void       resetErrors() { s_errReads = 0; s_errLost = 0; }
int16_t    tempC10()     { return s_tempC10 + Cfg::s.corrC10; }   // с поправкой «Корр. °» (прогрев - по сырой)
bool       hasHumidity() { return s_kind == SensorKind::Sht40; }
uint8_t    humidity()    { return s_hum; }
bool       heating()     { return s_kind == SensorKind::Sht40 && (s_sht == Sht::Heating || cooling(millis())); }
}  // namespace Sensor
