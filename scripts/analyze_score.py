#!/usr/bin/env python3
"""Harmonic summary of any score music21 can read.

Prints (or emits as JSON) the key, meter, tempo, ambitus, part inventory and a
bar-by-bar chord chart with roman numerals and chord symbols.

    python analyze_score.py bach/bwv66.6            # corpus path
    python analyze_score.py mypiece.mid --json      # any parseable file
    python analyze_score.py mypiece.xml --key "d minor" --bars 1-16

Verified on music21 10.5.0.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

from music21 import chord, converter, corpus, harmony, interval, key as m21key
from music21 import meter, note, roman, stream, tempo
from music21.analysis import discrete

KEY_ALGORITHMS = {
    'aarden': 'key.aarden',
    'krumhansl': 'key.krumhansl',
    'simple': 'key.simple',
    'bellman': 'key.bellman',
    'temperley': 'key.temperley',
}


# ---------------------------------------------------------------- loading


def load(source: str) -> stream.Score:
    """Parse a filesystem path, a corpus path, or a tinyNotation string."""
    if source.startswith('corpus:'):                       # explicit form
        s = corpus.parse(source[len('corpus:'):])
        if not isinstance(s, stream.Score):
            sc = stream.Score(); sc.insert(0, s); s = sc
        return s
    if os.path.exists(source):
        s = converter.parse(source)
    else:
        try:
            s = corpus.parse(source)
        except Exception:                                  # noqa: BLE001
            s = converter.parse(source)                    # tinyNotation etc.
    if not isinstance(s, stream.Score):
        sc = stream.Score()
        sc.insert(0, s)
        s = sc
    return s


def ensure_measures(s: stream.Score) -> stream.Score:
    if s.recurse().getElementsByClass(stream.Measure):
        return s
    return s.makeNotation(inPlace=False)


# ---------------------------------------------------------------- basics


def detect_key(s: stream.Score, algorithm: str, forced: str | None):
    if forced:
        k = m21key.Key(forced.split()[0], forced.split()[1] if ' ' in forced else 'major')
        return k, []
    k = s.analyze(KEY_ALGORITHMS.get(algorithm, algorithm))
    alts = [(str(a), round(a.correlationCoefficient, 4))
            for a in (k.alternateInterpretations or [])[:4]]
    return k, alts


def key_agreement(s: stream.Score) -> dict:
    """Run every weighting; unanimity is the real confidence signal."""
    out = {}
    for name, ident in KEY_ALGORITHMS.items():
        try:
            k = s.analyze(ident)
            out[name] = (str(k), round(k.correlationCoefficient, 4))
        except Exception as exc:                           # noqa: BLE001
            out[name] = (f'error: {exc}', 0.0)
    return out


def ambitus_of(sub) -> dict | None:
    amb = discrete.Ambitus()
    span = amb.getPitchSpan(sub)
    if span is None:
        return None
    lo, hi = span
    itv = interval.Interval(noteStart=lo, noteEnd=hi)
    return {'lowest': lo.nameWithOctave, 'highest': hi.nameWithOctave,
            'semitones': int(hi.ps - lo.ps), 'interval': itv.niceName}


def meters(s: stream.Score) -> list[dict]:
    seen = []
    for ts in s.recurse().getElementsByClass(meter.TimeSignature):
        entry = {'offset': float(ts.offset), 'ratio': ts.ratioString,
                 'measure': ts.measureNumber}
        if not seen or seen[-1]['ratio'] != entry['ratio']:
            seen.append(entry)
    return seen


def tempos(s: stream.Score) -> list[dict]:
    """Dedup: a MetronomeMark is usually duplicated into every Part."""
    out, seen = [], set()
    for mm in s.recurse().getElementsByClass(tempo.MetronomeMark):
        entry = (float(mm.offset), round(float(mm.getQuarterBPM() or 0), 3))
        if entry in seen:
            continue
        seen.add(entry)
        out.append({'offset': entry[0], 'bpm': entry[1], 'text': mm.text})
    return sorted(out, key=lambda x: x['offset'])


def parts_info(s: stream.Score) -> list[dict]:
    out = []
    for idx, p in enumerate(s.parts):
        ns = list(p.recurse().notes)
        # MIDI-parsed Parts get a memory address as .id; fall back to an index.
        pid = p.partName or (str(p.id) if not str(p.id).isdigit() else f'part{idx}')
        info = {'id': pid,
                'instrument': None,
                'notes': len(ns),
                'ambitus': ambitus_of(p)}
        inst = p.getInstrument(returnDefault=False)
        if inst is not None:
            info['instrument'] = inst.instrumentName or inst.classes[0]
        out.append(info)
    return out


# ---------------------------------------------------------------- harmony


def _label(c: chord.Chord, k: m21key.Key) -> tuple[str, str]:
    """(roman numeral figure, chord symbol) for one sounding chord."""
    try:
        rn = roman.romanNumeralFromChord(c, k).figure
    except Exception:                                      # noqa: BLE001
        rn = '?'
    closed = c.closedPosition(forceOctave=4, inPlace=False)
    closed.removeRedundantPitchNames(inPlace=True)
    try:
        sym = harmony.chordSymbolFigureFromChord(closed)
    except Exception:                                      # noqa: BLE001
        sym = 'Chord Symbol Cannot Be Identified'
    if sym.startswith('Chord Symbol Cannot'):
        sym = c.pitchedCommonName
    return rn, sym


def bar_chart(s: stream.Score, k: m21key.Key, per_bar: int) -> list[dict]:
    """One row per measure; `per_bar` chords kept, chosen by weighted duration."""
    ch = s.chordify(removeRedundantPitches=True)
    rows = []
    for m in ch.getElementsByClass(stream.Measure):
        chords = list(m.recurse().getElementsByClass(chord.Chord))
        if not chords:
            rows.append({'measure': m.number, 'chords': [], 'romans': [],
                         'symbols': [], 'offsets': []})
            continue
        # weight each distinct pitch-class set by duration * beat strength
        weight: dict[tuple, float] = defaultdict(float)
        first: dict[tuple, chord.Chord] = {}
        for c in chords:
            pcs = tuple(sorted({p.pitchClass for p in c.pitches}))
            bs = c.beatStrength if c.beatStrength is not None else 0.25
            bonus = 1.5 if (c.isTriad() or c.isSeventh()) else 1.0
            weight[pcs] += float(c.quarterLength) * (0.5 + bs) * bonus
            first.setdefault(pcs, c)
        best = sorted(weight, key=lambda p: -weight[p])[:per_bar]
        best.sort(key=lambda p: first[p].offset)
        picked = [first[p] for p in best]
        labels = [_label(c, k) for c in picked]
        rows.append({
            'measure': m.number,
            'offsets': [float(c.offset) for c in picked],
            'chords': [' '.join(p.nameWithOctave for p in c.pitches) for c in picked],
            'romans': [x[0] for x in labels],
            'symbols': [x[1] for x in labels],
        })
    return rows


def harmonic_rhythm(s: stream.Score) -> dict:
    ch = s.chordify(removeRedundantPitches=True)
    cs = list(ch.recurse().getElementsByClass(chord.Chord))
    if not cs:
        return {}
    changes = 0
    prev = None
    for c in cs:
        pcs = tuple(sorted({p.pitchClass for p in c.pitches}))
        if pcs != prev:
            changes += 1
        prev = pcs
    total_ql = float(ch.duration.quarterLength) or 1.0
    return {'verticalities': len(cs), 'distinct_changes': changes,
            'chords_per_quarter': round(changes / total_ql, 3),
            'mean_ql_per_chord': round(total_ql / max(changes, 1), 3)}


def pitch_class_profile(s: stream.Score, k: m21key.Key) -> dict:
    scale_pcs = {p.pitchClass for p in k.getScale().getPitches()}
    inside = outside = 0.0
    off: dict[str, float] = defaultdict(float)
    for n in s.recurse().notes:
        for p in n.pitches:
            ql = float(n.quarterLength)
            if p.pitchClass in scale_pcs:
                inside += ql
            else:
                outside += ql
                off[p.name] += ql
    tot = inside + outside or 1.0
    return {'in_key_pct': round(100 * inside / tot, 2),
            'out_of_key_pct': round(100 * outside / tot, 2),
            'out_of_key_by_name': {k2: round(v, 2)
                                   for k2, v in sorted(off.items(), key=lambda x: -x[1])}}


# ---------------------------------------------------------------- report


def analyze(source: str, algorithm='aarden', forced_key=None,
            per_bar=2, bars=None, compare=False) -> dict:
    s = ensure_measures(load(source))
    if bars:
        lo, hi = bars
        s = s.measures(lo, hi)
    k, alts = detect_key(s, algorithm, forced_key)
    md = s.metadata
    rep = {
        'source': source,
        'title': (md.title if md else None),
        'composer': (md.composer if md else None),
        'measures': len(s.parts[0].getElementsByClass(stream.Measure)) if s.parts
                    else len(s.getElementsByClass(stream.Measure)),
        'quarter_length': float(s.duration.quarterLength),
        'key': str(k),
        'key_algorithm': algorithm,
        'key_correlation': round(getattr(k, 'correlationCoefficient', 0.0) or 0.0, 4),
        'key_alternates': alts,
        'meters': meters(s),
        'tempos': tempos(s),
        'ambitus': ambitus_of(s),
        'parts': parts_info(s),
        'harmonic_rhythm': harmonic_rhythm(s),
        'pitch_class_profile': pitch_class_profile(s, k),
        'bars': bar_chart(s, k, per_bar),
    }
    if compare:
        rep['key_agreement'] = key_agreement(s)
    return rep


def as_text(r: dict) -> str:
    L = []
    L.append(f"{r['title'] or r['source']}  —  {r['composer'] or 'unknown composer'}")
    L.append(f"  key      {r['key']}  (r={r['key_correlation']}, {r['key_algorithm']})")
    if r['key_alternates']:
        L.append('  next     ' + ', '.join(f'{n} {c}' for n, c in r['key_alternates']))
    if r.get('key_agreement'):
        L.append('  vote     ' + ', '.join(f'{a}:{v[0]}' for a, v in r['key_agreement'].items()))
    L.append('  meter    ' + ', '.join(f"{m['ratio']}@m{m['measure']}" for m in r['meters'])
             or '  meter    (none)')
    L.append('  tempo    ' + (', '.join(f"{t['bpm']:.0f}bpm@{t['offset']}" for t in r['tempos'])
                              or '(none written — 120 assumed at playback)'))
    a = r['ambitus']
    if a:
        L.append(f"  ambitus  {a['lowest']}–{a['highest']}  ({a['semitones']} st, {a['interval']})")
    L.append(f"  length   {r['measures']} bars / {r['quarter_length']} ql")
    hr = r['harmonic_rhythm']
    if hr:
        L.append(f"  harm.rhy {hr['distinct_changes']} changes, "
                 f"{hr['mean_ql_per_chord']} ql per chord")
    p = r['pitch_class_profile']
    L.append(f"  in key   {p['in_key_pct']}%  (out: "
             f"{', '.join(f'{k2} {v}' for k2, v in list(p['out_of_key_by_name'].items())[:6]) or 'none'})")
    L.append('  parts')
    for pt in r['parts']:
        amb = pt['ambitus']
        rng = f"{amb['lowest']}–{amb['highest']}" if amb else '(no pitches)'
        L.append(f"    {pt['id'][:22]:24s} {pt['instrument'] or '':22s} "
                 f"{pt['notes']:5d} notes  {rng}")
    L.append('  chart')
    for b in r['bars']:
        if not b['romans']:
            L.append(f"    m{b['measure']:<4d} —")
            continue
        rn = ' | '.join(b['romans'])
        sy = ' | '.join(b['symbols'])
        L.append(f"    m{b['measure']:<4d} {rn:26s} {sy}")
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', help='file path, corpus path (bach/bwv66.6), or tinyNotation')
    ap.add_argument('--key', dest='forced_key', default=None,
                    help='skip detection, e.g. "d minor"')
    ap.add_argument('--algorithm', default='aarden', choices=sorted(KEY_ALGORITHMS))
    ap.add_argument('--compare-keys', action='store_true',
                    help='run all five weightings and print the vote')
    ap.add_argument('--per-bar', type=int, default=2,
                    help='how many chords to keep per measure (default 2)')
    ap.add_argument('--bars', default=None, help='measure range, e.g. 1-16')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)

    bars = None
    if a.bars:
        lo, _, hi = a.bars.partition('-')
        bars = (int(lo), int(hi or lo))

    r = analyze(a.source, a.algorithm, a.forced_key, a.per_bar, bars, a.compare_keys)
    print(json.dumps(r, indent=2) if a.json else as_text(r))
    return 0


if __name__ == '__main__':
    sys.exit(main())
