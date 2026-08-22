# 08 — Analysis, feature extraction, and verifying your own music

Two jobs. **Understanding** source material you are adapting — what key, what chords,
what register, what rhythmic character. And **verifying** what you just wrote, because
you cannot listen to it. The same tools do both: `chordify` and roman numerals give you
a chord chart from any score; key detection, `voiceLeading`, `features` and ambitus give
you numbers you can assert against. Everything below was executed on music21 **10.5.0**.

Source citations are to git HEAD (v11.0.0b8). Diffed against 10.5.0: `discrete.py`,
`harmonicFunction.py`, `graph/plot.py`, `corpora.py` are byte-identical; `voiceLeading`,
`features`, `search`, `tree`, `neoRiemannian` differ only by type annotations. **No API
in this chapter is v11-only.**

---

## The map — what to reach for

| Need | Call |
|---|---|
| Key of a piece | `s.analyze('key')` → `key.Key` with `.correlationCoefficient` |
| Key over time | `analysis.floatingKey.KeyAnalyzer` (per bar) or `analysis.windowed.WindowedAnalysis` |
| Chords of a polyphonic score | `s.chordify()` |
| Chord chart | `chordify` + `roman.romanNumeralFromChord` + `harmony.chordSymbolFigureFromChord` |
| Register | `s.analyze('ambitus')` → `interval.Interval` |
| Numeric fingerprint | `features.allFeaturesAsList(s)` (92 extractors) |
| Fast vertical slices, voice leading | `tree.fromStream.asTimespans` + `Verticality` |
| Find a motif | `search.noteNameSearch`, `search.rhythmicSearch`, `StreamSearcher` + `Wildcard` |
| Re-harmonise | `analysis.neoRiemannian.L/P/R/S/N` |
| A picture | `s.plot('pianoroll', doneAction=None).write('x.png')` with the Agg backend |
| Offline material | `corpus.parse`, `corpus.search` — 15,112 works, no network |

---

## Key detection

Five weighting profiles, all subclasses of `KeyWeightKeyAnalysis`
(`music21/analysis/discrete.py:201`). They all convolve a duration-weighted pitch-class
histogram (`discrete.py:344`) against a 12-element weight vector and take the best
correlation.

| Identifier | Class | Source line | Character (from Humdrum `keycor`) |
|---|---|---|---|
| `key.aarden` (also plain `'key'`) | `AardenEssen` | `discrete.py:775` | **default**; weak pull to the subdominant |
| `key.krumhansl` / `key.kessler` | `KrumhanslSchmuckler` | `discrete.py:726` | strong pull to the dominant |
| `key.simple` | `SimpleWeights` | `discrete.py:819` | steady over long spans, noisy over short |
| `key.bellman` | `BellmanBudge` | `discrete.py:857` | no particular neighbour-key bias |
| `key.temperley` | `TemperleyKostkaPayne` | `discrete.py:896` | in minor, tends to pick the relative major |

`KrumhanslKessler` is an alias of `KrumhanslSchmuckler` — since v6.3 they are the same
weights (`discrete.py:772`). Plain `'key'` resolves to `AardenEssen` because that class
claims the bare `'key'` identifier (`discrete.py:791`).

```python
from music21 import corpus
s = corpus.parse('bach/bwv66.6')

k = s.analyze('key')
print(k, k.tonic, k.mode, k.correlationCoefficient)
# f# minor  F#  minor  0.9379555412471554

for alt in k.alternateInterpretations[:5]:
    print(f'{str(alt):12s} {alt.correlationCoefficient:.4f}')
# A major      0.7748
# b minor      0.7556
# E major      0.6726
# c# minor     0.5867
# B major      0.5507
```

`.alternateInterpretations` is the other 23 keys sorted best-first, each carrying its own
`.correlationCoefficient` (`music21/key.py:1002`). The **gap** between first and second is
worth more than the absolute value.

### Run all five and take the vote

```python
for m in ['key.krumhansl', 'key.aarden', 'key.simple', 'key.bellman', 'key.temperley']:
    kk = s.analyze(m)
    print(f'{m:16s} {str(kk):10s} r={kk.correlationCoefficient:.4f} 2nd={kk.alternateInterpretations[0]}')
# bwv66.6 (whole piece): all five -> f# minor, r 0.8155–0.9380.  Unanimous: trust it.
#
# joplin/maple_leaf_rag bars 1-8   aarden:A- major  krumhansl:E- major  simple/bellman/temperley:g# minor
# beethoven/opus18no1/m1 bars 1-8  aarden:B- major  krumhansl/simple/bellman/temperley:F major
```

Those two are *actually* in A♭ major and B♭ major; the dominant-biased profiles landed on
the dominant, exactly as their documentation warns. **Disagreement means the excerpt is
short, modulating, or not common-practice** — not that one profile is better.

Atonal music breaks all five. Schoenberg Op.19/2 returns `G major r=0.5566`; the low `r`
and the 77% in-key figure are the tell, not the answer. `k.tonalCertainty()`
(`music21/key.py:1181`) condenses the whole alternates distribution into one number —
1.2643 for bwv66.6, higher = more certain, also exposed as native feature `K1`.

### Ambitus and interval diversity

```python
from music21.analysis import discrete
s.analyze('ambitus')                              # <music21.interval.Interval m21>
lo, hi = discrete.Ambitus().getPitchSpan(s)       # discrete.py:1012 -> F#2, E5

found = discrete.MelodicIntervalDiversity().countMelodicIntervals(s.parts[0])  # :1232
{k: v[1] for k, v in sorted(found.items(), key=lambda x: -x[1][1])}
# {'M2': 17, 'm3': 4, 'M3': 4, 'm2': 3, 'P4': 2}
```

`MelodicIntervalDiversity.getSolution()` is **broken** in both 10.5.0 and HEAD — it passes
the stream into the `found=` slot (`discrete.py:1290`). Call `countMelodicIntervals`
directly.

