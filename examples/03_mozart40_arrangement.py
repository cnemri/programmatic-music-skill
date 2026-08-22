#!/usr/bin/env python3
"""
"Mozart por Tangos" -- Symphony No. 40 in G minor, K. 550, i. Molto Allegro,
arranged for flamenco guitar.

Mozart's notes are not paraphrased here.  The Violin I line is read straight
out of a MIDI of the movement with music21, quantised, transposed, and played
by the guitar; only the accompaniment, the compas and the articulation are
mine.

The transposition is the whole argument.  G minor down a perfect fourth is
D minor, whose Andalusian cadence -- Dm C Bb A -- is flamenco *por medio*, the
most idiomatic key the instrument has.  And then Mozart cooperates:

  * The famous sighing motif is Eb-D in G minor: flat-6 to 5.  In D minor that
    is Bb-A -- flat-2 to 1 of A Phrygian dominant.  The most famous appoggiatura
    in Western music is the flamenco cadence's own resolution.
  * The first subject is eight bars of i answered by eight of V7: Dm answered
    by A7.  Mozart's dominant is the Phrygian tonic of por medio.
  * The bass of his transition (mm.28-33) walks F E D C Bb A.  Its last four
    steps ARE the Andalusian cadence, written by Mozart in 1788.

Meter is kept honest: one of Mozart's alla breve bars is one bar of *tangos
flamencos*, quarter for quarter, so nothing is stretched or squeezed to fit a
compas.  Molto allegro survives as a fast tangos at 148.

Form (sonata, condensed -- Mozart measure numbers in brackets):
    llamada . primer tema [1-19] . tutti y transicion [20-33]
    segundo tema [44-66] . falseta/desarrollo [101-125] . cadencia andaluza
    recapitulacion [164-179] . segundo tema en re menor [227-239]
    coda [293-299] . remate

Output: mozart40_flamenco.mid (+ per-voice stems)
"""

import os
import random

from music21 import converter, duration, instrument, midi, note, stream, tempo

random.seed(1788)                     # K. 550, Vienna

SRC = "k550_mvt1.mid"
OUT_MID = "mozart40_flamenco.mid"

# --------------------------------------------------------------------------
# Read Mozart
# --------------------------------------------------------------------------
MZ = converter.parse(SRC)
# This MIDI plays the exposition repeat, so measures 1-100 occur twice before
# the development.  Map a measure number to its first occurrence.
BARQ = 4.0                            # 2/2 -> four quarter-lengths per bar


def mo(m):
    return (m - 1) * BARQ if m <= 100 else 800 + (m - 101) * BARQ


def _topline(part_index):
    """Monophonic top line of a part, offsets snapped to a sixteenth grid."""
    d = {}
    for n in MZ.parts[part_index].flatten().notes:
        o = round(float(n.offset) * 4) / 4
        d[o] = max(d.get(o, 0), max(q.midi for q in n.pitches))
    return sorted(d.items())


VLN1 = _topline(6)
BASSLINE = _topline(9)
TRANSPOSE = -5                        # G minor -> D minor, por medio


def moz(m0, m1, pickup=0.0, tr=TRANSPOSE):
    """Mozart's Violin I for measures m0..m1, as (offset_from_m0, midi, dur).
    Durations run to the next attack, so the line comes out legato."""
    a, b = mo(m0) - pickup, mo(m1) + BARQ
    sel = [(o, p) for o, p in VLN1 if a <= o < b]
    out = []
    for i, (o, p) in enumerate(sel):
        nxt = sel[i + 1][0] if i + 1 < len(sel) else b
        out.append((o - mo(m0), p + tr, max(0.25, min(nxt - o, 4.0))))
    return out


def bass_root(m, tr=TRANSPOSE):
    v = [p for o, p in BASSLINE if mo(m) <= o < mo(m) + BARQ]
    return (min(v) + tr) if v else None


