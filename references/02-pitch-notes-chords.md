# Pitch, Notes, Chords, and Rhythm Atoms

Everything an agent needs to place a *specific sound* at a *specific loudness* with a *specific spelling*.
Covers `Pitch`/`Accidental`/`Microtone`, `Note`/`Rest`/`Unpitched`, `Chord`, `Volume`, `Tie`, `Beams`, grace durations.
Every claim below was executed on **music21 10.5.0** (current PyPI stable); source citations point at git HEAD (v11.0.0b8).
Read this before writing any note-generating loop: three of the traps here (int-chord cost, grace-note silence,
offset-0 pitch-bend cancellation) silently destroy output rather than raising.

Verification helper used throughout — paste it once, all MIDI examples depend on it:

```python
from music21.midi import ChannelVoiceMessages as CVM
from music21.midi import translate as mt

def midi_events(s, types=(CVM.NOTE_ON, CVM.NOTE_OFF)):
    """(absolute_tick, MidiEvent) for a Stream. 10080 ticks == 1 quarter."""
    out = []
    for tr in mt.streamHierarchyToMidiTracks(s):
        t = 0
        for e in tr.events:
            if e.isDeltaTime():
                t += e.time
                continue
            if e.type in types:
                out.append((t, e))
    return out

def velocities(s):
    return [e.velocity for _, e in midi_events(s, (CVM.NOTE_ON,)) if e.velocity > 0]
```

`e.type` is an `IntEnum`; compare with `e.type == CVM.NOTE_ON`, never `str(e.type) == 'NOTE_ON'`
(Python ≥3.11 `str()` on an `IntEnum` gives the integer).

## Constructing notes and chords, and what each form costs

Every construction form, all verified:

```python
from music21 import note, chord, pitch

note.Note('C#4')                     # <music21.note.Note C#>   name+octave string
note.Note(61)                        # int == MIDI number, spelling INFERRED (C#4)
note.Note(pitch.Pitch('C#4'))        # from a Pitch (reference is shared, not copied)
note.Note('C#', octave=4)            # split form
note.Note('C#4', quarterLength=1.5)  # -> 'C-sharp in octave 4 Dotted Quarter Note'
note.Note('C~4')                     # quarter-tone; see Microtonality
note.Note()                          # defaults: C4, quarterLength 1.0

chord.Chord('C4 E4 G4')                              # space-separated string  (FASTEST)
chord.Chord(['C4', 'E4', 'G4'])                      # list of strings
chord.Chord([60, 64, 67])                            # list of ints  (PATHOLOGICALLY SLOW)
chord.Chord([pitch.Pitch('C4'), pitch.Pitch('E4')])  # list of Pitch
chord.Chord([note.Note('C4'), note.Note('E4')])      # list of Note (Notes are NOT copied)
chord.Chord('C E G').pitches
# (<Pitch C>, <Pitch E>, <Pitch G>)   -- no octave; implicitOctave 4 is used for sound
```

`Note(60.5)` does **not** raise — it silently becomes `C~` (quarter-sharp), because the float goes to `.ps`.

Benchmark, 10.5.0, Python 3.14, Apple silicon, `timeit`, µs per construction:

| form | µs/op |
|---|---|
| `pitch.Pitch('C4')` | 0.94 |
| `pitch.Pitch(60)` | 1.18 |
| `note.Note(P)` (pre-built Pitch reused) | 1.77 |
| `note.Note('C4')` | 2.85 |
| `note.Note(60)` | 3.24 |
| `chord.Chord([Note, Note, Note])` | 9.97 |
| `chord.Chord('C4 E4 G4')` | 12.83 |
| `chord.Chord([Pitch, Pitch, Pitch])` | 15.93 |
| **`chord.Chord([60, 64, 67])`** | **958** |
| **`chord.Chord([60, 64, 67, 70])`** | **5310** |
| `chord.Chord([60, 63, 67, 70, 74])` | 2296 |

The int-chord cliff is not noise. `Chord.__init__` runs `self.simplifyEnharmonics(inPlace=True)` when
**all** members are `int` (`music21/chord/__init__.py:763-764`), which calls
`pitch.simplifyMultipleEnharmonics` → a brute-force product over every common enharmonic of every pitch
for fewer than five pitches (`music21/pitch.py:610`, `music21/pitch.py:704`). Four pitches is the worst
case; five and up switches to a greedy search and gets *faster*.

You do get better spelling for the cost:

```python
chord.Chord([61, 65, 68]).pitches                                   # (C#4, E#4, G#4)  -- a real triad
chord.Chord([pitch.Pitch(midi=x) for x in (61, 65, 68)]).pitches    # (C#4, F4,  G#4)  -- raw inference
```

**Rule for bulk generation:** build strings (`'C4 E4 G4'`) or pre-built `Pitch`/`Note` objects, never int
lists, and call `.simplifyEnharmonics()` yourself only where spelling actually matters. Reusing one
`Pitch` object across notes is the cheapest of all, but the `Note` holds a *reference* — mutate it and every
note changes; `copy.deepcopy` or a fresh `Pitch` per note if you will mutate.

