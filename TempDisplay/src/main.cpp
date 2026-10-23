// Fuses: у клонов из программы не читаются (ChipInfo). Ставит MiniCore при записи загрузчика urboot:
//        Clock External 8 MHz (Pro Mini 3.3 В; Nano - 16 MHz + делитель CLKPR по OSC_PRESCALER), BOD 2.7 В.
//
// Уличный термометр: ATmega328P (Pro Mini 3.3 В / 8 МГц) + SHT40 / DS18B20 (автоопределение) + SPI TFT ST7735S / ST7789V.
// Readme.md §6 - экраны и кнопки; config.h - пины и константы.
#include <Arduino.h>
#include <avr/wdt.h>
#include "buttons.h"
#include "config.h"
#include "history.h"
#include "sensor.h"
#include "settings.h"
#include "ui.h"

void setup()
{
    Cfg::load();
    Buttons::begin();
    Ui::begin();
    Sensor::begin();
    wdt_enable(WDT_TIMEOUT);                 // только режим сброса (см. config.h)
}

void loop()
{
    wdt_reset();
    const uint32_t now = millis();

    const SensorKind before = Sensor::kind();
    const bool heatBefore = Sensor::heating();
    Sensor::update(now, Cfg::pollS(), Cfg::s.heater);
    const bool fresh = Sensor::takeFresh();
    if (fresh) History::add(Sensor::tempC10());
    History::tick(now);
    if (fresh || Sensor::kind() != before || Sensor::heating() != heatBefore) Ui::onData();

    Ui::update(now, Buttons::poll(now));
}
