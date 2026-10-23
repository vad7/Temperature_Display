# Корпус уличного термометра (на стену, горизонтально): крышка с экраном, кнопки - на крышке слева от экрана,
# внутри HLK-3M03C и Arduino Pro Mini. CadQuery, все размеры - в блоке PARAMETERS (мм, откуда взято - в комментариях).
# Вариант = экран (свой корпус): --tft 18 (1.8", по умолчанию), 177 (1.77"), 24 (2.4").
#   PYTHONIOENCODING=utf-8 python Scripts/enclosure.py [--tft 18]       - один вариант: собрать, проверить, чертёж
#   PYTHONIOENCODING=utf-8 python Scripts/enclosure.py --all            - все варианты
#   PYTHONIOENCODING=utf-8 python Scripts/enclosure.py --update-project - все варианты + таблица в Readme §7
# Результат: Build/enclosure/TempDisplay_tft<вариант>_body.stl, _lid.stl, _ears.stl (уши и планка, плашмя),
#            _assembly.step, _layout.png, _promini.png, _preview.png, _dims.json
# Печать без поддержек: корпус - задней стенкой на столе, крышка - лицом на столе, уши - плашмя.
#
# Оси: X вправо, Y вверх (вид спереди), Z от стены (Z = 0 - стена, лицо крышки - Z = DEPTH). 0 по X и Y - центр.
# Компоновка (Readme §7): макетка кнопок вертикально у левой стенки (вставляется между стенкой и левыми стойками
# крышки, стоит на 2 упорах), угловые кнопки на её верхнем крае - толкатели через крышку слева от экрана; экран альбомно на крышке, гребёнкой влево; Pro Mini - вертикально (край RESET вниз, у нижней стенки),
# у задней стенки; HLK - лёжа выводами к крышке, длинной стороной вплотную к правой стенке, по центру по высоте,
# выводы AC - внизу (пользователь). Утонения: датчик - левая стенка и низ / верх слева; сеть - у AC: правая стенка над HLK,
# нижняя - у дна, на уровне утонения датчика (пользователь 2026-10-21).
import json
import os
import re
import sys

import cadquery as cq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Build", "enclosure")
TFT_KEY = sys.argv[sys.argv.index("--tft") + 1] if "--tft" in sys.argv[:-1] else os.environ.get("ENCL_TFT", "18")
PREFIX = "TempDisplay_tft" + TFT_KEY

# ===================================== PARAMETERS =====================================
# --- стенки и крепёж
WALL = 2.5            # толщина стенок (пользователь)
CORNER_R = 4.0        # скругление 4 вертикальных углов корпуса и крышки снаружи (пользователь); внутри полости -
                      # CORNER_R - WALL (стенка в углу та же), бортик крышки - соосно; дно и лицо крышки - плоские
BACK_T = 2.5          # задняя стенка (к стене)
LID_T = 2.5           # крышка (пользователь)
LID_LIP_H = 3.0       # бортик крышки внутрь корпуса (центровка)
LID_LIP_T = 1.2       # толщина бортика
FIT = 0.25            # зазор посадки бортика
# Саморезы Ø2.5 (пользователь), отверстия без потая (пользователь): головка лежит на детали; на крышке - небольшой
# конус под головку (пользователь 2026-10-16)
PILOT_D = 2.0         # глухое отверстие под саморез Ø2.5 (нарезает резьбу в пластике)
CLEAR_D = 2.8         # сквозное под саморез Ø2.5
# Печать FDM: круглые отверстия выходят меньше модели (измерено пользователем 2026-10-16: Ø3.0 -> 2.2, Ø2.8 -> 1.9,
# габариты и окно экрана - в норме). Все отверстия под винты и толкатели строятся с запасом HOLE_COMP по диаметру
# (hole()); размеры выше - готовые, после печати. Другой принтер / пластик - перемерить и поправить.
# Слайсер пользователя: сопло 0.30, периметры 3 x 0.40 (шире сопла), шов случайный, первый слой 0.25 - отсюда и
# потеря; если ширину периметров сделать 0.30-0.33 и шов выровненный - HOLE_COMP уменьшить по новому замеру.
HOLE_COMP = 0.2
HEAD_D, HEAD_H = 5.0, 1.8   # головка самореза 2.5 (полукруглая, типовая) - зона для проверок
# Глухое отверстие = длина самореза - толщина прижимаемой детали + запас у дна (пользователь: 1.5 мм, где позволяет
# высота стойки; проверка - screw_list() в checks(), меньше SCREW_MARGIN_MIN - ошибка)
SCREW_MARGIN = 1.5
SCREW_MARGIN_MIN = 0.5
LID_SCREW_L = 12      # крышка -> стойки корпуса
HLK_SCREW_L = 8       # ухо / планка HLK -> стойки HLK
PM_SCREW_L = 6        # уши Pro Mini -> стойки
TFT_SCREW_L = 5       # плата экрана 2.4" -> стойки крышки (стойка 2.9 мм: 6 мм упрётся); у других - TFT_VARIANTS
TFT_SCREW_D = 2.5
TFT_PILOT_D = PILOT_D
LID_CSK_D = 4.4       # конус под головку на лице крышки: Ø у поверхности (после печати), 90° - глубина
                      # (4.4 - 2.8) / 2 = 0.8 мм; крышка 2.5 - под конусом остаётся 1.7
LID_BOSS_D = 5.5      # стойки корпуса под крышку (стенка вокруг Ø2.0 - 1.75); слиты со стенками
LID_BOSS_DEPTH = LID_SCREW_L - LID_T + SCREW_MARGIN   # глухое в стойке: 12 - 2.5 + 1.5 = 11
BOSS_CLR = 0.3        # от стойки до деталей
# Крепление на стену: 3 места под шуруп Ø4 - утонения Ø4.5 изнутри (остаток THIN_SKIN), сверлить нужные
# (пользователь); над головкой до крышки - ни деталей корпуса, ни стоек (шуруп закручивается при снятой крышке;
# макетка кнопок - съёмная, не мешает; проверка - checks())
WALL_HOLE_D = 4.5
WALL_HEAD_D = 8.5     # головка шурупа и отвёртка - зона
WALL_HEAD_CLR = 0.3   # зазор вокруг зоны головки до деталей и выступов (у HLK: между выступом Nano и HLK 9.3 мм)
WALL_HOLE_POST_DY = 8.0   # место у HLK: выше левой стойки HLK, мм (пользователь)
# места - WALL_HOLES ниже (от компоновки): слева посередине под макеткой (пользователь), под Pro Mini, слева от HLK -
# посередине между HLK и выступом Nano, на WALL_HOLE_POST_DY выше левой стойки HLK (пользователь 2026-10-21);
# макетка, Pro Mini и HLK на время монтажа снимаются

# --- экран 2.4" (Docs/TFT2.4 240x320 ST7789V.pdf - чертёж LCDWIKI MSP2401; u - вдоль модуля от края с
#     гребёнкой, v - поперёк от центра)
TFT_L = 77.18         # плата 42.72 x 77.18
TFT_W = 42.72
TFT_PCB_T = 1.6       # «1.60 (PCB)»
TFT_STACK = 2.2 + 0.5 # LCD 2.20 + лента 0.50 (всего с платой 4.30)
TFT_HOLE_D = 3.2      # 4 отверстия Ø3.20 (площадки Ø4.70)
TFT_HOLE_DV = 36.72   # 3.00 от длинных краёв
TFT_HOLE_U1 = 77.18 - 3.0 - 67.26   # от края с гребёнкой: 6.92
TFT_HOLE_U2 = 77.18 - 3.0           # 3.00 от дальнего края
TFT_BL_W = 42.72                    # рамка LCD (B/L) 42.72 x 60.26, от дальнего края 6.51
TFT_BL_U0, TFT_BL_U1 = 77.18 - 6.51 - 60.26, 77.18 - 6.51
TFT_AA_W = 36.72                    # видимая область 36.72 x 48.96, от дальнего края 9.26 (по центру поперёк)
TFT_AA_U0, TFT_AA_U1 = 77.18 - 9.26 - 48.96, 77.18 - 9.26
TFT_PINS_U = 2.0      # ряд из 14 штырей - 2.00 от края, 13 x 2.54 по центру (4.85 от длинных краёв)
TFT_PINS_SPAN = 33.02
TFT_PINS_BACK = 12.68 - 4.30 + 2.5  # штыри за платой (12.68 всего - 4.30) + пайка / изгиб проводов
TFT_SMD_H = 3.0       # детали на обратной стороне «3.00 Max (SMD)»
# Детали на обратной стороне (рисунок Back, оценка по рисунку ±1 мм): (u0, u1, f0, f1), f - поперёк от левого
# края на виде спереди (гребёнка внизу); на корпусе гребёнка слева -> Y = TFT_W / 2 - f
TFT_BACK_PARTS = {
    "слот SD": (33.2, 62.7, 0.5, 20.5),
    "R1-R3": (44.0, 50.2, 26.4, 29.3),
    "C2": (28.9, 31.8, 32.8, 34.1),
    "U1 U2 Q1 C1 R4-R6": (14.9, 27.2, 19.5, 39.7),
}
TFT_GAP = 0.2         # зазор стекло - крышка
WINDOW_MARGIN = 0.8   # окно = AA + поле с каждой стороны
TFT_BOSS_D = 6.0      # стойки крепления модуля на крышке (саморез TFT_SCREW_L); до рамки LCD 3.5
TFT_PILOT_INTO_LID = 1.0   # глухое отверстие стойки уходит в крышку 2.5 (на лице остаётся 1.5)
TFT_BOSS_GLASS_CLR = 0.3   # стойка не касается рамки LCD
TFT_BL_EDGE = 1.7     # от рамки LCD до стенки (бортик крышки 0.25 + 1.2 + запас)

# --- варианты экрана (свой корпус у каждого): экран - гребёнкой влево от XM0, по центру по Y
TFT_VARIANTS = {"24": {k: globals()[k] for k in (
    "TFT_L", "TFT_W", "TFT_PCB_T", "TFT_STACK", "TFT_HOLE_DV", "TFT_HOLE_U1", "TFT_HOLE_U2", "TFT_BL_W",
    "TFT_BL_U0", "TFT_BL_U1", "TFT_AA_W", "TFT_AA_U0", "TFT_AA_U1", "TFT_PINS_U", "TFT_PINS_SPAN", "TFT_PINS_BACK",
    "TFT_SMD_H", "TFT_BACK_PARTS", "TFT_BOSS_D", "TFT_SCREW_L", "TFT_SCREW_D", "TFT_PILOT_D")}}