## Pitch: the number line and the spelling, kept separate

A `Pitch` carries two independent things: a *sounding position* (`ps`, `midi`, `frequency`) and a
*written identity* (`step` + `accidental` + `octave`).

```python
p = pitch.Pitch('E-5')
p.ps, p.midi, p.name, p.nameWithOctave, p.step, p.octave, p.alter, p.pitchClass, p.diatonicNoteNum
# 75.0, 75, 'E-', 'E-5', 'E', 5, -1.0, 3, 38
round(p.frequency, 3)   # 622.254
```

- `.ps` is a float (pitch space); `.midi` is `.ps` rounded **up at .5** via a deliberate
  `math.floor(x + 0.5)`, then clamped into 0–127 by octave transposition (`music21/pitch.py:2721-2740`) —
  `.midi = -10` gives 2, not 0.
- `.pitchClass` is `int` 0–11; `.pitchClassString` uses `'A'`/`'B'` for 10/11.
- `.diatonicNoteNum` counts *staff lines*: `C#4`→29 vs `D-4`→30 even though both are MIDI 61.
- `.frequency` is live in both directions; setting it creates a `Microtone` (see below).

`octave=None` means "unspecified", not "octave 0":

```python
q = pitch.Pitch('C')
q.octave, q.implicitOctave, q.ps, q.nameWithOctave, str(q)
# None, 4, 60.0, 'C', 'C'
```

`.implicitOctave` (default 4) is what `.ps`, `.midi`, `.frequency` and MIDI export actually use, so an
octave-less chord sounds in octave 4. `.nameWithOctave` omits the octave, so round-tripping through it
loses nothing but also fixes nothing.

Comparison is **not a total order** (`music21/pitch.py:2089-2136`, whose own docstring says
"Do not rely on this behavior"):

```python
pitch.Pitch('C#4') == pitch.Pitch('D-4')   # False  -- equality is name+octave
pitch.Pitch('C#4') <  pitch.Pitch('D-4')   # False  -- ordering is .ps only
pitch.Pitch('C#4') >  pitch.Pitch('D-4')   # False  -- neither <, nor >, nor ==
pitch.Pitch('C#4').isEnharmonic(pitch.Pitch('D-4'))   # True
```

`sorted()` is stable, so equal-`ps` pitches keep insertion order. Sort deterministically with
`key=lambda p: (p.ps, p.diatonicNoteNum)`.

`.transpose(x)` takes an int (semitones) or an interval name (`'m3'`, `'P5'`, `'A4'`), returns a new
`Pitch`, and accepts `inPlace=True`. `Note.transpose` mirrors it. `transposeBelowTarget` /
`transposeAboveTarget` fold a pitch into a register — useful for keeping a line inside an instrument's range.

## Accidentals and display control

```python
a = pitch.Accidental('half-sharp')
a.name, a.alter, a.modifier, a.unicode, a.isTwelveTone(), a.displayType, a.displayStatus
# 'half-sharp', 0.5, '~', '𝄲', False, 'normal', None

pitch.Accidental.listNames()
# ['double-flat', 'double-sharp', 'flat', 'half-flat', 'half-sharp', 'natural',
#  'one-and-a-half-flat', 'one-and-a-half-sharp', 'quadruple-flat', 'quadruple-sharp',
#  'sharp', 'triple-flat', 'triple-sharp']
```

`Accidental.set` accepts a wide alias set (`music21/pitch.py:1175-1294`): names, ASCII modifiers
(`'#'`, `'-'`, `'##'`, `'~'`, `` '`' ``, `'#~'`, `` '-`' ``), LilyPond German (`'is'`, `'es'`, `'isis'`,
`'ih'`, `'eh'`), and numeric `.alter` values including `0.5`/`-1.5`. Non-standard values need
`allowNonStandardValue=True`.

Two orthogonal display attributes: `.displayStatus` is tri-state `None`/`True`/`False` and decides whether
a glyph is actually printed (`None` = "not yet decided"); `.displayType` is the *policy* consulted by
`makeAccidentals` — `'normal'`, `'always'`, `'never'`, `'unless-repeated'`, `'even-tied'`,
`'if-absolutely-necessary'`.

```python
m = stream.Measure([key.KeySignature(2), note.Note('C#4'), note.Note('C#4'), note.Note('C4')])
m.makeAccidentals(inPlace=True)
[(n.nameWithOctave, n.pitch.accidental.displayStatus) for n in m.notes]
# [('C#4', False), ('C#4', False), ('C4', True)]
```

In D major the C♯s are covered by the key signature (`displayStatus False`) and the C natural must be
shown. If you never call `makeAccidentals`/`makeNotation`, `displayStatus` stays `None` and exporters
apply their own defaults — usually printing every accidental. Force a courtesy accidental with
`n.pitch.accidental.displayType = 'always'`.

## Enharmonic spelling: matters for notation and analysis, invisible to MIDI

Spelling changes `.name`, `.step`, `.diatonicNoteNum`, every interval computed from the pitch, and hence
every chord-quality answer. It changes nothing about the sound:

```python
for nm in ('C#4', 'D-4', 'B##3'):
    velocities(stream.Stream([note.Note(nm)]))   # all produce MIDI pitch 61
```

The most common way an agent produces wrong-looking (and wrong-*analyzing*) music is transposing by
semitone count instead of by interval name:

```python
root = pitch.Pitch('D3')
chord.Chord([root.transpose(i) for i in (0, 3, 6)])
# <Chord D3 F3 G#3>   commonName: 'enharmonic equivalent to diminished triad'
chord.Chord([root.transpose(i) for i in ('P1', 'm3', 'd5')])
# <Chord D3 F3 A-3>   commonName: 'diminished triad'
```

Same three MIDI notes; only the second one is a chord music21 can reason about. **Build harmony with
interval names.**

Reading and forcing spellings:

```python
pitch.Pitch('C#4').getEnharmonic()                # D-4          (default = "up")
pitch.Pitch('C#4').getHigherEnharmonic()          # D-4
pitch.Pitch('C#4').getLowerEnharmonic()           # B##3
pitch.Pitch('C#4').getAllCommonEnharmonics()      # [D-4, B##3]
pitch.Pitch('C#4').getAllCommonEnharmonics(alterLimit=1)   # [D-4]
pitch.Pitch('G##4').simplifyEnharmonic(mostCommon=True)    # A4
pitch.Pitch('E#4').simplifyEnharmonic()                    # F4

pitch.simplifyMultipleEnharmonics([1, 5, 8])
# [C#, E#, G#]
pitch.simplifyMultipleEnharmonics([1, 5, 8], keyContext=key.Key('A-'))
# [D-, F, A-]
```

`simplifyEnharmonic()` alone only respells double-accidentals and B#/E#/C-/F-; `mostCommon=True` also
normalizes to the flat/sharp a tonal reader expects. `simplifyMultipleEnharmonics` minimizes a dissonance
score over the whole set — always give it a `keyContext` when you have one.

To force a spelling, assign the `Pitch` or the `.name`; both keep the sound:

```python
n = note.Note(61)                       # C#4 (spellingIsInferred True)
n.pitch = pitch.Pitch('D-4')            # D-4, midi still 61
n2 = note.Note(); n2.pitch.ps = 61; n2.pitch.name = 'D-'   # D-4
```

`.spellingIsInferred` is `True` for any pitch built from a number and `False` for one built from a string.
Analysis routines and `makeAccidentals` respect it, so a chord built from ints will be respelled behind
your back by things that would leave a string-built chord alone.

## Microtonality

Three independent mechanisms, and they stack (`Pitch.alter` is accidental-alter + microtone-alter,
`music21/pitch.py:2409-2435`).

**1. Quarter-tone accidentals** — ASCII shortcuts `~` (half-sharp), `` ` `` (half-flat), `#~`
(one-and-a-half-sharp), `` -` `` (one-and-a-half-flat):

```python
p = pitch.Pitch('C~4')
p.ps, p.midi, p.alter, p.getCentShiftFromMidi(), p.isTwelveTone(), round(p.frequency, 3)
# 60.5, 61, 0.5, -50, False, 269.292
```

`.midi` rounds **up**: C~4 (ps 60.5) reports MIDI 61, so the correcting cent shift is −50.

**2. `Microtone`, arbitrary cents** — assign an int/float (cents) or a string.
**3. Frequency**, which derives the nearest twelve/quarter-tone pitch plus a residual microtone:

```python
p2 = pitch.Pitch('A4'); p2.microtone = 33
p2, p2.ps, p2.microtone.cents, p2.getCentShiftFromMidi(), round(p2.frequency, 4)
# A4(+33c), 69.33, 33, 33, 448.4675
pitch.Microtone('(-33c)').cents      # -33.0
pitch.Microtone(0.5).cents           # 0.5   -- floats are CENTS, not semitones

p3 = pitch.Pitch('A4'); p3.frequency = 452.0
p3, p3.microtone, round(p3.ps, 4)     # A~4(-3c), (-3c), 69.4658
pitch.Pitch('A4').getHarmonic(3)      # E6(+2c)

# convert freely between the two representations
pitch.Pitch('G#~4').convertQuarterTonesToMicrotones()   # G#4(+50c)
r = pitch.Pitch('A4'); r.microtone = -50
r.convertMicrotonesToQuarterTones()                     # A`4
```

Use quarter-tone **accidentals** for anything that must be notated (they export as MusicXML
`<accidental>quarter-sharp</accidental>` with `<alter>0.5</alter>`); use **`Microtone`** for anything that
only has to sound right.

### Microtones DO survive MIDI export — as pitch bend, with three hard limits

Contrary to the usual assumption, music21 emits pitch bend. `noteToMidiEvents` sets
`me1.centShift = n.pitch.getCentShiftFromMidi()` whenever `not n.pitch.isTwelveTone()`
(`music21/midi/translate.py:544-545`), and `assignPacketsToChannels` turns that into a `PITCH_BEND`
before the note-on and a reset after the note-off (`music21/midi/translate.py:1654-1665`, `1553-1569`).
Overlapping microtonal notes are pushed onto separate channels automatically. Verified:

```python
s = stream.Stream(); s.append(note.Rest()); s.append(note.Note('C~4'))
for t, e in midi_events(s, (CVM.NOTE_ON, CVM.NOTE_OFF, CVM.PITCH_BEND)):
    print(t, e)
