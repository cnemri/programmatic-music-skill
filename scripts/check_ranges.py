#!/usr/bin/env python3
"""
Report every note that falls outside its instrument's playable range.

    python scripts/check_ranges.py score.musicxml
    python scripts/check_ranges.py out.mid --source music21     # library data only
    python scripts/check_ranges.py score.xml --instrument Clarinet --assume sounding
    python scripts/check_ranges.py --list-instruments

Writing below an instrument's lowest string is the single most common error in
generated scores, and it is inaudible in a soundfont render: FluidSynth happily
pitch-shifts a sample down to a note no bass guitar can produce.

Two range sources are consulted:

  music21   -- Instrument.lowestNote / .highestNote, in WRITTEN pitch.
               Only 45 of 116 Instrument classes define a low note and only 9
               define a high note, so on its own this catches almost nothing at
               the top of the staff.
  practical -- PRACTICAL_WRITTEN_RANGES below. Hand-entered standard
               professional written ranges. NOT music21 data. Used to fill the
               gaps; music21's own value wins whenever it exists and is tighter.

Exits 1 if any note is out of range, 0 otherwise, so it can gate a build.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict

from music21 import converter, instrument, interval, note, pitch, stream

# ---------------------------------------------------------------------------
# SUPPLEMENT -- NOT music21 data.
# Standard professional ranges, expressed in WRITTEN pitch to match music21's
# convention (instrument.py:144 -- "a note object or a string for _written_
# pitch"). Conservative: the low/high a competent player is reliably expected to
# produce, not the record-setting extreme.
# ---------------------------------------------------------------------------
PRACTICAL_WRITTEN_RANGES: dict[str, tuple[str, str]] = {
    # woodwind
    'Piccolo': ('D4', 'C7'),
    'Flute': ('C4', 'D7'),
    'Recorder': ('F4', 'G6'),
    'Oboe': ('B-3', 'G6'),
    'EnglishHorn': ('B3', 'G6'),
    'Clarinet': ('E3', 'C7'),
    'BassClarinet': ('E-3', 'G6'),
    'Bassoon': ('B-1', 'E-5'),
    'Contrabassoon': ('B-1', 'G4'),
    'SopranoSaxophone': ('B-3', 'F#6'),
    'AltoSaxophone': ('B-3', 'F#6'),
    'TenorSaxophone': ('B-3', 'F#6'),
    'BaritoneSaxophone': ('B-3', 'F#6'),
    'Saxophone': ('B-3', 'F#6'),
    'Harmonica': ('C3', 'C6'),
    # brass
    'Horn': ('C3', 'C6'),
    'Trumpet': ('F#3', 'D6'),
    'Trombone': ('E2', 'B-4'),
    'BassTrombone': ('B-1', 'B-4'),
    'Tuba': ('D1', 'F4'),
    # strings (bowed)
    'Violin': ('G3', 'A7'),
    'Viola': ('C3', 'E6'),
    'Violoncello': ('C2', 'A5'),
    'Contrabass': ('E2', 'G4'),
    # strings (plucked) -- music21 stores these in SOUNDING pitch, see gotchas
    'Harp': ('C1', 'G#7'),
    'Guitar': ('E2', 'E6'),
    'AcousticGuitar': ('E2', 'E6'),
    'ElectricGuitar': ('E2', 'E6'),
    'AcousticBass': ('E1', 'G3'),
    'ElectricBass': ('E1', 'G4'),
    'FretlessBass': ('E1', 'G4'),
    'Banjo': ('C3', 'A5'),
    'Mandolin': ('G3', 'E6'),
    'Ukulele': ('C4', 'A5'),
    # keyboard
    'Piano': ('A0', 'C8'),
    'ElectricPiano': ('A0', 'C8'),
    'Harpsichord': ('F1', 'F6'),
    'Celesta': ('C4', 'C8'),
    'PipeOrgan': ('C2', 'C7'),
    'ElectricOrgan': ('C2', 'C6'),
    'ReedOrgan': ('C2', 'C6'),
    'Accordion': ('F3', 'A6'),
    # pitched percussion
    'Marimba': ('C2', 'C7'),
    'Vibraphone': ('F3', 'F6'),
    'Xylophone': ('C4', 'C7'),
    'Glockenspiel': ('G3', 'C6'),
    'TubularBells': ('C4', 'F5'),
    'ChurchBells': ('C4', 'F5'),
    'Timpani': ('D2', 'C4'),
    'SteelDrum': ('C4', 'C6'),
    'Kalimba': ('C4', 'C6'),
    'Dulcimer': ('G2', 'A5'),
    # voice
    'Soprano': ('C4', 'A5'),
    'MezzoSoprano': ('A3', 'F5'),
    'Alto': ('F3', 'D5'),
    'Tenor': ('C3', 'A4'),
    'Baritone': ('A2', 'F4'),
    'Bass': ('E2', 'D4'),
    'Vocalist': ('C3', 'C5'),
    'Choir': ('E2', 'A5'),
}


@dataclass
class Bound:
    """One end of a resolved range."""
    name: str
    midi: int
    source: str            # 'music21' | 'practical' | 'none'


@dataclass
class Violation:
    part: str
    instrument: str
    measure: object
    offset: float
    written: str
    writtenMidi: int
    sounding: str
    side: str              # 'low' | 'high'
    limit: str
    limitMidi: int
    limitSource: str
    semitonesOut: int

    def line(self) -> str:
        return (f'  m.{self.measure!s:<4} off {self.offset:>7.3f}  '
                f'{self.written:<5} (sounds {self.sounding:<5}) '
                f'{self.semitonesOut:>2} semitone(s) {self.side} of '
                f'{self.limit} [{self.limitSource}]')


def _p(name: str) -> pitch.Pitch:
    return pitch.Pitch(name)


def range_for(inst: instrument.Instrument,
              source: str = 'both') -> tuple[Bound | None, Bound | None]:
    """Resolve an instrument's WRITTEN range.

    source='music21'   only Instrument.lowestNote/.highestNote
    source='practical' only PRACTICAL_WRITTEN_RANGES
    source='both'      music21 wins where defined, practical fills the gaps
    """
    lo = hi = None
    if source in ('music21', 'both'):
        if inst.lowestNote is not None:
            lo = Bound(str(inst.lowestNote), inst.lowestNote.midi, 'music21')
        if inst.highestNote is not None:
            hi = Bound(str(inst.highestNote), inst.highestNote.midi, 'music21')
    if source in ('practical', 'both'):
        # walk the MRO so ElectricGuitar falls back to Guitar, etc.
        for cls in type(inst).__mro__:
            entry = PRACTICAL_WRITTEN_RANGES.get(cls.__name__)
            if entry is None:
                continue
            plo, phi = _p(entry[0]), _p(entry[1])
            if lo is None:
                lo = Bound(str(plo), plo.midi, 'practical')
            if hi is None:
                hi = Bound(str(phi), phi.midi, 'practical')
            break
    return lo, hi


def resolve_sounding(part: stream.Stream, assume: str) -> bool:
    """True if the part's written notes are already sounding pitch."""
    if assume == 'sounding':
        return True
    if assume == 'written':
        return False
    flag = part.atSoundingPitch
    if flag == 'unknown':
        for site in part.contextSites():
            if site.site.isStream and site.site.atSoundingPitch != 'unknown':
                return bool(site.site.atSoundingPitch)
        return True        # agents overwhelmingly write concert pitch
    return bool(flag)


