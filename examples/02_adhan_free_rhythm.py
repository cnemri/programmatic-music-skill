#!/usr/bin/env python3
"""
"Adhan por Granaina" -- the call to prayer as free-rhythm flamenco guitar.

The premise: flamenco's *por arriba* mode -- E Phrygian dominant, E F G# A B C D
-- IS Maqam Hijaz on E.  Jins Hijaz on the tonic (E F G# A) with jins Nahawand
above it (A B C D).  Al-Andalus never really left.  So the Hijazi adhan can be
set in flamenco without transposing a single note of it.

What is respected, faithfully:

  * The adhan is *mursala* -- unmetered.  Every phrase of the call here is in
    free rhythm.  Nothing is quantised, there is no pulse under it, and the
    lengths come from breath and Arabic prosody, not from a bar line.
  * The structural pauses (*saktah*) between phrases are real silence, 1.5-3s
    of it.  In flamenco those pauses are exactly where the guitar answers the
    cantaor, so the two traditions meet without either giving anything up.
  * The melodic arch (*sayr*): the takbir low in the tonic register, the
    shahada climbing to the ghammaz, the peak on "Hayya 'ala-l-falah", then
    the descent and a long *qafla* landing on the tonic.
  * Melisma falls on the long vowels -- the -a- of Allah, the -u- of Rasul,
    the -a- of salah and falah -- and the augmented second F<->G# is exposed
    on "ak-bar", the way a muezzin plants the maqam in your ear at the start.

The one metered section is a guitar falseta *por taranto* between the shahada
and the hay'ala.  It is purely instrumental: no phrase of the call is ever
forced into a compas.

The muezzin's line is played by the guitar in *tremolo* -- p-a-m-i -- which is
how a guitar sustains a vocal note, with *ligados* for the melismatic turns.

Because the piece is largely non-metric, everything is written in SECONDS:
the MIDI tempo is a constant 60 bpm, so one quarter-length is one second.

Output: adhan_flamenco.mid (+ per-voice stems)
"""

import os
import random

from music21 import duration, instrument, midi, note, stream, tempo

random.seed(711)          # Tariq lands at Gibraltar

OUT_MID = "adhan_flamenco.mid"

# --------------------------------------------------------------------------
# Voices
# --------------------------------------------------------------------------
VOZ = stream.Part(id="voz")     # the muezzin's line -- tremolo, ligado, picado
HAR = stream.Part(id="har")     # rasgueados, arpeggios, the remates
BAS = stream.Part(id="bas")     # bordones
ECO = stream.Part(id="eco")     # sympathetic octave, answering the call
PRC = stream.Part(id="prc")     # golpe; cajon and palmas only in the taranto

for p, nm in ((VOZ, "Voz"), (HAR, "Rasgueado"), (BAS, "Bordones"), (ECO, "Eco")):
    g = instrument.AcousticGuitar()
    g.midiProgram = 24          # GM nylon-string guitar
    p.insert(0, g)
    p.partName = nm
PRC.partName = "prc"
for p in (VOZ, HAR, BAS, ECO, PRC):
    p.insert(0, tempo.MetronomeMark(number=60))   # 1 quarter-length = 1 second

JIT = 0.010


def put(part, t, pitch, dur, vel, jitter=True):
    n = note.Note(pitch)
    n.duration = duration.Duration(quarterLength=max(dur, 0.05))
    n.volume.velocity = max(1, min(127, int(round(vel))))
    if jitter:
        t += random.uniform(-JIT, JIT)
    part.insert(max(0.0, t), n)


# --------------------------------------------------------------------------
# Maqam Hijaz on E  ==  flamenco por arriba (E Phrygian dominant)
#   qarar E4 . F4 . G#4 . A4(ghammaz) . B4 . C5 . D5 . E5(jawab) . F5
# --------------------------------------------------------------------------
E4, F4, Gs4, A4, B4, C5, D5, E5, F5, Gs5, A5 = 64, 65, 68, 69, 71, 72, 74, 76, 77, 80, 81
D4, C4, B3, A3 = 62, 60, 59, 57

