#!/usr/bin/env python3
"""
"Una Mattina / Bella Ciao" -- Rumba Flamenca for Spanish guitar.

Built with music21.  Four nylon-guitar voices (melody, harmony/rasgueado,
bass strings, a doubling voice for octaves/tremolo) plus a flamenco
percussion track (palmas, golpe, cajon).

The arrangement leans on the fact that Einaudi's ostinato figure and the
opening of Bella Ciao share the same E-A-B-C cell, so the two themes can be
stacked verbatim in the final section.

Everything is placed at absolute quarter-length offsets so that strums,
rasgueados and tremolo can be micro-timed the way a real guitarist plays
them.  Output: una_mattina_bella_ciao_flamenco.mid
"""

import os
import random

from music21 import chord, duration, instrument, midi, note, stream, tempo

random.seed(1936)  # the year the Andalusian cadence and I agreed on

OUT_MID = "una_mattina_bella_ciao_flamenco.mid"

# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------

MEL = stream.Part(id="melody")      # punteado / picado / tremolo top line
HAR = stream.Part(id="harmony")     # rasgueados, arpeggios
BAS = stream.Part(id="bass")        # bordones -- the low strings
OCT = stream.Part(id="octave")      # doubling voice, tremolo repeats
PRC = stream.Part(id="PERC")        # palmas, golpe, cajon

for p, name in ((MEL, "Guitarra Punteado"), (HAR, "Guitarra Rasgueado"),
                (BAS, "Guitarra Bordones"), (OCT, "Guitarra Octavas")):
    g = instrument.AcousticGuitar()   # GM 24 -- nylon string guitar
    g.midiProgram = 24
    p.insert(0, g)
    p.partName = name
PRC.partName = "PERC"

# --------------------------------------------------------------------------
# Note helpers
# --------------------------------------------------------------------------

HUMANIZE = 0.012        # +/- quarter-lengths of timing jitter


def put(part, offset, pitch, dur, vel, jitter=True):
    """Place one note (pitch = midi number or name) at an absolute offset."""
    n = note.Note(pitch)
    n.duration = duration.Duration(quarterLength=max(dur, 0.05))
    n.volume.velocity = max(1, min(127, int(vel)))
    off = offset + (random.uniform(-HUMANIZE, HUMANIZE) if jitter else 0.0)
    part.insert(max(0.0, off), n)
    return n


def strum(part, offset, pitches, dur, vel, spread=0.035, up=False,
          vel_curve=6):
    """One rasgueo/strum: chord tones fanned out in time like a real pick-hand.

    `up` = golpe-side (thumb up, low-to-high is the default `down` for the
    hand travelling toward the floor across a guitar's low-to-high strings).
    """
    ps = sorted(pitches)
    if up:
        ps = ps[::-1]
    for i, p in enumerate(ps):
        # the first string struck rings longest, later ones a hair shorter
        d = max(0.1, dur - i * spread)
        v = vel + (vel_curve if i >= len(ps) - 2 else 0) - i * 1.2
        put(part, offset + i * spread, p, d, v)


def rasgueado(part, offset, pitches, total=1.0, hits=5, vel=88, spread=0.028):
    """The flamenco roll: e-a-m-i (+thumb) fired off in rapid succession."""
    step = total / (hits + 0.6)
    for k in range(hits):
        # abanico: alternate the direction of each finger's sweep
        up = (k % 2 == 1)
        v = vel - 16 + int(18 * (k / max(1, hits - 1)))   # crescendo into the beat
        sub = pitches if k in (0, hits - 1) else pitches[max(0, len(pitches) - 4):]
        strum(part, offset + k * step, sub, total - k * step + 0.35, v,
              spread=spread, up=up)


def arpeggio(part, offset, pitches, pattern, step=0.5, vel=70, dur=None,
             vel_accent=()):
    """p-i-m-a style arpeggio; `pattern` indexes into `pitches`."""
    for k, idx in enumerate(pattern):
        v = vel + (10 if k in vel_accent else 0) + random.randint(-4, 4)
        d = dur if dur is not None else step * 2.2
        put(part, offset + k * step, pitches[idx % len(pitches)], d, v)