# 0      PITCH_BEND ch=1 p1=0 p2=64     <- track init, neutral
# 10080  PITCH_BEND ch=1 p1=0 p2=48     <- -50 cents
# 10080  NOTE_ON    ch=1 pitch=61
# 20160  NOTE_OFF   ch=1 pitch=61
# 20160  PITCH_BEND ch=1 p1=0 p2=64     <- reset
```

**Limit 1 — bend range.** `MidiEvent.setPitchBend(cents, bendRange=2)` assumes the General MIDI default
of ±2 semitones (`music21/midi/base.py:641`, `:722`) and clamps beyond ±200 cents. music21 never emits
the RPN 0 messages that would set a different range, so a synth configured for ±12 semitones plays your
quarter tone six times too flat. Leave the target at the GM default, or inject RPN 0 yourself.

**Limit 2 — offset 0 is broken.** The per-track neutral bend is appended at offset 0 *after* the loop
(`music21/midi/translate.py:1699-1715`) and the final sort is stable, so at tick 0 it lands *after* the
note's own bend and *before* its note-on, cancelling it. Verified on a real written file:

```python
s = stream.Stream(); s.append(note.Note('C~4')); s.append(note.Note('D`4'))
s.write('midi', fp='/tmp/o0.mid')
# t=0      PITCH_BEND p2=48   (-50 cents)
# t=0      PITCH_BEND p2=64   (0 cents)   <-- cancels the line above
# t=0      NOTE_ON pitch=61              <-- sounds as plain C#4
# t=10080  PITCH_BEND p2=64
# t=10080  PITCH_BEND p2=48   (-50)      <-- second note is fine
# t=10080  NOTE_ON pitch=62
```

Workaround: never start a microtonal note at offset 0 of a part. Pad with a short rest, or start the part
one tick later, or post-process the `MidiFile` to delete the stray neutral bend.

**Limit 3 — no round trip.** `converter.parse()` of that file returns `['C#4', 'D4']`: the MIDI reader
ignores pitch bend entirely. Microtones are write-only through MIDI. MusicXML preserves them exactly.

## Velocity: every place it can be set, and who wins

**The one line that decides everything:** `music21/midi/translate.py:552`

```python
me1.velocity = int(round(n.volume.cachedRealized * 127))
```

MIDI velocity is `Volume.cachedRealized × 127`, nothing else. `cachedRealized` is the memoized result of
`Volume.getRealized()` (`music21/volume.py:165-296`), and `prepareStreamForMidi` calls
`volume.realizeVolume(part)` on every part right before export (`music21/midi/translate.py:2311`, `:2317`),
so at write time it is always fresh. `getRealized` is:

```
val = 0.5                                                  # baseLevel
if velocityScalar is not None:
    if velocityIsRelative:  val = 0.5 * (velocityScalar * 2)   # == velocityScalar
    else:                   val = velocityScalar               # absolute, stops here
else:
    val += 0.20866                                         # -> 0.70866 -> velocity 90
if velocityIsRelative:
    if a Dynamic is in context:  val *= dynamic.volumeScalar * 2
    for a in note.articulations:  val += a.volumeShift
clip val to [0, 1]
```

Verified precedence table (velocity of the emitted NOTE_ON):

| setup | velocity |
|---|---|
| nothing set | **90** (the 0.70866 default) |
| `n.volume.velocity = 100`, no dynamic | 100 |
| `n.volume.velocity = 100` + `Dynamic('pp')` | **50** — the dynamic rescaled it |
| same + `n.volume.velocityIsRelative = False` | **100** — velocity wins exactly |
| `Dynamic('ppp'/'pp'/'p'/'mp')` alone | 27 / 45 / 63 / 81 |
| `Dynamic('mf'/'f'/'ff'/'fff')` alone | 99 / **126 / 127 / 127** |
| `velocity=64` + `Accent()` | 77 |
| `velocity=64` + `Accent()` + `velocityIsRelative=False` | **64** — accent ignored |

Two things to internalize:

1. **`velocityIsRelative` is the switch, not a precedence order.** Default `True` means velocity is a
   *modifier* that dynamics and articulations then scale. Set it `False` and the number you wrote is the
   byte that ships — dynamics and articulations become decorative. For an agent that computes dynamics
   itself, set `velocityIsRelative = False` on every note and treat `Dynamic` objects as notation only.
2. **`ff` and `fff` are the same MIDI velocity (127), and `f` is 126.** Anything above *forte* is
   indistinguishable in a dynamics-driven export. If you need audible gradation at the top, set velocities
   explicitly.

Ways to set it, all equivalent at the byte level:

```python
n.volume.velocity = 100          # int 0..127
n.volume.velocityScalar = 0.79   # float 0..1, stored as-is; .velocity reads back round(x*127)
n.volume = 100                   # NotRest._setVolume: >= 1 -> velocity
n.volume = 0.79                  # < 1 -> velocityScalar   (music21/note.py:1284-1291)
n.volume = volume.Volume(velocity=100, velocityIsRelative=False)
```

`n.volume = 1` sets **velocity 1**, not full scale — the `< 1` test makes 1 an integer velocity
(`n.volume = 0.99` → velocity 126). Never pass a bare `1`.

Velocity 0 emits `NOTE_ON` with velocity 0, which every device reads as a note-off: the note is silent.
All other values 1–127 round-trip exactly, in both relative and absolute mode.

**Chords.** A `Chord` has one `Volume`, and optionally one per member:

```python
c = chord.Chord('C4 E4 G4')
c.setVolumes([40, 80, 120])                 # per-member; clears the chord-level Volume
for x in c:
    x.volume.velocityIsRelative = False
