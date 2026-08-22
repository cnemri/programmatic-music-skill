# Instruments, Scoring, and Making a Score Look Like Music

Everything between "a Stream of correct pitches" and "a score a player would accept":
which instrument, what it can actually play, whether it transposes, what clef, how the
staves are bracketed, and the `make*` calls that turn absolute offsets into measures,
ties, beams and accidentals. Range violations and transposition errors are silent —
they render fine in a soundfont and are wrong on paper. Everything below was executed on
music21 **10.5.0**; the instrument data was diffed against v11.0.0b8 source and is identical.

## The complete instrument table

116 `Instrument` subclasses. Read the columns exactly:

- **GM** — `Instrument.midiProgram`, **0-indexed** (`music21/instrument.py:169`).
  MusicXML `<midi-program>` is this **+1**. `—` means music21 sets none, and the MusicXML
  exporter then emits no `<midi-instrument>` for it.
- **low / high** — `lowestNote` / `highestNote`, in **written** pitch
  (`music21/instrument.py:144-145`). `—` means *music21 defines no value*. It is **not** a
  claim that the instrument has no limit there. Only **45 of 116** classes define a low
  note, only **9** define a high note, and only those same **9** define both.
- **transp** — `Instrument.transposition`, the interval from **written to sounding**
  (`music21/instrument.py:176-177`). 12 classes are transposing.
- **notes** — `stringPitches` are **sounding** pitches of open strings; `perc key` is the
  0-indexed GM percussion key (`<midi-unpitched>` is this **+1**); `ch` is a hard-coded
  `midiChannel` (only `UnpitchedPercussion`, which pins channel 9 = MIDI 10,
  `music21/instrument.py:1126`).

Machine-readable copy with every field: `references/instrument_table.json`.

