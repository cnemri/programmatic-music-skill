# Pitch Relationships, Harmony & Theory Generation

Everything about *which pitches* to write: intervals, keys, scales (Western, modal, maqam,
raga, microtonal, invented), Roman numerals in both directions, chord symbols, figured-bass
realization, voice-leading checking, and post-tonal machinery (rows, set classes, sieves).
You cannot hear the result, so every example below was executed on music21 **10.5.0** and the
printed output is real. Anything marked `[v11]` was read at git HEAD but not run.

---

## 1. Intervals

`Interval` is the atom. Three orthogonal views: `GenericInterval` (staff distance only),
`ChromaticInterval` (semitones only), `DiatonicInterval` (generic + specifier). `Interval`
carries all three. `GenericInterval` has **no** `.semitones` — that is the point of it.

```python
from music21 import interval, pitch, note

i = interval.Interval('m3')
i.name, i.directedName, i.semitones, i.niceName   # 'm3' 'm3' 3 'Minor Third'

i2 = interval.Interval(noteStart=note.Note('C4'), noteEnd=note.Note('E-5'))
i2.name, i2.semitones      # 'm10', 15
i2.generic, i2.chromatic   # <GenericInterval 10>, <ChromaticInterval 15>

interval.Interval(pitch.Pitch('C4'), pitch.Pitch('G4'))   # <Interval P5>  positional = start,end
interval.Interval(6).name                                 # 'd5'   int arg == semitones
i.transposePitch(pitch.Pitch('C#4'))                      # <Pitch E4>
interval.add(['M3', 'm3'])                                # <Interval P5>
interval.subtract(['P5', 'M3'])                           # <Interval m3>
interval.Interval('M3').complement                        # <Interval m6>
interval.Interval('M3').reverse()                         # <Interval M-3>
interval.intervalFromGenericAndChromatic(3, 4)            # <Interval M3>
interval.ChromaticInterval(6).getDiatonic()               # <DiatonicInterval d5>

# transposePitch caps accidentals at 4; force respelling with maxAccidental
interval.Interval('A5').transposePitch(pitch.Pitch('F#4'))                     # C##5
interval.Interval('A5').transposePitch(pitch.Pitch('B#4'), maxAccidental=1)    # G#5
interval.Interval('A5').transposePitch(pitch.Pitch('B#4'), maxAccidental=None) # F###5
```

---

## 2. Transposing a whole Score — diatonic vs chromatic

`Stream.transpose()` accepts either, and they do different things.

**Chromatic** (an `Interval`, a string, or an int): every pitch moves the same number of
semitones and **key signatures are rewritten**.
**Diatonic / modal** (a `GenericInterval`): every pitch moves by *staff steps*, accidentals
are re-derived from the prevailing key, and **key signatures stay put** — the music moves
*within* the key. Implemented by `GenericInterval.transposePitchKeyAware`
(`music21/interval.py:1430`).

```python
from music21 import converter, key, interval

s = converter.parse('tinyNotation: 4/4 d4 e f f# g1 a-4 g b- a c1')
s.measure(1).insert(0, key.Key('G'))
s.measure(3).insert(0, key.Key('c'))

s.transpose('M2').flatten().pitches
# ['E4','F#4','G4','G#4','A4','B-4','A4','C5','B4','D4']   key sigs -> A major, d minor
s.transpose(interval.GenericInterval(2)).flatten().pitches
# ['E4','F#4','G-4','G4','A4','B-4','A-4','C5','B4','D4']  key sigs stay G major, c minor
```

`F4 -> G-4` in the diatonic case is correct: F-natural contradicts G major by one flat, so
the same contradiction is carried to the new step.

For a real score, compute the interval between tonics so the key travels with the notes:

```python
from music21 import corpus
s = corpus.parse('bach/bwv66.6')
s.analyze('key')                                                  # f# minor
i = interval.Interval(key.Key('f#').tonic, key.Key('d').tonic)    # <Interval M-3>
t = s.transpose(i)
t.analyze('key')                                                  # d minor
{str(ks) for ks in t.recurse().getElementsByClass(key.KeySignature)}   # {'d minor'}
```

`transpose()` returns a copy (`inPlace=True` to mutate), descends into every part, measure
and voice, and rewrites `KeySignature` objects for you.

---

## 3. Keys and key signatures

`Key` subclasses **both** `KeySignature` and `scale.DiatonicScale` (`music21/key.py:872`), so
a `Key` *is* a usable scale object.

```python
from music21 import key

k = key.Key('g')                          # lowercase string => minor
k.tonic, k.mode, k.sharps                 # <Pitch G>, 'minor', -2
key.Key('G'), key.Key('b-')               # G major; b- minor (sharps -5)
key.Key('D', 'dorian').sharps             # 0   -- modes supported, sig follows the mode
key.Key('e', 'phrygian').pitches          # E F G A B C D E,  sharps 0
k.relative, k.parallel                    # B- major, G major

# Key IS a scale:
[str(p) for p in k.pitches]               # ['G4','A4','B-4','C5','D5','E-5','F5','G5']
k.pitchFromDegree(7), k.getLeadingTone()  # F5 (natural minor), F#5 (raised)
k.getDominant()                           # D5
k.accidentalByStep('B'), k.alteredPitches # <Accidental flat>, [B-, E-]
key.Key('C').deriveByDegree(3, 'B-')      # <Key of G- major>  (which key has B- as degree 3?)

ks = key.KeySignature(3)
ks.alteredPitches, ks.asKey('minor')      # [F#, C#, G#], <Key of f# minor>
```

**Accidental display.** Accidentals live on `Pitch`; whether they *print* is
`accidental.displayStatus`, set by `makeAccidentals()` (also run by `makeNotation` on write).

```python
m = stream.Measure([key.KeySignature(-3), meter.TimeSignature('4/4')])   # E- major
for n in ['E-4', 'A-4', 'B-4', 'B4']:
    m.append(note.Note(n))
p = stream.Part([m]); p.makeAccidentals(inPlace=True)
# E-4 flat displayStatus False | A-4 flat False | B-4 flat False   <- covered by the sig
# B4  natural displayStatus True                                   <- cancels it, printed
```

