// Fuses: читаются этой программой (вывод в Serial), не задаются.
//
// ChipInfo - проверка МК на плате Arduino Nano / Pro Mini: что за чип (оригинал ATmega328P / подделка / LGT8F328P /
// другой) и стресс-тест работоспособности (например, при питании 3.3 В). Serial 38400 (любой кварц 8 / 16 МГц).
//
// 1. Отчёт при старте и по команде «r»:
//    - подпись кристалла: 1E 95 0F - ATmega328P, 1E 95 14 - ATmega328, 1E 95 16 - ATmega328PB;
//    - служебные байты области подписи (партия, пластина, координаты): у оригинала разные, у известных подделок
//      почти все FF (microfarad.de/blog/counterfeit-atmega328p) - признак, не доказательство;
//    - LGT8F328P (и перемаркированные AVGA328P): регистры GUID0..3 (0xF3-0xF6, ядро LGT8fx, lgtx8p.h) - уникальный
//      номер; у ATmega328P эти адреса зарезервированы и читаются как 0. Только чтение, без записи;
//    - поддерживает ли чип чтение подписи из программы (SIGRD): клон, отдающий вместо подписи содержимое flash, -
//      не ATmega (оригинал и известные подделки подпись отдают); тогда фьюзы и температура не расшифровываются;
//    - время выполнения команд в тактах (Timer1, такт CPU): у ATmega - по даташиту (Instruction Set Summary),
//      клоны с другим ядром дают другие числа - «отпечаток» ядра;
//    - фьюзы, BOD, загрузочная секция и загрузчик; Vcc (по внутреннему 1.1 В); встроенный датчик температуры.
// 2. Стресс-тест - ТОЛЬКО при Vcc < LOW_VCC_MV (4 В, например питание 3.3 В на +5V): вычисления (CRC32 эталона),
//    деление, ОЗУ, чтение flash, Vcc. При 5 В (USB) - ожидание: тест не идёт, журнал не пишется, строки
//    состояния нет (Vcc проверяется раз в секунду, переход ниже 4 В - сообщение и старт теста).
//    Строка состояния раз в секунду; итоги копятся в EEPROM (видны после возврата на 5 В и USB: команда «l»).
//    Сторожевой таймер 2 с: зависание -> сброс, счётчик зависаний в EEPROM.
//    Светодиод D13: при 5 В (ожидание) - погашен; тест идёт: 1 Гц - ошибок нет, 5 Гц - были ошибки.
//    Отдельно копятся наработка и ошибки при пониженном питании (Vcc < LOW_VCC_MV, например 3.3 В).
// 3. Тест делителя частоты CLKPR (команда «k»): период генератора сторожевого таймера (128 кГц, не зависит
//    от кварца) в тиках Timer1 при делителе 1 и 2 - отношение должно быть ~2. Нужен для кварца 16 МГц при 3.3 В
//    (MiniCore: -DOSC_PRESCALER=1, F_CPU 8 МГц); с кварцем 8 МГц делитель не нужен, тест - справочный.
// 4. Тест сторожевого таймера в режиме сброса (команда «w»): программа зависает с запрещёнными прерываниями,
//    сторож (2 с, wdt_enable) должен перезапустить МК - отчёт появится сам примерно через 2-4 с.
// Команды: r - отчёт, l - журнал EEPROM, c - очистить журнал, e - тест одной ячейки EEPROM, k - тест CLKPR,
//          w - тест сторожа (зависание).
//
// Питание 3.3 В: подавать на пин +5V Nano, USB при этом ОТКЛЮЧИТЬ (иначе на шине будет 5 В от USB).
// Не на VIN (там стабилизатор 5 В). Serial при этом недоступен - смотреть светодиод, потом журнал «l» от USB.
//
// Важно: avrdude при загрузке через бутлоадер получает подпись от самого бутлоадера (она зашита в его код),
// поэтому «avrdude видит 1E 95 0F» не доказывает, что чип настоящий. Здесь подпись читается из кристалла.
#include <Arduino.h>
#include <EEPROM.h>
#include <avr/boot.h>
#include <avr/pgmspace.h>
#include <avr/power.h>
#include <avr/wdt.h>
#include <util/atomic.h>
#include <util/crc16.h>

// ------------------------------------------------------------------ параметры
#define SERIAL_BAUD           38400UL   // при 8 МГц ошибка 0.2% (115200 - 3.5%); и при F_CPU / 2 в тесте «k»
#define USB_WAIT_MS           1500      // пауза после старта: успеть открыть монитор (только в setup)
#define STATUS_MS             1000UL    // строка состояния и замер Vcc
#define LOW_VCC_MV            4000      // ниже - «пониженное питание»: только тогда идёт стресс-тест
#define LED_OK_HALF_MS        500UL     // мигание 1 Гц - ошибок нет
#define LED_ERR_HALF_MS       100UL     // мигание 5 Гц - были ошибки
#define LOG_SAVE_MS           60000UL   // журнал в EEPROM - раз в минуту (ресурс ячейки 100 000 записей)
#define LOG_ERR_SAVE_MS       5000UL    // при новых ошибках - не чаще раза в 5 с

// Область подписи (signature row), адреса для boot_signature_byte_get(), даташит ATmega328P «Signature Bytes»
#define SIGROW_SIZE           0x20
#define SIGROW_SIG0           0x00      // 0x1E - производитель Atmel
#define SIGROW_OSCCAL         0x01      // заводская калибровка RC-генератора 8 МГц
#define SIGROW_SIG1           0x02      // 0x95 - 32 КБ flash
#define SIGROW_SIG2           0x04      // 0x0F / 0x14 / 0x16 - модель
#define SIGROW_SERIAL_FIRST   0x0E      // байты партии / пластины / координат (недокументированы, у оригинала есть)
#define SIGROW_SERIAL_LAST    0x17