velocities(stream.Stream([c]))              # [40, 80, 120]

c = chord.Chord('C4 E4 G4'); c.volume.velocity = 100        # uniform
velocities(stream.Stream([c]))                              # [100, 100, 100]
```

`chordToMidiEvents` prefers each component's own `Volume` and falls back to the chord's
(`music21/chord/__init__.py:544`; `music21/midi/translate.py:783-796`). Per-member volumes with
`velocityIsRelative=True` are still scaled by an enclosing `Dynamic` and clip at 127 — with `Dynamic('ff')`,
`[40, 80, 120]` becomes `[68, 127, 127]`. `c.volume = [..]` (a list) was removed in v8; use `setVolumes`.

**Stale cache trap.** `cachedRealized` is only refreshed by `getRealized()` or `realizeVolume()`. Going
through a `Stream` is safe; calling the low-level converter directly is not:

```python
n = note.Note('C4')
n.volume.cachedRealized          # 0.71 -- reading it caches the pre-velocity value
n.volume.velocity = 20
[e.velocity for e in mt.noteToMidiEvents(n) if e.type == CVM.NOTE_ON]   # [90]  <-- STALE
velocities(stream.Stream([n]))                                          # [20]  <-- correct
```

## Note attribute surface

```python
n = note.Note('E-5', quarterLength=1.5)
n.addLyric('Ah'); n.addLyric('2')
n.lyric                                  # 'Ah\n2'   -- newline-joined, all verses
[(l.number, l.text, l.syllabic) for l in n.lyrics]
# [(1, 'Ah', 'single'), (2, '2', 'single')]
n.lyric = 'one\ntwo'                     # a string with \n creates verses 1 and 2
n.lyric = 'be-'                          # trailing hyphen -> syllabic 'begin', text 'be'
n.lyric = None                           # clears n.lyrics to []

n.articulations += [articulations.Staccato(), articulations.Accent()]  # plain list
n.expressions.append(expressions.Trill())                              # plain list
n.stemDirection = 'up'          # 'up','down','noStem','double','unspecified','none'
n.notehead = 'diamond'          # 'normal','x','diamond','cross','triangle','slash', ...
n.noteheadParenthesis = True
n.fullName                      # 'E-flat in octave 5 Dotted Quarter Note'
n.pitches                       # (<Pitch E-5>,)  -- n.pitch IS n.pitches[0]
```

`.articulations` and `.expressions` are ordinary lists on `GeneralNote`. Articulations feed `getRealized`
via `.volumeShift` (relative mode only); expressions do not.

Duration is linked to the note and normalizes itself:

```python
n2 = note.Note('C4'); n2.quarterLength = 1.75
n2.duration.type, n2.duration.dots      # 'quarter', 2  (a double-dotted quarter)
note.Note('C4', type='half', dots=1).quarterLength    # 3.0
n3 = note.Note('C4'); n3.duration = duration.Duration(4/3)
n3.duration.tuplets, n3.quarterLength                 # (<Tuplet 3/2/half>,), 4/3