The MusicXML then holds `<fifths>-3</fifths>` and one `<accidental>natural</accidental>`.

---

## 4. Built-in scales

Constructed as `ScaleClass(tonic)`. On C4:

| class | pitches |
|---|---|
| `MajorScale` / `MinorScale` | C D E F G A B C / C D E- F G A- B- C |
| `DorianScale` / `PhrygianScale` | C D E- F G A B- C / C D- E- F G A- B- C |
| `LydianScale` / `MixolydianScale` | C D E F# G A B C / C D E F G A B- C |
| `LocrianScale` | C D- E- F G- A- B- C |
| `HarmonicMinorScale` / `MelodicMinorScale` | C D E- F G A- B C / C D E- F G A B C (asc) |
| `WholeToneScale` | C D E F# G# A# B# |
| `ChromaticScale` | C C# D E- E F F# G A- A B- B C |
| `OctatonicScale` | C D E- F G- A- A B C |
| `Hypo{dorian,phrygian,lydian,mixolydian,locrian,aeolian}Scale` | plagal, start a 4th below |
| `RagAsawari` / `RagMarwa` | C D F G A- C (asc) / C D- E F# A B A C D- |
| `WeightedHexatonicBlues` | C E- F F# G B- C |
| `CyclicalScale(t, ['P5'])` / `OctaveRepeatingScale(t, ['m3','M3'])` | interval stacks |
| `SieveScale(t, '4@0\|4@1\|4@2')` | Xenakis sieve → scale (C C# D E) |
| `ScalaScale(t, 'pyth_12')` | any of 3935 bundled `.scl` files |

Universal `ConcreteScale` API (`music21/scale/__init__.py:1271`) — works on all of the above
*and* on anything you define in §5:

```python
sc.pitches                                  # one octave from the tonic
sc.getPitches('D2', 'D5')                   # any range
sc.getPitches('D4','D5', direction=scale.Direction.DESCENDING)
sc.pitchFromDegree(5)
sc.pitchesFromScaleDegrees([1, 3, 5])       # a triad; add 'D3','D6' for a range
sc.getScaleDegreeFromPitch('B-4')           # 6, or None if not in scale
sc.getScaleDegreeFromPitch('B-4', comparisonAttribute='name')   # ignore octave/spelling
sc.nextPitch('F#4')                                             # G4
sc.nextPitch('F#4', scale.Direction.DESCENDING)
sc.nextPitch('B-4', scale.Direction.ASCENDING, stepSize=3)      # skip 3 scale steps
sc.intervalBetweenDegrees(2, 3)             # <Interval A2>
sc.solfeg('F#4')                            # 'mi'
sc.match(['D','F#','A'])                    # {'matched': [...], 'notMatched': []}
sc.findMissing(['D','F#','A'])              # the rest of the scale
sc.transpose('P4'); sc.getDegreeMaxUnique() # new scale a 4th up; 7
```

**Melodic minor is direction-dependent, and the argument order is a trap:**

```python
mm = scale.MelodicMinorScale('a')
mm.getPitches('a4','a5', direction=scale.Direction.ASCENDING)    # A B C D E F# G# A
mm.getPitches('a4','a5', direction=scale.Direction.DESCENDING)   # A G F E D C B A  correct
mm.getPitches('a5','a4')                                         # A G# F# ...      WRONG
```

Swapping min/max reverses the *ascending* collection. Always pass
`minPitch=<low>, maxPitch=<high>, direction=Direction.DESCENDING`.

---

## 5. Custom scales — the general recipe

Three tiers, cheapest first.

### 5a. Just give it the pitches

`ConcreteScale(pitches=[...])` builds an `AbstractScale` from the intervals between
consecutive pitches (`music21/scale/__init__.py:322`). Maqam Hijaz on D — D E♭ F♯ G A B♭ C:

```python
from music21 import scale
hijaz = scale.ConcreteScale(pitches=['D4','E-4','F#4','G4','A4','B-4','C5','D5'])

hijaz.getTonic()                       # <Pitch D4>
hijaz.getPitches('D4', 'D6')
# ['D4','E-4','F#4','G4','A4','B-4','C5','D5','E-5','F#5','G5','A5','B-5','C6','D6']
hijaz.pitchFromDegree(3)               # <Pitch F#4>
hijaz.nextPitch('F#4')                 # <Pitch G4>
hijaz.nextPitch('F#4', scale.Direction.DESCENDING)   # <Pitch E-4>
hijaz.getScaleDegreeFromPitch('B-4')   # 6
hijaz.getScaleDegreeFromPitch('B4')    # None
hijaz.getDegreeMaxUnique()             # 7
hijaz.abstract.octaveDuplicating       # True
```

Always give the closing octave (`'D5'`) explicitly. Omit it and music21 infers one, setting
`octaveDuplicating` from the span — a multi-octave list silently becomes non-repeating.

### 5b. A named, reusable, transposable scale class

Subclass `AbstractScale` (the shape) + `ConcreteScale` (the tonic). Every built-in does this;
`HarmonicMinorScale` is nine lines (`music21/scale/__init__.py:3027`). Copy-pasteable:

```python
from music21 import scale

class AbstractHijaz(scale.AbstractScale):
    def __init__(self, **keywords):
        super().__init__(**keywords)
        self.type = 'Abstract Hijaz'
        self.octaveDuplicating = True
        self.buildNetwork()

    def buildNetwork(self, mode=None):
        # 1 b2 3 4 5 b6 b7 8  ->  m2 A2 m2 M2 m2 M2 M2
        self._net = scale.intervalNetwork.IntervalNetwork(
            ['m2', 'A2', 'm2', 'M2', 'm2', 'M2', 'M2'], octaveDuplicating=True)

class HijazScale(scale.ConcreteScale):
    usePitchDegreeCache = True
    def __init__(self, tonic=None, **keywords):
        super().__init__(tonic=tonic, **keywords)
        self.type = 'Hijaz'
        self._abstract = AbstractHijaz()
```

```
h = HijazScale('D4')            ->  <HijazScale D Hijaz>,  h.name == 'D Hijaz'
h.pitches                           ['D4','E-4','F#4','G4','A4','B-4','C5','D5']
h.getPitches('D2','D5')             ['D2','E-2','F#2','G2','A2','B-2','C3','D3', ... ,'D5']
h.transpose('P4').pitches           ['G4','A-4','B4','C5','D5','E-5','F5','G5']
h.pitchFromDegree(5)                <Pitch A4>
h.getScaleDegreeFromPitch('B-4')    6
h.deriveRanked(['E-','F#','A'], comparisonAttribute='name')
   [(3, <HijazScale D Hijaz>), (2, <HijazScale B Hijaz>),
    (2, <HijazScale G# Hijaz>), (2, <HijazScale F Hijaz>)]
```

`deriveRanked`, `transpose`, `nextPitch`, degrees — everything the built-ins do now works on
your maqam, and `deriveRanked` searches *your* family of scales.

### 5c. Direction-dependent scales (`fillArbitrary`)

For ragas and maqamat where ascent ≠ descent, build the network node-by-node
(`music21/scale/intervalNetwork.py:685`; `AbstractRagAsawari` at
`music21/scale/__init__.py:1033` is the model). Ascending pentatonic, descending heptatonic:

```python
from music21 import scale
from music21.scale import intervalNetwork
from music21.scale.intervalNetwork import Terminus, Direction
A, D = Direction.ASCENDING, Direction.DESCENDING

class AbstractBhairavi(scale.AbstractScale):
    """asc: 1 b3 4 5 b7 8   /   desc: 8 b7 b6 5 4 b3 b2 1"""
    def __init__(self, **keywords):
        super().__init__(**keywords)
        self.type = 'Abstract Bhairavi'
        self.octaveDuplicating = True
        self.buildNetwork()

    def buildNetwork(self, mode=None):
        self.tonicDegree = 1
        nodes = ({'id': Terminus.LOW, 'degree': 1},
                 {'id': 0, 'degree': 3}, {'id': 1, 'degree': 4},
                 {'id': 2, 'degree': 5}, {'id': 3, 'degree': 7},
                 {'id': Terminus.HIGH, 'degree': 8},
                 {'id': 4, 'degree': 7}, {'id': 5, 'degree': 6}, {'id': 6, 'degree': 5},
                 {'id': 7, 'degree': 4}, {'id': 8, 'degree': 3}, {'id': 9, 'degree': 2})
        LO, HI = Terminus.LOW, Terminus.HIGH
        edges = tuple({'interval': iv, 'connections': ([a, b, dr],)} for iv, a, b, dr in (
            # ascending  C -> Eb -> F -> G -> Bb -> C
            ('m3', LO, 0, A), ('M2', 0, 1, A), ('M2', 1, 2, A), ('m3', 2, 3, A), ('M2', 3, HI, A),
            # descending C -> Bb -> Ab -> G -> F -> Eb -> Db -> C
            ('M2', HI, 4, D), ('M2', 4, 5, D), ('m2', 5, 6, D), ('M2', 6, 7, D),
            ('M2', 7, 8, D), ('M2', 8, 9, D), ('m2', 9, LO, D)))
        self._net = intervalNetwork.IntervalNetwork(octaveDuplicating=True,
                                                    pitchSimplification=None)
        self._net.fillArbitrary(nodes, edges)

class Bhairavi(scale.ConcreteScale):
    def __init__(self, tonic=None, **keywords):
        super().__init__(tonic=tonic, **keywords)
        self.type = 'Bhairavi'
        self._abstract = AbstractBhairavi()
```

```
b = Bhairavi('C4')
b.getPitches('C4','C5', direction=A)   ['C4','E-4','F4','G4','B-4','C5']
b.getPitches('C4','C5', direction=D)   ['C5','B-4','A-4','G4','F4','E-4','D-4','C4']
b.nextPitch('F4', A)                   <Pitch G4>
b.nextPitch('A-4', D)                  <Pitch G4>
Bhairavi('D4').getPitches('D4','D5', direction=A)   ['D4','F4','G4','A4','C5','D5']
```

Node ids are `Terminus.LOW`, `Terminus.HIGH` and ints; `degree` is the scale-degree number
the node represents (repeat degrees freely on the descending branch); each edge lists
`(fromId, toId, Direction)`. `pitchSimplification` defaults to `'maxAccidental'` and will
respell — `'mostCommon'` turned `D-4` into `C#4`; pass `None` to keep your spelling.

---

## 6. Microtonal scales — Scala files (Maqam Rast and friends)

music21 ships 3935 `.scl` files in `music21/scale/scala/scl/`, and `ScalaScale` takes a file
stem **or a raw `.scl` string** (>3 newlines triggers raw parsing;
`music21/scale/__init__.py:3284`). This is the cleanest route to quarter tones.

```python
# .scl format: comment lines start with !, then a description line, then the
# note count, then one cents value (or ratio) per degree ending at the octave.
rast = '\n'.join(['! rast.scl', '!', 'Maqam Rast', ' 7', '!',
                  ' 200.0', ' 350.0', ' 500.0', ' 700.0', ' 900.0', ' 1050.0', ' 2/1', ''])
r = scale.ScalaScale('C4', rast)
r.name                       # 'C Scala: rast.scl'
[str(p) for p in r.pitches]  # ['C4','D4','E`4','F4','G4','A4','B`4','C5']
[p.ps for p in r.pitches]    # [60.0, 62.0, 63.5, 65.0, 67.0, 69.0, 70.5, 72.0]
[round(p.frequency, 2) for p in r.pitches]
#   [261.63, 293.66, 320.24, 349.23, 392.0, 440.0, 479.82, 523.25]
r.getPitches('C4','C6')      # two full octaves, quarter tones intact
r.pitchFromDegree(3)         # <Pitch E`4>    ` == half-flat
```

Bundled files need no cents at all:

```
scale.ScalaScale('C4', 'gorgo-pelog').pitches
  ['C4','C~4(+15c)','E-4(-7c)','F4(+21c)','G4(-15c)','G~4(-1c)','B-4(-22c)','C5(+6c)']
scale.ScalaScale('C4', 'kurzweil_arab').pitches       # 24-tone Arabic
  ['C4','C#~4(-20c)','D4(-20c)','D~4','E`4(+5c)','F4(+2c)','F#4(+23c)','G4(+6c)',
   'G#4(-14c)','G#~4(+7c)','A~4(-20c)','B4(+10c)','C5']
