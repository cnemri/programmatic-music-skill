# 15 — Verifying music you cannot hear

You are going to produce a piece, be unable to listen to it, and have to decide whether it
is finished. This chapter is how you decide with evidence instead of hope.

The failures below are all ones that produce a file that *renders fine* and is *wrong*.
None of them raise an exception. Every one is cheap to detect and expensive to ship.

---

## The failure modes, ranked by how often they bite

| # | Failure | Symptom you would hear | How to detect |
|---|---|---|---|
| 1 | MIDI channel folding | notes cut short, thin texture | `verify.full_report(midi_path=...)['midi_channel_collision']` |
| 2 | Percussion not on channel 10 | drums play as a piano | `midiio.describe_midi` — perc track must show channel 10, no program |
| 3 | Notes below the instrument's range | boomy, synthetic, "not a guitar" | `verify.range_check` |
| 4 | Wrong section is loudest | climax buried under a busy interlude | `verify.section_levels` → `is_peak` |
| 5 | Clipping | distortion | `verify.audio_stats`, `peak_dbfs >= -0.1` |
| 6 | Melody buried | you can't follow the tune | `verify.density_by_part` + stem levels |
| 7 | Harmonic slip | one chord fights the melody | `verify.outside_mode` |
| 8 | Mechanical rhythm | sequencer, not a player | `verify.rhythm_report` |
| 9 | Misquoted source melody | "that isn't Bella Ciao" | `verify.melody_match` |
| 10 | Fade never fires | abrupt cut, or 6 s of silence | compare `audio_stats['duration_s']` to the fade start |

---

## Symbolic checks — before you render

Cheap. Run them all.

```python
from m21kit import verify, scales

pitched = verify.pitched_parts(score)      # drums are GM key numbers, not pitches!

verify.pitch_report(pitched)
# {'notes': 397, 'lowest': 'D3', 'highest': 'G5', 'ambitus_semitones': 29,
#  'pitch_class_names': ['C','C#','D','E','F','G','A','A#']}

verify.outside_mode(pitched, [p % 12 for p in scales.pitches('hijaz', 'D4')])
# {'outside': {'E': 74, 'C#': 30}, 'outside_pct': 30.7}
```

**Interpreting `outside_mode` is a judgement call, not a pass/fail.** In the example above
the E naturals come from a C major chord and the C♯s from A7 — both correct, because
flamenco mixes A aeolian for the cadence chords with A Phrygian dominant for the tonic.
What the tool is for is the *other* case: one pitch class appearing hundreds of times that
you cannot explain. That is a wrong chord, and you will find it in `first_offsets`.

```python
verify.rhythm_report(score)
# velocity_distinct: 1        -> you never varied dynamics
# distinct_durations: 2       -> every note is the same length
# offset_grid_pct: 100.0      -> nothing is off the beat, ever
```

```python
from music21 import instrument
verify.range_check(part, instrument.AcousticGuitar())
verify.range_check(bass_part, low=40, high=88)      # when the class has no range
```

```python
verify.key_check(pitched, expected='d minor')
# {'detected': 'd minor', 'confidence': 0.87, 'match': True}
```
Low confidence is *not* automatically a failure — a Krumhansl profile is built on
common-practice tonality and is genuinely confused by modal, maqam and pentatonic music.
A confident answer a tritone away from what you wrote *is* a failure.

---

## MIDI checks — after writing, before rendering

```python
from m21kit import midiio
for t in midiio.describe_midi('out.mid'):
    print(t)
# {'track': 1, 'name': 'Acoustic Guitar', 'channels': [1],  'programs': [24], 'notes': 374}
# {'track': 2, 'name': 'Acoustic Guitar', 'channels': [2],  'programs': [24], 'notes': 1637}
# {'track': 5, 'name': '',                'channels': [10], 'programs': [],   'notes': 738}
```

What you are checking:
- **every note-bearing track has a distinct channel.** Two tracks both showing `[1]` is
  channel folding — notes are being cut short right now.
- **the percussion track shows channel 10 and no program.** A program change on 10 is
  harmless on most synths but the *absence* of channel 10 means drums-as-piano.
- **note counts are what you expect.** An order-of-magnitude surprise means a loop bug.

Meta events (track name, end-of-track) and `DeltaTime` objects carry channel 1 and are not
a collision. Only count real note events.

---

## Audio checks — after rendering

```python
verify.audio_stats('out.mp3')
# {'duration_s': 210.09, 'peak_dbfs': -1.2, 'clipped': False,
#  'lufs': -14.1, 'true_peak_dbtp': -1.2, 'lra': 11.0}
```

