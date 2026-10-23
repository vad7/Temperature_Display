// ui.cpp - экраны термометра. Альбомная ориентация, разметка - от tft.width() / tft.height().
//  Главный: крупная температура (7-сегментные цифры, рисуются прямоугольниками - без шрифта), стрелка тенденции
//           справа, макс - вверху слева, мин - внизу слева, влажность (SHT40) - внизу справа.
//  График:  24 ч, точки - средние за 10 мин, время справа налево (справа - сейчас).
//  Настройки: Кн.1 / Кн.2 - пункт (по кругу), ДН Кн.1 - правка / сохранить, ДН Кн.2 - выход.
// Текст - шрифт FontUiS / FontUiL (Scripts/gen_font.py: только используемые символы, ASCII - свои коды, остальные -
// по таблице FontUiMap[]); строки в исходнике - UTF-8, в PROGMEM, перекодируются utf8ToFont(). Кадрового буфера нет: перерисовываются только изменившиеся области.
#include "ui.h"
#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include "config.h"
#include "history.h"
#include "sensor.h"
#include "settings.h"

#if LCD_CTRL == LCD_ST7789
#include <Adafruit_ST7789.h>
static Adafruit_ST7789 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);
#elif LCD_CTRL == LCD_ILI9341
#include <Adafruit_ILI9341.h>
static Adafruit_ILI9341 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);
#else
#include <Adafruit_ST7735.h>
static Adafruit_ST7735 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);
#endif
#if LCD_BIG
#include "font_ui_l.h"
#define UI_FONT FontUiL
#else
#include "font_ui_s.h"
#define UI_FONT FontUiS
#endif

// ---------------------------------------------------------------- разметка (доли экрана)
#define MARGIN_DIV        40     // поле = ширина / 40
#define ARROW_W_PCT       18     // зона стрелки - % ширины справа
#define DIGIT_ASPECT_PCT  48     // ширина цифры = высота * 48 %
#define DIGIT_FILL_PCT    90     // высота цифры = высота зоны * 90 %
#define DIGIT_W_DIV10     56     // ширина строки «-88.8°» = 5.6 ширины цифры (см. drawLayout)
#define SEG_T_DIV         5      // толщина сегмента = ширина цифры / 5
#define TEXT_BUF          40     // буфер строки (перекодированной)
#define SETTINGS_ITEMS    5
#define CHAR_DEG          ((char)FONT_CODE_DEG)  // «°» в шрифте

enum class Screen : uint8_t { Main, Graph, List, Edit };