scale.ScalaScale('C4', 'slendro5_2').pitches
  ['C4','D~4(+17c)','F4(-2c)','G4(+2c)','A~4(+19c)','C5']
scale.ScalaScale('C4', 'pyth_12').pitches
  ['C4','C#4(+14c)','D4(+4c)','E-4(-6c)','E4(+8c)','F4(-2c)', ...]
```

Cents quantize to the nearest 12-TET step plus a residual `Microtone` printed as `(+15c)`;
`p.ps` and `p.frequency` stay exact. Quarter tones can also be typed directly —
`` ` `` = half-flat, `~` = half-sharp — so
`ConcreteScale(pitches=['C4','D4','E`4','F4','G4','A4','B`4','C5'])` gives the same Rast with
no Scala file. Microtones are legal throughout `ConcreteScale` networks.

`ConcreteScale.tune(stream)` retunes in place, matching on `Pitch.name`
(`music21/scale/__init__.py:1561`):

```python
p = converter.parse("tinyNotation: 4/4 c4 d e f g a b c'")
scale.ScalaScale('C4', 'pyth_12').tune(p)
# C4/60.0  D4(+4c)/62.0391  E4(+8c)/64.0782  F4(-2c)/64.9805
# G4(+2c)/67.0195  A4(+6c)/69.0587  B4(+10c)/71.0978  C5/72.0
```