def run(part, offset, pitches, step=0.25, vel=84, accent_every=4):
    """Picado: fast alternating i-m single-note scale run."""
    for k, p in enumerate(pitches):
        v = vel + (9 if k % accent_every == 0 else 0) + random.randint(-3, 3)
        put(part, offset + k * step, p, step * 1.15, v)


def tremolo(part_bass, part_mel, offset, bass_pitches, melody_pitch,
            vel=80, unit=0.25):
    """Classic p-a-m-i tremolo: thumb on the bass, then three fast repeats."""
    strum(part_bass, offset, bass_pitches, unit * 4.2, vel - 6, spread=0.03)
    for k in range(1, 4):
        put(part_mel, offset + k * unit, melody_pitch, unit * 1.25,
            vel + (8 if k == 1 else 0) - k)
    # and the melody note struck on the beat by the thumb-side too
    put(part_mel, offset, melody_pitch, unit * 0.9, vel + 4)


# --- percussion -----------------------------------------------------------
CLAP = 39          # palmas
CLAP_S = 82        # shaker -- palmas sordas (muffled claps)
GOLPE = 37         # side stick -- knuckle rap on the soundboard
CAJON_LO = 64      # low conga  -- cajon bass tone
CAJON_HI = 62      # muted high conga -- cajon slap
CAJON_SLAP = 63    # open high conga


def hit(offset, key, vel):
    put(PRC, offset, key, 0.25, vel)


def palmas_bar(offset, vel=62, sordas=False, density=8):
    """A bar of hand-claps in compas. Accents fall on the tresillo."""
    key = CLAP_S if sordas else CLAP
    accents = {0.0, 1.5, 3.0}
    step = 4.0 / density
    for k in range(density):
        t = k * step
        v = vel + (16 if t in accents else 0) + random.randint(-5, 5)
        hit(offset + t, key, v)


def cajon_bar(offset, vel=78, fill=False):
    """Rumba flamenca: 3+3+2 bass, slaps on the backbeat."""
    for t in (0.0, 1.5, 3.0):
        hit(offset + t, CAJON_LO, vel + 8)
    for t in (1.0, 2.0, 3.5):
        hit(offset + t, CAJON_HI, vel - 12)
    hit(offset + 2.5, CAJON_SLAP, vel - 4)
    if fill:
        for t in (3.25, 3.75):
            hit(offset + t, CAJON_HI, vel - 6)


def golpe_bar(offset, vel=72):
    for t in (1.0, 3.0):
        hit(offset + t, GOLPE, vel)


# --------------------------------------------------------------------------
# Voicings -- real guitar shapes in standard tuning (E2 A2 D3 G3 B3 E4)
# --------------------------------------------------------------------------
V = {
    "Am":    [45, 52, 57, 60, 64],              # x02210
    "Am_hi": [45, 52, 57, 60, 64, 69],
    "F":     [41, 48, 53, 57, 60, 64],          # Fmaj7, open top E
    "C":     [48, 52, 55, 60, 64],              # x32010
    "G":     [43, 47, 50, 55, 59, 67],          # 320033
    "Dm":    [50, 57, 62, 65, 69],              # xx0231
    "E":     [40, 47, 52, 56, 59, 64],          # 022100
    "E7b9":  [40, 47, 52, 56, 59, 65],          # the flamenco E: F natural on top
    "E7":    [40, 47, 50, 56, 59, 64],
    "A7":    [45, 52, 55, 61, 64],
}
# (root, arpeggio tones low->high) used by the Einaudi ostinato
ARP = {
    "Am": [45, 52, 57, 60, 64],
    "F":  [41, 48, 53, 57, 60],
    "C":  [48, 52, 55, 60, 64],
    "G":  [43, 50, 55, 59, 62],
    "Dm": [38, 50, 57, 62, 65],
    "E7b9": [40, 47, 56, 59, 65],
}
# the bordones -- the lowest pitch each shape really has on a guitar in
# standard tuning (nothing below E2 = 40 exists on the instrument)
BASSNOTE = {"Am": 45, "F": 41, "C": 48, "G": 43, "Dm": 50, "E": 40,
            "E7b9": 40, "E7": 40, "A7": 45}