#define SIG_ATMEL             0x1E
#define SIG_32K               0x95
#define SIG_328P              0x0F
#define SIG_328               0x14
#define SIG_328PB             0x16

// Порог «почти все FF» по служебным байтам (у подделок из статьи microfarad - FF во всех 17 байтах ниже)
#define FAKE_FF_MIN           14        // столько FF и больше - как у известных подделок
#define GENUINE_FF_MAX        3         // столько FF и меньше - как у оригинала

// LGT8F328P: уникальный номер GUID0..3 (lgtx8p.h ядра LGT8fx), у ATmega328P - зарезервированные адреса
#define LGT_GUID_FIRST        0xF3
#define LGT_GUID_COUNT        4
#define LGT_GUID_MIN_BYTES    2         // ненулевых байтов GUID, чтобы считать его номером, а не случайностью

// Flash
#define FLASH_SIZE            32768UL
#define FLASH_TAIL_DUMP       16        // байт с конца flash (там версия загрузчика)

// Фьюзы: high - BOOTRST бит 0, BOOTSZ1:0 биты 2:1; extended - BODLEVEL2:0 биты 2:0
#define HFUSE_BOOTRST_BIT     0
#define HFUSE_BOOTSZ_SHIFT    1
#define HFUSE_BOOTSZ_MASK     0x03
#define EFUSE_BOD_MASK        0x07
#define BOD_OFF               0x07
#define BOD_1V8               0x06
#define BOD_2V7               0x05
#define BOD_4V3               0x04

// Допустимая частота по даташиту (Speed Grades): 4 МГц при 1.8 В, 10 МГц при 2.7 В, 20 МГц при 4.5 В, линейно
#define SG_V1_MV              1800UL
#define SG_V2_MV              2700UL
#define SG_V3_MV              4500UL
#define SG_F1_KHZ             4000UL
#define SG_F2_KHZ             10000UL
#define SG_F3_KHZ             20000UL

// АЦП: опорное AVcc и вход - внутренний 1.1 В; опорное 1.1 В и вход - датчик температуры
#define ADC_MUX_BANDGAP       0x0E
#define ADC_MUX_TEMP          0x08
#define ADC_SETTLE_CONV       50        // холостых преобразований после смены входа (~5 мс, конденсатор AREF)
#define ADC_SAMPLES           8
#define BANDGAP_MV            1100UL    // номинал, разброс по даташиту 1.0-1.2 В
#define ADC_FULL_SCALE        1024UL
// Датчик температуры (даташит, табл. «Temperature vs. Sensor Output Voltage»): 314 мВ при +25 °C, ~1 мВ/°C
#define TEMP_MV_AT_25C        314L
#define TEMP_REF_C            25L

// Стресс-тест
#define CPU_TEST_BYTES        256          // длина псевдослучайной последовательности
#define CPU_XS_SEED           0x12345678UL // xorshift32
#define CPU_LCG_SEED          0x87654321UL // LCG
#define CPU_LCG_MUL           1103515245UL
#define CPU_LCG_ADD           12345UL
#define CPU_TEST_CRC_REF      0xC27F1637UL // эталон: python Scripts/chipinfo_crc_ref.py
#define CRC32_POLY            0xEDB88320UL
#define CRC32_INIT            0xFFFFFFFFUL
#define DIV_TEST_COUNT        16
#define DIV_SHIFT             7
#define RAM_TEST_BYTES        512
#define RAM_TEST_STEP         31

// Журнал в EEPROM - в конце EEPROM (не мешает настройкам будущей прошивки в начале)
#define LOG_MAGIC             0xC1F1    // 0xC1F0 - журнал без учёта пониженного питания (сбросится)

// Тест CLKPR: Timer1 с делителем 64 считает такты CPU за период WDT 16 мс (16 МГц: ~4000 тиков, разброс
// генератора WDT - десятки %, но отношение при делителе 1 и 2 от него не зависит)
#define CLK_TEST_TIMER_DIV    64
#define CLK_TEST_WDT_US       16000UL
#define CLK_RATIO_X100_MIN    190       // отношение тиков (x100) при делителе 1 и 2: норма 200
#define CLK_RATIO_X100_MAX    210
#define CLK_TEST_TIMEOUT      0xFFFF    // флаг WDIF не появился
#define WDT_WAIT_LOOPS        1000000UL // ограничение ожидания флага (~0.5-1 с)
// UBRR (U2X) для SERIAL_BAUD при F_CPU / 2, с округлением: 16 МГц -> 25 (38 462 бод), 8 МГц -> 12 (38 462 бод)
#define UBRR_HALF_CPU         ((F_CPU / 2 + 4UL * SERIAL_BAUD) / (8UL * SERIAL_BAUD) - 1)
#define WARM_MAGIC            0x5AA5
#define WDT_MAGIC             0xA55A
#define WDT_TEST_MAGIC        0x3CC3

// Отпечаток ядра: такты на команду у ATmega328P (даташит, Instruction Set Summary)
#define TIMING_REPEAT         16        // команд в блоке (REP16)
#define CYC_NOP               1
#define CYC_LPM               3
#define CYC_LD                2
#define CYC_MUL               2
#define CYC_RJMP              2
#define CYC_CLR               1         // clr __zero_reg__ после MUL
#define SIGRD_CHECK_FIRST     4         // с этого адреса сравнивать «подпись» с flash

// Служебные байты, по которым сравнивались оригинал и подделка (microfarad.de): 5, 9, 11, 15-19, 21-29
static const uint8_t SERVICE_BYTES[] PROGMEM = { 5, 9, 11, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29 };

