# Подключение USB-UART адаптера для прошивки (загрузчик) - Pro Mini и Nano: Docs/usb_uart.svg, work/png/usb_uart.png.
# Pro Mini - разъём на торце по Docs/Pro Mini 328 pinout.png, Pro Mini 328.png: BLK(GND) GND VCC RXI TXO GRN(DTR),
# конденсатор автосброса - на плате. Nano - выводы по надписям на плате (TX1, RX0, RST, GND, +5V); вывода DTR нет -
# DTR адаптера на RST через 0.1 мкФ (типовая схема автосброса Arduino - ОЦЕНКА, без него - кнопка RESET).
#   python Scripts/usb_uart.py
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "Docs", "usb_uart.svg")
PNG = os.path.join(ROOT, "work", "png", "usb_uart.png")

ADAPTER = ("GND", "VCC 3.3 В", "TXD", "RXD", "DTR")          # выводы адаптера (порядок у адаптеров разный - по надписям)
COL = {"GND": "#000000", "VCC": "#c0392b", "TX": "#1f5fbf", "RX": "#1e8449", "DTR": "#8e44ad"}
STEP = 1.0

fig, axes = plt.subplots(1, 2, figsize=(13, 5))


def box(ax, x, y0, names, title, w=2.6, side="right"):
    """Блок с выводами; side - сторона выводов. Возвращает {имя: (x, y) вывода}."""
    h = len(names) * STEP + 0.6
    ax.add_patch(Rectangle((x, y0), w, h, fc="#eef3f8", ec="black", lw=1.5))
    ax.text(x + w / 2, y0 + h + 0.2, title, ha="center", va="bottom", fontsize=10, fontweight="bold")
    pins = {}
    for i, n in enumerate(names):
        y = y0 + h - 0.6 - i * STEP
        xp = x + w if side == "right" else x
        ax.plot([xp], [y], "s", color="0.3", ms=6)
        ax.text(xp - 0.15 if side == "right" else xp + 0.15, y, n, ha="right" if side == "right" else "left",
                va="center", fontsize=9)
        pins[n] = (xp, y)
    return pins


def link(ax, a, b, color, label=""):
    xm = (a[0] + b[0]) / 2
    ax.plot([a[0], xm, xm, b[0]], [a[1], a[1], b[1], b[1]], color=color, lw=2.2)
    if label:
        ax.text(xm + 0.1, (a[1] + b[1]) / 2 + 0.12, label, fontsize=8, color=color, ha="left", va="bottom")


def panel(ax, title, board, names, wires, notes):
    ax.set_aspect("equal")
    ax.axis("off")
    ad = box(ax, 0, 0, ADAPTER, "USB-UART 3.3 В")
    bd = box(ax, 7.5, -0.5, names, board, w=2.8, side="left")
    for a, b, c, lab in wires:
        if a == "DTR" and lab:                               # DTR -> 0.1 мкФ -> RST (Nano)
            (x0, y0), (x1, y1) = ad[a], bd[b]
            xc = (x0 + x1) / 2
            ax.plot([x0, xc - 0.25], [y0, y0], color=c, lw=2.2)
            ax.plot([xc - 0.25] * 2, [y0 - 0.3, y0 + 0.3], color=c, lw=2.5)
            ax.plot([xc + 0.05] * 2, [y0 - 0.3, y0 + 0.3], color=c, lw=2.5)
            ax.plot([xc + 0.05, xc + 0.6, xc + 0.6, x1], [y0, y0, y1, y1], color=c, lw=2.2)
            ax.text(xc - 0.1, y0 - 0.4, lab, fontsize=8, color=c, ha="center", va="top")
        else:
            link(ax, ad[a], bd[b], c)
    ax.text(0, -1.4, title, fontsize=11, fontweight="bold", va="top")
    for i, s in enumerate(notes):
        ax.text(0, -2.1 - i * 0.55, s, fontsize=8.5, va="top")
    ax.set_xlim(-0.5, 11)
    ax.set_ylim(-2.4 - len(notes) * 0.55, 6.6)


panel(axes[0], "Pro Mini 3.3 В (разъём на торце)", "Pro Mini",
      ("GND", "VCC", "RXI", "TXO", "DTR (GRN)"),
      [("GND", "GND", COL["GND"], ""), ("VCC 3.3 В", "VCC", COL["VCC"], ""), ("TXD", "RXI", COL["TX"], ""),
       ("RXD", "TXO", COL["RX"], ""), ("DTR", "DTR (GRN)", COL["DTR"], "")],
      ["Адаптер - перемычкой на 3.3 В. VCC - только при отключённом HLK", "(иначе - без VCC, общий только GND).",
       "DTR - автосброс (конденсатор - на плате); нет DTR - нажать RESET", "в начале загрузки (загрузчик ждёт 1 с)."])
panel(axes[1], "Nano (внешний адаптер вместо своего USB)", "Nano",
      ("GND", "+5V", "RX0", "TX1", "RST"),
      [("GND", "GND", COL["GND"], ""), ("VCC 3.3 В", "+5V", COL["VCC"], ""), ("TXD", "RX0", COL["TX"], ""),
       ("RXD", "TX1", COL["RX"], ""), ("DTR", "RST", COL["DTR"], "0.1 мкФ")],
      ["Выводы - по надписям на плате Nano. Питание проекта - 3.3 В на +5V", "(не VIN); USB Nano при этом не подключать.",
       "DTR - на RST через 0.1 мкФ (у Nano нет вывода DTR; ОЦЕНКА - типовая", "схема автосброса). Без DTR - кнопка RESET."])

