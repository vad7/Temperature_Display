// buttons.h - две кнопки на GND (внутренняя подтяжка): антидребезг, короткое (КН) и долгое (ДН) нажатие.
#pragma once
#include <stdint.h>

enum class BtnEvent : uint8_t { None, Short1, Long1, Short2, Long2 };

namespace Buttons {
void     begin();
BtnEvent poll(uint32_t now);   // не больше одного события за вызов; ДН - сразу по истечении BTN_LONG_MS
}
