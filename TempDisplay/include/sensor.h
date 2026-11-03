// sensor.h - датчик температуры: автоопределение (сначала SHT40, затем DS18B20) и опрос по периоду.
#pragma once
#include <stdint.h>
#include "config.h"

namespace Sensor {
void       begin();
void       update(uint32_t now, uint8_t pollS, bool heater);  // в каждом проходе loop(); heater - опция прогрева
bool       heating();                            // SHT40 остывает после импульса нагревателя (показания не обновляются)
bool       takeFresh();                          // есть новое измерение с прошлого вызова (флаг сбрасывается)
SensorKind kind();                               // None - датчик не найден при включении
bool       failed();                             // последнее измерение пропало (все повторы неудачны)
uint16_t   errReads();                           // неудачных чтений с включения (с повторами)
uint16_t   errLost();                            // пропавших измерений с включения
void       resetErrors();
int16_t    tempC10();                            // последнее измерение + поправка «Корр. °», десятые °C
bool       hasHumidity();                        // только SHT40
uint8_t    humidity();                           // %, 0..100
}