namespace {
// 7-сегментные коды: бит 0 - a (верх), 1 - b, 2 - c, 3 - d (низ), 4 - e, 5 - f, 6 - g (середина)
const uint8_t SEG_DIGITS[] PROGMEM = { 0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F };
#define SEG_MINUS 0x40
#define SEG_ONE   0x06                                   // «1» - рисуется по центру ячейки
#define SEG_BLANK 0x00

Screen   s_screen = Screen::Main;
uint32_t s_tAct;                       // последнее нажатие
uint8_t  s_item;                       // пункт настроек
Settings s_edit;                       // значения в режиме правки
char     s_buf[TEXT_BUF];

// Разметка
int16_t s_w, s_h, s_m;                 // экран и поле
int16_t s_asc, s_lh;                   // шрифт: высота над базовой линией и строки
int16_t s_dx, s_dy, s_dw, s_dh, s_t;   // крупные цифры: начало, размер цифры, толщина сегмента
int16_t s_ax, s_ay, s_aw, s_ah;        // зона стрелки
uint8_t s_cell[4];                     // текущие коды ячеек: сотни/знак, десятки, единицы, десятые
int8_t  s_arrow = 0;                   // -1 / 0 / 1 - нарисованная стрелка

// ---------------------------------------------------------------- текст
// UTF-8 из PROGMEM -> коды шрифта в s_buf (дописывается с позиции pos). Возвращает новую позицию.
// Символ не из FontUiMap[] -> пробел (значит, шрифт не перегенерирован: Scripts/gen_font.py).
uint8_t utf8ToFont(PGM_P src, uint8_t pos)
{
    for (;;) {
        uint8_t c = pgm_read_byte(src++);
        if (!c || pos >= TEXT_BUF - 1) break;
        uint16_t u = c;
        if (c >= 0x80) u = ((uint16_t)(c & 0x1F) << 6) | (pgm_read_byte(src++) & 0x3F);  // двухбайтные
        if (u > FONT_ASCII_LAST) {                        // буквы, «°» - по таблице шрифта
            c = ' ';
            for (uint8_t i = 0; i < FONT_MAP_COUNT; i++)
                if (pgm_read_word(&FontUiMap[i]) == u) { c = (uint8_t)(FONT_MAP_FIRST + i); break; }
        }
        s_buf[pos++] = (char)c;
    }
    s_buf[pos] = 0;
    return pos;
}

uint8_t appendNum(uint8_t pos, int16_t v)               // целое
{
    itoa(v, s_buf + pos, 10);
    return (uint8_t)strlen(s_buf);
}

uint8_t appendC10(uint8_t pos, int16_t c10)             // «-12.5»
{
    if (c10 < 0) { s_buf[pos++] = '-'; c10 = -c10; }
    pos = appendNum(pos, c10 / 10);
    s_buf[pos++] = '.';
    s_buf[pos++] = (char)('0' + c10 % 10);
    s_buf[pos] = 0;
    return pos;
}

uint8_t appendChar(uint8_t pos, char c)
{
    s_buf[pos++] = c;
    s_buf[pos] = 0;
    return pos;
}

int16_t textWidth()
{
    int16_t x1, y1;
    uint16_t w, h;
    tft.getTextBounds(s_buf, 0, 0, &x1, &y1, &w, &h);
    return (int16_t)w + x1;
}

// Строка s_buf: верх строки - top; выравнивание: 0 - влево от x, 1 - вправо до x, 2 - по центру x
void drawText(int16_t x, int16_t top, uint8_t align, uint16_t color)
{
    const int16_t w = textWidth();
    if (align == 1) x -= w;
    else if (align == 2) x -= w / 2;
    tft.setTextColor(color);
    tft.setCursor(x, top + s_asc);
    tft.print(s_buf);
}

// ---------------------------------------------------------------- крупные цифры
void segRect(int16_t x, int16_t y, int16_t w, int16_t h, bool on)
{
    tft.fillRect(x, y, w, h, on ? COL_TEMP : COL_BG);
}

// Ячейка цифры: перерисовываются только изменившиеся сегменты (без мерцания).
// «1» - по центру ячейки (иначе справа и у «-1», «104» разрыв): при переходе в «1» / из «1» ячейка - заново.
void drawCell(int16_t x, uint8_t mask, uint8_t old)
{
    const int16_t t = s_t, w = s_dw, y = s_dy;
    const int16_t hh = (s_dh - 3 * t) / 2;               // длина вертикального сегмента
    if ((mask == SEG_ONE) != (old == SEG_ONE)) {
        tft.fillRect(x, y, w, s_dh, COL_BG);
        old = SEG_BLANK;
    }
    if (mask == SEG_ONE) {
        const int16_t xc = x + (w - t) / 2;
        if (old != SEG_ONE) {
            segRect(xc, y + t, t, hh, true);
            segRect(xc, y + 2 * t + hh, t, hh, true);
        }
        return;
    }
    const uint8_t diff = mask ^ old;
    if (diff & 0x01) segRect(x + t, y, w - 2 * t, t, mask & 0x01);                     // a
    if (diff & 0x02) segRect(x + w - t, y + t, t, hh, mask & 0x02);                   // b
    if (diff & 0x04) segRect(x + w - t, y + 2 * t + hh, t, hh, mask & 0x04);          // c
    if (diff & 0x08) segRect(x + t, y + 2 * t + 2 * hh, w - 2 * t, t, mask & 0x08);   // d
    if (diff & 0x10) segRect(x, y + 2 * t + hh, t, hh, mask & 0x10);                  // e
    if (diff & 0x20) segRect(x, y + t, t, hh, mask & 0x20);                           // f
    if (diff & 0x40) segRect(x + t, y + t + hh, w - 2 * t, t, mask & 0x40);           // g
}

int16_t cellX(uint8_t i)                                  // 0..2 - целая часть, 3 - десятые
{
    const int16_t g = s_t;
    if (i < 3) return s_dx + i * (s_dw + g);
    return s_dx + 3 * (s_dw + g) + s_t + g;              // после точки
}

uint8_t digitMask(uint8_t d) { return pgm_read_byte(&SEG_DIGITS[d]); }

void drawTemp(bool valid, int16_t c10)
{
    uint8_t m[4];
    if (!valid) {
        m[0] = SEG_BLANK; m[1] = SEG_MINUS; m[2] = SEG_MINUS; m[3] = SEG_MINUS;
    } else {
        const bool neg = c10 < 0;
        uint16_t a = neg ? (uint16_t)(-c10) : (uint16_t)c10;
        const uint8_t frac = a % 10;
        a /= 10;
        const uint8_t ones = a % 10, tens = (a / 10) % 10, hund = a / 100;
        m[3] = digitMask(frac);
        m[2] = digitMask(ones);
        if (hund) {                                       // 100..125 °C (знака нет)
            m[0] = digitMask(hund % 10);
            m[1] = digitMask(tens);
        } else if (tens) {
            m[0] = neg ? SEG_MINUS : SEG_BLANK;
            m[1] = digitMask(tens);
        } else {                                          // |t| < 10: знак - рядом с цифрой
            m[0] = SEG_BLANK;
            m[1] = neg ? SEG_MINUS : SEG_BLANK;
        }
    }
    for (uint8_t i = 0; i < 4; i++) {
        if (m[i] != s_cell[i]) drawCell(cellX(i), m[i], s_cell[i]);
        s_cell[i] = m[i];
    }
}

void drawTempStatic()                                     // точка и «°»
{
    const int16_t xDot = s_dx + 3 * (s_dw + s_t);
    tft.fillRect(xDot, s_dy + s_dh - s_t, s_t, s_t, COL_TEMP);
    const int16_t r = s_dw / 5;
    const int16_t cx = cellX(3) + s_dw + s_t + r, cy = s_dy + r;
    tft.fillCircle(cx, cy, r, COL_TEMP);
    tft.fillCircle(cx, cy, r - (s_t + 1) / 2, COL_BG);
}

// ---------------------------------------------------------------- стрелка
void drawArrow(int8_t dir)
{
    if (dir == s_arrow) return;
    s_arrow = dir;
    tft.fillRect(s_ax, s_ay, s_aw, s_ah, COL_BG);
    if (!dir) return;
    const int16_t cx = s_ax + s_aw / 2, cy = s_ay + s_ah / 2;
    const int16_t a = min(s_aw / 2 - 1, s_ah / 3);        // полуширина головки
    const int16_t stemW = max(2, a / 2), stemH = a;
    const uint16_t col = dir > 0 ? COL_UP : COL_DOWN;
    if (dir > 0) {
        tft.fillTriangle(cx, cy - a - stemH / 2, cx - a, cy - stemH / 2, cx + a, cy - stemH / 2, col);
        tft.fillRect(cx - stemW / 2, cy - stemH / 2, stemW, stemH + a / 2, col);
    } else {
        tft.fillTriangle(cx, cy + a + stemH / 2, cx - a, cy + stemH / 2, cx + a, cy + stemH / 2, col);
        tft.fillRect(cx - stemW / 2, cy - stemH / 2 - a / 2, stemW, stemH + a / 2, col);
    }
}

// ---------------------------------------------------------------- главный экран
void layout()
{
    s_w = tft.width();
    s_h = tft.height();
    s_m = max(2, s_w / MARGIN_DIV);
    tft.setFont(&UI_FONT);
    tft.setTextWrap(false);
    utf8ToFont(PSTR("ЙКу"), 0);                           // самые высокие и низкие глифы
    int16_t x1, y1;
    uint16_t w, h;
    tft.getTextBounds(s_buf, 0, 0, &x1, &y1, &w, &h);
    s_asc = -y1;
    s_lh = (int16_t)h + 1;

    // зона крупных цифр между строкой макс и строкой мин, справа - стрелка
    s_aw = (int16_t)((int32_t)s_w * ARROW_W_PCT / 100);
    const int16_t zx = s_m, zy = s_m + s_lh + s_m / 2;
    const int16_t zw = s_w - 2 * s_m - s_aw, zh = s_h - 2 * (s_m + s_lh) - s_m;
    s_dh = (int16_t)((int32_t)zh * DIGIT_FILL_PCT / 100);
    s_dw = (int16_t)((int32_t)s_dh * DIGIT_ASPECT_PCT / 100);
    const int16_t dwMax = (int16_t)((int32_t)zw * 10 / DIGIT_W_DIV10);
    if (s_dw > dwMax) {                                   // не влезает по ширине - уменьшить
        s_dw = dwMax;
        s_dh = (int16_t)((int32_t)s_dw * 100 / DIGIT_ASPECT_PCT);
    }
    s_t = max(2, s_dw / SEG_T_DIV);
    const int16_t total = (int16_t)((int32_t)s_dw * DIGIT_W_DIV10 / 10);
    s_dx = zx + (zw - total) / 2;
    s_dy = zy + (zh - s_dh) / 2;
    s_ax = s_w - s_m - s_aw;
    s_ay = zy;
    s_ah = zh;
}

void drawMainValues()
{
    const bool ok = Sensor::kind() != SensorKind::None;
    drawTemp(ok, Sensor::tempC10());

    const Trend t = History::trend(Cfg::trendMin());
    int8_t dir = 0;
    if (ok && t.valid) {
        if (t.deltaC10 >= (int16_t)Cfg::s.thrC10) dir = 1;
        else if (t.deltaC10 <= -(int16_t)Cfg::s.thrC10) dir = -1;
    }
    drawArrow(dir);

    // макс - вверху слева, мин - внизу слева
    const int16_t topY = s_m, botY = s_h - s_m - s_lh;
    tft.fillRect(s_m, topY, s_w / 2, s_lh, COL_BG);
    tft.fillRect(s_m, botY, s_w * 2 / 3 - s_m, s_lh, COL_BG);
    if (t.hasMinMax) {
        uint8_t p = utf8ToFont(PSTR("макс "), 0);
        p = appendC10(p, t.maxC10);
        appendChar(p, CHAR_DEG);
        drawText(s_m, topY, 0, COL_TEXT);
    }
    if (!ok) {
        utf8ToFont(PSTR("нет датчика"), 0);
        drawText(s_m, botY, 0, COL_UP);
    } else if (t.hasMinMax) {
        uint8_t p = utf8ToFont(PSTR("мин "), 0);
        p = appendC10(p, t.minC10);
        appendChar(p, CHAR_DEG);
        drawText(s_m, botY, 0, COL_TEXT);
    }

    // влажность - внизу справа
    tft.fillRect(s_w * 2 / 3, botY, s_w / 3 - s_m, s_lh, COL_BG);
    if (ok && Sensor::hasHumidity()) {
        uint8_t p = appendNum(0, Sensor::humidity());
        appendChar(p, '%');
        drawText(s_w - s_m, botY, 1, Sensor::heating() ? COL_EDIT : COL_TEXT);   // жёлтая - датчик остывает
    }
}

void showMain()
{
    s_screen = Screen::Main;
    tft.fillScreen(COL_BG);
    for (uint8_t i = 0; i < 4; i++) s_cell[i] = SEG_BLANK;
    s_arrow = 0;
    drawTempStatic();
    drawMainValues();
}

// ---------------------------------------------------------------- график за сутки
void drawGraph()
{
    History::takeGraphChanged();                          // рисуем актуальное - флаг новой точки не нужен
    tft.fillScreen(COL_BG);
    const uint8_t n = History::graphCount();
    int16_t vmin = INT16_MAX, vmax = INT16_MIN;
    for (uint8_t i = 0; i < n; i++) {
        const int16_t v = History::graphAt(i);
        if (v == HIST_NONE) continue;
        if (v < vmin) vmin = v;
        if (v > vmax) vmax = v;
    }
    if (vmin > vmax) {
        utf8ToFont(PSTR("нет данных за сутки"), 0);
        drawText(s_w / 2, (s_h - s_lh) / 2, 2, COL_TEXT);
        return;
    }
    if (vmax - vmin < 10) {                               // не меньше 1 °C по высоте
        const int16_t c = (vmax + vmin) / 2;
        vmin = c - 5;
        vmax = c + 5;
    }

    // поле графика: слева - подписи температуры, снизу - подписи времени
    appendC10(0, -888);
    const int16_t x0 = s_m + textWidth() + s_m, x1 = s_w - s_m - 1;
    const int16_t y0 = s_m + s_asc / 2, y1 = s_h - s_m - s_lh - 3;
    const int16_t pw = x1 - x0, ph = y1 - y0;

    tft.drawFastHLine(x0, y1, pw + 1, COL_GRID);
    for (uint8_t hr = 0; hr <= 24; hr += GRAPH_TICK_H) {  // засечки каждый час, подписи - каждые GRAPH_LABEL_H
        const int16_t x = x1 - (int16_t)((int32_t)hr * pw / 24);
        if (hr % GRAPH_LABEL_H == 0) {
            tft.drawFastVLine(x, y0, ph, COL_GRID);
            if (hr && hr < 24) {                          // у краёв подписи нет (слева не помещается)
                uint8_t p = appendChar(0, '-');
                p = appendNum(p, hr);
                utf8ToFont(PSTR("ч"), p);
                drawText(x, y1 + 3, 2, COL_TEXT);
            }
        } else {
            tft.drawFastVLine(x, y1 - 2, 5, COL_GRID);
        }
    }
    appendC10(0, vmax);
    drawText(x0 - s_m / 2, y0 - s_asc / 2, 1, COL_TEXT);
    appendC10(0, vmin);
    drawText(x0 - s_m / 2, y1 - s_lh, 1, COL_TEXT);
    if (vmin < 0 && vmax > 0)                             // 0 °C
        tft.drawFastHLine(x0, y1 - (int16_t)((int32_t)(-vmin) * ph / (vmax - vmin)), pw, COL_ZERO);

    int16_t px = 0, py = 0;
    bool have = false;
    for (uint8_t i = 0; i < n; i++) {
        const int16_t v = History::graphAt(i);
        if (v == HIST_NONE) { have = false; continue; }
        const uint8_t age = (uint8_t)(n - 1 - i);         // 0 - последняя точка (справа)
        const int16_t x = x1 - (int16_t)((int32_t)age * pw / (GRAPH_SLOTS - 1));
        const int16_t y = y1 - (int16_t)((int32_t)(v - vmin) * ph / (vmax - vmin));
        if (have) tft.drawLine(px, py, x, y, COL_PLOT);
        else      tft.drawPixel(x, y, COL_PLOT);
        px = x; py = y; have = true;
    }
}

// ---------------------------------------------------------------- настройки
// шаг строк: строка + поле, но не больше свободной высоты между заголовком и подсказкой / SETTINGS_ITEMS
int16_t rowStep() { return min((int16_t)(s_lh + s_m), (int16_t)((s_h - 3 * s_m - 2 * s_lh - s_m) / SETTINGS_ITEMS)); }
int16_t rowTop(uint8_t i) { return s_m + s_lh + s_m + i * rowStep(); }

void itemLabel(uint8_t i)
{
    if (i == 0)      utf8ToFont(PSTR("Опрос датчика"), 0);
    else if (i == 1) utf8ToFont(PSTR("Тенденция за"), 0);
    else if (i == 2) utf8ToFont(PSTR("Порог стрелки"), 0);
    else if (i == 3) utf8ToFont(PSTR("Прогрев датчика"), 0);
    else             utf8ToFont(PSTR("Переворот"), 0);       // экрана на 180° (кнопки меняются местами)
}

void itemValue(uint8_t i, const Settings& st)
{
    uint8_t p;
    if (i == 0) {
        p = appendNum(0, Cfg::pollS(st.pollIdx));
        utf8ToFont(PSTR(" с"), p);
    } else if (i == 1) {
        const uint8_t m = Cfg::trendMin(st.trendIdx);
        if (m < 60) { p = appendNum(0, m);      utf8ToFont(PSTR(" мин"), p); }
        else        { p = appendNum(0, m / 60); utf8ToFont(PSTR(" ч"), p); }
    } else if (i == 2) {
        p = appendC10(0, st.thrC10);
        appendChar(p, CHAR_DEG);
    } else {
        if (i == 3 ? st.heater : st.flip) utf8ToFont(PSTR("вкл"), 0);
        else                              utf8ToFont(PSTR("выкл"), 0);
    }
}

void drawRow(uint8_t i)
{
    const bool sel = i == s_item;
    const bool edit = sel && s_screen == Screen::Edit;
    const int16_t top = rowTop(i);
    const int16_t rs = rowStep();
    tft.fillRect(0, top - (rs - s_lh) / 2, s_w, rs, sel ? COL_SEL : COL_BG);
    itemLabel(i);
    drawText(s_m, top, 0, COL_TEXT);
    itemValue(i, edit ? s_edit : Cfg::s);
    drawText(s_w - s_m, top, 1, edit ? COL_EDIT : COL_TEMP);
}

void drawHint()
{
    const int16_t top = s_h - s_m - s_lh;
    tft.fillRect(0, top, s_w, s_lh, COL_BG);
    if (s_screen == Screen::Edit) utf8ToFont(PSTR("ДН Кн.1 - сохранить"), 0);
    else                          utf8ToFont(PSTR("ДН Кн.1 - правка"), 0);
    drawText(s_w / 2, top, 2, COL_TEXT);
}

void showSettings()
{
    s_screen = Screen::List;
    tft.fillScreen(COL_BG);
    utf8ToFont(PSTR("Настройки"), 0);
    drawText(s_w / 2, s_m, 2, COL_EDIT);
    for (uint8_t i = 0; i < SETTINGS_ITEMS; i++) drawRow(i);
    drawHint();
}

void editStep(int8_t d)                                   // правка значения по кругу
{
    if (s_item == 0) {
        const uint8_t n = Cfg::pollCount();
        s_edit.pollIdx = (uint8_t)((s_edit.pollIdx + n + d) % n);
    } else if (s_item == 1) {
        const uint8_t n = Cfg::trendCount();
        s_edit.trendIdx = (uint8_t)((s_edit.trendIdx + n + d) % n);
    } else if (s_item == 2) {
        int16_t v = s_edit.thrC10 + d;
        if (v > TREND_THR_MAX_C10) v = TREND_THR_MIN_C10;
        if (v < TREND_THR_MIN_C10) v = TREND_THR_MAX_C10;
        s_edit.thrC10 = (uint8_t)v;
    } else if (s_item == 3) {
        s_edit.heater = !s_edit.heater;
    } else {
        s_edit.flip = !s_edit.flip;
    }
    drawRow(s_item);
}

uint8_t rotation()                                         // поворот экрана с учётом настройки «Перевернуть»
{
    return Cfg::s.flip ? (uint8_t)((TFT_ROTATION + 2) & 3) : TFT_ROTATION;
}

BtnEvent swapButtons(BtnEvent e)                           // экран перевёрнут - Кн.1 и Кн.2 меняются местами
{
    switch (e) {
        case BtnEvent::Short1: return BtnEvent::Short2;
        case BtnEvent::Short2: return BtnEvent::Short1;
        case BtnEvent::Long1:  return BtnEvent::Long2;
        case BtnEvent::Long2:  return BtnEvent::Long1;
        default:               return e;
    }
}

void selectStep(int8_t d)
{
    const uint8_t old = s_item;
    s_item = (uint8_t)((s_item + SETTINGS_ITEMS + d) % SETTINGS_ITEMS);
    drawRow(old);
    drawRow(s_item);
}
}  // namespace