| class | GM | low (written) | midi | high (written) | midi | transp | semis | notes |
|---|---|---|---|---|---|---|---|---|
| `Accordion` | 21 | F3 | 53 | A6 | 93 | — | — |  |
| `AcousticBass` | 32 | E1 | 28 | — | — | — | — | str E1 A1 D2 G2 |
| `AcousticGuitar` | 24 | E2 | 40 | — | — | — | — | str E2 A2 D3 G3 B3 E4 |
| `Agogo` | 113 | — | — | — | — | — | — | perc key 67; ch 9 |
| `Alto` | 53 | — | — | — | — | — | — |  |
| `AltoSaxophone` | 65 | B-3 | 58 | — | — | M-6 | -9 |  |
| `Bagpipes` | 109 | — | — | — | — | — | — |  |
| `Banjo` | 105 | C3 | 48 | — | — | P-8 | -12 | str C3 G3 D4 A4 |
| `Baritone` | 53 | — | — | — | — | — | — |  |
| `BaritoneSaxophone` | 67 | B-3 | 58 | — | — | M-13 | -21 |  |
| `Bass` | 53 | — | — | — | — | — | — |  |
| `BassClarinet` | 71 | E-3 | 51 | — | — | M-9 | -14 |  |
| `BassDrum` | — | — | — | — | — | — | — | perc key 35; mod 'acoustic'; ch 9 |
| `BassTrombone` | 57 | B-1 | 34 | — | — | — | — |  |
| `Bassoon` | 70 | B-1 | 34 | — | — | — | — |  |
| `BongoDrums` | — | — | — | — | — | — | — | perc key 60; mod 'high'; ch 9 |
| `BrassInstrument` | 61 | — | — | — | — | — | — |  |
| `Castanets` | — | — | — | — | — | — | — | ch 9 |
| `Celesta` | 8 | — | — | — | — | — | — |  |
| `Choir` | 52 | — | — | — | — | — | — |  |
| `ChurchBells` | 14 | — | — | — | — | — | — |  |
| `Clarinet` | 71 | E3 | 52 | — | — | M-2 | -2 |  |
| `Clavichord` | 7 | — | — | — | — | — | — |  |
| `Conductor` | — | — | — | — | — | — | — |  |
| `CongaDrum` | — | — | — | — | — | — | — | perc key 64; mod 'low'; ch 9 |
| `Contrabass` | 43 | E2 | 40 | — | — | P-8 | -12 | str E1 A1 D2 G2 |
| `Contrabassoon` | 70 | B-1 | 34 | — | — | — | — |  |
| `Cowbell` | — | — | — | — | — | — | — | perc key 56; ch 9 |
| `CrashCymbals` | — | — | — | — | — | — | — | perc key 49; mod '1'; ch 9 |
| `Cymbals` | — | — | — | — | — | — | — | ch 9 |
| `Dulcimer` | 15 | — | — | — | — | — | — |  |
| `ElectricBass` | 33 | E1 | 28 | — | — | — | — | str E1 A1 D2 G2 |
| `ElectricGuitar` | 26 | E2 | 40 | — | — | — | — | str E2 A2 D3 G3 B3 E4 |
| `ElectricOrgan` | 16 | C2 | 36 | C6 | 84 | — | — |  |
| `ElectricPiano` | 2 | A0 | 21 | C8 | 108 | — | — |  |
| `EnglishHorn` | 69 | B3 | 59 | — | — | P-5 | -7 |  |
| `FingerCymbals` | — | — | — | — | — | — | — | ch 9 |
| `Flute` | 73 | C4 | 60 | — | — | — | — |  |
| `FretlessBass` | 35 | E1 | 28 | — | — | — | — | str E1 A1 D2 G2 |
| `Glockenspiel` | 9 | — | — | — | — | — | — |  |
| `Gong` | — | — | — | — | — | — | — |  |
| `Guitar` | 24 | E2 | 40 | — | — | — | — | str E2 A2 D3 G3 B3 E4 |
| `Handbells` | — | — | — | — | — | — | — |  |
| `Harmonica` | 22 | C3 | 48 | C6 | 84 | — | — |  |
| `Harp` | 46 | C1 | 24 | G#7 | 104 | — | — |  |
| `Harpsichord` | 6 | F1 | 29 | F6 | 89 | — | — |  |
| `HiHatCymbal` | — | — | — | — | — | — | — | perc key 44; mod 'pedal'; ch 9 |
| `Horn` | 60 | C2 | 36 | — | — | P-5 | -7 |  |
| `Instrument` | — | — | — | — | — | — | — |  |
| `Kalimba` | 108 | — | — | — | — | — | — |  |
| `KeyboardInstrument` | — | — | — | — | — | — | — |  |
| `Koto` | 107 | — | — | — | — | — | — |  |
| `Lute` | 24 | — | — | — | — | — | — |  |
| `Mandolin` | 48 | G3 | 55 | — | — | — | — | str G3 D4 A4 E5 |
| `Maracas` | — | — | — | — | — | — | — | perc key 70; ch 9 |
| `Marimba` | 12 | — | — | — | — | — | — |  |
| `MezzoSoprano` | 53 | — | — | — | — | — | — |  |
| `Oboe` | 68 | B-3 | 58 | — | — | — | — |  |
| `Ocarina` | 79 | C4 | 60 | — | — | — | — |  |
| `Organ` | 19 | — | — | — | — | — | — |  |
| `PanFlute` | 75 | C4 | 60 | — | — | — | — |  |
| `Percussion` | — | — | — | — | — | — | — |  |
| `Piano` | 0 | A0 | 21 | C8 | 108 | — | — |  |
| `Piccolo` | 72 | D4 | 62 | — | — | P8 | 12 |  |
| `PipeOrgan` | 19 | C2 | 36 | C6 | 84 | — | — |  |
| `PitchedPercussion` | — | — | — | — | — | — | — |  |
| `Ratchet` | — | — | — | — | — | — | — | ch 9 |
| `Recorder` | 74 | F4 | 65 | — | — | — | — |  |
| `ReedOrgan` | 20 | C2 | 36 | C6 | 84 | — | — |  |
| `RideCymbals` | — | — | — | — | — | — | — | ch 9 |
| `Sampler` | 55 | — | — | — | — | — | — |  |
| `SandpaperBlocks` | — | — | — | — | — | — | — | ch 9 |
| `Saxophone` | 65 | B-3 | 58 | — | — | — | — |  |
| `Shakuhachi` | 77 | C4 | 60 | — | — | — | — |  |
| `Shamisen` | 106 | — | — | — | — | — | — |  |
| `Shehnai` | 111 | — | — | — | — | — | — |  |
| `Siren` | — | — | — | — | — | — | — | ch 9 |
| `Sitar` | 104 | — | — | — | — | — | — |  |
| `SizzleCymbal` | — | — | — | — | — | — | — | ch 9 |
| `SleighBells` | — | — | — | — | — | — | — | ch 9 |
| `SnareDrum` | — | — | — | — | — | — | — | perc key 38; mod 'acoustic'; ch 9 |
| `Soprano` | 53 | — | — | — | — | — | — |  |
| `SopranoSaxophone` | 64 | B-3 | 58 | — | — | M-2 | -2 |  |
| `SplashCymbals` | — | — | — | — | — | — | — | ch 9 |
| `SteelDrum` | 114 | — | — | — | — | — | — |  |
| `StringInstrument` | 48 | — | — | — | — | — | — |  |
| `SuspendedCymbal` | — | — | — | — | — | — | — | ch 9 |
| `Taiko` | 116 | — | — | — | — | — | — | ch 9 |
| `TamTam` | — | — | — | — | — | — | — | ch 9 |
| `Tambourine` | — | — | — | — | — | — | — | perc key 54; ch 9 |
| `TempleBlock` | — | — | — | — | — | — | — | ch 9 |
| `Tenor` | 53 | — | — | — | — | — | — |  |
| `TenorDrum` | — | — | — | — | — | — | — | ch 9 |
| `TenorSaxophone` | 66 | B-3 | 58 | — | — | M-9 | -14 |  |
| `Timbales` | — | — | — | — | — | — | — | perc key 65; mod 'high'; ch 9 |
| `Timpani` | 47 | — | — | — | — | — | — |  |
| `TomTom` | — | — | — | — | — | — | — | perc key 41; mod 'low floor'; ch 9 |
| `Triangle` | — | — | — | — | — | — | — | perc key 81; mod 'open'; ch 9 |
| `Trombone` | 57 | E2 | 40 | — | — | — | — |  |
| `Trumpet` | 56 | F#3 | 54 | — | — | M-2 | -2 |  |
| `Tuba` | 58 | D1 | 26 | — | — | — | — |  |
| `TubularBells` | 14 | — | — | — | — | — | — |  |
| `Ukulele` | 48 | C4 | 60 | — | — | — | — | str G4 C4 E4 A4 |
| `UnpitchedPercussion` | — | — | — | — | — | — | — | ch 9 |
| `Vibraphone` | 11 | — | — | — | — | — | — |  |
| `Vibraslap` | — | — | — | — | — | — | — | perc key 58; ch 9 |
| `Viola` | 41 | C3 | 48 | — | — | — | — | str C3 G3 D4 A4 |
| `Violin` | 40 | G3 | 55 | — | — | — | — | str G3 D4 A4 E5 |
| `Violoncello` | 42 | C2 | 36 | — | — | — | — | str C2 G2 D3 A3 |
| `Vocalist` | 53 | — | — | — | — | — | — |  |
| `Whip` | — | — | — | — | — | — | — | ch 9 |
| `Whistle` | 78 | C4 | 60 | — | — | — | — | perc key 71 |
| `WindMachine` | — | — | — | — | — | — | — | ch 9 |
| `Woodblock` | 115 | — | — | — | — | — | — | perc key 76; mod 'high'; ch 9 |
| `WoodwindInstrument` | — | — | — | — | — | — | — |  |
| `Xylophone` | 13 | — | — | — | — | — | — |  |

