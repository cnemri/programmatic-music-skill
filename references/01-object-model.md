# The music21 Object Model and Stream System

What this chapter is for: you generate music as code and render it without ever hearing it, so
every structural decision must be verifiable by inspection. It tells you what a `Stream` is,
what an offset is, when music21 silently rewrites your data, and which composition style to
use. Every example was executed on **music21 10.5.0** (PyPI stable); line citations are to the
**v11.0.0b8 tree**, whose `stream/base.py` API differs only by `Stream.hasElement` (10.5 only).

---

## 1. The cast, in one screen

```
ProtoM21Object            music21/prebase.py:22   -- .classes, .classSet, __repr__. No offset. Pitch/Duration/Tuplet.
  Music21Object           music21/base.py:341     -- can live in a Stream. .offset .duration .sites .activeSite
                                             .derivation .priority .groups .id .style .editorial
    Stream                music21/stream/base.py:115  -- a Music21Object that CONTAINS Music21Objects
      Voice, Measure, Part, PartStaff, Score, Opus, SpannerStorage, VariantStorage
```

Non-negotiable facts:

* A `Stream` is **not** a list. It is `_elements: list` + `_offsetDict: {id(el): (offset, el)}`
  + `_endElements: list` (`music21/stream/core.py:55-62`). An element's offset is stored **in the
  container**, not in the element.
* One element can be in many Streams at once with a **different offset in each**. That is the
  central design fact and the source of most bugs.
* `Duration` and `Pitch` are *not* `Music21Object`s and cannot be inserted into a Stream.
* Equality is bizarre: `Music21Object.__eq__` compares class + `equalityAttributes`, which
  defaults to `('duration',)` (`music21/base.py:451`, `music21/base.py:549`). `__hash__` is `id(self) >> 4`
  (`music21/base.py:563`). So `note.Note('C') == note.Note('G')` is **False** only because `Note` adds
  `pitch` to its equality attributes — but two `Music21Object()`s with equal durations are
  `==`. **Always compare with `is`.**

```python
note.Note('C4').classes
# ('Note', 'NotRest', 'GeneralNote', 'Music21Object', 'ProtoM21Object', 'object')
```

`classSet` (`music21/prebase.py:127`) also holds the class objects and qualified strings, so
`'music21.note.Note' in n.classSet` and `note.Note in n.classSet` both work.

---

## 2. The two composition styles

This is the first decision you make and it determines everything downstream.

### Style A — absolute offsets in a flat Part (`insert`)

Use when timing is the content: micro-timing, swing, rubato, tape-music/generative work,
anything where you render to MIDI/audio and notation is secondary or non-existent.

```python
from music21 import *

p = stream.Part()
p.insert(0, instrument.Piano())
p.insert(0, tempo.MetronomeMark(number=96))
for off, pit, ql in [(0.0, 'C4', 0.5), (0.5, 'E4', 0.5), (1.0, 'G4', 1.0), (1.75, 'B4', 0.25)]:
    p.insert(off, note.Note(pit, quarterLength=ql))
sc = stream.Score([p])
sc.show('text')
```

```
{0.0} <music21.stream.Part 0x106caf0e0>
    {0.0} <music21.instrument.Piano 'Piano'>
    {0.0} <music21.tempo.MetronomeMark Quarter=96>
    {0.0} <music21.note.Note C>
    {0.5} <music21.note.Note E>
    {1.0} <music21.note.Note G>
    {1.75} <music21.note.Note B>
```

`p.hasMeasures()` is `False`, `p.highestTime` is `2.0`. Overlaps are legal. Gaps are legal.
Offsets are exactly what you wrote.

**Micro-timing survives MIDI export exactly**, at 10080 ticks/quarter:

```python
p = stream.Part(); p.insert(0, tempo.MetronomeMark(number=120))
for off in [0.0, 0.97, 2.03, 3.0]:
    p.insert(off, note.Note('C4', quarterLength=0.9))
stream.Score([p]).write('midi', fp='/tmp/micro.mid')
# raw ticks written: NOTE_ON 0 / NOTE_OFF 9072 (0.9) / NOTE_ON 9778 (0.97004) /
#                    NOTE_OFF 18850 / NOTE_ON 20462 (2.02996) ...
```

But `converter.parse('/tmp/micro.mid')` gives back `0.0, 1.0, 2.0, 3.0` — the **reader**
quantizes by default. Use `converter.parse(fp, quantizePost=False)` to see what you wrote.

### Style B — Measures + `append` + `makeNotation`

Use when the deliverable is engraved notation (MusicXML/LilyPond/PDF), or when you need
beams, ties over barlines, accidental logic, tuplet brackets.

```python
p = stream.Part(id='rh')
p.insert(0, instrument.Piano())
p.append(clef.TrebleClef())
p.append(key.KeySignature(-1))
p.append(meter.TimeSignature('6/8'))
for pitches, ql in [(['C4'],0.5), (['E4'],0.5), (['G4'],0.5),
                    (['F4'],1.0), (['A4'],0.5),
                    (['G4','B4'],1.5), (['C5'],1.5)]:
    p.append(note.Note(pitches[0], quarterLength=ql) if len(pitches) == 1
             else chord.Chord(pitches, quarterLength=ql))
sc2 = stream.Score([p]).makeNotation()      # returns a COPY
sc2.show('text')
```