HIJAZ_E = [52, 53, 56, 57, 59, 60, 62, 64, 65, 68, 69, 71, 72, 74, 76, 77, 80, 81]
A_MINOR = [57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81]

# guitar voicings, standard tuning, nothing below the open low E (40)
V = {
    "E7b9":  [40, 47, 52, 56, 59, 65],   # 0 2 2 1 0 1 -- the flamenco E, F on top
    "E":     [40, 47, 52, 56, 59, 64],
    "Esus":  [40, 47, 52, 57, 59, 64],   # A on the G string, taranta colour
    "F":     [41, 48, 53, 57, 60, 64],   # Fmaj7, open top E ringing
    "Am":    [45, 52, 57, 60, 64],
    "Am9":   [45, 52, 57, 59, 64],
    "Dm":    [50, 57, 62, 65, 69],
    "G":     [43, 47, 50, 55, 59, 67],
    "C":     [48, 52, 55, 60, 64],
}
ARP = {
    "E7b9": [40, 47, 52, 56, 59, 65],
    "E":    [40, 47, 52, 56, 59, 64],
    "F":    [41, 48, 53, 57, 60, 64],
    "Am":   [45, 52, 57, 60, 64],
    "Am9":  [45, 52, 57, 59, 64],
    "Dm":   [50, 57, 62, 65, 69],
    "G":    [43, 50, 55, 59, 62],
    "C":    [48, 52, 55, 60, 64],
}
BASSNOTE = {"E7b9": 40, "E": 40, "Esus": 40, "F": 41, "Am": 45, "Am9": 45,
            "Dm": 50, "G": 43, "C": 48}

GOLPE, CLAP, CLAP_S = 37, 39, 82
CAJON_LO, CAJON_HI, CAJON_SLAP = 64, 62, 63


# --------------------------------------------------------------------------
# Guitar technique
# --------------------------------------------------------------------------
def strum(t, pitches, dur, vel, spread=0.038, up=False, part=None):
    part = HAR if part is None else part
    ps = sorted(pitches)
    if up:
        ps = ps[::-1]
    for i, p in enumerate(ps):
        put(part, t + i * spread, p, max(0.12, dur - i * spread),
            vel + (5 if i >= len(ps) - 2 else 0) - i * 1.3)


def rasgueado(t, pitches, total=1.0, hits=5, vel=88, spread=0.03):
    """The roll.  Fingers fire in sequence, alternating sweep direction."""
    step = total / (hits + 0.6)
    for k in range(hits):
        v = vel - 16 + int(18 * (k / max(1, hits - 1)))
        sub = pitches if k in (0, hits - 1) else pitches[-4:]
        strum(t + k * step, sub, total - k * step + 0.5, v,
              spread=spread, up=(k % 2 == 1))


def arpeggio(t, pitches, pattern, step=0.22, vel=58, dur=None, part=None):
    for k, idx in enumerate(pattern):
        put(part or HAR, t + k * step, pitches[idx % len(pitches)],
            dur if dur is not None else step * 3.0, vel + random.randint(-4, 4))


def picado(t, pitches, step=0.16, vel=84, part=None):
    for k, p in enumerate(pitches):
        put(part or VOZ, t + k * step, p, step * 1.2,
            vel + (8 if k % 4 == 0 else 0) + random.randint(-3, 3))
    return t + len(pitches) * step