struct TestLog {
    uint16_t magic;
    uint16_t boots;        // включений и сбросов
    uint16_t warmResets;   // сбросов без пропадания питания (ОЗУ сохранилось)
    uint16_t wdtResets;    // зависаний (сработал сторожевой таймер)
    uint32_t seconds;      // наработка теста, с
    uint32_t passes;       // проходов теста
    uint32_t errCpu;       // CRC32 вычислений не совпала с эталоном
    uint32_t errDiv;       // ошибка деления
    uint32_t errRam;       // ошибка ОЗУ
    uint32_t errFlash;     // CRC flash изменилась
    uint16_t vccMin;       // мВ
    uint16_t vccMax;       // мВ
    uint8_t  lastMcusr;    // флаги сброса последнего старта (0 - стёр загрузчик)
    uint32_t secondsLow;   // наработка при Vcc < LOW_VCC_MV, с
    uint32_t errLow;       // ошибок при Vcc < LOW_VCC_MV
};

#define LOG_ADDR              (E2END + 1 - sizeof(TestLog))
#define EE_TEST_ADDR          (LOG_ADDR - 1)

extern char __data_load_end;            // конец этой программы во flash (код + начальные данные)

// Переживают сброс без пропадания питания (не обнуляются при старте)
uint8_t  g_mcusr     __attribute__((section(".noinit")));
uint16_t g_warmMagic __attribute__((section(".noinit")));
volatile uint16_t g_wdtFired __attribute__((section(".noinit")));
uint16_t g_wdtTest  __attribute__((section(".noinit")));     // идёт тест «w»

static TestLog  s_log;
static uint8_t  s_ram[RAM_TEST_BYTES];
static uint16_t s_flashCrcRef;
static uint32_t s_errSinceBoot;
static uint32_t s_errSaved;
static uint8_t  s_pass;
static uint16_t s_vcc;
static bool     s_testOn;               // идёт стресс-тест (Vcc < LOW_VCC_MV)
static bool     s_isAtmel;              // подпись прочитана и это ATmega 32 КБ - фьюзы и датчик достоверны
static volatile uint8_t s_ldTarget;     // ячейка для замера LD

// Флаги сброса - до инициализации C (загрузчик может их уже стереть) и выключить сторож после его сброса
void saveMcusr(void) __attribute__((naked, used, section(".init3")));
void saveMcusr(void)
{
    g_mcusr = MCUSR;
    MCUSR = 0;
    wdt_disable();
}

// Сторож в режиме «прерывание + сброс»: сначала прерывание (отметка в .noinit), на следующем таймауте - сброс
ISR(WDT_vect)
{
    g_wdtFired = WDT_MAGIC;
}

// ------------------------------------------------------------------ вывод
static void printHex(uint8_t v)
{
    if (v < 0x10) Serial.print('0');
    Serial.print(v, HEX);
}

static void printHex16(uint16_t v)
{
    printHex(v >> 8);
    printHex(v & 0xFF);
}

static uint8_t sigByte(uint8_t addr)
{
    uint8_t v;
    ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { v = boot_signature_byte_get(addr); }
    return v;
}

static uint8_t fuseByte(uint8_t which)
{
    uint8_t v;
    ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { v = boot_lock_fuse_bits_get(which); }
    return v;
}

// ------------------------------------------------------------------ АЦП
static uint16_t adcConvert()
{
    ADCSRA |= _BV(ADSC);
    while (ADCSRA & _BV(ADSC)) {}
    return ADC;
}

static void adcSelect(uint8_t admux)
{
    ADMUX = admux;
    for (uint8_t i = 0; i < ADC_SETTLE_CONV; i++) adcConvert();   // установление опорного и 1.1 В
}

static uint16_t adcAverage()
{
    uint32_t sum = 0;
    for (uint8_t i = 0; i < ADC_SAMPLES; i++) sum += adcConvert();
    return (uint16_t)(sum / ADC_SAMPLES);
}

static uint16_t measureVcc()          // вход АЦП уже переключён на 1.1 В (adcSelect в setup / после отчёта)
{
    const uint16_t bg = adcAverage();
    return bg ? (uint16_t)(BANDGAP_MV * ADC_FULL_SCALE / bg) : 0;
}

static uint32_t maxKhz(uint16_t mv)
{
    if (mv < SG_V1_MV) return 0;
    if (mv < SG_V2_MV) return SG_F1_KHZ + (mv - SG_V1_MV) * (SG_F2_KHZ - SG_F1_KHZ) / (SG_V2_MV - SG_V1_MV);
    if (mv < SG_V3_MV) return SG_F2_KHZ + (mv - SG_V2_MV) * (SG_F3_KHZ - SG_F2_KHZ) / (SG_V3_MV - SG_V2_MV);
    return SG_F3_KHZ;
}

