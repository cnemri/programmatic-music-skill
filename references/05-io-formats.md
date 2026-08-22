# I/O and Formats: Getting Music In and Out of music21

Every byte entering or leaving music21 goes through `converter`. This chapter enumerates every
format, what each preserves, and the traps that silently produce garbage instead of raising.
Covers tinyNotation (fastest sketch input), writing MusicXML that opens in MuseScore/Finale,
PDF/PNG requirements, `freezeThaw` caching, and the pickle cache that will hand you a stale
parse without a word. Citations are git HEAD (v11.0.0b8); **all examples executed on 10.5.0**,
Python 3.14, macOS. v11 differences are marked.

## The format matrix

From `Converter.subConvertersList()` at runtime on 10.5.0:

| Format name(s) | Parse | Write | Input ext | Output ext | Fidelity |
|---|---|---|---|---|---|
| `musicxml`, `xml` | yes | **yes** | `.xml .mxl .musicxml` | `.musicxml .xml .mxl` | Reference format. Best fidelity; loss list below. |
| `midi` | yes | **yes** | `.mid .midi` | `.mid` | Pitch/rhythm/tempo/key/TS/instrument/lyrics survive. Dynamics, articulations, slurs, beams, metadata **lost**. |
| `abc` | yes | **no** ⚠ | `.abc` | — | Import only. `write('abc')` emits `repr(obj)`. |
| `humdrum` (kern) | yes | **no** ⚠ | `.krn` | — | Import only. `write('humdrum')` emits `repr(obj)`. |
| `romantext`, `rntext` | yes | **yes** | `.rntxt .rntext .romantext .rtxt` | `.rntxt` | Round-trips RomanNumerals+key+TS. Source must be in Measures. |
| `mei` | yes | no | `.mei` | — | `write`/`show` raise `NotImplementedError` (`subConverters.py:1398`). |
| `capella` | yes | no | `.capx` | — | Import only, uncompressed capx. |
| `musedata` | yes | no | `.md .musedata .zip` | — | Import only; also a directory of parts. |
| `noteworthytext` / `noteworthy` | yes | no | `.nwctxt` / `.nwc` | — | Import only; `.nwc` is `readBinary`. |
| `cttxt`, `har`, `clercqTemperley` | yes | no | same | — | Rock harmony; returns a `Part`. |
| `volpiano` | yes | **yes** | `.volpiano .vp` | `.txt .vp` | Chant: pitch, neume grouping, barlines. No durations. |
| `tinynotation` | yes | **no** | `.tntxt .tinynotation` | — | Input only by design (`subConverters.py:667`). |
| `scala` | **no** ⚠ | **no** ⚠ | `.scl` | `.scl` | Registered but a 4-line stub (`subConverters.py:588`). Use `scale.scala.ScalaFile`. |
| `braille` | no | **yes** | — | `.txt` | Unicode; `braille.ascii` subformat for ASCII. |
| `text`, `txt`, `t` | no | **yes** | — | `.txt` | `obj._reprText()`. The debugging workhorse. |
| `textline` | no | **yes** | — | `.txt` | One-line repr; `show()` **returns** rather than prints. |
| `lilypond`, `lily` | no | yes* | — | `.ly .png .pdf .svg` | *Needs the `lilypond` binary — even for plain `.ly`. |
| `vexflow` | no | yes | — | `.html` | 10.5.0 only; **removed in v11**. jsonpickle+music21j; dead. |
| `ipython`, `jupyter` | no | display | — | — | Notebook only; delegates to MuseScore (png) or music21j (midi). |
| pickle (`freezeThaw`) | `converter.thaw` | `converter.freeze` | `.p .p.gz` | `.p .p.gz` | **Lossless.** Not reachable via `converter.parse()`. |

`registerFormats` / `registerInputExtensions` / `registerOutputExtensions` are class attributes
(`subConverters.py:52-64`). **Order matters for output** — `.write()` uses
`registerOutputExtensions[0]`, which is why bare `write('musicxml')` yields `.musicxml`.

## parse, parseData, parseURL

`converter.parse()` (`converter/__init__.py:1288`) dispatches in this order: a `(path, number)`
pair; a `str` starting with `MThd`; `os.path.exists`; `common.cleanpath` (expands `~`);
`http(s)://`; else `parseData`.

