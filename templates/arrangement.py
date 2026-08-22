#!/usr/bin/env python3
"""
TEMPLATE: arrange an existing piece into another style.

The workflow that matters here is: **read the source's actual notes, do not
paraphrase them from memory.** Parse the score, extract the line, transpose it,
and then prove with verify.melody_match that what you rendered is what the
composer wrote. The arrangement lives in the accompaniment, the groove and the
articulation -- not in approximating the tune.

    python templates/arrangement.py --corpus bach/bwv66.6 -o out.mp3
    python templates/arrangement.py --file mozart.mid --part 0 --transpose -5 -o out.mp3

Choosing the transposition is a real compositional decision, not a convenience.
Moving G minor down a fourth to D minor puts the Andalusian cadence on Dm-C-Bb-A,
which is flamenco *por medio* -- the source's own dominant becomes the target
style's tonic. Look for that kind of alignment before you pick a key.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from music21 import converter, corpus, instrument, stream    # noqa: E402
from m21kit import drums, midiio, perform, render, verify     # noqa: E402

BPM = 108
BAR = 4.0
GROOVE = 'tangos_flamencos'
GM_PROGRAM = 24

# Target-style voicings, por medio (D minor / A Phrygian).
VOICING = {
    'Dm': [45, 50, 57, 62, 65], 'Gm': [43, 50, 55, 58, 62],
    'C':  [48, 52, 55, 60, 64], 'Bb': [46, 53, 58, 62, 65],
    'F':  [41, 48, 53, 57, 60, 65], 'A7': [45, 52, 57, 61, 64, 70],
}
PC_TO_CHORD = {2: 'Dm', 7: 'Gm', 0: 'C', 10: 'Bb', 5: 'F', 9: 'A7'}


def load(a) -> stream.Score:
    sc = corpus.parse(a.corpus) if a.corpus else converter.parse(a.file)
    if not isinstance(sc, stream.Score):
        s = stream.Score(); s.insert(0, sc); sc = s
    return sc


def extract_line(sc: stream.Score, part_index: int, transpose: int,
                 bars: tuple[int, int] | None) -> list[tuple[float, int, float]]:
    """The source's top line as (offset_from_start, midi, duration).

    Offsets are snapped to a sixteenth grid and durations run to the next
    attack, which turns a performance-timed MIDI into something you can place
    on a compás without inheriting its rubato.
    """
    part = list(sc.parts)[part_index] if sc.parts else sc
    top: dict[float, int] = {}
    for n in part.flatten().notes:
        o = round(float(n.offset) * 4) / 4
        top[o] = max(top.get(o, 0), max(p.midi for p in n.pitches))
    seq = sorted(top.items())
    if bars:
        lo, hi = (bars[0] - 1) * BAR, bars[1] * BAR
        seq = [(o, p) for o, p in seq if lo <= o < hi]
    if not seq:
        return []
    base = seq[0][0] - (seq[0][0] % BAR)
    out = []
    for i, (o, p) in enumerate(seq):
        nxt = seq[i + 1][0] if i + 1 < len(seq) else o + 1.0
        out.append((o - base, p + transpose, max(0.25, min(nxt - o, 4.0))))
    return out


def harmonise(line, nbars: int) -> list[str]:
    """One chord per bar, chosen from the melody's own pitch content.

    Crude on purpose -- for real work read the source's bass line instead
    (see references/08-analysis-and-verification.md and chordify()).
    """
    out = []
    for b in range(nbars):
        pcs = [p % 12 for o, p, _ in line if b * BAR <= o < (b + 1) * BAR]
        best, score = 'Dm', -1
        for pc, name in PC_TO_CHORD.items():
            tones = {(pc + i) % 12 for i in (0, 3, 7)} | {(pc + i) % 12 for i in (0, 4, 7)}
            s = sum(1 for x in pcs if x in tones)
            if s > score:
                best, score = name, s
        out.append(best)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--corpus', help='e.g. bach/bwv66.6')
    g.add_argument('--file', help='any music21-parseable score')
    ap.add_argument('--part', type=int, default=0, help='which part is the melody')
    ap.add_argument('--transpose', type=int, default=0, help='semitones')
    ap.add_argument('--bars', help='source bar range, e.g. 1:16')
    ap.add_argument('-o', '--out', default='arrangement.mp3')
    ap.add_argument('--sf2', default=None)
    a = ap.parse_args()

    src = load(a)
    print(f'source: {len(src.parts)} parts, {float(src.highestTime) / BAR:.0f} bars')
    try:
        print(f'  key analysis: {src.analyze("key")}')
    except Exception:
        pass

    rng = tuple(int(x) for x in a.bars.split(':')) if a.bars else None
    line = extract_line(src, a.part, a.transpose, rng)
    if not line:
        print('no notes extracted -- try a different --part', file=sys.stderr)
        return 1
    nbars = int(max(o for o, _, _ in line) // BAR) + 1
    chords = harmonise(line, nbars)
    print(f'extracted {len(line)} notes over {nbars} bars, transposed {a.transpose:+d}')

    # ---- build the arrangement ---------------------------------------
    mel = stream.Part(id='melody'); har = stream.Part(id='chords')
    bas = stream.Part(id='bass');   prc = stream.Part(id='drums')
    for p in (mel, har, bas):
        i = instrument.AcousticGuitar(); i.midiProgram = GM_PROGRAM; p.insert(0, i)
    midiio.add_tempo_map([mel, har, bas, prc], [(0, BPM)])

    for o, p, d in line:                       # the source, verbatim
        perform.put(mel, o, p, d * 0.94, 96 + (8 if o % 1 == 0 else 0), jitter=0.01)

    for b, ch in enumerate(chords):            # the arrangement, yours
        t, ps = b * BAR, VOICING[ch]
        perform.strum(har, t + 1.0, ps, 0.9, 84)
        perform.strum(har, t + 2.0, ps, 0.9, 82)
        perform.strum(har, t + 2.5, ps[-4:], 0.4, 66, up=True)
        if b % 4 == 3:
            perform.rasgueado(har, t + 3.0, ps, total=1.0, hits=5, vel=92)
        else:
            perform.strum(har, t + 3.0, ps, 0.9, 84)
        root = min(ps)
        perform.put(bas, t, root, 1.4, 92)
        perform.put(bas, t + 1.5, root + 7 if root + 7 < 60 else root, 0.9, 80)
        perform.put(bas, t + 3.0, root, 0.9, 86)
        drums.groove(prc, t, GROOVE, vel=78, fill=(b % 8 == 7))

    sc = stream.Score()
    for p in (mel, har, bas, prc):
        sc.insert(0, p)

    render.score_to_mp3(sc, a.out, sf2=a.sf2, channels=[1, 2, 3, 10],
        stems=[render.Stem('melody', gain_db=4.5, eq=[(2700, 1.2, 3.0)]),
               render.Stem('chords', gain_db=-3.5, pan=-0.15, eq=[(340, 1.1, -2.5)]),
               render.Stem('bass',   gain_db=1, hp=55),
               render.Stem('drums',  gain_db=-6, pan=0.2)])

    # ---- prove the source survived -----------------------------------
    print('\n-- verification --')
    m = verify.melody_match(mel, [(o, p) for o, p, _ in line])
    print(f'source fidelity: {m["matched"]}/{m["expected"]} notes at the right '
          f'offset ({m["pct"]}%)')
    if m['pct'] < 99:
        print('  MISSES:', m['first_misses'][:5])
    print('audio:', verify.audio_stats(a.out))
    print('pulse:', verify.pulse(a.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