r = note.Rest(quarterLength=2)
r, r.fullName, r.pitches, hasattr(r, 'volume')
# <Rest half>, 'Half Rest', (), False        <-- Rest has NO .volume
note.Unpitched(displayName='E4').displayPitch()   # E4 -- staff position only
```

`duration.quarterLength = 0.0` yields type `'zero'` and `isGrace == False` — a zero-length note is *not* a
grace note. `Rest` is a `GeneralNote` but not a `NotRest`, so it has no `volume`, `tie`, `beams`, `notehead`
or `stemDirection`; guard with `isinstance(x, note.NotRest)`.

Beams (`music21/beam.py`) are per-note and normally produced by `makeNotation()`/`makeBeams()`; build them
by hand only to override: `b = beam.Beams(); b.fill('16th', type='start')` → `b.getTypes() ==
['start','start']`. Also `b.append('start')`, `b.setAll(...)`, `b.setByNumber(3, 'partial', direction='right')`.

## Chords: the analysis surface

```python
c = chord.Chord('C4 E4 G4 B-4')
c.root(), c.bass(), c.third, c.fifth, c.seventh
# C4, C4, E4, G4, B-4                       (root()/bass() are methods; third/fifth/seventh properties)
c.inversion(), c.inversionName(), c.inversionText(), c.quality
# 0, 7, 'Root Position', 'major'
c.commonName            # 'dominant seventh chord'
c.pitchedCommonName     # 'C-dominant seventh chord'
c.fullName              # 'Chord {C in octave 4 | E in octave 4 | G in octave 4 | B-flat in octave 4} Quarter'
c.isDominantSeventh(), c.isSeventh(), c.isMajorTriad()      # True, True, False
c.semitonesFromChordStep(3), c.semitonesFromChordStep(7)    # 4, 10
c.intervalFromChordStep(5)                                  # <Interval P5>
```

`.quality` reports the *triad* quality (`'major'` here, from the C-E-G core) — use `.commonName` or the
`is*` predicates for the full chord: `isMajorTriad`, `isMinorTriad`, `isDiminishedTriad`,
`isAugmentedTriad`, `isDominantSeventh`, `isDiminishedSeventh`, `isHalfDiminishedSeventh`, `isConsonant`,
`isTriad`, `isSeventh`, `isNinth`, and the augmented-sixth family.

Post-tonal:

```python
c.pitchClasses, c.orderedPitchClasses     # [0, 4, 7, 10], [0, 4, 7, 10]
c.normalOrder, c.primeForm                # [4, 7, 10, 0], [0, 2, 5, 8]
c.forteClass, c.forteClassTnI             # '4-27B', '4-27'
c.intervalVector                          # [0, 1, 2, 1, 1, 1]
c.chordTablesAddress                      # ChordTableAddress(cardinality=4, forteClass=27, ...)
c.hasZRelation, c.getZRelation(), c.areZRelations(other)
c.geometricNormalForm(), c.isTranspositionallySymmetrical()
```

All pitch-class based, so spelling never affects them; backing tables in `music21/chord/tables.py`.

```python
c[0]                    # <Note C>       by index
c['E4']                 # <Note E>       by nameWithOctave  (c['E'] raises KeyError)
c[pitch.Pitch('G4')]    # <Note G>       by Pitch
c['0.pitch'], c['E4.notehead']     # C4, 'normal'   attribute access on a member
c[0].volume.velocity = 10          # mutation through the index sticks
c.pitches = [pitch.Pitch(x) for x in ('D4', 'F4', 'A4')]    # wholesale replacement
c.setTie(tie.Tie('start'), 'E4'); c.setNotehead('diamond', 'G4')   # per-member

# annotateIntervals writes lyrics onto the CHORD, not its members
[l.text for l in chord.Chord('C4 E4 G4 B-4').annotateIntervals(stripSpecifiers=False).lyrics]
# ['m7', 'P5', 'M3']       (default stripSpecifiers=True gives ['7', '5', '3'])
```

v11 narrows the accepted key types to int, nameWithOctave string, and `Pitch`
(`music21/chord/__init__.py:832`); the `'0.pitch'` attribute form still works in 10.5. A chord shares one
`Duration` across all members, so `c.quarterLength = 3` updates every member.

## Chord voicing for a composer

```python
chord.Chord('C3 E5 G6 B-7').closedPosition()                  # <Chord C3 E3 G3 B-3>
chord.Chord('C3 E5 G6 B-7').closedPosition(forceOctave=4)     # <Chord C4 E4 G4 B-4>
chord.Chord('C3 E5 G6 B-7').semiClosedPosition()              # <Chord C3 E3 G3 B-3>
```

`closedPosition` packs everything into one octave above the bass and removes redundant pitches by default
(`leaveRedundantPitches=True` keeps doublings); `semiClosedPosition` re-opens colliding pitch classes.
**There is no `openPosition` method** — `hasattr(chord.Chord, 'openPosition')` is `False`.

```python
for i in range(4):
    cc = chord.Chord('C4 E4 G4 B-4'); cc.inversion(i); print(i, cc)
# 0 <Chord C4 E4 G4 B-4> / 1 <Chord E4 G4 B-4 C5> / 2 <Chord G4 B-4 C5 E5> / 3 <Chord B-4 C5 E5 G5>

c2 = chord.Chord('C4 E4 G4 C5 E5')
c2.removeRedundantPitches()        # <Chord C4 E4 G4 C5 E5>   -- same NAME AND OCTAVE only
c2.removeRedundantPitchNames()     # <Chord C4 E4 G4>         -- same name, any octave
c2.removeRedundantPitchClasses()   # <Chord C4 E4 G4>         -- same pitch class (B#3 == C4)
```

`inversion()` with no argument *reads*; with an int it *mutates in place* and re-octaves — it needs a
findable root, so a quartal or cluster chord raises or answers nonsense. `removeRedundantPitches` will
**not** thin an octave doubling; `removeRedundantPitchClasses` collapses enharmonics
(`chord.Chord('C4 B#3').removeRedundantPitchClasses()` → `<Chord C4>`).

Building voicings from root + quality — use interval names so the spelling comes out right:

```python
QUALITIES = {'maj': ['P1', 'M3', 'P5'],      'min': ['P1', 'm3', 'P5'],
             'dim': ['P1', 'm3', 'd5'],      'aug': ['P1', 'M3', 'A5'],
             'dom7': ['P1', 'M3', 'P5', 'm7'], 'maj7': ['P1', 'M3', 'P5', 'M7'],
             'min7': ['P1', 'm3', 'P5', 'm7'], 'halfdim7': ['P1', 'm3', 'd5', 'm7'],
             'dim7': ['P1', 'm3', 'd5', 'd7']}