# --- the voice --------------------------------------------------------------
def tremolo_note(t, pitch, dur, vel, rate=0.098, part=None):
    """A guitar sustaining a vocal note: p-a-m-i repeated, shaped so it
    breathes -- swelling in, easing out, with a ~5 Hz undulation that reads
    as the vibrato a muezzin puts on a held vowel."""
    part = VOZ if part is None else part
    n = max(2, int(round(dur / rate)))
    import math
    for k in range(n):
        f = k / max(1, n - 1)
        env = 1.0 - 0.34 * (max(0.0, f - 0.55) / 0.45) ** 2    # gentle decay
        env *= 0.72 + 0.28 * min(1.0, f / 0.14)                # attack swell
        vib = 3.2 * math.sin(2 * math.pi * 5.0 * k * rate)
        put(part, t + k * rate, pitch, rate * 1.9,
            vel * env + vib + random.uniform(-2, 2))
    return t + dur


def melisma(t, pitches, step=0.145, vel=80, part=None):
    """Ligado -- hammered and pulled, notes overlapping, the way a melisma on
    a long vowel actually moves."""
    part = VOZ if part is None else part
    for k, p in enumerate(pitches):
        put(part, t + k * step, p, step * 1.75,
            vel - 4 + (5 if k == 0 else 0) + random.randint(-3, 3))
    return t + len(pitches) * step


def slide(t, frm, to, vel):
    """A grace note a breath ahead of the beat -- the guitar's portamento."""
    put(VOZ, t - 0.075, frm, 0.16, vel - 22)
    return t


def sing(t, events, vel=84, under=False):
    """Render one breath-phrase of the call.  Events:
        ("n", pitch, dur)      syllabic note
        ("t", pitch, dur)      held vowel, sustained in tremolo
        ("m", [pitches])       melisma / ligado turn
        ("s", from_p)          slide into the next note
        ("r", dur)             a catch of breath inside the phrase
    """
    pend_slide = None
    for ev in events:
        kind = ev[0]
        if kind == "s":
            pend_slide = ev[1]
            continue
        if kind == "r":
            t += ev[1]
            continue
        if pend_slide is not None:
            nxt = ev[1] if kind in ("n", "t") else ev[1][0]
            slide(t, pend_slide, nxt, vel)
            pend_slide = None
        if kind == "n":
            put(VOZ, t, ev[1], ev[2] * 1.35, vel + random.randint(-4, 4))
            t += ev[2]
        elif kind == "t":
            if under and ev[2] > 0.6:
                # the guitar's lower octave holds under the held vowel
                put(ECO, t, ev[1] - 12, ev[2] * 1.05, vel * 0.42)
            t = tremolo_note(t, ev[1], ev[2], vel)
        elif kind == "m":
            step = ev[2] if len(ev) > 2 else 0.145
            t = melisma(t, ev[1], step, vel)
    return t


# --- accompaniment ----------------------------------------------------------
def cushion(t, ch, dur, vel=48, step=0.30):
    """The colchon the guitar lays under the cante: a slow arpeggio, left to
    ring, never competing with the voice."""
    ps = ARP[ch]
    pat = [0, 1, 2, 3, 4, 3, 2, 1] * 6
    n = max(2, int(dur / step))
    arpeggio(t, ps, pat[:n], step=step, vel=vel, dur=step * 4.5)
    put(BAS, t, BASSNOTE[ch], min(dur, 6.0), vel + 16)


def remate(t, ch, vel=86, total=1.1, hits=5, golpe=True):
    """The guitar's answer in the silence after a phrase."""
    rasgueado(t, V[ch], total=total, hits=hits, vel=vel)
    put(BAS, t, BASSNOTE[ch], 2.2, vel + 4)
    if golpe:
        put(PRC, t + total * 0.62, GOLPE, 0.25, vel - 18)
    return t + total


# ==========================================================================
#  I.  TEMPLE -- the guitar alone, setting the maqam (libre)
# ==========================================================================
t = 0.6
rasgueado(t, V["E7b9"], total=2.2, hits=7, vel=76)
put(BAS, t, 40, 4.6, 84)
t += 3.4

