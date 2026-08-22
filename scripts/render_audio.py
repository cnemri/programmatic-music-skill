#!/usr/bin/env python3
"""
Render any music21-parseable score (or a MIDI file) to a mastered mp3.

    python scripts/render_audio.py score.mid -o out.mp3
    python scripts/render_audio.py song.musicxml -o out.mp3 --lufs -16 --lra 14
    python scripts/render_audio.py piece.mid -o out.mp3 \
        --stem "melody:+4:0.05" --stem "chords:-3:-0.2" --stem "drums:-6:0.2:perc"

Each --stem is name:gain_db[:pan[:perc]] and they are applied to the Parts in order.
Mark the percussion stem `perc` so it renders on MIDI channel 10 as drums rather than
as whatever melodic patch music21 guessed.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from music21 import converter, corpus, stream          # noqa: E402
from m21kit import midiio, render, verify              # noqa: E402


def parse_stem(spec: str) -> tuple[render.Stem, bool]:
    bits = spec.split(':')
    name = bits[0]
    gain = float(bits[1]) if len(bits) > 1 and bits[1] else 0.0
    pan = float(bits[2]) if len(bits) > 2 and bits[2] else 0.0
    is_perc = len(bits) > 3 and bits[3].lower().startswith('perc')
    eq = [] if is_perc else ([(2600.0, 1.2, 3.0)] if gain > 2 else [])
    return render.Stem(name=name, gain_db=gain, pan=pan, eq=eq,
                       hp=70.0 if is_perc else 90.0), is_perc


def load(src: str) -> stream.Score:
    if src.startswith('corpus:'):
        sc = corpus.parse(src[len('corpus:'):])
    else:
        sc = converter.parse(src)
    if not isinstance(sc, stream.Score):
        s = stream.Score()
        s.insert(0, sc)
        sc = s
    return sc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', help='MIDI/MusicXML/ABC/kern file, or corpus:bach/bwv66.6')
    ap.add_argument('-o', '--out', default='out.mp3')
    ap.add_argument('--sf2', default=None, help='soundfont (auto-found/downloaded)')
    ap.add_argument('--stem', action='append', default=[],
                    help='name:gain_db[:pan[:perc]] per part, in order')
    ap.add_argument('--lufs', type=float, default=-14.0)
    ap.add_argument('--lra', type=float, default=11.0)
    ap.add_argument('--fade-out', type=float, default=4.0)
    ap.add_argument('--title', default=None)
    ap.add_argument('--artist', default=None)
    ap.add_argument('--keep', action='store_true', help='keep intermediate wavs')
    ap.add_argument('--no-verify', action='store_true')
    a = ap.parse_args()

    tools = render.have_tools()
    missing = [k for k, v in tools.items() if not v]
    if missing:
        print(f'error: not on PATH: {missing}\n  brew install fluidsynth ffmpeg', file=sys.stderr)
        return 2

    sc = load(a.source)
    parts = list(sc.parts) or [sc]
    ns = list(sc.flatten().notes)
    # .notes counts Note AND Chord objects; MIDI import merges simultaneous
    # note-ons into Chords, so report pitches too or the number looks wrong.
    print(f'{a.source}: {len(parts)} part(s), {len(ns)} note/chord objects '
          f'({sum(len(n.pitches) for n in ns)} pitches), '
          f'{float(sc.highestTime):.0f} quarter-lengths')

    if a.stem:
        if len(a.stem) != len(parts):
            print(f'error: {len(parts)} parts but {len(a.stem)} --stem specs', file=sys.stderr)
            return 2
        pairs = [parse_stem(s) for s in a.stem]
        stems = [p[0] for p in pairs]
        channels, nxt = [], 1
        for _, is_perc in pairs:
            if is_perc:
                channels.append(10)
            else:
                if nxt == 10:
                    nxt += 1
                channels.append(nxt)
                nxt += 1
    else:
        stems = None
        channels = None

    res = render.score_to_mp3(
        sc, a.out, stems=stems, sf2=a.sf2, channels=channels,
        target_lufs=a.lufs, lra=a.lra, fade_out=a.fade_out,
        keep=a.keep,
        tags={k: v for k, v in (('title', a.title), ('artist', a.artist)) if v})

    print(f'\nwrote {res["mp3"]}')
    if not a.no_verify:
        st = verify.audio_stats(res['mp3'])
        print(f'  {st["duration_s"]}s  peak {st["peak_dbfs"]}dBFS  '
              f'LUFS {st.get("lufs", "?")}  clipped={st["clipped"]}')
        p = verify.pulse(res['mp3'])
        print(f'  pulse: {p["bpm"]} bpm (strength {p["strength"]}, metered={p["metered"]})')
        tracks = midiio.describe_midi(res['midi'])
        used = [c for t in tracks if t['notes'] for c in t['channels']]
        if len(used) != len(set(used)):
            print('  WARNING: MIDI channel collision -- notes are being cut short.')
        if st['clipped']:
            print('  WARNING: clipped. Re-render with a lower synth gain.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
