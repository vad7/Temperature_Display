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
#include "menu.h"
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
#define ARROW_LEN_PCT     75     // длина стрелки - % высоты зоны крупных цифр
#define ARROW_HEAD_PCT    45     // головка (треугольник) - % длины стрелки
#define ARROW_HEAD_W_PCT  100    // ширина головки - % её высоты (меньше - острее)
#define ARROW_STEM_W_PCT  35     // толщина стержня - % ширины головки
#define DIGIT_ASPECT_PCT  48     // ширина цифры = высота * 48 %
#define DIGIT_FILL_PCT    90     // высота цифры = высота зоны * 90 %
#define DIGIT_W_DIV10     50     // ширина строки «-88.8» = 4 цифры + 5 толщин сегмента (зазоры, точка) = 5.0 ширины
                                 // цифры; «°» у крупных цифр нет (пользователь 2026-11-03: цифры на 12 % крупнее)
#define SEG_T_DIV         5      // толщина сегмента = ширина цифры / 5
#define GRAPH_MIN_SPAN_C10 10    // график: ось температуры - не меньше 1 °C
#define GRAPH_LABEL_GAP   3      // график: зазор между осью времени и подписями, пикселей
#define GRAPH_TICK_PX     2      // график: засечка часа - на 2 пикселя в обе стороны от оси
#define LABEL_WIDEST_C10  (-888) // самая широкая подпись оси температуры «-88.8» - под неё поле слева
#define MINMAX_WIDEST_C10 1888   // самое широкое мин / макс «188.8°» (цифры одной ширины, «-» уже цифры)
#define ROT_MASK          3      // setRotation(): 0..3
#define TEXT_BUF          40     // буфер строки (перекодированной)
#define CHAR_DEG          ((char)FONT_CODE_DEG)  // «°» в шрифте

// Подсветка: таймер 2, быстрый ШИМ (TOP 255) на OC2B = D3; частота - делителем: 8 МГц / 64 / 256 = 490 Гц,
// с BRIGHT_FAST - 8 МГц / 1 / 256 = 31 кГц (даташит ATmega328P, Timer/Counter2: WGM2 = 3, CS2 = 4 / 1)
#define BL_WGM            (_BV(WGM21) | _BV(WGM20))                                 // быстрый ШИМ
#define BL_COM            (TFT_BL_ACTIVE_LOW ? (_BV(COM2B1) | _BV(COM2B0)) : _BV(COM2B1))  // инверсный - светит низкий
#define BL_CLK_SLOW       _BV(CS22)                                                 // делитель 64
#define BL_CLK_FAST       _BV(CS20)                                                 // без делителя
#define PCT_FULL          100
#define SEC_PER_MIN       60

enum class Screen : uint8_t { Splash, Main, Graph, List, Edit };
enum : uint8_t { ALIGN_LEFT, ALIGN_RIGHT, ALIGN_CENTER };   // выравнивание drawText()
enum : int8_t { ARROW_DOWN = -1, ARROW_NONE = 0, ARROW_UP = 1 };   // стрелка тенденции
// ячейки крупных цифр слева направо: сотни / знак, десятки, единицы, (точка), десятые
enum : uint8_t { CELL_HUND, CELL_TENS, CELL_ONES, CELL_FRAC, CELL_COUNT };