# the octave/fifth above it, for the alternating thumb
BASSUP = {"Am": 52, "F": 48, "C": 55, "G": 50, "Dm": 57, "E": 47,
          "E7b9": 47, "E7": 47, "A7": 52}

# scales
A_MIN = [45, 47, 48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72,
         74, 76, 77]
E_PHRYG_DOM = [40, 41, 44, 45, 47, 48, 50, 52, 53, 56, 57, 59, 60, 62, 64, 65,
               68, 69, 71, 72]

BAR = 4.0


def b(n):
    """bar number (1-based) -> quarter-length offset"""
    return (n - 1) * BAR


# --------------------------------------------------------------------------
# Tempo map
# --------------------------------------------------------------------------
TEMPI = [
    (b(1),  54),    # intro libre
    (b(3),  60),
    (b(5),  76),    # Una Mattina
    (b(13), 80),
    (b(21), 88),    # transicion accelerando
    (b(22), 94),
    (b(23), 100),
    (b(24), 106),
    (b(25), 108),   # Bella Ciao, rumba
    (b(41), 112),   # falseta
    (b(49), 112),   # mashup
    (b(57), 112),
    (b(61), 104),   # coda, rit.
    (b(62), 92),
    (b(63), 78),
    (b(63) + 2, 64),
    (b(64), 52),
]
for off, bpm in TEMPI:
    for p in (MEL, HAR, BAS, OCT, PRC):
        p.insert(off, tempo.MetronomeMark(number=bpm))

# ==========================================================================
# 1. INTRODUCCION LIBRE  (bars 1-4) -- por arriba, A Phrygian
# ==========================================================================
o = b(1)
rasgueado(HAR, o, V["Am"], total=1.6, hits=6, vel=84)
put(BAS, o, 45, 3.4, 82)                                   # open A bordon
run(MEL, o + 2.0, [69, 71, 72, 74, 76], step=0.22, vel=76)  # A B C D E
strum(HAR, o + 3.1, V["Am_hi"], 1.6, 78, spread=0.045)

o = b(2)
run(MEL, o + 0.2, [77, 76, 74, 72, 71, 69, 68, 69], step=0.2, vel=82)
rasgueado(HAR, o + 2.0, V["E7b9"], total=1.7, hits=7, vel=92)
put(BAS, o + 2.0, 40, 3.0, 90)                              # open E bordon

o = b(3)
# descending Andalusian sigh with golpe answers
for k, (ch, t) in enumerate([("Am", 0.0), ("G", 1.0), ("F", 2.0), ("E7b9", 3.0)]):
    strum(HAR, o + t, V[ch], 1.15, 74 + k * 5, spread=0.03, up=(k % 2 == 1))
    put(BAS, o + t, BASSNOTE[ch], 1.0, 78 + k * 3)
    hit(o + t + 0.55, GOLPE, 58 + k * 5)

o = b(4)
run(MEL, o, [76, 77, 76, 74, 72, 71, 69, 68], step=0.2, vel=88)
rasgueado(HAR, o + 1.8, V["E7b9"], total=2.0, hits=8, vel=100)
put(BAS, o + 1.8, 40, 2.2, 96)
for t in (2.6, 3.0, 3.4, 3.7):
    hit(o + t, CLAP, 58 + int((t - 2.6) * 30))

# ==========================================================================
# 2. UNA MATTINA  (bars 5-20)
#    i - VI - III - VII ostinato, Einaudi's rolling left hand on nylon.
# ==========================================================================
UM_CHORDS = ["Am", "F", "C", "G"] * 2