```
{0.0} <music21.stream.Part rh>
    {0.0} <music21.stream.Measure 1 offset=0.0>
        {0.0} <music21.instrument.Piano 'Piano'>
        {0.0} <music21.clef.TrebleClef>
        {0.0} <music21.key.KeySignature of 1 flat>
        {0.0} <music21.meter.TimeSignature 6/8>
        {0.0} <music21.note.Note C>
        {0.5} <music21.note.Note E>
        {1.0} <music21.note.Note G>
        {1.5} <music21.note.Note F>
        {2.5} <music21.note.Note A>
    {3.0} <music21.stream.Measure 2 offset=3.0>
        {0.0} <music21.chord.Chord G4 B4>
        {1.5} <music21.note.Note C>
        {3.0} <music21.bar.Barline type=final>
```

You can also build `Measure` objects yourself and `append` them to the Part; then measure
offsets are `Part`-relative and note offsets are `Measure`-relative. Do this when you want
control over measure numbers, barlines, anacrusis (`m.padAsAnacrusis()` → `paddingLeft`), or
explicit `Voice`s.

### Trade-offs

| | Style A (flat + `insert`) | Style B (Measures + `append`) |
|---|---|---|
| Offset semantics | absolute in the Part | note-in-measure; measure-in-part |
| Overlap/polyphony | free; `makeVoices` later | must be in explicit `Voice`s |
| Micro-timing | exact | `makeNotation` will notate it as ugly tuplets |
| Gaps | legal, silent | need `makeRests` |
| `.append` cost | O(1) amortized | O(1) amortized |
| `.insert` cost | **O(n²)** — see §11 | n/a |
| Notation quality | needs `makeNotation` (a copy) | already good |

**Rule:** compose in Style A when the target is audio; convert to Style B *once*, at export
time, via `makeNotation()` (which copies) or by letting `.write('musicxml')` do it. Never
compose micro-timed material into `Measure`s and expect the notation to be readable — a note
at offset `0.51` becomes `Fraction(51, 100)` with a 25:16 tuplet.

---

## 3. `insert` vs `append` vs `storeAtEnd` vs `.elements =`

```python
s.insert(offset, el)      # music21/stream/base.py:2204 -- place at explicit offset
s.insert(el)              # uses el.getOffsetBySite(el.activeSite) -- its CURRENT offset
s.insert([o1, e1, o2, e2])# legacy alternating list form; still works in 10.5.0
s.append(el)              # music21/stream/base.py:2534 -- place at s.highestTime, then advance it
s.append([e1, e2, e3])    # sequential, each after the previous
s.storeAtEnd(el)          # music21/stream/base.py:2655 -- _endElements; sorts after everything
s.insertAndShift(o, el)   # push later elements right
```

* `append` uses `highestTime`, i.e. the **latest release** of any element, not the last
  element's offset. Appending after a long overlapping note jumps past it.
* `storeAtEnd` **raises** for anything with non-zero duration (`music21/stream/base.py:2694`).
  `m.rightBarline = bar.Barline('final')` uses it. Its offset reads as `highestTime` unless
  you ask: `m.elementOffset(b, returnSpecial=True)` → `<OffsetSpecial.AT_END>`.
* Inserting the *same object* twice into the *same* Stream raises
  `StreamException: the object (...) is already found in this Stream`.
* `.elements = iterable` (`music21/stream/base.py:912`) replaces contents wholesale, taking each
  element's **current/naive** offset. Fresh notes all have offset 0, so they stack:

```python
c = stream.Stream()
c.elements = (note.Note('E4'), note.Note('F4'))
print([(e, e.offset) for e in c])
# [(<music21.note.Note E>, 0.0), (<music21.note.Note F>, 0.0)]
```

* `Stream([e1, e2, ...])` (`music21/stream/base.py:328`) **appends** if every given element has offset
  0.0, otherwise inserts at their offsets (`music21/stream/base.py:369`); with all-`Part`/`Voice`
  children it inserts instead, so parts are simultaneous. Force it with
  `givenElementsBehavior=stream.enums.GivenElementsBehavior.INSERT`.

**Mutating a duration after `append` does not re-flow anything.** Offsets were already fixed:

```python
s = stream.Stream(); n = note.Note('C4', quarterLength=1)
s.append(n); s.append(note.Note('D4', quarterLength=1))
n.duration.quarterLength = 4
print([(e.offset, e.duration.quarterLength) for e in s], s.highestTime)
# [(0.0, 4.0), (1.0, 1.0)] 4.0        <- D4 is now buried inside C4
s.append(note.Note('E4'))
# E4 lands at 4.0, not 2.0
```

---

## 4. Offsets are `float` **or** `Fraction`: `opFrac`

Every offset and quarterLength passes through `common.opFrac`
(`music21/common/numberTools.py:246`), which returns a `float` when the value is exactly
representable in binary, and a `Fraction` otherwise, with denominator capped at
`defaults.limitOffsetDenominator == 65535` (`music21/defaults.py:39`).

```python
common.opFrac(3)            # 3.0
common.opFrac(1/4)          # 0.25
common.opFrac(1/3)          # Fraction(1, 3)
common.opFrac(Fraction(2,4))# 0.5     <- reduced back to float
common.opFrac(0.99999999842)# 1.0
```

Consequences you will hit:

```python
s = stream.Stream()
for i in range(3):
    s.append(note.Note(quarterLength=Fraction(1,3)))
print([repr(e.offset) for e in s], repr(s.highestTime))
# ['0.0', 'Fraction(1, 3)', 'Fraction(2, 3)'] '1.0'
```