namespace {
// 7-сегментные коды: биты сегментов SEG_A (верх) ... SEG_G (середина)
#define SEG_A     0x01                                   // верх
#define SEG_B     0x02                                   // справа сверху
#define SEG_C     0x04                                   // справа снизу
#define SEG_D     0x08                                   // низ
#define SEG_E     0x10                                   // слева снизу
#define SEG_F     0x20                                   // слева сверху
#define SEG_G     0x40                                   // середина
const uint8_t SEG_DIGITS[] PROGMEM = { 0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F };   // 0..9
#define SEG_MINUS SEG_G
#define SEG_ONE   (SEG_B | SEG_C)                        // «1» - рисуется по центру ячейки
#define SEG_BLANK 0x00

// Названия пунктов настроек - одной строкой через '\0', порядок - MENU_ITEMS (menu.h)
#define MENU_NAME(id, name) name "\0"
const char MENU_NAMES[] PROGMEM = MENU_ITEMS(MENU_NAME);
#undef MENU_NAME

Screen   s_screen = Screen::Main;
uint32_t s_tAct;                       // последнее нажатие
uint8_t  s_item;                       // пункт настроек
uint8_t  s_first;                      // первый видимый пункт (список прокручивается, если не помещается)
Settings s_edit;                       // значения в режиме правки
char     s_buf[TEXT_BUF];

// Разметка
int16_t s_w, s_h, s_m;                 // экран и поле
int16_t s_asc, s_lh;                   // шрифт: высота над базовой линией и строки
int16_t s_dx, s_dy, s_dw, s_dh, s_t;   // крупные цифры: начало, размер цифры, толщина сегмента
int16_t s_ax, s_ay, s_aw, s_ah;        // зона стрелки
int16_t s_mmX;                         // правый край мин / макс (не скачут при смене числа знаков)
int16_t s_maxY, s_minY, s_humY;        // верх строк макс, мин (и ошибки датчика), влажности
int16_t s_txtW;                        // ширина строк макс / мин (стирание, до стрелки / влажности)
uint8_t s_cell[CELL_COUNT];            // текущие коды ячеек (CELL_*)
int8_t  s_arrow = ARROW_NONE;          // нарисованная стрелка (ARROW_*)

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

// Строка s_buf: верх строки - top; выравнивание ALIGN_*: влево от x, вправо до x, по центру x
void drawText(int16_t x, int16_t top, uint8_t align, uint16_t color)
{
    const int16_t w = textWidth();
    if (align == ALIGN_RIGHT) x -= w;
    else if (align == ALIGN_CENTER) x -= w / 2;
    tft.setTextColor(color);
    tft.setCursor(x, top + s_asc);
    tft.print(s_buf);
}

// ---------------------------------------------------------------- подсветка
void backlight(uint8_t level)                             // level - из BRIGHT_LEVELS: % | BRIGHT_FAST
{
    OCR2B  = (uint8_t)((uint16_t)(level & ~BRIGHT_FAST) * UINT8_MAX / PCT_FULL);   // 255 - постоянно включена
    TCCR2A = BL_COM | BL_WGM;
    TCCR2B = (level & BRIGHT_FAST) ? BL_CLK_FAST : BL_CLK_SLOW;
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
    if (diff & SEG_A) segRect(x + t, y, w - 2 * t, t, mask & SEG_A);                     // a
    if (diff & SEG_B) segRect(x + w - t, y + t, t, hh, mask & SEG_B);                   // b
    if (diff & SEG_C) segRect(x + w - t, y + 2 * t + hh, t, hh, mask & SEG_C);          // c
    if (diff & SEG_D) segRect(x + t, y + 2 * t + 2 * hh, w - 2 * t, t, mask & SEG_D);   // d
    if (diff & SEG_E) segRect(x, y + 2 * t + hh, t, hh, mask & SEG_E);                  // e
    if (diff & SEG_F) segRect(x, y + t, t, hh, mask & SEG_F);                           // f
    if (diff & SEG_G) segRect(x + t, y + t + hh, w - 2 * t, t, mask & SEG_G);           // g
}

int16_t cellX(uint8_t i)                                  // ячейка CELL_*: до CELL_FRAC - целая часть
{
    const int16_t g = s_t;
    if (i < CELL_FRAC) return s_dx + i * (s_dw + g);
    return s_dx + CELL_FRAC * (s_dw + g) + s_t + g;      // после точки
}

uint8_t digitMask(uint8_t d) { return pgm_read_byte(&SEG_DIGITS[d]); }

void drawTemp(bool valid, int16_t c10)
{
    uint8_t m[CELL_COUNT];
    if (!valid) {
        m[CELL_HUND] = SEG_BLANK; m[CELL_TENS] = SEG_MINUS; m[CELL_ONES] = SEG_MINUS; m[CELL_FRAC] = SEG_MINUS;
    } else {
        const bool neg = c10 < 0;
        uint16_t a = neg ? (uint16_t)(-c10) : (uint16_t)c10;
        const uint8_t frac = a % 10;
        a /= 10;
        const uint8_t ones = a % 10, tens = (a / 10) % 10, hund = a / 100;
        m[CELL_FRAC] = digitMask(frac);
        m[CELL_ONES] = digitMask(ones);
        if (hund) {                                       // 100..125 °C (знака нет)
            m[CELL_HUND] = digitMask(hund % 10);
            m[CELL_TENS] = digitMask(tens);
        } else if (tens) {
            m[CELL_HUND] = neg ? SEG_MINUS : SEG_BLANK;
            m[CELL_TENS] = digitMask(tens);
        } else {                                          // |t| < 10: знак - рядом с цифрой
            m[CELL_HUND] = SEG_BLANK;
            m[CELL_TENS] = neg ? SEG_MINUS : SEG_BLANK;
        }
    }
    for (uint8_t i = 0; i < CELL_COUNT; i++) {
        if (m[i] != s_cell[i]) drawCell(cellX(i), m[i], s_cell[i]);
        s_cell[i] = m[i];
    }
}

void drawTempStatic()                                     // точка
{
    const int16_t xDot = s_dx + CELL_FRAC * (s_dw + s_t);
    tft.fillRect(xDot, s_dy + s_dh - s_t, s_t, s_t, COL_TEMP);
}

// ---------------------------------------------------------------- стрелка
void drawArrow(int8_t dir)
{
    if (dir == s_arrow) return;
    s_arrow = dir;
    tft.fillRect(s_ax, s_ay, s_aw, s_ah, COL_BG);
    if (dir == ARROW_NONE) return;
    const int16_t cx = s_ax + s_aw / 2, cy = s_ay + s_ah / 2;
    const int16_t len = (int16_t)((int32_t)min(s_dh, s_ah) * ARROW_LEN_PCT / 100);   // длина стрелки
    const int16_t hh = (int16_t)((int32_t)len * ARROW_HEAD_PCT / 100);               // высота головки
    const int16_t hw = min((int16_t)(s_aw / 2 - 1), (int16_t)((int32_t)hh * ARROW_HEAD_W_PCT / 200));  // полуширина
    const int16_t sw = max((int16_t)2, (int16_t)((int32_t)hw * 2 * ARROW_STEM_W_PCT / 100));         // стержень
    const int16_t tip = dir == ARROW_UP ? cy - len / 2 : cy + len / 2;                       // острие
    const int16_t base = dir == ARROW_UP ? tip + hh : tip - hh;                              // основание головки
    const uint16_t col = dir == ARROW_UP ? COL_UP : COL_DOWN;
    tft.fillTriangle(cx, tip, cx - hw, base, cx + hw, base, col);
    if (dir == ARROW_UP) tft.fillRect(cx - sw / 2, base, sw, cy + len / 2 - base, col);
    else         tft.fillRect(cx - sw / 2, cy - len / 2, sw, base - (cy - len / 2), col);
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
    appendChar(appendC10(0, MINMAX_WIDEST_C10), CHAR_DEG);
    s_mmX = s_m + textWidth();

    // зона крупных цифр: альбомная - между строкой макс и строкой мин, справа стрелка; книжная - во всю ширину, под
    // цифрами строки макс и мин, справа от них стрелка, внизу влажность
    s_aw = (int16_t)((int32_t)s_w * ARROW_W_PCT / 100);
    s_humY = s_h - s_m - s_lh;
    const bool land = s_w >= s_h;
    const int16_t band = 2 * s_lh + s_m / 2;              // книжная: строки макс и мин
    const int16_t zx = s_m, zy = land ? s_m + s_lh + s_m / 2 : s_m;
    const int16_t zw = land ? s_w - 2 * s_m - s_aw : s_w - 2 * s_m;
    const int16_t zh = land ? s_h - 2 * (s_m + s_lh) - s_m : s_humY - band - 3 * s_m;
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
    s_ax = s_w - s_m - s_aw;
    if (land) {
        s_dy = zy + (zh - s_dh) / 2;
        s_maxY = s_m;
        s_minY = s_humY;
        s_ay = zy;
        s_ah = zh;
        s_txtW = s_w * 2 / 3 - s_m;
    } else {                                              // цифры, макс / мин со стрелкой, влажность - равные зазоры
        const int16_t gap = (s_humY - s_m - s_dh - band) / 3;
        s_dy = s_m + gap;
        s_maxY = s_dy + s_dh + gap;
        s_minY = s_maxY + band - s_lh;
        s_ay = s_maxY;
        s_ah = band;
        s_txtW = s_ax - s_m;
    }
}

void drawMainValues()
{
    const bool ok = Sensor::kind() != SensorKind::None;
    drawTemp(ok, Sensor::tempC10());

    const Trend t = History::trend(Cfg::trendMin());
    int8_t dir = ARROW_NONE;
    if (ok && t.valid) {
        if (t.deltaC10 >= (int16_t)Cfg::s.thrC10) dir = ARROW_UP;
        else if (t.deltaC10 <= -(int16_t)Cfg::s.thrC10) dir = ARROW_DOWN;
    }
    drawArrow(dir);

    // макс и мин слева (за Cfg::mmHours(), только значения; строки - layout())
    const MinMax mm = History::minMax(Cfg::mmHours());
    tft.fillRect(s_m, s_maxY, s_txtW, s_lh, COL_BG);
    tft.fillRect(s_m, s_minY, s_txtW, s_lh, COL_BG);
    if (mm.valid) {
        appendChar(appendC10(0, mm.maxC10), CHAR_DEG);
        drawText(s_mmX, s_maxY, ALIGN_RIGHT, COL_MAX);
    }
    if (!ok) {
        utf8ToFont(PSTR("нет датчика"), 0);
        drawText(s_m, s_minY, ALIGN_LEFT, COL_ERR);
    } else if (Sensor::failed()) {                        // температура - последняя удачная
        utf8ToFont(PSTR("ошибка датчика"), 0);
        drawText(s_m, s_minY, ALIGN_LEFT, COL_ERR);
    } else if (mm.valid) {
        appendChar(appendC10(0, mm.minC10), CHAR_DEG);
        drawText(s_mmX, s_minY, ALIGN_RIGHT, COL_MIN);
    }

    // влажность - внизу справа
    tft.fillRect(s_w * 2 / 3, s_humY, s_w / 3 - s_m, s_lh, COL_BG);
    if (ok && Sensor::hasHumidity()) {
        uint8_t p = appendNum(0, Sensor::humidity());
        appendChar(p, '%');
        drawText(s_w - s_m, s_humY, ALIGN_RIGHT, Sensor::heating() ? COL_EDIT : COL_TEXT);   // жёлтая - датчик остывает
    }
}

// Заставка при включении: название, версия, автор (по центру, 4 строки); датчик и его выводы - строкой 4,
// когда определён (Ui::showSensor)
int16_t splashStep() { return s_lh * 3 / 2; }
int16_t splashTop()  { return (s_h - 3 * splashStep() - s_lh) / 2; }

void showSplash()
{
    s_screen = Screen::Splash;
    s_tAct = millis();
    tft.fillScreen(COL_BG);
    const int16_t step = splashStep();
    int16_t top = splashTop();
    utf8ToFont(PSTR("Термометр"), 0);
    drawText(s_w / 2, top, ALIGN_CENTER, COL_EDIT);
    utf8ToFont(PSTR("версия " FW_VERSION), 0);
    drawText(s_w / 2, top += step, ALIGN_CENTER, COL_TEXT);
    utf8ToFont(PSTR("автор Вадим"), 0);
    drawText(s_w / 2, top + step, ALIGN_CENTER, COL_TEXT);
}
}  // namespace

