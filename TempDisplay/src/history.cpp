// history.cpp - кольцевые буферы (int16, десятые °C). ОЗУ: (TREND_SLOTS + GRAPH_SLOTS + 2 * MINMAX_SLOTS) * 2 байт.
// Тенденция - наклон прямой МНК по точкам периода (x - номер интервала), умноженный на число интервалов периода.
// Мин / макс - по измерениям: мин и макс каждого закрытого часа + текущего (незакрытого) часа.
#include "history.h"
#include <Arduino.h>
#include "config.h"

namespace {
struct Ring {
    int16_t* buf;
    uint8_t  size, head, count;          // head - куда писать следующую точку
};

struct Acc {
    int32_t  sum;
    uint16_t n;
    int16_t  mn, mx;
    uint32_t tStart;
};

int16_t s_trendBuf[TREND_SLOTS];
int16_t s_graphBuf[GRAPH_SLOTS];
Ring    s_trend = { s_trendBuf, TREND_SLOTS, 0, 0 };
Ring    s_graph = { s_graphBuf, GRAPH_SLOTS, 0, 0 };
int16_t s_minBuf[MINMAX_SLOTS], s_maxBuf[MINMAX_SLOTS];
Ring    s_min = { s_minBuf, MINMAX_SLOTS, 0, 0 };
Ring    s_max = { s_maxBuf, MINMAX_SLOTS, 0, 0 };
Acc     s_trendAcc, s_graphAcc, s_mmAcc;
bool    s_graphChanged, s_started;

void push(Ring& r, int16_t v)
{
    r.buf[r.head] = v;
    r.head = (uint8_t)((r.head + 1) % r.size);
    if (r.count < r.size) r.count++;
}

int16_t at(const Ring& r, uint8_t i)     // i = 0 - самая старая точка
{
    return r.buf[(uint8_t)((r.head + r.size - r.count + i) % r.size)];
}

void accAdd(Acc& a, int16_t v)
{
    if (a.n == 0) { a.mn = v; a.mx = v; }
    a.sum += v;
    a.n++;
    if (v < a.mn) a.mn = v;
    if (v > a.mx) a.mx = v;
}

// Закрыть интервалы, истёкшие к моменту now; пустой интервал - точка HIST_NONE
bool accClose(Acc& a, Ring& r, uint32_t now, uint32_t slotMs)
{
    bool pushed = false;
    while (now - a.tStart >= slotMs) {
        push(r, a.n ? (int16_t)(a.sum / (int32_t)a.n) : HIST_NONE);
        a.sum = 0;
        a.n = 0;
        a.tStart += slotMs;
        pushed = true;
    }
    return pushed;
}

// Закрыть часы мин / макс, истёкшие к моменту now; пустой час - HIST_NONE
void mmClose(uint32_t now)
{
    Acc& a = s_mmAcc;
    while (now - a.tStart >= MINMAX_SLOT_S * 1000UL) {
        push(s_min, a.n ? a.mn : HIST_NONE);
        push(s_max, a.n ? a.mx : HIST_NONE);
        a.sum = 0;
        a.n = 0;
        a.tStart += MINMAX_SLOT_S * 1000UL;
    }
}

void mmAdd(MinMax& m, int16_t mn, int16_t mx)
{
    if (!m.valid) { m.minC10 = mn; m.maxC10 = mx; m.valid = true; }
    if (mn < m.minC10) m.minC10 = mn;
    if (mx > m.maxC10) m.maxC10 = mx;
}
}  // namespace

namespace History {
void add(int16_t c10)
{
    accAdd(s_trendAcc, c10);
    accAdd(s_graphAcc, c10);
    accAdd(s_mmAcc, c10);
}

void tick(uint32_t now)
{
    if (!s_started) {
        s_started = true;
        s_trendAcc.tStart = now;
        s_graphAcc.tStart = now;
        s_mmAcc.tStart = now;
        return;
    }
    accClose(s_trendAcc, s_trend, now, TREND_SLOT_S * 1000UL);
    mmClose(now);
    if (accClose(s_graphAcc, s_graph, now, GRAPH_SLOT_S * 1000UL)) s_graphChanged = true;
}

Trend trend(uint8_t periodMin)
{
    Trend t = { false, 0 };
    uint8_t slots = (uint8_t)((uint16_t)periodMin * 60U / TREND_SLOT_S);
    if (slots > s_trend.count) slots = s_trend.count;

    // МНК по точкам периода: x - номер интервала (0 - самый старый из периода)
    float sx = 0, sy = 0, sxx = 0, sxy = 0;
    uint8_t n = 0;
    const uint8_t first = s_trend.count - slots;
    for (uint8_t i = 0; i < slots; i++) {
        const int16_t v = at(s_trend, first + i);
        if (v == HIST_NONE) continue;
        const float x = i;
        sx += x; sy += v; sxx += x * x; sxy += x * v;
        n++;
    }

    const uint8_t need = (uint8_t)((uint16_t)periodMin * 60U / TREND_SLOT_S / 2U);
    const float den = n * sxx - sx * sx;
    if (n >= 2 && n >= need && den != 0.0f) {
        const float slope = (n * sxy - sx * sy) / den;  // десятые °C за интервал
        t.deltaC10 = (int16_t)lroundf(slope * (float)((uint16_t)periodMin * 60U / TREND_SLOT_S));
        t.valid = true;
    }
    return t;
}

MinMax minMax(uint8_t hours)
{
    MinMax m = { false, 0, 0 };
    uint8_t slots = hours ? hours - 1 : 0;                // полных часов, плюс текущий
    if (slots > s_min.count) slots = s_min.count;
    for (uint8_t i = s_min.count - slots; i < s_min.count; i++) {
        const int16_t mn = at(s_min, i);
        if (mn != HIST_NONE) mmAdd(m, mn, at(s_max, i));
    }
    if (s_mmAcc.n) mmAdd(m, s_mmAcc.mn, s_mmAcc.mx);
    return m;
}

bool takeGraphChanged()
{
    const bool c = s_graphChanged;
    s_graphChanged = false;
    return c;
}

uint8_t graphCount()        { return s_graph.count; }
int16_t graphAt(uint8_t i)  { return at(s_graph, i); }
}  // namespace History