Triplets sum **exactly** to 1.0. Using `0.3333333333333333` floats also gives `1.0`, because
`opFrac` snaps them to `Fraction(1,3)` on the way in.

```python
s = stream.Stream(); n = note.Note('E4')
s.insert(Fraction(1, 100000), n)
print(repr(s.elementOffset(n)))     # Fraction(1, 65535)
```

`Stream.insert` does `offset = float(offset)` (`music21/stream/base.py:2314`) before
`coreSetElementOffset` re-fractionalizes it (`music21/stream/core.py:198`). Round-trip is exact for
any denominator ≤ 65535; **finer offsets are silently snapped**.

And the killer for computed durations:

```python
note.Note('C4', quarterLength=0.51).duration.quarterLength   # Fraction(51, 100)
duration.Duration(0.16).tuplets    # (<music21.duration.Tuplet 25/16/512th>,)
```

Rules:
* Never test offsets with `==` against a float literal you computed by division. Compare
  `opFrac(x) == opFrac(y)`, or use `Fraction` throughout.
* Never round-trip offsets through `float()` yourself.
* Build tuplet durations as `Fraction(1,3)`, not `0.333`.
* If you generated offsets from a physical model / random process, run `.quantize()` before
  notating (see §10).

---

## 5. Sorting: `sortTuple`, `priority`, `classSortOrder`, `autoSort`

Order inside a Stream is decided by `SortTuple` (`music21/sorting.py:40`), produced by
`Music21Object.sortTuple()` (`music21/base.py:2632`):

```
(atEnd, offset, priority, classSortOrder, isNotGrace, insertIndex)
```

`classSortOrder` values you will care about (all verified on 10.5.0):

```
TextExpression  -30    Instrument      -25    Stream          -20
Metadata        -30    SystemLayout    -10    Barline          -5
Clef              0    MetronomeMark     1    KeySignature      2
TimeSignature     4    Dynamic          10    Note/Rest/Chord  20
```

So at offset 0 a `Clef` always precedes a `KeySignature` precedes a `TimeSignature` precedes
notes, regardless of insertion order. Override per-element with `.priority` (an int, default
0, `music21/base.py:2829`), which beats `classSortOrder`:

```python
s = stream.Stream(); a = note.Note('A'); b = note.Note('B')
s.insert(0, a); s.insert(0, b)
[x.name for x in s]                     # ['A', 'B']   (insertIndex tiebreak)
b.priority = -1; s.sort(force=True)
[x.name for x in s]                     # ['B', 'A']

# grace notes sort before non-grace at the same offset via isNotGrace:
n = note.Note('C4'); n.duration = duration.GraceDuration(type='eighth')
s = stream.Stream(); s.append(n); s.append(note.Note('D4'))
[e.sortTuple().shortRepr() for e in s]  # ['0.0 <0.20.[Grace].N>', '0.0 <0.20.N+1>']
                                        # shortRepr is 'offset <priority.classSortOrder.insertIndex>';
                                        # insertIndex is a PROCESS-GLOBAL counter, never stable across runs
```

**Sorting is lazy and mutating.** `insert` sets `isSorted=False`; the *first read* of
`s[0]`, `len`, iteration, `.notes`, `.show()`, … calls `sort()` (`music21/stream/base.py:7642`),
which reorders `_elements` **in place**:

```python
s = stream.Stream(); s.insert(10, note.Note('A')); s.insert(0, note.Note('B'))
print(s.isSorted, s._elements)   # False [<Note A>, <Note B>]
print(s[0])                      # <music21.note.Note B>
print(s.isSorted, s._elements)   # True  [<Note B>, <Note A>]
```

If you need insertion order preserved, set `s.autoSort = False` before inserting; then
iteration yields raw order and `s.sorted()` returns a sorted shallow copy.

---

## 6. `activeSite`, `sites`, and why bare `.offset` lies

`el.offset` (`music21/base.py:2494`) is *not* stored on the element. It is
`el.activeSite.elementOffset(el)`. `activeSite` is a **weakref to whichever Stream touched
the element most recently** (`music21/base.py:2434`), and iterating a Stream sets it on every element
it yields.

```python
n = note.Note('C4')
a = stream.Stream(); b = stream.Stream()
a.insert(0, n); b.insert(5, n)
print(n.getOffsetBySite(a), n.getOffsetBySite(b), n.offset)
# 0.0 5.0 5.0        <- bare .offset reports the last site touched
```

Safe accessors, cheapest first:

| call | meaning | measured (M-series, 10.5.0) |
|---|---|---|
| `strm.elementOffset(el)` | offset in `strm`; raises if absent | 0.16 µs |
| `el.getOffsetBySite(strm)` | same, but follows `.derivation.origin` on miss (`music21/base.py:942`) | 0.27 µs |
| `el.getOffsetInHierarchy(score)` | cumulative offset through nested Streams (`music21/base.py:1120`) | 25 µs |
| `recursiveIterator.currentHierarchyOffset()` | same, during a `recurse()` | ~10× faster |
| `el.offset` | whatever site was touched last | fast and **wrong** |

`el.sites` (`music21/sites.py:179`) holds weak references to every Stream the element has ever been
added to, plus `None`. Dead sites are purged lazily. `el.purgeOrphans()` /
`el.purgeLocations()` force it.

A short-lived site (e.g. the Stream made by `.stream()`) can die between calls; then `.offset`
falls back to `_activeSiteStoredOffset` (`music21/base.py:2604`) — a stale number with no error.