---

## Key over time

Use `floatingKey` for a per-bar answer, `windowed` for an arbitrary quarter-note grid.

### floatingKey — per measure, smoothed

`KeyAnalyzer` (`music21/analysis/floatingKey.py:26`) analyses each measure alone, then
smooths each bar's interpretation dictionary with its neighbours weighted by `1/distance`
(`floatingKey.py:137`).

```python
from music21.analysis import floatingKey
ka = floatingKey.KeyAnalyzer(s)
ka.windowSize = 4                # bigger = fewer modulations reported
ka.run()                         # one Key per measure, 0-indexed
# [A, A, A, f#, f#, f#, f#, f#, f#, f#]
ka.getRawKeyByMeasure()          # unsmoothed; noisy but honest
# [A, E, A, f#, E, A, b, C#, F#, b]
```

### WindowedAnalysis — arbitrary window in quarter notes

`WindowedAnalysis` (`music21/analysis/windowed.py:45`) re-bars the stream into 1/4
measures (`windowed.py:65`) and slides any `DiscreteAnalysis` processor over them.

```python
from music21.analysis import windowed, discrete
wa = windowed.WindowedAnalysis(s, discrete.AardenEssen())
data, colors = wa.analyze(8, windowType='noOverlap')   # 8 quarter notes per window
for i, (tonic, mode, r) in enumerate(data):
    print(f'q{i*8:3d}-{i*8+8:3d}: {tonic} {mode} r={r:.3f}')
# q 0-8: A major r=0.899 | q 8-16: F# minor r=0.890 | q 16-24: A major r=0.895
# q 24-32: F# major r=0.716 | q 32-40: B minor r=0.778
```

`windowType` is `'overlap'` (default), `'noOverlap'`, or `'adjacentAverage'`
(`windowed.py:116`). Each datum is a `(Pitch, modeStr, correlation)` triple — note the
mode comes back as a **string**, not part of the Pitch.

---

## chordify — the single most useful analysis call

`Stream.chordify()` (`music21/stream/base.py:6234`) splits every part at every unique
onset and gathers the simultaneities into `Chord` objects, preserving the measure
structure. It is how you turn four independent voices into something you can name.

```python
from music21 import chord
ch = s.chordify()                                          # -> a stream.Part
len(ch.recurse().getElementsByClass(chord.Chord))          # 51

for c in ch.measure(1).recurse().getElementsByClass(chord.Chord):
    print(c.offset, c.quarterLength, [p.nameWithOctave for p in c.pitches])
# 0.0 1.0 ['F#3', 'C#4', 'F#4', 'A4']     2.0 1.0 ['A3', 'E4', 'C#5']
# 1.0 1.0 ['G#3', 'B3', 'E4', 'B4']       3.0 1.0 ['G#3', 'B3', 'E4', 'E5']
```

### The parameters that matter

* **`removeRedundantPitches=True`** — the default. Octave doublings collapse to one pitch.
  Bar 1 above shows `F#3 C#4 F#4 A4`: the two F♯s survive because they are *different
  octaves of the same name* — the flag removes exact `nameWithOctave` duplicates, not
  pitch-class duplicates. Set it `False` when you need voice count per verticality.
* **`addPartIdAsGroup=True`** — stamps each pitch's `.groups` with the source part id, so
  you can un-chordify later: `[p for p in c.pitches if 'Bass' in p.groups]`.
* **`toSoundingPitch=True`** (default) transposes transposing instruments first; leave it
  on or a written-pitch clarinet part will chordify to nonsense. **`addTies=True`**
  (default) ties across split points — turn it off only if raw iteration must not see
  tied continuations.

`closedPosition(forceOctave=4)` collapses a spread voicing to one octave, which is what
chord-symbol identification wants:

```python
c.closedPosition(forceOctave=4, inPlace=False)
# F#3 C#4 F#4 A4  ->  ['F#4', 'A4', 'C#5']   c.commonName == 'minor triad'
# G#3 B3  E4  B4  ->  ['G#4', 'B4', 'E5']    'major triad'
```

### chordify → roman numerals and chord symbols

```python
from music21 import roman, harmony
k = s.analyze('key')                              # f# minor

for m in ch.getElementsByClass('Measure')[:4]:
    for c in m.recurse().getElementsByClass(chord.Chord):
        rn  = roman.romanNumeralFromChord(c, k).figure
        cc  = c.closedPosition(forceOctave=4, inPlace=False)
        cc.removeRedundantPitchNames(inPlace=True)
        sym = harmony.chordSymbolFigureFromChord(cc)
        print(f'm{m.number} {c.offset:4}  {str([p.nameWithOctave for p in c.pitches]):40s} {rn:8s} {sym}')
# m1  0.0  ['F#3', 'C#4', 'F#4', 'A4']            i        F#m
# m1  1.0  ['G#3', 'B3', 'E4', 'B4']              bVII6    E/G#
# m1  2.0  ['A3', 'E4', 'C#5']                    III      A
# m2  1.5  ['E3', 'D4', 'G#4', 'B4']              bVII7    E7
# m2  3.0  ['E#3', 'C#4', 'G#4', 'C#5']           V6       C#/E#
# m3  0.5  ['B2', 'D4', 'G#4', 'B4']              iio6     G#dim/B
# m3  1.5  ['C#3', 'B3', 'E#4', 'G#4']            V75#3    C#7
```

Note `bVII` for an E major triad in F♯ minor: music21 measures minor-key roman numerals
against the **harmonic** minor, where degree 7 is E♯, so the natural VII is spelled flat.
`rn.romanNumeralAlone` (`'VII'`) and `rn.scaleDegree` (`7`) give the accidental-free form.
Correct behaviour, not a bug. And `harmony.chordSymbolFigureFromChord` returns the literal
string `'Chord Symbol Cannot Be Identified'` for unrecognised chords rather than raising —
test for it and fall back to `c.pitchedCommonName`.

### Mapping harmony to function