# the augmented second, stated plainly: E - F - G# - A, and back down
picado(t, [E4, F4, Gs4, A4], step=0.30, vel=72, part=HAR)
t += 1.35
picado(t, [B4, A4, Gs4, F4], step=0.26, vel=76, part=HAR)
t += 1.25
melisma(t, [Gs4, F4, E4], 0.22, vel=70, part=HAR)
t += 0.95
strum(t, V["E7b9"], 2.4, 68, spread=0.05)
t += 2.9

# Andalusian cadence, rubato -- Am G F E
for ch, hold in (("Am", 1.5), ("G", 1.35), ("F", 1.5), ("E7b9", 2.6)):
    strum(t, V[ch], hold + 0.9, 66, spread=0.042, up=(ch == "G"))
    put(BAS, t, BASSNOTE[ch], hold + 0.6, 74)
    t += hold
t += 0.6

# a tremolo on the tonic, thinning out -- the invitation
tremolo_note(t, E5, 2.1, 62, part=HAR)
arpeggio(t, ARP["E7b9"], [0, 1, 2, 3, 4, 3, 2, 1], step=0.26, vel=44)
t += 2.9
t += 1.4                                            # silence before the call

# ==========================================================================
#  II.  TAKBIR -- Allahu akbar x4  (qarar: the tonic register)
#       four breath-phrases, each a step higher through jins Hijaz
# ==========================================================================
CALL_START = t

# 1. "Allahu akbar"  -- E ... G#, left open on the third
cushion(t, "E7b9", 5.6, vel=40)
t = sing(t, [
    ("n", E4, 0.42),                                   # Al-
    ("n", E4, 0.30), ("m", [F4, E4], 0.15), ("t", E4, 0.70),   # -laa-
    ("n", F4, 0.32),                                   # -hu
    ("n", Gs4, 0.48),                                  # ak-
    ("m", [Gs4, A4, Gs4], 0.16), ("t", Gs4, 1.25),     # -bar
], vel=74)
t += 1.7
remate(t, "E7b9", vel=70, total=0.9, hits=4)
t += 1.5

# 2. "Allahu akbar"  -- rises to A, resolves onto the tonic.
#    "hu"(F) -> "ak"(G#) is the augmented second, ascending, in the open.
cushion(t, "E7b9", 6.4, vel=42)
t = sing(t, [
    ("n", E4, 0.38),
    ("n", Gs4, 0.34), ("m", [A4, Gs4], 0.15), ("t", Gs4, 0.62),
    ("n", F4, 0.32),
    ("s", F4), ("n", Gs4, 0.46),
    ("m", [A4, Gs4, F4], 0.17), ("t", E4, 1.9),
], vel=78)
t += 2.1
remate(t, "F", vel=74, total=1.0, hits=4)
t += 1.7

# 3. "Allahu akbar"  -- up to the ghammaz, left open on A
cushion(t, "Am9", 6.2, vel=44)
t = sing(t, [
    ("n", Gs4, 0.36),
    ("n", A4, 0.34), ("m", [B4, A4], 0.15), ("t", A4, 0.72),
    ("n", Gs4, 0.30),
    ("n", A4, 0.46),
    ("m", [B4, C5, B4, A4], 0.16), ("t", A4, 1.5),
], vel=82)
t += 1.9
remate(t, "Am", vel=76, total=1.0, hits=4)
t += 1.5

# 4. "Allahu akbar"  -- touches C, then the long fall home
cushion(t, "E7b9", 7.6, vel=44)
t = sing(t, [
    ("n", A4, 0.36),
    ("n", B4, 0.34), ("m", [C5, B4], 0.15), ("t", B4, 0.78),
    ("n", A4, 0.32),
    ("n", B4, 0.44),
    ("m", [C5, B4, A4, Gs4, A4, Gs4, F4], 0.165), ("t", E4, 2.3),
], vel=84)
t += 2.5
remate(t, "E7b9", vel=82, total=1.3, hits=6)
t += 2.1