`parseData` sniffs (`__init__.py:681-721`): explicit `format=`; a `"<name>:"` header matched
against every registered format (`formatFromHeader`, `:1076`); then heuristics — `<?xml` → `mei`
if `<mei` present else `musicxml`; `MThd` → midi; `!!!`/`**` → humdrum; `WK#:`+`measure` →
musedata; `M:` **and** `K:` anywhere → abc; `Time Signature:`+`m1` → romanText. Those are loose
enough to misclassify ordinary prose. **Pass `format=` whenever you know it.**

```python
converter.parse("tinyNotation: 4/4 c4 d e f")            # header prefix
converter.parse("4/4 c4 d e f", format='tinyNotation')   # explicit — preferred
converter.parse(xml_string)                              # str, sniffed as musicxml
converter.parse(xml_string.encode('utf-8'))              # bytes
converter.parse(pathlib.Path('score.musicxml'))          # Path
converter.parse(open('x.mid','rb').read())               # raw MIDI bytes
```

All six verified. `parseURL` (`:728`) is gated on `autoDownload`, default `'ask'`:

```python
>>> converter.parseURL(joplin_mxl_url)
ConverterException: Automatic downloading of URLs is presently set to 'ask'; ...
>>> environment.Environment()['autoDownload'] = 'allow'   # process-only
>>> converter.parseURL(joplin_mxl_url)
<Score>  2 parts, 813 notes
# cached at .../T/music21/m21-10.5.0-735ae8e4e6f32b7e38a952fa7d1ad6b5.mxl
```

`Environment()[k]=v` is in-process. `UserSettings()[k]=v` validates and writes `~/.music21rc`
immediately. `forceSource=True` refetches.

## tinyNotation

Formal EBNF at `tinyNotation.py:768-829`. All output below executed on 10.5.0.

**Pitch.** `a b c d e f g`, `r` for rest. Lowercase = octave 4 up; repeated uppercase = down.

```
'4/4 c4 d e f'      -> C4 D4 E4 F4
'4/4 C4 D E F'      -> C3 D3 E3 F3    (single uppercase = octave 3)
'4/4 CC4 DD EE'     -> C2 D2 E2       (n uppercase -> octave 4-n)
"4/4 c'4 d'' e'''"  -> C5 D6 E7       (n apostrophes -> octave 4+n)
```

**Accidentals.** `#` sharp, `-` flat (never `b`), `n` natural; repeat for double. Parentheses
make it editorial — stored in `.editorial.ficta`, **not printed**.

```
'4/4 c#4 d- en f##'  -> C#4 D-4 E4 F##4
'4/4 c(#)4 d(-)'     -> C4 (accidental=None, ficta=sharp), D4 (ficta=flat)
```

**Duration.** A number after the pitch: `1`=whole … `16`=sixteenth, powers of two only. Omit it
and the previous duration carries (`stateDict['lastDuration']`, `:504-509`). `.` adds a dot.

```
'4/4 c4. d8 e2'         -> 1.5, 0.5, 2.0
'4/4 c8 d e f g a b c'  -> eight eighths (duration carried)
```

**Tuplets.** Only `trip{...}` (3:2) and `quad{...}` (4:3).
`'4/4 trip{c8 d e} quad{f16 g a b}'` → `1/3 1/3 1/3, 0.1875 ×4`.

**Ties.** `~` starts a tie to the next note: `'4/4 c4~ c2.'` → `[('C4','start'),('C4','stop')]`.

**Meter.** `n/d` as a token, valid mid-stream: `'3/4 c4 d e 2/4 f g'` changes meter at bar 2.

**Modifiers** (`:152-158`): `=data` sets `.id`, `_data` sets `.lyric`. `[d]`, `<d>`, `(d)`,
`*d*` parse but have **no default action** — they are hooks.

```
'4/4 c4=myNote d'   -> recurse().getElementById('myNote') -> <Note C>
'4/4 c4_word d_two' -> lyrics ['word', 'two']
```

**Output.** A `stream.Part` (not a `Score`), already through `makeNotation`: measures, final
barline, auto Treble/Bass clef by range. `makeNotation=False` gives a flat Part.

### What tinyNotation cannot express

Verified with `raiseExceptions=True` — every one fails:

| Input | Result |
|---|---|
| `<c e g>4` | `Could not parse token: '<c'` — no chords |
| `c4 \| d4` | fails on `'\|'` — bars are inferred, never written |
| `k: C` | fails — **no key signatures** |
| `c4\mf` | fails — no dynamics, articulations, slurs, expressions |
| `c5`, `c3` | fails — not valid duration types |
| `\clef bass` | fails — clef is inferred only |

Also absent: multiple voices, multiple parts, grace notes, repeats, tempo, text.

**The silent-drop trap** (`:1251`) — an unparseable token disappears without warning:

```python
>>> [n.nameWithOctave for n in converter.parse('tinyNotation: 4/4 c2 d3 e2').recurse().notes]
['C4', 'E4']        # d3 vanished
```

**Always pass `raiseExceptions=True` when generating tinyNotation from code.**

### Extending it

Four hooks, all verified on 10.5.0.

**A `State`** (bracketed group) — the chord support everyone wants:

```python
from music21 import tinyNotation, chord
class ChordState(tinyNotation.State):
    def affectTokenAfterParse(self, n):
        super().affectTokenAfterParse(n)
        return None                                    # suppress the single Note
    def end(self):
        ch = chord.Chord(self.affectedTokens)
        ch.duration = self.affectedTokens[0].duration
        return ch

tnc = tinyNotation.Converter("2/4 C4 chord{C4 e g'} F.4 chord{D8 F# A}")
tnc.bracketStateMapping['chord'] = ChordState
tnc.parse().stream    # [<Note C>, <Chord C3 E4 G5>, <Note F>, <Chord D3 F#3 A3>]
```

**A `Modifier`** — reassign one of the six slots:

```python
class HarmonyModifier(tinyNotation.Modifier):
    def postParse(self, n):
        cs = harmony.ChordSymbol(n.pitch.name + self.modifierData)
        cs.duration = n.duration
        return cs
tnc = tinyNotation.Converter('4/4 C2_maj7 D4_m E-_sus4')
tnc.modifierUnderscore = HarmonyModifier   # -> Cmaj7, Dm, E-sus4
```

**A `Token`** — append `(regex_with_one_group, TokenClass)` to `tokenMap`:

```python
class KeyToken(tinyNotation.Token):
    def parse(self, parent):
        return key.Key(self.token)
tnc = tinyNotation.Converter('4/4 kE- G1 kf# A1')
tnc.tokenMap.append((r'k(.*)', KeyToken))  # -> [E- major, f# minor]
```

**Style** via `modifierStar`: a `postParse` setting `m21Obj.style.color` on
`'3/4 C4*pink* D4*green*'` yields `[('C','pink'), ('D','green')]`.

Tokens read converter state through `parent.stateDict`. For a whole dialect, subclass
`tinyNotation.Converter` and set `tokenMap` / `bracketStateMapping` as class attributes.

## Writing MusicXML correctly

`ConverterMusicXML.write` (`subConverters.py:908`) builds a `GeneralObjectExporter`
(`m21ToXml.py:245`), applies `makeNotation`, emits bytes, then optionally compresses or shells
out to MuseScore. Path rules:

- no suffix on `fp` → `.musicxml` appended (`:898`); `fp='noext'` → `noext.musicxml`
- `fp` ending `.mxl`, or `fmt='mxl'`, or `compress=True` → compressed (all three verified)
- any other suffix is left untouched

### makeNotation

`makeNotation=True` (default) **deep-copies**, wraps in a well-formed `Score`, fills gaps with
rests, and runs `makeMeasures`/`makeTies`/`makeBeams`/`makeAccidentals` plus best-clef selection
(`m21ToXml.py:367-500`). Measured on eight eighth notes in 4/4:

```
makeNotation=True  -> <beam> tags = 8
makeNotation=False -> <beam> tags = 0
```

`False` skips the copy and all fixing. Two consequences:

```python
>>> flat_stream.write('musicxml', makeNotation=False)
MusicXMLExportException: Can only export Scores with makeNotation=False

# and, given a real Score, nothing validates it — m1 declares 4/4, holds one 3.0-QL note:
>>> sc.write('musicxml', fp='short.musicxml', makeNotation=False)
>>> converter.parse('short.musicxml').parts[0].getElementsByClass(stream.Measure)[0].duration.quarterLength
3.0        # malformed bar written silently
```

**Default to `True`.** Use `False` only when you have already built explicit `Measure`s inside
`Part`s inside a `Score` and need the speed, or want your own beaming/spelling preserved.

### A file that actually opens in MuseScore/Finale