TFT_VARIANTS["24"]["HLK_LEFT_POST_DY"] = -3.0   # головка самореза планки HLK - не под слотом SD экрана
TFT_NAMES = {"24": '2.4" LCDWIKI MSP2401 240x320', "18": '1.8" 128x160 ST7735S', "177": '1.77" 128x160 ST7735S'}
# 1.8" (Docs/TFT1.8 128x160 ST7735S.png - чертёж продавца TZT; на чертеже - портрет, гребёнка 8 штырей внизу):
# плата 45.00 x 53.00, 4 отверстия Ø3.00 через 39.97 x 45.00 (2.45 от края с гребёнкой), рамка LCD (BL)
# 34.00 x 43.70 (4.78 от дальнего края, по центру поперёк), AA 28.03 x 35.04 (2.43 от рамки, по центру поперёк),
# LCD 2.45 без скотча, плата 1.60, детали сзади до 3.60 (SMD), гребёнка - 1.74 от края, 8 x 2.54 по центру
TFT_VARIANTS["18"] = {
    "TFT_L": 53.0, "TFT_W": 45.0, "TFT_PCB_T": 1.6,
    "TFT_STACK": 2.45 + 0.5,                 # LCD 2.45 + скотч 0.5 - ОЦЕНКА (на чертеже «2.45 без клея»)
    "TFT_HOLE_DV": 39.97, "TFT_HOLE_U1": 2.45, "TFT_HOLE_U2": 2.45 + 45.0,
    "TFT_BL_W": 34.0, "TFT_BL_U0": 53.0 - 4.78 - 43.70, "TFT_BL_U1": 53.0 - 4.78,
    "TFT_AA_W": 28.03, "TFT_AA_U0": 53.0 - 4.78 - 2.43 - 35.04, "TFT_AA_U1": 53.0 - 4.78 - 2.43,
    "TFT_PINS_U": 1.74, "TFT_PINS_SPAN": 7 * 2.54,
    "TFT_PINS_BACK": 8.5 + 2.5,              # гребёнка 2.54 за платой (пластик + штырь) + пайка - ОЦЕНКА
    "TFT_SMD_H": 3.6,                        # «SMD 3.60 max»
    # детали сзади (рисунок Rear, оценка ±1 мм; f - от левого края на виде спереди, вид сзади зеркальный)
    "TFT_BACK_PARTS": {
        "слот SD": (12.1, 39.9, 0.0, 18.7),
        "U21 C1 C2 J1": (35.0, 47.0, 27.0, 42.0),
        "R9-R13 Q": (19.7, 35.5, 23.1, 27.9),
    },
    "TFT_BOSS_D": 5.3,                       # до рамки LCD 2.99 поперёк - полная стойка Ø5.3
    "TFT_SCREW_L": 5, "TFT_SCREW_D": 2.5, "TFT_PILOT_D": PILOT_D,
    "HLK_LEFT_POST_DY": 0.0,                 # по центру: -3 - головка под стабилизатором U21
}
# 1.77" (Docs/TFT1.77 128x160 ST7735S.png - чертёж TZT GMT177-01, портрет, гребёнка 2 x 7 вверху): плата
# 34.00 x 53.70, 4 отверстия Ø2.5 через 30.00 x 49.70 (2.00 от краёв), AA 28.03 x 35.04, рамка LCD - 43.70 в длину,
# толщина без штырей 3.65 (плата 1.20), гребёнка: ряд 1-8 - 2.00 от края, 7 x 2.54 по центру, штыри 11.30
TFT_VARIANTS["177"] = {
    "TFT_L": 53.7, "TFT_W": 34.0, "TFT_PCB_T": 1.2,
    "TFT_STACK": 3.65 - 1.2,                 # LCD со скотчем: 3.65 max - плата 1.20
    "TFT_HOLE_DV": 30.0, "TFT_HOLE_U1": 2.0, "TFT_HOLE_U2": 2.0 + 49.7,
    "TFT_BL_W": 30.9,                        # ширина рамки LCD - ОЦЕНКА по рисунку (на чертеже не подписана)
    "TFT_BL_U0": 5.45, "TFT_BL_U1": 5.45 + 43.70,   # положение рамки - ОЦЕНКА по рисунку, длина 43.70 - чертёж
    "TFT_AA_W": 28.03, "TFT_AA_U0": 7.3, "TFT_AA_U1": 7.3 + 35.04,   # начало AA - ОЦЕНКА по рисунку ±0.5
    "TFT_PINS_U": 2.0, "TFT_PINS_SPAN": 7 * 2.54,
    "TFT_PINS_BACK": 11.3 - 3.65 + 2.5,      # штыри 11.30 (чертёж) за модулем + пайка - ОЦЕНКА
    "TFT_SMD_H": 1.6,                        # U1 (микросхема шрифтов), Q1, R, C - ОЦЕНКА по фото
    "TFT_BACK_PARTS": {"U1 Q1 R1-R3 C1-C3": (6.0, 22.0, 5.0, 29.0)},   # ОЦЕНКА по фото оборота
    "TFT_BOSS_D": 4.4,                       # дальние отверстия - 2.55 от рамки LCD: стойка Ø4.4
    # отверстия Ø2.5 - саморез 2.2 (2.5 не пройдёт); глухое ~0.8 Ø; стойка 2.45 + 0.2 + 1.0 в крышку = 3.65
    "TFT_SCREW_L": 4, "TFT_SCREW_D": 2.2, "TFT_PILOT_D": 1.8,
    "HLK_LEFT_POST_DY": 0.0,
}
HLK_LEFT_POST_DY = 0.0    # левая стойка HLK по Y от середины (по варианту - TFT_VARIANTS)
if TFT_KEY not in TFT_VARIANTS:
    raise SystemExit("--tft: нужно одно из %s" % ", ".join(TFT_VARIANTS))
globals().update(TFT_VARIANTS[TFT_KEY])

# --- кнопки и макетка (кнопка угловая 4.5 x 4.5, 3 вывода - Docs/Button 4.5x4.5 3P Rgiht Angle.avif;
#     макетка 20 x 80, шаг 2.54, Docs/Perfboard_20x80.png)
# Макетка вертикально у левой стенки, сторона пайки - к стенке; кнопки и детали - на стороне к экрану, кнопки - на
# верхнем крае (ряд A - у крышки), толкатели - через крышку (пользователь). Сверху макетку держит крышка, снизу -
# 2 упора с пазом (пользователь), по X - стенка (бортик крышки) и левые стойки крышки.
BTN_W = 4.5           # корпус кнопки 4.5 x 4.5 (поперёк толкателя)
BTN_H = 11.0          # H: от тыла корпуса до торца толкателя (пользователь: «размер кнопки 11 мм»)
BTN_BODY_L = 2.75     # тыл корпуса - верх пластины (чертёж); выводы 1 / 2 (через 3 мм) - на уровне пластины,
                      # 3-й - на 1.98 ближе к тылу: по сетке 2.54 не попадают - подогнуть / рассверлить
BTN_RIVET = 0.4       # заклёпки над пластиной - ОЦЕНКА по чертежу
BTN_PLUNGER_D = 2.3   # толкатель Ø2.3 (чертёж)
BTN_HOLE_D = 3.0      # отверстие в крышке: толкатель + зазор
BTN_OUT_MIN = 1.0     # толкатель над крышкой - не меньше (проверка)
PB_W = 20.0           # ширина макетки (по Z)
PB_T = 1.6            # толщина (типовая, ИЗМЕРИТЬ)
PB_LEN = 47.6         # обрезана после 17-го столбца: 5.71 + 16 * 2.54 + 1.27 (по Y)
PB_COL0 = 5.71        # центр столбца 1 от края (80 - 27 * 2.54) / 2
PB_ROW0 = 3.65        # центр ряда A от края (20 - 5 * 2.54) / 2
PB_BTN_COLS = (4.5, 11.5)  # центры кнопок: выводы 1 / 2 - в столбцах 4 / 5 и 11 / 12 (пара - по середине корпуса, -0.3)
PB_BTN_ROW = 0        # ряд A (у крышки) - выводы 1 / 2
PB_SOLDER = 1.5       # сторона пайки - хвосты выводов до стенки (ОЦЕНКА); в этом зазоре - бортик крышки
PB_BACK = 11.0        # детали на стороне к экрану (кнопки, резисторы стоя, C1 лёжа) - зона
PB_PARTS_CLR = BOSS_CLR      # детали макетки - между левыми стойками крышки (на уровне правых, пользователь)
PB_EDGE = 0.5         # от макетки до верхней / нижней стенок и до крышки
PB_SLOT_CLR = 0.15    # паз упора: зазор с каждой стороны платы
PB_STOP_W = 4.0       # упор под макеткой (по Y), слит со стойкой крышки и левой стенкой
PB_STOP_RIB = 2.0     # стенка паза со стороны пайки - выше низа макетки (хвосты ряда F - с 3.65 - 1)
# C1 (Scripts/perfboard.py) - стоя за нижней стойкой крышки: выводы E16 (+) / F17 (-), центр - между ними
PB_C1_D = 5.0         # электролит 100 мкФ 6.3 В Ø5 x 11 (Ø6.3 не помещается: до стенки 6.85 мм)
PB_C1_H = 12.5        # над платой: 11 + выводы 1.5
PB_C1_COL, PB_C1_ROW = 16.5, 4.5     # центр: между столбцами 16 / 17 и рядами E / F (A = 0)

# --- HLK-3M03C (Docs/3W-C series ... V2.9.pdf, разд. 9: 39 x 23.5 x 18, выводы 5 мм с грани 39 x 23.5;
#     AC - у одного края (±3 от середины), -Vo / +Vo - у другого (±9), 2.7 мм от краёв по длине)
HLK_L, HLK_W, HLK_H = 39.0, 23.5, 18.0   # лёжа выводами к крышке: Y = 39 (вдоль правой стенки), X = 23.5, Z = 18
HLK_PINS = 5.0        # выводы (даташит)
HLK_PIN_CUT = 3.0     # выводы после пайки проводов откусываются (пользователь) - остаток под пайку
# от верха HLK до платы экрана: остаток выводов + детали на обороте экрана + зазор (пользователь: было 5,
# «увеличь чуть-чуть, чтоб штырьки не упирались в резисторы и SD»)
HLK_TO_TFT = HLK_PIN_CUT + TFT_SMD_H + 0.5
HLK_PIN_U = 2.7       # выводы от торцов ((39 - 33.6) / 2): AC - у нижнего торца, DC - у верхнего (пользователь)
HLK_PIN_AC_V, HLK_PIN_DC_V = 3.0, 9.0    # выводы поперёк (по X) от середины
HLK_PIN_ZONE = 1.5    # вокруг вывода - пайка
HLK_CLR = 0.2         # от HLK до стоек
HLK_POST_D = 6.0      # 2 стойки (пользователь): слева по центру (планка HLK + Nano) и у верхнего торца (ухо,
                      # слита с верхней стенкой); саморез 2.5 x 8 сверху
LEFT_BOSS_Y = 14.7    # левые стойки крышки по Y (прежнее место - раскладка макетки и упоры под него)
NANO_PM_CLR = 0.5     # от штырьков Nano до держателей Pro Mini (ширина корпуса - и по ряду Pro Mini + Nano + HLK)
HLK_EAR_L = 12.0      # ухо, прижимает HLK (пользователь: ~10 мм; от центра стойки до конца 9 мм)

# --- уши (отдельные детали, печать плашмя): прямоугольная пластина с отверстием под саморез над стойкой
EAR_T = 2.0           # толщина
EAR_W = 6.0           # ширина