// ------------------------------------------------------------------ отчёт: подпись и тип чипа
static void reportSignature()
{
    uint8_t row[SIGROW_SIZE];
    for (uint8_t i = 0; i < SIGROW_SIZE; i++) row[i] = sigByte(i);

    Serial.println(F("--- Область подписи (32 байта) ---"));
    for (uint8_t i = 0; i < SIGROW_SIZE; i++) {
        printHex(row[i]);
        Serial.print((i % 16 == 15) ? '\n' : ' ');
    }

    uint8_t guid[LGT_GUID_COUNT];
    bool guidZero = true, guidFF = true;
    for (uint8_t i = 0; i < LGT_GUID_COUNT; i++) {
        guid[i] = _SFR_MEM8(LGT_GUID_FIRST + i);
        if (guid[i] != 0x00) guidZero = false;
        if (guid[i] != 0xFF) guidFF = false;
    }
    Serial.print(F("Регистры 0xF3-0xF6 (GUID LGT8F): "));
    for (uint8_t i = 0; i < LGT_GUID_COUNT; i++) { printHex(guid[i]); Serial.print(' '); }
    Serial.println();

    bool asFlash = true;                 // SIGRD не работает: «подпись» = содержимое flash
    for (uint8_t i = SIGRD_CHECK_FIRST; i < SIGROW_SIZE; i++)
        if (row[i] != pgm_read_byte(i)) asFlash = false;
    const bool atmel = !asFlash && row[SIGROW_SIG0] == SIG_ATMEL && row[SIGROW_SIG1] == SIG_32K;
    s_isAtmel = atmel;
    if (asFlash)
        Serial.println(F("!!! Чтение подписи не поддерживается: вместо неё читается flash. Это НЕ ATmega\n"
                         "    (оригинал и известные подделки подпись отдают) - клон другого производителя"));
    Serial.print(F("Подпись: "));
    printHex(row[SIGROW_SIG0]); Serial.print(' ');
    printHex(row[SIGROW_SIG1]); Serial.print(' ');
    printHex(row[SIGROW_SIG2]);
    Serial.print(F("  -> "));
    if (!atmel) {
        uint8_t guidBytes = 0;           // у LGT8F GUID - случайный номер: ненулевых байтов должно быть несколько
        for (uint8_t i = 0; i < LGT_GUID_COUNT; i++) if (guid[i] != 0x00 && guid[i] != 0xFF) guidBytes++;
        if (!guidZero && !guidFF && guidBytes >= LGT_GUID_MIN_BYTES)
            Serial.println(F("возможно LGT8F328P / AVGA328P (есть GUID) - сверить с таймингами команд"));
        else
            Serial.println(F("НЕ Atmel/Microchip, производитель не опознан"));
    }
    else if (row[SIGROW_SIG2] == SIG_328P)  Serial.println(F("ATmega328P"));
    else if (row[SIGROW_SIG2] == SIG_328)   Serial.println(F("ATmega328 (без P) - если на корпусе 328P, это перемаркировка"));
    else if (row[SIGROW_SIG2] == SIG_328PB) Serial.println(F("ATmega328PB"));
    else                                    Serial.println(F("неизвестная модель 32 КБ"));
    if (atmel && !guidZero)
        Serial.println(F("  Внимание: по адресам GUID LGT8F не нули - необычно для ATmega"));

    Serial.print(F("OSCCAL заводской: 0x")); printHex(row[SIGROW_OSCCAL]);
    Serial.print(F(", текущий: 0x"));        printHex(OSCCAL);
    Serial.println();

    Serial.print(F("Партия/пластина/координаты (0x0E-0x17): "));
    for (uint8_t i = SIGROW_SERIAL_FIRST; i <= SIGROW_SERIAL_LAST; i++) { printHex(row[i]); Serial.print(' '); }
    Serial.println();

    if (!atmel) return;
    uint8_t ff = 0;
    for (uint8_t i = 0; i < sizeof(SERVICE_BYTES); i++)
        if (row[pgm_read_byte(&SERVICE_BYTES[i])] == 0xFF) ff++;
    Serial.print(F("Служебных байтов = FF: ")); Serial.print(ff);
    Serial.print('/'); Serial.print(sizeof(SERVICE_BYTES));
    Serial.print(F("  -> "));
    if (ff >= FAKE_FF_MIN)         Serial.println(F("КАК У ИЗВЕСТНЫХ ПОДДЕЛОК (клон кристалла)"));
    else if (ff <= GENUINE_FF_MAX) Serial.println(F("как у оригинала"));
    else                           Serial.println(F("неясно"));
}

// ------------------------------------------------------------------ отчёт: фьюзы и загрузчик
static void reportFuses()
{
    const uint8_t lo   = fuseByte(GET_LOW_FUSE_BITS);
    const uint8_t hi   = fuseByte(GET_HIGH_FUSE_BITS);
    const uint8_t ext  = fuseByte(GET_EXTENDED_FUSE_BITS);
    const uint8_t lock = fuseByte(GET_LOCK_BITS);

    Serial.println(F("--- Фьюзы ---"));
    Serial.print(F("low 0x"));    printHex(lo);
    Serial.print(F("  high 0x")); printHex(hi);
    Serial.print(F("  ext 0x"));  printHex(ext);
    Serial.print(F("  lock 0x")); printHex(lock);
    Serial.println();
    if (!s_isAtmel) {
        Serial.println(F("Чип не ATmega - фьюзы из программы не читаются (обычно это байты flash 0-3), расшифровка пропущена"));
    } else {
        Serial.print(F("BOD (сброс при снижении питания): "));
        switch (ext & EFUSE_BOD_MASK) {
            case BOD_OFF: Serial.println(F("выключен")); break;
            case BOD_1V8: Serial.println(F("1.8 В")); break;
            case BOD_2V7: Serial.println(F("2.7 В")); break;
            case BOD_4V3: Serial.println(F("4.3 В - ПРИ 3.3 В МК РАБОТАТЬ НЕ БУДЕТ (постоянный сброс)")); break;
            default:      Serial.println(F("недопустимое значение")); break;
        }

        // Размер загрузочной секции по BOOTSZ (даташит, табл. «Boot Size Configuration»): 11 - 512 б ... 00 - 4 КБ
        const uint8_t bootsz = (hi >> HFUSE_BOOTSZ_SHIFT) & HFUSE_BOOTSZ_MASK;
        const uint16_t bootBytes = 512U << (HFUSE_BOOTSZ_MASK - bootsz);
        const bool bootRst = !(hi & _BV(HFUSE_BOOTRST_BIT));          // 0 = запрограммирован
        Serial.print(F("Загрузочная секция (BOOTSZ): ")); Serial.print(bootBytes);
        Serial.print(F(" б с адреса 0x")); printHex16((uint16_t)(FLASH_SIZE - bootBytes));
        Serial.print(F(", старт с загрузчика (BOOTRST): ")); Serial.println(bootRst ? F("да") : F("нет"));
    }

    // Где реально лежит загрузчик: первый не-FF байт после конца этой программы
    uint16_t a = (uint16_t)(uintptr_t)&__data_load_end;
    while (a < FLASH_SIZE - 1 && pgm_read_byte(a) == 0xFF) a++;
    Serial.print(F("Программа до 0x")); printHex16((uint16_t)(uintptr_t)&__data_load_end);
    Serial.print(F(", загрузчик (первый не-FF) с 0x")); printHex16(a);
    Serial.print(F(", занято ~")); Serial.print((uint16_t)(FLASH_SIZE - a)); Serial.println(F(" б"));

    Serial.print(F("Последние байты flash: "));
    for (uint16_t i = FLASH_SIZE - FLASH_TAIL_DUMP; i < FLASH_SIZE; i++) {
        printHex(pgm_read_byte(i));
        Serial.print(' ');
    }
    Serial.println();
}

