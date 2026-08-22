# 14 — End-to-end workflows

Five playbooks. Each is the actual order of operations, with the decision points marked.

---

## A. Compose an original piece in a named style

1. **Plan in words first.** `scripts/new_project.py my-piece` writes a PLAN.md with the
   five questions: mode, harmony, rhythmic cell, characteristic gesture, form. Answer them.
   If you cannot say where the piece peaks and why, you are not ready to write code.
2. **Look the style up** in `13-idioms-and-grooves.md`. If it is not there, answer the five
   questions from research, not from vibes.
3. **Scale and voicings.** `scales.pitches(name, tonic)`; write chord voicings as real
   instrument shapes with the open strings where a player would have them.
4. **Skeleton**: a SECTIONS table (name, bars, chords, intensity), then a loop. Keep the
   form in data so changing it is one edit.
5. **Performance layer**: `perform.strum` / `roll` / `tremolo` / `run`, velocity shaping,
   `jitter`, and a groove from `drums.GROOVES`.
6. **Render** with one `render.Stem` per part.
7. **Verify** (`15-verifying-without-listening.md`), fix, re-render.

The trap at step 5: making a climax louder by raising velocity. Loudness follows **note
density**. To make a section peak, add voices — octave doubling, a denser strum pattern,
more of the groove — not a bigger number.

---

## B. Arrange an existing score into another style

1. **Get the real notes.** `corpus.parse`, `converter.parse`, or `scripts/fetch_score.py`.
   Never reconstruct a melody from memory — you will be subtly wrong and confident.
2. **Analyse it**: `scripts/analyze_score.py` for key, chords per bar, ambitus, form.
   Read the source's own bass line for the harmony; it is more reliable than a chord
   detector.
3. **Choose the transposition as a compositional act.** Look for an alignment between the
   source's harmony and the target style's. Real example: Mozart 40/i is in G minor; down
   a fourth to D minor puts the Andalusian cadence on Dm–C–B♭–A, which is flamenco *por
   medio* — so Mozart's dominant becomes the target style's tonic, and his E♭–D sigh
   becomes the Phrygian ♭2–1. That alignment is the arrangement's whole argument. Look for
   one before you pick a key by convenience.
4. **Extract the line verbatim**: snap offsets to a sixteenth grid, take durations to the
   next attack, transpose. Check the range afterwards — a transposition can push a violin
   line off the bottom of a guitar.
5. **Write the accompaniment in the target idiom.** This is where the arrangement lives.
6. **Prove the source survived**: `verify.melody_match(part, [(offset, midi), ...])`.
   Anything under 100 % means you dropped or displaced notes.
7. Render, verify, and **say in your write-up which notes are the composer's and which
   are yours.**

`templates/arrangement.py` is this, working.

---

## C. Audio in → score → new arrangement

1. `scripts/audio_to_score.py in.mp3 -o out.mid` — see `07-audio-to-score.md` for which
   transcriber to use and how good it actually is.
2. **Clean up.** Raw transcription is messy: `stream.quantize()`, drop notes under a
   duration or velocity floor, merge repeated pitches, `stream.stripTies()`.
3. **Understand it**: `analyze('key')`, `chordify()`, `analysis.discrete` for key over
   time. Get the form before you touch the notes.
4. Then workflow B from step 3.

Be honest about transcription quality. Polyphonic audio → MIDI is imperfect; if the source
is dense, take the chord chart and the melody and re-voice rather than trusting every note.

---

## D. Analyse a score and report on it

```bash
python scripts/analyze_score.py corpus:bach/bwv66.6
python scripts/analyze_score.py song.mid --json
```

Gives key (with confidence and alternatives), chords per bar as Roman numerals and chord
symbols, ambitus per part, meter, tempo, and a feature vector. `08-analysis-and-verification.md`
covers windowed key analysis, `chordify` in depth, and feature extraction.

---

## E. Produce printed notation

Composition at absolute offsets is not notation. To engrave:

```python
part.makeNotation(inPlace=True)      # measures, ties, beams, accidentals
score.write('musicxml', 'out.musicxml')
score.write('musicxml.pdf', 'out.pdf')     # needs MuseScore configured
```

Note that `makeNotation` will **quantise away** the micro-timing that makes the audio
sound alive. Keep two versions: the performance score you render, and a
`copy.deepcopy` you notate. See `05-io-formats.md` for the MuseScore/LilyPond setup and
`09-instruments-and-notation.md` for the full pipeline.

---

## Where time actually goes

In practice, on a piece of any size:

| | |
|---|---|
| deciding the form and the mode | 15 % — and it determines everything downstream |
| writing the notes | 25 % |
| the performance layer | 25 % — this is what makes it not sound generated |
| mixing (stem levels) | 15 % |
| verifying and fixing | 20 % |

The two most common ways to waste a whole cycle: rendering before checking the MIDI
channels, and picking stem levels before looking at `verify.density_by_part`.