def check_part(part: stream.Stream,
               inst: instrument.Instrument | None = None,
               *,
               source: str = 'both',
               assume: str = 'auto',
               tolerance: int = 0) -> tuple[list[Violation], dict]:
    """Return (violations, info) for one Part."""
    if inst is None:
        inst = part.getInstrument(returnDefault=True)
    lo, hi = range_for(inst, source)
    at_sounding = resolve_sounding(part, assume)
    trans = inst.transposition            # written -> sounding
    info = {
        'part': str(part.partName or part.id),
        'instrument': type(inst).__name__,
        'low': asdict(lo) if lo else None,
        'high': asdict(hi) if hi else None,
        'transposition': trans.directedName if trans else None,
        'interpretedAs': 'sounding' if at_sounding else 'written',
        'notesChecked': 0,
    }
    out: list[Violation] = []
    if lo is None and hi is None:
        return out, info

    for n in part.recurse().notes:
        if isinstance(n, note.Unpitched):
            continue
        for p in n.pitches:
            info['notesChecked'] += 1
            if at_sounding and trans is not None:
                written = p.transpose(trans.reverse())
                sounding = p
            elif not at_sounding and trans is not None:
                written = p
                sounding = p.transpose(trans)
            else:
                written = sounding = p
            m = n.getContextByClass(stream.Measure)
            common = dict(part=info['part'], instrument=info['instrument'],
                          measure=(m.number if m is not None else '-'),
                          offset=float(n.getOffsetInHierarchy(part)),
                          written=str(written), writtenMidi=written.midi,
                          sounding=str(sounding))
            if lo and written.midi < lo.midi - tolerance:
                out.append(Violation(side='low', limit=lo.name, limitMidi=lo.midi,
                                     limitSource=lo.source,
                                     semitonesOut=lo.midi - written.midi, **common))
            elif hi and written.midi > hi.midi + tolerance:
                out.append(Violation(side='high', limit=hi.name, limitMidi=hi.midi,
                                     limitSource=hi.source,
                                     semitonesOut=written.midi - hi.midi, **common))
    return out, info


