# 00 — Quickstart

The shortest path from nothing to an mp3 that sounds like music. Everything here is
verified working on music21 10.5.0.

---

## Install

```bash
pip install music21
brew install fluidsynth ffmpeg      # apt install fluidsynth ffmpeg
export PYTHONPATH=/path/to/this/repo:$PYTHONPATH
python -c "from m21kit import render; print(render.ensure_soundfont())"
```

---

## The 30-second version

```python
from music21 import stream, instrument
from m21kit import perform, drums, midiio, render, scales

BPM, BAR = 96, 4.0
mel = stream.Part(id='melody'); har = stream.Part(id='chords'); prc = stream.Part(id='drums')
for p in (mel, har):
    p.insert(0, instrument.AcousticGuitar())
midiio.add_tempo_map([mel, har, prc], [(0, BPM)])

Am, F, C, G = [45,52,57,60,64], [41,48,53,57,60,65], [48,52,55,60,64], [43,50,55,59,62,67]
tune = [69, 72, 71, 69, 67, 69, 71, 72]

for bar, ch in enumerate([Am, F, C, G] * 2):
    t = bar * BAR
    perform.arpeggio(har, t, ch, 'pima', step=0.5, vel=64)
    perform.strum(har, t, ch, dur=1.0, vel=84)
    perform.put(mel, t, tune[bar], 1.5, 96)
    perform.put(mel, t + 2, tune[(bar + 3) % 8], 1.5, 90)
    drums.groove(prc, t, 'rock_basic', vel=78, fill=(bar == 7))

score = stream.Score()
for p in (mel, har, prc):
    score.insert(0, p)

render.score_to_mp3(score, 'out.mp3',
    stems=[render.Stem('melody', gain_db=4, eq=[(2600, 1.2, 3)]),
           render.Stem('chords', gain_db=-3, pan=-0.15),
           render.Stem('drums',  gain_db=-6, pan=0.2)],
    channels=[1, 2, 10])
```

Note `channels=[1, 2, 10]`. Get that wrong and the drums are a piano and the two guitars
cut each other off.

---

## Then check it

```python
from m21kit import verify
print(verify.audio_stats('out.mp3'))       # clipped? loud enough?
print(verify.pulse('out.mp3'))             # is the tempo what you wrote?
for t in midiio.describe_midi('out.mid'):  # one channel per part?
    print(t)
```

---

## The five things that will bite you

| | Fix |
|---|---|
| Two parts on one MIDI channel, notes cut short | `midiio.write_midi(..., channels=[...])` |
| Drums play as a piano | that part's channel must be `10` |
| `Dynamic('pp')` halves velocities you set yourself | keep Dynamics out of the Part; set `note.volume.velocity` |
| Bass notes below the instrument's range sound fake | `verify.range_check(part, instrument.AcousticGuitar())` |
| Everything sounds mechanical | vary velocity, add `jitter=0.012`, use a real groove |

---

## Choosing how to build the stream

**Absolute offsets into a flat Part** — for anything with performance timing (strums,
rubato, micro-timing, most generated music):

```python
p = stream.Part()
p.insert(4.0, note.Note('C4'))
p.insert(4.033, note.Note('E4'))     # 17ms later — a strum
```

**Measures and `append()`** — only when you need engraved notation out the other end:

```python
m = stream.Measure(number=1)
m.append(note.Note('C4', quarterLength=1))
part.append(m)
part.makeNotation(inPlace=True)
```

You can convert the first into the second with `makeNotation()`; you cannot get precise
micro-timing back once you have. Start with offsets.

---

## Getting source material

```python
from music21 import corpus, converter
corpus.parse('bach/bwv66.6')                 # ~4000 works ship with music21, offline
converter.parse('song.mid')                  # MIDI, MusicXML, ABC, kern, MEI, …
converter.parse("tinyNotation: 4/4 c4 d e f g1")
converter.parse('https://example.com/x.krn') # any URL music21 can read
```

See `10-scores-and-datasets.md` for verified online sources.

---

## Where to go next

- Composing something in a specific style → `13-idioms-and-grooves.md`
- Custom scale / maqam / raga → `04-harmony-scales-theory.md`
- Arranging an existing piece → `14-workflows.md`
- Audio in → `07-audio-to-score.md`
- Something sounds wrong and you can't hear it → `15-verifying-without-listening.md`