# --- Arduino Pro Mini - аналог Baite BTE13-010 (Docs/Pro Mini 328 pinout.png; выводы - SparkFun Eagle:
#     угловые D9 / D10 у края RESET - 1.27 от обоих краёв, Ø1.02, площадка ~Ø1.9; у клона A4-A7 у того же края -
#     5.6..12.0 от длинного края)
PM_L, PM_W = 33.0, 18.0       # измерено пользователем (Baite BTE13-010); расчёт по шагу 2.54: 33.02 x 17.78
PM_T = 0.8                    # плата
PM_RAISE = 5.0                # над задней стенкой: хвосты штырьков снизу (~3 мм) + запас
PM_TOP_H = 4.0                # самая высокая деталь (кварц) - ОЦЕНКА, измерить
PM_TAILS = 3.0                # хвосты штырьков под платой
PM_UART_U = 31.75             # ряд UART (JP1) от края RESET (SparkFun: 1.27 от края UART)
# У края UART - 2 держателя (эскиз work/ProMini_holder_sketch.png): полка, паз, губа-защёлка, упор по длине
PM_HOLDER_W = 5.0             # ширина держателя (пользователь: 5 мм)
PM_HOLDER_T = 2.0             # толщина держателя
PM_SUPPORT = 0.8              # полка под краем платы (заход под плату)
PM_LIP = 0.5                  # губа над платой (защёлка; держатель отгибается при установке сверху)
PM_LEAD = 1.2                 # высота фаски захода на губе (45°)
PM_STOP = 1.0                 # закрытый торец паза - упор платы по длине (снаружи от края UART)
PM_CLR = 0.2                  # зазор платы в пазах
# У края RESET - 2 стойки за краем платы с ушами (эскиз work/Nano_mount 2.png), саморез 2.5 x 6
PM_POST_D = 6.0               # = ширина уха
PM_POST_CLR = 0.3             # от стойки до края платы
PM_TONGUE_V = 3.3             # язычок уха - между угловым выводом (до 2.2) и A4 / A7 (от 5.1) от длинного края
PM_TONGUE_W = 1.8             # ширина язычка
PM_EAR_OVER = 0.8             # язычок заходит на плату (отверстие углового вывода - с 0.77 от края)
PM_LEDGE = 1.0                # полочка под платой у стойки (под язычком)
PM_PLUG_W = 14.0              # разъём USB-UART на прямых штырях - сверху (крышка снята), зона над рядом UART

# --- запасная плата: клон Arduino Nano со штырьками - вместо Pro Mini (пользователь): на ребре вдоль Y, сторона
#     деталей (USB) - вправо к левой стойке HLK, штырьки - влево. Держит общая планка на левой стойке HLK: вправо
#     прижимает HLK, влево - паз над верхним ребром Nano с небольшим Г-загибом со стороны деталей. Снизу - низкие
#     выступы на задней стенке (не мешают штырькам).
NANO_L, NANO_W = 43.2, 18.5  # типовой клон (пользователь: «типовые подходят») - ИЗМЕРИТЬ
NANO_USB = 2.0               # разъём USB выступает за торец
NANO_PCB_T = 1.6
NANO_COMP_H = 4.0            # детали на верхней стороне (разъём USB) - ОЦЕНКА
NANO_PIN_ROW = 1.65          # ряды штырьков от длинных краёв: (0.73" - 0.6") / 2 - ОЦЕНКА
NANO_PINS = 8.5              # штырьки с пластиком колодки (2.5) со стороны штырьков - ОЦЕНКА
NANO_HDR_H = 2.54            # пластик колодки поперёк ряда
NANO_HDR_SPAN = 15 * 2.54    # 15 штырьков в ряду
NANO_TAIL = 2.5              # хвосты штырьков со стороны деталей
NANO_CLR = 0.5               # от деталей Nano до стойки HLK
NANO_HOOK = 1.0              # Г-загиб планки вниз по стороне деталей (не ниже хвостов верхнего ряда + 0.3)
NANO_BAR_LEFT = 2.0          # планка левее платы Nano (над колодкой)
NANO_RIDGE_H = 0.8           # выступ у задней стенки справа вдоль платы (ниже хвостов нижнего ряда)
NANO_RIDGE_W = 1.2
NANO_END_RIDGE_H = 1.5       # выступы слева - только у торцов, где нет штырьков
BAR_T = 2.5                  # общая планка HLK + Nano (над Nano остаётся BAR_T - (верх Nano - верх HLK))

# --- провода: утонения под отверстия (сверлить по месту)
MAINS_D = 6.0         # сетевой провод (пользователь)
SENSOR_D = 5.0        # провод датчика (пользователь)
HOLE_CLR = 0.5        # отверстие = провод + зазор
THIN_SKIN = 0.8       # остаток стенки в утонении (сверлится; снаружи - гладко)
SENSOR_Z = BACK_T + 4.0   # у задней стенки, под макеткой
# ======================================================================================

# --- производные размеры
HLK_POST_PILOT = HLK_SCREW_L - EAR_T + SCREW_MARGIN       # 8 - ухо 2 + 1.5 = 7.5 (планка 2.5 - запас 2.0)
PM_POST_PILOT = PM_SCREW_L - EAR_T + SCREW_MARGIN         # 6 - ухо 2 + 1.5 = 5.5
TFT_PILOT_DEPTH = TFT_STACK + TFT_GAP + TFT_PILOT_INTO_LID  # 2.9 + 1.0 = 3.9 (больше - тонко на лице крышки)
PB_X0 = max(PB_SOLDER, FIT + LID_LIP_T + 0.3)   # макетка от левой стенки: хвосты пайки и бортик крышки
PB_X1 = PB_X0 + PB_T
PB_ZONE_X1 = PB_X1 + PB_BACK
IW = max(PB_ZONE_X1 + BOSS_CLR + TFT_L + LID_BOSS_D + BOSS_CLR,          # по экрану и стойкам крышки
         PB_ZONE_X1 + BOSS_CLR + PM_W + 2 * (PM_CLR + PM_HOLDER_T) + NANO_PM_CLR + NANO_PINS + NANO_PCB_T
         + NANO_COMP_H + NANO_CLR + HLK_POST_D + HLK_CLR + HLK_W)               # по ряду Pro Mini, Nano, HLK
IH = max(PB_LEN + 2 * PB_EDGE, TFT_BL_W + 2 * TFT_BL_EDGE, TFT_W + 1.0,
         HLK_L + 2 * (HLK_CLR + HLK_POST_D))   # HLK по центру + стойка у торца целиком (ухо и головка - в полости)
W, H = IW + 2 * WALL, IH + 2 * WALL
CORNER_R_IN = max(CORNER_R - WALL, 0.0)   # скругление углов полости
HLK_TOP = BACK_T + HLK_H
TFT_PCB_BACK = HLK_TOP + HLK_TO_TFT                       # задняя сторона платы экрана
BODY_D = TFT_PCB_BACK + TFT_PCB_T + TFT_STACK + TFT_GAP
DEPTH = BODY_D + LID_T
Z_LID = BODY_D

# макетка: X от левой стенки, по Y - во всю высоту, по Z - у крышки
XL = -IW / 2
PB_Y1 = PB_LEN / 2                        # необрезанный край - вверху; макетка по центру по высоте
                                          # (кнопки и упоры - на прежних местах относительно стоек крышки)
PB_Y0 = PB_Y1 - PB_LEN
PB_Z1 = Z_LID - PB_EDGE                   # ряд A - к крышке
PB_Z0 = PB_Z1 - PB_W
def pb_yz(col, row):
    """Столбец / ряд макетки -> Y, Z (столбец 1 - сверху, ряд A - у крышки)."""
    return PB_Y1 - (PB_COL0 + (col - 1) * 2.54), PB_Z1 - (PB_ROW0 + row * 2.54)

# угловые кнопки: корпус на макетке со стороны к экрану, пластина (выводы 1 / 2) - на уровне ряда PB_BTN_ROW
BTN_X = XL + PB_X1 + BTN_W / 2                       # ось толкателя
BTN_PLATE_Z = PB_Z1 - (PB_ROW0 + PB_BTN_ROW * 2.54)
BTN_TIP_Z = BTN_PLATE_Z - BTN_BODY_L + BTN_H
BTN_OUT = BTN_TIP_Z - Z_LID - LID_T                  # толкатель над крышкой

# экран: гребёнка слева. u -> x; f (поперёк от левого края вида спереди) -> y
XM0 = XL + PB_ZONE_X1 + BOSS_CLR
XM1 = XM0 + TFT_L

def tft_x(u):
    return XM0 + u
def tft_y(f):
    return TFT_W / 2 - f

# стойки крышки: (x, y, стенка по X: -1/0/1, стенка по Y: -1/0/1)
# слева - у макетки (между ней и экраном), справа - в углах, в зазорах у торцов HLK (слиты с двумя стенками)
HLK_X1 = IW / 2
HLK_X0 = HLK_X1 - HLK_W
HLK_XC = (HLK_X0 + HLK_X1) / 2
HLK_Y0, HLK_Y1 = -HLK_L / 2, HLK_L / 2
_xbl = XL + PB_X1 + BOSS_CLR + LID_BOSS_D / 2    # макетка - между стенкой и левыми стойками
_ybr = LEFT_BOSS_Y
_ybr_r = HLK_Y1 + HLK_CLR + LID_BOSS_D / 2       # правые - за торцами HLK
LID_BOSSES = [(_xbl, sy * _ybr, 0, 0) for sy in (-1, 1)] + \
             [(IW / 2 - LID_BOSS_D / 2, sy * _ybr_r, 1, sy) for sy in (-1, 1)]


def pb_stops():
    """2 упора под макеткой - у левых стоек крышки (пользователь): опора от стенки до стойки + стенка паза со
    стороны пайки; со стороны деталей паз замыкает сама стойка. [(x0, x1, y0, y1, z0, z1)]"""
    r = []
    for sy in (-1, 1):
        y0, y1 = sy * _ybr - PB_STOP_W / 2, sy * _ybr + PB_STOP_W / 2
        r.append((XL - 0.01, _xbl, y0, y1, BACK_T, PB_Z0))
        r.append((XL - 0.01, XL + PB_X0 - PB_SLOT_CLR, y0, y1, PB_Z0 - 0.01, PB_Z0 + PB_STOP_RIB))
    return r

HLK_POSTS = (  # (x, y, направление уха)
    (HLK_X0 - HLK_CLR - HLK_POST_D / 2, HLK_LEFT_POST_DY, "+x"),
    (HLK_XC, HLK_Y1 + HLK_CLR + HLK_POST_D / 2, "-y"),
)

# Pro Mini: свои координаты (lx - вдоль от края RESET, ly - поперёк от середины), в корпусе - вертикально:
# край RESET внизу, стойки слиты с нижней стенкой. Глобально: X = PM_CX - ly, Y = PM_BASE + lx
PM_Z0 = BACK_T + PM_RAISE
PM_TOPZ = PM_Z0 + PM_T                      # верх платы = верх стоек (ухо лежит плашмя)
PM_HALF = PM_W / 2 + PM_CLR + PM_HOLDER_T   # половина ширины с держателями
PM_CX = XM0 + PM_HALF                       # левый край держателей - по левому краю экрана (за зоной макетки)
PM_BASE = -IH / 2 + PM_POST_D + PM_POST_CLR
PM_POSTS_L = tuple((-(PM_POST_CLR + PM_POST_D / 2), s * (PM_W / 2 - PM_TONGUE_V)) for s in (-1, 1))
PM_EAR_L = PM_POST_D / 2 + PM_POST_CLR + PM_EAR_OVER   # от центра стойки до конца язычка