```python
from music21 import stream, note, meter, key, tempo, instrument, metadata, dynamics
sc = stream.Score()
sc.insert(0, metadata.Metadata(title='Round Trip Test', composer='Agent'))
p = stream.Part(id='Flute'); p.insert(0, instrument.Flute())
p.append(meter.TimeSignature('3/4')); p.append(key.Key('E-'))
p.append(tempo.MetronomeMark(number=92, referent=note.Note(type='quarter')))
p.insert(0, dynamics.Dynamic('mp'))
for pn in ['E-5','F5','G5','A-5','B-5','C6']:
    p.append(note.Note(pn, quarterLength=1.0))
sc.insert(0, p)
sc.write('musicxml', fp='/tmp/score.musicxml')
```

Yields a 6.7 KB MusicXML 4.0 partwise file with DOCTYPE, `<work-title>`, `<movement-title>`,
`<identification>`/`<creator type="composer">`, and a `<part-list>` carrying `<score-part>` +
`<score-instrument>` + `<midi-instrument>` — everything both editors expect. A grand staff is a
`Score` of two `stream.PartStaff` objects plus `layout.StaffGroup(symbol='brace')`; verified to
export as **one** `<score-part>` with `<staff>1</staff>`/`<staff>2</staff>`.

## Reading MusicXML: what survives

Measured by writing a maximally loaded score and re-parsing with `forceSource=True`:

| Feature | Survives |
|---|---|
| Pitch/spelling/octave/duration/dots; measures, TS, key, clefs, barlines | yes |
| Chords; voices (2 → 2 `Voice` objects); ties, slurs, `DynamicWedge` | yes |
| Grace notes, tuplets, repeat barlines | yes |
| `Dynamic`, `TextExpression`, articulations, ornaments, lyrics | yes |
| `MetronomeMark`, `Instrument` (name kept, **id regenerated**) | yes |
| `ChordSymbol` — **only if inside a Measure** | conditional |
| `metadata.composer` | yes |
| `metadata.title` | **no — becomes `.movementName`** |
| `roman.RomanNumeral` | **no — degrades to plain `Chord`** |
| Object `.id`, `.derivation`, custom attributes, editorial | no |

The title behavior is deliberate: the exporter writes the title into *both* `<work-title>` and
`<movement-title>` (`m21ToXml.py:2513`) because renderers display `movement-title` at the top of
the page; the importer sees them equal and **deletes `md['title']`** (`xmlToM21.py:1229-1241`).

```python
>>> b = converter.parse('score.musicxml', forceSource=True)
>>> b.metadata.title, b.metadata.movementName
(None, 'Round Trip Test')
```

Read titles as `md.title or md.movementName`. `parseFile` also injects the **filename** as
`movementName` when a file declares none (`subConverters.py:855-857`).

For RomanNumerals, analysis, derivations, or arbitrary attributes, MusicXML is the wrong
container — use `freezeThaw`.

## Compressed MusicXML (.mxl)

A zip holding the score plus `META-INF/container.xml`. `ArchiveManager`
(`__init__.py:114`) handles it transparently, including `.mxl` fetched by `parseURL`.

```python
am = converter.ArchiveManager('/tmp/a.mxl')
am.isArchive()   # True (it opens the file; a mislabeled .mxl returns False)
am.getNames()    # ['a.musicxml', 'META-INF/container.xml']
am.getData()     # XML as str, encoding auto-detected
```

`getData(dataFormat='musedata')` returns a **list** of strings — that is how `.zip` musedata is
read. Writing compresses via `archiveTools.compressXML(deleteOriginal=True)`
(`subConverters.py:970-976`), and **that deletion is not scoped to the temp file**:

```python
pathlib.Path('/tmp/clobber.musicxml').write_text('SENTINEL')
s.write('musicxml', fp='/tmp/clobber.mxl')
# clobber.musicxml exists: False   <-- your file is gone
```

## MIDI in and out

`ConverterMidi` (`subConverters.py:995`), `readBinary=True`. Measured round-trip of a 3/4,
A-major, Clarinet part at ♩=138:

```
pitches       ['A4','C#5','E5','A5','G#5','F#5']       preserved
durations     [1.0, 0.5, 0.5, 1.0, 2.0, 1.0]           preserved
TimeSignature 3/4   KeySignature A major   ♩=138       preserved
Instrument    <Clarinet 'Clarinet'>, partName Clarinet preserved
lyrics        ['hi', None, ...]                        preserved (lyric meta-events)
dynamics []   articulations [[], ...]  metadata.title None   LOST
volume.velocity  [127]*6                                flattened
```