`music21/analysis/harmonicFunction.py` converts roman numerals to Riemann function labels
and back — useful when you want to *reharmonise by function* rather than by chord.

```python
from music21.analysis import harmonicFunction as hf
rn = roman.romanNumeralFromChord(chord.Chord('E4 G#4 B4'), key.Key('f#'))
hf.romanToFunction(rn)                                        # 'dP'  (dominant parallel)
hf.functionToRoman(hf.HarmonicFunction('D'), keyOrScale=key.Key('C'))
# <music21.roman.RomanNumeral V in C major>
```
18 labels (`harmonicFunction.py:20`): `T Tp Tg t tP tG S Sp Sg s sP sG D Dp Dg d dP dG`.
In F♯ minor: E major → `dP`, A major → `tP`, C♯ major → `D`, B minor → `s`.

---

## Recipe: harmonic summary of any score

`scripts/analyze_score.py` — argparse CLI, accepts a filesystem path, a corpus path, or a
tinyNotation string, and emits text or JSON.

```bash
python scripts/analyze_score.py bach/bwv66.6 --compare-keys
python scripts/analyze_score.py mypiece.mid --bars 1-16 --per-bar 1
python scripts/analyze_score.py score.musicxml --key "d minor" --json
```

What it does that a naive loop does not: it picks **one or two chords per bar** by
weighting each distinct pitch-class set by `duration × (0.5 + beatStrength) × 1.5 if
triad/seventh`, so passing tones and suspensions lose to the harmony they decorate. Tested
output on four sources in four formats:

```
$ analyze_score.py bach/bwv66.6 --compare-keys                    # .mxl, 4 voices
bach/bwv66.6
  key      f# minor  (r=0.938, aarden)
  next     A major 0.7748, b minor 0.7556, E major 0.6726, c# minor 0.5867
  vote     all five profiles -> f# minor
  meter    4/4@m0     tempo 96bpm@0.0     length 10 bars / 36.0 ql
  ambitus  F#2–E5  (34 st, Minor Twenty-first)
  harm.rhy 48 changes, 0.75 ql per chord
  in key   92.71%  (out: E# 6.0, A# 3.5, D# 1.0)
  parts    Soprano 37 notes E4–E5 | Alto 42 F#3–A4 | Tenor 45 E#3–E4 | Bass 41 F#2–D4
  chart
    m0 III | bVII6      A | E/G#          m3 i | V        F#m | C#
    m1 i | bVII6        F#m | E/G#        m8 I6 | I65     F#/A# | F#7/A#   <- Picardy third
    m2 III | V6         A | C#/E#         m9 iv6 | I      Bm/D | F#
```

```
$ analyze_score.py verdi/laDonnaEMobile --bars 1-8 --per-bar 1    # .mxl, piano reduction
  key B- major (r=0.904)   meter 3/8@m1   tempo 75bpm   ambitus F2–F5 (36 st)   in key 100.0%
  chart  m1 I64 B-/F | m2 I64 B-/F | m3 V7 F7 | m4 V7 F7 | m5 I64 B-/F | m7 V7 F7

$ analyze_score.py beethoven/opus18no1/movement1 --bars 1-8 --compare-keys   # .krn
  key B- major (r=0.781)   meter 3/4@m1   tempo 132bpm   in key 88.12% (out: E 8.5, B 1.0)
  vote aarden:B- major, krumhansl:F major, simple:F major, bellman:F major, temperley:F major

$ analyze_score.py /tmp/bwv66.mid --bars 1-2                      # round-tripped MIDI
  parts  Soprano 9 notes A4–E5 | Alto 9 E4–A4 | Tenor 11 A3–E4 | Bass 10 A2–A3
  chart  m1 I | V6   A | E/G#
```

The MIDI run is the argument for `--key`: MIDI carries no key signature, the analyser
re-detects A major from two bars, and every roman numeral shifts relative to the printed
score. Pin it with `--key "f# minor"`.

---

## Feature extraction — a numeric fingerprint

`features.allFeaturesAsList(s)` (`music21/features/base.py:1170`) runs **72 jSymbolic +
20 native = 92 extractors** in ~1.5 s for a chorale, returning a list of lists in
registration order. To get them *named*, drive the `DataSet` yourself:

```python
from music21 import features
from music21.features import jSymbolic, native

ds = features.DataSet(classLabel='')
fes = list(jSymbolic.featureExtractors) + list(native.featureExtractors)
ds.addFeatureExtractors(fes); ds.addData(s); ds.process()
rows = ds.getFeaturesAsList(includeClassLabel=False, includeId=False, concatenateLists=False)
named = {fe().name: (fe.id, rows[i]) for i, fe in enumerate(fes)}
```

The ten that actually tell you something about a composition, with bwv66.6's values:

| id | Feature | bwv66.6 | Read it as |
|---|---|---|---|
| `P8` | Pitch Variety | 24 | distinct pitches used. Under ~8 for a whole piece = static. |
| `P9` | Pitch Class Variety | 10 | distinct pitch classes. 12 = chromatic; 7 = strictly diatonic. |
| `P10` | Range | 34 | semitones from lowest to highest. Compare to your instruments. |
| `R15` | Note Density | 7.24 | notes per second. Under ~1 = sparse; over ~15 = a blur. |
| `QL1` | Unique Note Quarter Lengths | 3 | **the single best mechanical-rhythm detector.** 1–2 = a grid. |
| `QL3` | Most Common QL Prevalence | 0.601 | fraction of notes at the commonest duration. >0.9 = a grid. |
| `M11` | Stepwise Motion | 0.585 | fraction of melodic intervals that are seconds. Singable melody ≈ 0.5–0.7. |
| `M9` | Repeated Notes | 0.145 | fraction of unisons. >0.4 = a stuck sequencer. |
| `CS9` | Triad Simultaneity Prevalence | 0.692 | fraction of verticalities that are triads. Consonance proxy. |
| `K1` | Tonal Certainty (native) | 1.264 | key-detector confidence. <1.0 = ambiguous or atonal. |