UM_MEL_A = [   # (offset in bar, midi, dur)
    [(0.0, 64, 1.0), (1.0, 69, 0.5), (1.5, 71, 0.5), (2.0, 72, 1.0), (3.0, 71, 1.0)],
    [(0.0, 69, 1.5), (1.5, 72, 0.5), (2.0, 71, 1.0), (3.0, 69, 1.0)],
    [(0.0, 67, 1.0), (1.0, 69, 0.5), (1.5, 71, 0.5), (2.0, 72, 1.0), (3.0, 71, 1.0)],
    [(0.0, 74, 1.5), (1.5, 71, 0.5), (2.0, 69, 1.0), (3.0, 67, 1.0)],
    [(0.0, 64, 1.0), (1.0, 69, 0.5), (1.5, 71, 0.5), (2.0, 72, 2.0)],
    [(0.0, 72, 1.0), (1.0, 74, 1.0), (2.0, 72, 1.0), (3.0, 69, 1.0)],
    [(0.0, 71, 1.0), (1.0, 72, 1.0), (2.0, 74, 1.0), (3.0, 76, 1.0)],
    [(0.0, 74, 1.5), (1.5, 72, 0.5), (2.0, 71, 1.0), (3.0, 69, 1.0)],
]

PAT8 = [0, 1, 2, 3, 2, 1, 2, 3]
PAT16 = [0, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 3, 4, 3, 2, 1]

# --- A section: bare, no percussion, Einaudi at his most transparent
for i in range(8):
    o = b(5 + i)
    ch = UM_CHORDS[i]
    arpeggio(HAR, o, ARP[ch], PAT8, step=0.5, vel=62, dur=1.1,
             vel_accent=(0, 4))
    put(BAS, o, BASSNOTE[ch], 3.9, 70)
    for t, p, d in UM_MEL_A[i]:
        put(MEL, o + t, p, d * 0.95, 74 + random.randint(-4, 4))

# --- B section: 16ths, melody an octave up, palmas sordas creep in
for i in range(8):
    o = b(13 + i)
    ch = UM_CHORDS[i]
    arpeggio(HAR, o, ARP[ch], PAT16, step=0.25, vel=60, dur=0.6,
             vel_accent=(0, 4, 8, 12))
    put(BAS, o, BASSNOTE[ch], 2.0, 76)
    put(BAS, o + 2.0, BASSUP[ch], 1.9, 66)
    for t, p, d in UM_MEL_A[i]:
        put(MEL, o + t, p + 12, d * 0.95, 80 + random.randint(-4, 4))
        put(OCT, o + t, p, d * 0.9, 58 + random.randint(-4, 4))
    if i >= 2:
        palmas_bar(o, vel=44 + i * 3, sordas=True, density=8)
    if i >= 4:
        hit(o + 1.0, GOLPE, 52 + i * 3)
        hit(o + 3.0, GOLPE, 50 + i * 3)
    if i == 7:
        rasgueado(HAR, o + 3.0, V["E7b9"], total=1.0, hits=4, vel=92)

# ==========================================================================
# 3. TRANSICION (bars 21-24) -- Andalusian cadence, accelerando into compas
# ==========================================================================
CAD = ["Am", "G", "F", "E7b9"]
for i in range(4):
    o = b(21 + i)
    ch = CAD[i]
    put(BAS, o, BASSNOTE[ch], 2.0, 66 + i * 9)
    rasgueado(HAR, o, V[ch], total=2.0, hits=3 + i, vel=62 + i * 11)
    strum(HAR, o + 2.0, V[ch], 0.9, 66 + i * 10, up=True)
    if i >= 2:
        rasgueado(HAR, o + 3.0, V[ch], total=1.0, hits=3 + i, vel=76 + i * 8)
    palmas_bar(o, vel=40 + i * 11, sordas=(i < 2), density=4 if i < 2 else 8)
    cajon_bar(o, vel=48 + i * 11, fill=(i == 3))
    golpe_bar(o, vel=46 + i * 10)

# picado flourish over the E7 leading in
run(MEL, b(24) + 2.0, [88, 86, 84, 83, 81, 80, 77, 76], step=0.25, vel=96)