Import quantization (`:1017-1020`) defaults to
`defaults.quantizationQuarterLengthDivisors = (4, 3)` — nearest 16th or triplet-8th:

```python
converter.parse(fp, forceSource=True)                             # [0.3333, 0.25, 1.0]
converter.parse(fp, forceSource=True, quantizePost=False)         # [0.32996, 0.2, 1.0]
converter.parse(fp, forceSource=True, quarterLengthDivisors=(8,3))
```

Both keywords enter the **pickle cache key** (`__init__.py:321-327`: `noQtz`, `qld8`), so
differently quantized parses of one file do not collide. Export keywords:
`addStartDelay=False`, `addEndDelay=True`, `encoding='utf-8'`.

## The output formats that are traps

`SubConverter.write()` has a base implementation (`subConverters.py:268-279`):

```python
def write(self, obj, fmt, fp=None, subformats=(), **keywords):
    dataStr = repr(obj)
    fp = self.writeDataStream(fp, dataStr, **keywords)
    return fp
```

Any subconverter that does not override it **writes the Python repr and returns a path as if it
worked**. Verified — no exception, no warning:

```
s.write('abc', fp='a.abc')      -> content: '<music21.stream.Part 0x1054ab4d0>'
s.write('humdrum', fp='a.krn')  -> content: '<music21.stream.Part 0x1054ab4d0>'
s.write('scala', fp='a.scl')    -> content: '<music21.stream.Part 0x1054ab4d0>'
```

**music21 cannot export ABC, Humdrum/kern, MEI, Capella, MuseData, NoteWorthy, or Scala.** Hand
the MusicXML to `verovio`, `humlib`, or `xml2abc` instead.

`scala` cannot parse either — `converter.parse('x.scl')` raises
`ConverterFileException: File is not in a correct format`. The real API:

```python
sf = scale.scala.ScalaFile(); sf.open(path); sd = sf.read(); sf.close()
s = scale.ScalaScale('C4', 'ennea45')
```

RomanText output requires the RomanNumerals **inside Measures** — a bare `Part` writes a header
and nothing else, and re-parsing then raises
`RomanTextException: Cannot find the first measure definition`:

```python
p.makeMeasures(inPlace=True)                 # required
sc.write('romantext', fp='cad.rntxt')
# Composer: Agent / Title: Cadence / Time Signature: 4/4 / m1 C: I / m2 IV / m3 V7 / m4 I
# re-parses to [('I','C major'), ('IV',…), ('V7',…), ('I',…)]
```

## Rendering to PDF / PNG / SVG

Two paths, both needing an **external binary**.

**MuseScore** — `converter/museScore.py:30`. `write('musicxml.png')` writes the `.musicxml`,
then runs `mscore <file> -o <out.png> -T 0 [-r dpi]`. Keywords `dpi=None`, `trimEdges=True`,
`leaveMargin=0`. MuseScore emits `name-1.png` / `name-01.png` / …, so music21 hunts for the
numbered file (`findNumberedPNGPath`, `:103`) and raises `IOError` if none appears. Binary from
`environLocal['musescoreDirectPNGPath']`.

**LilyPond** — `subConverters.py:400`; `lily.png`/`lily.pdf`/`lily.svg` route to
`createPNG`/`createPDF`/`createSVG`. `LilypondConverter.__init__` probes for the binary, so
**even `write('lily')` for a plain `.ly` text file fails without LilyPond installed**.

### On this machine: no. Neither renderer exists.

There is no `~/.music21rc`, so the macOS defaults apply (`environment.py:417-425`) and point at
uninstalled apps:

```
musicxmlPath / musescoreDirectPNGPath = /Applications/MuseScore 3.app/.../mscore  ** MISSING **
lilypondPath                          = /Applications/Lilypond.app/.../lilypond   ** MISSING **
midiPath                              = /Applications/GarageBand.app              ** MISSING **
graphicsPath / pdfPath / vectorPath   = /System/Applications/Preview.app          EXISTS
```

Nothing on `PATH` either (`mscore`, `musescore`, `lilypond`, `verovio` all absent);
`verovio`/`abjad` are not in the venv.