---

## 7. `flatten()` vs `recurse()` vs `.notes`

* `.flatten()` (`music21/stream/base.py:7783`) returns a **new Stream containing the same element
  objects**, re-inserted at their hierarchy offsets. `retainContainers=True` also keeps the
  sub-Streams ("semiFlat").
* `.recurse()` (`music21/stream/base.py:8084`) returns a `RecursiveIterator` — no new Stream, no
  re-offsetting, lazy.
* `.notes` / `.notesAndRests` / `.getElementsByClass(...)` return a `StreamIterator` that
  looks **only at the Stream's own `_elements`** — they do not descend.
* `.pitches` returns a plain `list[Pitch]`.
* **`.flat` was removed.** On 10.5.0 `score.flat` raises
  `AttributeError: 'Score' object has no attribute 'flat'`.

```python
sc = stream.Score([stream.Part([stream.Measure([note.Note('C4')])])])
len(sc.notes)             # 0    <- the classic zero-notes surprise
len(sc.recurse().notes)   # 1
len(sc.flatten().notes)   # 1
```

### The offsets trap

`recurse()` yields elements whose `.offset` is **container-relative**; `flatten()` yields
absolute:

```python
# 3 measures of 4 quarter notes
for el in sc.recurse().notes[:5]: print(el.offset)   # 0.0 1.0 2.0 3.0 0.0
for el in sc.flatten().notes[:5]: print(el.offset)   # 0.0 1.0 2.0 3.0 4.0
```

Which silently corrupts offset filters:

```python
b = corpus.parse('bach/bwv66.6')
len(b.recurse().getElementsByClass(note.Note).getElementsByOffset(0, 2))       # 133  (WRONG)
len(b.recurse().getElementsByOffsetInHierarchy(0, 2).notes)                    # correct
len(b.flatten().notes.getElementsByOffset(0, 2))                               # correct
```

### `flatten()` mutates your originals' `activeSite`

`flatten()` itself inserts with `setActiveSite=False` (`music21/stream/base.py:8050`), so calling it
is safe. **Touching the result is not** — the shared note objects get re-pointed:

```python
n2 = p2.getElementsByClass(stream.Measure)[1].notes[0]
print(n2.offset)          # 0.0   (measure-relative)
fl = p2.flatten(); list(fl)
print(n2.offset)          # 4.0   (now Part-relative -- same object!)
print(p2.getElementsByClass(stream.Measure)[1].notes[0].offset)  # 0.0 again (re-pointed back)
```

So: `.offset` read anywhere near a `flatten()` is a coin flip. Use `getOffsetBySite`.

### Caching

`flatten()` caches into `self._cache['flatten']` (`music21/stream/base.py:8000`), so repeated calls
return the *same object*; any structural change clears the cache via `coreElementsChanged`
(`music21/stream/core.py:296`).

```python
f1 = bwv.flatten(); f2 = bwv.flatten(); f1 is f2      # True
bwv.insert(0, note.Note('C4')); bwv.flatten() is f1   # False
```

### Preferred idioms

```python
score.recurse().notes                        # iterate everything, cheap
score.recurse().getElementsByClass(chord.Chord)
score['Note']                                # == score.recurse().getElementsByClass('Note')
score[note.Note]                             # same, class form
score.recurse().notes.stream()               # flat Stream WITH hierarchy offsets (music21/stream/iterator.py:782)
score.flatten().notes                        # flat Stream, cached, absolute offsets
part.getElementsByClass(stream.Measure)      # one level only -- what you want for measures
```

Iterator methods chain and are lazy; `.stream()` materializes. `.first()`, `.last()`,
`len()`, `in`, slicing all work on iterators. Do **not** access Stream-only attributes on an
iterator (`s.notes.pop(0)`) — `StreamIterator.__getattr__` (`music21/stream/iterator.py:220`) builds a whole
throwaway Stream per call and is deprecated.

Never combine `flatten(retainContainers=True)` with `flatten()`; the same object then appears
three times (`music21/stream/base.py:7970`).

---

## 8. Contexts and derivations

`getContextByClass` (`music21/base.py:1350`) walks backwards through the element's hierarchy — its
Measure, then earlier Measures, then the Part — to find the governing object. This is how you
answer "what key/meter/clef/tempo is in force here".

```python
n = m2.notes[1]                              # 2nd note of measure 2
n.getContextByClass(meter.TimeSignature)     # <music21.meter.TimeSignature 3/4>
n.getContextByClass(key.Key)                 # D major
n.getContextByClass(stream.Measure)          # <music21.stream.Measure 2 offset=3.0>
n.getContextByClass(stream.Part)             # <music21.stream.Part P1>
n.measureNumber, n.beat, n.beatStr, n.beatStrength   # 2, 2.0, '2', 0.5
```

Search direction is controlled by `getElementMethod=ElementSearch.BEFORE / AFTER /
AT_OR_BEFORE (default) / ALL / ..._OFFSET`. `n.next(cls)` / `n.previous(cls)` are friendlier
wrappers.

`contextSites()` (`music21/base.py:1850`) enumerates the containment chain with cumulative offsets:

```
ContextTuple(site=<music21.stream.Measure 2 offset=3.0>, offset=1.0, recurseType=<RecursionType.ELEMENTS_FIRST>)
ContextTuple(site=<music21.stream.Part P1>,             offset=4.0, recurseType=<RecursionType.FLATTEN>)
ContextTuple(site=<music21.stream.Score 0x...>,         offset=4.0, recurseType=<RecursionType.ELEMENTS_ONLY>)
```