os.makedirs(os.path.dirname(PNG), exist_ok=True)
fig.savefig(SVG, bbox_inches="tight")
fig.savefig(PNG, dpi=100, bbox_inches="tight")
print("SVG ->", os.path.relpath(SVG, ROOT))
print("PNG ->", os.path.relpath(PNG, ROOT))

# ---------------------------------------------------------------- Nano: ICSP 2x3 и программатор Arduino as ISP
# ICSP - Docs/Nano pinout A000005.pdf, стр. 3: 1 MISO (CIPO), 2 +5V, 3 SCK, 4 MOSI (COPI), 5 RESET, 6 GND; разъём у
# торца с VIN / RX / TX (напротив USB), вид сверху: у края - 1 3 5, ближе к середине - 2 4 6, вывод 1 - со стороны VIN.
# Программатор - плата со скетчем ArduinoISP (Readme §8): D12 MISO, D11 MOSI, D13 SCK, D10 - RESET цели.
SVG2 = os.path.join(ROOT, "Docs", "nano_icsp.svg")
PNG2 = os.path.join(ROOT, "work", "png", "nano_icsp.png")
ICSP = {1: "MISO", 2: "+5V", 3: "SCK", 4: "MOSI", 5: "RESET", 6: "GND"}
ISP = {1: "D12", 2: "5V", 3: "D13", 4: "D11", 5: "D10", 6: "GND"}
ICSP_COL = {1: COL["RX"], 2: COL["VCC"], 3: COL["DTR"], 4: COL["TX"], 5: "#d35400", 6: COL["GND"]}

fig2, ax = plt.subplots(figsize=(11, 5.6))
ax.set_aspect("equal")
ax.axis("off")
# торец Nano (вид сверху), разъём 2x3: x - номер столбца, y - ряд (у края - нечётные)
bx, by, W = 0.0, 0.0, 6.0
ax.add_patch(Rectangle((bx, by), W, 5.2, fc="#d6eaf0", ec="black", lw=1.5))
ax.plot([bx, bx + W], [by, by], color="black", lw=4)
ax.text(bx + W / 2, by - 0.35, "торец Nano (VIN, RX, TX); USB - с другого конца", ha="center", va="top", fontsize=8)
ax.text(bx + 0.15, by + 4.9, "гребёнка\nс VIN", fontsize=7.5, va="top")
ax.text(bx + W - 0.15, by + 4.9, "гребёнка\nс RX / TX", fontsize=7.5, va="top", ha="right")
ax.text(bx + W / 2, by + 5.5, "Nano, вид сверху (со стороны МК)", ha="center", va="bottom", fontsize=10,
        fontweight="bold")
for n in ICSP:
    col, row = (n - 1) // 2, (n - 1) % 2                      # 1,2 - столбец 0; нечётные - ряд у края
    x, y = bx + 1.6 + col * 1.4, by + 1.3 + row * 1.4
    ax.add_patch(Rectangle((x - 0.3, y - 0.3), 0.6, 0.6, fc=ICSP_COL[n], ec="black"))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    ax.text(x, y + (-0.45 if row == 0 else 0.45), ICSP[n], ha="center", va="top" if row == 0 else "bottom",
            fontsize=8, color=ICSP_COL[n], fontweight="bold")
ax.text(bx + W / 2, by + 3.75, "ICSP 2x3", ha="center", va="bottom", fontsize=9)
# программатор - таблица соединений
px = 7.5
ax.text(px, 5.3, "ICSP Nano  ->  Arduino as ISP", fontsize=10, fontweight="bold", va="center")
for i, n in enumerate((1, 4, 3, 5, 2, 6)):
    yp = 4.4 - i * 0.75
    ax.add_patch(Rectangle((px, yp - 0.25), 0.5, 0.5, fc=ICSP_COL[n], ec="black"))
    ax.text(px + 0.25, yp, str(n), ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    ax.text(px + 0.8, yp, ICSP[n], fontsize=9.5, va="center")
    ax.plot([px + 2.6, px + 3.8], [yp, yp], color=ICSP_COL[n], lw=2.2)
    ax.text(px + 4.0, yp, ISP[n], fontsize=9.5, va="center", fontweight="bold")
notes = [
    "ICSP Nano: 1 MISO, 2 +5V, 3 SCK, 4 MOSI, 5 RESET, 6 GND (Docs/Nano pinout A000005.pdf, стр. 3). Вывод 1 - у края, "
    "со стороны гребёнки с VIN.",
    "Программатор - плата со скетчем ArduinoISP: D12 - MISO, D11 - MOSI, D13 - SCK, D10 - RESET цели, 5V, GND. "
    "USBasp - по своей распиновке.",
    "Плата - без экрана, датчика и HLK (экран сидит на тех же D11 / D13); питание 5 В от программатора - только голой "
    "плате. Нужно для записи загрузчика и фьюзов (Readme §8, «Новая плата»).",
]
for i, s in enumerate(notes):
    ax.text(-0.3, -1.2 - i * 0.55, s, fontsize=8.3, va="top")
ax.set_xlim(-0.5, 13)
ax.set_ylim(-1.5 - len(notes) * 0.55, 6.8)
fig2.savefig(SVG2, bbox_inches="tight")
fig2.savefig(PNG2, dpi=100, bbox_inches="tight")
print("SVG ->", os.path.relpath(SVG2, ROOT))
print("PNG ->", os.path.relpath(PNG2, ROOT))
