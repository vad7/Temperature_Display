// menu.h - пункты меню настроек (Readme §6): порядок строк на экране = порядок в MENU_ITEMS.
// Из списка получаются номера пунктов (ITEM_*) и строка названий (ui.cpp, MENU_NAMES); названия - шрифт
// Scripts/gen_font.py (ищет X(ITEM_..., "...") здесь).
#pragma once
#include <stdint.h>

#define MENU_ITEMS(X)                        \
    X(ITEM_THR,    "Прог стрел.")            \
    X(ITEM_TREND,  "Тенденция за")           \
    X(ITEM_MINMAX, "Мин/макс за")            \
    X(ITEM_POLL,   "Опрос датчика")          \
    X(ITEM_HEATER, "Прогрев")                \
    X(ITEM_CORR,   "Корр. °")                \
    X(ITEM_ROT,    "Поворот")                \
    X(ITEM_SWAP,   "Обмен кнопок")           \
    X(ITEM_BRIGHT, "Яркость")                \
    X(ITEM_ERRORS, "Ошибки")       /* не правится: неудачных чтений / пропавших измерений, ДН Кн.1 - сброс */

#define MENU_ENUM(id, name) id,
enum MenuItem : uint8_t { MENU_ITEMS(MENU_ENUM) ITEM_COUNT };
#undef MENU_ENUM