Coverage: `classes 116 | withLowestNote 45 | withHighestNote 9 | withBothBounds 9 |
withNoBounds 71 | transposing 12 | withMidiProgram 78 | inGMPercMap 16`.
**music21 alone cannot tell you a note is too high.** `scripts/check_ranges.py` carries a
hand-entered `PRACTICAL_WRITTEN_RANGES` supplement (marked as not-music21) to close that hole.

## Finding an instrument: fromString, MIDI program, partName

```python
from music21 import *
for s in ['Clarinet 2 in A', 'Bb Clarinet', 'Eb Clarinet',
          'Klarinette in B.', 'Corno inglese', 'saxofono tenore']:
    i = instrument.fromString(s)
    print(f'{s!r:20} -> {type(i).__name__:16} transp={i.transposition}')
```
```
'Clarinet 2 in A'    -> Clarinet         transp=<music21.interval.Interval m-3>
'Bb Clarinet'        -> Clarinet         transp=<music21.interval.Interval M-2>
'Eb Clarinet'        -> Clarinet         transp=<music21.interval.Interval m3>
'Klarinette in B.'   -> Clarinet         transp=<music21.interval.Interval M-2>
'Corno inglese'      -> EnglishHorn      transp=<music21.interval.Interval P-5>
'saxofono tenore'    -> TenorSaxophone   transp=<music21.interval.Interval M-9>
```

`fromString` (`music21/instrument.py:2326`) searches English/French/German/Italian/Russian/
Spanish plus abbreviations, sets `.transposition` from the key named in the string, and
**overwrites `.instrumentName` with your whole input string** — including junk. Pin the
language with `instrument.fromString(s, language=instrument.SearchLanguage.GERMAN)`.
`instrument.getAllNamesForInstrument(instrument.Flute())` (`:2513`) goes the other way.

```python
instrument.instrumentFromMidiProgram(65)   # -> <music21.instrument.AltoSaxophone …>
instrument.instrumentFromMidiProgram(128)  # -> InstrumentException: No instrument found …
```

`MIDI_PROGRAM_TO_INSTRUMENT` (`music21/instrument.py:1933`) is lossy and one-way: programs
80–103 and 118–127 all map to `Sampler`, 44/45/48–51 to bare `StringInstrument`.
The lookup sets `inst.midiProgram = number` afterwards, so the round trip preserves the
program even when the class is generic.

**There is no `deducePartName()` function** — `hasattr(instrument, 'deducePartName')` is
`False`. What exists is `Part.partName` (`music21/stream/base.py:13590`), which walks the
Part for the first `Instrument` and takes its `.partName`, falling back to `.instrumentName`:

```python
p = stream.Part()
p.partName                      # None
p.insert(0, instrument.Clarinet())
p.partName, p.partAbbreviation  # ('Clarinet', 'Cl')
p.partName = 'Reed 1'           # explicit always wins
```

The result is **cached**: mutating an already-inserted instrument's name does nothing until
`p.coreElementsChanged()`. Related: `partitionByInstrument(s)` (`:2097`) re-splits a Stream
into one Part per unique `instrumentName` — it matches by *name string*, not class, and the
returned parts still need `makeRests(fillGaps=True)` + `makeMeasures()` + `makeTies()`.
`deduplicate(s)` (`:1822`) collapses duplicate instruments at one offset;
`unbundleInstruments`/`bundleInstruments` (`:46`, `:85`) move `NotRest.storedInstrument`
in and out of the Stream.

## Transposing instruments done right

`Instrument.transposition` is the interval **written → sounding**: a B♭ clarinet is `M-2`,
so written C4 sounds B♭3. The Stream machinery is `atSoundingPitch` +
`toWrittenPitch()` / `toSoundingPitch()` (`music21/stream/base.py:5233, 5401, 5495`) — both
exist and both work on `Stream`, `Part` and `Score`. **You must declare which one you
wrote:** `atSoundingPitch` defaults to `'unknown'`, and with `'unknown'` both conversions
are silent no-ops that still flip the flag.

```python
sc = stream.Score(); p = stream.Part(id='clarinet')
p.insert(0, instrument.Clarinet())
m = stream.Measure(number=1)
m.insert(0, key.KeySignature(0))                       # concert C major
for nm in ['C4', 'D4', 'E4', 'F4']:
    m.append(note.Note(nm, quarterLength=1))
p.append(m); sc.insert(0, p)
sc.atSoundingPitch = True                              # <-- the whole trick
written = sc.toWrittenPitch()
back    = written.toSoundingPitch()
```
```
sounding source          atSoundingPitch=True   ['C4','D4','E4','F4']  key=0 sharps
after toWrittenPitch()   atSoundingPitch=False  ['D4','E4','F#4','G4'] key=2 sharps
round-trip               atSoundingPitch=True   ['C4','D4','E4','F4']  key=0 sharps
```

