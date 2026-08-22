# 10 — Where to Get Scores: the Bundled Corpus and the Live Web

Where you legally and reliably GET music to parse, adapt or learn from. Part 1 is the
corpus that ships inside the `music21` wheel — 3,194 files, 15,112 works, zero network,
zero licence risk. Part 2 is every online source I fetched with `curl` on 2026-08-22 and
parsed, with the HTTP status printed and the dead ones named. Part 3 is
`scripts/fetch_score.py`, one CLI over all of it. Verified on **music21 10.5.0**;
line citations are to the **v11.0.0b8** tree.

---

## 1. What ships in the box

`pip install music21` puts **66 MB** of scores under `music21/corpus/`. Nothing is
downloaded at first use — it is all already on disk.

```
3,194 files            corpus.getCorePaths()
15,112 works           corpus.corpora.CoreCorpus().metadataBundle
   35 collections      corpus.corpora.CoreCorpus().directoryInformation
   66 MB on disk       (+ 1.0 MB metadata cache: corpus/_metadataCache/core.p.gz)
```

Files ≠ works: an ABC file is an **Opus** holding many tunes. `essenFolksong` is 31 files
but **8,545** works; `oneills1850` is 39 files, 2,047 works.

**By format** (`p.suffix for p in corpus.getCorePaths()`):

| ext | files | notes |
|---|---|---|
| `.krn` | 1,326 | Humdrum, mostly trecento + palestrina + a few Bach |
| `.abc` | 1,146 | folk collections; each file is an Opus |
| `.mxl` | 535 | compressed MusicXML — the Bach chorales live here |
| `.xml` | 118 | uncompressed MusicXML |
| `.rntxt` | 68 | RomanText harmonic analyses (monteverdi, trecento, demos) |
| `.musicxml` | 1 | |

**All 35 collections** — `dirName | files | works | title` (`isComposer` false for the
five collection-style entries marked ✱):

```
airdsAirs      6  1186  Aird's Airs ✱          liliuokalani     1     1  Queen Liliʻuokalani
bach         433   433  J.S. Bach              luca             1     1  D. Luca
beach          1     1  Amy Beach              lusitano         1     1  Vicente Lusitano
beethoven     26    26  Beethoven              miscFolk         2   187  Miscellaneous Folk ✱
chopin         1     1  Chopin                 monteverdi      97    97  Monteverdi
ciconia        1     1  Ciconia                mozart          16    16  Mozart
corelli        1     1  Corelli                nottingham…      1     3  Nottingham (partial) ✱
cpebach        1     1  C.P.E. Bach            oneills1850     39  2047  O'Neill's 1850 ✱
demos         13    13  Demonstration Files ✱  palestrina    1318  1318  Palestrina
essenFolksong 31  8545  Essen Folksong ✱       ryansMammoth  1059  1059  Ryan's Mammoth ✱
handel         1     1  Handel                 schoenberg       2     2  Schoenberg
haydn          9     9  Haydn                  schubert         1     1  Schubert
joplin         1     1  Joplin                 schumann_clara   5     5  Clara Schumann
johnson_j_r    1     1  J. Rosamund Johnson    schumann_robert  7     7  Robert Schumann
josquin        8    37  Josquin                theoryExercises  2     2  Theory Exercises ✱
leadSheet      2     2  Leadsheet demos ✱      trecento       103   103  14th-c. Italian ✱
                                               verdi 1 · weber 1 · webern 1
```

Practical read: **Bach chorales (433 files, four parts, MusicXML)** are the workhorse.
**Palestrina (1,318)** for modal counterpoint. **Essen (8,545)** for monophonic melody
statistics. Everything else is a handful of pieces.

### core vs. local vs. virtual

Three `Corpus` subclasses in `music21/corpus/corpora.py`:

* **`CoreCorpus`** — the 3,194 bundled files. `parseUsingCorpus = True`, so
  `corpus.parse('bach/bwv66.6')` resolves a relative path inside the package.
* **`LocalCorpus`** — directories *you* register. Named or anonymous; multiple named
  local corpora can coexist and each gets its own metadata cache.