**Export:** quarter tones round-trip through MusicXML intact but MIDI silently rounds them to
the nearest semitone (`E\`4` → `E4`). Microtonal MIDI needs hand-written pitch bend, one
channel per voice.

---

## 7. Generating melody from any scale

Hold a current `Pitch`, walk it with `nextPitch`, let the scale enforce membership. Identical
code for a maqam, a raga, or C major.

```python
import random
from music21 import scale, stream, note, meter, tempo
random.seed(7)

hijaz = scale.ConcreteScale(pitches=['D4','E-4','F#4','G4','A4','B-4','C5','D5'])
part = stream.Part()
part.append(tempo.MetronomeMark(number=96))
part.append(meter.TimeSignature('4/4'))

cur = hijaz.pitchFromDegree(1); cur.octave = 4
for _ in range(16):
    n = note.Note(cur)
    n.quarterLength = random.choice([0.5, 0.5, 1.0, 0.25])
    part.append(n)
    if random.random() < 0.75:                       # step
        d = scale.Direction.ASCENDING if random.random() < 0.55 else scale.Direction.DESCENDING
        cur = hijaz.nextPitch(cur, d)
    else:                                            # leap three scale steps
        cur = hijaz.nextPitch(cur, scale.Direction.ASCENDING, stepSize=3)
    if cur.ps > 79:
        cur = hijaz.pitchFromDegree(1); cur.octave = 4
part.makeMeasures(inPlace=True)

# D4/1.0 G4/0.25 A4/0.5 B-4/0.5 C5/0.5 B-4/0.5 E-5/0.5 D4/0.5
# E-4/0.5 D4/1.0 E-4/1.0 D4/0.5 C4/1.0 B-3/0.5 C4/0.25 F#4/0.25   -- all 16 verified in scale
```

`nextPitch` crosses octaves correctly and preserves the scale's spelling (`E-5`, `B-3`),
which `Pitch(ps=...)` arithmetic would not.

---

## 8. Scale matching — "what scale is this?"

`deriveRanked(pitches, resultsReturned=4, comparisonAttribute='pitchClass'|'name',
removeDuplicates=False)` returns `(matchCount, ConcreteScale)` pairs, searching every
transposition of *this object's* scale type (`music21/scale/__init__.py:2357`). Call it on an
un-tonicized instance (`scale.MajorScale()`) to search all keys. Loop over candidate classes
and take the highest count — that is the whole algorithm.

```python
s = converter.parse("tinyNotation: 4/4 d4 e- f# g a b- c' d'")
pitches = [n.pitch for n in s.flatten().notes]
for cls in (scale.MajorScale, scale.MinorScale, scale.HarmonicMinorScale,
            scale.MelodicMinorScale, scale.OctatonicScale, scale.WholeToneScale):
    print(cls().deriveRanked(pitches, comparisonAttribute='name', resultsReturned=2))
# MajorScale         [(7, B- major),          (6, G major)]
# MinorScale         [(7, G minor),           (6, E minor)]
# HarmonicMinorScale [(8, G harmonic minor),  (5, D harmonic minor)]   <- 8/8, the answer
# MelodicMinorScale  [(7, G melodic minor),   (6, C melodic minor)]
# OctatonicScale     [(5, B- Octatonic),      (5, A Octatonic)]
# WholeToneScale     [(4, B- Whole tone),     (3, B Whole tone)]

hij = scale.ConcreteScale(pitches=['D4','E-4','F#4','G4','A4','B-4','C5','D5'])
hij.deriveRanked(pitches, comparisonAttribute='name', resultsReturned=3)
#   [(8, D Concrete), (5, A Concrete), (5, G Concrete)]
hij.derive(pitches, comparisonAttribute='name')      # single best match
hij.deriveAll(pitches, comparisonAttribute='name')   # every scale containing ALL pitches
```

Counts are per *occurrence*, not per pitch class, unless `removeDuplicates=True`. For tonal
music `stream.analyze('key')` is complementary and often better:

```python
s.analyze('key')                                    # g minor, correlationCoefficient 0.7526
[(str(k), round(k.correlationCoefficient, 3)) for k in s.analyze('key').alternateInterpretations[:4]]
#   [('B- major', 0.494), ('c minor', 0.468), ('G major', 0.437), ('D major', 0.369)]
```

---

## 9. Roman numerals → chords

`RomanNumeral(figure, keyOrScale)` produces a real `Chord` with correct spelling, octaves and
inversion. Verified in **A minor**:

```
figure     pitches              .romanNumeralAlone  .scaleDegreeWithAlteration  .inversion()
i          A4 C5 E5             i                   (1, None)                   0
VI         F5 A5 C6             VI                  (6, None)                   0
III        C5 E5 G5             III                 (3, None)                   0
VII        G5 B5 D6             VII                 (7, None)                   0
iv         D5 F5 A5             iv                  (4, None)                   0
V7         E5 G#5 B5 D6         V                   (5, None)                   0
V43        B4 D5 E5 G#5         V                   (5, None)                   2
i64        E5 A5 C6             i                   (1, None)                   2
V65/iv     C#5 E5 G5 A5         V                   (5, None)                   1
viio7/V    D#5 F#5 A5 C6        vii                 (7, None)                   0
N6         D5 F5 B-5            II                  (2, flat)                   1
bII        B-4 D5 F5            II                  (2, flat)                   0
It6        F5 A5 D#6            It                  (4, sharp)                  1
Fr43       F5 A5 B5 D#6         Fr                  (2, None)                   2
Ger65      F5 A5 C6 D#6         Ger                 (4, sharp)                  1
#ivo7      D#5 F#5 A5 C6        iv                  (4, sharp)                  0
```

Grammar: `[b|#|bb|##]RN[figured-bass digits][/secondary]`, plus `o` (dim), `ø` (half-dim),
`+` (aug), `[no5]`, `[add6]`, `[b5]`.

### A progression, voiced

```python
from music21 import roman, key, chord, stream, meter, note

k = key.Key('a')
s = stream.Part()
s.append(meter.TimeSignature('4/4')); s.append(k)
for fig in ['i', 'VI', 'III', 'VII', 'iv', 'V7', 'i']:
    rn = roman.RomanNumeral(fig, k)
    rn.duration.quarterLength = 2.0
    rn.closedPosition(forceOctave=4, inPlace=True)   # tidy the register
    rn.lyric = fig
    s.append(rn)
# i   ['A4','C5','E5']      VI  ['F4','A4','C5']    III ['C4','E4','G4']
# VII ['G4','B4','D5']      iv  ['D4','F4','A4']    V7  ['E4','G#4','B4','D5']
# i   ['A4','C5','E5']
```

A `RomanNumeral` **is** a `Chord` — it goes straight into a stream and writes/plays.
`rn.bass()`, `rn.root()`, `rn.third`, `rn.fifth`, `rn.seventh` all work, so splitting bass
from upper structure is `note.Note(rn.bass().transpose('P-8'))` plus `chord.Chord(rn.pitches)`.

```python
rn = roman.RomanNumeral('V7', 'C')
rn.key = key.Key('E-')                             # re-spell into a new key, in place
rn.pitches                                         # (B-4, D5, F5, A-5)
roman.RomanNumeral('V7', 'C').transpose('M2')      # <RomanNumeral V7 in D major>
roman.RomanNumeral('V7', 'C').figureAndKey         # 'V7 in C major'
roman.RomanNumeral('bII6', 'C').isNeapolitan()     # True
roman.RomanNumeral('bVI', 'C').isMixture()         # True
roman.RomanNumeral('V65', 'C').figuresWritten      # '65'  -- bridge to figured bass
roman.RomanNumeral('V65', 'C').bassScaleDegreeFromNotation()      # 7
roman.RomanNumeral('V7', scale.HarmonicMinorScale('a')).pitches   # E5 G#5 B5 D6
```

**`Minor67Default`** — case alone cannot say whether `VII` in A minor is G or G♯
(`music21/roman.py:1452`). Set it per object; `sixthMinor` is the analogue for degree 6, and
the default `CAUTIONARY` is why analysis emits `bVI`/`bVII` rather than `VI`/`VII`.

```python
from music21.roman import Minor67Default
roman.RomanNumeral('VII', 'a', seventhMinor=Minor67Default.QUALITY).pitches   # G  B  D
roman.RomanNumeral('vii', 'a', seventhMinor=Minor67Default.QUALITY).pitches   # G# B  D#
roman.RomanNumeral('VII', 'a', seventhMinor=Minor67Default.SHARP).pitches     # G# B# D#
roman.RomanNumeral('VII', 'a', seventhMinor=Minor67Default.FLAT).pitches      # G  B  D
```

---

## 10. Roman numerals ← chords (analysis)

`romanNumeralFromChord(chord, key, preferSecondaryDominants=False)` (`music21/roman.py:922`).
In C major:

```
['C','E','G']         -> I          score=100      ['F','A','C']        -> IV       score=59
['G','B','D','F']     -> V7         score=80       ['A-','C','E-','F#'] -> Ger65    score=33
['D-','F','A-']       -> bII        score=0        ['B-','D','F']       -> bVII     score=0
['B','D','F','A-']    -> viiob753   score=0    <- ugly but pitch-correct
['E','G#','B','D']    -> III75#3    score=0    ... preferSecondaryDominants=True -> V7/vi
```

`.functionalityScore` (0–100) ranks how idiomatic the numeral is in the key — a cheap filter
for "is this chord functional here?".

```python
from music21 import corpus
s = corpus.parse('bach/bwv66.6').measures(1, 4)
k = s.analyze('key')                       # f# minor
red = s.chordify()
for c in red.recurse().getElementsByClass(chord.Chord):
    c.removeRedundantPitchNames(inPlace=True)
    c.addLyric(roman.romanNumeralFromChord(c, k).figure)
# m1 0.0 ['F#','C#','A'] i      | m1 1.0 ['G#','B','E'] bVII6 | m1 2.0 ['A','E','C#'] III
# m2 1.0 ['E','G#','B']  bVII   | m2 1.5 ['E','D','G#','B'] bVII7 | m2 3.0 ['E#','C#','G#'] V6
```

`chordify()` + `removeRedundantPitchNames()` + `romanNumeralFromChord()` is the whole
analysis pipeline. Passing tones produce nonsense figures — filter by `beatStrength` or
`functionalityScore` if you only want structural harmonies.

---

## 11. Chord symbols — the lead-sheet workflow

`ChordSymbol('Cmaj7')` parses jazz/pop figures into pitches. Legal suffixes are in
`harmony.CHORD_TYPES` (50 kinds, each with abbreviations).

