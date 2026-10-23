// buttons.cpp - опрос кнопок по millis(): состояние принимается, если не менялось BTN_DEBOUNCE_MS.
// КН - отпускание раньше BTN_LONG_MS; ДН - удержание BTN_LONG_MS (событие сразу, отпускание после него - без события).
#include "buttons.h"
#include <Arduino.h>
#include "config.h"

namespace {
struct Btn {
    uint8_t  pin;
    BtnEvent shortEv, longEv;
    bool     raw, pressed, longFired;
    uint32_t tChange, tPress;
};

Btn s_btn[] = {
    { PIN_BTN1, BtnEvent::Short1, BtnEvent::Long1, false, false, false, 0, 0 },
    { PIN_BTN2, BtnEvent::Short2, BtnEvent::Long2, false, false, false, 0, 0 },
};

BtnEvent pollOne(Btn& b, uint32_t now)
{
    const bool raw = digitalRead(b.pin) == LOW;          // нажата - вывод на GND
    if (raw != b.raw) { b.raw = raw; b.tChange = now; }
    if (now - b.tChange >= BTN_DEBOUNCE_MS && raw != b.pressed) {
        b.pressed = raw;
        if (raw) { b.tPress = now; b.longFired = false; }
        else if (!b.longFired) return b.shortEv;
    }
    if (b.pressed && !b.longFired && now - b.tPress >= BTN_LONG_MS) {
        b.longFired = true;
        return b.longEv;
    }
    return BtnEvent::None;
}
}  // namespace

namespace Buttons {
void begin()
{
    for (Btn& b : s_btn) pinMode(b.pin, INPUT_PULLUP);
}

BtnEvent poll(uint32_t now)
{
    for (Btn& b : s_btn) {
        const BtnEvent e = pollOne(b, now);
        if (e != BtnEvent::None) return e;
    }
    return BtnEvent::None;
}
}  // namespace Buttons
