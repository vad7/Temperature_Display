// settings.cpp - хранение настроек в EEPROM: [метка][версия][Settings][CRC-8].
#include "settings.h"
#include <EEPROM.h>
#include <avr/pgmspace.h>
#include <util/crc16.h>
#include "config.h"

#define SETTINGS_MAGIC    0x7D     // метка блока
#define SETTINGS_VERSION  7       // при изменении структуры Settings - увеличить (2: + heater, 3: + flip, 4: + mmIdx,
                                   // 5: flip -> rot + swapBtn, + brightIdx, 6: + corrC10,
                                   // 7: thrC10 -> thrC100)

namespace {
const uint8_t POLL[]  PROGMEM = POLL_PERIODS_S;
const uint8_t TREND[] PROGMEM = TREND_PERIODS_MIN;
const uint8_t MINMAX[] PROGMEM = MINMAX_PERIODS_H;
const uint8_t BRIGHT[] PROGMEM = BRIGHT_LEVELS;

struct Stored {
    uint8_t  magic;
    uint8_t  version;
    Settings s;
    uint8_t  crc;
};

uint8_t crcOf(const Stored& st)
{
    const uint8_t* p = reinterpret_cast<const uint8_t*>(&st);
    uint8_t crc = 0;
    for (uint8_t i = 0; i < offsetof(Stored, crc); i++) crc = _crc8_ccitt_update(crc, p[i]);
    return crc;
}

uint8_t indexOf(const uint8_t* table, uint8_t n, uint8_t value)
{
    for (uint8_t i = 0; i < n; i++)
        if (pgm_read_byte(&table[i]) == value) return i;
    return 0;
}

void defaults(Settings& s)
{
    s.pollIdx  = indexOf(POLL, sizeof(POLL), POLL_PERIOD_DEF_S);
    s.trendIdx = indexOf(TREND, sizeof(TREND), TREND_PERIOD_DEF_MIN);
    s.thrC100  = TREND_THR_DEF_C100;
    s.heater   = HEATER_DEF;
    s.rot      = ROT_DEF;
    s.swapBtn  = SWAP_BTN_DEF;
    s.brightIdx = indexOf(BRIGHT, sizeof(BRIGHT), BRIGHT_DEF);
    s.mmIdx    = indexOf(MINMAX, sizeof(MINMAX), MINMAX_PERIOD_DEF_H);
    s.corrC10  = TEMP_CORR_DEF_C10;
}
}  // namespace

namespace Cfg {
Settings s;

uint8_t pollCount()            { return sizeof(POLL); }
uint8_t trendCount()           { return sizeof(TREND); }
uint8_t pollS(uint8_t idx)     { return pgm_read_byte(&POLL[idx < sizeof(POLL) ? idx : 0]); }
uint8_t trendMin(uint8_t idx)  { return pgm_read_byte(&TREND[idx < sizeof(TREND) ? idx : 0]); }
uint8_t mmCount()              { return sizeof(MINMAX); }
uint8_t mmHours(uint8_t idx)   { return pgm_read_byte(&MINMAX[idx < sizeof(MINMAX) ? idx : 0]); }
uint8_t brightCount()          { return sizeof(BRIGHT); }
uint8_t bright(uint8_t idx)    { return pgm_read_byte(&BRIGHT[idx < sizeof(BRIGHT) ? idx : 0]); }

void load()
{
    Stored st;
    EEPROM.get(EE_SETTINGS_ADDR, st);
    const bool ok = st.magic == SETTINGS_MAGIC && st.version == SETTINGS_VERSION && st.crc == crcOf(st)
                    && st.s.pollIdx < sizeof(POLL) && st.s.trendIdx < sizeof(TREND)
                    && st.s.thrC100 >= TREND_THR_MIN_C100 && st.s.thrC100 <= TREND_THR_MAX_C100
                    && st.s.heater <= 1 && st.s.rot < ROT_COUNT && st.s.swapBtn <= 1
                    && st.s.brightIdx < sizeof(BRIGHT) && st.s.mmIdx < sizeof(MINMAX)
                    && st.s.corrC10 >= -TEMP_CORR_MAX_C10 && st.s.corrC10 <= TEMP_CORR_MAX_C10;
    if (ok) s = st.s;
    else    defaults(s);
}

void save()
{
    Stored st;
    st.magic   = SETTINGS_MAGIC;
    st.version = SETTINGS_VERSION;
    st.s       = s;
    st.crc     = crcOf(st);
    EEPROM.put(EE_SETTINGS_ADDR, st);
}
}  // namespace Cfg
