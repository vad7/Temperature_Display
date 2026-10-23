// sensor.h - датчик температуры: автоопределение (сначала SHT40, затем DS18B20) и опрос по периоду.
#pragma once
#include <stdint.h>
#include "config.h"

namespace Sensor {
void       begin();
void       update(uint32_t now, uint8_t pollS, bool heater);  // в каждом проходе loop(); heater - опция прогрева
bool       heating();                            // SHT40 остывает после импульса нагревателя (показания не обновляются)
bool       takeFresh();                          // есть новое измерение с прошлого вызова (флаг сбрасывается)
SensorKind kind();                               // None - датчика нет (идёт повторный поиск)
int16_t    tempC10();                            // последнее измерение, десятые °C
bool       hasHumidity();                        // только SHT40
uint8_t    humidity();                           // %, 0..100
}