* **`VirtualCorpus`** — **dead**. `music21/corpus/virtual.py:17` says
  *"TURNED OFF in 2017 -- to be recreated with a bigger test set."* `corpus.virtual`
  still imports and the `VirtualWork` classes still list URLs, but nothing consumes
  them. Do not build on it.

Registering a local corpus — **must be inside `if __name__ == '__main__'`**, because
`cacheMetadata` forks with `multiprocessing`:

```python
# localdemo.py  -- run as a FILE, not via python -c / heredoc
from music21 import corpus

def main():
    lc = corpus.corpora.LocalCorpus('demo')
    lc.addPath('/tmp/mylocalscores')
    lc.save()                                  # persists to the music21 environment
    corpus.cacheMetadata('demo', verbose=False)
    print(lc.metadataBundle)                   # <MetadataBundle 'demo': {2 entries}>
    print(corpus.search('bwv66', corpusNames=('demo',)))   # {1 entry}
    print([c.name for c in corpus.manager.iterateCorpora()])  # ['core','local','demo']
    lc.delete()

if __name__ == '__main__':
    main()
```

Without the guard the fork re-executes stdin and dies with
`FileNotFoundError: .../<stdin>` — repeatedly, until you kill it.

---

## 2. Searching the offline corpus

`corpus.search()` returns a `MetadataBundle`, which is a **set** — it supports
`.intersection`, `.union`, `.difference`, `.symmetric_difference`, and chained
`.search()`. First call pays ~0.9 s to unpickle `core.p.gz`; after that it is in-memory.

```python
from music21 import corpus

corpus.search('bach')                            # 564  -- any field
corpus.search('bach',       field='composer')    # 363
corpus.search('palestrina', field='composer')    # 1318
corpus.search('shandon',    field='title')       # 1
corpus.search('3/4',        field='timeSignature')  # 1875
corpus.search('6/8',        field='timeSignature')  # 2164
corpus.search(numberOfParts=4)                   # 945
corpus.search('humdrum',    field='fileFormat')  # 1326
corpus.search('Bayern',     field='localeOfComposition')  # 93
corpus.search('E5',         field='pitchHighest')         # 2198
corpus.search(3,            field='keySignatureFirst')    # 1031 (3 sharps)
corpus.search('bach', fileExtensions=('.krn',))  # 3   -- bwv277/281/366
```

**Chaining is AND.** Keyword args on one call are also AND:

```python
b = corpus.search('bach', field='composer')      # 363
b = b.search(numberOfParts=4)                    # 323
b = b.search('3/4', field='timeSignature')       # 32   Bach 4-part chorales in 3/4
b[0].sourcePath                                  # PosixPath('bach/bwv11.6.mxl')
score = b[0].parse()                             # -> stream.Score
```

Query may be a **string (regex)**, a **compiled pattern**, an **int**, or a **callable**:

```python
import re
corpus.search(re.compile(r'^Wie'), field='title')                  # 32
corpus.search(lambda v: isinstance(v, int) and v > 2000,
              field='noteCount')                                   # 54
```

**The full field list is 148 names** — `metadata.bundles.MetadataBundle.listSearchFields()`.
The analysis-derived ones (`RichMetadata`, `music21/metadata/__init__.py:2493`) are the
useful ones for composition:

```
ambitus  keySignatureFirst  keySignatures  noteCount  numberOfParts
pitchHighest  pitchLowest  scoreQuarterLength  tempoFirst  tempos
timeSignatureFirst  timeSignatures  sourcePath  corpusFilePath  fileFormat
```

`ambitus` is an `AmbitusShort` namedtuple, **not searchable by string**:

```python
md.ambitus  # AmbitusShort(semitones=34, diatonic='m7', pitchLowest='F#2', pitchHighest='E5')
corpus.search('m7', field='ambitus')   # 0  -- namedtuple repr never matches
```

Filter on range yourself instead:

```python
wide = [e for e in corpus.search('bach', field='composer')
        if e.metadata.ambitus and e.metadata.ambitus.semitones > 36]
```