// ------------------------------------------------------------------ отчёт: такты команд (отпечаток ядра)
#define REP4(x)   x x x x
#define REP16(x)  REP4(x) REP4(x) REP4(x) REP4(x)

// Чтение TCNT1 (сначала младший байт - защёлка старшего) и замеряемый блок - в одной вставке: компилятор не может
// ничего вставить между чтениями таймера, указатели и операнды загружаются до первого чтения.
#define T_START   "lds %A[t0], %[lo]\n\t" "lds %B[t0], %[hi]\n\t"
#define T_STOP    "lds %A[t1], %[lo]\n\t" "lds %B[t1], %[hi]\n\t"
#define T_OUT     [t0] "=&r"(t0), [t1] "=&r"(t1)
#define T_IN      [lo] "n"(_SFR_MEM_ADDR(TCNT1L)), [hi] "n"(_SFR_MEM_ADDR(TCNT1H))

static uint16_t tEmpty()
{
    uint16_t t0, t1;
    asm volatile(T_START T_STOP : T_OUT : T_IN : "memory");
    return t1 - t0;
}

static uint16_t tNop()
{
    uint16_t t0, t1;
    asm volatile(T_START REP16("nop\n\t") T_STOP : T_OUT : T_IN : "memory");
    return t1 - t0;
}

static uint16_t tRjmp()
{
    uint16_t t0, t1;
    asm volatile(T_START REP16("rjmp .+0\n\t") T_STOP : T_OUT : T_IN : "memory");
    return t1 - t0;
}

static uint16_t tLpm()
{
    uint16_t t0, t1;
    asm volatile(T_START REP16("lpm __tmp_reg__, Z\n\t") T_STOP : T_OUT : T_IN, "z"((uint16_t)0) : "memory");
    return t1 - t0;
}

static uint16_t tLd()
{
    uint16_t t0, t1;
    asm volatile(T_START REP16("ld __tmp_reg__, %a[p]\n\t") T_STOP : T_OUT : T_IN, [p] "e"(&s_ldTarget) : "memory");
    return t1 - t0;
}

static uint16_t tMul()
{
    uint16_t t0, t1;
    const uint8_t x = TIMING_REPEAT;
    asm volatile(T_START REP16("mul %[x], %[x]\n\t") "clr __zero_reg__\n\t" T_STOP
                 : T_OUT : T_IN, [x] "r"(x) : "r0", "memory");
    return t1 - t0;
}

static uint16_t measureCycles(uint16_t (*fn)())
{
    uint16_t t;
    ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
        const uint8_t a = TCCR1A, b = TCCR1B;           // Timer1 занят ядром под ШИМ D9/D10 - восстановить
        TCCR1A = 0;
        TCCR1B = _BV(CS10);                              // нормальный режим, такт CPU без делителя
        t = fn();
        TCCR1A = a;
        TCCR1B = b;
    }
    return t;
}

static bool printCycles(const __FlashStringHelper* name, uint16_t (*fn)(), uint16_t base, uint16_t expect)
{
    const uint16_t c = measureCycles(fn) - base;
    Serial.print(name); Serial.print(F(" x")); Serial.print(TIMING_REPEAT);
    Serial.print(F(": ")); Serial.print(c);
    Serial.print(F(" тактов (ATmega: ")); Serial.print(expect); Serial.print(')');
    Serial.println(c == expect ? F("") : F("  <- ОТЛИЧИЕ"));
    return c == expect;
}

static void reportTiming()
{
    Serial.println(F("--- Такты команд (отпечаток ядра) ---"));
    const uint16_t base = measureCycles(tEmpty);
    bool same = true;
    same &= printCycles(F("NOP "), tNop,  base, TIMING_REPEAT * CYC_NOP);
    same &= printCycles(F("RJMP"), tRjmp, base, TIMING_REPEAT * CYC_RJMP);
    same &= printCycles(F("LPM "), tLpm,  base, TIMING_REPEAT * CYC_LPM);
    same &= printCycles(F("LD  "), tLd,   base, TIMING_REPEAT * CYC_LD);
    same &= printCycles(F("MUL "), tMul,  base, TIMING_REPEAT * CYC_MUL + CYC_CLR);
    Serial.println(same ? F("Тайминги как у ядра AVR (ATmega)") : F("Тайминги ОТЛИЧАЮТСЯ от ATmega - другое ядро"));
}

// ------------------------------------------------------------------ отчёт: питание и температура
static void reportAnalog()
{
    Serial.println(F("--- Питание и температура ---"));
    adcSelect(_BV(REFS1) | _BV(REFS0) | ADC_MUX_TEMP);
    const uint16_t t = adcAverage();
    adcSelect(_BV(REFS0) | ADC_MUX_BANDGAP);                         // обратно - замер Vcc для теста
    const uint16_t vcc = measureVcc();
    const long mv = (long)t * (long)BANDGAP_MV / (long)ADC_FULL_SCALE;

    Serial.print(F("Vcc ~ ")); Serial.print(vcc);
    Serial.print(F(" мВ (по 1.1 В, точность ~10%), допустимо по даташиту до ~"));
    Serial.print(maxKhz(vcc) / 1000); Serial.print(F(" МГц, работаем на "));
    Serial.print(F_CPU / 1000000UL); Serial.println(F(" МГц"));
    Serial.print(F("Датчик температуры: АЦП ")); Serial.print(t);
    if (s_isAtmel) {
        Serial.print(F(", ~")); Serial.print(TEMP_REF_C + (mv - TEMP_MV_AT_25C));
        Serial.println(F(" C (грубо, +-10 C без калибровки)"));
    } else {
        Serial.println(F(" (чип не ATmega - пересчёт в C и Vcc не гарантированы)"));
    }
}