# ==========================================================================
# 4-6.  BELLA CIAO
# ==========================================================================
# 8-bar tune, pickup 1.5 beats early.  (offset, midi, dur)
BC = [
    (-1.5, 64, 0.5), (-1.0, 69, 0.5), (-0.5, 71, 0.5),
    (0.0, 72, 0.5), (0.5, 69, 1.5),
    (2.5, 64, 0.5), (3.0, 69, 0.5), (3.5, 71, 0.5),
    (4.0, 72, 0.5), (4.5, 69, 1.5),
    (6.5, 64, 0.5), (7.0, 69, 0.5), (7.5, 71, 0.5),
    (8.0, 72, 1.0), (9.0, 71, 0.5), (9.5, 69, 0.5),
    (10.0, 72, 1.0), (11.0, 71, 0.5), (11.5, 69, 0.5),
    (12.0, 76, 2.0), (14.0, 76, 1.0), (15.0, 76, 1.0),
    (16.0, 77, 1.0), (17.0, 77, 1.0),
    (18.5, 77, 0.5), (19.0, 76, 0.5), (19.5, 74, 0.5),
    (20.0, 76, 1.0), (21.0, 76, 1.0),
    (22.5, 76, 0.5), (23.0, 74, 0.5), (23.5, 72, 0.5),
    (24.0, 71, 1.0), (25.0, 76, 1.0), (26.0, 72, 1.0), (27.0, 71, 1.0),
    (28.0, 69, 3.5),
]
BC_HARM = ["Am", "Am", "Am", "E7b9", "Dm", "Am", "E7b9", "Am"]
# harmony for the mash-up: Einaudi's four chords, then Bella Ciao's cadence
BC_HARM_MASH = ["Am", "F", "C", "G", "Dm", "Am", "E7b9", "Am"]


def rumba_bar(offset, ch, vel=80, roll_on_4=False, sparse=False):
    """Rumba flamenca strum pattern for one bar."""
    v = V[ch]
    top = v[max(0, len(v) - 4):]
    if sparse:
        strum(HAR, offset + 0.0, v, 1.3, vel, spread=0.03)
        strum(HAR, offset + 1.5, top, 0.5, vel - 18, spread=0.02, up=True)
        strum(HAR, offset + 2.0, v, 1.1, vel - 6, spread=0.03)
        strum(HAR, offset + 3.5, top, 0.45, vel - 20, spread=0.02, up=True)
    else:
        strum(HAR, offset + 0.0, v, 0.95, vel + 6, spread=0.032)
        strum(HAR, offset + 1.0, v, 0.45, vel - 10, spread=0.028)
        strum(HAR, offset + 1.5, top, 0.4, vel - 16, spread=0.02, up=True)
        strum(HAR, offset + 2.0, v, 0.9, vel + 2, spread=0.032)
        strum(HAR, offset + 2.5, top, 0.4, vel - 18, spread=0.02, up=True)
        if roll_on_4:
            rasgueado(HAR, offset + 3.0, v, total=1.0, hits=4, vel=vel + 8)
        else:
            strum(HAR, offset + 3.0, v, 0.45, vel - 6, spread=0.028)
            strum(HAR, offset + 3.5, top, 0.4, vel - 16, spread=0.02, up=True)
    put(BAS, offset, BASSNOTE[ch], 1.4, vel + 4)
    put(BAS, offset + 1.5, BASSUP[ch], 0.9, vel - 12)
    put(BAS, offset + 3.0, BASSNOTE[ch], 0.9, vel - 6)


def place_melody(section_start, notes, part=MEL, vel=92, transpose=0,
                 doubling=None, double_transpose=-12):
    for t, p, d in notes:
        put(part, section_start + t, p + transpose, d * 0.94,
            vel + random.randint(-5, 5))
        if doubling is not None:
            put(doubling, section_start + t, p + double_transpose, d * 0.9,
                vel - 26 + random.randint(-4, 4))


# --- Bella Ciao 1 (bars 25-32): punteado melody, guitar keeps a light compas
S = b(25)
place_melody(S, BC, vel=92)
for i in range(8):
    o = b(25 + i)
    rumba_bar(o, BC_HARM[i], vel=72, sparse=True)
    palmas_bar(o, vel=52, sordas=True, density=4)
    cajon_bar(o, vel=62)
    golpe_bar(o, vel=54)