Field names are **prefix-matched and lowercased** (`music21/metadata/__init__.py:1162`),
so `field='compos'` hits `composer`, and `field='timeSignature'` hits
`timeSignatureFirst` — which is why `field='timeSignatures'` (plural, exact) returns 0
at top level while `field='timeSignature'` returns 1,875. An unknown field is silently
0 results, never an error.

### getComposer, getWork, parse

```python
corpus.getComposer('bach')                        # 433 Paths
corpus.getComposer('bach', fileExtensions=['xml'])   # 410  (xml and mxl are equivalent)
corpus.getComposer('bach', fileExtensions=['krn'])   # 3
corpus.getCorePaths()                             # 3194
corpus.getPaths()                                 # core + every registered local

corpus.parse('bach/bwv66.6')                      # Score, 4 parts
corpus.getWork('beethoven/opus18no1')             # list of 8 Paths (4 mvts x krn+mxl)
corpus.parse('beethoven/opus18no1', movementNumber=2)   # 'Adagio affettuoso…'
corpus.parse('essenFolksong/teste')               # Opus, 8 scores
corpus.parse('essenFolksong/teste', number=3)     # Score 'Rosestock, Holderbl!'
```

### chorales.Iterator

`music21/corpus/chorales.py` wraps the 433 Bach files in four numbering systems.

```python
from music21.corpus import chorales

len(chorales.Iterator())                                        # 371  (riemenschneider)
len(chorales.Iterator(numberingSystem='bwv',  returnType='filename'))         # 353
len(chorales.Iterator(numberingSystem='kalmus', returnType='filename'))       # 337
len(chorales.Iterator(numberingSystem='baerenreiter', returnType='filename')) # 190
len(chorales.ChoraleList().byBWV)                                             # 186

for ch in chorales.Iterator(1, 5):            # inclusive range, parses each
    print(ch.metadata.title, len(ch.parts))
# Aus meines Herzens Grunde 4 / Ich dank’ dir, lieber Herre 4 / ...

list(chorales.Iterator(returnType='filename'))[:3]
# ['bach/bwv269', 'bach/bwv347', 'bach/bwv153.1']
```

`numberingSystem='title'` yields **0** and raises
`Cannot parse Chorales because no titles to parse.` — it is unimplemented. Use
`returnType='filename'` when you only want paths (no parse cost).

### Rebuilding the metadata bundle

You need this after adding files to a local corpus, or if the shipped cache is stale.

```python
from music21 import corpus
from music21.metadata import bundles

corpus.cacheMetadata('demo')                # rebuild one named local corpus
corpus.cacheMetadata(('local', 'demo'))     # several

mb = bundles.MetadataBundle('mine')
failed = mb.addFromPaths(list_of_paths, parseUsingCorpus=False,
                         useMultiprocessing=True, storeOnDisk=True)
mb.write()                                  # -> <scratch>/music21/local-mine.p.gz
mb.read(); mb.validate(); mb.clear()
```

Every entry parses the score to derive `noteCount`/`ambitus`/`numberOfParts`, so
rebuilding the whole core corpus takes minutes. The shipped `core.p.gz` is 1.0 MB and
its `filePath` fields still point at the maintainer's machine
(`/Users/cuthbert/Git/music21base/...`) — use `sourcePath` (relative) or
`corpusFilePath`, never `filePath`.

---

## 3. Online sources — verified 2026-08-22

Every row was fetched with `curl` and, where marked, parsed. Status codes are real.