def build(root, quality, octave=3):
    r = pitch.Pitch(root); r.octave = octave
    return chord.Chord([r.transpose(i) for i in QUALITIES[quality]])

build('D', 'halfdim7')     # <Chord D3 F3 A-3 C4>   commonName 'half-diminished seventh chord'
build('D', 'dim7')         # <Chord D3 F3 A-3 C-4>  commonName 'diminished seventh chord'

def drop2(ch, octave=4):
    """Standard jazz drop-2: 2nd voice from the top goes down an octave."""
    ch = ch.closedPosition(forceOctave=octave)
    ps = sorted(ch.pitches, key=lambda p: p.ps)
    ps[-2].octave -= 1
    return chord.Chord(sorted(ps, key=lambda p: p.ps))

drop2(chord.Chord('C4 E4 G4 B4'))     # <Chord G3 C4 E4 B4>
```

For lead sheets, `harmony.ChordSymbol('Dm7')` parses a figure to pitches (`['D3','F3','A3','C4']`) and
`harmony.ChordSymbol(root='C', kind='minor-seventh')` takes the structured form. `'C6/9'` raises
`ValueError`; write `'C69'` — which in 10.5.0 yields only `['C3','A3','D4']`, so verify exotic figures.

## Ties

A `Tie` is a mark on a note, not a link between two notes. Valid types:
`('start', 'stop', 'continue', 'let-ring', 'continue-let-ring')` (`music21/tie.py:105`).

```python
a = note.Note('C4', quarterLength=1); a.tie = tie.Tie('start')
b = note.Note('C4', quarterLength=1); b.tie = tie.Tie('stop')
s = stream.Stream(); s.append([a, b]); midi_events(s)
# [(0, NOTE_ON pitch=60), (20160, NOTE_OFF pitch=60)]     -- ONE note, 2 quarters long

# makeTies / makeNotation is the machine-generated route: it splits at barlines and marks correctly
pt = stream.Part([meter.TimeSignature('4/4'), note.Note('C4', quarterLength=6.0)]).makeNotation()
[(n.quarterLength, n.tie) for n in pt.recurse().notes]   # [(4.0, <Tie start>), (2.0, <Tie stop>)]
midi_events(pt)
# [(0, NOTE_ON pitch=60), (60480, NOTE_OFF pitch=60)]     -- still one 6-quarter note
```

MIDI export calls `subs.stripTies(inPlace=True, matchByPitch=True)` on every part before packetizing
(`music21/midi/translate.py:2706-2707`): the tied group collapses into a single note and the note-off is
deferred to the end of the group. A tie start with **no** stop still merges into the following note.

Chord ties: setting `c.tie` marks every member; `c.setTie(tie.Tie('start'), 'E4')` marks one.
Tied chords produce one note-on and one note-off per member across the whole group.

## Grace notes

```python
g = note.Note('B4', quarterLength=1).getGrace()
g.duration          # <GraceDuration unlinked type:quarter quarterLength:0.0>
g.duration.isGrace, g.duration.type, g.duration.slash, g.quarterLength
# True, 'quarter', True, 0.0

note.Note('B4').getGrace(appoggiatura=True).duration
# <AppoggiaturaDuration unlinked type:quarter quarterLength:0.0>   (slash=False)

g2 = note.Note('E5'); g2.duration = duration.GraceDuration(0.5)    # direct construction
g.duration.stealTimePrevious = 0.5     # notational hint only; nothing consumes it on export
```

`getGrace` deep-copies the note and swaps in a `GraceDuration` whose `quarterLength` is 0 but whose `.type`
remembers the visual note value (`music21/note.py:942-996`; `music21/duration.py:3131`);
`AppoggiaturaDuration` is the unslashed variant. Grace notes occupy **zero** stream time, and are
**silent in MIDI**:

```python
s = stream.Stream()
s.append(note.Note('C5')); s.append(note.Note('B4').getGrace()); s.append(note.Note('C5'))
[(e.name, s.elementOffset(e), e.quarterLength) for e in s.notes]
# [('C', 0.0, 1.0), ('B', 1.0, 0.0), ('C', 1.0, 1.0)]   -- grace shares offset 1.0; highestTime 2.0

