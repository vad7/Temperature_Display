// ui.h - экраны (Readme §6): главный, график за сутки, настройки; обработка кнопок и автовыход.
#pragma once
#include <stdint.h>
#include "buttons.h"

namespace Ui {
void begin();                              // экран, заставка без датчика, подсветка
void showSensor();                         // строка датчика на заставке (после Sensor::begin), отсчёт SPLASH_MS
void onData();                             // новое измерение / смена датчика - обновить значения
void update(uint32_t now, BtnEvent e);     // в каждом проходе loop()
}