```
write('lily')  / write('lily.png')     -> LilyTranslateException: Cannot find a copy of Lilypond…
write('musicxml.png') / ('musicxml.pdf') -> SubConverterException: Cannot find a path to 'mscore'
```

**Worse, `s.show()` fails silently.** With default `showFormat='musicxml'` it writes a temp
file, then `launch()` calls `subprocess.run(..., check=False)` (`subConverters.py:204`), so a
missing app prints an OS error to stderr and `show()` **returns normally**:

```
The application /Applications/MuseScore 3.app/.../mscore cannot be opened … Code=260
returned (no exception)
```

### What does work here

1. **`write('musicxml')` / `write('midi')`** — full-fidelity files. This is the deliverable.
2. **`show('text')`** — the canonical structural check (offsets + objects).
3. **`show('textline')`, `converter.toData(s, 'braille.ascii')`** — compact inspection.
4. **matplotlib graphs** — `matplotlib` *is* installed, so `music21.graph` renders a real PNG:

```python
import matplotlib; matplotlib.use('Agg')
from music21 import corpus, graph
p = graph.plot.HorizontalBarPitchSpaceOffset(corpus.parse('bach/bwv66.6'), doneAction=None)
p.run(); p.write('/tmp/pianoroll.png')      # 86,831-byte PNG — verified
```

`doneAction=None` is the headless switch; without it music21 launches a viewer.

5. **The `/skip` escape hatch.** `ConverterMusicXML.write` checks
   `str(environLocal['musescoreDirectPNGPath']).startswith('/skip')` (`:967`) and returns the
   plain `.musicxml` instead of crashing; `UserSettings` exempts `/skip*` from path validation.

```python
environment.Environment()['musescoreDirectPNGPath'] = '/skip'
s.write('musicxml.png', fp='/tmp/skip.png')   # -> /tmp/skip.musicxml, no exception
```

### Configuring a headless machine

```python
us = environment.UserSettings()
us['musescoreDirectPNGPath'] = '/usr/bin/mscore3'   # validated to exist; writes ~/.music21rc
us['musicxmlPath']           = '/usr/bin/mscore3'
us['lilypondPath']           = '/usr/bin/lilypond'
us['directoryScratch']       = '/tmp/m21scratch'    # must already exist
us['autoDownload']           = 'allow'
us['warnings']               = 0                    # silence environLocal.warn
```

A bad path raises `UserSettingsException: attempting to set a value to a path that does not
exist`. `Environment()[k]=v` skips validation *and* the file write — process-scoped only.
`environment.set/get` are module-level wrappers.

`runThroughMuseScore` sets `QT_QPA_PLATFORM=offscreen` and `XDG_RUNTIME_DIR` on Linux **only
when `common.runningInNotebook()`** (`museScore.py:75-82`); in a plain script export them
yourself. `directoryScratch` relocates the temp root — verified, temp writes then land in
`/tmp/m21scratch/tmpXXXX.musicxml`.

## freezeThaw: caching an expensive parse

The only lossless serializer; pickles the object graph after fixing weakrefs
(`setupSerializationScaffold` / `teardownSerializationScaffold`).

```python
s = corpus.parse('bach/bwv66.6')                              # 4 parts, 165 notes
fp = converter.freeze(s, fmt='pickle', fp='/tmp/bwv.p.gz')    # 9,592 bytes, 0.021 s
s2 = converter.thaw(fp)                                       # 0.005 s, 165 notes
data = converter.freezeStr(s); s3 = converter.thawStr(data)   # 140,778 bytes in memory
```

zlib is a 15× win (9.6 KB vs 141 KB) and is the default for `converter.freeze`
(`zipType='zlib'`); pass `zipType=None` for a plain `.p` and the same value to `thaw`.
`fmt='jsonpickle'` also works (34 KB, readable, slower); `zipType` may only be `None` or
`'zlib'` (`freezeThaw.py:635`).

It preserves what MusicXML destroys:

```python
converter.thaw(converter.freeze(sc))     # [('I','g minor'), ('V65','g minor'), ('I','g minor')]
converter.parse(sc.write('musicxml'))    # 0 RomanNumerals — they became plain Chords
```

Two traps. **`fastButUnsafe=True` destroys the source stream** — it skips the defensive deepcopy
(`freezeThaw.py:213`):