# --------------------------------------------------------------------------
# Voices
# --------------------------------------------------------------------------
MEL = stream.Part(id="mel")      # picado / the Violin I line
HAR = stream.Part(id="har")      # rasgueado, arpeggio
BAS = stream.Part(id="bas")      # bordones
OCT = stream.Part(id="oct")      # octave doubling, inner voices
PRC = stream.Part(id="prc")      # cajon, palmas, golpe

for p, nm_ in ((MEL, "Picado"), (HAR, "Rasgueado"), (BAS, "Bordones"),
               (OCT, "Octavas")):
    g = instrument.AcousticGuitar()
    g.midiProgram = 24
    p.insert(0, g)
    p.partName = nm_
PRC.partName = "prc"

JIT = 0.012


def put(part, t, pitch, dur, vel, jitter=True):
    n = note.Note(int(pitch))
    n.duration = duration.Duration(quarterLength=max(dur, 0.05))
    n.volume.velocity = max(1, min(127, int(round(vel))))
    if jitter:
        t += random.uniform(-JIT, JIT)
    part.insert(max(0.0, t), n)


# --------------------------------------------------------------------------
# Voicings -- por medio (D minor / A Phrygian), real guitar shapes
# --------------------------------------------------------------------------
V = {
    "Dm":  [45, 50, 57, 62, 65],        # A2 D3 A3 D4 F4
    "Dm4": [45, 50, 57, 62, 67],        # sus4 colour
    "Gm":  [43, 50, 55, 58, 62],        # G2 D3 G3 Bb3 D4
    "Bb":  [46, 53, 58, 62, 65],        # Bb2 F3 Bb3 D4 F4
    "A7":  [45, 52, 57, 61, 64, 70],    # the por medio A: Bb (flat 9) on top
    "A":   [45, 52, 57, 61, 64],
    "C":   [48, 52, 55, 60, 64],
    "C7":  [48, 52, 58, 60, 64],
    "F":   [41, 48, 53, 57, 60, 65],
    "G7":  [43, 50, 55, 59, 62, 65],
    "Am":  [45, 52, 57, 60, 64],
    "E7":  [40, 47, 52, 56, 59, 64],
    "D7":  [50, 57, 62, 66, 69],
}
ARP = {k: v for k, v in V.items()}
ROOT = {"Dm": 50, "Dm4": 50, "Gm": 43, "Bb": 46, "A7": 45, "A": 45, "C": 48,
        "C7": 48, "F": 41, "G7": 43, "Am": 45, "E7": 40, "D7": 50}

GOLPE, CLAP, CLAP_S = 37, 39, 82
CAJON_LO, CAJON_HI, CAJON_SLAP = 64, 62, 63


def guitarify(root):
    """A playable three-note shape on an arbitrary root -- used in the
    development, where Mozart goes to keys no flamenco guitar calls home."""
    r = root
    while r < 40:
        r += 12
    while r > 52:
        r -= 12
    return [r, r + 7, r + 12, r + 19]


# --------------------------------------------------------------------------
# Technique
# --------------------------------------------------------------------------
def strum(t, pitches, dur, vel, spread=0.032, up=False, part=None):
    part = HAR if part is None else part
    ps = sorted(pitches)
    if up:
        ps = ps[::-1]
    for i, p in enumerate(ps):
        put(part, t + i * spread, p, max(0.1, dur - i * spread),
            vel + (5 if i >= len(ps) - 2 else 0) - i * 1.3)


def rasgueado(t, pitches, total=1.0, hits=5, vel=90, spread=0.028):
    step = total / (hits + 0.6)
    for k in range(hits):
        v = vel - 16 + int(18 * (k / max(1, hits - 1)))
        sub = pitches if k in (0, hits - 1) else pitches[-4:]
        strum(t + k * step, sub, total - k * step + 0.4, v, spread=spread,
              up=(k % 2 == 1))