namespace Ui {
void showSensor()
{
    s_tAct = millis();                    // время заставки - от вывода датчика
    uint16_t col = COL_TEMP;
    switch (Sensor::kind()) {
        case SensorKind::Sht40:   utf8ToFont(PSTR("5НТ40: а4 а5"), 0); break;           // без «датчик» - книжная 128
        case SensorKind::Ds18b20: appendNum(utf8ToFont(PSTR("Дс18В20: Д"), 0), PIN_ONEWIRE); break;
        default:                  utf8ToFont(PSTR("нет датчика"), 0); col = COL_ERR; break;
    }
    drawText(s_w / 2, splashTop() + 3 * splashStep(), ALIGN_CENTER, col);
}
}  // namespace Ui

namespace {

void showMain()
{
    s_screen = Screen::Main;
    backlight(Cfg::bright());                             // отменённая правка яркости - назад
    tft.fillScreen(COL_BG);
    for (uint8_t i = 0; i < CELL_COUNT; i++) s_cell[i] = SEG_BLANK;
    s_arrow = ARROW_NONE;
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
        // первая точка - по закрытии первого интервала GRAPH_SLOT_S после включения
        utf8ToFont(PSTR(" мин"), appendNum(utf8ToFont(PSTR("точки через "), 0), GRAPH_SLOT_S / SEC_PER_MIN));
        drawText(s_w / 2, (s_h - s_lh) / 2, ALIGN_CENTER, COL_TEXT);
        return;
    }
    if (vmax - vmin < GRAPH_MIN_SPAN_C10) {
        const int16_t c = (vmax + vmin) / 2;
        vmin = c - GRAPH_MIN_SPAN_C10 / 2;
        vmax = c + GRAPH_MIN_SPAN_C10 / 2;
    }