Also useful: `T1`/`T2` max and average independent voices (4 / 3.90 — catches accidental
unison collapse), `R22`/`R23` time between attacks and its variability (0.4375 / 0.1875),
`P13`/`P14`/`P15` bass/middle/high register importance (0.184 / 0.767 / 0.049 — a
top-heavy mix shows up here), `m17` direction of motion (0.47; 0.5 is balanced), `R30`
tempo, `R31` time signature, `R36` duration in seconds.

### Compare your piece to a reference

```python
ds = features.DataSet(classLabel='Composer')
ds.addFeatureExtractors(features.extractorsById(
    ['r31', 'r32', 'p1', 'p2', 'p22', 'ql1', 'ql2', 'k1', 'cs9'], ['jSymbolic', 'native']))
ds.addData('bach/bwv66.6', classValue='Bach')
ds.addData('mozart/k155/movement1', classValue='Mozart')
ds.process(); print(ds.getString(outputFmt='csv'))
```
```
Identifier,...,Tonal_Certainty,Unique_Note_Quarter_Lengths,Most_Common_QL,Triad_Simultaneity,Composer
bach/bwv66.6,...,1.2643,3,1.0,0.6923,Bach
mozart/k155/movement1,...,1.3847,14,0.5,0.3680,Mozart
```

`QL1` = 3 for the chorale, 14 for the Mozart quartet — that one number separates hymn
writing from instrumental writing. Formats: `'tab'` (Orange), `'csv'`, `'arff'`
(`music21/features/outputFormats.py:56,143,188`); `ds.write('out.csv')` picks by extension.
For one vector without the ceremony: `features.vectorById(s, 'p20')` → the 12-element
pitch-class distribution (`features/base.py:1279`).

---

## Verifying your own output

You wrote it, you cannot hear it. These are the assertions that catch the things that
still render fine and are wrong. Run against a deliberately broken 8-bar two-part piece —
parallel fifths throughout, one duration, no velocities, a cello note below C2:

```python
from music21 import corpus, note, chord, key, tree, instrument
from music21.analysis import discrete, patel, windowed

sc = build_my_piece()             # the Score under test
TARGET = key.Key('d', 'minor')    # what I *meant* to write
fail = []
```

**1 — Did it stay in the key I intended? 2 — Did it drift?**
```python
k = sc.analyze('key')
ok = (k.tonic.name == TARGET.tonic.name and k.mode == TARGET.mode)
# detected d minor r=0.827  target d minor  -> OK

wa = windowed.WindowedAnalysis(sc, discrete.AardenEssen())
data, _ = wa.analyze(8, windowType='noOverlap')
[f'{d[0]}{"" if d[1] == "major" else "m"}' for d in data if d[0]]
# ['Dm', 'Fm', 'Gm', 'Dm', 'C']
```
A *confident* answer a fifth or tritone from what you wrote is a real failure; a
*low-confidence* answer on modal, pentatonic or maqam material is not — the Krumhansl
family only knows common-practice tonality. Windows wandering to unrelated keys where you
wrote no modulation means a wrong chord somewhere.

**3 — Scale conformance, duration-weighted.**
```python
pcs = {p.pitchClass for p in TARGET.getScale().getPitches()}
out = sum(float(n.quarterLength) for n in sc.recurse().notes
          for p in n.pitches if p.pitchClass not in pcs)
tot = sum(float(n.quarterLength) for n in sc.recurse().notes for _ in n.pitches)
# 0.0% of note-duration outside d minor
```
Weight by duration, not note count — a passing chromatic sixteenth is not the same
offence as a whole-note wrong third. Judge the *named* offenders, not the percentage: one
pitch class you cannot explain is the bug.

**4 — Is my voice leading clean?** `music21/voiceLeading.py:90`.
```python
st = tree.fromStream.asTimespans(sc, flatten=True, classList=(note.Note, chord.Chord))
p5 = p8 = ovl = 0
for v in st.iterateVerticalities():
    for q in v.getAllVoiceLeadingQuartets():      # tree/verticality.py:942
        p5 += q.parallelFifth(); p8 += q.parallelOctave(); ovl += q.voiceOverlap()
# parallel 5ths=7  parallel 8ves=0  overlaps=0  -> FAIL
```
Also on `VoiceLeadingQuartet`: `hiddenFifth()`/`hiddenOctave()` (`voiceLeading.py:953,960`),
`voiceCrossing()` (`:995`), `antiParallelMotion()` (`:680`), `isProperResolution()`
(`:1024`), `motionType()` (`:294`). Whether parallel fifths are a *failure* is a style
question — in rock or organum they are the point. Count them, then decide.

The corpus ships a regression fixture, so you can confirm your detector works before
trusting it. Report the **measure number**, not the offset — that is what a human acts on:

```python
fixture = corpus.parse('demos/chorale_with_parallels')
# ... same loop over its verticalities, printing f'm{v.measureNumber}' ...
# P8 m1 2.0  v1n1=C#5 v1n2=D5 / v2n1=C#3 v2n2=D3
# P8 m2 3.0  v1n1=D5  v1n2=E5 / v2n1=D3  v2n2=E3
# P8 m4 9.0  v1n1=A#5 v1n2=B5 / v2n1=A#4 v2n2=B4
# P5 m4 9.0  v1n1=C#5 v1n2=D5 / v2n1=F#3 v2n2=G3
```
The same loop over `bach/bwv66.6` returns zero — that is the point of the fixture.

**5 — How dissonant is it, actually?**
```python
diss = tot_v = 0
for v in st.iterateVerticalities():
    c = v.toChord()
    if len(c.pitches) < 2: continue
    tot_v += 1
    diss += not c.isConsonant()
# bwv66.6: 17/51 = 33.3%   |  the broken piece: 0/32 = 0.0%
```
Zero dissonance over dozens of verticalities means nothing is moving against anything.