// ------------------------------------------------------------------ журнал EEPROM
static void logClear()
{
    memset(&s_log, 0, sizeof(s_log));
    s_log.magic  = LOG_MAGIC;
    s_log.vccMin = UINT16_MAX;
}

static void logSave()
{
    EEPROM.put(LOG_ADDR, s_log);               // пишет только изменившиеся байты
    s_errSaved = s_errSinceBoot;
}

static void printLog()
{
    Serial.println(F("--- Журнал теста (EEPROM, копится между включениями) ---"));
    Serial.print(F("Наработка ")); Serial.print(s_log.seconds);
    Serial.print(F(" с, проходов ")); Serial.println(s_log.passes);
    Serial.print(F("Стартов ")); Serial.print(s_log.boots);
    Serial.print(F(", сбросов без пропадания питания ")); Serial.print(s_log.warmResets);
    Serial.print(F(", зависаний (сторож) ")); Serial.println(s_log.wdtResets);
    Serial.print(F("Ошибки: CPU ")); Serial.print(s_log.errCpu);
    Serial.print(F(", деление ")); Serial.print(s_log.errDiv);
    Serial.print(F(", ОЗУ ")); Serial.print(s_log.errRam);
    Serial.print(F(", flash ")); Serial.println(s_log.errFlash);
    Serial.print(F("Vcc мин/макс: "));
    if (s_log.vccMax) { Serial.print(s_log.vccMin); Serial.print('/'); Serial.print(s_log.vccMax); Serial.println(F(" мВ")); }
    else              Serial.println(F("нет данных"));
    Serial.print(F("При пониженном питании (Vcc < ")); Serial.print(LOW_VCC_MV);
    Serial.print(F(" мВ): наработка ")); Serial.print(s_log.secondsLow);
    Serial.print(F(" с, ошибок ")); Serial.println(s_log.errLow);
    Serial.print(F("MCUSR последнего старта: 0x")); printHex(s_log.lastMcusr);
    Serial.println(F(" (бит 0 - питание, 1 - кнопка, 2 - BOD, 3 - сторож; 0 - стёр загрузчик)"));
}

static void eepromCellTest()
{
    const uint8_t old = EEPROM.read(EE_TEST_ADDR);
    EEPROM.write(EE_TEST_ADDR, 0x55);
    const bool ok1 = EEPROM.read(EE_TEST_ADDR) == 0x55;
    EEPROM.write(EE_TEST_ADDR, 0xAA);
    const bool ok2 = EEPROM.read(EE_TEST_ADDR) == 0xAA;
    EEPROM.write(EE_TEST_ADDR, old);
    Serial.print(F("EEPROM ячейка ")); Serial.print((uint16_t)EE_TEST_ADDR);
    Serial.println(ok1 && ok2 ? F(": OK") : F(": ОШИБКА"));
}

// ------------------------------------------------------------------ тест делителя CLKPR
// 1) Эталон - компьютер: при делителе 2 скорость UART пересчитывается под F_CPU / 2 (U2X, UBRR0 = UBRR_HALF_CPU).
//    Делитель работает - строка в мониторе читается; не работает (CPU остался на F_CPU) - скорость x2, мусор.
// 2) Эталон - генератор WDT (опрос флага WDIF с ограничением по времени) + вывод WDTCSR для диагностики клона.
static uint8_t s_wdtcsrCfg, s_wdtcsrClr;
static uint32_t s_wdifClearLoops;        // циклов ожидания, пока сброс WDIF дойдёт до регистра

static bool waitWdif()
{
    for (uint32_t n = WDT_WAIT_LOOPS; n; n--)
        if (WDTCSR & _BV(WDIF)) return true;
    return false;
}

// Тиков Timer1 за один период WDT 16 мс (0xFFFF - флаг не появился). Вызывать при запрещённых прерываниях.
static uint16_t wdtPeriodTicks()
{
    wdt_reset();
    WDTCSR = _BV(WDCE) | _BV(WDE);                       // разрешение изменения
    WDTCSR = _BV(WDIF) | _BV(WDIE);                      // только прерывание, 16 мс, флаг сброшен
    s_wdtcsrCfg = WDTCSR;
    if (!waitWdif()) return CLK_TEST_TIMEOUT;            // синхронизация с генератором WDT
    WDTCSR = _BV(WDIF) | _BV(WDIE);                      // сброс флага (WDE и WDP не меняются)
    s_wdtcsrClr = WDTCSR;                                // сразу после записи (у клона - ещё 0xC0)
    s_wdifClearLoops = 0;                                // у клона запись доходит с задержкой - дождаться
    while (WDTCSR & _BV(WDIF))
        if (++s_wdifClearLoops >= WDT_WAIT_LOOPS) return CLK_TEST_TIMEOUT;
    TCNT1 = 0;
    if (!waitWdif()) return CLK_TEST_TIMEOUT;
    return TCNT1;
}

static void printTicks(uint16_t t)
{
    if (t == CLK_TEST_TIMEOUT) Serial.print(F("нет флага"));
    else                       Serial.print(t);
}