`.derivation` (`music21/derivation.py:68`) records where a derived object came from. Every
copy/transform sets it:

```python
t = sc.transpose('M3')
t.derivation                 # <Derivation of <Score ...> from <Score ...> via 'transpose'>
t.derivation.method          # 'transpose'
t.derivation.origin is sc    # True
t.derivation.rootDerivation  # the original Score (a property, NOT a method)
sc.flatten().derivation.method   # 'flatten'
```

Derivations are why `getOffsetBySite` works on a copy of an element against the original's
Stream (`music21/base.py:1050`) — a nice trick and an occasional source of surprising non-errors.

---

## 9. The Duration model

`Duration` (`music21/duration.py:1520`) is `components: tuple[DurationTuple]` + `tuplets` + a cached
`quarterLength`. `DurationTuple` (`music21/duration.py:786`) is an immutable `(type, dots,
quarterLength)`.

```python
d = duration.Duration(1/3)
d.type, d.tuplets, repr(d.quarterLength)
# ('eighth', (<music21.duration.Tuplet 3/2/eighth>,), 'Fraction(1, 3)')
d.tuplets[0].tupletMultiplier()      # Fraction(2, 3)

d2 = duration.Duration(0.625)
d2.type, d2.isComplex
# ('complex', True)
d2.components
# (DurationTuple(type='eighth', dots=0, quarterLength=0.5),
#  DurationTuple(type='32nd',  dots=0, quarterLength=0.125))

duration.Duration(type='half', dots=2).quarterLength    # 3.5
duration.Duration(Fraction(1,7)).tuplets                # (<Tuplet 7/4/16th>,)
```

`expressionIsInferred` (`duration.py` `_DOC_ATTR`) is `True` when you created the Duration
from a **number** and `False` when from a **type**. `makeNotation`'s tuplet routines
(`splitElementsToCompleteTuplets`, `consolidateCompletedTuplets`) are only allowed to
re-express durations where it is `True`:

```python
duration.Duration(0.5).expressionIsInferred      # True   -- makeNotation may rewrite it
duration.Duration('eighth').expressionIsInferred # False  -- frozen

# linked (music21/duration.py:1844): unlink to make a note LOOK like one value, LAST another
d = duration.Duration(1.0); d.linked = False; d.type = 'half'
d.quarterLength, d.type                          # (1.0, 'half')

# GraceDuration (music21/duration.py:3131): always ql 0.0, unlinked, keeps a display type
g = duration.GraceDuration(type='eighth')
g.quarterLength, g.type, g.linked, g.isGrace     # (0.0, 'eighth', False, True)
```

**Set `type=`/`dots=` explicitly when you want music21 to leave your notation alone.** Grace
notes contribute **nothing** to `highestTime` and are **inaudible in MIDI** unless realized.

---

## 10. `makeNotation`: what it runs, when it runs, how to stop it

`Stream.makeNotation` (`music21/stream/base.py:6971`), in order:

1. `coreGatherMissingSpanners()`
2. if no Measures: `makeVoices(fillGaps=True)` then `makeMeasures()`. (The
   `StreamException: no measures found` guard at `music21/stream/base.py:7050` is effectively
   unreachable — `makeMeasures` on an *empty* Part still yields one 4/4 measure containing a
   `TrebleClef`, a `TimeSignature` and a final `Barline`.)
3. `makeAccidentalsInMeasureStream(...)` — unless `streamStatus.accidentals` is truthy
4. `makeTies()` — splits notes across barlines, adds `Tie` objects
5. per measure: `splitElementsToCompleteTuplets`, `consolidateCompletedTuplets(onlyIfTied=True)`
6. `makeBeams()` — unless `streamStatus.beams` is truthy
7. per measure: `makeTupletBrackets()` — unless `m.streamStatus.tuplets`

`Score.makeNotation` (`music21/stream/base.py:14291`) delegates to each Part. `Measure.makeNotation`
(`music21/stream/base.py:13126`) does accidentals + beams + tuplet brackets only — **no makeTies**,
because ties are cross-bar.

The individual pieces (`stream/makeNotation.py`):

| function | what it does | destructive? |
|---|---|---|
| `makeMeasures` (:232) | chops a flat Stream into `Measure`s using TimeSignatures found (default 4/4); adds clef, final barline; does **not** pad the last bar | `inPlace` opt |
| `makeRests` (:711) | fills leading space and (with `fillGaps=True`) internal gaps with `Rest`s; recurses into Parts/Measures/Voices | `inPlace` opt |
| `makeTies` (:987) | splits notes overflowing a barline into tied notes in the next measure; does **not** shift anything | `inPlace` opt |
| `makeBeams` (:51) | sets `.beams` from the TimeSignature's beat structure | `inPlace` opt |
| `makeAccidentalsInMeasureStream` (:1644) | sets `pitch.accidental.displayStatus` per measure w/ key-signature + carry-over logic | in place |
| `makeVoices` (:11157 in base) | separates overlapping material into `Voice`s | `inPlace` opt |
| `makeTupletBrackets` (:1369) | sets `Tuplet.type` start/stop for brackets | `inPlace` opt |
| `splitElementsToCompleteTuplets` (:1959) | splits a note so a partial tuplet group completes | **always in place** |
| `consolidateCompletedTuplets` (:2035) | merges a tied 1/3+1/3+1/3 back into a plain note | **always in place** |
| `realizeOrnaments` (:1492) | expands Trill/Mordent/Turn into real notes; returns a **new** Stream | not in place |