# ==========================================================================
#  III.  SHAHADA  (the ghammaz register)
# ==========================================================================
# 5. "Ashhadu an la ilaha illa-llah"  -- centred G#-B, cadence on the tonic
cushion(t, "Am9", 9.5, vel=44)
t = sing(t, [
    ("n", Gs4, 0.28), ("n", Gs4, 0.26), ("n", A4, 0.30),        # Ash-ha-du
    ("n", A4, 0.30),                                            # an
    ("n", B4, 0.36), ("m", [C5, B4], 0.15), ("t", B4, 0.82),    # laa
    ("n", A4, 0.26),                                            # i-
    ("n", A4, 0.30), ("m", [Gs4], 0.15),                        # -laa-
    ("n", Gs4, 0.32),                                           # -ha
    ("n", A4, 0.28), ("n", Gs4, 0.32),                          # il-la
    ("m", [A4, Gs4, F4, Gs4, F4], 0.16), ("t", E4, 2.2),        # -llaah
], vel=86)
t += 2.4
remate(t, "F", vel=80, total=1.1, hits=5)
t += 1.8

# 6. the repeat, a degree higher, left open on the ghammaz
cushion(t, "Dm", 9.8, vel=44)
t = sing(t, [
    ("n", A4, 0.28), ("n", A4, 0.26), ("n", B4, 0.30),
    ("n", B4, 0.30),
    ("s", B4), ("n", C5, 0.38), ("m", [D5, C5], 0.15), ("t", C5, 0.86),
    ("n", B4, 0.26),
    ("n", B4, 0.30), ("m", [A4], 0.15),
    ("n", A4, 0.32),
    ("n", B4, 0.28), ("n", A4, 0.32),
    ("m", [B4, A4, Gs4, A4], 0.16), ("t", A4, 2.0),
], vel=90)
t += 2.3
remate(t, "Am", vel=84, total=1.2, hits=5)
t += 1.8

# 7. "Ashhadu anna Muhammadan rasulu-llah" -- melisma on the long -uu- of Rasul
cushion(t, "Am9", 11.5, vel=44)
t = sing(t, [
    ("n", B4, 0.26), ("n", B4, 0.24), ("n", C5, 0.30),          # Ash-ha-du
    ("n", B4, 0.26), ("n", B4, 0.30),                           # an-na
    ("n", A4, 0.26), ("n", B4, 0.28),                           # Mu-ham-
    ("n", A4, 0.26), ("n", Gs4, 0.36),                          # -ma-dan
    ("n", A4, 0.30),                                            # ra-
    ("n", B4, 0.34), ("m", [C5, D5, C5, B4], 0.15), ("t", B4, 0.95),   # -suu-
    ("n", A4, 0.30),                                            # -lul-
    ("m", [B4, A4, Gs4, A4, Gs4, F4], 0.165), ("t", E4, 2.4),   # -llaah
], vel=90)
t += 2.5
remate(t, "E7b9", vel=84, total=1.2, hits=5)
t += 1.8

# 8. the repeat, reaching for D -- the ear starts leaning upward
cushion(t, "Dm", 11.8, vel=46)
t = sing(t, [
    ("n", C5, 0.26), ("n", C5, 0.24), ("n", D5, 0.30),
    ("n", C5, 0.26), ("n", C5, 0.30),
    ("n", B4, 0.26), ("n", C5, 0.28),
    ("n", B4, 0.26), ("n", A4, 0.36),
    ("n", B4, 0.30),
    ("s", C5), ("n", D5, 0.36), ("m", [E5, D5, C5, B4], 0.15), ("t", C5, 0.95),
    ("n", B4, 0.30),
    ("m", [C5, B4, A4, B4, A4, Gs4], 0.165), ("t", A4, 2.2),
], vel=94)
t += 2.4
remate(t, "Am", vel=88, total=1.4, hits=6)
t += 2.3