```
C           C3 E3 G3            Cmaj7    C3 E3 G3 B3         G7      G2 B2 D3 F3
Cm7b5       C3 E-3 G-3 B-3      Co7/Cdim7 C3 E-3 G-3 B--3    C+/Caug C3 E3 G#3
Dsus4       D3 G3 A3            Cadd9    C3 E3 G3 D4         Cpower  C3 G3
Dm11        D2 F2 A2 C3 E3 G3   B-13     B-1 D2 F2 A-2 C3 E-3 G3
E7#9        E2 G#2 B2 D3 F##3   F#m7b5   F#2 A2 C3 E3   (kind label says 'minor-seventh';
Cm/E-       E-3 G3 C4  root=C4 bass=E-3                  the pitches are correct half-dim)
A7/C#       C#3 E3 G3 A3  root=A3 bass=C#3
```

```python
harmony.ChordSymbol(root='C', bass='E', kind='major')                 # C/E
harmony.ChordSymbol(kind='dominant-seventh', root='G', inversion=1)   # G7/B
harmony.ChordSymbol('Dm7').transpose('M2')                            # Em7
harmony.NoChord()                                                     # 'N.C.', pitches ()

harmony.chordSymbolFigureFromChord(chord.Chord('C4 E-4 G-4 B-4'))     # 'Cø7'
harmony.chordSymbolFigureFromChord(chord.Chord('E-3 G3 C4'))          # 'Cm/E-'
harmony.chordSymbolFigureFromChord(chord.Chord('G3 B3 D4 F4 A4'))     # 'G9'
harmony.chordSymbolFigureFromChord(c, includeChordType=True)  # ('Cø7','half-diminished-seventh')
harmony.chordSymbolFromChord(chord.Chord('C4 E4 G4 B-4'))     # <ChordSymbol C7>
```

### End to end

```python
from music21 import harmony, stream, chord, meter, converter

mel = converter.parse("tinyNotation: 4/4 e'4 d' c' d' e'2 g' a'1")   # returns a Part
for off, fig in {0.0: 'C', 4.0: 'Am', 6.0: 'F', 8.0: 'G7'}.items():
    mel.insert(off, harmony.ChordSymbol(fig))

sc = stream.Score([mel])
harmony.realizeChordSymbolDurations(sc)      # gives each symbol its sounding length
for cs in sc.recurse().getElementsByClass(harmony.ChordSymbol):
    print(cs.figure, cs.getOffsetInHierarchy(sc), cs.quarterLength, cs.pitches)
# C 0.0 4.0 C3 E3 G3 | Am 4.0 2.0 A2 C3 E3 | F 6.0 2.0 F3 A3 C4 | G7 8.0 4.0 G2 B2 D3 F3

comp = stream.Part()
comp.insert(0, meter.TimeSignature('4/4'))
for cs in sc.recurse().getElementsByClass(harmony.ChordSymbol):
    c = chord.Chord(cs.pitches); c.quarterLength = cs.quarterLength
    comp.insert(cs.getOffsetInHierarchy(sc), c.transpose(12))
comp.makeMeasures(inPlace=True)
# m1 {0.0} Chord C4 E4 G4 | m2 {0.0} Chord A3 C4 E4  {2.0} Chord F4 A4 C5
# m3 {0.0} Chord G3 B3 D4 F4
```

`realizeChordSymbolDurations` (`music21/harmony.py:2532`) extends each symbol to the next one
or to the end of the piece.

---

## 12. Figured bass realization

`FiguredBassLine` + `Rules` + `Realization` (`music21/figuredBass/realizer.py`, `rules.py`).

```python
from music21.figuredBass import realizer, rules
from music21 import note, key, meter

fbLine = realizer.FiguredBassLine(key.Key('B-'), meter.TimeSignature('3/4'))
for n, fig in [('B-2', None), ('C3', '6'), ('D3', '6'), ('E-3', '6'), ('F3', '6'),
               ('C3', '6'), ('D3', '6'), ('A2', '7,5,#3'), ('B-2', None)]:
    fbLine.addElement(note.Note(n), fig)

r = rules.Rules()
r.partMovementLimits = [(1, 2), (2, 12), (3, 12)]   # (partNumber, max semitone leap)
real = fbLine.realize(r)                     # realize(fbRules=None, numParts=4, maxPitch=None)
real.getNumSolutions()                       # 7541
real.keyboardStyleOutput = False             # set BEFORE generating -> 4 separate parts
prog = real.getAllPossibilityProgressions()[0]                  # deterministic pick
out  = real.generateRealizationFromPossibilityProgression(prog)

# soprano  D4  C4  B-3 C4  D4  E-4 D4  C#4 D4
# alto     F3  A3  B-3 G3  A3  A3  B-3 G3  F3
# tenor    D3  E-3 F3  G3  F3  A3  F3  E-3 D3
# bass     B-2 C3  D3  E-3 F3  C3  D3  A2  B-2
```

Figures are comma-separated: `'6'`, `'6,4'`, `'7,5,#3'`, `'#'` (raise the third), `'b7'`,
`'6,b5'`. From a notated stream they live in lyrics:

```python
s = converter.parse('tinynotation: 4/4 C4 D8_6 E8_6 F4 G4_7 c1', makeNotation=False)
realizer.figuredBassFromStream(s).realize(r).getNumSolutions()      # 13
```

### Roman-numeral progression → four parts

`RomanNumeral.figuresWritten` yields the figured-bass string, so the two modules connect:

```python
k = key.Key('C')
fbLine = realizer.FiguredBassLine(k)
for f in ['I', 'vi', 'IV', 'V7', 'I']:
    rn = roman.RomanNumeral(f, k)
    b = note.Note(rn.bass()); b.octave = 3; b.quarterLength = 1.0
    fbLine.addElement(b, rn.figuresWritten or None)     # '' must become None

r = rules.Rules(); r.partMovementLimits = [(1, 4), (2, 12), (3, 12)]
real = fbLine.realize(r)
real.keyboardStyleOutput = False
out = real.generateRealizationFromPossibilityProgression(real.getAllPossibilityProgressions()[0])
# solutions: 9
# part0: C5 C5 C5 B4 C5   part1: G4 A4 A4 F4 E4
# part2: E4 E4 F4 D4 C4   part3: C3 A3 F3 G3 C3
```