# --- Bella Ciao 2 (bars 33-40): full rumba, melody doubled in octaves
S = b(33)
place_melody(S, BC, vel=98, doubling=OCT, double_transpose=-12)
for i in range(8):
    o = b(33 + i)
    rumba_bar(o, BC_HARM[i], vel=80, roll_on_4=(i in (3, 7)))
    palmas_bar(o, vel=62, density=8)
    cajon_bar(o, vel=74, fill=(i in (3, 7)))
    golpe_bar(o, vel=66)
# answering picado lick in the long final note of the phrase
run(MEL, b(40) + 2.0, [81, 80, 77, 76, 74, 72, 71, 69], step=0.25, vel=98)

# ==========================================================================
# 7. FALSETA (bars 41-48) -- picado runs, then tremolo over the cadence
# ==========================================================================
FALSETA_CAD = ["Am", "G", "F", "E7b9"]

# bars 41-44: picado
LICKS = [
    [81, 79, 77, 76, 74, 72, 71, 69, 71, 72, 74, 76, 77, 76, 74, 72],   # Am
    [79, 77, 76, 74, 72, 71, 69, 67, 69, 71, 72, 74, 76, 74, 72, 71],   # G
    [77, 76, 74, 72, 71, 69, 68, 69, 71, 72, 74, 76, 77, 76, 74, 73],   # F
    [76, 77, 80, 81, 80, 77, 76, 74, 72, 71, 69, 68, 64, 65, 68, 64],   # E7b9
]
for i in range(4):
    o = b(41 + i)
    ch = FALSETA_CAD[i]
    run(MEL, o, LICKS[i], step=0.25, vel=90 + i * 3)
    put(BAS, o, BASSNOTE[ch], 2.0, 84)
    strum(HAR, o, V[ch], 1.6, 70, spread=0.035)
    strum(HAR, o + 2.0, V[ch], 1.4, 66, spread=0.03, up=True)
    palmas_bar(o, vel=56, sordas=True, density=8)
    cajon_bar(o, vel=70)
    golpe_bar(o, vel=60)

# bars 45-48: tremolo -- p-a-m-i, the sound of Recuerdos de la Alhambra
TREM_LINE = [
    ("Am", [69, 69, 72, 71]),
    ("G",  [71, 71, 74, 71]),
    ("F",  [69, 72, 72, 69]),
    ("E7b9", [68, 69, 68, 64]),
]
for i in range(4):
    o = b(45 + i)
    ch, mels = TREM_LINE[i]
    for k, mp in enumerate(mels):
        tremolo(HAR, MEL, o + k, ARP[ch][:3], mp + 12, vel=82 + i * 3,
                unit=0.25)
    put(BAS, o, BASSNOTE[ch], 3.8, 84)
    palmas_bar(o, vel=48 + i * 5, sordas=True, density=8)
    cajon_bar(o, vel=68 + i * 4, fill=(i == 3))

# ==========================================================================
# 8. MASHUP / CLIMAX (bars 49-56)
#    Bella Ciao sung on top of Einaudi's ostinato -- same E-A-B-C cell.
# ==========================================================================
S = b(49)
place_melody(S, BC, vel=116, doubling=OCT, double_transpose=-12)
for i in range(8):
    o = b(49 + i)
    ch = BC_HARM_MASH[i]
    # Einaudi's rolling 16ths, but strummed hard on the compas accents
    arpeggio(HAR, o, ARP[ch], PAT16, step=0.25, vel=80, dur=0.6,
             vel_accent=(0, 4, 8, 12))
    strum(HAR, o + 0.0, V[ch], 0.9, 106, spread=0.03)
    strum(HAR, o + 1.5, V[ch], 0.6, 96, spread=0.028, up=True)
    strum(HAR, o + 2.5, V[ch], 0.45, 88, spread=0.024, up=True)
    if i in (3, 7):
        rasgueado(HAR, o + 3.0, V[ch], total=1.0, hits=5, vel=108)
    else:
        strum(HAR, o + 3.0, V[ch], 0.7, 100, spread=0.03)
    put(BAS, o, BASSNOTE[ch], 1.4, 110)
    put(BAS, o + 1.5, BASSUP[ch], 0.9, 94)
    put(BAS, o + 3.0, BASSNOTE[ch], 0.9, 102)
    palmas_bar(o, vel=90, density=8)
    cajon_bar(o, vel=102, fill=(i in (3, 7)))
    golpe_bar(o, vel=88)