def arpeggio(t, pitches, pattern, step=0.25, vel=62, dur=None, part=None):
    for k, idx in enumerate(pattern):
        put(part or HAR, t + k * step, pitches[idx % len(pitches)],
            dur if dur is not None else step * 2.6, vel + random.randint(-4, 4))


def tremolo(t, pitch, dur, vel, rate=0.115, part=None):
    part = MEL if part is None else part
    n = max(2, int(round(dur / rate)))
    for k in range(n):
        put(part, t + k * rate, pitch, rate * 1.8,
            vel + (4 if k % 4 == 0 else -2) + random.uniform(-2, 2))
    return t + dur


# --- compas: tangos flamencos.  Beat 1 stays light; 2, 3 and 4 drive. -------
def tangos_guitar(t, ch, vel=84, roll=False, sparse=False):
    ps = V[ch] if ch in V else ch
    top = ps[max(0, len(ps) - 4):]
    if sparse:
        strum(t + 1.0, ps, 0.9, vel, spread=0.03)
        strum(t + 2.0, top, 0.45, vel - 14, spread=0.022, up=True)
        strum(t + 3.0, ps, 0.85, vel - 4, spread=0.03)
        return
    strum(t + 0.0, top, 0.4, vel - 24, spread=0.02, up=True)     # ghost on 1
    strum(t + 1.0, ps, 0.85, vel + 6, spread=0.03)               # 2
    strum(t + 1.5, top, 0.4, vel - 14, spread=0.022, up=True)
    strum(t + 2.0, ps, 0.85, vel + 4, spread=0.03)               # 3
    strum(t + 2.5, top, 0.4, vel - 16, spread=0.022, up=True)
    if roll:
        rasgueado(t + 3.0, ps, total=1.0, hits=5, vel=vel + 10)  # 4
    else:
        strum(t + 3.0, ps, 0.85, vel + 6, spread=0.03)
        strum(t + 3.5, top, 0.4, vel - 14, spread=0.022, up=True)


def tangos_bass(t, ch, vel=88):
    r = ROOT[ch] if ch in ROOT else ch
    put(BAS, t + 0.0, r, 0.9, vel - 10)
    put(BAS, t + 1.0, r, 0.9, vel)
    put(BAS, t + 2.0, r + 7 if r + 7 < 60 else r, 0.8, vel - 8)
    put(BAS, t + 3.0, r, 0.9, vel - 2)


def tangos_perc(t, vel=80, sordas=False, fill=False, palmas=True):
    put(PRC, t + 0.0, CAJON_LO, 0.25, vel - 14)
    put(PRC, t + 1.0, CAJON_LO, 0.25, vel + 6)
    put(PRC, t + 2.0, CAJON_SLAP, 0.25, vel)
    put(PRC, t + 2.5, CAJON_LO, 0.25, vel - 10)
    put(PRC, t + 3.0, CAJON_SLAP, 0.25, vel + 4)
    for tt in (0.5, 1.5, 3.5):
        put(PRC, t + tt, CAJON_HI, 0.25, vel - 22)
    put(PRC, t + 1.0, GOLPE, 0.25, vel - 8)
    put(PRC, t + 3.0, GOLPE, 0.25, vel - 6)
    if palmas:
        key = CLAP_S if sordas else CLAP
        for k in range(8):
            tt = k * 0.5
            put(PRC, t + tt, key,
                0.25, vel - (26 if sordas else 14)
                + (12 if tt in (1.0, 2.0, 3.0) else 0) + random.randint(-4, 4))
    if fill:
        for tt in (3.25, 3.5, 3.75):
            put(PRC, t + tt, CAJON_HI, 0.25, vel - 4)


def place(t0, notes, part=MEL, vel=92, oct_shift=0, double=None, dvel=-30):
    """Mozart's line, played by the guitar."""
    for rel, p, d in notes:
        on_beat = abs(rel % 1.0) < 0.01
        v = vel + (9 if on_beat else 0) + random.randint(-4, 4)
        put(part, t0 + rel, p + oct_shift, d * 0.94, v)
        if double is not None:
            put(double, t0 + rel, p + oct_shift - 12, d * 0.9, v + dvel)