| Source | Content | Format | Licence | Verified URL pattern (HTTP) | Parse |
|---|---|---|---|---|---|
| **kernscores.stanford.edu** | ~110k Humdrum works, 22 collections | `**kern` | mixed, mostly CCARH non-commercial | `http://kernscores.stanford.edu/cgi-bin/ksdata?l=<dir>&file=<f>.krn&f=kern` → **200** | ✅ |
| **kern.humdrum.org** | same data, canonical host | `**kern` | same | `https://kern.humdrum.org/cgi-bin/ksdata?...` → **503** ❌ | — |
| **craigsapp/\*** GitHub | Bach chorales, Beethoven/Mozart/Haydn/Scarlatti sonatas, Chopin, Joplin, Densmore | `**kern` | **CC BY-NC-SA 4.0** | `https://raw.githubusercontent.com/craigsapp/<repo>/master/kern/<f>.krn` → **200** | ✅ |
| **ccarh/essen-folksong-collection** | ~8k European/Asian/African folk melodies | `**kern` | CCARH restrictive (no commercial derivatives) | `https://raw.githubusercontent.com/ccarh/essen-folksong-collection/main/<region>/<sub>/<f>.krn` → **200** | ✅ |
| **humdrum-tools/humdrum-data** | index of 848 repo/dir pairs, `make`-driven | `**kern` | per-sub-repo | `https://raw.githubusercontent.com/humdrum-tools/humdrum-data/master/.lists/LIST.txt` → **200**, 80,880 B | index |
| **Josquin Research Project** | Renaissance polyphony, ~2k works | `**kern` | free for research | `https://josquin.stanford.edu/data?a=humdrum&f=<JRPid>` → **200** | ✅ |
| **OpenScore Lieder** | 1,462 songs + 1,156 RomanText analyses | `.mxl` `.rntxt` `.mscz` | **CC0-1.0** | `https://raw.githubusercontent.com/OpenScore/Lieder/main/scores/<Composer>/<Set>/<Song>/<id>.mxl` → **200** | ✅ |
| **OpenScore StringQuartets** | 122 quartet movements (+613 PDFs) | `.mxl` `.mscx` | **CC0-1.0** | `https://raw.githubusercontent.com/OpenScore/StringQuartets/main/scores/<Composer>/<Work>/<id>.mxl` → **200** | ✅ |
| **Mutopia Project** | ~2,300 engravings | `.mid` `.ly` `.pdf` | public domain / CC | `https://www.mutopiaproject.org/ftp/<Composer>/<Cat>/<slug>/<slug>.mid` → **200** | ✅ |
| **thesession.org** | ~50k Irish trad tunes, per-setting ABC | JSON→ABC | **CC0** (site states public domain) | `https://thesession.org/tunes/<id>?format=json` → **200** | ✅ |
| **TheSession bulk** | whole DB as JSON/CSV | JSON | CC0 | `https://raw.githubusercontent.com/adactio/TheSession-data/main/json/tunes.json` → **200**, 24 MB | via ABC |
| **Nottingham (jukedeck)** | 1,034 British folk tunes, cleaned | `.abc` `.mid` | public domain source | `https://raw.githubusercontent.com/jukedeck/nottingham-dataset/master/ABC_cleaned/<set>.abc` → **200** | ✅ Opus |
| **Nottingham (original NMD)** | same, Eric Foxley's originals | `.abc` (`.txt`) | public domain | `http://abc.sourceforge.net/NMD/nmd/<set>.txt` → **200** (`jigs.txt` 130 kB) | ✅ |
| **mfiles.co.uk** | 305 classical MIDI sequences | `.mid` | **© Music Files Ltd, all rights reserved** ⚠ | `https://www.mfiles.co.uk/downloads/<slug>.mid` → **200** | ✅ |
| **IMSLP** | 700k+ scores | PDF (+ some MIDI/XML) | mostly PD scans | metadata API → **200**; file download → JS interstitial ⚠ | ✗ |
| **Meertens Tune Collections** | Dutch folk songs | `**kern`/MIDI/features | research use, registration for full set | `http://www.liederenbank.nl/mtc/downloads/MTC-sampleset.zip` → **200**, 44 MB | — |
| **Lakh MIDI (LMD)** | 176,581 MIDI files | `.mid` | CC BY 4.0 (Raffel) | `http://hog.ee.columbia.edu/craffel/lmd/lmd_full.tar.gz` → **200**, **1.77 GB** (http only) | — |
| **MAESTRO v3** | 1,276 performances, aligned audio+MIDI | `.midi` | CC BY-NC-SA 4.0 | `https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip` → **200**, **58.4 MB** | — |
| **GiantMIDI-Piano** | 10,855 transcribed piano works | `.mid` | disclaimer-gated, 193 MB | `https://github.com/bytedance/GiantMIDI-Piano` → **200**; download needs `disclaimer.md` agreement ⚠ | — |
| **POP909** | 909 Chinese pop piano arrangements | `.mid` + annotations | **MIT** | `https://raw.githubusercontent.com/music-x-lab/POP909-Dataset/master/POP909/<nnn>/<nnn>.mid` → **200** | ✅ |

