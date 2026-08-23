---
name: programmatic-music
description: Compose, arrange, analyse and render real music in code with music21 — from scratch or from an existing score or audio file. Use when asked to write/compose/generate a piece, song, melody, chord progression, groove or arrangement; to transcribe or "make an mp3 of" something; to arrange or restyle existing music into another genre (jazz, flamenco, orchestral, lo-fi, metal, maqam, raga…); to harmonise, reharmonise, transpose or change the mode/meter/groove of a score; to analyse a MIDI/MusicXML/audio file for key, chords, form or features; or for anything involving music21, MIDI generation, soundfonts, FluidSynth rendering, or turning notation into audio. Don't use for audio DSP with no notes involved (mixing existing stems, mastering a podcast, sound design), or for lyric writing alone.
---

# Programmatic music with music21

music21 models **notation** superbly and models **performance** not at all, and it does not
render audio. That gap is where generated music goes wrong: theoretically correct, audibly
dead, or silently broken in ways you cannot hear because you cannot listen.

This skill covers both halves — the library in depth, and the performance and rendering
layer that turns a Stream into something a person would play twice.

## Setup

```bash
pip install music21                          # 10.5.0 stable; everything here is verified on it
brew install fluidsynth ffmpeg               # or: apt install fluidsynth ffmpeg
python -c "from m21kit import render; print(render.ensure_soundfont())"   # ~141MB, once
```

`m21kit/` is this skill's helper library — put it on `PYTHONPATH` or copy it into the
project. It is plain functions over music21; nothing is subclassed or monkeypatched.

## The five rules that matter most

1. **Give every Part its own MIDI channel.** music21 folds Parts that share an instrument
   onto one channel, and then one voice's note-off cuts another's identical pitch short.
   Always `midiio.write_midi(score, path, channels=[1,2,3,10])`. Verify with
   `midiio.describe_midi`.
2. **Percussion goes on channel 10** or it plays as a piano.
3. **`Dynamic` scales velocity -- including velocity you set yourself.** A note with
   `velocity = 100` under a `Dynamic('pp')` renders at 50, because the Dynamic multiplies
   rather than defers. Shape velocity by hand and keep `Dynamic` objects out of the Part.
   Hairpins (`Crescendo`/`Diminuendo`) do nothing at all. Default velocity is **90**.
4. **Never write below an instrument's real range.** A guitar stops at E2 (40). Sampled
   patches will render lower notes and they will sound synthetic. `verify.range_check`.
5. **You cannot hear it, so measure it.** Before you call anything finished, run the
   checks in `references/15-verifying-without-listening.md`.

## Workflow

**Composing from scratch**

1. Decide form, key/mode, meter, tempo and instrumentation *in words* first. Name the
   climax. If you cannot say why a section exists, the listener won't find a reason.
2. Build flat Parts and `insert()` at absolute quarter-length offsets — not Measures +
   `append()` — for anything with performance timing. (`references/01-object-model.md`)
3. Melody and harmony from `scales`/`roman`/`harmony`; voicings as real instrument shapes.
4. Add performance: strums, rolls, tremolo, micro-timing, velocity shaping
   (`m21kit.perform`), and a groove from `m21kit.drums`.
5. `render.score_to_mp3(score, out, stems=[...])` — one stem per voice, balanced in dB.
6. Verify. Fix. Re-render.

**Arranging or restyling existing material** — get the score first (`m21kit`
`scripts/fetch_score.py`, or `converter.parse` on MIDI/MusicXML/kern/ABC), extract the
line you want, then treat it as step 3 above. Quote the source exactly and prove it with
`verify.melody_match`; the arrangement lives in the accompaniment, compás and articulation.

**From audio** — `scripts/audio_to_score.py` transcribes to a music21 Score, then as above.

## Reference chapters

Read the one you need; do not read them all.

| | |
|---|---|
| `00-quickstart.md` | shortest path to a working piece |
| `01-object-model.md` | Streams, offsets, `flatten` vs `recurse`, `makeNotation`, deepcopy |
| `02-pitch-notes-chords.md` | pitch, notes, chords, **velocity**, microtones, grace notes |
| `03-meter-tempo-expression.md` | meter incl. additive, tempo maps, ornaments, articulations |
| `04-harmony-scales-theory.md` | intervals, keys, **custom/non-Western scales**, roman numerals, chord symbols, figured bass |
| `05-io-formats.md` | every parse/write format, tinyNotation, MusicXML, PDF/PNG |
| `06-midi-deep.md` | **channels, percussion, ticks, tempo events, round-trip** |
| `07-audio-to-score.md` | transcription: music21's own, and the modern external pipeline |
| `08-analysis-and-verification.md` | key finding, `chordify`, features, self-checking |
| `09-instruments-and-notation.md` | full instrument/GM/range table, transposing instruments |
| `10-scores-and-datasets.md` | where to get scores, verified sources |
| `11-audio-rendering.md` | soundfonts, FluidSynth, stems, mixing, mastering |
| `12-performance-realism.md` | strums, tremolo, swing, humanisation, voicing |
| `13-idioms-and-grooves.md` | concrete style recipes across traditions |
| `14-workflows.md` | end-to-end playbooks |
| `15-verifying-without-listening.md` | **read this before shipping anything** |
| `16-pitfalls.md` | 201 recorded traps, consolidated from every chapter |

## Scripts

```bash
python scripts/analyze_score.py <file|corpus-path>   # key, chords, form, features
python scripts/audio_to_score.py in.mp3 -o out.mid   # audio -> music21
python scripts/fetch_score.py --corpus bach/bwv66.6  # get source material
python scripts/check_ranges.py score.mid --instrument Violin
python scripts/render_audio.py score.mid -o out.mp3  # MIDI -> mastered mp3
python scripts/verify_music.py out.mp3 --midi out.mid
python scripts/build_pitfalls.py                     # regenerate ch.16 after editing a chapter
python scripts/new_project.py my-piece               # scaffold a composition
```

## Honesty

Say that you verified numerically and could not listen. Do not imply you heard it. When
you quote existing music, say what is the source's and what is yours. When a tradition's
rhythm is non-metric (an adhan, an alap, a taranta), do not force it into a compás and
call it faithful — `verify.pulse` will show you whether you did.