# Nano: сторона деталей - к левой стойке HLK
NANO_X1 = HLK_POSTS[0][0] - HLK_POST_D / 2 - NANO_CLR - NANO_COMP_H   # плата: сторона деталей
NANO_X0 = NANO_X1 - NANO_PCB_T
NANO_TOPZ = BACK_T + NANO_W
NANO_ROW_LO, NANO_ROW_HI = BACK_T + NANO_PIN_ROW, NANO_TOPZ - NANO_PIN_ROW
NANO_HOOK_Z = max(NANO_TOPZ - NANO_HOOK, NANO_ROW_HI + 0.32 + 0.3)     # низ правого выступа (хвосты штырьков)
NANO_HOOK_Z_L = max(NANO_TOPZ - NANO_HOOK, NANO_ROW_HI + NANO_HDR_H / 2 + 0.1)   # низ левого (пластик колодки)
BAR_X0 = NANO_X0 - NANO_BAR_LEFT - HLK_POSTS[0][0]                      # планка в своих координатах
BAR_X1 = HLK_EAR_L - EAR_W / 2
# места под шурупы на стену (X, Y): слева посередине (под макеткой), под Pro Mini, у HLK - по X посередине между
# выступом Nano (справа вдоль платы) и HLK, по Y - на WALL_HOLE_POST_DY выше левой стойки HLK
WALL_HOLES = ((XL + 8.8, 0.0), (PM_CX, -8.0),
              ((NANO_X1 + 0.2 + NANO_RIDGE_W + HLK_X0) / 2, HLK_POSTS[0][1] + WALL_HOLE_POST_DY))


def pm_xy(lx, ly):
    return PM_CX - ly, PM_BASE + lx


def pm_box(lx0, lx1, ly0, ly1, z0, z1):
    x0, y0 = pm_xy(lx0, ly1)
    x1, y1 = pm_xy(lx1, ly0)
    return (x0, x1, y0, y1, z0, z1)


def pm_place(shape):
    return shape.rotate((0, 0, 0), (0, 0, 1), 90).translate((PM_CX, PM_BASE, 0))


def rbox(x0, x1, y0, y1, z0, z1, r):
    """Параллелепипед со скруглёнными вертикальными рёбрами (r <= 0.05 - острые); грани по Z - плоские."""
    b = box(x0, x1, y0, y1, z0, z1)
    return b.edges("|Z").fillet(r) if r > 0.05 else b


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(x, y, z0, z1, d):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def hole(x, y, z0, z1, d):
    """Отверстие под винт / толкатель: диаметр после печати d (модель - d + HOLE_COMP)."""
    return cyl(x, y, z0, z1, d + HOLE_COMP)


def countersink(x, y, z_top, d_top, d_bot):
    """Конус 90° под головку: Ø d_top на поверхности z_top, сужается вниз до d_bot (диаметры после печати)."""
    h = (d_top - d_bot) / 2
    c = cq.Solid.makeCone((d_bot + HOLE_COMP) / 2, (d_top + HOLE_COMP) / 2, h + 0.01, cq.Vector(x, y, z_top - h),
                          cq.Vector(0, 0, 1))
    return cq.Workplane("XY").add(c)


def wall_post(x, y, d, wx, wy, z0, z1, grow=0.0):
    """Стойка, слитая со стенками: цилиндр + заполнение до стенки по X (wx) и по Y (wy): -1/0/1."""
    r = d / 2 + grow
    s = cyl(x, y, z0, z1, 2 * r)
    if wy:
        yw = wy * IH / 2
        s = s.union(box(x - r, x + r, min(y, yw), max(y, yw), z0, z1))
    if wx:
        xw = wx * IW / 2
        s = s.union(box(min(x, xw), max(x, xw), y - r, y + r, z0, z1))
    if wx and wy:
        s = s.union(box(min(x, wx * IW / 2), max(x, wx * IW / 2), min(y, wy * IH / 2), max(y, wy * IH / 2), z0, z1))
    return s


# ---------------------------------------------------------------- уши
def ear(length):
    """Ухо HLK: прямоугольник, центр отверстия - (0, 0), вытянуто по +X, Z 0..EAR_T."""
    r = EAR_W / 2
    return box(-r, length - r, -r, r, 0, EAR_T).cut(hole(0, 0, -1, EAR_T + 1, CLEAR_D))


def ear_pm():
    """Ухо Pro Mini: прямоугольник над стойкой + узкий язычок на плату (между угловым выводом и A4 / A7)."""
    r = EAR_W / 2
    e = box(-r, r, -r, r, 0, EAR_T)
    e = e.union(box(r - 0.01, PM_EAR_L, -PM_TONGUE_W / 2, PM_TONGUE_W / 2, 0, EAR_T))
    return e.cut(hole(0, 0, -1, EAR_T + 1, CLEAR_D))


def ears_all():
    """[(англ. имя, деталь на месте, деталь плашмя)] - 2 уха HLK, 2 уха Pro Mini."""
    res = []
    x, y, _ = HLK_POSTS[0]
    bar = bar_hlk_nano()
    res.append(("bar_hlk_nano", bar.translate((x, y, HLK_TOP)),
                bar.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, BAR_T))))    # печать: верхом на столе
    x, y, d = HLK_POSTS[1]
    e = ear(HLK_EAR_L)
    ang = {"+x": 0, "+y": 90, "-x": 180, "-y": -90}[d]
    res.append(("ear_hlk_2", e.rotate((0, 0, 0), (0, 0, 1), ang).translate((x, y, HLK_TOP)), e))
    for i, (lx, ly) in enumerate(PM_POSTS_L):
        e = ear_pm()
        res.append(("ear_promini_%d" % (i + 1), pm_place(e.translate((lx, ly, PM_TOPZ))), e))
    return res


def ear_box(x, y, z, direction, length):
    r = EAR_W / 2
    if direction == "+x":
        return (x - r, x + length - r, y - r, y + r, z, z + EAR_T)
    if direction == "-y":
        return (x - r, x + r, y - length + r, y + r, z, z + EAR_T)
    return (x - r, x + r, y - r, y + length - r, z, z + EAR_T)


# ---------------------------------------------------------------- Pro Mini: держатели и стойки (свои координаты)
def pm_holders_local():
    """Держатели у края UART (lx = PM_L): строятся для края в 0 (плата - в +lx), отражаются и сдвигаются."""
    z_b0, z_b1 = PM_Z0, PM_Z0 + PM_T + PM_CLR               # паз: уровень платы
    top = z_b1 + PM_LEAD + 0.6
    x0, x1 = -PM_STOP, PM_HOLDER_W
    shape = None
    for sgn, edge in ((-1, -PM_W / 2), (1, PM_W / 2)):
        inner = edge - sgn * PM_SUPPORT                    # полка под платой
        outer = edge + sgn * (PM_CLR + PM_HOLDER_T)
        post = box(x0, x1, min(inner, outer), max(inner, outer), BACK_T, top)
        notch_out = edge + sgn * PM_CLR                    # паз: край платы + зазор
        post = post.cut(box(0, x1 + 0.1, min(inner, notch_out) - 0.01, max(inner, notch_out) + 0.01, z_b0, z_b1))
        lip = edge - sgn * PM_LIP                          # губа над платой
        post = post.cut(box(x0 - 0.1, x1 + 0.1, min(inner, lip) - 0.01, max(inner, lip) + 0.01, z_b1, top + 0.1))
        # фаска захода: от кромки губы вверх-наружу до края паза
        prof = [(lip, z_b1 + 0.15), (notch_out, top + 0.01), (lip - sgn * 2.0, top + 0.01), (lip - sgn * 2.0, z_b1 + 0.15)]
        wedge = cq.Workplane("YZ").polyline(prof).close().extrude(x1 - x0 + 0.2).translate((x0 - 0.1, 0, 0))
        post = post.cut(wedge)
        shape = post if shape is None else shape.union(post)
    return shape.mirror("YZ").translate((PM_L, 0, 0))


def pm_mount():
    """Держатели у края UART + стойки у края RESET (слиты с нижней стенкой, полочка под язычком) - в корпусе."""
    s = pm_holders_local()
    wall_lx = -(PM_POST_CLR + PM_POST_D)                   # нижняя стенка в своих координатах
    for lx, ly in PM_POSTS_L:
        r = PM_POST_D / 2
        s = s.union(cyl(lx, ly, BACK_T, PM_TOPZ, PM_POST_D))
        s = s.union(box(wall_lx - 0.01, lx, ly - r, ly + r, BACK_T, PM_TOPZ))
        s = s.union(box(lx, PM_LEDGE, ly - PM_TONGUE_W / 2, ly + PM_TONGUE_W / 2, BACK_T, PM_Z0))
        s = s.cut(hole(lx, ly, PM_TOPZ - PM_POST_PILOT, PM_TOPZ + 1, PILOT_D))
    return pm_place(s)


# ---------------------------------------------------------------- корпус
def build_body():
    body = rbox(-W / 2, W / 2, -H / 2, H / 2, 0, BODY_D, CORNER_R)
    body = body.cut(rbox(-IW / 2, IW / 2, -IH / 2, IH / 2, BACK_T, BODY_D + 1, CORNER_R_IN))

    # стойки под крышку - слиты со стенками
    for x, y, wx, wy in LID_BOSSES:
        body = body.union(wall_post(x, y, LID_BOSS_D, wx, wy, BACK_T, BODY_D))
        body = body.cut(hole(x, y, BODY_D - LID_BOSS_DEPTH, BODY_D + 1, PILOT_D))

    # макетка кнопок: 2 упора с пазом (слиты со стенкой и стойками крышки)
    for b in pb_stops():
        body = body.union(box(*b))

    # HLK: стойка слева (отдельно стоящая) и у верхнего торца (слита с верхней стенкой)
    for i, (x, y, _) in enumerate(HLK_POSTS):
        if i == 1:
            body = body.union(wall_post(x, y, HLK_POST_D, 0, 1, BACK_T, HLK_TOP))
        else:
            body = body.union(cyl(x, y, BACK_T, HLK_TOP, HLK_POST_D))
        body = body.cut(hole(x, y, HLK_TOP - HLK_POST_PILOT, HLK_TOP + 1, PILOT_D))

    # Pro Mini
    body = body.union(pm_mount())

    # Nano на ребре: низкие выступы у задней стенки (справа вдоль платы, слева - у торцов)
    for b in nano_ridges():
        body = body.union(box(*b))

    # места под шурупы на стену: утонения изнутри (снаружи гладко), сверлить нужные
    for x, y in WALL_HOLES:
        body = body.cut(hole(x, y, THIN_SKIN, BACK_T + 1, WALL_HOLE_D))

    # утонения под провода: изнутри, остаток THIN_SKIN (снаружи гладко)
    body = body.cut(thin_spots())
    return body