static void clockTest()
{
    Serial.println(F("--- Делитель частоты CLKPR ---"));

    // 1) Компьютер как эталон
    Serial.println(F("Сейчас: делитель 2 + скорость UART под F_CPU / 2. Следующая строка должна читаться:"));
    Serial.flush();
    const uint16_t ubrr = UBRR0;
    const uint8_t  ucsra = UCSR0A;
    clock_prescale_set(clock_div_2);
    UCSR0A = ucsra | _BV(U2X0);
    UBRR0 = UBRR_HALF_CPU;
    Serial.println(F(">>> ДЕЛИТЕЛЬ РАБОТАЕТ: CPU на F_CPU / 2, строка передана при пересчитанной скорости <<<"));
    Serial.flush();
    clock_prescale_set(clock_div_1);
    UBRR0 = ubrr;
    UCSR0A = ucsra;
    Serial.println(F("(вместо строки выше мусор - делитель НЕ работает)"));

    // 2) Генератор WDT как эталон
    uint16_t t1, t2;
    ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
        const uint8_t a = TCCR1A, b = TCCR1B;
        TCCR1A = 0;
        TCCR1B = _BV(CS11) | _BV(CS10);                  // делитель 64
        t1 = wdtPeriodTicks();
        clock_prescale_set(clock_div_2);
        t2 = wdtPeriodTicks();
        clock_prescale_set(clock_div_1);
        TCCR1A = a;
        TCCR1B = b;
        wdt_enable(WDTO_2S);                             // вернуть сторож теста
        WDTCSR |= _BV(WDIF) | _BV(WDIE);                 // сбросить флаг замера (иначе - ложное «зависание»)
    }
    Serial.print(F("WDT: WDTCSR после настройки 0x")); printHex(s_wdtcsrCfg);
    Serial.print(F(", после сброса флага 0x"));        printHex(s_wdtcsrClr);
    Serial.println(F(" (ATmega: 0x40 и 0x40)"));
    Serial.print(F("Сброс флага WDIF дошёл через ")); Serial.print(s_wdifClearLoops);
    Serial.println(F(" циклов опроса (ATmega: 0)"));
    Serial.print(F("Период WDT в тиках Timer1/64: делитель 1 - ")); printTicks(t1);
    Serial.print(F(", делитель 2 - ")); printTicks(t2);
    if (t1 != CLK_TEST_TIMEOUT && t2 != CLK_TEST_TIMEOUT && t1 && t2) {
        const uint16_t ratio = (uint16_t)((uint32_t)t1 * 100UL / t2);
        Serial.print(F(", отношение ")); Serial.print(ratio / 100); Serial.print('.');
        if (ratio % 100 < 10) Serial.print('0');
        Serial.println(ratio % 100);
        Serial.print(F("Частота CPU по WDT (грубо): ~"));
        Serial.print((uint32_t)t1 * CLK_TEST_TIMER_DIV * 1000UL / CLK_TEST_WDT_US);
        Serial.println(F(" кГц"));
        Serial.println(ratio >= CLK_RATIO_X100_MIN && ratio <= CLK_RATIO_X100_MAX
                       ? F("По WDT: делитель 2 даёт половину частоты")
                       : F("По WDT: отношение не 2"));
    } else {
        Serial.println();
        Serial.println(F("По WDT замер невозможен: флаг WDIF ведёт себя не как у ATmega"));
    }
}

// ------------------------------------------------------------------ тест сторожа (режим сброса)
static void wdtResetTest()
{
    Serial.println(F("--- Тест сторожа: зависаю. Отчёт должен появиться САМ через ~2-4 с."));
    Serial.println(F("    Нет отчёта 10 с - сторож в режиме сброса НЕ работает, нажмите RESET."));
    Serial.flush();
    g_wdtTest = WDT_TEST_MAGIC;
    cli();
    wdt_enable(WDTO_2S);                                 // только сброс (WDIE выключен), как в рабочей прошивке
    for (;;) {}
}

// ------------------------------------------------------------------ стресс-тест
static void noteError()
{
    s_errSinceBoot++;
    if (s_vcc && s_vcc < LOW_VCC_MV) s_log.errLow++;
}

static uint32_t crc32Byte(uint32_t crc, uint8_t b)
{
    crc ^= b;
    for (uint8_t k = 0; k < 8; k++) crc = (crc & 1) ? (crc >> 1) ^ CRC32_POLY : crc >> 1;
    return crc;
}

static bool testCpu()                  // генератор + CRC32: тот же алгоритм, что Scripts/chipinfo_crc_ref.py
{
    uint32_t x = CPU_XS_SEED, y = CPU_LCG_SEED, crc = CRC32_INIT;
    for (uint16_t i = 0; i < CPU_TEST_BYTES; i++) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        y = y * CPU_LCG_MUL + CPU_LCG_ADD;
        crc = crc32Byte(crc, (uint8_t)((x >> 24) ^ (y >> 16)));
    }
    return (crc ^ CRC32_INIT) == CPU_TEST_CRC_REF;
}

static bool testDiv()
{
    static volatile uint32_t seed = CPU_XS_SEED;
    bool ok = true;
    for (uint8_t i = 0; i < DIV_TEST_COUNT; i++) {
        uint32_t x = seed;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        seed = x;
        const uint16_t d = (uint16_t)(x >> DIV_SHIFT) | 1;
        const uint32_t q = x / d, r = x % d;
        if (q * d + r != x || r >= d) ok = false;
    }
    return ok;
}

static bool testRam()
{
    volatile uint8_t* p = s_ram;
    bool ok = true;
    for (uint16_t i = 0; i < RAM_TEST_BYTES; i++) p[i] = (uint8_t)(i * RAM_TEST_STEP + s_pass);
    for (uint16_t i = 0; i < RAM_TEST_BYTES; i++) if (p[i] != (uint8_t)(i * RAM_TEST_STEP + s_pass)) ok = false;
    for (uint16_t i = 0; i < RAM_TEST_BYTES; i++) p[i] = (uint8_t)~(i * RAM_TEST_STEP + s_pass);
    for (uint16_t i = 0; i < RAM_TEST_BYTES; i++) if (p[i] != (uint8_t)~(i * RAM_TEST_STEP + s_pass)) ok = false;
    s_pass++;
    return ok;
}