### When it runs behind your back

* **`.write('musicxml')` / `.show()`**: `GeneralObjectExporter` deep-copies, runs `makeRests`,
  wraps in a Score, and calls `Score.makeNotation` on the *copy*
  (`music21/musicxml/m21ToXml.py:346, 402, 428`). **Your original is untouched** — verified:

  ```python
  # before write: displayStatus [None, None, None, None] beams [False, False, False, False]
  # after  write: displayStatus [None, None, None, None] beams [False, False, False, False]
  # after makeNotation(inPlace=True): displayStatus [True, False, False, False] beams [True, True, True, True]
  ```

* **`.write('midi')`**: `prepareStreamForMidi` deep-copies, `expandRepeats()`, then
  `makeMeasures(inPlace=True)`, `makeTies`, `makeRests(fillGaps=True)` on the copy
  (`music21/midi/translate.py:2256-2263, 2685`). Again the original is untouched. It does **not** run
  makeBeams/makeAccidentals, and does **not** realize ornaments.
* **`makeNotation(inPlace=True)`** and the `splitElementsToCompleteTuplets` /
  `consolidateCompletedTuplets` helpers *do* mutate.
* **`sort()`** runs on the first read after any `insert` (§5).
* **`activeSite`** is reassigned by any iteration (§6).

### How to suppress it

```python
score.write('musicxml', fp=..., makeNotation=False)   # music21/converter/subConverters.py:914
```

Requirements: the object must be a `Score` **with Measures**, otherwise
`MusicXMLExportException: Cannot export with makeNotation=False if there are no measures`.
Complex (multi-component) durations also fail — run `splitAtDurations(recurse=True)` first.
The MIDI writer accepts the keyword and ignores it.

Finer-grained, and it survives into `write()`:

```python
for part in sc.parts:
    part.streamStatus.beams = True         # music21/stream/streamStatus.py:169 -- "already done", skip makeBeams
    part.streamStatus.accidentals = True   # music21/stream/streamStatus.py:156 -- skip makeAccidentals
    part.streamStatus.tuplets = True       # music21/stream/streamStatus.py:182 -- skip makeTupletBrackets
```

Verified effect on the emitted MusicXML for a bar of four C#-eighths in 2/4:

```
default:               beam tags 4   accidental tags 1
streamStatus flags on: beam tags 0   accidental tags 1
```

Also available: `Stream.makeNotation(..., inPlace=False)` returns a copy so you can diff;
`GeneralObjectExporter().makeNotation = False`; `ScoreExporter(sc, makeNotation=False)`.

---

## 11. Copying: `deepcopy`, `template`, `cloneEmpty`, and shared objects

`Music21Object.__deepcopy__` (`music21/base.py:658` → `_deepcopySubclassable` at `music21/base.py:613`) skips
`_derivation`, `_activeSite`, `_sites`, `_cache` (`music21/base.py:628`), gives the copy a fresh
`Sites()`, sets `derivation.method = '__deepcopy__'`, and calls `purgeOrphans()`. Spanners
inside a copied Stream are re-pointed at the copies:

```python
d = copy.deepcopy(part)
d.spanners.first().getSpannedElements()[0] is d.notes[0]     # True
```

Costs, measured:

```
20 deepcopies of bach/bwv66.6 (165 notes, 4 parts):   0.219 s   (~11 ms each)
20 x .template() of the same:                         0.132 s   (~6.6 ms each)
deepcopy of a 2000-note flat Part:                    0.108 s
```

So a deepcopy is roughly 55 µs per note. Every `inPlace=False` call pays this. In a loop over
4000 events, `x = x.transpose(...)` costs seconds; use `inPlace=True`.

`.template()` (`music21/stream/base.py:4709`) gives you the *scaffolding* — instruments, clefs, keys,
meters, measure structure, barlines — with notes replaced by rests. It is the right way to
build a second voice against an existing part, or an empty score in the same layout:

```python
tpl = sc.template()                 # keeps 40 measures, fills each with a Rest
tpl = sc.template(fillWithRests=False)
tpl = sc.template(removeClasses=('GeneralNote', 'Dynamic'), retainVoices=False)
```

`.cloneEmpty(derivationMethod=...)` (`music21/stream/base.py:1375`) is the low-level version: same
class and attributes, zero elements.

**The shared-object hazard.** A `Music21Object` in two Streams is one object:

```python
n = note.Note('C4'); a.insert(0, n); b.insert(5, n)
n.pitch.name = 'D'
a[0].pitch.name, b[0].pitch.name       # ('D', 'D')
```

This is exactly what `flatten()`, `.stream()`, `getElementsByClass(...).stream()`,
`measures()` and `chordify()`'s internals rely on — and exactly what bites you when you build
a repeated motif by inserting the *same* Note list at four offsets. Always
`copy.deepcopy(motif)` per placement, or rebuild the notes.

---

## 12. Structural surgery you will actually use

All of these default to `inPlace=False` (returning a deep copy) unless noted.