`peak_dbfs` of exactly 0.0 means it clipped — lower the FluidSynth gain and re-render.
`lufs` should be near your target. `lra` under ~4 on music that is supposed to be dynamic
means the compressor flattened it.

### The dynamic arc

The single most valuable audio check. Compute section boundaries from the **tempo map**,
not by eye — under tempo changes, bars and seconds are not proportional, and guessed
boundaries measure the wrong music.

```python
tm = midiio.TempoMap.from_score(score)
bar = lambda n: tm.seconds((n - 1) * 4)

rows = verify.section_levels('out.mp3', [
    ('intro',   bar(1),  bar(9)),
    ('verse',   bar(9),  bar(28)),
    ('climax',  bar(49), bar(57)),
    ('coda',    bar(57), bar(65)),
])
assert next(r for r in rows if r['is_peak'])['section'] == 'climax'
```

If your climax is not the peak, the mix is wrong however good the notes are. Reach for
*density* to fix it — how many voices are playing and how many notes each spends — before
you reach for velocity. Velocity is not loudness; a section that adds a doubling voice and
a busier iqa' will out-measure one that merely plays harder. In practice
the offender is almost always a dense accompaniment section out-shouting a sparser one —
fix it in the stem gains or by thinning the accompaniment, not by shouting louder.

### Is there a pulse?

```python
verify.pulse('out.mp3', start=20, end=100)
# {'strength': 0.49, 'period_s': 0.395, 'bpm': 152.0, 'metered': True}
```

Restricted to plausible *beat* periods (0.27–1.33 s) on purpose. A naive autocorrelation
locks onto the ~0.1 s tremolo rate or the ~0.03 s strum spread and reports 600 bpm; that
mistake makes the measurement worthless.

- `strength > 0.3` — a clear pulse.
- `strength < 0.1` — genuinely free rhythm. This is how you *prove* a rubato or
  non-metric passage is unmetered rather than merely claiming it.
- The detected bpm is often a simple multiple or fraction of what you wrote — half-bar and
  tresillo periodicities are real features of the music, not errors.

### Did the harmony survive?

```python
verify.harmony_match('out.mp3', [
    (bar(9),  bar(10), 'Dm'), (bar(10), bar(11), 'Dm'),
    (bar(11), bar(12), 'C'),  (bar(12), bar(13), 'A7'),
])
# {'bars': 4, 'root_matches': 4, 'pct': 100.0}
```

Roots only — a chroma estimate cannot reliably separate a triad from its relative minor,
and pretending otherwise produces false alarms. **Above ~85 % root agreement is a pass.**
Name the chord however you like: `Eb` and `D#` are the same root, and any suffix
(`Cmaj7`, `Fm6`, `F#m7b5`, `Gsus4`) is ignored rather than mangled. A name that will not
parse comes back in `unparsed_names` instead of quietly scoring zero, and a segment with no
signal in it reports `detected: None` rather than guessing a chord from silence.
Expect misses in very sparse textures (a single held note gives the estimator nothing) and
where C major and A minor genuinely share content; check whether the same bar reads
correctly in a denser repeat before you go changing it.

### Did you quote the tune correctly?

```python
verify.melody_match(melody_part, expected=[64,69,71,72,69, 64,69,71,72,69], transpose=0)
# {'mode': 'pitch-sequence', 'expected': 10, 'matched': 10, 'pct': 100.0}
```

Use this whenever you arrange existing material. It is the difference between "I
transcribed it" and "I believe I transcribed it". With `(offset, midi)` pairs it also
checks placement, which catches an off-by-one-bar section start.

---

## One call

```python
rep = verify.full_report(
    sc=verify.pitched_parts(score),
    midi_path='out.mid',
    audio='out.mp3',
    allowed_pcs=[p % 12 for p in scales.pitches('minor', 'D4')],
    expected_key='d minor',
    sections=[('intro', 0, 15), ('climax', 95, 120)])
```

Or from the shell: `python scripts/verify_music.py out.mp3 --midi out.mid`.

---

## What none of this tells you

Measurement catches errors. It does not tell you the piece is *good* — whether the melody
is memorable, whether the form earns its climax, whether the harmony is interesting. For
those, reason about the music explicitly before you write it: name the form, name the
climax, name what makes each section different from the last. If you cannot say why a
section exists, the listener will not find a reason either.

And say plainly in your final message that you verified numerically and could not listen.
Do not imply you heard it.