### Dead or gated — do not follow these

* `https://kern.humdrum.org/cgi-bin/ksdata?...` → **503 Service Unavailable** (Apache
  2.4.66, both `:80` after the 301 and `:443`). The site root 301s but the data CGI is
  down. **Mirror: `http://kernscores.stanford.edu/cgi-bin/ksdata` (200, identical API).**
* `https://abcnotation.com/` → **connection timeout** (DNS resolves to 192.70.246.47,
  TCP never completes). Its 700k-tune index is unreachable; use thesession.org and the
  Nottingham/NMD archives instead.
* `http://abc.sourceforge.net/NMD/nmd/NMD.zip` → **404** (the page still links it). The
  individual `.txt` files in the same directory are **200**.
* IMSLP file downloads: `Special:ImagefromIndex/<n>` returns **200 text/html** —
  a `friendlyredirect.html` JS interstitial, not the file. Even past it, IMSLP is
  scanned **PDF**, which music21 cannot read. Its *metadata* is genuinely open (below).
* `https://musescore.com/openscore` → **403** to a plain client. Use the
  **github.com/OpenScore** repos, which are the same data as CC0 `.mxl`.
* Lakh MIDI over **https** to `hog.ee.columbia.edu` fails (curl exit before TLS);
  plain **http** returns 200 with `Content-Length: 1768163879`.

### Snippets that were actually executed

```python
# kernscores (the live mirror) -- returns raw Humdrum text
import urllib.request
from music21 import converter
url = ('http://kernscores.stanford.edu/cgi-bin/ksdata'
       '?l=osu/classical/bach/inventions&file=inven01.krn&f=kern')
s = converter.parse(urllib.request.urlopen(url).read().decode(), format='humdrum')
# Inventio 1 | 2 parts | 22 bars | C major | 4/4 | 464 notes

# directory index: TSV of filename<TAB>order<TAB>title
idx = ('http://kernscores.stanford.edu/cgi-bin/ksdata'
       '?l=musedata/bach/brandenburg&format=index')      # 200, 1570 B
```

```python
# craigsapp Humdrum over raw.githubusercontent
def kern(repo, path, owner='craigsapp', branch='master'):
    u = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'
    return converter.parse(urllib.request.urlopen(u).read().decode(), format='humdrum')

kern('bach-370-chorales',       'kern/chor001.krn')    # 4 parts, 23 bars, G major, 3/4
kern('joplin',                  'kern/entertainer.krn')# 2 parts, 92 bars, C major, 2/4
kern('beethoven-piano-sonatas', 'kern/sonata01-1.krn') # 2 parts, 155 bars, 2/2
kern('chopin-mazurkas',         'kern/mazurka06-1.krn')# 2 parts, 75 bars, 3/4
kern('mozart-piano-sonatas',    'kern/sonata01-1.krn') # 2 parts, 100 bars, C major
kern('beethoven-string-quartets','kern/quartet01-1.krn')
kern('haydn-piano-sonatas',     'kern/sonata12-1.krn')
kern('scarlatti-keyboard-sonatas','kern/L001K514.krn')
kern('densmore-teton-sioux',    'kern/sioux001.krn')
kern('chopin-preludes',         'kern/prelude28-04.krn')  # 2 parts, 26 bars, e minor
```

Naming is per-repo — enumerate rather than guess:
`https://api.github.com/repos/craigsapp/<repo>/contents/kern`. Counts I measured off the
kernscores index: Beethoven sonatas **102** movements, Beethoven quartets **71**, Mozart
sonatas **69**, Chopin mazurkas **56**, Joplin **54**, Scarlatti **545**, Bach chorales
**370**, Densmore Teton Sioux **245**, Haydn sonatas **25**, Chopin preludes **24**.
`raw.githubusercontent.com` silently serves `master` for repos whose only branch is
`main`, so `master` is a safe default.