Rules (`True` unless noted): `forbidParallel{Fifths,Octaves}`, `forbidHidden{Fifths,Octaves}`,
`forbidVoice{Overlap,Crossing}`, `forbidIncompletePossibilities`,
`upperPartsMaxSemitoneSeparation=12`, `partMovementLimits=[]`,
`resolve{DominantSeventh,DiminishedSeventh,AugmentedSixth}Properly`,
`doubledRootInDim7=False`. Loosen them when `getNumSolutions()` returns 0.

---

## 13. Voice-leading checking

`VoiceLeadingQuartet(v1n1, v1n2, v2n1, v2n2)` — two voices, two time points
(`music21/voiceLeading.py:90`).

```python
from music21 import voiceLeading
voiceLeading.VoiceLeadingQuartet('C4','D4','G4','A4').parallelFifth()    # True
voiceLeading.VoiceLeadingQuartet('C4','D4','C5','D5').parallelOctave()   # True
voiceLeading.VoiceLeadingQuartet('E4','F4','C5','F5').hiddenOctave()     # True
voiceLeading.VoiceLeadingQuartet('C4','D4','E4','F4').motionType()       # MotionType.parallel
```

Also `parallelUnison`, `antiParallelMotion`, `contraryMotion`, `similarMotion`,
`obliqueMotion`, `noMotion`, `voiceCrossing`, `voiceOverlap`, `inward/outwardContraryMotion`,
`hiddenFifth`, `hiddenInterval(iv)`, `leapNotSetWithStep`, `isProperResolution`,
`opensIncorrectly`, `closesIncorrectly`. A working checker (index alignment assumes
homorhythm — `chordify()` first, or use `figuredBass.checker`, for free rhythm):

```python
def checkParallels(sc):
    out, parts = [], list(sc.parts)
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a = parts[i].flatten().notes.stream()
            b = parts[j].flatten().notes.stream()
            for k in range(min(len(a), len(b)) - 1):
                vlq = voiceLeading.VoiceLeadingQuartet(a[k], a[k+1], b[k], b[k+1])
                if vlq.parallelFifth():  out.append((i, j, k, 'P5'))
                if vlq.parallelOctave(): out.append((i, j, k, 'P8'))
                if vlq.hiddenFifth():    out.append((i, j, k, 'hidden5'))
    return out
```

Soprano `c'' d'' e'' f''` over bass `f g a b-` returns
`[(0,1,0,'P5'), (0,1,1,'P5'), (0,1,2,'P5')]` — three consecutive parallel fifths, flagged.

---

## 14. Post-tonal: rows, set classes, sieves

### Twelve-tone rows (`music21/serial.py`)

```python
from music21 import serial, stream, note
r = serial.TwelveToneRow([0,1,4,2,3,7,5,8,6,10,9,11])
r.pitchClasses()   # [0,1,4,2,3,7,5,8,6,10,9,11]
r.noteNames()      # ['C','C#','E','D','E-','G','F','G#','F#','B-','A','B']
print(r.matrix())  # 12x12, hex digits, P0 across the top and I0 down the left:
#   0  1  4  2  3  7  5  8  6  A  9  B
#   B  0  3  1  2  6  4  7  5  9  8  A
#   8  9  0  A  B  3  1  4  2  6  5  7
#   ... 9 more rows ...
#   1  2  5  3  4  8  6  9  7  B  A  0

# transformations return a new ToneRow (music21/serial.py:455, :512)
r.zeroCenteredTransformation('P',  5)   # [5,6,9,7,8,0,10,1,11,3,2,4]
r.zeroCenteredTransformation('I',  5)   # [5,4,1,3,2,10,0,9,11,7,8,6]
r.zeroCenteredTransformation('R',  5)   # [4,2,3,11,1,10,0,8,7,9,6,5]
r.zeroCenteredTransformation('RI', 5)   # [6,8,7,11,9,0,10,2,3,1,4,5]
r.originalCenteredTransformation('T', 5)   # index from the row's own first pc; 'T' not 'P'

r.isTwelveToneRow(); r.isAllInterval()     # True; False
r.getIntervalsAsString()                   # '13T14T3T4E2'
r.areCombinatorial('P', 0, 'I', 5)         # False  (indices must be ints)
serial.pcToToneRow([0,4,7])                # a ToneRow from any pc list
w = serial.getHistoricalRowByName('RowWebernOp29')
w.pitchClasses(), w.composer, w.title   # [3,11,2,1,5,4,7,6,10,9,0,8], 'Webern', 'Cantata I'

# a row IS a Stream of Notes, so a transformation becomes music directly
s = stream.Part()
for n in r.zeroCenteredTransformation('RI', 3).notes:
    nn = note.Note(n.pitch); nn.octave = 4; nn.quarterLength = 0.5
    s.append(nn)
# E4 F#4 F4 A4 G4 B-4 G#4 C4 C#4 B4 D4 E-4
```

### Set classes (`music21/chord/tables.py`)

```python
from music21 import chord
from music21.chord import tables

c = chord.Chord('C4 E4 G4 B4')
c.normalOrder, c.primeForm      # [11,0,4,7], [0,1,5,8]
c.forteClass, c.commonName      # '4-20', 'major seventh chord'
c.intervalVector                # [1,0,1,2,2,0]   .intervalVectorString -> '<101220>'
c.chordTablesAddress   # ChordTableAddress(cardinality=4, forteClass=20, inversion=0, pcOriginal=4)

addr = tables.seekChordTablesAddress(chord.Chord([0,1,4,6]))
tables.addressToPrimeForm(addr)                 # (0, 1, 4, 6)
tables.addressToIntervalVector(addr)            # (1, 1, 1, 1, 1, 1)
tables.addressToCommonNames(addr)               # ['all-interval tetrachord']
tables.addressToForteName(addr)                 # '4-15A'   (classification='tni' -> '4-15')
tables.addressToZAddress(addr)                  # 4-29, inversion 1
tables.forteIndexToInversionsAvailable(4, 29)   # [-1, 1]
tables.intervalVectorToAddress((1,1,1,1,1,1))   # [4-15, 4-29]  -- the Z-pair
chord.Chord([0,1,4,6]).hasZRelation             # True; .getZRelation() -> <Chord C D- E- G>

pf = tables.addressToPrimeForm((5, 35, 0))      # (0, 2, 4, 7, 9)  -- build FROM a set class
chord.Chord([p + 60 for p in pf]).pitchNames    # ['C','D','E','G','A']  (pentatonic)
```