def thin_spot_list():
    """(ось, (a, b, c), диаметр, название): «x» - в левой/правой стенке (a = X начала, b = Y, c = Z),
    «y» - в нижней/верхней (a = X, b = Y начала, c = Z)."""
    dm, ds = MAINS_D + HOLE_CLR, SENSOR_D + HOLE_CLR
    depth = WALL - THIN_SKIN
    return [
        ("x", (IW / 2, HLK_Y0 + HLK_PIN_U + 1.0, HLK_TOP + dm / 2 + 0.5), dm, "сеть - правая стенка у AC (над HLK)"),
        ("y", (HLK_XC, -IH / 2 - depth, SENSOR_Z), dm, "сеть - нижняя стенка у AC (у дна)"),
        ("x", (-IW / 2 - depth, 0.0, min(SENSOR_Z, PB_Z0 - ds / 2 - 0.3)), ds, "датчик - левая стенка"),
        ("y", (XL + PB_X1 + 4.0, -IH / 2 - depth, SENSOR_Z), ds, "датчик - нижняя стенка слева"),
        ("y", (XL + PB_X1 + 4.0, IH / 2, SENSOR_Z), ds, "датчик - верхняя стенка слева"),
    ]


def thin_spots():
    depth = WALL - THIN_SKIN
    shape = None
    for axis, (a, b, c), d, _ in thin_spot_list():
        if axis == "x":
            s = cq.Workplane("YZ").circle(d / 2).extrude(depth).translate((a, b, c))
        else:
            s = cq.Workplane("XZ").circle(d / 2).extrude(-depth).translate((a, b, c))
        shape = s if shape is None else shape.union(s)
    return shape


# ---------------------------------------------------------------- Nano
def nano_ridges():
    """Выступы у задней стенки: справа вдоль платы, слева - у торцов (за рядами штырьков)."""
    r = [(NANO_X1 + 0.2, NANO_X1 + 0.2 + NANO_RIDGE_W, -NANO_L / 2 + 3, NANO_L / 2 - 3, BACK_T, BACK_T + NANO_RIDGE_H)]
    for sy in (-1, 1):
        y0, y1 = sorted((sy * (NANO_HDR_SPAN / 2 + 0.4), sy * (NANO_L / 2 - 0.2)))
        r.append((NANO_X0 - 0.2 - NANO_RIDGE_W, NANO_X0 - 0.2, y0, y1, BACK_T, BACK_T + NANO_END_RIDGE_H))
    return r


def nano_zones():
    """Nano (вместо Pro Mini): плата, детали (сторона USB), штырьки с колодкой - зоны для проверок."""
    yl, yu = -NANO_L / 2 - NANO_USB, NANO_L / 2 + NANO_USB
    return {
        "Nano: плата": (NANO_X0, NANO_X1, -NANO_L / 2, NANO_L / 2, BACK_T, NANO_TOPZ),
        "Nano: детали": (NANO_X1, NANO_X1 + NANO_COMP_H, yl, yu, BACK_T + NANO_RIDGE_H + 0.3, NANO_HOOK_Z - 0.01),
        "Nano: штырьки": (NANO_X0 - NANO_PINS, NANO_X0, -NANO_HDR_SPAN / 2, NANO_HDR_SPAN / 2, BACK_T,
                          NANO_ROW_HI + NANO_HDR_H / 2),
    }


def bar_hlk_nano():
    """Общая планка на левой стойке HLK (свои координаты: центр отверстия - (0, 0), низ - Z 0 = верх HLK):
    вправо - на HLK, влево - паз над ребром Nano (низ паза = верх Nano) между двумя выступами вниз - на тех же
    местах по X, что и выступы у задней стенки (пользователь): справа - по стороне деталей, слева - по стороне штырьков
    (ниже пластика колодки не опускается)."""
    r = EAR_W / 2
    x0 = HLK_POSTS[0][0]
    b = box(BAR_X0, BAR_X1, -r, r, 0, BAR_T)
    b = b.cut(box(BAR_X0 - 0.1, NANO_X1 + 0.2 - x0, -r - 0.1, r + 0.1, -0.1, NANO_TOPZ - HLK_TOP))
    for (xa, xb), zl in nano_bar_hooks():
        b = b.union(box(xa - x0, xb - x0, -r, r, zl - HLK_TOP, NANO_TOPZ - HLK_TOP + 0.01))
    return b.cut(hole(0, 0, -1, BAR_T + 1, CLEAR_D))


def nano_bar_hooks():
    """Выступы планки над Nano: ((x0, x1), низ Z) - справа по стороне деталей, слева по стороне штырьков."""
    right = (NANO_X1 + 0.2, NANO_X1 + 0.2 + NANO_RIDGE_W)
    left = (NANO_X0 - 0.2 - NANO_RIDGE_W, NANO_X0 - 0.2)
    return [(right, NANO_HOOK_Z), (left, NANO_HOOK_Z_L)]


# ---------------------------------------------------------------- крышка
def build_lid():
    lid = rbox(-W / 2, W / 2, -H / 2, H / 2, Z_LID, DEPTH, CORNER_R)
    # бортик внутрь корпуса, с вырезами под стойки (слева - между стенкой и макеткой)
    rim_o = rbox(-IW / 2 + FIT, IW / 2 - FIT, -IH / 2 + FIT, IH / 2 - FIT, Z_LID - LID_LIP_H, Z_LID + 0.01,
                 CORNER_R_IN - FIT)
    rim_i = rbox(-IW / 2 + FIT + LID_LIP_T, IW / 2 - FIT - LID_LIP_T, -IH / 2 + FIT + LID_LIP_T,
                 IH / 2 - FIT - LID_LIP_T, Z_LID - LID_LIP_H - 1, Z_LID + 0.02, CORNER_R_IN - FIT - LID_LIP_T)
    rim = rim_o.cut(rim_i)
    for x, y, wx, wy in LID_BOSSES:
        rim = rim.cut(wall_post(x, y, LID_BOSS_D, wx, wy, Z_LID - LID_LIP_H - 1, Z_LID, grow=FIT))
    lid = lid.union(rim)
    for x, y, _, _ in LID_BOSSES:
        lid = lid.cut(hole(x, y, Z_LID - 1, DEPTH + 1, CLEAR_D))
        lid = lid.cut(countersink(x, y, DEPTH, LID_CSK_D, CLEAR_D))    # конус под головку (печать лицом вниз - без поддержек)
    for c in PB_BTN_COLS:                              # толкатели кнопок
        y, _ = pb_yz(c, PB_BTN_ROW)
        lid = lid.cut(hole(BTN_X, y, Z_LID - 1, DEPTH + 1, BTN_HOLE_D))

    # окно экрана: AA + поле
    wy = TFT_AA_W / 2 + WINDOW_MARGIN
    lid = lid.cut(box(tft_x(TFT_AA_U0) - WINDOW_MARGIN, tft_x(TFT_AA_U1) + WINDOW_MARGIN, -wy, wy, Z_LID - 1, DEPTH + 1))

    # стойки модуля экрана: до рамки LCD 3.5 мм - стойки полные (рамка - вычитается на всякий случай)
    lcd = box(tft_x(TFT_BL_U0) - TFT_BOSS_GLASS_CLR, tft_x(TFT_BL_U1) + TFT_BOSS_GLASS_CLR,
              -TFT_BL_W / 2 - TFT_BOSS_GLASS_CLR, TFT_BL_W / 2 + TFT_BOSS_GLASS_CLR,
              Z_LID - TFT_GAP - TFT_STACK - 0.01, Z_LID + 0.01)
    zb = Z_LID - TFT_GAP - TFT_STACK
    for u in (TFT_HOLE_U1, TFT_HOLE_U2):
        for v in (-TFT_HOLE_DV / 2, TFT_HOLE_DV / 2):
            lid = lid.union(cyl(tft_x(u), v, zb, Z_LID, TFT_BOSS_D).cut(lcd))
            lid = lid.cut(hole(tft_x(u), v, zb - 0.1, zb + TFT_PILOT_DEPTH, TFT_PILOT_D))
    return lid


def screw_list():
    """(где, Ø, длина самореза, толщина прижимаемой детали, глубина глухого, доступная высота) - проверка запаса."""
    return [
        ("крышка в стойки корпуса", 2.5, LID_SCREW_L, LID_T, LID_BOSS_DEPTH, BODY_D - BACK_T),
        ("ухо HLK", 2.5, HLK_SCREW_L, EAR_T, HLK_POST_PILOT, HLK_TOP - BACK_T),
        ("планка HLK + Nano", 2.5, HLK_SCREW_L, BAR_T, HLK_POST_PILOT, HLK_TOP - BACK_T),
        ("уши Pro Mini", 2.5, PM_SCREW_L, EAR_T, PM_POST_PILOT, PM_TOPZ - BACK_T),
        ("плата экрана в стойки крышки", TFT_SCREW_D, TFT_SCREW_L, TFT_PCB_T, TFT_PILOT_DEPTH,
         TFT_STACK + TFT_GAP + LID_T - 0.8),
    ]


def tft_boss_full():
    """Стойки экрана не задевают рамку LCD (полные)."""
    r = TFT_BOSS_D / 2 + TFT_BOSS_GLASS_CLR
    for u in (TFT_HOLE_U1, TFT_HOLE_U2):
        du = max(TFT_BL_U0 - u, 0.0, u - TFT_BL_U1)          # до прямоугольника рамки по u и v
        dv = max(TFT_HOLE_DV / 2 - TFT_BL_W / 2, 0.0)
        if (du * du + dv * dv) ** 0.5 < r:
            return False
    return True


# ---------------------------------------------------------------- модели деталей (для сборки и проверок)
LABELS = {   # англ. имя (STEP) -> подпись на чертеже
    "tft_glass": "экран: рамка LCD", "tft_pcb": "экран: плата", "tft_header_zone": "штыри экрана",
    "perfboard": "макетка", "perfboard_parts_zone": "детали макетки", "perfboard_c1": "C1 на макетке",
    "button_1": "кнопка 1", "button_2": "кнопка 2",
    "hlk": "HLK", "promini": "Pro Mini", "promini_plug_zone": "разъём USB-UART",
}
ZONES = ("tft_header_zone", "perfboard_parts_zone", "promini_plug_zone")
LID_PARTS = ("tft_glass", "tft_pcb", "tft_header_zone")


def hlk_pins():
    """Зоны выводов HLK: имя -> габарит (AC - у нижнего торца, DC - у верхнего; поперёк - по X)."""
    p = {}
    for name, yc, vs in (("hlk_pin_ac", HLK_Y0 + HLK_PIN_U, HLK_PIN_AC_V), ("hlk_pin_dc", HLK_Y1 - HLK_PIN_U, HLK_PIN_DC_V)):
        for i, v in enumerate((-vs, vs)):
            xc = HLK_XC + v
            p["%s_%d" % (name, i + 1)] = (xc - HLK_PIN_ZONE, xc + HLK_PIN_ZONE, yc - HLK_PIN_ZONE, yc + HLK_PIN_ZONE,
                                          HLK_TOP, HLK_TOP + HLK_PIN_CUT)
    return p


def tft_back_parts():
    zb = TFT_PCB_BACK
    return {"экран сзади: " + n: (tft_x(u0), tft_x(u1), tft_y(f1), tft_y(f0), zb - TFT_SMD_H, zb)
            for n, (u0, u1, f0, f1) in TFT_BACK_PARTS.items()}