```python
# OpenScore Lieder -- CC0 MusicXML *and* a matching RomanText analysis
import urllib.parse
base = 'https://raw.githubusercontent.com/OpenScore/Lieder/main/'
p = 'scores/Schubert,_Franz/4_Gesänge_aus_„Wilhelm_Meister“,_D.877/1_Mignon_und_der_Harfner/lc5093434.mxl'
data = urllib.request.urlopen(base + urllib.parse.quote(p)).read()   # 13,541 B
# -> 4 parts, 50 bars, b minor, 2/2, 720 notes
# sibling file 'analysis_automatic.rntxt' parses to a chordified Score of the same piece
```

Non-ASCII paths **must** be `urllib.parse.quote`d. Enumerate the whole tree in one call:
`https://api.github.com/repos/OpenScore/Lieder/git/trees/main?recursive=1` (not
truncated; 1,462 `.mxl`, 1,462 `.mscz`, 1,352 `.mscx`, 1,156 `.rntxt`).

```python
# thesession.org -- ABC bodies with NO header; you must synthesise one
import json
meta = json.loads(urllib.request.urlopen(
    'https://thesession.org/tunes/182?format=json').read())
st = meta['settings'][0]                       # 21 settings for this tune
body = st['abc'].replace('!', '\n')            # '!' is their line separator
key  = st['key'].replace('major', '').replace('minor', 'min') \
                .replace('dorian', 'dor').replace('mixolydian', 'mix')
abc  = f"X:1\nT:{meta['name']}\nM:4/4\nL:1/8\nK:{key}\n{body}\n"
s = converter.parse(abc, format='abc')         # 1 part, 19 bars, D major, 148 notes
```

Meter comes from `meta['type']` (`reel`→4/4, `jig`→6/8, `slip jig`→9/8, `slide`→12/8,
`polka`→2/4, `waltz`/`mazurka`→3/4, `three-two`→3/2), not from the ABC.

```python
# MIDI archives
mid = urllib.request.urlopen(
    'https://www.mfiles.co.uk/downloads/mozart-symphony40-1.mid').read()   # 107,078 B
# -> 10 parts, 399 bars, 2/2, 10,892 notes
# index of all 305: https://www.mfiles.co.uk/classical-midi.htm , hrefs 'downloads/*.mid'

urllib.request.urlopen('https://www.mutopiaproject.org/ftp/BachJS/BWV772/'
                       'bach-invention-01/bach-invention-01.mid').read()   # 3,929 B
# -> 2 parts, 22 bars, C major, 4/4, 460 notes
# discover paths: https://www.mutopiaproject.org/cgibin/make-table.cgi?Composer=BachJS
```

`.mid` and `.mxl` are **binary** — write to a temp file with the right suffix before
`converter.parse`; passing bytes to `parse()` guesses wrong.

```python
# IMSLP: metadata yes, files no
api = ('https://imslp.org/imslpscripts/API.ISCR.php?account=worklist/'
       'disclaimer=accepted/sort=id/type=2/start=0/retformat=json')   # 200, 314 kB
# type=1 -> composers, type=2 -> works; 1000 rows/page, 'moreresultsavailable': True
# each row: {'id', 'parent', 'intvals': {'composer','worktitle','icatno','pageid'},
#            'permlink'}
```

Use IMSLP to *identify* a work and its catalogue number, then fetch the notation from a
Humdrum/MusicXML source above. Do not try to make music21 read an IMSLP PDF; see
chapter 07 for the OMR route.

### Research datasets (large — check the size before you pull)