### Xenakis sieves (`music21/sieve.py`)

Sieve strings combine residual classes `modulus@shift` with `|` (union), `&` (intersection),
`^` (symmetric difference), `-` (complement).

```python
from music21 import sieve
s = sieve.Sieve('3@2|7@1'); s.setZRange(0, 47)
s.segment()                          # [1,2,5,8,11,14,15,17,20,22,23,26,29,32,35,36,...]
s.segment(segmentFormat='binary')    # [0,1,1,0,0,1,0,0,1,0,0,1,...]
s.segment(segmentFormat='width')     # [1,3,3,3,3,1,2,3,2,1,3,3,...]   gaps -> rhythm
sieve.CompressionSegment([0,2,4,5,7,9,11])      # '5@2|5@4|6@5|7@0'  (a set -> a sieve)
[str(p) for p in sieve.PitchSieve('13@3|13@6|13@9', 'c2', 'c5')()]
#   ['E-2','F#2','A2','E3','G3','B-3','F4','G#4','B4']
scale.SieveScale('C4', '4@0|4@1|4@2').pitches   # C4 C#4 D4 E4

w = sieve.Sieve('5@0|8@3'); w.setZRange(0, 32)
widths = w.segment(segmentFormat='width')       # [3,2,5,1,4,4,1,5,2,3]
p = stream.Part()
for i, wd in enumerate(widths):
    p.append(note.Note(60 + (i * 7) % 12, quarterLength=wd * 0.25))
# C4/0.75 G4/0.5 D4/1.25 A4/0.25 E4/1.0 B4/1.0 F#4/0.25 C#4/1.25 ...
```

---

## Gotchas

1. **`key.Key('g').getScale()` returns B-flat *major*.** `getScale` is inherited from
   `KeySignature` and defaults to `mode='major'`, ignoring the `Key`'s own mode
   (`music21/key.py:820`); it also raises `KeyException` for any mode but major/minor. Use
   `k.pitches` / `k.getPitches()` (a `Key` *is* a `DiatonicScale`) or `k.getScale(k.mode)`.
   For harmonic/melodic minor build `scale.HarmonicMinorScale(k.tonic)` explicitly.

2. **Roman-numeral round trips are not stable in minor.** `RomanNumeral('V7','a')` →
   `romanNumeralFromChord` → `'V75#3'`; `'VI'` → `'bVI'`; `viio7` in C *major* →
   `'viiob753'`. Pitches are right, strings are verbose — and `'bVI'` ≠ `'VI'` (in A minor
   `bVI` is F♭ A♭ C♭). Cause: `Minor67Default.CAUTIONARY` (`music21/roman.py:1452`). Never
   feed a generated figure back in unchecked; compare `.pitches`, not `.figure`.
   `preferSecondaryDominants=True` helps only with applied dominants.

3. **`ChordSymbol('Bb7')` is silently wrong** — parsed as root B-natural with a flat-13
   alteration → `B1 D#2 F#2 A3`. music21 spells flats with `-`: `'B-7'`, `'A-'`, `'E-maj7'`.
   `'Ab'` raises, `'Bb13'` does not. `'Cmaj9'`, `'C6/9'`, `'G13sus4'` also raise — consult
   `harmony.CHORD_TYPES` for the legal abbreviation (`'CM9'`, `'C69'`, `'C7sus4'`).
   `ChordSymbol('NC')` raises; use `harmony.NoChord()`.

4. **Quarter tones survive MusicXML but are destroyed by MIDI** — `E\`4` (ps 63.5)
   round-trips through `.musicxml` and comes back from `.mid` as `E4`. Microtonal work is
   score-only unless you emit pitch bend yourself. Relatedly `ConcreteScale.tune()` matches
   on `Pitch.name`, so a Rast scale containing `E\`` will not retune notes named `E` — `tune`
   is for alternate temperaments of the *same* note names, not for mapping into a maqam.

5. **`getPitches(high, low)` is not the descending form.** For any direction-dependent scale
   (melodic minor, ragas, your `fillArbitrary` scales) pass
   `minPitch=<low>, maxPitch=<high>, direction=Direction.DESCENDING`. Swapping the arguments
   reverses the *ascending* collection and quietly yields wrong notes.

Further traps, decreasing damage:

6. `Realization.generateRandomRealization()` **crashes on Python ≥ 3.11 with music21 10.5.0**
   (`TypeError: Population must be a sequence`): `random.sample` on `dict.keys()` at
   `music21/figuredBass/realizer.py:666`. Fixed at HEAD `[v11]`. Use
   `getAllPossibilityProgressions()[i]` + `generateRealizationFromPossibilityProgression`.
7. `Realization.keyboardStyleOutput` must be `False` **before** generating, or you get two
   piano-style parts of `Chord` objects instead of four vocal lines.
8. `ConcreteScale.getChord(min, max)` returns *every* scale pitch in range as one chord — use
   `pitchesFromScaleDegrees([1,3,5])`. And `ConcreteScale.romanNumeral(n)` stacks diatonic
   thirds: on Hijaz D, `romanNumeral(4)` gives G–B–D, but B is not in the scale (B♭ is).
9. `IntervalNetwork` defaults to `pitchSimplification='maxAccidental'` and respells your
   pitches (`'mostCommon'` turned `D-4` into `C#4`). Pass `pitchSimplification=None`.
10. `RomanNumeral.figuresWritten` is `''`, not `None`, for a root-position triad, and
    `addElement(n, '')` differs from `addElement(n, None)` — coerce with `or None`.
11. `serial` transformation indices must be `int` (`areCombinatorial('P','0',…)` raises
    `SerialException`), and `originalCenteredTransformation` spells transposition `'T'`.
12. `realizeChordSymbolDurations` gives a symbol placed past the last note
    `quarterLength 0.0`. Keep every `ChordSymbol` at or before the final note's offset.
13. `interval.Interval` caps spelling at four accidentals; `A5` above `B#4` is `F###5`, and
    only `maxAccidental=1` gives the readable `G#5`.