# ==========================================================================
#  IV.  FALSETA POR TARANTO -- the one metered section, guitar alone.
#       No phrase of the call is ever put into a compas; this is the guitar
#       answering on its own terms, and then getting out of the way.
# ==========================================================================
BPM = 78.0
BEAT = 60.0 / BPM
BARQ = 4 * BEAT
TAR_START = t + 0.4
TAR_CHORDS = ["Am", "G", "F", "E7b9"] * 2 + ["Am", "G", "F", "E7b9"]

TAR_LICKS = [
    [A4, B4, C5, D5, E5, D5, C5, B4],                # Am
    [B4, C5, D5, B4, A4, B4, A4, 67],                # G   (G natural: A aeolian)
    [A4, C5, 65, A4, Gs4, A4, F4, E4],               # F
    [E5, F5, Gs5, A5, Gs5, F5, E5, D5],              # E -- jins Hijaz, up top
    [C5, B4, A4, B4, C5, D5, C5, B4],
    [D5, C5, B4, A4, 67, A4, B4, 67],
    [A4, 65, E4, F4, A4, C5, B4, A4],
    [Gs4, A4, C5, E5, D5, C5, B4, Gs4],
]
for i, ch in enumerate(TAR_CHORDS):
    o = TAR_START + i * BARQ
    put(BAS, o, BASSNOTE[ch], BEAT * 1.6, 84 + min(i, 6) * 2)
    put(BAS, o + 2 * BEAT, BASSNOTE[ch], BEAT * 1.2, 72 + min(i, 6) * 2)
    v = 60 + min(i, 8) * 3
    if i < 8:
        picado(o, TAR_LICKS[i], step=BEAT / 2, vel=v + 6, part=VOZ)
        strum(o, V[ch], BEAT * 1.4, v - 6, spread=0.034)
        strum(o + 2 * BEAT, V[ch], BEAT * 1.1, v - 10, spread=0.03, up=True)
    else:
        # the last four bars: the cadence, all rasgueado, and then it stops
        rasgueado(o, V[ch], total=BEAT * 2, hits=5 + (i - 8), vel=v + 8)
        strum(o + 2 * BEAT, V[ch], BEAT * 1.6, v + 4, spread=0.036, up=True)
        if i == 11:
            rasgueado(o + 2 * BEAT, V[ch], total=BEAT * 2, hits=8, vel=92)
    # compas: cajon on the 3+3+2, palmas, golpe on 2 and 4
    for k, tt in enumerate((0.0, 1.5, 3.0)):
        put(PRC, o + tt * BEAT, CAJON_LO, 0.25, 56 + min(i, 8) * 2)
    for tt in (1.0, 2.0, 3.5):
        put(PRC, o + tt * BEAT, CAJON_HI, 0.25, 44 + min(i, 8) * 2)
    put(PRC, o + 2.5 * BEAT, CAJON_SLAP, 0.25, 50 + min(i, 8) * 2)
    for k in range(4 if i < 6 else 8):
        tt = k * (1.0 if i < 6 else 0.5)
        put(PRC, o + tt * BEAT, CLAP_S if i < 6 else CLAP,
            0.25, (34 if i < 6 else 46) + min(i, 8) * 2
            + (12 if tt in (0.0, 1.5, 3.0) else 0))
    for tt in (1.0, 3.0):
        put(PRC, o + tt * BEAT, GOLPE, 0.25, 46 + min(i, 8) * 2)

t = TAR_START + len(TAR_CHORDS) * BARQ + 2.4       # let the compas die away

