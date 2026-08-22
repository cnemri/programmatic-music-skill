#!/usr/bin/env python3
"""
TEMPLATE: non-metric / free-rhythm music.

For traditions where there is no beat: an Arabic taqsim or adhan, a Hindustani
alap, flamenco cante libre (granaína, taranta, malagueña), plainchant, rubato
recitative. Forcing these into a compás and calling it faithful is the single
most common way to get a tradition wrong.

The technique: **set the tempo to 60 bpm, so one quarter-length is exactly one
second, and compose in seconds.** Phrase lengths come from breath and prosody,
not bar lines. Silences between phrases are real and structural -- and in most
of these traditions the accompanist answers *in* those silences, which is where
the form actually lives.

Verify it with verify.pulse(): strength under ~0.1 proves it is unmetered.

    python templates/free_rhythm.py -o out.mp3
"""
from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from music21 import instrument, stream                  # noqa: E402
from m21kit import midiio, perform, render, scales, verify   # noqa: E402

SEED = 3
SCALE, TONIC = 'maqam_hijaz', 'D4'      # microtonal maqamat: see is_microtonal()
GM_PROGRAM = 24

# The accompaniment's chords. In modal/maqam music these are a cushion, not a
# progression -- they must never pull the ear away from the line.
CUSHION = {
    'i':   [38, 50, 57, 62, 65],
    'bII': [39, 46, 51, 58, 63],
    'iv':  [43, 50, 55, 58, 62],
    'V':   [45, 52, 57, 61, 64],
}

# Each phrase: (register-anchor degree, syllable shape, cushion chord).
# The arch is the form: low -> mid -> peak -> descent -> cadence on the tonic.
PHRASES = [
    (0, [0, 1, 2, 1, 0],             'i'),
    (0, [0, 2, 3, 2, 1, 0],          'i'),
    (2, [2, 3, 4, 3, 2],             'iv'),
    (3, [3, 4, 5, 4, 3, 2],          'iv'),
    (4, [4, 5, 6, 7, 6, 5, 4],       'bII'),   # the peak
    (4, [7, 6, 5, 4, 3, 2, 1],       'V'),     # descent begins
    (1, [2, 1, 0, 1, 0],             'V'),
    (0, [1, 0, 1, 0],                'i'),     # the cadence, long and still
]


def build() -> tuple[stream.Score, list[tuple[str, float, float]]]:
    random.seed(SEED)
    voz = stream.Part(id='voice')     # the line -- played as tremolo so it sings
    har = stream.Part(id='cushion')
    bas = stream.Part(id='bass')
    for p in (voz, har, bas):
        i = instrument.AcousticGuitar()
        i.midiProgram = GM_PROGRAM
        p.insert(0, i)
    # 60 bpm => 1 quarter-length == 1 second. Everything below is in seconds.
    midiio.add_tempo_map([voz, har, bas], [(0, 60)])

    deg = scales.pitches(SCALE, TONIC, octaves=2)
    t = 1.0
    marks: list[tuple[str, float, float]] = []

    # --- opening: the instrument alone, establishing the mode ---------
    perform.roll(har, t, CUSHION['i'], total=2.0, hits=6, vel=76)
    perform.put(bas, t, 38, 4.2, 84)
    t += 3.2
    perform.run(har, t, deg[:4], step=0.30, vel=72)
    t += 1.6
    perform.ligado(har, t, [deg[3], deg[2], deg[1], deg[0]], step=0.22, vel=70)
    t += 1.8
    marks.append(('opening', 0.0, t))

    # --- the phrases --------------------------------------------------
    for i, (anchor, shape, chord) in enumerate(PHRASES):
        start = t
        ps = CUSHION[chord]
        # cushion: slow arpeggio under the phrase, never competing
        perform.arpeggio(har, t, ps, [0, 1, 2, 3, 4, 3, 2, 1] * 3,
                         step=0.34, vel=44, dur=1.5)
        perform.put(bas, t, min(ps), 7.0, 62)

        vel = 74 + 5 * i - (10 if i >= 6 else 0)
        for k, d in enumerate(shape):
            pitch = deg[min(d + anchor, len(deg) - 1)]
            last = (k == len(shape) - 1)
            if last:
                # long held vowel: a plucked instrument sustains by tremolo
                hold = 2.6 if i == len(PHRASES) - 1 else 1.6
                t = perform.tremolo(voz, t, pitch, hold, vel=vel, rate=0.1)
            elif k % 3 == 2:
                t = perform.ligado(voz, t, [pitch, deg[min(d + anchor + 1, len(deg) - 1)],
                                            pitch], step=0.16, vel=vel)
            else:
                perform.put(voz, t, pitch, 0.42, vel, jitter=0.012)
                t += random.uniform(0.32, 0.5)     # prosody, not a grid

        marks.append((f'phrase{i + 1}', start, t))

        # the answer, in the silence -- this is the form
        if i < len(PHRASES) - 1:
            t += 0.5
            perform.roll(har, t, ps, total=1.0, hits=4, vel=70 + 2 * i)
            perform.put(bas, t, min(ps), 2.0, 74)
            t += random.uniform(1.6, 2.6)          # the saktah: real silence

    # --- final cadence, ringing out -----------------------------------
    t += 0.6
    perform.strum(har, t, CUSHION['bII'], 3.0, 62, spread=0.055)
    perform.put(bas, t, 39, 3.2, 70)
    t += 3.0
    perform.roll(har, t, CUSHION['i'], total=2.2, hits=6, vel=72)
    perform.put(bas, t, 38, 5.5, 80)
    for k, p in enumerate([62, 69, 74, 81]):        # harmonics
        perform.put(voz, t + 2.2 + k * 0.4, p, 3.5 - k * 0.4, 58 - k * 5)
    marks.append(('cadence', t, t + 7.0))

    sc = stream.Score()
    for p in (voz, har, bas):
        sc.insert(0, p)
    return sc, marks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default='free_rhythm.mp3')
    ap.add_argument('--sf2', default=None)
    a = ap.parse_args()

    sc, marks = build()
    print(f'{len(sc.parts)} parts, {len(sc.flatten().notes)} notes, '
          f'{float(sc.highestTime):.1f}s of music')
    if scales.is_microtonal(SCALE):
        print(f'NOTE: {SCALE} is microtonal; plain MIDI cannot carry the '
              f'quarter tones. Rendered as {scales.nearest_12tet(SCALE)}.')

    render.score_to_mp3(
        sc, a.out, sf2=a.sf2, channels=[1, 2, 3],
        # dynamic music: a looser loudness target and a wide LRA, or the
        # normaliser flattens the contrast the whole piece is built on
        target_lufs=-16.0, lra=14.0,
        stems=[render.Stem('voice',   gain_db=4.5, eq=[(2400, 1.2, 3.0)],
                           reverb=0.7, echo=(900, 0.17)),
               render.Stem('cushion', gain_db=-4, pan=-0.15, reverb=0.7),
               render.Stem('bass',    gain_db=0.5, hp=52, reverb=0.6)])

    print('\n-- verification --')
    print('audio:', verify.audio_stats(a.out))
    pulse = verify.pulse(a.out)
    print('pulse:', pulse)
    print('  ->', 'GOOD: genuinely unmetered.' if pulse['strength'] < 0.15
          else 'WARNING: a pulse is detectable; this should be free rhythm.')
    print('\nphrase lengths (should all differ -- breath, not bar lines):')
    for nm, t0, t1 in marks:
        print(f'  {nm:10s} {t0:6.1f} - {t1:6.1f}s   len {t1 - t0:4.1f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