```python
s.transpose('M2')                     # or inPlace=True; also accepts interval.Interval
s.chordify()                          # music21/stream/base.py:6234
s.stripTies(matchByPitch=True)        # 7180 -- merge tied notes back into long notes
s.quantize([4, 3], processOffsets=True, processDurations=True)   # 9311
s.sliceByQuarterLengths([0.5], addTies=True)                     # 9596
s.sliceAtOffsets([1.5, 2.25])                                    # 9716
s.shiftElements(10.0, startOffset=2.0)                           # 5944 -- ALWAYS in place
left, right = s.splitAtQuarterLength(1.5)                        # 3209
sc.measures(2, 4)                     # 4417 -- Score/Part excerpt, renumbered offsets
part.measure(3)                       # 4651 -- one Measure, live reference
s.expandRepeats()                     # 9547 -- writes out repeats
part.makeVoices(fillGaps=True)        # 11157
score.voicesToParts()                 # 11324
part.explode()                        # 11564 -- Part-with-voices -> Score of Parts
score.partsToVoices() / score.implode()   # the inverses
s.offsetMap()                         # 6576 -> [OffsetMap(element, offset, endTime, voiceIndex)]
```

Verified behaviors worth knowing:

```python
# chordify on a Score returns a PART -- it templates off part 1 (music21/stream/base.py:6485)
type(score.chordify())                                       # <class 'music21.stream.base.Part'>

# quantize rescues float-derived garbage
# before: [(0.0, Fraction(51,100)), (Fraction(49,100), Fraction(13,50)),
#          (Fraction(19,25), Fraction(6,25)), (Fraction(101,100), Fraction(99,100))]
# after .quantize([4,3]): [(0.0, 0.5), (0.5, 0.25), (0.75, 0.25), (1.0, 1.0)]

# getElementsByOffset boundaries (notes at 0,1,2,3 each ql 1.5)
p.getElementsByOffset(1.0, 2.0)                              # 2 elements
p.getElementsByOffset(1.0, 2.0, includeEndBoundary=False)    # 1
p.getElementsByOffset(1.0, 2.0, mustBeginInSpan=False)       # 3

# measures() puts collected context objects on the PART at offset 0, not inside measure 1:
#   Instrument, TrebleClef, MetronomeMark, KeySignature, TimeSignature,
#   then <Measure 2 offset=0.0>, <Measure 3 offset=4.0>, ...

# makeNotation auto-voices overlapping material in a flat Part:
#   {0.0} Measure 1 -> {0.0} Voice 0 -> Note C (ql 4)
#                      {0.0} Voice 1 -> Note E (ql 2), Note G (ql 2)

# ornaments are NOT realized by MIDI export
stream.Score([partWithTrill]).write('midi')                              # 1 note in the file
len(stream.makeNotation.realizeOrnaments(partWithTrill).recurse().notes) # 32

# Stream.duration, once set, stops tracking highestTime (music21/stream/base.py:8533)
st.duration = duration.Duration(8.0)
st.duration, st.highestTime                                  # (<Duration 8.0>, 1.0)
```

---

## 13. Performance

### `insert` into a sorted Stream is O(n²)

`Stream.insert` → `coreInsert` reads `self.highestTime` to decide whether sortedness is
preserved (`music21/stream/core.py:109-121`). `highestTime` is a full scan of `_elements`
(`music21/stream/base.py:8458`) whose cache is cleared by every `coreElementsChanged`. Measured
(seconds):

| n | `insert(i, note)` ascending | `insert(..., ignoreSort=True)` + `sort()` | `coreInsert` + `coreElementsChanged` | `append` |
|---|---|---|---|---|
| 500 | 0.035 | 0.005 | 0.002 | 0.004 |
| 1000 | 0.128 | 0.006 | 0.006 | 0.007 |
| 2000 | 0.474 | 0.014 | 0.032 | 0.014 |
| 4000 | **2.025** | 0.033 | 0.021 | 0.030 |

4× per doubling — textbook quadratic. Ironically, inserting in *descending* offset order is
fast (0.015 s for 2000) because `isSorted` goes `False` on the first insert and the
`highestTime` branch is skipped.

**Recipes for bulk building** (both linear, both verified to produce identical Streams):

```python
# A. public API
p = stream.Part()
for off, n in events:
    p.insert(off, n, ignoreSort=True)
p.sort()

# B. core API -- documented as "core", stable enough to use (music21/stream/core.py:71, 211)
p = stream.Part()
for off, n in events:
    p.coreInsert(off, n)
p.coreElementsChanged()        # MANDATORY; leaves isSorted False, sorts on first read
```

`coreInsert` skips `coreGuardBeforeAddElement` — so it will happily let you insert a
non-`Music21Object` or the same object twice and corrupt the Stream. Validate your own input.

### Other costs

* `.flatten()` is O(n log n) and **cached**; `recurse()` is lazy and allocation-free per pass.
  For a 165-note chorale: 50× `flatten().notes` = 6.0 ms (cache hits), 50× `recurse().notes` =
  11.9 ms, 50× notes on a pre-flattened Stream = 5.1 ms. Hoist `fl = score.flatten()` out of
  loops anyway, so a stray mutation cannot silently invalidate and rebuild it.
* `Stream.index()` is cached in `_cache['index']`; `elementOffset` is a dict lookup.
* `sort()` is O(n log n) with a Python-level key function; on 10k+ elements it dominates. Set
  `autoSort = False` while building, sort once at the end.
* `deepcopy` ≈ 55 µs/note (§11). `spannerBundle` and `asTree`/`asTimespans` are cached in
  `_cache` and rebuilt on any change.
* `getOffsetInHierarchy` is ~25 µs vs 0.27 µs for `getOffsetBySite` and 0.16 µs for
  `elementOffset`; inside a `recurse()` use `ri.currentHierarchyOffset()` (`music21/stream/iterator.py:1910`).
