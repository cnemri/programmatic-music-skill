# Audio to Score: Transcribing Recordings into music21

Someone hands you an mp3 and asks you to re-arrange it. This chapter gets that audio into a
`stream.Score` you can edit. It covers music21's own `audioSearch` (tested, and mostly a
museum piece), the external pipeline you should actually use (basic-pitch, librosa, demucs),
the bridge from note events into music21, and the cleanup that turns a noisy transcription
into readable notation. Every command and timing below was executed on this machine:
macOS/arm64, Python 3.14.7 and 3.12.10, music21 10.5.0. Source citations are git HEAD (v11.0.0b8).

## Capability matrix

Measured, not guessed. "Works here" means *installed and run on this machine*.

| Task | Best tool | Install | Works here |
|---|---|---|---|
| Polyphonic transcription | **basic-pitch** (ONNX) | `uv pip install "basic-pitch[onnx]" "scipy<1.13" "setuptools<81"` | **y — Python 3.12 only** |
| Monophonic transcription | **librosa `pyin`** | `pip install librosa` | **y — 3.14** |
| Monophonic (neural, robust) | **torchcrepe** | `pip install torch torchcrepe` | **y — 3.14** |
| Monophonic (music21 native) | `audioSearch.transcriber` | ships with music21 | y, but see verdict below |
| Beat + tempo | **librosa `beat.beat_track`** | `pip install librosa` | **y — 3.14** |
| Onset detection | **librosa `onset.onset_detect`** | `pip install librosa` | **y — 3.14** |
| Key | **music21 `.analyze('key')`** on transcribed notes | built in | **y** |
| Chords / harmony | **music21 `.chordify()` + reduction** (below) | built in | **y** |
| Stem separation | **demucs** | `pip install demucs` | **y — 3.14** |
| Chroma / CQT / HPSS / segmentation | **librosa** | `pip install librosa` | **y — 3.14** |
| Drum transcription | *(none good)* — madmom is the usual answer | `pip install madmom` | **n — build fails on 3.14** |
| Optical music recognition (images) | **not music21** — use Audiveris/oemer | — | n/a, see `music21.omr` below |

### Python-version reality check

This machine's default is **Python 3.14.7**, which is too new for most MIR packages.

| Package | 3.14 | Why |
|---|---|---|
| numpy 2.5.2, scipy 1.18.1, librosa 1.0.0, pretty_midi, music21 | ✅ | cp314 wheels exist |
| torch 2.13.0, torchaudio, torchcrepe 0.0.24, demucs 4.1.0 | ✅ | cp314 wheels exist |
| **basic-pitch** | ❌ | needs `tensorflow`/`coremltools`; no cp314 wheels. pip backtracks to basic-pitch 0.2.6, which pins `numpy<1.24`, whose setup.py dies with `AttributeError: module 'pkgutil' has no attribute 'ImpImporter'` |
| **aubio** | ❌ | `failed-wheel-build-for-install` (C extension, no cp314 wheel) |
| **crepe** (TF version) | ❌ | pulls TensorFlow |
| **madmom** | ❌ | build fails; unmaintained, still assumes `numpy<1.24` era APIs |

**Fallback that works:** make a 3.12 venv with `uv`, which is already on this box.

```bash
uv python install 3.12
uv venv --python 3.12 /tmp/audio312
VIRTUAL_ENV=/tmp/audio312 uv pip install "basic-pitch[onnx]" music21 librosa
VIRTUAL_ENV=/tmp/audio312 uv pip install "setuptools<81" "scipy<1.13"   # see below
```

Two pins are mandatory and neither is documented by basic-pitch:

* `setuptools<81` — `resampy` 0.4.2 imports `pkg_resources`, removed in setuptools 81+.
  Without it: `ModuleNotFoundError: No module named 'pkg_resources'`.
* `scipy<1.13` — basic-pitch 0.3.0 calls `scipy.signal.gaussian`, moved to
  `scipy.signal.windows.gaussian` in 1.13. Without it:
  `AttributeError: module 'scipy.signal' has no attribute 'gaussian'`.

basic-pitch **0.4.0** would fix the scipy call, but it requires `tensorflow-macos<2.16`, which
only has cp39/cp310/cp311 wheels — so 0.4.0 needs Python **3.11**. On 3.12 you get 0.3.0.

---

## Half A: what music21 itself ships

### `audioSearch` anatomy