**6 — Is my rhythm too uniform? 7 — Did I ever vary dynamics?**
```python
durs    = sorted({float(n.quarterLength) for n in sc.recurse().notes})
onsets  = {float(n.getOffsetInHierarchy(sc)) for n in sc.recurse().notes}
offbeat = sum(1 for o in onsets if o % 1.0)
npvi    = patel.nPVI(sc.parts[0].flatten())       # music21/analysis/patel.py:15
vels    = {n.volume.velocity for n in sc.recurse().notes}
# durations=2 [1.0, 4.0]  off-beat onsets=0  nPVI=0.0  velocities={None}  -> FAIL, FAIL
```
`nPVI` is the normalised pairwise variability index — the average percentage difference
between successive durations. **0.0 means every note is the same length.** bwv66.6 scores
9.09; a swung or speech-rhythm line scores 40+. Under ~15 with fewer than 3 distinct
durations is a machine. `{None}` velocities means MIDI will render everything at 90.

**8 — Ambitus vs the target instrument's actual range.**
```python
for p in sc.parts:
    span = discrete.Ambitus().getPitchSpan(p)
    inst = p.getInstrument()
    lo, hi = inst.lowestNote, inst.highestNote
    bad = (lo is not None and span[0].ps < lo.ps) or (hi is not None and span[1].ps > hi.ps)
# top  D5-A5  vs Violin G3-None       -> OK
# bot  G1-D5  vs Violoncello C2-None  -> FAIL
```
**Only 45 of 116 `Instrument` subclasses carry any range data, and almost all of those
set `lowestNote` only** — `highestNote` is `None` for every string, wind and brass class.
Keyboards are the exception (`Piano` A0–C8, `Harpsichord` F1–F6, `Harp` C1–G♯7). For an
upper bound you must supply your own number.

Aggregate on the broken piece: `FAILURES: ['voiceLeading', 'rhythm', 'dynamics',
'range/bot']`. Also cheap and worth asserting: `len(sc.parts)` matches your intent; every
part has `p.getInstrument(returnDefault=False) is not None`; `sc.duration.quarterLength`
matches the form you planned; `recurse().getElementsByClass(tempo.MetronomeMark)` is
non-empty.

---

## Trees — fast vertical slices

`tree.fromStream.asTimespans` (`music21/tree/fromStream.py:316`) builds an interval tree
of `PitchedTimespan`s. A `Verticality` (`music21/tree/verticality.py:52`) is everything
sounding at one offset, **without constructing a Chord** — that is the speed.

```python
from music21 import tree, note, chord
st = tree.fromStream.asTimespans(s, flatten=True, classList=(note.Note, chord.Chord))
len(st), st.endTime                               # 165 36.0

v = st.getVerticalityAt(6.5)                      # <Verticality 6.5 {E3 D4 G#4 B4}>
v.measureNumber, v.beatStrength                   # 2, 0.125
v.pitchSet; v.pitchClassSet; v.toChord()

for vv in list(st.iterateVerticalities())[:3]:    # tree/timespanTree.py:448
    print(vv.offset, vv.measureNumber, vv.beatStrength, sorted(str(p) for p in vv.pitchSet))
# 0.0 m0 0.25  ['A3', 'C#5', 'E4']
# 0.5 m0 0.125 ['B3', 'B4', 'E4', 'G#3']
# 1.0 m1 1.0   ['A4', 'C#4', 'F#3', 'F#4']
```

**When it beats plain iteration:** `iterateVerticalities()` over bwv66.6 yields the same
51 slices as `chordify()` in **~0.0005 s vs 0.034 s — about 70× faster**, because no
`Chord` objects, no measure rebuilding, no ties. Use the tree when *measuring*
(voice-leading sweeps, dissonance counts, statistics over many scores); use `chordify()`
when you want a Stream you can write out or transform. `chordify` is itself built on the
tree (`stream/base.py:6417`).

```python
st.iterateVerticalitiesNwise(n=3)             # sliding windows -> [0.0, 0.5, 1.0], ...
st.iterateConsonanceBoundedVerticalities()    # groups bounded by consonances (:360)
st.maximumOverlap()                           # max simultaneous voices
st.toPartwiseTimespanTrees()                  # dict of per-part trees
```

`tree.analysis.Horizontality` (`music21/tree/analysis.py:31`) classifies three-note
melodic fragments. `hasPassingTone` / `hasNeighborTone` are **properties, not methods**:

```python
from music21.tree import analysis as tanalysis
pt = nt = 0
for seq in st.iterateVerticalitiesNwise(n=3):
    for part, tss in seq.unwrap().items():
        h = tanalysis.Horizontality(timespans=tss)
        pt += h.hasPassingTone; nt += h.hasNeighborTone
# bwv66.6: passing tones 32, neighbor tones 23
```

---

## Search

`music21/search/base.py`. All searches return **indices into the stream you searched**,
so keep that stream around.

```python
from music21 import search, note
sop = s.parts[0].flatten().notes.stream()

search.noteNameSearch(sop, [note.Note('C#'), note.Note('B'), note.Note('A')])   # [0, 6]
search.rhythmicSearch(sop, [note.Note(quarterLength=q) for q in (1.0, 0.5, 0.5)])  # [9, 33]

# Wildcards, via StreamSearcher (search/base.py:109)
ss = search.StreamSearcher(sop, [note.Note('C#'), search.Wildcard(), note.Note('A')])
ss.algorithms = [search.StreamSearcher.wildcardAlgorithm,
                 search.StreamSearcher.noteNameAlgorithm]
res = ss.run()
[r.index for r in res]       # [0, 6, 21]
res[0].els                   # (<Note C#>, <Note B>, <Note A>)

# Fuzzy / corpus-scale: encode the melody as bytes and use difflib (search/base.py:766)
search.translateStreamToStringNoRhythm(sop[:8])                 # 'IGEGILIG'
search.approximateNoteSearch(query, [cand1, cand2])             # ratio-sorted

# Lyrics (search/lyrics.py:113)
ls = search.lyrics.LyricSearcher(corpus.parse('schubert/Lindenbaum'))
ls.indexText[:56]   # "Am Brunnen vor dem Thore da steht ein Lin denbaum; ich"
ls.search('Brunnen')
# [SearchMatch(mStart=9, mEnd=9, matchText='Brunnen', els=(<Note B>, <Note G#>), ...)]
```

