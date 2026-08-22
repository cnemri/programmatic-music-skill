#!/usr/bin/env python3
"""
Check a piece you cannot listen to.

    python scripts/verify_music.py out.mp3
    python scripts/verify_music.py out.mp3 --midi out.mid --score score.musicxml
    python scripts/verify_music.py out.mp3 --scale hijaz --tonic D4 --key "d minor"
    python scripts/verify_music.py out.mp3 --section intro:0:15 --section climax:95:120

Exits non-zero if it finds something that is definitely wrong (clipping, a MIDI
channel collision, notes outside a declared instrument range), so it can gate a
build. Judgement calls -- notes outside the mode, low key confidence -- are
reported but never fail the run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from m21kit import midiio, scales, verify        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('audio', nargs='?', help='rendered mp3/wav')
    ap.add_argument('--midi', help='the .mid that produced it')
    ap.add_argument('--score', help='any music21-parseable score for symbolic checks')
    ap.add_argument('--scale', help='expected mode, e.g. hijaz / minor / raga_malkauns')
    ap.add_argument('--tonic', default='C4')
    ap.add_argument('--key', help='expected key, e.g. "d minor"')
    ap.add_argument('--instrument', help='check every part against this range')
    ap.add_argument('--section', action='append', default=[],
                    help='name:start_s:end_s (repeatable)')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    if not (a.audio or a.midi or a.score):
        ap.error('give at least one of: audio, --midi, --score')

    fails: list[str] = []
    rep: dict = {}

    # ---- symbolic ----------------------------------------------------
    if a.score:
        from music21 import converter, instrument as m21inst
        sc = converter.parse(a.score)
        pitched = verify.pitched_parts(sc) if hasattr(sc, 'parts') else sc
        rep['pitch'] = verify.pitch_report(pitched)
        rep['rhythm'] = verify.rhythm_report(sc)
        if hasattr(sc, 'parts'):
            rep['density'] = verify.density_by_part(sc)
        if a.scale:
            allowed = [p % 12 for p in scales.pitches(a.scale, a.tonic)]
            rep['mode'] = verify.outside_mode(pitched, allowed)
        try:
            rep['key'] = verify.key_check(pitched, a.key)
            if a.key and rep['key'].get('match') is False:
                fails.append(f'key: wrote {a.key}, analysis says {rep["key"]["detected"]}')
        except Exception as e:
            rep['key'] = {'error': str(e)}
        if a.instrument:
            inst = m21inst.fromString(a.instrument)
            rr = [dict(part=str(p.id), **verify.range_check(p, inst)) for p in sc.parts]
            rep['range'] = rr
            bad = sum(r.get('out_of_range', 0) for r in rr)
            if bad:
                fails.append(f'range: {bad} notes outside {a.instrument}')

    # ---- midi --------------------------------------------------------
    if a.midi:
        tracks = midiio.describe_midi(a.midi)
        rep['midi_tracks'] = tracks
        used = [c for t in tracks if t['notes'] for c in t['channels']]
        if len(used) != len(set(used)):
            fails.append('midi: two note-bearing tracks share a channel '
                         '(notes are being cut short) -- use midiio.write_midi(channels=...)')
        rep['midi_channels'] = used

    # ---- audio -------------------------------------------------------
    if a.audio:
        st = verify.audio_stats(a.audio)
        rep['audio'] = st
        if st['clipped']:
            fails.append('audio: clipped at 0 dBFS -- lower the FluidSynth gain')
        rep['pulse'] = verify.pulse(a.audio)
        if a.section:
            secs = []
            for s in a.section:
                nm, t0, t1 = s.split(':')
                secs.append((nm, float(t0), float(t1)))
            rep['sections'] = verify.section_levels(a.audio, secs)

    # ---- output ------------------------------------------------------
    if a.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        for k, v in rep.items():
            print(f'\n== {k}')
            if isinstance(v, list):
                for row in v:
                    print('  ', row)
            else:
                print('  ', v)
        print()
        if fails:
            print('FAIL:')
            for f in fails:
                print('  -', f)
        else:
            print('no hard failures found.')
        if 'sections' in rep:
            peak = next((r for r in rep['sections'] if r.get('is_peak')), None)
            if peak:
                print(f'loudest section: {peak["section"]} ({peak["rms_db"]} dB) '
                      f'-- is that where your climax is?')
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