B = BARQ
def bar(n):
    return (n - 1) * B


# ==========================================================================
# Timeline
# ==========================================================================
LAYOUT = []            # (flamenco_bar, mozart_m0, mozart_m1, label)

# --- chord per Mozart bar, read off his own bass line ----------------------
CH_FIRST = (["Dm"] * 6 + ["A7", "A7", "Dm", "Gm", "Bb", "Gm", "Bb", "A7", "Bb"]
            + ["A7"] * 4)                                        # mm.1-19
CH_TUTTI = ["A7", "A7", "Dm", "Dm", "Bb", "Gm", "C", "C",
            "F", "C", "Dm", "C", "Bb", "A7"]                     # mm.20-33
CH_SECOND = ["G7", "C7", "Dm", "C7", "Gm", "F", "Bb", "Dm",
             "G7", "C7", "Dm", "C7", "Gm", "F", "Bb"]            # mm.44-58
CH_RECAP = (["Dm"] * 4 + ["A7", "A7", "Dm", "Gm", "Bb", "Gm", "Bb", "A7"]
            + ["Bb", "A7", "A7", "A7"])                          # mm.164-179
CH_SEC_D = ["A7", "A7", "Bb", "A7", "F", "Dm", "Gm", "Dm",
            "A7", "A7", "Dm", "A7", "Bb"]                        # mm.227-239
CH_CODA = ["Dm", "A7", "A7", "A7", "Dm", "Dm", "Dm"]             # mm.293-299

TEMPI = [(bar(1), 126), (bar(5), 138), (bar(9), 148),     # llamada -> tema
         (bar(28), 152),                                   # tutti
         (bar(42), 138),                                   # segundo tema, held back
         (bar(57), 150), (bar(67), 156),                   # desarrollo, pressing
         (bar(77), 160),                                   # cadencia andaluza
         (bar(81), 152),                                   # recapitulacion
         (bar(97), 146),                                   # segundo tema en re menor
         (bar(110), 158), (bar(117), 168), (bar(121), 174),  # coda, remate
         (bar(123), 148), (bar(124), 112), (bar(125), 84)]   # rallentando
for off, bpm in TEMPI:
    for p in (MEL, HAR, BAS, OCT, PRC):
        p.insert(off, tempo.MetronomeMark(number=bpm))

# ==========================================================================
# 1. LLAMADA -- bars 1-8.  The thesis, stated before Mozart arrives:
#    Bb-A, his sigh, is the Phrygian cadence of por medio.
# ==========================================================================
t = bar(1)
rasgueado(t, V["Dm"], total=1.8, hits=6, vel=82)
put(BAS, t, 50, 3.6, 88)
# the motif, bare: Bb-A-A, three times, exactly Mozart's rhythm
for k in range(3):
    o = bar(2) + k * 1.0
    put(MEL, o + 0.0, 70, 0.45, 78 + k * 6)      # Bb4
    put(MEL, o + 0.5, 69, 0.45, 84 + k * 6)      # A4
    if k == 2:
        put(MEL, o + 1.0, 69, 1.1, 80)
put(BAS, bar(2), 45, 3.6, 78)
strum(bar(3) + 1.0, V["A7"], 1.6, 78, spread=0.04)

# the cadence itself: Dm C Bb A, one bar each, rasgueado
for k, ch in enumerate(["Dm", "C", "Bb", "A7"]):
    o = bar(4 + k)
    rasgueado(o, V[ch], total=1.7, hits=4 + k, vel=76 + k * 6)
    strum(o + 2.0, V[ch], 1.4, 74 + k * 6, spread=0.035, up=True)
    put(BAS, o, ROOT[ch], 3.6, 84 + k * 3)
    put(PRC, o + 1.0, GOLPE, 0.25, 56 + k * 6)
    put(PRC, o + 3.0, GOLPE, 0.25, 58 + k * 6)
    if k >= 2:
        tangos_perc(o, vel=54 + k * 8, sordas=True)