namespace Ui {
void begin()
{
    pinMode(PIN_TFT_BL, OUTPUT);
    digitalWrite(PIN_TFT_BL, TFT_BL_ACTIVE_LOW ? LOW : HIGH);   // подсветка горит
#if LCD_CTRL == LCD_ST7789
    tft.init(LCD_WIDTH, LCD_HEIGHT);
    tft.invertDisplay(TFT_ST7789_INVERT);
#elif LCD_CTRL == LCD_ILI9341
    tft.begin();                          // 240x320, скорость SPI - по умолчанию библиотеки
#else
    tft.initR(TFT_ST7735_TAB);
#endif
    tft.setRotation(rotation());
    layout();
    showMain();
}

void onData()
{
    if (s_screen == Screen::Main) drawMainValues();
}

void update(uint32_t now, BtnEvent e)
{
    if (e != BtnEvent::None) s_tAct = now;
    if (Cfg::s.flip) e = swapButtons(e);

    // автовыход из графика и настроек (несохранённая правка отменяется)
    if (s_screen != Screen::Main && now - s_tAct >= UI_TIMEOUT_MS) {
        showMain();
        return;
    }

    switch (s_screen) {
        case Screen::Main:
            if (e == BtnEvent::Short1) { s_screen = Screen::Graph; drawGraph(); }
            else if (e == BtnEvent::Long1 || e == BtnEvent::Short2) { s_item = 0; showSettings(); }
            break;
        case Screen::Graph:
            if (e == BtnEvent::Short1 || e == BtnEvent::Short2) showMain();
            else if (History::takeGraphChanged()) drawGraph();
            break;
        case Screen::List:
            if (e == BtnEvent::Short1)      selectStep(1);
            else if (e == BtnEvent::Short2) selectStep(-1);
            else if (e == BtnEvent::Long1) {
                s_edit = Cfg::s;
                s_screen = Screen::Edit;
                drawRow(s_item);
                drawHint();
            } else if (e == BtnEvent::Long2) showMain();
            break;
        case Screen::Edit:
            if (e == BtnEvent::Short1)      editStep(1);
            else if (e == BtnEvent::Short2) editStep(-1);
            else if (e == BtnEvent::Long1) {
                if (memcmp(&s_edit, &Cfg::s, sizeof(Settings)) != 0) {
                    const bool flipped = s_edit.flip != Cfg::s.flip;
                    Cfg::s = s_edit;
                    Cfg::save();
                    if (flipped) {                         // новый поворот - экран целиком заново
                        tft.setRotation(rotation());
                        showSettings();
                        break;
                    }
                }
                s_screen = Screen::List;
                drawRow(s_item);
                drawHint();
            } else if (e == BtnEvent::Long2) showMain();
            break;
    }
}
}  // namespace Ui
