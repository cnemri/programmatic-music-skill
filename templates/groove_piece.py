#!/usr/bin/env python3
"""
TEMPLATE: a groove-driven instrumental piece, any tradition.

Copy this, change the CONFIG block, replace the melody, run it. It produces a
mastered mp3 and prints a verification report.

The structure is deliberately explicit: a SECTIONS table drives everything, so
changing the form is editing one list rather than renumbering bars by hand.

    python templates/groove_piece.py -o out.mp3
"""
from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from music21 import instrument, stream                       # noqa: E402
from m21kit import drums, midiio, perform, render, scales, verify   # noqa: E402

# ===========================================================================
# CONFIG
# ===========================================================================
SEED = 7
BPM = 104
BAR = 4.0                       # quarter-lengths per bar (4/4)
SCALE, TONIC = 'flamenco', 'A4'     # try: dorian / raga_malkauns / maqam_hijaz
GROOVE = 'tangos_flamencos'         # drums.list_grooves() for the catalogue
GM_PROGRAM = 24                     # 24 nylon guitar, 0 piano, 26 jazz guitar

# por medio: A Phrygian. Real guitar shapes, nothing below the low E (40).
CHORDS = {
    'Dm': [45, 50, 57, 62, 65],
    'C':  [48, 52, 55, 60, 64],
    'Bb': [46, 53, 58, 62, 65],
    'A7': [45, 52, 57, 61, 64, 70],     # Bb (flat 9) on top
}
CADENCE = ['Dm', 'C', 'Bb', 'A7']       # the Andalusian cadence

#            name          bars  chords            intensity 0..1  melody?
SECTIONS = [
    ('intro',              4,    ['Dm', 'Dm', 'A7', 'A7'], 0.25, False),
    ('theme',              8,    CADENCE * 2,              0.50, True),
    ('theme_forte',        8,    CADENCE * 2,              0.70, True),
    ('falseta',            8,    CADENCE * 2,              0.60, 'solo'),
    ('climax',             8,    CADENCE * 2,              1.00, True),
    ('coda',               4,    ['Dm', 'C', 'Bb', 'A7'],  0.40, False),
]
# ===========================================================================


def build() -> tuple[stream.Score, list[tuple[str, int, int]]]:
    random.seed(SEED)
    mel = stream.Part(id='melody')
    har = stream.Part(id='chords')
    bas = stream.Part(id='bass')
    oct_ = stream.Part(id='octaves')
    prc = stream.Part(id='drums')
    for p in (mel, har, bas, oct_):
        i = instrument.AcousticGuitar()
        i.midiProgram = GM_PROGRAM
        p.insert(0, i)
    midiio.add_tempo_map([mel, har, bas, oct_, prc], [(0, BPM)])

    notes = scales.pitches(SCALE, TONIC, octaves=2)
    layout: list[tuple[str, int, int]] = []
    bar_no = 0

    for name, nbars, chords, intensity, melody in SECTIONS:
        layout.append((name, bar_no + 1, bar_no + nbars))
        for b in range(nbars):
            t = (bar_no + b) * BAR
            ch = chords[b % len(chords)]
            ps = CHORDS[ch]
            vel = 52 + 55 * intensity

            # --- accompaniment -----------------------------------------
            if intensity < 0.5:
                perform.arpeggio(har, t, ps, 'pima', step=0.5, vel=vel - 10)
            else:
                perform.strum(har, t + 1.0, ps, 0.9, vel)
                perform.strum(har, t + 2.0, ps, 0.9, vel - 4)
                perform.strum(har, t + 2.5, ps[-4:], 0.4, vel - 18, up=True)
                if intensity >= 0.9 or b % 4 == 3:
                    perform.rasgueado(har, t + 3.0, ps, total=1.0,
                                      hits=5 + int(2 * intensity), vel=vel + 8)
                else:
                    perform.strum(har, t + 3.0, ps, 0.9, vel)

            # --- bass ---------------------------------------------------
            root = min(ps)
            perform.put(bas, t, root, 1.4, vel + 6, jitter=0.008)
            perform.put(bas, t + 1.5, root + 7 if root + 7 < 60 else root, 0.9, vel - 8)
            perform.put(bas, t + 3.0, root, 0.9, vel)

            # --- melody -------------------------------------------------
            if melody == 'solo':
                # a fast run through the mode -- the instrumental break
                line = random.sample(notes, min(8, len(notes)))
                line.sort(reverse=(b % 2 == 0))
                perform.run(mel, t, line, step=0.25, vel=vel + 12)
            elif melody:
                for beat, deg in ((0.0, b % 4), (1.5, (b + 2) % 5), (2.5, (b + 4) % 6)):
                    p_ = notes[deg + 4]
                    perform.put(mel, t + beat, p_,
                                1.2 if beat == 0 else 0.8, vel + 14, jitter=0.012)
                    # Loudness follows note DENSITY, not velocity. To make a
                    # climax actually peak, add voices -- don't just turn it up.
                    if intensity >= 0.9:
                        perform.put(oct_, t + beat, p_ - 12,
                                    1.1 if beat == 0 else 0.7, vel - 14, jitter=0.012)

            # --- compas -------------------------------------------------
            drums.groove(prc, t, GROOVE, vel=44 + 50 * intensity,
                         fill=(b == nbars - 1),
                         only=['hand_clap'] if intensity < 0.4 else None)
        bar_no += nbars

    # final chord, let it ring
    end = bar_no * BAR
    perform.roll(har, end, CHORDS['A7'], total=1.8, hits=6, vel=104)
    perform.put(bas, end, 45, 4.0, 104)

    sc = stream.Score()
    for p in (mel, har, bas, oct_, prc):
        sc.insert(0, p)
    return sc, layout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default='groove_piece.mp3')
    ap.add_argument('--sf2', default=None)
    a = ap.parse_args()

    sc, layout = build()
    print(f'{len(sc.parts)} parts, {len(sc.flatten().notes)} notes, '
          f'{int(sc.highestTime // BAR)} bars')

    render.score_to_mp3(
        sc, a.out, sf2=a.sf2, channels=[1, 2, 3, 4, 10],
        stems=[render.Stem('melody',  gain_db=4, eq=[(2600, 1.2, 3.0)]),
               render.Stem('chords',  gain_db=-3, pan=-0.15,
                           eq=[(340, 1.1, -2.5)]),
               render.Stem('bass',    gain_db=1, hp=55, eq=[(108, 1.0, 2.0)]),
               render.Stem('octaves', gain_db=-6, pan=-0.3, hp=100),
               render.Stem('drums',   gain_db=-6, pan=0.2)])

    # ---- verify -----------------------------------------------------
    tm = midiio.TempoMap([(0, BPM)])
    secs = [(n, tm.seconds((a0 - 1) * BAR), tm.seconds(a1 * BAR)) for n, a0, a1 in layout]
    print('\n-- verification --')
    print('audio :', verify.audio_stats(a.out))
    print('pulse :', verify.pulse(a.out))
    print('mode  :', verify.outside_mode(verify.pitched_parts(sc),
                                         [p % 12 for p in scales.pitches(SCALE, TONIC)]))
    print('rhythm:', verify.rhythm_report(sc))
    for row in verify.section_levels(a.out, secs):
        print(f'  {row["section"]:14s} {row["rms_db"]:6.1f} dB'
              + ('   <- loudest' if row['is_peak'] else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