# two bars of compas alone, setting the tangos before the theme enters
for k in range(2):
    o = bar(7 + k)
    tangos_guitar(o, "Dm", vel=72 + k * 4, sparse=(k == 0))
    tangos_bass(o, "Dm", vel=82)
    tangos_perc(o, vel=64 + k * 8, sordas=(k == 0), fill=(k == 1))

# ==========================================================================
# 2. PRIMER TEMA -- Mozart mm.1-19
# ==========================================================================
S = bar(9)
LAYOUT.append((9, 1, 19, "primer tema"))
place(S, moz(1, 19), vel=94)
for i, ch in enumerate(CH_FIRST):
    o = S + i * B
    soft = i < 8
    tangos_guitar(o, ch, vel=66 if soft else 78, sparse=soft)
    tangos_bass(o, ch, vel=78 if soft else 88)
    tangos_perc(o, vel=58 if soft else 74, sordas=soft,
                fill=(i in (7, 15)))
    if i >= 13:                       # the dominant pedal tightens up
        rasgueado(o + 3.0, V[ch], total=1.0, hits=4, vel=88)

# ==========================================================================
# 3. TUTTI Y TRANSICION -- Mozart mm.20-33.
#    His bass walks F E D C Bb A; the last four are the Andalusian cadence.
# ==========================================================================
S = bar(28)
LAYOUT.append((28, 20, 33, "tutti y transicion"))
place(S, moz(20, 33), vel=104, double=OCT, dvel=-32)
for i, ch in enumerate(CH_TUTTI):
    o = S + i * B
    tangos_guitar(o, ch, vel=92, roll=(i in (3, 9, 13)))
    tangos_bass(o, ch, vel=98)
    tangos_perc(o, vel=88, fill=(i in (3, 9, 13)))

# ==========================================================================
# 4. SEGUNDO TEMA -- Mozart mm.44-66, in F major.  The chromatic descent.
#    Lighter: half-time feel, the guitar arpeggiating behind it.
# ==========================================================================
S = bar(42)
LAYOUT.append((42, 44, 58, "segundo tema"))
place(S, moz(44, 58), vel=86)
PAT = [0, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 3, 4, 3, 2, 1]
for i, ch in enumerate(CH_SECOND):
    o = S + i * B
    arpeggio(o, ARP[ch], PAT, step=0.25, vel=58, dur=0.62)
    strum(o + 0.0, V[ch], 1.5, 70, spread=0.034)
    strum(o + 2.0, V[ch], 1.2, 64, spread=0.03, up=True)
    put(BAS, o, ROOT[ch], 1.9, 84)
    put(BAS, o + 2.0, ROOT[ch], 1.8, 74)
    tangos_perc(o, vel=52 + min(i, 12) * 2, sordas=(i < 12), palmas=(i >= 6))

# ==========================================================================
# 5. FALSETA / DESARROLLO -- Mozart mm.101-125.
#    His most chromatic music.  The guitar answers the way a flamenco falseta
#    does at full stretch: bare picado, bass octaves, compas underneath, and
#    no chords getting in the way.
# ==========================================================================
S = bar(57)
LAYOUT.append((57, 101, 120, "falseta / desarrollo"))
place(S, moz(101, 120), vel=100, double=OCT, dvel=-38)
for i in range(20):
    o = S + i * B
    m = 101 + i
    r = bass_root(m)
    v = 78 + min(i, 16) * 1.5
    if r is not None:
        while r < 38:
            r += 12
        while r > 55:
            r -= 12
        put(BAS, o + 0.0, r, 0.9, v + 4)
        put(BAS, o + 1.0, r, 0.9, v + 10)
        put(BAS, o + 2.0, r, 0.8, v)
        put(BAS, o + 3.0, r, 0.9, v + 6)
        sh = guitarify(r)
        strum(o + 1.0, sh, 0.6, v - 14, spread=0.026)
        strum(o + 3.0, sh, 0.6, v - 12, spread=0.026)
    tangos_perc(o, vel=72 + min(i, 16) * 1.6, fill=(i % 8 == 7))