`noteNameSearch` and `rhythmicSearch` take **`Note` objects, not strings** — `['C#','B']`
raises `AttributeError: 'str' object has no attribute 'classes'`. Note the syllable-split
spelling in `indexText` ("Lin denbaum"): search short stems. `LyricSearcher` also accepts
a compiled regex.

Other descriptors worth one line each:

```python
from music21.analysis import elements, segmentByRests, metrical, patel
elements.attributeCount(s.recurse().notes, 'quarterLength')   # {0.5: 58, 1.0: 99, 2.0: 8}
elements.attributeCount(s.recurse().notes, 'name')            # {'C#': 33, 'B': 28, ...}
segmentByRests.Segmenter.getSegmentsList(s.parts[0])          # phrase-ish chunks
segmentByRests.Segmenter.getIntervalList(s.parts[0])          # ['M-2','M-2','M2',...]
patel.melodicIntervalVariability(s.parts[0].flatten())        # 65.287
metrical.labelBeatDepth(part_with_measures)   # metrical.py:29 — stacks one '*' lyric per
                                              # metrical level; downbeat 4, offbeat 16th 1
```

---

## neoRiemannian transforms — re-harmonisation

`music21/analysis/neoRiemannian.py`. Each transform moves **one** note of a major or
minor triad, keeping two common tones. That is exactly what you want for re-harmonising:
the melody usually survives.

| Fn | Line | Name | C major → |
|---|---|---|---|
| `L` | `:60` | Leading-tone exchange (root → down m2) | E minor `B3 E4 G4` |
| `P` | `:109` | Parallel (third flips) | C minor `C4 E-4 G4` |
| `R` | `:146` | Relative (fifth → up M2) | A minor `C4 E4 A4` |
| `S` | `:599` | Slide (keeps the third) | C♯ minor `C#4 E4 G#4` |
| `N` | `:621` | Nebenverwandt | F minor `C4 F4 A-4` |

Each raises `LRPException` on anything that is not a major or minor triad; pass
`raiseException=False` to get the input back unchanged.

Worked re-harmonisation of `I–vi–IV–V` in C, a different transform per chord:

```python
from music21 import roman, key
from music21.analysis import neoRiemannian as nr

k = key.Key('C')
orig = [roman.RomanNumeral(f, k).closedPosition(forceOctave=4, inPlace=False)
        for f in ['I', 'vi', 'IV', 'V']]
ops = {'L': nr.L, 'P': nr.P, 'R': nr.R}

for c, recipe in zip(orig, ['', 'L', 'PL', 'R']):
    out = c
    for op in recipe:
        out = ops[op](out)
    common = len(set(c.pitchClasses) & set(out.pitchClasses))
    print(f'{c.pitchedCommonName:14s} --{recipe or "id":3s}-> {out.pitchedCommonName:14s} '
          f'{[str(p) for p in out.pitches]}  common={common}')
# C-major triad  --id -> C-major triad   ['C4', 'E4', 'G4']    common=3
# A-minor triad  --L  -> F-major triad   ['A4', 'C5', 'F5']    common=2
# F-major triad  --PL -> Db-major triad  ['F4', 'A-4', 'D-5']  common=1
# G-major triad  --R  -> E-minor triad   ['G4', 'B4', 'E5']    common=2
```

`C – F – D♭ – Em` instead of `C – Am – F – G`: the D♭ is a chromatic surprise that still
holds F in common with what preceded it. Chain length controls strangeness — one
transform is a substitution, three is a modulation. Bulk operators:

```python
nr.LRP_combinations(c, 'LPR', simplifyEnharmonics=True)   # apply a string of ops (:286)
nr.completeHexatonic(chord.Chord('C4 E4 G4'), simplifyEnharmonics=True)   # (:398)
# Cm -> Ab -> G#m -> E -> Em -> C     the PL cycle
nr.hexatonicSystem(c)                     # 'northern' (:442)
nr.chromaticMediants(c, 'UFM')            # Eb major; also LFM/USM/LSM (:499)
nr.disjunctMediants(c, 'upper')           # Eb minor (:563)
nr.isNeoR(chord.Chord('C4 E4 G4'), chord.Chord('B3 E4 G4'))   # 'L'  (:198)
nr.isChromaticMediant(c1, c2)             # 'USM' or False (:256)
```

`isNeoR` runs the analysis direction: give it two chords from a score you are studying
and it names the transform relating them, or returns `False`.

---

## Headless graphing

matplotlib is required, **`matplotlib.use('Agg')` must run before you import
`music21.graph`**, and every plot needs `doneAction=None` — the default is `'write'` to a
temp file followed by an OS open (`graph/primitives.py:563`).

```python
import matplotlib; matplotlib.use('Agg')
from music21 import corpus, graph

s = corpus.parse('bach/bwv66.6')
p = graph.plot.HistogramPitchSpace(s, doneAction=None)
p.run(); p.write('/tmp/pitches.png')          # graph/primitives.py:583

g = s.plot('pianoroll', doneAction=None)      # the .plot() shortcut returns the object
g.write('/tmp/pianoroll.png')
```

Shortcut names (`music21/graph/findPlot.py:26`): `pianoroll`, `key`, `ambitus`, `dolan`,
`instruments`; format words `horizontalbar`/`piano`, `histogram`, `scatter`,
`scatterweighted`, `3dbars`, `colorgrid`/`windowed`, `horizontalbarweighted`.

The plot classes worth knowing (`music21/graph/plot.py`):