# ==========================================================================
#  V.  HAY'ALA -- the summons.  The peak of the arch, back in free rhythm.
# ==========================================================================
# 9. "Hayya 'ala-s-salah"  -- the leap into the upper register
cushion(t, "Dm", 9.0, vel=62, step=0.26)
rasgueado(t, V["Dm"], total=1.6, hits=5, vel=78)
t = sing(t, [
    ("s", C5), ("t", D5, 1.10),                                 # Hay-
    ("n", E5, 0.40),                                            # -ya
    ("n", E5, 0.30),                                            # 'a-
    ("n", D5, 0.42),                                            # -las-
    ("n", C5, 0.36),                                            # sa-
    ("m", [D5, C5, B4, C5, B4, A4, B4, A4, Gs4], 0.15),         # -laah
    ("t", A4, 1.5),
    ("m", [Gs4, F4], 0.18), ("t", E4, 1.7),
], vel=98)
t += 2.3
remate(t, "E7b9", vel=90, total=1.3, hits=6)
t += 1.9

# 10. the repeat, higher still
cushion(t, "Dm", 9.4, vel=66, step=0.25)
rasgueado(t, V["Dm"], total=1.6, hits=5, vel=84)
t = sing(t, [
    ("s", D5), ("t", E5, 1.15),
    ("n", F5, 0.42),
    ("n", E5, 0.30),
    ("n", E5, 0.42),
    ("n", D5, 0.36),
    ("m", [E5, D5, C5, D5, C5, B4, C5, B4, A4], 0.15),
    ("t", B4, 1.4),
    ("m", [A4, Gs4], 0.18), ("t", A4, 1.8),
], vel=102, under=True)
t += 2.4
remate(t, "Am", vel=96, total=1.4, hits=6)
t += 1.9

# 11. "Hayya 'ala-l-falah" -- the zenith.  F5 is the flat 9 above the tonic;
#     the G#5 above it is touched once and never again.
cushion(t, "Dm", 10.6, vel=72, step=0.23)
rasgueado(t, V["Dm"], total=1.8, hits=6, vel=92)
rasgueado(t + 5.2, V["Am"], total=1.6, hits=5, vel=86)
t = sing(t, [
    ("s", E5), ("t", F5, 1.25),                                 # Hay-
    ("n", Gs5, 0.38),                                           # -ya   (zenith)
    ("n", F5, 0.32),                                            # 'a-
    ("n", E5, 0.44),                                            # -lal-
    ("n", D5, 0.36),                                            # fa-
    ("m", [E5, D5, C5, D5, C5, B4, C5, B4, A4, B4, A4, Gs4], 0.145),   # -laah
    ("t", A4, 1.6),
    ("m", [B4, A4, Gs4, F4], 0.17), ("t", E4, 2.0),
], vel=112, under=True)
put(ECO, t - 3.2, E4, 2.6, 46)      # the tonic answers from below, sympathetic
t += 2.5
remate(t, "F", vel=100, total=1.6, hits=7)
t += 2.0

# 12. the repeat: the descent proper begins
cushion(t, "E7b9", 10.2, vel=68, step=0.24)
rasgueado(t, V["E7b9"], total=1.8, hits=6, vel=88)
rasgueado(t + 5.4, V["F"], total=1.6, hits=5, vel=80)
t = sing(t, [
    ("s", D5), ("t", E5, 1.10),
    ("n", F5, 0.36),
    ("n", E5, 0.32),
    ("n", D5, 0.44),
    ("n", C5, 0.36),
    ("m", [D5, C5, B4, C5, B4, A4, Gs4, A4, Gs4, F4], 0.15),
    ("t", Gs4, 1.4),
    ("m", [A4, Gs4, F4], 0.18), ("t", E4, 2.4),
], vel=100, under=True)
t += 2.7
remate(t, "E7b9", vel=88, total=1.4, hits=6)
t += 2.2

# ==========================================================================
#  VI.  CLOSING TAKBIR and the TAHLIL -- hubut, then the qafla
# ==========================================================================
# 13. "Allahu akbar" -- the same words as the opening, now falling
cushion(t, "Am9", 6.6, vel=44)
t = sing(t, [
    ("n", Gs4, 0.38),
    ("n", Gs4, 0.32), ("m", [A4, Gs4], 0.15), ("t", Gs4, 0.80),
    ("n", F4, 0.32),
    ("n", Gs4, 0.44),
    ("m", [F4, Gs4, F4], 0.17), ("t", E4, 1.9),
], vel=86)
t += 2.0
remate(t, "F", vel=76, total=1.0, hits=4)
t += 1.6