def parts():
    """англ. имя -> (x0, x1, y0, y1, z0, z1): габариты деталей, ушей, головок саморезов и зон проводов."""
    zg = Z_LID - TFT_GAP
    p = {
        "tft_glass": (tft_x(TFT_BL_U0), tft_x(TFT_BL_U1), -TFT_BL_W / 2, TFT_BL_W / 2, zg - TFT_STACK, zg),
        "tft_pcb": (XM0, XM1, -TFT_W / 2, TFT_W / 2, TFT_PCB_BACK, TFT_PCB_BACK + TFT_PCB_T),
        "tft_header_zone": (XM0, tft_x(TFT_PINS_U + 2.0), -TFT_PINS_SPAN / 2 - 2, TFT_PINS_SPAN / 2 + 2,
                            TFT_PCB_BACK - TFT_PINS_BACK, TFT_PCB_BACK),
        "perfboard": (XL + PB_X0, XL + PB_X1, PB_Y0, PB_Y1, PB_Z0, PB_Z1),
        "perfboard_parts_zone": (XL + PB_X1, XL + PB_ZONE_X1, -_ybr + LID_BOSS_D / 2 + PB_PARTS_CLR,
                                 _ybr - LID_BOSS_D / 2 - PB_PARTS_CLR, PB_Z0, PB_Z1),
        "perfboard_c1": (XL + PB_X1, XL + PB_X1 + PB_C1_H) + pb_c1_yz(),
        "hlk": (HLK_X0, HLK_X1, HLK_Y0, HLK_Y1, BACK_T, HLK_TOP),
        "promini": pm_box(0, PM_L, -PM_W / 2, PM_W / 2, PM_Z0 - PM_TAILS, PM_TOPZ + PM_TOP_H),
        "promini_plug_zone": pm_box(PM_UART_U - 2.0, PM_L + PM_STOP, -PM_PLUG_W / 2, PM_PLUG_W / 2, PM_TOPZ, BODY_D),
    }
    for i, c in enumerate(PB_BTN_COLS):                # корпус кнопки (толкатель - plungers())
        y, _ = pb_yz(c, PB_BTN_ROW)
        p["button_%d" % (i + 1)] = (XL + PB_X1, XL + PB_X1 + BTN_W, y - BTN_W / 2, y + BTN_W / 2,
                                    BTN_PLATE_Z - BTN_BODY_L, BTN_PLATE_Z + BTN_RIVET)
    for i, (x, y, d) in enumerate(HLK_POSTS):
        t = BAR_T if i == 0 else EAR_T
        if i == 0:
            p["bar_hlk_nano"] = (x + BAR_X0, x + BAR_X1, y - EAR_W / 2, y + EAR_W / 2, NANO_TOPZ, HLK_TOP + BAR_T)
        else:
            p["ear_hlk_%d" % (i + 1)] = ear_box(x, y, HLK_TOP, d, HLK_EAR_L)
        p["head_hlk_%d" % (i + 1)] = (x - HEAD_D / 2, x + HEAD_D / 2, y - HEAD_D / 2, y + HEAD_D / 2,
                                      HLK_TOP + t, HLK_TOP + t + HEAD_H)
    for i, (lx, ly) in enumerate(PM_POSTS_L):
        r = EAR_W / 2
        p["ear_promini_%d" % (i + 1)] = pm_box(lx - r, lx + PM_EAR_L, ly - r, ly + r, PM_TOPZ, PM_TOPZ + EAR_T)
        x, y = pm_xy(lx, ly)
        p["head_promini_%d" % (i + 1)] = (x - HEAD_D / 2, x + HEAD_D / 2, y - HEAD_D / 2, y + HEAD_D / 2,
                                          PM_TOPZ + EAR_T, PM_TOPZ + EAR_T + HEAD_H)
    return p


def pb_c1_yz():
    """C1 на макетке: (y0, y1, z0, z1) - габарит Ø PB_C1_D вокруг центра."""
    y, z = pb_yz(PB_C1_COL, PB_C1_ROW)
    r = PB_C1_D / 2
    return (y - r, y + r, z - r, z + r)


def plungers():
    """Толкатели кнопок: англ. имя -> (x, y, z0, z1) - через крышку."""
    return {"button_%d_plunger" % (i + 1): (BTN_X, pb_yz(c, PB_BTN_ROW)[0], BTN_PLATE_Z, BTN_TIP_Z)
            for i, c in enumerate(PB_BTN_COLS)}


def body_features():
    """Стойки и держатели корпуса (для проверок): имя -> габарит."""
    f = {}
    for i, b in enumerate(nano_ridges()):
        f["выступ Nano %d" % (i + 1)] = b
    for i, (x, y, _) in enumerate(HLK_POSTS):
        r = HLK_POST_D / 2
        f["стойка HLK %d" % (i + 1)] = (x - r, x + r, y - r, y + r if i == 0 else IH / 2, BACK_T, HLK_TOP)
    for i, (lx, ly) in enumerate(PM_POSTS_L):
        r = PM_POST_D / 2
        f["стойка Pro Mini %d" % (i + 1)] = pm_box(-(PM_POST_CLR + PM_POST_D), lx + r, ly - r, ly + r, BACK_T, PM_TOPZ)
    for i, sgn in enumerate((-1, 1)):
        ye = sgn * PM_W / 2
        y_out = ye + sgn * (PM_CLR + PM_HOLDER_T)
        f["держатель Pro Mini %d" % (i + 1)] = pm_box(PM_L - PM_HOLDER_W, PM_L + PM_STOP, min(ye, y_out), max(ye, y_out),
                                                      BACK_T, PM_Z0 + PM_T + PM_CLR + PM_LEAD + 0.6)
    for i, (x, y, wx, wy) in enumerate(LID_BOSSES):
        r = LID_BOSS_D / 2
        x0, x1 = (x - r, IW / 2) if wx > 0 else (x - r, x + r)
        y0, y1 = (y - r, IH / 2) if wy > 0 else ((-IH / 2, y + r) if wy < 0 else (y - r, y + r))
        f["стойка крышки %d" % (i + 1)] = (x0, x1, y0, y1, BACK_T, BODY_D)
    for i, b in enumerate(pb_stops()):
        f["упор макетки %d" % (i + 1)] = b
    return f


def overlap(a, b):
    return all(min(a[i + 1], b[i + 1]) - max(a[i], b[i]) > 0 for i in (0, 2, 4))


def label(n):
    if n in LABELS:
        return LABELS[n]
    m = re.match(r"(ear|head)_(hlk|promini|perfboard)_(\d)", n)
    if m:
        what = {"hlk": "HLK", "promini": "Pro Mini", "perfboard": "макетки"}[m.group(2)]
        return "%s %s %s" % ("ухо" if m.group(1) == "ear" else "головка самореза", what, m.group(3))
    return n


def checks():
    ok = True
    warn = []
    p = parts()
    names = list(p)
    allowed = {("tft_glass", "tft_pcb"), ("tft_pcb", "tft_header_zone"), ("perfboard", "perfboard_parts_zone"),
               ("perfboard_parts_zone", "button_1"), ("perfboard_parts_zone", "button_2"),
               ("promini", "promini_plug_zone"), ("tft_header_zone", "promini_plug_zone"),
               ("tft_pcb", "promini_plug_zone"), ("tft_glass", "promini_plug_zone"),   # разъём - при снятой крышке
               ("promini", "ear_promini_1"), ("promini", "ear_promini_2")}            # язычки - на край платы
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if (a, b) in allowed or (b, a) in allowed:
                continue
            if overlap(p[a], p[b]):
                print("  ПЕРЕСЕЧЕНИЕ: %s / %s" % (label(a), label(b)))
                ok = False
    # детали и стойки корпуса
    for fn, fb in body_features().items():
        for n, b in p.items():
            if n.startswith(("ear_", "head_")) and fn.startswith(("стойка HLK", "стойка Pro Mini")):
                continue                                   # ухо и головка - на своей стойке
            if n == "promini" and fn.startswith(("стойка Pro Mini", "держатель Pro Mini")):
                continue                                   # полочки и пазы под платой - так задумано
            if overlap(fb, b):
                print("  ПЕРЕСЕЧЕНИЕ: %s / %s" % (fn, label(n)))
                ok = False
    # экран сзади: детали платы экрана против HLK, ушей и головок саморезов (ошибка), выводов HLK (внимание)
    for bn, bb in tft_back_parts().items():
        for n, b in p.items():
            if n in LID_PARTS or n in ZONES:
                continue
            if overlap(bb, b):
                print("  ПЕРЕСЕЧЕНИЕ: %s / %s" % (bn, label(n)))
                ok = False
        for n, b in hlk_pins().items():
            if overlap(bb, b):
                print("  ПЕРЕСЕЧЕНИЕ: вывод HLK %s (%.1f мм) / %s" % (n.replace("hlk_pin_", "").upper(),
                                                                  HLK_PIN_CUT, bn))
                ok = False
    # внутри полости
    for n, b in p.items():
        if b[0] < -IW / 2 or b[1] > IW / 2 or b[2] < -IH / 2 or b[3] > IH / 2 or b[4] < BACK_T - PM_TAILS - 0.1 \
                or b[5] > Z_LID:
            print("  ВЫХОДИТ ЗА ПОЛОСТЬ: %s" % label(n))
            ok = False
    # скруглённые углы полости: детали и стойки не заходят в угловой квадрат CORNER_R_IN (с бортиком крышки)
    rc = CORNER_R_IN + 0.1
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * IW / 2, sx * (IW / 2 - rc)))
            ya, yb = sorted((sy * IH / 2, sy * (IH / 2 - rc)))
            corner = (xa, xb, ya, yb, 0, BODY_D)
            for n, b in list(p.items()) + list(body_features().items()):
                if n.startswith("стойка крышки"):
                    continue                           # стойки крышки в углу слиты со стенками - так задумано
                if n not in ZONES and overlap(corner, b):
                    print("  В СКРУГЛЁННОМ УГЛУ ПОЛОСТИ: %s" % label(n))
                    ok = False
    # отверстия на стену: над головкой до крышки нет деталей корпуса и стоек (крышка с экраном снята)
    allp = {n: b for n, b in p.items() if n not in LID_PARTS and n != "promini_plug_zone"}
    removable = ("perfboard", "perfboard_parts_zone", "perfboard_c1", "button_1", "button_2",   # снимаются на монтаж
                 "promini", "ear_promini_1", "ear_promini_2", "head_promini_1", "head_promini_2",
                 "hlk", "bar_hlk_nano", "ear_hlk_2", "head_hlk_1", "head_hlk_2")
    allp.update(body_features())
    for x, y in WALL_HOLES:
        r = WALL_HEAD_D / 2 + WALL_HEAD_CLR
        zone = (x - r, x + r, y - r, y + r, 0, BODY_D)
        for n, b in allp.items():
            if n in removable:
                continue                               # макетка снимается на время монтажа
            if overlap(zone, b):
                print("  ОТВЕРСТИЕ НА СТЕНУ (%.0f, %.0f) ПОД: %s" % (x, y, label(n)))
                ok = False
    # разъём USB-UART сверху: свободно от деталей и стоек корпуса
    for n, b in allp.items():
        if n not in ("promini",) and not n.startswith("ear_promini") and overlap(p["promini_plug_zone"], b):
            print("  РАЗЪЁМ USB-UART УПИРАЕТСЯ В: %s" % label(n))
            ok = False
    # утонения не упираются в стойки и детали (сверлить снаружи - только через стенку)
    for axis, (a, b, c), d, name in thin_spot_list():
        r = d / 2
        if axis == "x":
            zone = (IW / 2 - 3 if a > 0 else -IW / 2, IW / 2 if a > 0 else -IW / 2 + 3, b - r, b + r, c - r, c + r)
        else:
            zone = (a - r, a + r, IH / 2 - 3 if b > 0 else -IH / 2, IH / 2 if b > 0 else -IH / 2 + 3, c - r, c + r)
        for fn, fb in list(body_features().items()) + list(allp.items()) + list(hlk_pins().items()):
            if overlap(zone, fb):
                print("  УТОНЕНИЕ «%s» УПИРАЕТСЯ В: %s" % (name, label(fn)))
                ok = False
    for zn, zb in nano_zones().items():
        for n, b in list(p.items()) + list(body_features().items()) + list(tft_back_parts().items()):
            if n in LID_PARTS or n in ZONES or n.startswith(("promini", "ear_promini", "head_promini", "выступ Nano")) \
                    or n == "bar_hlk_nano":
                continue                               # Pro Mini - вместо Nano; выступы и планка - по Nano
            if overlap(zb, b):
                print("  NANO УПИРАЕТСЯ: %s / %s" % (zn, label(n)))
                ok = False
    for zn, zb in nano_zones().items():                # выступы - только по своим местам
        for i, rb in enumerate(nano_ridges()):
            if overlap(zb, rb):
                print("  ВЫСТУП %d УПИРАЕТСЯ В: %s" % (i + 1, zn))
                ok = False
    y = HLK_POSTS[0][1]
    for (xa, xb), zl in nano_bar_hooks():                # выступы планки - не на деталях Nano
        hb = (xa, xb, y - EAR_W / 2, y + EAR_W / 2, zl, NANO_TOPZ)
        for zn, zb in nano_zones().items():
            if overlap(hb, zb):
                print("  ВЫСТУП ПЛАНКИ УПИРАЕТСЯ В: %s" % zn)
                ok = False
        if NANO_TOPZ - zl < 0.2:
            print("  ВЫСТУП ПЛАНКИ x %.1f..%.1f: глубина %.2f мм - мала" % (xa, xb, NANO_TOPZ - zl))
            ok = False
    if NANO_TOPZ < HLK_TOP:
        print("  NANO НИЖЕ HLK: планка не прижмёт Nano")
        ok = False
    # кнопки: толкатель над крышкой, отверстие - между бортиком крышки и платой экрана
    if BTN_OUT < BTN_OUT_MIN:
        print("  ТОЛКАТЕЛЬ НАД КРЫШКОЙ %.1f мм - мало (нужно от %.1f)" % (BTN_OUT, BTN_OUT_MIN))
        ok = False
    if BTN_X - BTN_HOLE_D / 2 < XL + FIT + LID_LIP_T + 0.5 or BTN_X + BTN_HOLE_D / 2 > XM0 - 0.5:
        print("  ОТВЕРСТИЕ КНОПКИ ЗАДЕВАЕТ БОРТИК КРЫШКИ / ПЛАТУ ЭКРАНА")
        ok = False
    # саморезы: запас у дна глухого отверстия, отверстие не глубже стойки
    for name, sd, ln, t, depth, post in screw_list():
        m = t + depth - ln
        note = "" if m >= SCREW_MARGIN - 1e-6 else " (меньше %.1f - не позволяет высота стойки)" % SCREW_MARGIN
        print("  саморез %.1f x %d, %s: запас у дна %.1f мм%s" % (sd, ln, name, m, note))
        if m < SCREW_MARGIN_MIN - 1e-6:
            print("  САМОРЕЗ УПРЁТСЯ: %s (запас %.1f < %.1f)" % (name, m, SCREW_MARGIN_MIN))
            ok = False
        if depth > post + 1e-6:
            print("  ОТВЕРСТИЕ ГЛУБЖЕ СТОЙКИ: %s (%.1f > %.1f)" % (name, depth, post))
            ok = False
    if not tft_boss_full():
        print("  СТОЙКИ ЭКРАНА ЗАДЕВАЮТ РАМКУ LCD")
        ok = False
    for w in dict.fromkeys(warn):
        print("  ВНИМАНИЕ: " + w)
    return ok