def check_score(sc: stream.Score, **kw) -> tuple[list[Violation], list[dict]]:
    parts = list(sc.parts) if sc.parts else [sc]
    allv: list[Violation] = []
    infos: list[dict] = []
    for p in parts:
        v, i = check_part(p, **kw)
        allv += v
        infos.append(i)
    return allv, infos


def list_instruments(source: str) -> None:
    import inspect
    rows = []
    for name, obj in sorted(vars(instrument).items()):
        if not (inspect.isclass(obj) and issubclass(obj, instrument.Instrument)):
            continue
        i = obj()
        lo, hi = range_for(i, source)
        rows.append((name,
                     f'{lo.name}({lo.source[:4]})' if lo else '-',
                     f'{hi.name}({hi.source[:4]})' if hi else '-',
                     i.transposition.directedName if i.transposition else '-',
                     '' if i.midiProgram is None else str(i.midiProgram)))
    print(f'{"class":26} {"low(written)":16} {"high(written)":16} {"transp":8} gm')
    for r in rows:
        print(f'{r[0]:26} {r[1]:16} {r[2]:16} {r[3]:8} {r[4]}')
    print(f'\n{len(rows)} classes; source={source}')


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', nargs='?', help='any music21-parseable score')
    ap.add_argument('--source', choices=('music21', 'practical', 'both'), default='both',
                    help="which range table to use (default: both)")
    ap.add_argument('--assume', choices=('auto', 'sounding', 'written'), default='auto',
                    help="how to read the notes; auto resolves .atSoundingPitch "
                         "and treats 'unknown' as sounding (default: auto)")
    ap.add_argument('--instrument', help='force this Instrument class for every part')
    ap.add_argument('--part', type=int, help='check only this part index')
    ap.add_argument('--tolerance', type=int, default=0, help='allow N semitones of slack')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--list-instruments', action='store_true')
    a = ap.parse_args()

    if a.list_instruments:
        list_instruments(a.source)
        return 0
    if not a.path:
        ap.error('give a score path, or --list-instruments')

    if a.path.startswith('corpus:'):
        from music21 import corpus
        sc = corpus.parse(a.path[len('corpus:'):])
    else:
        sc = converter.parse(a.path)
    if not isinstance(sc, stream.Score):
        sc = stream.Score([sc])

    forced = None
    if a.instrument:
        # accept both the class name ('AcousticGuitar') and the human name
        # ('Acoustic Guitar'), because an agent will reach for either.
        forced = getattr(instrument, a.instrument, None)
        forced = forced() if forced else instrument.fromString(a.instrument)

    parts = list(sc.parts) if sc.parts else [sc]
    if a.part is not None:
        parts = [parts[a.part]]

    violations: list[Violation] = []
    infos: list[dict] = []
    per_part: list[list[Violation]] = []
    for idx, p in enumerate(parts):
        v, i = check_part(p, forced, source=a.source, assume=a.assume,
                          tolerance=a.tolerance)
        i['index'] = idx
        violations += v
        per_part.append(v)
        infos.append(i)

    if a.json:
        print(json.dumps({'parts': infos,
                          'violations': [asdict(v) for v in violations]}, indent=2))
        return 1 if violations else 0

    # Pair each info with its own violations by INDEX. Matching on the part
    # name double-reported every violation whenever two parts shared a name --
    # two Parts both called 'Acoustic Guitar' each printed the other's, so the
    # listed lines did not add up to the total on the last line.
    for i, mine in zip(infos, per_part):
        rng = (f"{i['low']['name'] if i['low'] else '?'}"
               f"..{i['high']['name'] if i['high'] else '?'}")
        src = '/'.join(sorted({b['source'] for b in (i['low'], i['high']) if b}))
        print(f"[{i['index']}] {i['part']} [{i['instrument']}] range {rng} "
              f"({src or 'none'}), transp {i['transposition'] or 'none'}, "
              f"read as {i['interpretedAs']} pitch, {i['notesChecked']} notes")
        for v in mine:
            print(v.line())
        if not mine:
            print('  ok')
        if i['low'] is None and i['high'] is None:
            print('  WARNING: no range known for this instrument -- nothing checked')
    print(f'\n{len(violations)} note(s) out of range')
    return 1 if violations else 0


if __name__ == '__main__':
    sys.exit(main())