| Class | Line | Shows |
|---|---|---|
| `HorizontalBarPitchSpaceOffset` | `:1196` | **piano roll** — form and register at a glance |
| `WindowedKey` | `:988` | **key over time as a colour grid** — modulation at a glance |
| `WindowedAmbitus` | `:1017` | register over time |
| `HistogramPitchSpace` / `HistogramPitchClass` | `:630,660` | which notes dominate |
| `HistogramQuarterLength` | `:688` | rhythmic vocabulary — a single spike is a grid |
| `ScatterWeightedPitchSpaceQuarterLength` | `:739` | pitch × duration, dot size = count |
| `Dolan` | `:1274` | **instrumentation over time** — who plays when, by density |
| `Features` | `:1497` | grouped bars comparing feature vectors of several scores |
| `Plot3DBarsPitchSpaceQuarterLength` | `:1412` | scatter-weighted, in 3D |

You cannot see the PNG either — generate `WindowedKey` and `Dolan` **for the human
reviewer** and read the underlying numbers yourself. Every plot exposes `.axisX`/`.axisY`
(`music21/graph/axis.py:45`), `.title`, `.figureSize`, `.dpi`, `.colors`, `.alpha`;
`graph.plot.Features([mine, reference], featureExtractors=[...], doneAction=None)` puts
your piece next to a reference on the same axes.

---

## The bundled corpus — what you can reach offline

**15,112 works in 3,194 files, ~66 MB, zero network.** Counts from the metadata bundle
(`corpus.corpora.CoreCorpus().metadataBundle`), verified on 10.5.0.

| Directory | Works | Files | Format | Collection |
|---|---:|---:|---|---|
| `essenFolksong` | 8545 | 31 | abc | Essen Folksong Collection (German/European folk) |
| `oneills1850` | 2047 | 39 | abc | O'Neill's 1850 (Irish traditional) |
| `palestrina` | 1318 | 1318 | krn | Palestrina — complete masses, motets |
| `airdsAirs` | 1186 | 6 | abc | Aird's Airs (Scottish, 6 books) |
| `ryansMammoth` | 1059 | 1059 | abc | Ryan's Mammoth Collection (American fiddle) |
| `bach` | 433 | 433 | mxl 408, rntxt 20, krn 3, xml 2 | J.S. Bach — chorales + analyses |
| `miscFolk` | 187 | 2 | abc | miscellaneous folk |
| `trecento` | 103 | 103 | xml/mxl | 14th-c. Italian (Landini, Jacopo da Bologna…) |
| `monteverdi` | 97 | 97 | 49 mxl + 48 rntxt | madrigals books 3–5, nearly all with a paired roman-numeral analysis |
| `josquin` | 37 | 8 | abc | Josquin des Prez |
| `beethoven` | 26 | 26 | mxl/krn | quartets Op.18 nos 1/3/4/5, Op.59 nos 1–3, Op.74, Op.132, Op.133 *Grosse Fuge* |
| `mozart` | 16 | 16 | mxl | quartets K80, K155, K156, K458; piano sonata K545 exposition |
| `demos` | 13 | 13 | xml/mxl | test fixtures — `chorale_with_parallels`, `drum_sample`, `two-voices`, chord-symbol suite |
| `haydn` | 9 | 9 | mxl | quartets Op.1 no.1 (5 mvts), Op.74 nos 1–2 |
| `schumann_robert` | 7 | 7 | mxl/xml | quartet Op.41 no.1, *Dichterliebe* no.2, Op.48 no.2 |
| `schumann_clara` | 5 | 5 | mxl/xml | four Polonaises Op.1, Op.17 mvt 3 |
| `nottingham-dataset` | 3 | 1 | abc | Nottingham reels (partial) |
| `leadSheet` | 2 | 2 | mxl | *Alexander's Ragtime Band*, *Jeanie with the Light Brown Hair* |
| `schoenberg` | 2 | 2 | mxl | Op.19 movements 2 and 6 |
| `theoryExercises` | 2 | 2 | mxl | triad exercise, checker demo |

Fifteen more directories hold exactly one piece each — short, tonally clear, non-Bach
test cases: `beach/prayer_of_a_tired_child.musicxml`, `chopin/mazurka06-2.krn`,
`ciconia/quod_jactatur.xml`, `corelli/opus3no1/1grave.xml`, `cpebach/h186.mxl`,
`handel/rinaldo/Lascia_chio_pianga.mxl`, `johnson_j_r/lift_every_voice.mxl`,
`joplin/maple_leaf_rag.mxl`, `liliuokalani/aloha_oe.mxl`, `luca/gloria.xml`,
`lusitano/allor_che_ignuda.mxl`, `schubert/Lindenbaum.xml`, `verdi/laDonnaEMobile.mxl`,
`weber/concertino_clarinet.mxl`, `webern/webern_dormi_jesu_op_16_no_2.mxl`.

**363 works have composer "bach"**, 323 of them four-part chorales. **20 romanText
analysis files** live in `bach/choraleAnalyses/` and **48 more** in `monteverdi/` —
ground-truth roman-numeral readings to check your own analyser against:

```python
a = corpus.parse('bach/choraleAnalyses/riemenschneider001.rntxt')
[r.figure for r in a.recurse().getElementsByClass(roman.RomanNumeral)][:8]
# ['I', 'I', 'IV6', 'V6', 'I', 'V', 'vi', 'IV']       60 RNs, key G major
```

**12,834 of 15,112 works have no composer metadata** (the folk collections) — don't filter
by composer when mining those. Of the 233 composer strings that do exist, none are
normalised: `'J.S. Bach'` (338), `'J. S. Bach'` (20) and `'Bach, Johann Sebastian'` (3)
are three separate values, which is why `corpus.search` does substring matching.