# ---------------------------------------------------------------- чертёж
def layout_png(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 6.5), gridspec_kw={"width_ratios": [W, DEPTH * 1.6]})
    for ax in (ax1, ax2):
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)

    def rect(ax, b, **kw):
        ax.add_patch(Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], **kw))

    # вид спереди (крышка прозрачная)
    ax1.add_patch(Rectangle((-W / 2, -H / 2), W, H, fc="none", ec="k", lw=2))
    ax1.add_patch(Rectangle((-IW / 2, -IH / 2), IW, IH, fc="none", ec="k", lw=1))
    colors = {"tft_pcb": "#9ecae1", "tft_glass": "#3182bd", "tft_header_zone": "#fdae6b",
              "perfboard": "#2ca02c", "perfboard_parts_zone": "#a1d99b", "perfboard_c1": "#e6550d",
              "hlk": "#fc9272", "promini": "#bcbddc",
              "bar_hlk_nano": "#4a6fe3", "ear_hlk_2": "#4a6fe3", "ear_promini_1": "#4a6fe3", "ear_promini_2": "#4a6fe3"}
    p = parts()
    for n, c in colors.items():
        b = p[n]
        rect(ax1, b, fc=c, ec="k", alpha=0.6, lw=0.8)
        if not n.startswith("ear") and n not in ("perfboard", "perfboard_c1"):
            ax1.text((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, label(n).replace("экран: ", ""), ha="center",
                     va="center", fontsize=8, rotation=90 if n == "perfboard_parts_zone" else 0)
    for n, b in tft_back_parts().items():
        rect(ax1, b, fc="none", ec="m", ls="--", lw=0.8)
    for n, b in hlk_pins().items():
        rect(ax1, b, fc="r", ec="none", alpha=0.8)
    for n, b in body_features().items():
        rect(ax1, b, fc="0.55", ec="k", alpha=0.7, lw=0.6)
    for zn, nz in nano_zones().items():
        rect(ax1, nz, fc="none", ec="darkorange", ls="--", lw=1.0)
    ax1.text(NANO_X0, NANO_L / 2 - 3, "Nano", ha="right", fontsize=8, color="darkorange")
    ax1.add_patch(Rectangle((tft_x(TFT_AA_U0) - WINDOW_MARGIN, -TFT_AA_W / 2 - WINDOW_MARGIN),
                            TFT_AA_U1 - TFT_AA_U0 + 2 * WINDOW_MARGIN, TFT_AA_W + 2 * WINDOW_MARGIN,
                            fc="none", ec="b", lw=2, ls="--"))
    depth = WALL - THIN_SKIN
    for axis, (a, b, c), d, name in thin_spot_list():
        col = "r" if "сеть" in name else "g"
        if axis == "x":
            ax1.add_patch(Rectangle((a, b - d / 2), depth, d, fc=col))
        else:
            ax1.add_patch(Rectangle((a - d / 2, b), d, depth, fc=col))
    for n in ("button_1", "button_2"):                         # кнопки: корпус и толкатель (через крышку)
        rect(ax1, p[n], fc="0.3", ec="k", alpha=0.8, lw=0.6)
    for x, y, _, _ in plungers().values():
        ax1.add_patch(Circle((x, y), BTN_HOLE_D / 2, fc="w", ec="k", lw=1.2))
    for x, y in WALL_HOLES:
        ax1.add_patch(Circle((x, y), WALL_HOLE_D / 2, fc="w", ec="r", lw=1.5))
        ax1.add_patch(Circle((x, y), WALL_HEAD_D / 2, fc="none", ec="r", lw=0.8, ls=":"))
    ax1.set_xlim(-W / 2 - 4, W / 2 + 4)
    ax1.set_ylim(-H / 2 - 4, H / 2 + 4)
    ax1.set_title("Вид спереди: %.1f x %.1f мм (красное - утонения сети и выводы HLK, зелёное - утонения датчика, "
                  "синее - уши, серое - стойки, сиреневый пунктир - детали на обороте экрана)" % (W, H), fontsize=9)

    # вид слева (Y-Z, стена слева): макетка на упорах, кнопки с толкателями через крышку, глубина
    ax2.add_patch(Rectangle((0, -H / 2), DEPTH, H, fc="none", ec="k", lw=2))
    ax2.add_patch(Rectangle((0, -H / 2), BACK_T, H, fc="0.8", ec="k"))
    ax2.add_patch(Rectangle((Z_LID, -H / 2), LID_T, H, fc="0.8", ec="k"))
    for n in ("hlk", "promini", "tft_pcb", "tft_glass", "perfboard"):
        b = p[n]
        ax2.add_patch(Rectangle((b[4], b[2]), b[5] - b[4], b[3] - b[2], fc=colors[n], ec="k", alpha=0.5, lw=0.8))
    for n in ("tft_header_zone",):
        b = p[n]
        ax2.add_patch(Rectangle((b[4], b[2]), b[5] - b[4], b[3] - b[2], fc="none", ec="r", ls=":", lw=1))
    for n in ("button_1", "button_2"):
        b = p[n]
        ax2.add_patch(Rectangle((b[4], b[2]), b[5] - b[4], b[3] - b[2], fc="0.3", ec="k", lw=0.6))
    for _, y, z0, z1 in plungers().values():
        ax2.add_patch(Rectangle((z0, y - BTN_PLUNGER_D / 2), z1 - z0, BTN_PLUNGER_D, fc="k"))
    for b in pb_stops():
        ax2.add_patch(Rectangle((b[4], b[2]), b[5] - b[4], b[3] - b[2], fc="0.55", ec="k", lw=0.6))
    ax2.set_xlim(-3, DEPTH + 3)
    ax2.set_ylim(-H / 2 - 4, H / 2 + 4)
    ax2.set_title("Слева: глубина %.1f мм (стена слева; кнопки - тёмные, толкатель над крышкой %.1f; "
                  "упоры - серые)" % (DEPTH, BTN_OUT), fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=90)


# ---------------------------------------------------------------- разрезы крепления Pro Mini
def section_grid(shape, y, x0, x1, z0, z1, step=0.1):
    """Сечение Y = y на сетке: 1 - точка внутри тела (честная проверка, без триангуляции)."""
    import numpy as np
    solid = shape.val()
    xs = np.arange(x0, x1, step)
    zs = np.arange(z0, z1, step)
    g = np.zeros((len(zs), len(xs)))
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            g[j, i] = solid.isInside(cq.Vector(x, y, z), 1e-4)
    return g


def sections_png(body, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    cuts = ((PM_L - PM_HOLDER_W / 2, "держатели у края UART"),
            (PM_POSTS_L[0][0], "стойки у края RESET (за краем платы)"),
            (PM_LEDGE / 2, "язычки ушей на краю платы"))
    fig, axs = plt.subplots(1, 3, figsize=(18, 5))
    for ax, (lx, title) in zip(axs, cuts):
        y = pm_xy(lx, 0)[1]
        x0, x1, z1 = PM_CX - PM_HALF - 4, PM_CX + PM_HALF + 4, PM_TOPZ + PM_TOP_H + 4
        g = section_grid(body, y, x0, x1, 0.0, z1)
        ax.imshow(g, origin="lower", extent=(x0, x1, 0.0, z1), cmap="Greys", vmin=0, vmax=2.2,
                  interpolation="nearest")
        if lx >= 0:
            ax.add_patch(Rectangle((PM_CX - PM_W / 2, PM_Z0), PM_W, PM_T, fc="#3a5fcd"))     # плата
        for plx, ply in PM_POSTS_L:                                                     # уши
            px = pm_xy(plx, ply)[0]
            if lx < 0:
                ax.add_patch(Rectangle((px - EAR_W / 2, PM_TOPZ), EAR_W, EAR_T, fc="#4a6fe3", alpha=0.8))
            elif lx < PM_EAR_OVER:
                ax.add_patch(Rectangle((px - PM_TONGUE_W / 2, PM_TOPZ), PM_TONGUE_W, EAR_T, fc="#4a6fe3", alpha=0.8))
        ax.set_xlim(x0, x1)
        ax.set_ylim(-0.5, z1)
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.set_title("Pro Mini, разрез Y = %.1f: %s\n(X вправо, Z вверх от стены)" % (y, title), fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=90)


# ---------------------------------------------------------------- 3D-предпросмотр
def preview_png(body, lid, path):
    """Корпус (сверху-спереди, без крышки) и крышка (изнутри): сетка треугольников с простым освещением."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    def mesh(wp, flip=False):
        verts, tris = wp.val().tessellate(0.2, 0.3)
        v = np.array([(p.x, p.y, p.z) for p in verts])
        if flip:
            v[:, 0], v[:, 2] = -v[:, 0], DEPTH - v[:, 2]   # крышка изнутри
        return v[np.array(tris)]

    fig = plt.figure(figsize=(16, 7))
    for k, (wp, title, flip) in enumerate(((body, "Корпус (крышка снята)", False),
                                          (lid, "Крышка изнутри (зеркально: левое - справа)", True))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        t = mesh(wp, flip)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
        light = np.clip(n @ np.array([-0.4, -0.5, 0.75]), 0.15, 1.0)
        pc = Poly3DCollection(t, facecolors=plt.cm.Greys(0.35 + 0.6 * light), edgecolors="none")
        ax.add_collection3d(pc)
        ax.set_xlim(-W / 2, W / 2); ax.set_ylim(-W / 2, W / 2); ax.set_zlim(0, W)
        ax.view_init(elev=55, azim=-70)
        ax.set_axis_off()
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=90)


STL_TOL, STL_ANG = 0.01, 0.05      # допуск разбиения STL (мм, рад): отверстие Ø3 - ошибка < 0.01


def export_stl(shape, path):
    cq.exporters.export(shape, path, tolerance=STL_TOL, angularTolerance=STL_ANG)


# ---------------------------------------------------------------- Readme
PARAMS_START, PARAMS_END = "<!-- enclosure-params -->", "<!-- /enclosure-params -->"


def update_readme(tables):
    """tables: вариант -> {параметр: значение}; одинаковые во всех вариантах значения - одной ячейкой."""
    path = os.path.join(ROOT, "Readme.md")
    s = open(path, encoding="utf-8").read()
    keys = list(dict.fromkeys(k for t in tables.values() for k in t))
    vs = list(tables)
    rows = ["| Параметр | " + " | ".join(TFT_NAMES[v] for v in vs) + " |", "|---|" + "---|" * len(vs)]
    for k in keys:
        vals = [tables[v].get(k, "-") for v in vs]
        if len(set(vals)) == 1 and len(vs) > 1:
            vals = [vals[0]] + ["то же"] * (len(vs) - 1)
        rows.append("| %s | %s |" % (k, " | ".join(vals)))
    block = PARAMS_START + "\n\n" + "\n".join(rows) + "\n\n" + PARAMS_END
    if PARAMS_START in s:
        s = re.sub(re.escape(PARAMS_START) + r".*?" + re.escape(PARAMS_END), block, s, flags=re.S)
    else:
        print("  в Readme нет меток %s ... %s - таблица не вставлена" % (PARAMS_START, PARAMS_END))
        return
    open(path, "w", encoding="utf-8", newline="").write(s)
    print("  Readme: таблица параметров обновлена")


def assembly(body, lid, ears, path):
    """STEP: корпус, крышка, уши и детали (без проверочных зон) - под экран варианта."""
    assy = cq.Assembly()
    assy.add(body, name="body", color=cq.Color(0.85, 0.85, 0.85))
    assy.add(lid, name="lid", color=cq.Color(0.3, 0.3, 0.3))
    for n, e, _ in ears:
        assy.add(e, name=n, color=cq.Color(0.3, 0.45, 0.9))
    for n, b in parts().items():
        if n in ZONES or n.startswith(("ear_", "head_", "bar_")):
            continue                                   # проверочные зоны - не детали; уши - выше
        assy.add(box(*b), name=n, color=cq.Color(0.4, 0.6, 0.9))
    for n, (x, y, z0, z1) in plungers().items():
        assy.add(cyl(x, y, z0, z1, BTN_PLUNGER_D), name=n, color=cq.Color(0.2, 0.2, 0.2))
    assy.export(path)


def main():
    if "--all" in sys.argv or ("--update-project" in sys.argv and "--tft" not in sys.argv):
        import subprocess
        ok, tables = True, {}
        for v in TFT_VARIANTS:                         # каждый вариант - отдельным процессом (свои производные)
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--tft", v],
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            ok = ok and r.returncode == 0
            with open(os.path.join(OUT, "TempDisplay_tft%s_dims.json" % v), encoding="utf-8") as f:
                tables[v] = json.load(f)["table"]
        if "--update-project" in sys.argv:
            update_readme(tables)
        print("ВСЕ ВАРИАНТЫ: OK" if ok else "ВСЕ ВАРИАНТЫ: ЕСТЬ ПРОБЛЕМЫ")
        sys.exit(0 if ok else 1)
    os.makedirs(OUT, exist_ok=True)
    print("[%s] экран %s, корпус %.1f x %.1f x %.1f мм (внутри %.1f x %.1f, глубина до крышки %.1f)"
          % (PREFIX, TFT_NAMES[TFT_KEY], W, H, DEPTH, IW, IH, BODY_D))
    body = build_body()
    lid = build_lid()
    ears = ears_all()
    ok = checks()
    export_stl(body, os.path.join(OUT, PREFIX + "_body.stl"))
    export_stl(lid, os.path.join(OUT, PREFIX + "_lid.stl"))
    flat = None                                        # уши для печати: плашмя в ряд
    for i, (_, _, e) in enumerate(ears):
        e = e.translate((0, i * (EAR_W + 3), 0))
        flat = e if flat is None else flat.union(e)
    export_stl(flat, os.path.join(OUT, PREFIX + "_ears.stl"))
    assembly(body, lid, ears, os.path.join(OUT, PREFIX + "_assembly.step"))
    preview_png(body, lid, os.path.join(OUT, PREFIX + "_preview.png"))
    layout_png(os.path.join(OUT, PREFIX + "_layout.png"))
    sections_png(body, os.path.join(OUT, PREFIX + "_promini.png"))
    dims = {
        "Экран": "%s, плата %.1f x %.1f" % (TFT_NAMES[TFT_KEY], TFT_W, TFT_L),
        "Габарит, мм": "%.1f x %.1f x %.1f" % (W, H, DEPTH),
        "Стенки / задняя / крышка, мм": "%.1f / %.1f / %.1f" % (WALL, BACK_T, LID_T),
        "Окно экрана, мм": "%.1f x %.1f" % (TFT_AA_U1 - TFT_AA_U0 + 2 * WINDOW_MARGIN, TFT_AA_W + 2 * WINDOW_MARGIN),
        "Крышка": "4 самореза Ø2.5 x %d в стойки корпуса (глухое Ø%.1f глубиной %.1f), на лице - конус Ø%.1f "
                  "под головку" % (LID_SCREW_L, PILOT_D, LID_BOSS_DEPTH, LID_CSK_D),
        "Экран на крышке": "4 самореза Ø%.1f x %d (не длиннее) в стойки Ø%.1f (глухое Ø%.1f глубиной %.1f)"
                           % (TFT_SCREW_D, TFT_SCREW_L, TFT_BOSS_D, TFT_PILOT_D, TFT_PILOT_DEPTH),
        "Саморезы: запас у дна": ", ".join("%s %.1f x %d - %.1f" % (n, sd, ln, t + d - ln)
                                           for n, sd, ln, t, d, _ in screw_list()),
        "Кнопки": "угловые 4.5 x 4.5, H = %.0f, на крышке слева от экрана (отверстия Ø%.1f, толкатель над крышкой "
                  "%.1f); макетка %.1f x %.1f вертикально у левой стенки - между стенкой и стойками крышки, на 2 упорах "
                  "с пазом, сверху держит крышка" % (BTN_H, BTN_HOLE_D, BTN_OUT, PB_W, PB_LEN),
        "Pro Mini": "вертикально, на высоте %.1f над стенкой; у края UART 2 держателя с пазом, у края RESET 2 стойки "
                    "+ 2 уха с язычком, саморезы Ø2.5 x %d" % (PM_RAISE, PM_SCREW_L),
        "Nano (запасная)": "вместо Pro Mini: на ребре вдоль Y у левой стойки HLK, штырьки влево; общая планка "
                           "HLK + Nano (паз и Г-загиб над ребром), низкие выступы у задней стенки",
        "HLK-3M03C": "лёжа выводами к крышке, длинной стороной у правой стенки, по центру, AC внизу; до платы экрана "
                     "%.1f; стойка слева - планка HLK + Nano %.1f мм, стойка у верхнего торца - ухо %.0f x %.0f x %.0f; "
                     "саморезы Ø2.5 x %d" % (TFT_PCB_BACK - HLK_TOP, BAR_T, HLK_EAR_L, EAR_W, EAR_T, HLK_SCREW_L),
        "На стену": "%d места под шуруп Ø4 - утонения Ø%.1f (остаток %.1f), сверлить нужные: %s (на время монтажа "
                    "снять макетку, Pro Mini или HLK)"
                    % (len(WALL_HOLES), WALL_HOLE_D, THIN_SKIN, ", ".join("(%.0f; %.0f)" % xy for xy in WALL_HOLES)),
        "Утонения": "датчик Ø%.1f (левая, нижняя и верхняя слева), сеть Ø%.1f (у AC: правая над HLK, нижняя у дна); "
                    "остаток %.1f" % (SENSOR_D + HOLE_CLR, MAINS_D + HOLE_CLR, THIN_SKIN),
    }
    with open(os.path.join(OUT, PREFIX + "_dims.json"), "w", encoding="utf-8") as f:
        json.dump({"W": W, "H": H, "DEPTH": DEPTH, "IW": IW, "IH": IH, "table": dims}, f, ensure_ascii=False)
    if "--update-project" in sys.argv:
        update_readme({TFT_KEY: dims})
    print("  OK" if ok else "  ЕСТЬ ПРОБЛЕМЫ")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
