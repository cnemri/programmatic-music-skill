# programmatic-music-skill

An agent skill for composing, arranging, analysing and **rendering** real music in code
with [music21](https://github.com/cuthbertLab/music21).

music21 models notation superbly. It does not model performance, and it does not produce
audio. That gap is where generated music goes wrong — theoretically correct, audibly dead,
or silently broken in ways you cannot hear. This repo covers both halves: the library in
depth, and the performance and rendering layer on top of it.

Written against music21 **10.5.0** (current PyPI stable), with the source read at
`v11.0.0b8`. Every code example was executed.

## What's here

```
SKILL.md            the skill entry point (YAML frontmatter + body)
references/         16 chapters, from the object model to verifying audio you can't hear
m21kit/             the helper library
  midiio.py         MIDI channels, stems, tempo maps, wall-clock timing
  perform.py        strums, rolls, tremolo, arpeggios, humanisation, swing
  drums.py          full GM percussion map + 35 grooves across many traditions
  scales.py         200+ scales: modes, maqamat, ragas, all 72 melakarta, gamelan
  render.py         score -> stems -> mix -> mastered mp3 (FluidSynth + ffmpeg)
  verify.py         how to check your own music numerically
scripts/            CLI tools: render, verify, analyse, transcribe, fetch, scaffold
templates/          runnable starting points for four kinds of piece
```

## Install

```bash
pip install music21
brew install fluidsynth ffmpeg          # apt install fluidsynth ffmpeg
export PYTHONPATH=$PWD:$PYTHONPATH
python -c "from m21kit import render; print(render.ensure_soundfont())"   # ~141MB, once
```

As a CloudCode/Claude skill, clone into your skills directory — `SKILL.md` at the root is
a valid skill definition and the references load on demand.

## Try it

```bash
python templates/minimal.py      -o out.mp3    # smallest complete piece
python templates/groove_piece.py -o out.mp3    # sectioned, groove-driven
python templates/free_rhythm.py  -o out.mp3    # non-metric (taqsim / alap / cante libre)
python templates/arrangement.py --corpus bach/bwv66.6 --transpose -3 -o out.mp3
```

Each prints a verification report: loudness, clipping, whether the detected tempo matches
what you wrote, whether the climax is actually the loudest section.

## The five things that break generated music

1. **MIDI channel folding.** music21 puts Parts that share an instrument on one channel,
   and then one voice's note-off cuts another's identical pitch short. Use
   `midiio.write_midi(score, path, channels=[...])`.
2. **Percussion off channel 10** plays as a piano.
3. **`Dynamic` silently rescales your velocities.** `velocity = 100` under a `Dynamic('pp')`
   renders at 50. Shape velocity by hand and keep Dynamics out of the Part. Hairpins do
   nothing at all.
4. **Notes below an instrument's real range** render as synthetic mush. A guitar stops at
   E2. `verify.range_check`.
5. **You cannot listen, so measure.** `references/15-verifying-without-listening.md`.

## Licence

MIT. music21 itself is BSD-3-Clause; the FluidR3 GM soundfont is MIT.