```python
sf = freezeThaw.StreamFreezer(s, fastButUnsafe=True)
sf.write(fp='/tmp/bwv_fast.p.gz', zipType='zlib')
len(s.recurse().notes)      # 0   <-- the original is now empty
```

**A relative `fp` is silently rebased onto the temp dir** (`freezeThaw.py:648-650`):

```python
os.chdir('/tmp/m21io'); converter.freeze(s, fp='rel.p.gz')
# -> /var/folders/.../T/music21/rel.p.gz    NOT /tmp/m21io/rel.p.gz
```

Also, `converter.parse()` cannot read a frozen file
(`ConverterFileException: cannot find format from file extensions`) — use `converter.thaw()`.

## The pickle cache

`converter.parseFile` caches every file parse (`__init__.py:611-665`) via `PickleFilter`
(`:270`).

**Where.** `environLocal.getRootTempDir()` — here `/var/folders/7s/…/T/music21/`. Name
(`getPickleFp`, `:296`):

```
m21-<m21version>-py<major>.<minor>[-<quantization>]-<md5 of abs path>[-<number>].p.gz
m21-10.5.0-py3.14-d6b23c76d70af5fbfd265162dca81c84.p.gz
```

Version and Python minor are in the key, so upgrading either invalidates everything.
Downloaded URLs land in the same directory as `m21-<version>-<md5 of url><ext>` — a separate
cache with **no staleness check at all**.

**When used.** `PickleFilter.status()` (`:348`) compares mtimes only. Measured: first parse
0.0041 s (writes the pickle), second 0.0006 s — 7× faster.

**When stale.** No hash, no size. Any tool that rewrites content while preserving mtime
(`os.utime`, `rsync --times`, a git checkout, a restored backup) yields the old parse:

```python
# file now contains G A B; mtime rewound below the pickle's
converter.parse(src)                     # ['C4','D4','E4','F4']   STALE, silent
converter.parse(src, forceSource=True)   # ['G4','A4','B4']        correct
converter.parse(src)                     # ['C4','D4','E4','F4']   STALE AGAIN
```

**`forceSource=True` never refreshes the cache** — `status()` returns `fpPickle=None`, so
nothing is rewritten. Clear it explicitly:

```python
converter.PickleFilter('/path/score.musicxml').removePickle()          # one file
root = environment.Environment().getRootTempDir()
for f in root.glob('m21-*.p.gz'): f.unlink()                           # everything
converter.Converter().parseFileNoPickle(fp)                            # never cache
converter.parseFile(fp, forceSource=True, storePickle=False)
```

This also explains why registering a custom SubConverter for an extension music21 already
handles appears to do nothing until you pass `forceSource=True` (`__init__.py:903-916`).

## Writing a custom SubConverter

Subclass `SubConverter`, set the three class attributes, implement `parseData` (input) and
`write` (output). `parseFile` is optional — the base reads the file and calls `parseData`,
honoring `readBinary`. Executed end to end:

```python
class ScaleDegreeConverter(converter.subConverters.SubConverter):
    '''Format: "degrees: 1 3 5 8" -> C-major scale degrees as quarter notes.'''
    registerFormats          = ('degrees',)   # "degrees:" prefix + format='degrees'
    registerInputExtensions  = ('deg',)       # converter.parse('x.deg')
    registerOutputExtensions = ('deg',)       # .write('degrees')

    def parseData(self, dataString, number=None):
        sc = scale.MajorScale('C')
        p = stream.Part(); p.insert(0, meter.TimeSignature('4/4'))
        for tok in dataString.split():
            p.append(note.Note(sc.pitchFromDegree(int(tok), minPitch='C4', maxPitch='C6'),
                               quarterLength=1.0))
        self.stream = p.makeNotation()        # MUST set self.stream

    def parseFile(self, filePath, number=None, **keywords):
        self.parseData(pathlib.Path(filePath).read_text())

    def write(self, obj, fmt, fp=None, subformats=(), **keywords):
        sc = scale.MajorScale('C')
        degs = [str(sc.getScaleDegreeFromPitch(n.pitch) or 'x') for n in obj.recurse().notes]
        fp = fp or self.getTemporaryFile(subformats)
        pathlib.Path(fp).write_text(' '.join(degs) + '\n')
        return pathlib.Path(fp)               # MUST return the path

converter.registerSubConverter(ScaleDegreeConverter)
converter.parse('degrees: 1 3 5 4 2 1')   # ['C4','E4','G4','F4','D4','C4']
converter.parse('x.deg')                  # ['C4','D4','E4','F4']
s.write('degrees', fp='roundtrip.deg')    # '1 3 5 4 2 1\n'
converter.resetSubConverters()            # 'degrees' no longer registered
```