`audioSearch/__init__.py` is a 2011-era autocorrelation pitch tracker. The pipeline, exactly as
`transcriber.monophonicStreamFromFile` runs it (`audioSearch/transcriber.py:97`):

```
getFrequenciesFromAudioFile   wave.open -> int16 frames -> 1024-sample chunks
  -> autocorrelationFunction  scipy.signal.fftconvolve, parabolic interpolation -> Hz per chunk
  -> detectPitchFrequencies   snap each Hz to the nearest scale degree
  -> smoothFrequencies        7-wide moving average over the Hz series
  -> pitchFrequenciesToObjects  Hz -> pitch.Pitch, with per-run octave averaging
  -> joinConsecutiveIdenticalPitches  run-length encode -> (notes[], sampleCounts[])
  -> notesAndDurationsToStream  histogram-guess a quarter note, snap durations
```

Useful pieces you can call individually:

```python
from music21 import audioSearch, scale
audioSearch.audioChunkLength      # 1024  -> 23.2 ms resolution at 44.1 kHz
audioSearch.recordSampleRate      # 44100 -> HARDCODED, see below

audioSearch.normalizeInputFrequency(441.72)
# (440.0, <music21.pitch.Pitch A4>)

thresholds, pitches = audioSearch.prepareThresholds(scale.MajorScale('A3'))
# log2-fractional bin edges; feed back in to avoid recomputation

audioSearch.smoothFrequencies([440, 220, 440, 440, 442], smoothLevels=3)
audioSearch.quantizeDuration(1.70)      # -> 1.5
```

### The honest test

Rendered a known melody (C-major scale in quarters, then G/E halves and a C whole) with
fluidsynth, then transcribed it back.

```bash
fluidsynth -ni -F raw.wav -r 44100 FluidR3_GM.sf2 scale.mid
ffmpeg -y -i raw.wav -ac 1 -ar 44100 -sample_fmt s16 scale_mono44k.wav
```

```python
from music21.audioSearch import transcriber
p = transcriber.monophonicStreamFromFile('scale_mono44k.wav')
```

| Input | Pitches | Durations |
|---|---|---|
| **mono 44100 (ideal)** | `C4 D4 E4 F4 G4 A4 B4 C5 G4 E4 C4` — **11/11 correct** | `1.5 ×8, 4.0 ×3` — **all wrong** (truth `1×8, 2, 2, 4`) |
| **mono 22050** | `C5 D5 E5 F5 G5 A5 B5 C6 …` — **an octave sharp**, plus two phantom `E10` | wrong |
| **stereo 44100** | one note, `F10` — **total garbage** | n/a |
| **polyphonic mp3 (15 s)** | 15 notes, all `D3/A3/E3` | useless |

Speed is genuinely fine: **0.03 s for 10.8 s of audio (~320× realtime)** once warm. A first
call costs ~15 s because importing `scipy.signal` is lazy — warm up before timing anything.

**All of that requires scipy.** The module docstring says scipy merely "makes the process
faster and more accurate" (`audioSearch/__init__.py:15`). That is wrong: without scipy the
transcriber is *broken*. `autocorrelationFunction` falls back to `numpy.convolve`
(`audioSearch/__init__.py:155`), which — unlike `scipy.signal.fftconvolve` — **preserves the
input dtype**. The samples are `int16`, and the true autocorrelation peak does not fit:

```python
s = numpy.frombuffer(frames, dtype=numpy.int16)     # one 1024-sample chunk
numpy.convolve(s, s[::-1], 'full').dtype            # int16   peak      17883   <- wrapped
fftconvolve(s, s[::-1], 'full').dtype               # float64 peak 85214683.0   <- correct
```

On the identical file that yields 11 correct pitches with scipy installed, the numpy path
yields **one note**. Treat scipy as a hard requirement and check for it explicitly.

### The three hard limits

1. **Sample rate is hardcoded.** `getFrequenciesFromAudioFile` passes the module global
   `recordSampleRate` (44100), never `wv.getframerate()` (`audioSearch/__init__.py:418`). Feed
   it a 22.05 kHz file and every pitch comes out exactly an octave high. **Always resample to
   44100 first.**
2. **Mono 16-bit only.** Frames are read with `numpy.frombuffer(data, dtype=numpy.int16)`. A
   stereo file interleaves L/R into one buffer and the autocorrelation collapses.