```python
corpus.parse('bach/bwv66.6')                  # exact or partial path
corpus.getComposer('beethoven')               # 26 file paths
corpus.search('bach', field='composer')       # <MetadataBundle {363 entries}>
corpus.search('3/4', field='timeSignature')   # 1875 entries
corpus.search(4, field='numberOfParts')       # 945 entries
corpus.search('bach', field='composer').intersection(
    corpus.search(4, field='numberOfParts'))  # 323 four-part Bach
corpus.manager.listSearchFields()             # 148 fields

# Metadata entries carry pre-computed analysis — filter thousands without parsing any:
dict(list(corpus.corpora.CoreCorpus().metadataBundle)[0].metadata.all())
# {'ambitus': AmbitusShort(semitones=36, ..., pitchLowest='F2', pitchHighest='F5'),
#  'composer': 'J.S. Bach', 'noteCount': 208, 'numberOfParts': 4, 'keySignatureFirst': -1, ...}

# Multi-work files return an Opus, not a Score — this catches everyone with the abc sets:
o = corpus.parse('airdsAirs/book1.abc')       # <class 'music21.stream.base.Opus'>, 200 scores
o.getScoreByNumber(5).metadata.title          # "The Lady's play thing, or Gen Howe's March."
corpus.parse('airdsAirs/book1.abc', number=5) # a real Score, directly
```

Bach chorale helpers (`music21/corpus/chorales.py`):

```python
from music21.corpus import chorales
chorales.ChoraleList().byBWV[250]             # 186 entries, cross-numbered
# {'title': 'Was Gott tut, das ist wohlgetan', 'bwv': 250, 'kalmus': 339,
#  'baerenreiter': 346, 'budapest': 342, 'riemenschneider': 347, 'notes': ''}
len(chorales.ChoraleListRKBWV().byRiemenschneider)   # 371

[c.metadata.title for c in chorales.Iterator(numberingSystem='riemenschneider',
                                             currentNumber=1, highestNumber=4)]
# ['Aus meines Herzens Grunde', 'Ich dank’ dir, lieber Herre',
#  'Ach Gott, vom Himmel sieh’ darein', 'Es ist das Heil uns kommen her']
```
`Iterator` defaults to `'riemenschneider'`; BWV numbering starts at 250, so
`Iterator(1, 5, numberingSystem='bwv')` raises `BachException`.

### Your own scores as a corpus

```python
from music21 import corpus
lc = corpus.corpora.LocalCorpus('scratch')
lc.addPath('/path/to/my/scores')              # corpus/corpora.py:802
lc.getPaths()                                 # [PosixPath('.../tune0.musicxml'), ...]
lc.save()                                     # persist the named corpus to settings
lc.removePath('/path/to/my/scores')
```
`corpus.addPath(fp)` adds to the default unnamed local corpus. **Do not call
`cacheMetadata()` casually** — it forks a multiprocessing pool and took over two minutes
on two files here. You do not need it for `getPaths()` / `corpus.parse`, only for
`corpus.search` over local files.

---

## Gotchas

1. **`removeRedundantPitches=True` is the chordify default.** It removes duplicate
   `nameWithOctave`, not duplicate pitch classes, so octave doublings survive. If you are
   counting voices per verticality, pass `False` — or use the tree, which never merges.
2. **Roman numerals in minor keys are measured against harmonic minor.** A natural VII
   comes back as `bVII`. Use `rn.romanNumeralAlone` and `rn.scaleDegree` for the
   accidental-free form. Not a bug.
3. **`harmony.chordSymbolFigureFromChord` returns the sentence
   `'Chord Symbol Cannot Be Identified'`** rather than raising or returning `None`. Test
   for it; fall back to `chord.pitchedCommonName`.
4. **`analysis.reduceChords.ChordReducer` is broken** in 10.5.0 *and* in v11 HEAD:
   `fillMeasureGaps` puts an unhashable `PitchedTimespan` into a `set`
   (`music21/analysis/reduceChords.py:451`). Roll your own per-bar reduction — weight
   pitch-class sets by `duration × beatStrength` as `analyze_score.py` does.
5. **`MelodicIntervalDiversity.getSolution()` is broken** — it passes the stream into the
   `found=` parameter (`discrete.py:1290`). Use `countMelodicIntervals()` directly.
6. **`tree.analysis.Horizontality.hasPassingTone` / `.hasNeighborTone` are properties.**
   Calling them raises `TypeError: 'bool' object is not callable`.
7. **`search.noteNameSearch` / `rhythmicSearch` take `Note` objects, not strings.**
   `['C#', 'B']` raises `AttributeError: 'str' object has no attribute 'classes'`.
8. **`WindowedAnalysis.analyze(n, windowType='noOverlap')` warns and behaves oddly** when
   the piece length is not divisible by the window size. Trim or accept the ragged last
   window.
9. **`highestNote` is `None` for 44 of the 45 instrument classes that have any range
   data** — every string, wind and brass. `lowestNote` is reliable; upper bounds are your
   problem. See `references/09-instruments-and-notation.md`.
10. **Set `matplotlib.use('Agg')` before importing `music21.graph`,** and pass
    `doneAction=None` to every plot, or music21 shells out to open a viewer.
11. **A MetronomeMark is duplicated into every Part** by most parsers. Dedupe on
    `(offset, bpm)` or your tempo list will be four copies of one marking.
12. **Multi-work abc files parse to `Opus`, not `Score`.** `corpus.parse(path, number=N)`
    or `opus.getScoreByNumber(N)`.
13. **`Quality` (`P22`) is registered in both the jSymbolic and native extractor lists**,
    so `allFeaturesAsList` and `DataSet` emit a duplicate column. Harmless, but do not
    index features by name assuming uniqueness.
14. **Key detection on short excerpts is unreliable by design.** Under ~8 bars the
    profiles routinely return the dominant or the relative. Analyse the whole piece, then
    use `floatingKey` for local answers.
15. **`LocalCorpus.cacheMetadata()` forks a process pool and can take minutes.** Avoid it
    unless you genuinely need `corpus.search` over local files.