The **key signature transposes too** — `_transposeByInstrument` includes `key.KeySignature`
in its class filter (`music21/stream/base.py:5322-5325`). Written → sounding is the mirror:

```python
p = stream.Part(); p.append(instrument.BaritoneSaxophone())
m = stream.Measure(); m.append(note.Note('A4')); p.append(m)
sc = stream.Score([p]); sc.atSoundingPitch = False
sc.toSoundingPitch().recurse().notes[0].nameWithOctave        # 'C3'   (M-13 down)
```

Set the flag on the **Score**; parts left at `'unknown'` resolve upward through
`contextSites()` (`:5356`). Setting it never transposes anything by itself.

### What the exporters do with the flag — verified

MusicXML export unconditionally calls `toWrittenPitch(ottavasToSounding=True)`
(`music21/musicxml/m21ToXml.py:1429, 2673`). MIDI export calls `toSoundingPitch()` **only if
the flag is exactly `False`** (`music21/midi/translate.py:316`). One clarinet part holding
a written/concert C4, exported three ways:

| `atSoundingPitch` | MusicXML staff pitch | `<transpose>` emitted | MIDI note number |
|---|---|---|---|
| `True` | D4 | yes (−1 dia, −2 chr) | 60 (C4) |
| `False` | C4 | yes | 58 (B♭3) |
| `'unknown'` (default) | C4 | yes | **60 (C4)** |

The last row is the trap: MusicXML says "C4 on the staff, sounds a major second lower"
while the MIDI file plays C4. **The two exports of the same Score disagree by a whole
tone.** Always set the flag.

## Range checking

`lowestNote`/`highestNote` are **written** pitch, so a range check on a sounding-pitch part
must transpose to written first. `scripts/check_ranges.py` does that and reports every
offending note.

```bash
python scripts/check_ranges.py score.musicxml                   # music21 + practical table
python scripts/check_ranges.py score.musicxml --source music21  # library data only
python scripts/check_ranges.py score.xml --instrument Clarinet --assume sounding
python scripts/check_ranges.py --list-instruments
```

Real output on a score whose bass, violin and guitar parts each dip below the lowest string
and jump above the top fret:

```
Electric Bass [ElectricBass] range E1..G4 (music21/practical), transp none, read as sounding pitch, 4 notes
  m.1    off   1.000  C1    (sounds C1   )  4 semitone(s) low of E1 [music21]
  m.1    off   3.000  A0    (sounds A0   )  7 semitone(s) low of E1 [music21]
Clarinet [Clarinet] range E3..C7 (music21/practical), transp M-2, read as written pitch, 4 notes
  ok
Violin [Violin] range G3..A7 (music21/practical), transp none, read as sounding pitch, 4 notes
  m.1    off   1.000  F3    (sounds F3   )  2 semitone(s) low of G3 [music21]
  m.1    off   3.000  B7    (sounds B7   )  2 semitone(s) high of A7 [practical]
Guitar [AcousticGuitar] range E2..E6 (music21/practical), transp none, read as sounding pitch, 4 notes
  m.1    off   1.000  B1    (sounds B1   )  5 semitone(s) low of E2 [music21]
  m.1    off   3.000  A6    (sounds A6   )  5 semitone(s) high of E6 [practical]

6 note(s) out of range
```

The same run with `--source music21` finds only **4** of the 6 — both high-note violations
vanish, because neither Violin nor Guitar defines `highestNote`. Exit status is 1 when
anything is out of range, so it gates a build. It is importable too —
`from check_ranges import check_part, range_for; violations, info = check_part(part)`.
`--assume auto` resolves `.atSoundingPitch` up the tree and treats `'unknown'` as
**sounding**, because that is what generated scores overwhelmingly contain.

## Building a multi-part Score

```python
sc = stream.Score(id='quartet')
sc.insert(0, metadata.Metadata(title='Test Quartet', composer='Agent', copyright='CC0'))

parts = []
for pid, pname, cls, events in spec:
    p = stream.Part(id=pid)
    i = cls()
    i.partId = pid                      # <-- becomes <score-part id>, NOT Part.id
    i.partName = pname                  # <-- becomes <part-name>
    i.instrumentId = pid + '-I'         # <-- becomes <score-instrument id>
    p.insert(0, i)
    p.insert(0, meter.TimeSignature('4/4'))
    p.insert(0, key.KeySignature(0))
    for nm, off, ql in events:
        p.insert(off, note.Note(nm, quarterLength=ql))
    p.insert(0, clef.bestClef(p, recurse=True))
    p.makeNotation(inPlace=True)
    sc.insert(0, p); parts.append(p)

sc.insert(0, layout.StaffGroup(parts, name='String Quartet', abbreviation='Str Qt',
                               symbol='bracket', barTogether=True))
sc.atSoundingPitch = True
sc.write('musicxml', fp='quartet.musicxml')
```
```
score-part ids: ['P1', 'P2', 'P3', 'P4']
part-names    : ['Violin I', 'Violin II', 'Viola', 'Cello']
clef signs    : ['G', 'G', 'G', 'F']
group         : ['bracket'] ['yes']
midi programs : ['41', '41', '42', '43']       # music21 40,40,41,42 + 1
```

Rules that actually bite:

- **`Part.id` is ignored by MusicXML.** `<score-part id>` comes from `Instrument.partId`;
  if it is `None` or collides, the exporter substitutes a random MD5
  (`music21/musicxml/m21ToXml.py:2751-2753`). Set `partId` yourself for stable diffs.
- **`<part-name>` comes from `Part.partName`** (`:2931`), deduced from the first instrument.
  `Instrument.partName` gives "Violin I"-style names; `Instrument.instrumentName` names the
  sound. Different fields, both exported.
- `midiChannel` is auto-assigned at export via `autoAssignMidiChannel`
  (`music21/instrument.py:239`), skipping channel 9. It does **not** control MIDI-file
  channels — see `references/05-io-formats.md`.

### PartStaff and StaffGroup

`StaffGroup(parts, name=, abbreviation=, symbol=, barTogether=)` (`music21/layout.py:394`):
`symbol` ∈ `'bracket' | 'line' | 'brace' | 'square' | None`, `barTogether` ∈
`True | False | None | 'Mensurstrich'`. For a grand staff you want **one** MusicXML part
with two staves, not two parts joined by a brace — that needs `PartStaff`, not `Part`:

```python
rh = stream.PartStaff(id='rh'); lh = stream.PartStaff(id='lh')
# … fill each with Measures, put a BassClef in lh …
sc.insert(0, layout.StaffGroup([rh, lh], name='Piano', symbol='brace', barTogether=True))
```
```
PartStaff  <part> count=1 <staves>=['2'] part-group=0 group-symbol=[]
Part       <part> count=2 <staves>=[]    part-group=2 group-symbol=['brace']
```

Joining needs all four conditions (`music21/musicxml/partStaffExporter.py:155`):
the streams are `PartStaff`, they are in **one** `StaffGroup`, there are **≥2** of them,
and each already **has Measures**. Miss any one and you silently get separate parts.

## The makeNotation pipeline

Raw input: one flat `Part`, notes at absolute offsets, no measures, one note straddling a
barline, one accidental that needs cancelling. One call does everything
(`music21/stream/base.py:6971`):

```python
p = stream.Part(id='melody')
p.insert(0, instrument.Flute())
p.insert(0, meter.TimeSignature('4/4'))
p.insert(0, key.KeySignature(2))                        # D major
for off, nm, ql in [(0.0,'D5',0.5),(0.5,'E5',0.5),(1.0,'F#5',0.5),(1.5,'G5',0.5),
                    (2.0,'F5',1.0),(3.0,'F#5',1.0),(4.0,'A5',3.5),(7.5,'C#5',2.5)]:
    p.insert(off, note.Note(nm, quarterLength=ql))
p.makeNotation()                                        # or inPlace=True
```
```
{0.0} <music21.stream.Measure 1 offset=0.0>
    {0.0} <music21.instrument.Flute 'Flute'>   {0.0} <music21.clef.TrebleClef>
    {0.0} <music21.key.KeySignature of 2 sharps>  {0.0} <music21.meter.TimeSignature 4/4>
    {0.0} <music21.note.Note D> … {3.0} <music21.note.Note F#>
{4.0} <music21.stream.Measure 2 offset=4.0>
    {0.0} <music21.note.Note A>          {3.5} <music21.note.Note C#>
{8.0} <music21.stream.Measure 3 offset=8.0>
    {0.0} <music21.note.Note C#>         {2.0} <music21.bar.Barline type=final>
```

### The order, and what each step contributes

`Stream.makeNotation` runs exactly this sequence (`music21/stream/base.py:7038-7089`):

| # | Call | Only if | Effect |
|---|---|---|---|
| 1 | `makeVoices(fillGaps=True)` | no measures yet | overlapping notes → `Voice` sub-streams |
| 2 | `makeMeasures(bestClef=…)` | no measures yet | `Measure` objects + `Clef` + `TimeSignature` + final barline |
| 3 | `makeAccidentalsInMeasureStream` | `streamStatus.accidentals` false | sets every `Accidental.displayStatus` |
| 4 | `makeTies` | always | splits notes at barlines, links with `Tie` |
| 5 | `splitElementsToCompleteTuplets` / `consolidateCompletedTuplets` | per measure | fixes partial tuplets |
| 6 | `makeBeams` | `streamStatus.beams` false | 8ths and shorter get beam groups |
| 7 | `makeTupletBrackets` | per measure | tuplet brackets/numbers |

Stepping through by hand, printing after each call:

```
1. makeMeasures      3 measures; no ties, no beams, every displayStatus None
2. makeAccidentals   F#5 display=False (in key)   F5 -> natural display=True
                     next F#5 display=True (cancels)  C#5 display=False (in key)
3. makeTies          C#5 becomes  C#5 tie=start | C#5 tie=stop
4. makeBeams         D5['start'] E5['stop']  F#5['start'] G5['stop']
```

The accidentals step is the whole point: an F♮ inside D major prints a natural and the F♯
after it prints a courtesy sharp. Skip it and `displayStatus` is `None` everywhere, so
renderers guess. Cross-measure context comes from `makeAccidentalsInMeasureStream`
(`music21/stream/makeNotation.py:1690-1722`): for each measure it feeds the previous
measure's pitches in as `pitchPastMeasure` (filtered to non-diatonic pitches when a new key
signature intervenes) and carries `tiePitchSet` across the barline so a tied note does not
re-print its accidental. `Part.makeAccidentals` (`music21/stream/base.py:13698`) overrides
the base method to route through it; the base `Stream.makeAccidentals` (`:6735`) tracks
measures too but without the key-filtered `pitchPastMeasure` or the cross-barline tie set.

