// config.h - выбор экрана, параметры дисплеев, датчики, распиновка.
// Экран - секция [display] platformio.ini (разрешение и контроллер, Scripts/display_select.py), датчик - автоматически.
#pragma once
#include <stdint.h>

// ---------------------------------------------------------------- Экран
// Разрешение (LCD_RES) и контроллер (LCD_CTRL) задаёт display_select.py: -DLCD_RES=LCD_RES_240x320 -DLCD_CTRL=LCD_ST7789
#define LCD_RES_128x160  1   // 1.77" / 1.8"
#define LCD_RES_240x320  2   // 2.4" / 2.8"
#define LCD_ST7735       1   // 1.77" / 1.8" (Adafruit_ST7735)
#define LCD_ST7789       2   // 2.4" по названию продавца (Adafruit_ST7789)
#define LCD_ILI9341      3   // 2.4" MSP2401 / 2.8" MSP2806 - по документам LCDWIKI (Adafruit_ILI9341)

#ifndef LCD_RES                       // сборка без display_select.py (Arduino IDE) - как в platformio.ini
#define LCD_RES  LCD_RES_240x320
#endif
#ifndef LCD_CTRL
#define LCD_CTRL LCD_ST7789
#endif

#if LCD_RES == LCD_RES_240x320 && (LCD_CTRL == LCD_ST7789 || LCD_CTRL == LCD_ILI9341)
#define LCD_WIDTH        240
#define LCD_HEIGHT       320
#elif LCD_RES == LCD_RES_128x160 && LCD_CTRL == LCD_ST7735
#define LCD_WIDTH        128
#define LCD_HEIGHT       160
#else
#error "Недопустимое сочетание LCD_RES / LCD_CTRL"
#endif
#define LCD_BIG          (LCD_WIDTH >= 240)   // крупный шрифт интерфейса

// Подсветка: 1 - внешний P-MOSFET Q1 верхнего плеча (D6 = LOW - светит, работает с любым модулем);
//            0 - ключ уже на модуле экрана, D6 через 1 кОм прямо на LED/BL (HIGH - светит).
// Есть ли ключ на модуле: ток вывода LED/BL при 3.3 В - единицы мА (ключ есть) или десятки мА (нет, нужен Q1).
#ifndef TFT_BL_ACTIVE_LOW
#define TFT_BL_ACTIVE_LOW  0
#endif

// Ориентация и вариант инициализации (проверить на железе: смещение и цвета ST7735 - BLACKTAB / GREENTAB)
#define TFT_ROTATION       1              // альбомная: 320x240 / 160x128
#define TFT_ST7735_TAB     INITR_BLACKTAB // из Adafruit_ST7735.h (1.77" - порядок цветов BGR, подобрать вкладку)
#define TFT_ST7789_INVERT  1              // 1 - инверсия цветов ST7789 включена (как в init() библиотеки)

// Цвета (RGB565)
#define COL_BG             0x0000         // фон
#define COL_TEMP           0xFFFF         // крупные цифры
#define COL_TEXT           0xC618         // подписи
#define COL_UP             0xFC00         // стрелка «теплеет»
#define COL_DOWN           0x34DF         // стрелка «холодает»
#define COL_SEL            0x3186         // фон выбранного пункта настроек
#define COL_EDIT           0xFFE0         // значение в режиме правки
#define COL_GRID           0x4208         // сетка графика
#define COL_PLOT           0x07FF         // линия графика
#define COL_ZERO           0x8410         // линия 0 °C на графике

// ---------------------------------------------------------------- Датчик
// Определяется автоматически: сначала SHT40 (I2C), если не ответил - DS18B20 (1-Wire). Нет ни одного - повтор
// поиска с периодом опроса. Библиотеки: Adafruit SHT4x (SHT40), OneWire + DallasTemperature (DS18B20).
enum class SensorKind : uint8_t { None, Sht40, Ds18b20 };
#define DS18B20_RESOLUTION 12             // бит
#define DS18B20_CONV_MS    750UL          // даташит DS18B20, табл. 3: 12 бит - 750 мс (макс.)
#define SENSOR_MAX_ERRORS  3              // ошибок подряд - датчик потерян, снова поиск