for t, e in midi_events(s): print(t, e)
# 0      NOTE_ON  pitch=72
# 10080  NOTE_OFF pitch=72
# 10080  NOTE_OFF pitch=71      <-- grace note-off ...
# 10080  NOTE_ON  pitch=71      <-- ... emitted BEFORE its note-on, same tick
# 10080  NOTE_ON  pitch=72
# 20160  NOTE_OFF pitch=72
```

Zero delta-time between on and off, and the off sorts first. Synths drop this. MusicXML is fine
(`<grace slash="yes"/>` is written correctly), so: graces are for *notation* only.

Workaround for audible ornaments — realize them before export, on a copy (verified: the grace above
becomes NOTE_ON at 10080, NOTE_OFF at 11340):

```python
def realize_graces(part, steal=0.125):
    """Give each grace real time by stealing from the following note."""
    for g in list(part.recurse().notes):
        if not g.duration.isGrace:
            continue
        nxt = g.next('GeneralNote')
        if nxt is None or nxt.quarterLength <= steal:
            continue
        off = part.elementOffset(g)
        part.remove(g, recurse=True)
        g.duration = duration.Duration(steal)
        nxt.quarterLength -= steal
        part.insert(off, g)
        part.setElementOffset(nxt, off + steal)
```

Keep the grace version for `show()`/MusicXML and the realized version for `write('midi')`.

## Gotchas

Each verified on music21 10.5.0.

- **`chord.Chord([60, 64, 67])` costs ~960 µs, the four-note case ~5300 µs — up to 400× a string chord**,
  because `Chord.__init__` runs a brute-force enharmonic search for all-int input
  (`music21/chord/__init__.py:763`). In bulk, use strings or pre-built `Pitch`/`Note` lists.
- **`n.volume = 1` sets velocity 1, not maximum.** The numeric setter treats `< 1` as a scalar and `>= 1`
  as a velocity (`music21/note.py:1284-1291`); `n.volume = 0.99` → velocity 126.
- **A `Dynamic` in context silently rescales an explicit velocity** — `velocity=100` under `Dynamic('pp')`
  ships as 50. Set `velocityIsRelative = False` on every note whose velocity you computed yourself.
- **`f`, `ff`, `fff` clip at 126, 127, 127.** Dynamics alone cannot gradate above forte in MIDI.
- **Velocity 0 emits `NOTE_ON` velocity 0 — a note-off. The note is silent.** Use 1 as your floor.
- **A microtonal note starting at offset 0 loses its pitch bend**: the per-track neutral bend appended at
  offset 0 (`music21/midi/translate.py:1699-1715`) sorts after the note's own bend and cancels it. Pad
  the start of the part with a rest.
- **music21 assumes a ±2-semitone bend range and never sends RPN 0** (`music21/midi/base.py:641`); on a
  synth set to any other range, every microtone is wrong by that ratio.
- **Microtones do not survive a MIDI round trip** — `converter.parse()` ignores pitch bend and `C~4` comes
  back as `C#4`. MusicXML preserves `<alter>0.5</alter>` exactly.
- **Grace notes are inaudible in MIDI**: note-on and note-off share a tick and the off is emitted first.
  Realize them into real durations before `write('midi')`.
- **A tie between two *different* pitches silently deletes the second note.** `stripTies` merges the pair
  into the first pitch regardless of `matchByPitch`, so `C4~D4` exports as a 2-quarter C4.
- **`Pitch` comparison is not a total order**: `C#4 == D-4`, `C#4 < D-4` and `C#4 > D-4` are all `False`.
  Sort with `key=lambda p: (p.ps, p.diatonicNoteNum)`.
- **There is no `Chord.openPosition`** — only `closedPosition` and `semiClosedPosition`.
- **`removeRedundantPitches` does not remove octave doublings**, only exact name+octave duplicates. You
  usually want `removeRedundantPitchNames` or `removeRedundantPitchClasses`.
- **Transposing by semitone count breaks spelling and therefore analysis**: `D3.transpose(6)` → `G#3`,
  demoting a diminished triad to "enharmonic equivalent to diminished triad". Use interval names.
- **`note.Note(60.5)` does not raise** — it becomes a quarter-sharp `C~`, because the float lands on `.ps`.
- **`mt.noteToMidiEvents(n)` on a bare note can use a stale `cachedRealized`**: reading it before setting
  `velocity` freezes the old value. Only `getRealized()`, `realizeVolume()` or a `Stream` refreshes it.
- **`Rest` has no `.volume`, `.tie`, `.beams`, `.notehead` or `.stemDirection`** — it is a `GeneralNote`,
  not a `NotRest`. Guard with `isinstance(x, note.NotRest)`.
- **`accidental.displayStatus` stays `None` until `makeAccidentals`/`makeNotation` runs**, after which
  exporters guess — usually printing every accidental. Call `makeNotation()` before writing notation.
- **Octave-less pitches sound in octave 4** (`Pitch('C').octave is None` but `.ps == 60.0`). Set octaves
  explicitly for anything that must land in a given register.
- **`note.Note(pitch_obj)` shares the `Pitch`, it does not copy it.** Fastest construction path, but every
  mutation is global; deep-copy if you will mutate.
- **`e.type` on a `MidiEvent` is an `IntEnum`**, so `str(e.type)` is the integer under Python ≥3.11.
  Compare against `ChannelVoiceMessages.NOTE_ON`.