static uint16_t flashCrc()
{
    uint16_t crc = UINT16_MAX;
    const uint16_t end = (uint16_t)(uintptr_t)&__data_load_end;
    for (uint16_t a = 0; a < end; a++) crc = _crc16_update(crc, pgm_read_byte(a));
    return crc;
}

static void printStatus()
{
    Serial.print(F("t=")); Serial.print(s_log.seconds);
    Serial.print(F(" с  Vcc=")); Serial.print(s_vcc);
    Serial.print(F(" мВ (до ~")); Serial.print(maxKhz(s_vcc) / 1000);
    Serial.print(F(" МГц)  проходов ")); Serial.print(s_log.passes);
    Serial.print(F("  ошибок с включения ")); Serial.print(s_errSinceBoot);
    Serial.print(F(" (CPU/дел/ОЗУ/flash всего ")); Serial.print(s_log.errCpu);
    Serial.print('/'); Serial.print(s_log.errDiv);
    Serial.print('/'); Serial.print(s_log.errRam);
    Serial.print('/'); Serial.print(s_log.errFlash);
    Serial.println(')');
}

static void report()
{
    Serial.println();
    Serial.println(F("===== ChipInfo ====="));
    Serial.print(F("F_CPU сборки: ")); Serial.println(F_CPU);
    reportSignature();
    reportFuses();
    reportTiming();
    reportAnalog();
    printLog();
    Serial.println(F("Команды: r - отчёт, l - журнал, c - очистить журнал, e - тест ячейки EEPROM, k - тест CLKPR"));
}

void setup()
{
    const bool warm = g_warmMagic == WARM_MAGIC;            // ОЗУ сохранилось - сброс без пропадания питания
    const bool wdt  = warm && g_wdtFired == WDT_MAGIC;
    const bool wdtTest = warm && g_wdtTest == WDT_TEST_MAGIC;
    g_wdtTest = 0;
    g_warmMagic = WARM_MAGIC;
    g_wdtFired = 0;

    EEPROM.get(LOG_ADDR, s_log);
    if (s_log.magic != LOG_MAGIC) logClear();
    s_log.boots++;
    if (warm) s_log.warmResets++;
    if (wdt)  s_log.wdtResets++;
    s_log.lastMcusr = g_mcusr;
    logSave();

    pinMode(LED_BUILTIN, OUTPUT);
    Serial.begin(SERIAL_BAUD);
    delay(USB_WAIT_MS);
    if (wdt) Serial.println(F("!!! Предыдущий запуск завис (сработал сторожевой таймер)"));
    if (wdtTest) Serial.println(F("Перезапуск после теста сторожа «w»: если отчёт появился сам - сторож работает;\n"
                                   "если нажимали RESET - не работает"));
    report();

    s_flashCrcRef = flashCrc();
    s_vcc = measureVcc();                                  // вход АЦП - 1.1 В (выставлен в reportAnalog)
    s_testOn = s_vcc && s_vcc < LOW_VCC_MV;
    Serial.println(s_testOn ? F("Vcc < 4 В - стресс-тест запущен")
                            : F("Vcc >= 4 В - стресс-тест ждёт пониженного питания"));
    wdt_enable(WDTO_2S);
    WDTCSR |= _BV(WDIE);                                    // сначала прерывание (отметка), потом сброс
}

void loop()
{
    static uint32_t tStatus = 0, tLed = 0, tSave = 0, tErrSave = 0;
    const uint32_t now = millis();

    wdt_reset();

    // Один проход теста - только при пониженном питании
    if (s_testOn) {
        if (!testCpu()) { s_log.errCpu++; noteError(); }
        if (!testDiv()) { s_log.errDiv++; noteError(); }
        if (!testRam()) { s_log.errRam++; noteError(); }
        s_log.passes++;
    }

    // Раз в секунду: flash, Vcc, строка состояния
    if (now - tStatus >= STATUS_MS) {
        tStatus = now;
        s_vcc = measureVcc();
        const bool low = s_vcc && s_vcc < LOW_VCC_MV;
        if (low != s_testOn) {
            s_testOn = low;
            Serial.println(low ? F("Vcc < 4 В - стресс-тест запущен") : F("Vcc >= 4 В - стресс-тест остановлен"));
            if (!low) { logSave(); digitalWrite(LED_BUILTIN, LOW); }   // итог прогона - в EEPROM
        }
        if (s_testOn) {
            if (flashCrc() != s_flashCrcRef) { s_log.errFlash++; noteError(); }
            s_log.secondsLow++;
            if (s_vcc < s_log.vccMin) s_log.vccMin = s_vcc;
            if (s_vcc > s_log.vccMax) s_log.vccMax = s_vcc;
            s_log.seconds++;
            printStatus();
        }
    }

    // Журнал в EEPROM
    if (s_testOn && (now - tSave >= LOG_SAVE_MS || (s_errSinceBoot != s_errSaved && now - tErrSave >= LOG_ERR_SAVE_MS))) {
        tSave = tErrSave = now;
        logSave();
    }

    // Светодиод: 1 Гц - ошибок нет, 5 Гц - были
    if (s_testOn && now - tLed >= (s_errSinceBoot ? LED_ERR_HALF_MS : LED_OK_HALF_MS)) {
        tLed = now;
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }

    // Команды
    if (Serial.available()) {
        const char c = Serial.read();
        if (c == 'r') report();
        else if (c == 'l') printLog();
        else if (c == 'c') { logClear(); logSave(); Serial.println(F("Журнал очищен")); }
        else if (c == 'e') eepromCellTest();
        else if (c == 'k') clockTest();
        else if (c == 'w') wdtResetTest();
    }
}
