// history.h - история температуры в ОЗУ: средние за TREND_SLOT_S (тенденция, мин / макс) и за GRAPH_SLOT_S (график).
#pragma once
#include <stdint.h>

#define HIST_NONE  INT16_MIN      // в точке нет данных (датчика не было весь интервал)

struct Trend {
    bool    valid;     // данных хватает для стрелки (не меньше половины периода)
    int16_t deltaC10;  // изменение за период, десятые °C
    bool    hasMinMax; // есть хоть одно значение
    int16_t minC10;
    int16_t maxC10;
};

namespace History {
void    add(int16_t c10);                     // очередное измерение
void    tick(uint32_t now);                   // закрывает интервалы по времени (в каждом проходе loop())
Trend   trend(uint8_t periodMin);             // тенденция и мин / макс за период
bool    takeGraphChanged();                   // добавилась точка графика (флаг сбрасывается)
uint8_t graphCount();                         // точек графика (до GRAPH_SLOTS)
int16_t graphAt(uint8_t i);                   // i = 0 - самая старая, graphCount() - 1 - последняя
}