# --- cadencia andaluza, bars 73-76: the way back into the recapitulation ---
for k, ch in enumerate(["Dm", "C", "Bb", "A7"]):
    o = bar(77 + k)
    rasgueado(o, V[ch], total=2.0, hits=5 + k, vel=94 + k * 5)
    rasgueado(o + 2.0, V[ch], total=2.0, hits=5 + k, vel=98 + k * 5)
    put(BAS, o, ROOT[ch], 1.9, 104)
    put(BAS, o + 2.0, ROOT[ch], 1.8, 100)
    tangos_perc(o, vel=92 + k * 3, fill=True)

# ==========================================================================
# 6. RECAPITULACION -- Mozart mm.164-179, with the anacrusis
# ==========================================================================
S = bar(81)
LAYOUT.append((81, 164, 179, "recapitulacion"))
place(S, moz(164, 179, pickup=1.0), vel=108, double=OCT, dvel=-30)
for i, ch in enumerate(CH_RECAP):
    o = S + i * B
    tangos_guitar(o, ch, vel=96, roll=(i in (3, 7, 11, 15)))
    tangos_bass(o, ch, vel=102)
    tangos_perc(o, vel=94, fill=(i in (7, 15)))

# ==========================================================================
# 7. SEGUNDO TEMA EN RE MENOR -- Mozart mm.227-239.
#    In the recapitulation his second subject is in the minor, so the
#    chromatic descent now falls Bb - A: straight onto the Phrygian tonic.
# ==========================================================================
S = bar(97)
LAYOUT.append((97, 227, 239, "segundo tema en re menor"))
place(S, moz(227, 239), vel=98, double=OCT, dvel=-34)
for i, ch in enumerate(CH_SEC_D):
    o = S + i * B
    arpeggio(o, ARP[ch], PAT, step=0.25, vel=66, dur=0.6)
    tangos_guitar(o, ch, vel=84, sparse=(i < 4))
    tangos_bass(o, ch, vel=94)
    tangos_perc(o, vel=80 + min(i, 10) * 1.5, fill=(i in (7, 12)))

# ==========================================================================
# 8. CODA -- Mozart mm.293-299, the driving arpeggiated figure as picado
# ==========================================================================
S = bar(110)
LAYOUT.append((110, 293, 299, "coda"))
place(S, moz(293, 299), vel=112, double=OCT, dvel=-28)
for i, ch in enumerate(CH_CODA):
    o = S + i * B
    tangos_guitar(o, ch, vel=100, roll=(i in (3, 6)))
    tangos_bass(o, ch, vel=106)
    tangos_perc(o, vel=100, fill=(i in (3, 6)))

# ==========================================================================
# 9. REMATE -- Mozart ends on his tonic; flamenco ends on the Phrygian one.
#    So: his D minor, then the cadence that has been implicit all along,
#    Dm C Bb A, landing on A major.
# ==========================================================================
for k in range(4):                                   # bars 117-120, driving
    o = bar(117 + k)
    ch = ["Dm", "Dm", "Bb", "A7"][k]
    rasgueado(o, V[ch], total=1.9, hits=5 + k, vel=100 + k * 4)
    rasgueado(o + 2.0, V[ch], total=1.9, hits=6 + k, vel=104 + k * 4)
    put(BAS, o, ROOT[ch], 1.9, 110)
    put(BAS, o + 2.0, ROOT[ch], 1.8, 106)
    tangos_perc(o, vel=100 + k * 3, fill=True)
