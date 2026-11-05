// settings.h - настройки в EEPROM (Readme §6): период опроса, период тенденции, порог стрелки, прогрев, поворот,
// обмен кнопок, яркость, период мин / макс.
#pragma once
#include <stdint.h>

struct Settings {
    uint8_t pollIdx;     // индекс в POLL_PERIODS_S
    uint8_t trendIdx;    // индекс в TREND_PERIODS_MIN
    uint8_t thrC100;     // порог стрелки тенденции, сотые °C
    uint8_t heater;      // прогрев SHT40 при высокой влажности: 0 - нет, 1 - да
    uint8_t rot;         // поворот экрана: четверти оборота от TFT_ROTATION, 0 .. ROT_COUNT - 1
    uint8_t swapBtn;     // Кн.1 / Кн.2 местами: 0 - нет, 1 - да
    uint8_t brightIdx;   // индекс в BRIGHT_LEVELS
    uint8_t mmIdx;       // индекс в MINMAX_PERIODS_H
    int8_t  corrC10;     // поправка температуры, десятые °C: -TEMP_CORR_MAX_C10 ... +TEMP_CORR_MAX_C10
};

#define ROT_COUNT    4   // поворотов экрана: 0 / 90 / 180 / 270°
#define ROT_STEP_DEG 90

namespace Cfg {
extern Settings s;

void     load();                     // EEPROM -> s; ошибка версии / контрольной суммы / диапазона - умолчания
void     save();                     // s -> EEPROM (пишутся только изменившиеся байты)

uint8_t  pollCount();
uint8_t  trendCount();
uint8_t  pollS(uint8_t idx);         // период опроса, с
uint8_t  trendMin(uint8_t idx);      // период тенденции, мин
uint8_t  mmCount();
uint8_t  mmHours(uint8_t idx);       // период мин / макс, ч
inline uint8_t pollS()    { return pollS(s.pollIdx); }
inline uint8_t trendMin() { return trendMin(s.trendIdx); }
inline uint8_t mmHours()  { return mmHours(s.mmIdx); }
uint8_t  brightCount();
uint8_t  bright(uint8_t idx);        // яркость: % | BRIGHT_FAST
inline uint8_t bright()   { return bright(s.brightIdx); }
}