# 14. and again, quieter, almost spoken
cushion(t, "E7b9", 6.0, vel=40)
t = sing(t, [
    ("n", F4, 0.36),
    ("n", Gs4, 0.32), ("m", [F4], 0.16), ("t", F4, 0.70),
    ("n", E4, 0.32),
    ("n", Gs4, 0.42),
    ("m", [F4, E4], 0.18), ("t", E4, 2.1),
], vel=78)
t += 2.4
strum(t, V["F"], 2.6, 62, spread=0.05)
put(BAS, t, 41, 2.8, 70)
t += 2.4

# 15. "La ilaha illa-llah" -- the qafla.  Starts on the third, waves once on
#     "illa", and comes to rest on the tonic and stays there.
cushion(t, "E7b9", 11.0, vel=42, step=0.36)
t = sing(t, [
    ("n", Gs4, 0.44), ("m", [A4, Gs4], 0.16), ("t", Gs4, 1.05),   # Laa
    ("n", F4, 0.30),                                              # i-
    ("n", Gs4, 0.36), ("m", [F4], 0.16), ("t", F4, 0.72),         # -laa-
    ("n", E4, 0.32),                                              # -ha
    ("n", F4, 0.32),                                              # il-
    ("n", Gs4, 0.38), ("m", [F4, E4, F4], 0.16),                  # -la
    ("t", E4, 3.4),                                               # -llaah
    ("m", [F4, E4], 0.20), ("t", E4, 3.0),
], vel=82)

# the guitar's Phrygian cadence: bII -> I, and then let it ring out
strum(t + 0.5, V["F"], 3.0, 62, spread=0.055)
put(BAS, t + 0.5, 41, 3.2, 70)
rasgueado(t + 3.2, V["E7b9"], total=2.4, hits=6, vel=74)
put(BAS, t + 3.2, 40, 5.5, 80)
t += 6.4
# armonicos at the twelfth fret -- the last sound
for k, p in enumerate([64, 71, 76, 83]):
    put(VOZ, t + k * 0.42, p, 4.0 - k * 0.4, 56 - k * 5)
put(HAR, t + 2.2, 40, 5.0, 54)
END = t + 7.0

# ==========================================================================
# Write MIDI: full score + one stem per voice
# ==========================================================================
PARTS = [(VOZ, 1, "voz"), (HAR, 2, "har"), (BAS, 3, "bas"),
         (ECO, 4, "eco"), (PRC, 10, "prc")]


def retrack(mf, channels):
    """music21 folds parts sharing a program onto one channel, which lets one
    voice's note-off cut another's identical pitch short.  Separate them."""
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

os.makedirs("stems_adhan", exist_ok=True)
for i, (p, ch, nm) in enumerate(PARTS):
    one = stream.Score()
    one.insert(0, p)
    dump(retrack(midi.translate.streamToMidiFile(one), [ch]),
         os.path.join("stems_adhan", f"{i}_{nm}.mid"))

n = sum(len(p.flatten().notes) for p in score.parts)
print(f"wrote {OUT_MID}: {n} notes, {END:.1f}s "
      f"({int(END // 60)}:{int(END % 60):02d})")
print(f"  temple      0.0 - {CALL_START:.1f}s")
print(f"  adhan begins  {CALL_START:.1f}s")
print(f"  taranto     {TAR_START:.1f} - {TAR_START + len(TAR_CHORDS) * BARQ:.1f}s "
      f"(the only metered music, {BPM:.0f} bpm)")
print(f"  ends        {END:.1f}s")