3. **The duration lattice is tiny.** `quantizeDuration` only emits
   `{0.25, 0.5, 1.0, 1.5, 2.0, 4.0}` — no `0.75`, no `3.0`, no triplets. Combined with
   `quarterLengthEstimation`, which picks the quarter-note length from an 8-bin histogram, one
   bad guess rescales the whole piece. That is why the pitch-perfect run above still has
   nonsense rhythm.

```python
>>> [audioSearch.quantizeDuration(x) for x in (0.6, 0.9, 2.5, 3.0)]
[0.5, 1.0, 2.0, 4.0]
```

### `recording.py` and `scoreFollower.py`

* `recording.py` needs **PyAudio + portaudio** (`brew install portaudio && pip install pyaudio`),
  not installed here. Microphone only; irrelevant for file transcription.
* `scoreFollower.py` is real-time score following: it repeatedly transcribes short windows and
  matches them against a known `Score` with `music21.search`. It depends on the same weak
  front-end, so it inherits every limit above. Interesting as an algorithm, not as a tool.

### `music21.omr` does not do OMR

Worth stating plainly because the name misleads: **`music21/omr/` contains no image
processing.** It takes MusicXML *already produced by* OMR software and tries to fix it.

* `correctors.ScoreCorrector` — hashes each measure to a string, then runs a horizontal model
  (compare a flagged measure to other measures in the same part) and a vertical model (compare
  across parts at the same moment) via `difflib`, replacing low-confidence measures.
* `evaluators.OmrGroundTruthPair` — counts measure differences between an OMR score and a
  ground truth, before and after correction. Ships Mozart K525 fixtures.

To actually turn a *picture* of a score into MusicXML, use **Audiveris** or **oemer** outside
Python, then `converter.parse()` the result and optionally run `ScoreCorrector` over it.

### Verdict: is `audioSearch` worth using in 2026?

**No, with one exception.** Pitch accuracy on clean, loud, monophonic, mono-44.1 kHz audio is
genuinely good, and it has **zero dependencies beyond numpy/scipy** — no model download, no
network. If you are offline and need the pitch *sequence* of a clean solo line and will fix the
rhythm yourself, it works and it is fast.

For anything else — polyphony, real recordings, anything where rhythm matters — use
`librosa.pyin` (same dependency weight, better tracker, honest sample-rate handling) or
basic-pitch. `audioSearch` has had no substantive algorithmic change since 2011.

---

## Half B: the modern pipeline

### basic-pitch — polyphonic audio → MIDI

Spotify's ICASSP-2022 model. Instrument-agnostic, handles polyphony, emits pitch bends.

```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

# The bundled TF SavedModel will NOT load under TF 2.16 (Keras 3).
# The bundled .onnx does, and is faster. Always prefer it.
model_out, midi_data, note_events = predict(src, str(ICASSP_2022_MODEL_PATH) + '.onnx')
```

Real run — a 210.1 s flamenco arrangement of Mozart's 40th:

```
predict: 2.4s                       # ~87x realtime, CPU only
model_out: {'note': (18067, 88), 'onset': (18067, 88), 'contour': (18067, 264)}
n note_events: 2512
instruments: 1   notes: 2512
median note length: 0.267s          n shorter than 50ms: 0
pitch range: MIDI 40..89
pitch-class histogram: A=635 D=382 E=284 F=245 Bb=273 C#=167 ...
```

That histogram is A–B♭–C♯–D–E–F: **A Phrygian dominant**, which is exactly right for flamenco.
Good sanity check that the transcription is tracking real content, not noise.

Output shapes worth knowing:

* `note_events` — `(start_s, end_s, midi_pitch, amplitude_0_1, [bend, ...])`.
  **They are not sorted by time.** Sort before use.
* `midi_data` — a `pretty_midi.PrettyMIDI`; `midi_data.write('out.mid')` and you are done.
* `model_out` — raw posteriorgrams if you want your own note-creation logic.