# ==========================================================================
# 9. ULTIMA VUELTA + CODA (bars 57-64)
# ==========================================================================
# bars 57-60: last statement of the chorus half, everything wide open
S = b(57)
LAST = [(t - 12.0, p, d) for (t, p, d) in BC if t >= 12.0]
place_melody(S, LAST, vel=112, doubling=OCT, double_transpose=-12)
for i in range(4):
    o = b(57 + i)
    ch = BC_HARM_MASH[4 + i]
    rumba_bar(o, ch, vel=94, roll_on_4=(i == 3))
    palmas_bar(o, vel=84, density=8)
    cajon_bar(o, vel=94, fill=(i == 3))
    golpe_bar(o, vel=84)

# bars 61-63: the Andalusian cadence, slowing, grand rasgueados
for i, ch in enumerate(["Am", "G", "F"]):
    o = b(61 + i)
    put(BAS, o, BASSNOTE[ch], 3.8, 96 - i * 4)
    rasgueado(HAR, o, V[ch], total=2.2, hits=6, vel=94 - i * 4)
    strum(HAR, o + 2.4, V[ch], 1.5, 84 - i * 4, spread=0.04, up=True)
    palmas_bar(o, vel=66 - i * 12, sordas=True, density=4)
    hit(o + 1.0, GOLPE, 70 - i * 8)
    hit(o + 3.0, CAJON_LO, 74 - i * 8)

# bar 63 second half + 64: E7(b9) -> Am, the Phrygian landing
o = b(63) + 2.0
put(BAS, o, 40, 2.0, 96)
rasgueado(HAR, o, V["E7b9"], total=2.0, hits=7, vel=98)
run(MEL, o + 1.0, [77, 76, 74, 72, 71, 69, 68, 64], step=0.125, vel=88)

o = b(64)
put(BAS, o, 45, 4.0, 92)
rasgueado(HAR, o, V["Am_hi"], total=1.8, hits=6, vel=96)
hit(o, CAJON_LO, 90)
hit(o + 0.25, CLAP, 76)
# armonicos: the last thing you hear, 12th-fret harmonics of A minor
for k, p in enumerate([69, 76, 81, 88]):
    put(MEL, o + 2.2 + k * 0.28, p, 3.0 - k * 0.3, 62 - k * 4)
put(HAR, o + 3.6, 45, 3.0, 58)

# ==========================================================================
# Assemble, fix the percussion channel, write MIDI
# ==========================================================================
PARTS = [(MEL, 1, "melody"), (HAR, 2, "harmony"), (BAS, 3, "bass"),
         (OCT, 4, "octave"), (PRC, 10, "perc")]


def retrack(mf, channels):
    """music21 folds parts that share a program onto one channel, which lets
    one voice's note-off cut another voice's identical pitch short.  Give each
    voice its own channel; channel 10 gets the GM drum kit (no program)."""
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

dump(retrack(midi.translate.streamToMidiFile(score),
             [ch for _, ch, _ in PARTS]), OUT_MID)

# per-voice stems, so the mix can be balanced properly at the audio stage
os.makedirs("stems", exist_ok=True)
for i, (p, ch, name) in enumerate(PARTS):
    one = stream.Score()
    one.insert(0, p)
    dump(retrack(midi.translate.streamToMidiFile(one), [ch]),
         os.path.join("stems", f"{i}_{name}.mid"))

n_notes = sum(len(p.flatten().notes) for p in score.parts)
print(f"wrote {OUT_MID}: {len(PARTS) + 1} tracks, {n_notes} notes, "
      f"{score.highestTime:.0f} quarter-lengths ({int(score.highestTime // 4)} bars)")
print("stems:", ", ".join(sorted(os.listdir("stems"))))