| dataset | canonical URL | size | note |
|---|---|---|---|
| Lakh MIDI full | `http://hog.ee.columbia.edu/craffel/lmd/lmd_full.tar.gz` | **1.77 GB** | 176,581 dedup'd MIDI, http **only** |
| Lakh matched | `…/lmd_matched.tar.gz` | 1.41 GB | 45,129 matched to Million Song Dataset |
| Lakh aligned | `…/lmd_aligned.tar.gz` | 0.27 GB | time-aligned subset |
| Lakh clean_midi | `…/clean_midi.tar.gz` | **0.23 GB** | 17k files with artist/title — best starting subset |
| MAESTRO v3 MIDI | `https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip` | **58.4 MB** | competition-grade piano performance, ~200 h |
| POP909 | `https://codeload.github.com/music-x-lab/POP909-Dataset/zip/refs/heads/master` | 46 MB | MIT; melody/bridge/piano tracks + beat & chord annotations |
| GiantMIDI-Piano | repo → `disclaimer.md` | 193 MB | 10,855 transcriptions; transcribed, not engraved — expect no barlines you'd trust |
| MTC sample set | `http://www.liederenbank.nl/mtc/downloads/MTC-sampleset.zip` | 44 MB | Dutch folk; full corpus via `download.php` |
| Pianist8 (Zenodo) | `https://zenodo.org/records/5089279` | 3.9 MB | 8 pianists, style-transfer benchmark |

MAESTRO and GiantMIDI are **performance** MIDI: expressive timing, no quantised meter.
`converter.parse()` will produce hundreds of tiny tuplet-ridden measures. Run
`s.quantize()` or `midi.translate` with `quantizePost=True` before analysing rhythm.

---

## 4. `scripts/fetch_score.py`

One CLI over everything above. `python fetch_score.py --schemes` lists the prefixes.

```bash
python scripts/fetch_score.py bach/bwv66.6
# bwv66.6.mxl | 4 parts | 10 bars | f# minor | 4/4 | 165 notes | corpus:bach/bwv66.6

python scripts/fetch_score.py humdrum:craigsapp/bach-370-chorales/kern/chor001.krn
# Aus meines Herzens Grunde… | 4 parts | 23 bars | G major | 3/4 | 229 notes | https://raw…

python scripts/fetch_score.py kernscores:osu/classical/bach/inventions/inven01.krn
# Inventio 1 | 2 parts | 22 bars | C major | 4/4 | 464 notes | http://kernscores…

python scripts/fetch_score.py session:182
# The Silver Spear | 1 parts | 19 bars | D major | 4/4 | 148 notes | https://thesession.org…

python scripts/fetch_score.py jrp:Jos2721
# La Bernardina | 3 parts | 46 bars | C major | 2/1 | 404 notes | https://josquin.stanford.edu…

python scripts/fetch_score.py mfiles:mozart-symphony40-1 --no-key
python scripts/fetch_score.py mutopia:BachJS/BWV772/bach-invention-01/bach-invention-01.mid
python scripts/fetch_score.py https://raw.githubusercontent.com/.../sq7313978.mxl
python scripts/fetch_score.py session:182/2 --json --out tune.mxl
python scripts/fetch_score.py --search "composer=bach numberOfParts=4 timeSignature=3/4"
# 32 matches / bach/bwv11.6.mxl / bach/bwv122.6.mxl / …
```

Schemes: `corpus:` `humdrum:owner/repo[@branch]/path` `kernscores:` `session:id[/n]`
`jrp:` `mfiles:` `mutopia:` `url:`. A bare argument is tried as a local path, then a URL,
then a corpus path. `--raw` prints the fetched bytes instead of parsing (useful to see a
Humdrum header or the thesession JSON); it refuses `corpus:`, which is already local.
Responses are cached under `$TMPDIR/m21fetch` (override with
`M21_FETCH_CACHE`); `--no-cache` bypasses. Fetch failure prints
`FETCH FAILED <Type>: <msg>` to stderr and exits **2**, so a shell loop can tell a dead
link from an empty score.

Tested live against: bundled corpus, craigsapp Humdrum (5 repos), ccarh Essen,
kernscores CGI, thesession.org, JRP, mfiles, Mutopia, OpenScore Lieder + StringQuartets,
POP909, Nottingham/jukedeck — 13 distinct hosts, all green.

---

## 5. Choosing a source for a task

