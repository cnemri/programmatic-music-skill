# 12 — Performance realism

Notation-accurate MIDI sounds like notation. This chapter is the difference between a
score that is theoretically right and audio a person would listen to twice.

The core claim: **a Chord object is a lie about how instruments work.** Four pitches at one
instant is not what a guitarist, a harpist, a string section or a pianist produces. Almost
everything below is about restoring the time and level structure that notation throws away.

---

## Write at absolute offsets

For anything performance-shaped, build flat Parts and `insert()` at absolute
quarter-lengths. Measures + `append()` is for engraving; it fights you the moment you need
a note 20 ms early.

```python
from music21 import stream
p = stream.Part(id='guitar')
p.insert(12.033, note)          # 33 ms after beat 4 of bar 4 at 120bpm
```

Then write MIDI with `midiio.write_midi`, which bypasses the converter's `makeNotation`
and preserves those offsets exactly. `score.write('midi')` may quantise them away.

Resolution: music21 writes **10080 ticks per quarter** (`defaults.ticksPerQuarter`), chosen
so triplets, quintuplets and septuplets all divide exactly. At 120 bpm one tick is ~0.05 ms,
so 1/10080 ql is the practical floor -- far finer than you need. 5 ms is the smallest
musically useful increment; anything below that is noise.

---

## 1. Strums, rolls, arpeggios

A strum is a chord smeared across time, low string to high, with the last-struck strings
loudest and the first-struck ringing longest.

```python
perform.strum(part, offset, [45,52,57,61,64], dur=1.0, vel=88, spread=0.035)
```

`spread` in quarter-lengths. At 120 bpm (1 QL = 0.5 s):

| Gesture | spread QL | ms/string |
|---|---|---|
| fast up-stroke | 0.018 | ~9 |
| normal down-strum | 0.030–0.040 | 15–20 |
| slow expressive rasgueo | 0.050–0.060 | 25–30 |
| piano rolled chord | 0.040 | 20 |
| harp gliss | 0.06–0.10 | 30–50 |

Three details do most of the work, and `perform.strum` applies all three:
1. **duration taper** — the first string struck rings longest.
2. **top boost** — the last two strings are a few velocity units louder.
3. **direction** — up-strums reverse the order *and* are usually shorter and quieter.

A repeated strum is a **roll**: `perform.roll` / `rasgueado`. What makes a roll sound like
a hand and not a repeat is (a) a crescendo into the beat, (b) alternating sweep direction,
(c) the inner hits using only the top strings.

---

## 2. Sustaining on a plucked instrument

A guitar cannot hold a note. It fakes one with **tremolo** — and so must you, or every
long note dies to silence mid-phrase.

```python
perform.tremolo(part, offset, pitch=76, dur=2.4, vel=82, rate=0.1)
```

The envelope is the whole trick: a swell over the first ~14 %, a gentle fall over the tail,
and a few velocity units of ~5 Hz undulation that the ear reads as vibrato. Flat repetition
at a fixed velocity sounds like a stuck key.

Classical/flamenco tremolo proper is **p-a-m-i**: thumb on the bass on the beat, then three
fast repeats of the melody note — `perform.guitar_tremolo`.

For decaying sampled instruments under a long phrase, `perform.sustain(..., retrigger=1.0)`
re-strikes quietly so the line does not vanish.

---

## 3. Velocity is the melody of dynamics

**`Dynamic` objects DO scale MIDI velocity -- including velocities you set yourself.**
A `Dynamic('pp')` in the Part renders unmarked notes at 45 and `ff` at 127; and a note you
explicitly gave `velocity = 100` comes out at **50** under that `pp`, because the Dynamic
multiplies rather than defers. If you are shaping velocity by hand, keep `Dynamic` objects
out of the Part. Hairpins (`Crescendo`/`Diminuendo`) do nothing at all -- ramp by hand.

```
no Dynamic                       -> [90, 90, 90, 90]      (90 is the default, not 64)
Dynamic('pp') then Dynamic('ff') -> [45, 45, 127, 127]
Dynamic('pp') + velocity = 100   -> [50, 50]              <- your value was halved
Crescendo spanner                -> [90, 90, 90, 90]      <- no effect
```

```python
n.volume.velocity = 96                       # per note
perform.crescendo(part, 32.0, 48.0, 60, 112) # ramp across an offset window
```

Ranges that read correctly through a GM soundfont:

| | velocity |
|---|---|
| ghost / palm-muted / *palmas sordas* | 25–45 |
| p | 50–65 |
| mf | 70–85 |
| f | 90–105 |
| ff / accent | 108–120 |

Never exceed ~120; the top of the range is compressed in most sample sets and 127 buys
nothing. Never use a single velocity for a whole part — `verify.rhythm_report` reports
`velocity_distinct`, and a value of 1 is a red flag.

---

## 4. Micro-timing

Perfect grid alignment is the single loudest "this was generated" signal.

- **Jitter**: ±8–15 ms on every note (`put(..., jitter=0.012)`). Blunt but effective.
- **Deliberate feel** beats jitter: a backbeat snare a few ms *late* drags, a bass note a
  few ms *early* pushes. Program the intent, then add small jitter on top.
- **Swing**: `perform.swing(stream, ratio=0.62)` moves off-beats later. 0.5 straight,
  0.667 triplet, 0.58–0.62 the usual medium-up jazz feel. Swing the eighths (`unit=0.5`)
  or the sixteenths (`unit=0.25`), never both.
- **Rubato** in free-rhythm music is not jitter — it is composed. Write the phrase in
  seconds (set tempo 60 so 1 QL = 1 s) and place each note where it belongs.

---

## 5. Ornaments and slides

- **music21 ornaments do not sound.** A `Trill` in a stream exports as one plain note.
  Call `stream.realizeOrnaments()` to expand them into real notes, or write them out.
- **Grace notes**: real music21 grace notes have zero MIDI duration and frequently produce
  nothing. `perform.grace_into(part, offset, grace_pitch, vel)` places a short real note
  ~75 ms *before* the beat, which always sounds and reads as a scoop or acciaccatura.
- **Slides/portamento** need pitch bend, which is per-channel. For one sliding voice, give
  it its own channel. Usually a grace note is cheaper and good enough.
- **Melisma / hammer-ons**: `perform.ligado` — deliberately overlapping short notes, only
  the first properly struck.

---

## 6. Voicing like a player, not a theorist

`chord.Chord(['C4','E4','G4'])` is a theory object. Real instruments have fixed shapes:

```python
# guitar, standard tuning E2 A2 D3 G3 B3 E4
Am   = [45, 52, 57, 60, 64]           # x02210
E7b9 = [40, 47, 52, 56, 59, 65]       # 0-2-2-1-0-1, the flamenco E
Dm   = [45, 50, 57, 62, 65]           # A2 in the bass, por medio
```

Rules that matter:
- **Nothing below the instrument's lowest note.** A guitar stops at E2 = 40. Writing 33
  (A1) gives you a boomy synthetic thud. `verify.range_check` catches it.
- **Keep the same voicing across a progression** where a player would — the open strings
  that ring through are half the sound.
- **Don't double the third** in close position; it muddies through a sampled patch.

---

## 7. Ensemble behaviour

- **Never let two parts play the identical pitch at the identical offset on the same MIDI
  channel** — the first note-off kills both. Separate channels (`midiio.retrack`) or
  offset one by 10–20 ms, which is what two players would do anyway.
- **Octave doubling** at −25 to −30 velocity thickens a line without a second audible part.
- **Section entries** are staggered in real ensembles. Ten ms of spread across a "unison"
  is the difference between a section and a sampler.

---

## 8. Percussion

Grooves are in `m21kit.drums`. Three things distinguish a real groove:
- **Ghost notes** — the quiet snare sixteenths between backbeats, at 25–35 % velocity, are
  what make funk funky. Omit them and it is a drum machine.
- **Accent hierarchy** — never one velocity per instrument. Downbeat > backbeat > offbeat >
  ghost.
- **The right pattern for the tradition.** A bulería is a 12-beat cycle accented 12-3-6-8-10,
  not a 4/4 with accents moved; a maqsum is not a rock beat with congas. `drums.GROOVES`
  has the patterns; `drums.list_grooves()` lists them.

---

## Checklist before you render

```python
r = verify.rhythm_report(score)
assert r['velocity_distinct'] > 10          # not one flat dynamic
assert r['distinct_durations'] > 3          # not all one note length
assert r['offset_grid_pct'] < 95            # not everything nailed to the beat
verify.range_check(part, instrument.AcousticGuitar())
verify.density_by_part(score)               # set stem levels from this
```