    // поле графика: слева - подписи температуры, снизу - подписи времени
    appendC10(0, LABEL_WIDEST_C10);
    const int16_t x0 = s_m + textWidth() + s_m, x1 = s_w - s_m - 1;
    const int16_t y0 = s_m + s_asc / 2, y1 = s_h - s_m - s_lh - GRAPH_LABEL_GAP;
    const int16_t pw = x1 - x0, ph = y1 - y0;

    // подписи времени - каждые GRAPH_LABEL_H часов, не помещаются (книжная) - реже вдвое
    uint8_t lblH = GRAPH_LABEL_H;
    utf8ToFont(PSTR("ч"), appendNum(0, -GRAPH_HOURS));    // самая широкая подпись
    const int16_t lblW = textWidth() + 1;
    while ((int32_t)lblH * pw / GRAPH_HOURS < lblW && lblH < GRAPH_HOURS) lblH *= 2;

    tft.drawFastHLine(x0, y1, pw + 1, COL_GRID);
    for (uint8_t hr = 0; hr <= GRAPH_HOURS; hr += GRAPH_TICK_H) {  // засечки каждый час
        const int16_t x = x1 - (int16_t)((int32_t)hr * pw / GRAPH_HOURS);
        if (hr % lblH == 0) {
            tft.drawFastVLine(x, y0, ph, COL_GRID);
            if (hr && hr < GRAPH_HOURS) {                          // у краёв подписи нет (слева не помещается)
                uint8_t p = appendChar(0, '-');
                p = appendNum(p, hr);
                utf8ToFont(PSTR("ч"), p);
                drawText(x, y1 + GRAPH_LABEL_GAP, ALIGN_CENTER, COL_TEXT);
            }
        } else {
            tft.drawFastVLine(x, y1 - GRAPH_TICK_PX, 2 * GRAPH_TICK_PX + 1, COL_GRID);
        }
    }
    appendC10(0, vmax);
    drawText(x0 - s_m / 2, y0 - s_asc / 2, ALIGN_RIGHT, COL_TEXT);
    appendC10(0, vmin);
    drawText(x0 - s_m / 2, y1 - s_lh, ALIGN_RIGHT, COL_TEXT);
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
// шаг строк: строка + поле, но не больше свободной высоты между заголовком и подсказкой / ITEM_COUNT и не меньше
// строки + 1; все пункты не помещаются - список прокручивается (s_first)
int16_t listH()   { return s_h - 3 * s_m - 2 * s_lh - s_m; }
int16_t rowStep() { return max((int16_t)(s_lh + 1), min((int16_t)(s_lh + s_m), (int16_t)(listH() / ITEM_COUNT))); }
uint8_t rowsVisible() { return (uint8_t)min((int16_t)ITEM_COUNT, (int16_t)(listH() / rowStep())); }
int16_t rowTop(uint8_t i) { return s_m + s_lh + s_m + (i - s_first) * rowStep(); }

void itemLabel(uint8_t i)                                 // название пункта i - из MENU_NAMES
{
    PGM_P p = MENU_NAMES;
    while (i--) p += strlen_P(p) + 1;
    utf8ToFont(p, 0);
}

void itemValue(uint8_t i, const Settings& st)
{
    uint8_t p;
    switch (i) {
        case ITEM_THR:
            appendChar(appendC10(0, st.thrC10), CHAR_DEG);
            break;
        case ITEM_TREND: {
            const uint8_t m = Cfg::trendMin(st.trendIdx);
            if (m < 60) { p = appendNum(0, m);      utf8ToFont(PSTR(" м"), p); }   // «м» - «мин» налезает на название
            else        { p = appendNum(0, m / 60); utf8ToFont(PSTR(" ч"), p); }
            break;
        }
        case ITEM_MINMAX:
            utf8ToFont(PSTR(" ч"), appendNum(0, Cfg::mmHours(st.mmIdx)));
            break;
        case ITEM_POLL:
            utf8ToFont(PSTR(" с"), appendNum(0, Cfg::pollS(st.pollIdx)));
            break;
        case ITEM_HEATER:
            if (st.heater) utf8ToFont(PSTR("да"), 0);
            else           utf8ToFont(PSTR("нет"), 0);
            break;
        case ITEM_CORR:                                   // «+0.5°», «-1.2°», «0.0°»
            appendChar(appendC10(st.corrC10 > 0 ? appendChar(0, '+') : 0, st.corrC10), CHAR_DEG);
            break;
        case ITEM_ROT:
            appendChar(appendNum(0, st.rot * ROT_STEP_DEG), CHAR_DEG);
            break;
        case ITEM_SWAP:
            if (st.swapBtn) utf8ToFont(PSTR("да"), 0);
            else            utf8ToFont(PSTR("нет"), 0);
            break;
        case ITEM_BRIGHT: {
            const uint8_t b = Cfg::bright(st.brightIdx);
            p = appendChar(appendNum(0, b & ~BRIGHT_FAST), '%');
            if (b & BRIGHT_FAST) utf8ToFont(PSTR("x"), p);
            break;
        }
        default:                                          // ITEM_ERRORS: неудачных чтений / пропавших измерений
            utoa(Sensor::errReads(), s_buf, 10);
            p = appendChar((uint8_t)strlen(s_buf), '/');
            utoa(Sensor::errLost(), s_buf + p, 10);
            break;
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
    drawText(s_m, top, ALIGN_LEFT, COL_TEXT);
    itemValue(i, edit ? s_edit : Cfg::s);
    drawText(s_w - s_m, top, ALIGN_RIGHT, edit ? COL_EDIT : COL_TEMP);
}

bool scrollToItem()                                       // выбранный пункт - в видимых строках; true - список сдвинут
{
    const uint8_t n = rowsVisible(), old = s_first;
    if (s_item < s_first) s_first = s_item;
    else if (s_item >= s_first + n) s_first = (uint8_t)(s_item - n + 1);
    return s_first != old;
}

void drawRows()
{
    for (uint8_t i = s_first; i < s_first + rowsVisible(); i++) drawRow(i);
}

void drawHint()
{
    const int16_t top = s_h - s_m - s_lh;
    tft.fillRect(0, top, s_w, s_lh, COL_BG);
    if (s_screen == Screen::Edit)    utf8ToFont(PSTR("ДН Кн.1 - сохранить"), 0);
    else if (s_item == ITEM_ERRORS) utf8ToFont(PSTR("ДН Кн.1 - сброс"), 0);
    else                            utf8ToFont(PSTR("ДН Кн.1 - правка"), 0);
    drawText(s_w / 2, top, ALIGN_CENTER, COL_TEXT);
}

void showSettings()
{
    s_screen = Screen::List;
    tft.fillScreen(COL_BG);
    utf8ToFont(PSTR("Настройки"), 0);
    drawText(s_w / 2, s_m, ALIGN_CENTER, COL_EDIT);
    scrollToItem();
    drawRows();
    drawHint();
}

void editStep(int8_t d)                                   // правка значения по кругу
{
    uint8_t n;
    switch (s_item) {
        case ITEM_THR: {
            int16_t v = s_edit.thrC10 + d;
            if (v > TREND_THR_MAX_C10) v = TREND_THR_MIN_C10;
            if (v < TREND_THR_MIN_C10) v = TREND_THR_MAX_C10;
            s_edit.thrC10 = (uint8_t)v;
            break;
        }
        case ITEM_TREND:
            n = Cfg::trendCount();
            s_edit.trendIdx = (uint8_t)((s_edit.trendIdx + n + d) % n);
            break;
        case ITEM_MINMAX:
            n = Cfg::mmCount();
            s_edit.mmIdx = (uint8_t)((s_edit.mmIdx + n + d) % n);
            break;
        case ITEM_POLL:
            n = Cfg::pollCount();
            s_edit.pollIdx = (uint8_t)((s_edit.pollIdx + n + d) % n);
            break;
        case ITEM_HEATER:
            s_edit.heater = !s_edit.heater;
            break;
        case ITEM_CORR: {
            int8_t v = (int8_t)(s_edit.corrC10 + d);
            if (v > TEMP_CORR_MAX_C10) v = -TEMP_CORR_MAX_C10;
            if (v < -TEMP_CORR_MAX_C10) v = TEMP_CORR_MAX_C10;
            s_edit.corrC10 = v;
            break;
        }
        case ITEM_ROT:
            s_edit.rot =(uint8_t)((s_edit.rot + ROT_COUNT + d) % ROT_COUNT);
            break;
        case ITEM_SWAP:
            s_edit.swapBtn = !s_edit.swapBtn;
            break;
        case ITEM_BRIGHT:                                 // яркость видна сразу (отмена правки - showMain)
            n = Cfg::brightCount();
            s_edit.brightIdx = (uint8_t)((s_edit.brightIdx + n + d) % n);
            backlight(Cfg::bright(s_edit.brightIdx));
            break;
    }
    drawRow(s_item);
}

uint8_t rotation()                                         // поворот экрана с учётом настройки «Поворот»
{
    return (uint8_t)((TFT_ROTATION + Cfg::s.rot) & ROT_MASK);
}

BtnEvent swapButtons(BtnEvent e)                           // «Обмен кнопок» - Кн.1 и Кн.2 местами
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
    s_item = (uint8_t)((s_item + ITEM_COUNT + d) % ITEM_COUNT);
    if (scrollToItem()) drawRows();
    else {
        drawRow(old);
        drawRow(s_item);
    }
    if (old == ITEM_ERRORS || s_item == ITEM_ERRORS) drawHint();
}
}  // namespace