# the motif one last time, in octaves, as the cadence falls
for k in range(3):
    o = bar(121) + k * 1.0
    put(MEL, o + 0.0, 70, 0.45, 108)
    put(MEL, o + 0.5, 69, 0.45, 114)
    put(OCT, o + 0.0, 58, 0.45, 84)
    put(OCT, o + 0.5, 57, 0.45, 88)
o = bar(121)
for k, ch in enumerate(["Dm", "C", "Bb", "A7"]):
    rasgueado(o + k * 1.0, V[ch], total=0.95, hits=4, vel=104 + k * 5)
    put(BAS, o + k * 1.0, ROOT[ch], 0.95, 108 + k * 3)
tangos_perc(o, vel=104, fill=True)

o = bar(122)                                          # two bars of A, rallentando
rasgueado(o, V["A7"], total=2.2, hits=7, vel=112)
put(BAS, o, 45, 4.0, 112)
tangos_perc(o, vel=104, fill=True)
strum(o + 2.4, V["A7"], 1.6, 104, spread=0.04, up=True)

o = bar(123)
rasgueado(o, V["Bb"], total=1.6, hits=5, vel=104)
put(BAS, o, 46, 1.8, 104)
rasgueado(o + 2.0, V["A7"], total=2.0, hits=6, vel=108)
put(BAS, o + 2.0, 45, 2.0, 108)
put(PRC, o + 0.0, CAJON_LO, 0.25, 96)
put(PRC, o + 2.0, CAJON_LO, 0.25, 100)

o = bar(124)                                          # the landing: A major
strum(o, V["A"] + [73], 3.6, 106, spread=0.055)
put(BAS, o, 45, 4.0, 108)
put(PRC, o, CAJON_LO, 0.3, 100)
put(PRC, o + 0.06, CLAP, 0.3, 90)
o = bar(125)
rasgueado(o, V["A"], total=1.8, hits=5, vel=92)
put(BAS, o, 45, 3.8, 96)
# armonicos over A, the last sound
for k, p in enumerate([69, 76, 81, 88]):
    put(MEL, bar(126) + k * 0.3, p, 3.2 - k * 0.3, 62 - k * 5)
put(HAR, bar(126) + 1.6, 45, 4.0, 56)
END = bar(127) + 3.0

# ==========================================================================
# Write
# ==========================================================================
PARTS = [(MEL, 1, "mel"), (HAR, 2, "har"), (BAS, 3, "bas"),
         (OCT, 4, "oct"), (PRC, 10, "prc")]


def retrack(mf, channels):
    for idx, ch in enumerate(channels, start=1):
        keep = []
        for ev in mf.tracks[idx].events:
            if ch == 10 and ev.type == midi.ChannelVoiceMessages.PROGRAM_CHANGE:
                continue
            if ev.channel is not None:
                ev.channel = ch
            keep.append(ev)
        mf.tracks[idx].events = keep
    return mf


def dump(mf, path):
    mf.open(path, "wb")
    mf.write()
    mf.close()


score = stream.Score()
for p, _, _ in PARTS:
    score.insert(0, p)
dump(retrack(midi.translate.streamToMidiFile(score), [c for _, c, _ in PARTS]),
     OUT_MID)

os.makedirs("stems_mozart", exist_ok=True)
for i, (p, ch, nm_) in enumerate(PARTS):
    one = stream.Score()
    one.insert(0, p)
    dump(retrack(midi.translate.streamToMidiFile(one), [ch]),
         os.path.join("stems_mozart", f"{i}_{nm_}.mid"))

n = sum(len(p.flatten().notes) for p in score.parts)
mozn = sum(len(moz(a, b)) for _, a, b, _ in LAYOUT)
print(f"wrote {OUT_MID}: {n} notes, {int(END // 4)} bars")
print(f"  {mozn} of them are Mozart's own Violin I line, transposed -5 (G minor -> D minor)")
for fb, m0, m1, label in LAYOUT:
    print(f"  bar {fb:3d}  <- Mozart mm.{m0}-{m1:<4d} {label}")