| you want | use |
|---|---|
| four-part harmony to learn voice-leading from | `corpus` Bach chorales (offline, 433) or `craigsapp/bach-370-chorales` |
| modal counterpoint | `corpus` palestrina (1,318), josquin, `jrp:` ids |
| melody statistics, n-gram models | `corpus` essenFolksong (8,545 works, monophonic, offline) |
| Irish/British trad heads to arrange | `session:`, `jukedeck/nottingham-dataset` |
| piano writing with real pedalling/voicing | `craigsapp/{beethoven,mozart,haydn,scarlatti}-*` |
| romantic song + a ready RomanText analysis | `OpenScore/Lieder` (CC0 — safest licence of the lot) |
| something you may ship commercially | **CC0 only**: OpenScore Lieder/StringQuartets, thesession.org |
| bulk training data | Lakh `clean_midi` (230 MB) before `lmd_full` (1.77 GB) |
| expressive timing to imitate | MAESTRO |

---

## Gotchas

1. **`kern.humdrum.org` is 503.** Every tutorial points there. Use
   `http://kernscores.stanford.edu/cgi-bin/ksdata` — same query API, returns 200.
2. **`corpus.cacheMetadata` forks.** Run it from a `.py` file under
   `if __name__ == '__main__':`. From `python -c`, a heredoc, or a notebook cell it
   spawns children that die with `FileNotFoundError: …/<stdin>` in a loop.
3. **`field='timeSignatures'` returns 0; `field='timeSignature'` returns 1,875.** Field
   names are prefix-matched, and the prefix hits `timeSignatureFirst`. An unknown field
   never errors — it silently returns an empty bundle. Verify with
   `MetadataBundle.listSearchFields()`.
4. **`ambitus` is unsearchable as a string.** It is an `AmbitusShort` namedtuple; filter
   `e.metadata.ambitus.semitones` in Python.
5. **Files ≠ works.** `len(corpus.getCorePaths())` is 3,194 but the bundle has 15,112
   entries. ABC files are `Opus` objects — `corpus.parse('essenFolksong/teste')` gives
   you an `Opus`, not a `Score`. Index with `number=`, or take `.scores[0]`.
6. **`entry.metadata.filePath` points at the maintainer's laptop.** Use `sourcePath`
   (relative) or `corpusFilePath`.
7. **`corpus.virtual` is dead** (off since 2017). It imports fine and lists URLs that
   nothing fetches.
8. **`chorales.Iterator(numberingSystem='title')` is unimplemented** — length 0, and
   iterating raises.
9. **Binary formats need a real file suffix.** `.mxl` and `.mid` bytes handed to
   `converter.parse()` guess wrong; write a `NamedTemporaryFile(suffix='.mxl')` first.
10. **mfiles.co.uk is free-to-download, not free-to-use** — "© 1999-2026 Music Files
    Ltd. All rights reserved." Fine for private analysis, not for redistribution.
11. **CCARH data (Essen, MuseData, most of kernscores) forbids commercial derivative
    editions, public performance, and sound recording.** Read
    `essen-folksong-collection/license.txt`. The craigsapp repos are CC BY-NC-SA 4.0 —
    also non-commercial. **OpenScore is the only large CC0 set here.**
12. **IMSLP file links are a JS interstitial**, and the payload is a PDF scan anyway.
    Its API (`API.ISCR.php`, type=1 composers / type=2 works, 1,000 rows per page) is
    fully open and is the right way to use it.
13. **GitHub's unauthenticated API is 60 requests/hour.** Enumerating many repos with
    `/git/trees/<branch>?recursive=1` hits 403 fast. One recursive tree call per repo,
    cache the result, or send a token.
14. **`raw.githubusercontent.com/<owner>/<repo>/master/...` works even when the repo's
    only branch is `main`.** Convenient, but if you get a 404 retry with `main` before
    assuming the path is wrong.
15. **`abcnotation.com` times out** — do not route ABC lookups through it.
16. **Performance MIDI (MAESTRO, GiantMIDI, Lakh) is unquantised.** Parse then
    `s.quantize((4, 3), processOffsets=True, processDurations=True)` before you trust a
    measure count or a time signature.
17. **Lakh is http-only.** `https://hog.ee.columbia.edu/...` fails to connect; plain
    `http://` returns 200.