Registry API (`__init__.py:405-503`): `registerSubConverter(cls)` uses `appendleft`, so **custom
converters shadow built-ins** for the same format or extension (v9+);
`unregisterSubConverter(cls)` removes or masks one; `unregisterSubConverter('all')` strips
everything including defaults; `resetSubConverters()` restores stock — call it in test teardown.
The registry is **module-global and shared across all `Converter` instances**
(`__init__.py:447-449`). `converter/qmConverter.py` is the in-tree reference; users' guide 54
walks the same ground.

Other hooks: `readBinary`, `codecWrite` + `stringEncoding`,
`registerOutputSubformatExtensions` (maps `'png'` → `'png'` for `format.subformat` calls),
`checkShowAbility()` (return False when a binary is missing), `launch()`, `show()`.

## Gotchas

1. **`s.show()` fails silently when the viewer is missing.** `launch()` uses
   `subprocess.run(check=False)`; the OS error goes to stderr and `show()` returns normally.
   Never treat `show()` as verification — use `show('text')`.

2. **`write('abc' | 'humdrum' | 'scala')` writes `repr(obj)` and returns a path.** No
   exception. music21 exports only musicxml, mxl, midi, rntxt, braille, text, textline,
   volpiano, lilypond, and (10.5.0 only) vexflow.

3. **`converter.parse('x.scl')` cannot parse Scala at all** despite `scala` being registered.
   Use `scale.scala.ScalaFile` / `scale.ScalaScale`.

4. **`forceSource=True` bypasses the pickle but never refreshes it.** The next plain `parse()`
   returns the stale object again. Call `PickleFilter(fp).removePickle()`.

5. **The pickle cache keys on mtime only.** `os.utime`, `rsync --times`, or a git checkout
   makes music21 serve an old parse with no warning.

6. **Writing `foo.mxl` deletes `foo.musicxml` in the same directory** —
   `compressXML(deleteOriginal=True)` is not scoped to the temp file it just wrote.

7. **`metadata.title` round-trips into `metadata.movementName`.** Read
   `md.title or md.movementName`. An untitled MusicXML file returns the *filename* as
   `movementName`.

8. **`StreamFreezer(s, fastButUnsafe=True)` empties `s`.** Afterwards the original has zero
   elements.

9. **A relative `fp` to `converter.freeze` lands in the temp dir, not the cwd.**

10. **tinyNotation silently drops unparseable tokens** — `'4/4 c2 d3 e2'` yields two notes.
    Always pass `raiseExceptions=True` when generating it from code.

11. **tinyNotation has no key signatures, chords, dynamics, barlines, clefs, or parts**, and
    only `trip{}`/`quad{}` tuplets. It returns a `Part`, not a `Score`.

12. **`makeNotation=False` requires a `Score`** and validates nothing — a 3-beat bar in 4/4
    exports silently malformed.

13. **`parseURL` refuses by default** (`autoDownload='ask'`), and its download cache has no
    staleness check — use `forceSource=True` to refetch.

14. **The subconverter registry is global**; custom converters shadow built-ins. Call
    `resetSubConverters()` in teardown.

15. **`ConverterVexflow` exists in 10.5.0 but is gone in v11**, and embeds a jsonpickle blob
    for an obsolete music21j. Don't build on it.

16. **`show('braille')` in a terminal writes a temp file and launches a viewer** instead of
    printing. Use `print(converter.toData(s, 'braille.ascii'))`.

17. **`converter.parse()` cannot read a frozen `.p`/`.p.gz`** — use `converter.thaw()`.

18. **Format sniffing is loose**: `'M:' and 'K:' in data` claims ABC; `<?xml` without `<mei`
    claims MusicXML. Pass `format=` whenever you know it.

19. **On this machine there is no MuseScore, no LilyPond, and no `~/.music21rc`**, so defaults
    point at nonexistent apps and every PNG/PDF/SVG path fails — including bare `.ly` output.
    Ship `.musicxml`/`.mid`, verify with `show('text')`, and use `graph.plot.*` with
    `doneAction=None` when you need a picture.
