// settings.h - настройки в EEPROM (Readme §6): период опроса, период тенденции, порог стрелки, прогрев, переворот.
#pragma once
#include <stdint.h>

struct Settings {
    uint8_t pollIdx;     // индекс в POLL_PERIODS_S
    uint8_t trendIdx;    // индекс в TREND_PERIODS_MIN
    uint8_t thrC10;      // порог стрелки тенденции, десятые °C
    uint8_t heater;      // прогрев SHT40 при высокой влажности: 0 - выкл, 1 - вкл
    uint8_t flip;        // экран перевёрнут на 180° (кнопки меняются местами): 0 - нет, 1 - да
};

namespace Cfg {
extern Settings s;

void     load();                     // EEPROM -> s; ошибка версии / контрольной суммы / диапазона - умолчания
void     save();                     // s -> EEPROM (пишутся только изменившиеся байты)

uint8_t  pollCount();
uint8_t  trendCount();
uint8_t  pollS(uint8_t idx);         // период опроса, с
uint8_t  trendMin(uint8_t idx);      // период тенденции, мин
inline uint8_t pollS()    { return pollS(s.pollIdx); }
inline uint8_t trendMin() { return trendMin(s.trendIdx); }
}