// Прогрев SHT40 (опция в настройках; даташит SHT4x, разд. 4.9): сушка от конденсата при высокой влажности.
// Температура важнее: измерение с нагревом и HEATER_COOLDOWN_S после него - не используются (на экране и в
// истории остаётся последнее честное значение). Импульс 110 мВт / 1 с (~33 мА; 200 мВт - до 75 мА, много для
// длинного провода), не чаще HEATER_INTERVAL_S: скважность 1 / 300 = 0.3 % (допустимо до 10 %).
#define HEATER_RH_ON       95             // %: при влажности от этого значения
#define HEATER_MAX_T_C10   600            // нагреватель - только ниже 60 °C (даташит: окружающая до 65 °C)
#define HEATER_INTERVAL_S  300UL          // минимум между импульсами
#define HEATER_COOLDOWN_S  120UL          // после импульса температура не обновляется (подобрать на железе)
#define HEATER_DEF         0              // по умолчанию выключен
// Настройка «Перевернуть экран»: поворот TFT_ROTATION + 2 (180°), Кн.1 и Кн.2 меняются местами (пользователь)
#define FLIP_DEF           0              // по умолчанию не перевёрнут

// I2C для SHT40 на проводе до улицы: минимальная частота, которую даёт Wire.setClock() при 8 МГц без делителя
// TWI (TWBR <= 255: ~15 кГц), с запасом - 20 кГц (TWBR = 192). Датчик не торопим.
#define I2C_CLOCK_HZ    20000UL
#define I2C_TIMEOUT_US  25000UL    // тайм-аут операции Wire (сброс шины): залипание SDA/SCL не вешает программу

// ---------------------------------------------------------------- Распиновка (Readme.md §3)
// Аппаратный SPI ATmega328P (фиксирован): D11 - MOSI (SDA/SDI/DIN экрана), D13 - SCK, D12 - MISO (SDO, не обязателен).
// Аппаратный I2C (фиксирован): A4 - SDA, A5 - SCL.
// Утверждено 2026-10-14. Свободны: D3, D7, D12, A0-A3, A6, A7.
#define PIN_ONEWIRE     2    // DS18B20, подтяжка 4.7 кОм к 3.3 В
#define PIN_BTN1        4    // Кн.1 (верхняя) -> GND, внутренняя подтяжка
#define PIN_BTN2        5    // Кн.2 (нижняя)  -> GND, внутренняя подтяжка
#define PIN_TFT_BL      6    // подсветка, ШИМ (Timer0), см. TFT_BL_ACTIVE_LOW
#define PIN_TFT_RST     8
#define PIN_TFT_DC      9
#define PIN_TFT_CS      10   // = SS: при SPI-мастере обязан быть выходом
// D11 - MOSI, D13 - SCK (аппаратный SPI); A4 - SDA, A5 - SCL (SHT40)

// ---------------------------------------------------------------- Интерфейс (Readme §6)
#define BTN_DEBOUNCE_MS      30UL     // антидребезг кнопок
#define BTN_LONG_MS          1000UL   // долгое нажатие (ДН) - от 1 с
#define UI_TIMEOUT_MS        30000UL  // автовыход из настроек и графика без нажатий

// Настройки (EEPROM): варианты значений и умолчания
#define POLL_PERIODS_S       { 2, 5, 10, 20, 30, 60 }      // период опроса датчика, с
#define POLL_PERIOD_DEF_S    10
#define TREND_PERIODS_MIN    { 15, 30, 60, 120, 180 }      // период тенденции (и мин / макс), мин
#define TREND_PERIOD_DEF_MIN 60

// Тенденция и история
#define TREND_THR_MIN_C10    1        // порог стрелки тенденции (настройка), десятые °C: 0.1 ... 2.0, шаг 0.1
#define TREND_THR_MAX_C10    20
#define TREND_THR_DEF_C10    5        // 0.5 °C за период (улица)
#define TREND_SLOT_S         120      // точка тенденции - среднее за 2 мин
#define TREND_SLOTS          90       // 90 x 2 мин = 3 ч - максимальный период
#define GRAPH_SLOT_S         600      // точка графика - среднее за 10 мин
#define GRAPH_SLOTS          144      // 144 x 10 мин = 24 ч
#define GRAPH_TICK_H         1        // засечки по времени - каждый час
#define GRAPH_LABEL_H        6        // подписи -6ч, -12ч, ... (подпись каждого часа не помещается по ширине)
#define EE_SETTINGS_ADDR     0        // настройки - в начале EEPROM

// Сторожевой таймер - только режим сброса (у клона режим прерывания работает не как у ATmega)
#define WDT_TIMEOUT          WDTO_2S

// ---------------------------------------------------------------- Serial
#define SERIAL_BAUD     38400UL    // = monitor_speed в platformio.ini (на 8 МГц ошибка 0.2%)