namespace Ui {
void begin()
{
    pinMode(PIN_TFT_BL, OUTPUT);
    digitalWrite(PIN_TFT_BL, TFT_BL_ACTIVE_LOW ? HIGH : LOW);   // подсветка выключена до заставки (без белого и шума)
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
    showSplash();                         // строка датчика - Ui::showSensor после Sensor::begin
    backlight(Cfg::bright());             // подсветка горит (ШИМ, настройка «Яркость»)
}

void onData()
{
    if (s_screen == Screen::Main) drawMainValues();
}

void update(uint32_t now, BtnEvent e)
{
    if (e != BtnEvent::None) s_tAct = now;
    if (Cfg::s.swapBtn) e = swapButtons(e);

    // автовыход из графика и настроек (несохранённая правка отменяется)
    if (s_screen != Screen::Main && now - s_tAct >= UI_TIMEOUT_MS) {
        showMain();
        return;
    }

    switch (s_screen) {
        case Screen::Splash:                      // до кнопки (нажатие только закрывает) или SPLASH_MS
            if (e != BtnEvent::None || now - s_tAct >= SPLASH_MS) showMain();
            break;
        case Screen::Main:
            if (e == BtnEvent::Short1) { s_screen = Screen::Graph; drawGraph(); }
            else if (e == BtnEvent::Long1 || e == BtnEvent::Short2) { s_item = 0; showSettings(); }   // курсор - на первой строке
            break;
        case Screen::Graph:
            if (e == BtnEvent::Short1 || e == BtnEvent::Short2) showMain();
            else if (History::takeGraphChanged()) drawGraph();
            break;
        case Screen::List:
            if (e == BtnEvent::Short1)      selectStep(-1);     // Кн.1 - верхняя: пункт выше
            else if (e == BtnEvent::Short2) selectStep(1);
            else if (e == BtnEvent::Long1 && s_item == ITEM_ERRORS) {
                Sensor::resetErrors();
                drawRow(s_item);
            } else if (e == BtnEvent::Long1) {
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
                    const bool rotated = s_edit.rot != Cfg::s.rot;
                    Cfg::s = s_edit;
                    Cfg::save();
                    if (rotated) {                         // новый поворот - разметка и экран целиком заново
                        tft.setRotation(rotation());
                        layout();
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