Tuning knobs that matter: `onset_threshold` (0.5; raise to drop spurious attacks),
`frame_threshold` (0.3; raise to drop quiet noise), `minimum_note_length` (ms),
`minimum_frequency`/`maximum_frequency` (band-limit to an instrument's range),
`melodia_trick` (on by default; helps monophonic lines).

### librosa — everything that is not note transcription

All of this runs on **Python 3.14** with librosa 1.0.0. Timings are for the same 210 s file at
22050 Hz mono (load: 2.7 s).

```python
import librosa, numpy as np
y, sr = librosa.load(src, sr=22050, mono=True)
```

| Call | Time | Result on the test file |
|---|---|---|
| `librosa.beat.beat_track(y=y, sr=sr)` | 4.32 s | tempo `152.0` bpm, 504 beats |
| `librosa.feature.tempo(y=y, sr=sr)` | — | `152.0` (was `librosa.beat.tempo` before 1.0) |
| `librosa.onset.onset_detect(y=y, sr=sr, units='time')` | 0.30 s | 928 onsets |
| `librosa.feature.chroma_cqt(y=y, sr=sr)` | 0.86 s | `(12, 9048)`; ranked A .53, D .40, A♯ .30 |
| `np.abs(librosa.cqt(y=y, sr=sr))` | 0.10 s | `(84, 9048)` |
| `librosa.effects.hpss(y)` | 7.39 s | harmonic rms .147 / percussive .032 |
| `librosa.piptrack(y=y, sr=sr)` | 0.02 s | `(1025, n)` magnitudes+freqs; crude, prefer `pyin` |
| `librosa.pyin(y, fmin=65, fmax=2093)` | 1.43 s / 20 s audio | 737 / 862 frames voiced |
| `librosa.segment.agglomerative(mfcc, 8)` | 8.28 s | boundaries at 0, 5.7, 26.3, 67.7, 98.0, 198.7 s |

`pyin` is the monophonic workhorse — it returns `(f0, voiced_flag, voiced_prob)`, and turning
that into note events is ~15 lines (see `transcribe_pyin` in the script). On the fluidsynth
scale it is **exactly right**:

```
  0.00   0.51 C4    0.51   1.00 D4    1.00   1.49 E4    1.49   1.97 F4
  1.97   2.48 G4    2.48   3.00 A4    3.00   3.48 B4    3.48   3.97 C5
  3.97   4.99 G4    5.02   5.97 E4    5.97  10.75 C4
```

Pitches 11/11, durations correct — the final C4 runs long only because the soundfont's release
tail keeps sounding, which is a property of the render, not an error in the tracker.

### demucs — stem separation

Works on 3.14. Separate first, then transcribe a single stem: transcription quality on an
isolated instrument is far better than on a full mix.

```bash
pip install demucs
python -m demucs -n htdemucs --two-stems=other -o out/ track.wav   # 20s audio -> 12.7s
python -m demucs -n htdemucs -o out/ track.wav                     # 4 stems
```
Writes `out/htdemucs/<track>/{drums,bass,other,vocals}.wav`. First run downloads weights.

### torchcrepe — neural monophonic f0

Works on 3.14 (`pip install torch torchcrepe`). More robust than `pyin` on noisy or breathy
material; slower.

```python
import torch, torchcrepe, librosa
y, sr = librosa.load(path, sr=16000, mono=True)          # crepe requires 16 kHz
f0, periodicity = torchcrepe.predict(
    torch.tensor(y)[None], 16000, hop_length=160,
    fmin=50, fmax=1000, model='tiny',                     # 'full' is better and ~5x slower
    return_periodicity=True, device='cpu')
```
`tiny` took **5.8 s for 10.8 s of audio**. Gate on `periodicity > 0.5`, then run the same
run-length grouping used for `pyin`.

---

## The bridge: note events → music21

Two routes. Both end in a `Score`.

### Route 1 — via MIDI (shortest)

```python
midi_data.write('t.mid')                       # pretty_midi from basic-pitch
sc = converter.parse('t.mid')                  # 0.7s for 2512 notes
```

**Know what `converter.parse` silently does to MIDI:** it quantizes on import.

```python
converter.parse('t.mid')                       # 1473 objects,  29 distinct quarterLengths
converter.parse('t.mid', quantizePost=False)   # 2280 objects, 299 distinct quarterLengths
```

So `sc.quantize(...)` on a default-parsed MIDI looks like a no-op — because the work already
happened, on a grid you did not choose. The object count also drops because music21 fuses
notes that quantization pushed onto the same offset into `Chord`s. **Parse with
`quantizePost=False` whenever you want to control the grid yourself.**

### Route 2 — events straight into a Part (full control)

Skips MIDI entirely; keeps amplitude as velocity. `bpm` converts seconds to quarterLengths.

```python
from music21 import instrument, metadata, note, stream, tempo

def events_to_score(events, bpm, title='Transcription'):
    qps = bpm / 60.0                                   # quarters per second
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=title)
    p = stream.Part()
    p.insert(0, tempo.MetronomeMark(number=bpm))
    p.insert(0, instrument.Piano())
    for start, end, midi, amp in events:
        n = note.Note(midi)
        n.quarterLength = (end - start) * qps
        n.volume.velocity = max(1, min(127, int(amp * 127)))
        p.insert(start * qps, n)                       # insert, NOT append
    sc.insert(0, p)
    return sc
```

Use `insert(offset, n)`, never `append` — transcribed notes overlap, and `append` would
serialise them into a monophonic smear.

---

## Cleanup recipes

Raw transcription is unreadable. Apply these in order.

### 1. Drop sub-threshold notes (before building the Score)

```python
kept = [e for e in events if (e[1] - e[0]) >= 0.05 and e[3] >= min_amplitude]
```
Duration and amplitude thresholds together remove most spurious partials. On real output:
`310 -> 310 after threshold -> 159 after merge`.

### 2. Merge repeated pitches

Pitch trackers break one sustained note into fragments across a brief unvoiced dip.

```python
merged, by_pitch = [], {}
for s, e, m, a in sorted(kept):
    prev = by_pitch.get(m)
    if prev is not None and s - prev[1] <= merge_gap:   # 0.03 is a good default
        prev[1] = max(prev[1], e); prev[3] = max(prev[3], a)
        continue
    row = [s, e, m, a]; merged.append(row); by_pitch[m] = row
```

### 3. Quantize

```python
sc.quantize(quarterLengthDivisors=(4, 3), processOffsets=True,
            processDurations=True, inPlace=True, recurse=True)
```
`(4, 3)` = sixteenths **and** triplet-eighths; music21 picks whichever fits each note better.
Use `(4,)` for straight-only, `(8, 6)` for demisemis + triplet-sixteenths. Measured on the
unquantized parse: **299 distinct quarterLengths → 19, in 0.10 s, with zero notes collapsed to
length 0.** Coarser grids read better; `(2,)` or `(1,)` before `chordify()` is often right.

### 4. Infer key

```python
k = sc.analyze('key')
# <music21.key.Key of d minor>   correlationCoefficient 0.82
k.alternateInterpretations[:3]
# [F major 0.631, g minor 0.579, a minor 0.553]
```
Check `correlationCoefficient`. Above ~0.8 is trustworthy; the 0.51 you get from a 20 s muezzin
excerpt is not, because Krumhansl-style profiles assume common-practice tonality. See
`04-harmony-scales-theory.md`.

### 5. Time signature

Transcription gives you no meter. music21's MIDI parser inserts a default `4/4`. Either supply
it, or derive it from librosa's beat grid:

```python
_, beats = librosa.beat.beat_track(y=y, sr=sr)
# group beat intervals, look for a period-3 or period-4 accent pattern
p.insert(0, meter.TimeSignature('3/4'))
p.makeMeasures(inPlace=True)
```

### 6. Chordify — and why you must reduce first

```python
sc.chordify()          # 2193 verticalities from a 210s transcription. Unusable.
```
Every onset misalignment creates a new vertical slice. Collapse each bar to the pitch classes
that actually sounded longest:

```python
def harmonic_reduction(sc, max_pitches=3):
    ch = sc.chordify()
    if not ch.getElementsByClass(stream.Measure):
        ch.makeMeasures(inPlace=True)
    k = sc.analyze('key')
    out = stream.Part(id='reduction')
    out.insert(0, m21key.Key(k.tonic.name, k.mode))
    for m in ch.getElementsByClass(stream.Measure):
        weight = {}
        for el in m.recurse().notes:
            for pp in el.pitches:
                weight[pp.pitchClass] = weight.get(pp.pitchClass, 0.0) + float(el.quarterLength)
        if not weight:
            out.append(note.Rest(quarterLength=4.0)); continue
        c = chord.Chord(sorted(sorted(weight, key=weight.get, reverse=True)[:max_pitches]))
        c.quarterLength = m.barDuration.quarterLength
        try: c.addLyric(roman.romanNumeralFromChord(c, k).figure)
        except Exception: pass
        out.append(c)
    return out
```

Real output on the flamenco Mozart, key `d minor`:

```
m1   D-minor triad                  i
m2   A-tritone-fourth               v54
m3   A-major triad                  V6
m4   D-minor triad                  i
m5   C-incomplete dominant-seventh  bVII7
m6   Bb-incomplete major-seventh    bVI65
m7   D-quartal trichord             i52
m8   D-minor triad                  i
m9   Bb-incomplete major-seventh    bVI65
m10  D-minor triad                  i
```

`i – V – i – ♭VII – ♭VI – i`: the Andalusian cadence, recovered from an mp3. That is the level
of correctness to aim for — the reduction is meaningful even where individual notes are wrong.

---

## The complete script

`scripts/audio_to_score.py`. Auto-selects the best available backend and degrades when
optional deps are missing.

```bash
# polyphonic, on the 3.12 venv where basic-pitch lives
/tmp/audio312/bin/python scripts/audio_to_score.py song.mp3 \
    --max-seconds 30 -o out.musicxml --reduce

# monophonic melody, works on 3.14 with nothing but librosa
python scripts/audio_to_score.py solo.wav --backend pyin --monophonic --tempo 120 --show

# music21-only, zero external deps
python scripts/audio_to_score.py solo.wav --backend audiosearch --monophonic
```

Verified run (3.12, basic-pitch, first 30 s of the flamenco mp3):

```
[1/5] source: mozart40_flamenco.mp3
  auto-selected backend: basic-pitch
[2/5] transcribing with basic-pitch
  basic-pitch: 310 events in 0.7s
[3/5] cleaning events
  cleanup: 310 -> 310 after threshold -> 159 after merge
  estimated tempo: 143.6 bpm
[4/5] building Score
[5/5] quantize / key / meter
  quantize(4, 3): 0.00s
  key: d minor (r=0.80)
done in 9.3s
wrote out.musicxml
parts: 2   objects: 248   range: G2 - E6   measures: 18   key: d minor (r=0.82)
```

Verified run (3.14, no basic-pitch, auto → pyin), the fluidsynth scale — a perfect round trip:

```
{0.0} <music21.stream.Measure 1>   C D E F     (each 1.0)
{4.0} <music21.stream.Measure 2>   G A B C     (each 1.0)
{8.0} <music21.stream.Measure 3>   G(2.0) E(2.0)
{12.0} ... C tie=start / C tie=continue / C tie=stop
```

The final note is tied across three bars because the soundfont's reverb tail sustained it;
`makeNotation` split and tied it correctly. Requesting a missing backend fails loudly with the
fix:

```
$ python audio_to_score.py x.wav --backend basic-pitch
backend 'basic-pitch' needs 'basic_pitch', which is not installed.
  pip install basic-pitch onnxruntime
```

Key flags: `--backend {auto,basic-pitch,pyin,audiosearch}`, `--monophonic`, `--tempo`,
`--quantize 4,3`, `--time-signature`, `--min-duration`, `--min-amplitude`, `--merge-gap`,
`--max-seconds`, `--transpose`, `--chordify`, `--reduce`, `--no-key`, `--show`.

---

## Adapt it to something else

Once you hold a `Score`, transcription is over and every other chapter applies. All verified on
the score produced above.

```python
sc = converter.parse('out.musicxml')          # 2 parts, 268 objects, d minor
```

**Transpose** — see `02-pitch-notes-chords.md`.
```python
sc.transpose(interval.Interval('m3'))          # -> f minor
sc.transpose(3)                                # semitones, same thing
```

**Change mode** — map scale degrees through a new key. See `04-harmony-scales-theory.md`.
```python
k, tgt = sc.analyze('key'), m21key.Key('D', 'major')
for n in part.flatten().notes:
    d = k.getScaleDegreeFromPitch(n.pitch, comparisonAttribute='pitchClass')
    if d: n.pitch = tgt.pitchFromDegree(d)
# verified: 250 notes -> analyze('key') == D major
```

**Extract the melody** — take the top voice of each verticality.
```python
top = stream.Part()
for el in sc.parts[0].flatten().notes:
    top.append(note.Note(max(el.pitches, key=lambda p: p.midi),
                         quarterLength=el.quarterLength))
```
Or transcribe with `--monophonic`, or run demucs first and transcribe only the lead stem.

**Re-harmonize** — feed the reduction's roman numerals into new chords; `04-harmony-scales-theory.md`.

**Change meter / groove** — strip bars, insert a new `TimeSignature`, re-bar. Verified: the
same material re-barred to `3/4` yields 24 measures instead of 18. Groove and swing live in
`13-idioms-and-grooves.md`; humanization in `12-performance-realism.md`.
```python
flat = sc.parts[0].flatten().notes.stream()
flat.insert(0, meter.TimeSignature('3/4'))
flat.makeMeasures(inPlace=True)
```

**Hear it / check it** — `11-audio-rendering.md` for fluidsynth rendering,
`15-verifying-without-listening.md` for validating a score you cannot listen to, and
`scripts/analyze_score.py` for a bar-by-bar harmonic report.

---

## Gotchas

1. **`audioSearch` hardcodes 44100 Hz.** `getFrequenciesFromAudioFile` never reads
   `wv.getframerate()` (`audioSearch/__init__.py:418`). A 22.05 kHz file transcribes exactly an
   octave sharp, silently. Resample first.

2. **`audioSearch` needs mono 16-bit.** Frames go through
   `numpy.frombuffer(data, dtype=numpy.int16)`; stereo interleaving produces one garbage note.
   It also uses stdlib `wave`, so **it cannot open an mp3 at all** — ffmpeg first.

3. **`audioSearch` rhythm is unreliable even when its pitches are perfect.**
   `quantizeDuration` snaps to `{0.25, 0.5, 1.0, 1.5, 2.0, 4.0}` — no `0.75`, no `3.0`, no
   triplets — and `quarterLengthEstimation` guesses the beat from an 8-bin histogram. One bad
   guess rescales the whole piece.

4. **`audioSearch` without scipy silently returns near-nothing.** The `numpy.convolve` fallback
   keeps the `int16` dtype and the autocorrelation peak wraps (85,214,683 → 17,883). Eleven
   correct notes with scipy became **one** without it. The docstring's "faster and more
   accurate" understates this badly. `pip install scipy` before using anything in `audioSearch`.

5. **`music21.omr` performs no optical recognition.** It post-corrects MusicXML that some other
   OMR program produced. For images use Audiveris or oemer.

6. **`converter.parse(midi)` quantizes by default.** `quantizePost=True` is implicit; it also
   fuses notes onto shared offsets into `Chord`s (2280 objects → 1473). Pass
   `quantizePost=False` when you want the grid to be your decision.

7. **basic-pitch `note_events` are not time-sorted.** The first tuple off the model on a 210 s
   file started at 208.3 s. `sorted()` them.

8. **basic-pitch's bundled TensorFlow SavedModel does not load under TF 2.16 / Keras 3.** Point
   `predict()` at `str(ICASSP_2022_MODEL_PATH) + '.onnx'` with `onnxruntime` installed.

9. **basic-pitch needs `setuptools<81` and `scipy<1.13`** on 3.12 (see the install section).
   Neither is expressed in its metadata; both surface as unrelated-looking `AttributeError`s.

10. **basic-pitch cannot be installed on Python 3.14 at all.** pip backtracks to 0.2.6 and dies
   building numpy 1.23 with `pkgutil has no attribute 'ImpImporter'`. That traceback is a
   version-resolution symptom, not a numpy bug — don't chase it. Use a 3.12 venv.

11. **`aubio`, `crepe` and `madmom` all fail to build on 3.14.** librosa covers onsets and beats;
    torchcrepe covers neural f0; nothing here covers drum transcription well.

12. **Use `insert(offset, n)`, not `append`, when building a Part from events.** Transcribed
    notes overlap; `append` serialises them and destroys the timing.

13. **Reverb and release tails become over-long notes.** The tracker keeps following a decaying
    sample. Expect the last note of any rendered phrase to run long, and expect
    `makeNotation` to tie it across several bars.

14. **Never `chordify()` a raw transcription** — 2193 verticalities from one track. Quantize
    coarsely and reduce per measure first.

15. **`librosa.beat.tempo` moved to `librosa.feature.tempo` in librosa 1.0**, and
    `beat_track` now returns tempo as an array — `float(np.atleast_1d(t)[0])`.

16. **Key detection on non-common-practice music is weak.** Always read
    `k.correlationCoefficient` and `k.alternateInterpretations` before trusting `analyze('key')`;
    a modal or microtonal source will still return a confident-looking major/minor key.

17. **The first `audioSearch` call costs ~15 s** importing `scipy.signal` lazily. Warm up before
    you benchmark, or you will conclude it is 500× slower than it is.