* `score.recurse().notes.stream()` builds a flat `Score` with correct hierarchy offsets
  (`music21/stream/iterator.py:782`, max offset 35.0 for `bwv66.6`) and is a good `flatten()` substitute when
  you also want a filter applied.

---

## Gotchas

Every item below was reproduced on music21 10.5.0.

* **`.flat` no longer exists.** `score.flat` → `AttributeError`. Use `.flatten()`.
* **`insert()` into a sorted Stream is O(n²).** 4000 ascending inserts = 2.0 s vs 0.03 s with
  `ignoreSort=True` + `sort()`. Never build large Streams with plain `insert`.
* **`stream.notes` is 0 on any Score/Part with Measures.** `.notes` does not recurse. Use
  `recurse().notes` or `flatten().notes`.
* **`recurse()` offsets are container-relative; `flatten()` offsets are absolute.**
  `b.recurse().notes.getElementsByOffset(0,2)` returns 133 notes of a chorale — nonsense.
  Use `getElementsByOffsetInHierarchy` or flatten first.
* **`el.offset` is whatever Stream touched the element last.** Iterating a flat view rewrites
  it on the shared originals. Always `strm.elementOffset(el)` / `el.getOffsetBySite(strm)`.
* **`flatten()` shares element objects with the original** — mutating a note in the flat view
  mutates the score. So does `.stream()`, `measures()`, and iterators.
* **`opFrac` caps offset denominators at 65535.** `insert(Fraction(1,100000), n)` silently
  stores `Fraction(1,65535)`.
* **Computed float durations become grotesque tuplets.** `quarterLength=0.51` →
  `Fraction(51,100)`; `Duration(0.16)` → a 25:16 tuplet. Quantize or use exact Fractions.
* **Never compare offsets/quarterLengths with `==` on raw floats.** Compare `opFrac(a) == opFrac(b)`.
* **Changing a note's duration after `append` does not re-flow later offsets.** They were
  fixed at append time; the notes now overlap.
* **`append` uses `highestTime`, not the last element's offset** — it jumps past any long
  overlapping note.
* **`.elements = [...]` uses each element's naive offset**, so a list of fresh notes all land
  at 0.0.
* **`Stream([...])` appends when all offsets are 0, inserts otherwise** — and always inserts
  when the children are Parts/Voices. Silent, and different from what you may expect.
* **`storeAtEnd` raises for anything with non-zero duration**, and its offset reads back as
  `highestTime` unless you pass `returnSpecial=True`.
* **Reading a Stream sorts it in place.** `_elements` order changes on first `s[0]`/`len`/iteration.
* **`priority` beats `classSortOrder`**, so a mispriorized note can sort before its own clef.
* **`sortTuple().insertIndex` is a process-global counter.** It differs on every run; never
  assert on it or on the full `shortRepr()` string.
* **`Music21Object.__eq__` compares duration (and class), not identity.** `obj1 in [obj2]` can
  be `True` while `obj1 in {obj2}` is `False`. Use `is`.
* **Inserting the same object twice into one Stream raises**; inserting it into two Streams
  silently gives it two different offsets.
* **MIDI export does not realize ornaments.** A whole note with a `Trill` exports as 1 note;
  `stream.makeNotation.realizeOrnaments()` turns it into 32.
* **Grace notes have `quarterLength == 0.0` and are inaudible in MIDI.**
* **`converter.parse(midi)` quantizes by default**, even though `write('midi')` preserved your
  micro-timing exactly at 10080 ticks/quarter. Use `quantizePost=False` to verify a round trip.
* **`makeNotation=False` only works for MusicXML, only on a `Score`, and only if it already
  has Measures** — otherwise `MusicXMLExportException`. The MIDI writer accepts and ignores it.
* **`makeNotation=False` also rejects complex durations**:
  `MusicXMLExportException: Cannot convert complex durations to MusicXML. Try exporting with
  makeNotation=True or manually running splitAtDurations()` — e.g. any `quarterLength=0.625`.
* **`makeNotation()` on an empty Part silently invents a measure** (TrebleClef + 4/4 + final
  barline) rather than erroring, so "it exported fine" does not mean your notes were there.
* **`splitElementsToCompleteTuplets` and `consolidateCompletedTuplets` are always in place**,
  unlike every other `make*` function. `makeNotation(inPlace=True)` therefore rewrites your
  durations, ties, beams and accidental display flags.
* **`Duration(type='eighth')` has `expressionIsInferred=False` and will not be re-expressed;
  `Duration(0.5)` has `True` and can be split/merged by makeNotation.**
* **`chordify()` on a `Score` returns a `Part`**, not a Score (it templates off part 1).
* **`shiftElements` is always in place** and has no `inPlace` keyword.
* **`Stream.duration = X` decouples duration from `highestTime` permanently** for that Stream.
* **`derivation.rootDerivation` is a property, not a method** — calling it raises
  `TypeError: 'Score' object is not callable`.
* **`coreInsert` skips all validation.** It will accept a duplicate or a non-Music21Object and
  leave the Stream inconsistent; and forgetting `coreElementsChanged()` afterwards leaves
  `isFlat`, `highestTime` and every cache stale.
* **`flatten(retainContainers=True).flatten()` duplicates every element three times.**
* **A short-lived site can die between calls**, after which `.offset` returns a stale cached
  number (`_activeSiteStoredOffset`) with no warning.