The source comment says accidentals must precede ties (`base.py:7056`). Both orders produced
identical results in every case I tested — but follow the documented order anyway, since
`makeTies` doubles the note count and `tiePitchSet` is what keeps the two consistent.

### The other make* calls

```python
p.makeRests(fillGaps=True, inPlace=False)                    # gaps -> Rests
p.makeRests(refStreamOrTimeRange=[0.0, 8.0], fillGaps=True)  # also pad out to length 8.0
p.makeVoices(inPlace=False, fillGaps=True)                   # overlaps -> Voice 1 / Voice 2
m.makeBeams(inPlace=True, failOnNoTimeSignature=True)        # raise instead of no-op
```
```
makeRests  {0.0} Rest quarter | {1.0} Note C | {2.0} Rest dotted-half | {5.0} Note D
makeVoices {0.0} Voice[ C(ql=4) ]  +  {0.0} Voice[ E, F, Rest half ]
makeBeams  no TimeSignature -> StreamException 'cannot process beams in a Measure
           without a time signature'   (the default silently produces no beams)
```

`makeBeams` on a Stream that is neither a `Measure` nor contains Measures always raises
(`makeNotation.py:142`). `Measure.makeNotation` (`base.py:13126`) is a reduced pipeline —
accidentals, tuplets, beams; no `makeTies`, since ties are inherently cross-measure.
`Score.makeNotation` (`base.py:14291`) forwards to every part.

**Exporting calls this for you.** `sc.write('musicxml')` runs `makeNotation` on a deep copy,
including `makeMeasures` and `bestClef`, so a bare Part of notes still exports as valid
notated music. Call it yourself when you need to *inspect* the result, or when you want
`inPlace=True` so the object you hold is the notated one.

## Clefs

| class | sign | line | octaveChange | lowestLine |
|---|---|---|---|---|
| `FrenchViolinClef` | G | 1 | 0 | 33 |
| `TrebleClef` | G | 2 | 0 | 31 |
| `GSopranoClef` | G | 3 | 0 | 29 |
| `Treble8vaClef` | G | 2 | +1 | 24 |
| `Treble8vbClef` | G | 2 | −1 | 24 |
| `SopranoClef` | C | 1 | 0 | 29 |
| `MezzoSopranoClef` | C | 2 | 0 | 27 |
| `AltoClef` | C | 3 | 0 | 25 |
| `TenorClef` | C | 4 | 0 | 23 |
| `CBaritoneClef` | C | 5 | 0 | 21 |
| `FBaritoneClef` | F | 3 | 0 | 21 |
| `BassClef` | F | 4 | 0 | 19 |
| `Bass8vaClef` / `Bass8vbClef` | F | 4 | ±1 | 19 |
| `SubBassClef` | F | 5 | 0 | 17 |
| `PercussionClef` | percussion | — | 0 | 31 |
| `TabClef` | TAB | 5 | 0 | 31 |
| `NoClef` / `JianpuClef` | none / jianpu | — | 0 | None |

`lowestLine` is a `diatonicNoteNum` (E4 = 31). Setting `.octaveChange` on a `PitchClef`
shifts `lowestLine` by 7 per octave (`music21/clef.py:316`), but the `8va`/`8vb`
constructors ship with it already offset. `clef.clefFromString('G2', -1)` → `Treble8vbClef`;
`'Treble'`, `'TAB'`, `'Percussion'`, `'None'` also parse (`music21/clef.py:741`).

`clef.bestClef(stream, allowTreble8vb=False, recurse=False)` (`:894`) averages
`diatonicNoteNum` with a ±3 bonus outside A4/F2 and thresholds it:

```
['C6','D6','E6'] -> TrebleClef        ['D4'] -> TrebleClef  (Treble8vbClef if allowTreble8vb)
['C3','E3','G3'] -> BassClef          ['C0','D0'] -> Bass8vbClef
['C7','D7']      -> Treble8vaClef
```

Two traps: it does **not** recurse by default, so on a Part of Measures you get the fallback
`TrebleClef` unless you pass `recurse=True`; and it knows **nothing about the instrument** —
in the quartet above the viola's B3–C4 tessitura produced a `TrebleClef`. Choose per
instrument yourself: `AltoClef()` for viola, `TenorClef()` for high cello/bassoon/trombone,
`Treble8vbClef()` for tenor voice and guitar, `PercussionClef()` for a kit part. If no clef
exists anywhere, `makeMeasures` calls `bestClef(recurse=True)` (`makeNotation.py:496-501`)
**regardless of the `bestClef=False` argument**.

## Lyrics

```python
n = note.Note('C5')
n.lyrics.append(note.Lyric(text='A', number=1, syllabic='begin'))   # verse 1
n.lyrics.append(note.Lyric(text='Kyr', number=2, syllabic='begin')) # verse 2
n.lyric = 'hel-lo'          # shortcut: one Lyric, number=1, syllabic='single'
n.addLyric('one'); n.addLyric('two')   # appends as number=1 then 2
```

`syllabic` ∈ `'single' | 'begin' | 'middle' | 'end'` and controls the hyphens a renderer
draws. It is inferred from hyphens in the text (`music21/note.py:145`):
`'hel-'`→`begin`, `'-lo-'`→`middle`, `'-lo'`→`end`, `'hi'`→`single`, and the hyphens are
stripped. Reading `n.lyric` on a multi-verse note returns the verses joined by `\n`.
Export is per-verse and faithful:

```xml
<lyric name="1" number="1"><syllabic>begin</syllabic><text>A</text></lyric>
<lyric name="2" number="2"><syllabic>single</syllabic><text>Kyr</text></lyric>
```

Read them back with `text.assembleLyrics(part, lineNumber=1)` → `'Gloria !'` or
`text.assembleAllLyrics(part)` for every verse (`music21/text.py:56, 129`).
**Lyrics never reach MIDI.**

## Percussion

`note.Unpitched` (`music21/note.py:1833`) is a `NotRest` with **no `.pitch`**. It carries
`displayStep`/`displayOctave` (default `B4`) for staff placement and `storedInstrument`
for what sounds.

```python
u = note.Unpitched(displayName='E4', storedInstrument=instrument.SnareDrum())
u.displayPitch()                       # <music21.pitch.Pitch E4>
u.storedInstrument.percMapPitch        # 38
```

`UnpitchedPercussion.modifier` (`music21/instrument.py:1144`) picks the GM key:

```
SnareDrum        acoustic=38 side=37 electric=40
HiHatCymbal      closed=42 open=46 pedal=44
TomTom           low floor=41 high floor=43 low=45 low-mid=47 high-mid=48 high=50
BassDrum         acoustic=35 1=36
Woodblock        high=76 low=77
```

Modifiers are normalized (`'LO'` → `'low'`) and only remap when `inGMPercMap` is True.
`percussion.PercussionChord` (`music21/percussion.py:32`) groups simultaneous hits on one
stem and may mix `Unpitched` with real `Note`s; `.isChord` is `False` and `.pitches`
returns only the pitched members (`:147`). A drum part needs no extra work:

```python
p = stream.Part(id='drums'); p.insert(0, instrument.SnareDrum())
m = stream.Measure(number=1)
m.insert(0, meter.TimeSignature('4/4')); m.insert(0, clef.PercussionClef())
for i in range(4):
    kit = instrument.BassDrum() if i % 2 == 0 else instrument.SnareDrum()
    m.append(note.Unpitched(storedInstrument=kit, quarterLength=1))
p.append(m)
```
```
midi (channel, pitch): [(10, 35), (10, 38), (10, 35), (10, 38)]
xml <sign>: ['percussion']   <display-step>/<display-octave>: B4 ×4
xml <midi-unpitched>: ['39']        # 38 + 1
```

Channel 10 is automatic: `UnpitchedPercussion.__init__` hard-codes `midiChannel = 9`
(`music21/instrument.py:1126`) and `autoAssignMidiChannel` short-circuits to 9 (`:299`).

## Metadata, barlines, layout, style

```python
md = metadata.Metadata()
md.title = 'T'; md.composer = 'C'; md.copyright = '© X'
md.movementName = 'mvt'; md.movementNumber = '1'; md.opusNumber = '27'
md.alternativeTitle = 'alt'; md.localeOfComposition = 'Vienna'
md.lyricist = 'L'; md.librettist = 'Lb'; md.dateCreated = '1799/01/01'
md.addContributor(metadata.Contributor(role='arranger', name='A. Arranger'))
md.addCustom('myKey', 'myValue')          # md.getCustom('myKey') -> (<Text myValue>,)
sc.insert(0, md)                          # MUST be at offset 0 or it is dropped
# md.composers -> ('C',)   md.bestTitle -> 'T'
# md.contributors -> [('composer','C'),('lyricist','L'),('librettist','Lb'),
#                     ('arranger','A. Arranger')]
```

MusicXML mapping: `title`→`<work-title>`, `movementName`→`<movement-title>`, every
contributor→`<creator>`, `copyright`→`<rights>`. **None of it reaches MIDI** — a MIDI file
from a titled Score contains only per-track `SEQUENCE_TRACK_NAME = b'Flute'`.

```python
ms[0].leftBarline  = bar.Repeat(direction='start')
ms[1].rightBarline = bar.Repeat(direction='end', times=2)
ms[2].rightBarline = bar.Barline('final')
```
```xml
<barline location="left"><repeat direction="forward"/></barline>
<barline location="right"><repeat direction="backward" times="2"/></barline>
<barline location="right"><bar-style>light-heavy</bar-style></barline>
```

`bar.barTypeList` (`music21/bar.py:33`) is the real set of `type` values: `regular, dotted,
dashed, heavy, double, final, heavy-light, heavy-heavy, tick, short, none`.
`Barline.validStyles` is only `['light-light','light-heavy']` — the two *MusicXML* synonyms,
which `standardizeBarType` maps to `double` and `final`. Repeats export with no
`<bar-style>`; readers infer it.

Layout objects (`music21/layout.py`) are all `Music21Object`s you `insert` into a Score or
Measure: `ScoreLayout(scalingMillimeters=, scalingTenths=)` `:128`,
`PageLayout(pageNumber=, pageHeight=, pageWidth=, leftMargin=, isNew=)` `:205`,
`SystemLayout(leftMargin=, distance=, isNew=)` `:256`,
`StaffLayout(distance=, staffNumber=, staffSize=, staffLines=, hidden=)` `:298`.
They are MusicXML-only hints; nothing else reads them.

Per-object appearance goes through `.style` (a `NoteStyle`, `TextStyle`, … per class):

```python
n.style.color = 'red'; n.style.absoluteY = 20
n.notehead = 'diamond'; n.stemDirection = 'up'
```
```xml
<stem>up</stem><notehead color="#FF0000" parentheses="no">diamond</notehead>
```

