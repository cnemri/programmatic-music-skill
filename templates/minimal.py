#!/usr/bin/env python3
"""
TEMPLATE: the smallest complete piece. Read this first.

Melody, chords, drums, rendered to a mastered mp3 and verified. ~40 lines of
actual work. Everything else in templates/ is this plus structure.

    python templates/minimal.py -o out.mp3
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from music21 import instrument, stream                       # noqa: E402
from m21kit import drums, midiio, perform, render, verify     # noqa: E402

BPM, BAR = 96, 4.0
Am, F, C, G = [45, 52, 57, 60, 64], [41, 48, 53, 57, 60, 65], \
              [48, 52, 55, 60, 64], [43, 50, 55, 59, 62, 67]
PROGRESSION = [Am, F, C, G] * 4
MELODY = [69, 72, 71, 69, 67, 69, 71, 72, 74, 72, 71, 69, 67, 65, 67, 69]


def build() -> stream.Score:
    mel = stream.Part(id='melody')
    har = stream.Part(id='chords')
    prc = stream.Part(id='drums')
    for p in (mel, har):
        p.insert(0, instrument.AcousticGuitar())
    midiio.add_tempo_map([mel, har, prc], [(0, BPM)])

    for bar, ch in enumerate(PROGRESSION):
        t = bar * BAR
        # accompaniment: arpeggio for the first half, strummed for the second
        if bar < len(PROGRESSION) // 2:
            perform.arpeggio(har, t, ch, 'pima', step=0.5, vel=62)
        else:
            for beat in (0.0, 1.0, 2.0, 3.0):
                perform.strum(har, t + beat, ch, 0.9, 84 if beat % 2 == 0 else 74)
        # melody: one long note, one answering pair
        perform.put(mel, t, MELODY[bar], 1.6, 96, jitter=0.012)
        perform.put(mel, t + 2.0, MELODY[(bar + 5) % len(MELODY)], 0.9, 88, jitter=0.012)
        perform.put(mel, t + 3.0, MELODY[(bar + 6) % len(MELODY)], 0.9, 84, jitter=0.012)
        # groove: quieter for the first half, full for the second
        drums.groove(prc, t, 'rock_basic',
                     vel=58 if bar < len(PROGRESSION) // 2 else 80,
                     fill=(bar % 8 == 7))

    sc = stream.Score()
    for p in (mel, har, prc):
        sc.insert(0, p)
    return sc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default='minimal.mp3')
    ap.add_argument('--sf2', default=None)
    a = ap.parse_args()

    sc = build()
    render.score_to_mp3(
        sc, a.out, sf2=a.sf2,
        channels=[1, 2, 10],          # <- drums MUST be 10, guitars must differ
        stems=[render.Stem('melody', gain_db=4, eq=[(2600, 1.2, 3.0)]),
               render.Stem('chords', gain_db=-3, pan=-0.15),
               render.Stem('drums',  gain_db=-6, pan=0.2)])

    print('\naudio :', verify.audio_stats(a.out))
    print('pulse :', verify.pulse(a.out))
    print('rhythm:', verify.rhythm_report(sc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