## Variants, editorial, tablature

`variant.Variant` (`music21/variant.py:52`) is a container inserted at an offset holding
the alternate reading; `Stream.activateVariants(group=…)` (`base.py:11780`) swaps it in and
pushes the original out as a new Variant, so the operation is reversible:

```python
v = variant.Variant(); v.groups = ['ossia']
v.append(measure_with_alternate_notes)
part.insert(4.0, v)
part.activateVariants(group='ossia')   # C4,C4 -> C4,E4
```

`variant.addVariant`, `mergeVariantScores`, `mergePartAsOssia` and `refineVariant` build
them from a second Stream. `Editorial` (`music21/editorial.py:46`) is a dict on every
`Music21Object` with pre-made `comments` / `footnotes` lists of `editorial.Comment`; any
other key you set just lives there —
`n.editorial.myFlag = True` → `{'comments': […], 'footnotes': [], 'myFlag': True}`.

`text.TextBox(content, x, y)` (`music21/text.py:246`) is free-floating page text (programme
notes, headings) inserted into a Score. `tablature.FretNote(string=, fret=, fingering=)` and
`GuitarFretBoard` / `UkeleleFretBoard` / `BassGuitarFretBoard` / `MandolinFretBoard`
(`music21/tablature.py:32, 303`) model chord diagrams; `ChordWithFretBoard` (`:264`) pairs a
`ChordSymbol` with one. Pair a tab staff with `clef.TabClef()`.

## Gotchas

1. **`atSoundingPitch` defaults to `'unknown'`, and that makes MusicXML and MIDI disagree.**
   With the default, MusicXML writes your notes as *written* pitch plus a `<transpose>`
   element while MIDI plays them as *sounding* pitch. For a B♭ clarinet the two exports
   differ by a whole tone. Set `score.atSoundingPitch = True` (or `False`) on every Score.
2. **`toWrittenPitch()`/`toSoundingPitch()` are silent no-ops when the flag is `'unknown'`
   — and they still set the flag afterwards.** So the call *looks* like it worked and you
   now have a score mislabelled as written pitch. Verify a pitch changed, not the flag.
3. **Only 9 of 116 instruments have a `highestNote`; 71 have no range at all.** `—` in the
   table means "music21 has no data", never "unlimited". Any upper-range check must come
   from outside the library.
4. **`lowestNote`/`highestNote` are written pitch, `stringPitches` are sounding pitch.** The
   `Contrabass` docstring says so explicitly (`music21/instrument.py:588-590`):
   `lowestNote='E2'` but `stringPitches=['E1','A1','D2','G2']`. Never compare them directly.
5. **`Guitar` and `ElectricBass` have `transposition = None` even though real guitar and
   bass notation sounds an octave below the printed staff.** Their `lowestNote` is the
   *sounding* low string. `Contrabass` and `Banjo` *do* set `P-8`. `Contrabassoon` sets
   none, though it sounds an octave down. If you build a guitar part with the octave
   convention, music21 will not transpose it for you.
6. **`Part.id` is not the MusicXML part id** — `Instrument.partId` is; if unset the exporter
   assigns a random MD5 and diffs churn on every write. And **`Part.partName` is cached**,
   so renaming an instrument already inside the Part does nothing until
   `part.coreElementsChanged()`.
8. **Two `Part`s in a `StaffGroup` are two MusicXML parts.** A grand staff needs
   `stream.PartStaff`, ≥2 of them, one StaffGroup, and Measures already made — all four.
9. **`clef.bestClef` ignores the instrument and does not recurse by default.** On a Part of
   Measures without `recurse=True` you get `TrebleClef` for everything; even with it, a
   viola gets treble clef. Set clefs explicitly.
10. **`makeBeams` silently produces nothing when it cannot find a TimeSignature.** Pass
    `failOnNoTimeSignature=True` while developing.
11. **`makeMeasures` never fills an incomplete final measure** and never pads the start.
    Use `makeRests(refStreamOrTimeRange=[0, total])` and `padAsAnacrusis()`.
12. **`Part.makeAccidentals(inPlace=True)` leaves `streamStatus.accidentals` `False`,**
    because it passes a `StreamIterator` and the flag is only set for a `Stream`
    (`makeNotation.py:1737`). Harmless — the exporter just redoes the work — but do not
    test that flag to decide whether accidentals were made.
13. **`instrument.fromString` overwrites `instrumentName` with your entire input string,**
    junk included: `fromString('I <3 music saxofono tenore go beavers').instrumentName` is
    that whole sentence. Reset it after.
14. **`partitionByInstrument` matches on the `instrumentName` *string*, not the class,** so
    two `Clarinet()`s with different names split into two parts and two differently-classed
    instruments sharing a name merge into one.
15. **`instrumentFromMidiProgram` is lossy.** Programs 80–103 and 118–127 all return
    `Sampler`; 44/45/48–51 return bare `StringInstrument` with no range and no name worth
    printing.
16. **Metadata never reaches MIDI** — title, composer and copyright exist only in MusicXML;
    the only text in a MIDI file is the per-track instrument name. And **`Metadata` must be
    inserted at offset 0 of the Score**, or the exporter drops it entirely.
17. **MusicXML `<midi-program>` and `<midi-unpitched>` are 1-indexed; music21's
    `midiProgram` and `percMapPitch` are 0-indexed.** Off-by-one silently changes the sound.
