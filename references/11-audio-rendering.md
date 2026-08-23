# 11 — Rendering a score to audio

music21 stops at the MIDI file. Everything between "I have a .mid" and "here is an mp3
someone would listen to" is this chapter: soundfonts, FluidSynth, stems, mixing, mastering,
and the specific ways each step silently ruins a piece.

Tools: `fluidsynth` (MIDI → wav), `ffmpeg` (mix, master, encode). Both are on Homebrew and
apt. `m21kit.render` wraps the whole thing; read this to understand what it is doing and
when to override it.

---

## Why not `score.show('midi')`

`show('midi')` opens a GUI player. `midi.realtime.StreamPlayer` needs pygame and a live
audio device. Neither works headless, neither produces a file, and neither is what you
want. The pipeline is always:

```
music21 Score  →  .mid (one per voice)  →  .wav (one per voice)  →  mix  →  master  →  .mp3
                   midiio.write_stems      fluidsynth              ffmpeg
```

---

## Soundfonts

FluidSynth synthesises nothing on its own; it plays samples from a SoundFont (`.sf2`). No
soundfont, no sound — and the choice of soundfont matters more to the result than most of
your compositional decisions.

| Soundfont | Size | Get it | Character |
|---|---|---|---|
| **FluidR3 GM** | ~141 MB | `https://github.com/urish/cinto/raw/master/media/FluidR3%20GM.sf2` (verified working) | The default answer. Full GM, decent nylon/steel guitar, usable strings, good drums. |
| GeneralUser GS | ~30 MB | `https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2` | Smaller, cleaner, arguably better piano. |
| VintageDreamsWaves | 1.5 MB | ships with Homebrew's fluid-synth | Toy. Useful only to prove the pipeline runs. |

```python
from m21kit import render
sf2 = render.ensure_soundfont()      # finds one, or downloads FluidR3 (~141MB)
```

`fluidsynth --version` and `ffmpeg -version` first; `render.have_tools()` does it for you.

A soundfont is a *sample library*, which means **every instrument has a real range** and
notes outside it are stretched garbage. A nylon guitar patch played at A1 does not sound
like a guitar; it sounds like a synthesiser pretending. See `verify.range_check`.

---

## FluidSynth

```bash
fluidsynth -ni -F out.wav -r 48000 -g 0.42 -R 1 -C 0 \
  -o synth.reverb.room-size=0.6 -o synth.reverb.damp=0.4 \
  -o synth.reverb.width=0.7   -o synth.reverb.level=0.55 \
  -o synth.polyphony=768 \
  soundfont.sf2 input.mid
```

| Flag | Why |
|---|---|
| `-ni` | no shell, no MIDI input — required for batch |
| `-F out.wav` | render to file instead of the audio device |
| `-g 0.42` | **synth gain. Keep it low.** Headroom is free before the mix; a clipped stem can never be repaired. |
| `-R 1` / `-C 0` | reverb on, chorus off. Chorus flatters nothing and smears everything. |
| `-o synth.reverb.*` | the only reverb you get. Room 0.5–0.65 for a band, 0.8+ for a cathedral. |
| `-o synth.polyphony=768` | default is 256. A dense arrangement with rolls and tremolo will exceed it and **silently drop notes**. |

Reverb parameters are `-o` options. The long forms (`--reverb-damp` etc.) do **not** exist
and fluidsynth exits with a bare `Unknown option` and no clue which one.

---

## Stems, and why a flat render always fails

Render every part in one pass and you have exactly one lever — MIDI velocity — for
balance. Velocity is not level. A six-note rasgueado at velocity 80 is far louder than a
single melody note at velocity 110, because **loudness follows note density**, and no
velocity you can write will fix it.

So render one wav per voice and balance in dB:

```python
from m21kit import render
render.score_to_mp3(score, 'out.mp3',
    stems=[render.Stem('melody', gain_db=+4, eq=[(2600, 1.2, 3.0)]),
           render.Stem('chords', gain_db=-3, pan=-0.15),
           render.Stem('bass',   gain_db=+1, hp=55, eq=[(108, 1.0, 2.0)]),
           render.Stem('drums',  gain_db=-6, pan=+0.22)],
    channels=[1, 2, 3, 10])
```

Starting levels that usually work:

| Voice | gain_db | notes |
|---|---|---|
| lead / melody | +3 … +5 | plus a 2.5–3 kHz bell, which is what makes a line *read* over an accompaniment |
| strummed or arpeggiated chords | −2 … −5 | high note count, cut the 300–400 Hz mud |
| bass | 0 … +1 | high-pass at 50–60, small bump at ~110 |
| octave doubling / inner voices | −5 … −8 | it is glue, not a part |
| percussion | −4 … −10 | drums sound louder than they measure |

**Panning.** If the parts are one physical instrument, keep everything inside ±0.3 or it
stops sounding like one instrument in a room. Only spread wide for genuinely separate
players.

---

## Mastering

```
amix(normalize=0) → acompressor → loudnorm → afade
```

* `normalize=0` on `amix` is **mandatory**. The default divides by the number of inputs,
  so adding a stem quietly turns everything else down.
* `acompressor=threshold=-18dB:ratio=2.3:attack=14:release=240:makeup=2` — gentle glue.
  Higher ratios flatten the dynamic arc you spent the whole piece building.
* `loudnorm=I=-14:TP=-1.2:LRA=11` — streaming-normal.

**`LRA` is a target loudnorm compresses toward, not a ceiling and not a report.** Ask for
less range than the music has and it takes the difference out of your arc — quietly, and
downstream of the compressor, so every stem still measures correctly. Measured on a track
whose sections naturally span 11 dB:

| requested `lra` | resulting section range | loudest section |
|---|---|---|
| 9 | 4.5 dB | a four-bar *build* |
| 14 | 7.1 dB | first chorus |
| 20 | 8.7 dB | **final chorus** — correct |

The symptom is maddening from the inside: every stem measures louder in the climax than in
the first chorus, and the mixed section still comes out quieter. Diagnose it by mixing the
stems with gain/pan/EQ only — no compressor, no loudnorm — and measuring the sections
there. If the arc is right pre-master, it is not the arrangement's problem. **Ask for more
range than the music has** and loudnorm leaves it alone.

  For quiet, dynamic, or free-rhythm music use `I=-16:LRA=14`, or the normaliser squashes
  the contrast between a whispered opening and a climax.
* `afade=t=out:st=<end-4.5>:d=4.5` — compute the start from the *actual rendered duration*,
  which is longer than the score's `highestTime` because of the reverb tail. Hard-code it
  and the fade simply never happens.

---

## Audio-side gotchas

- **Clipping shows as `max_volume: 0.0 dB`.** Check every render:
  `verify.audio_stats(path)` reports `peak_dbfs` and `clipped`. Fix at the synth gain, not
  with a limiter.
- **The rendered file is longer than the score.** Reverb tails and the last note's decay
  add 3–8 s. Any timing computed from the score must account for it.
- **Stems have different lengths.** A part that stops early produces a shorter wav.
  `amix=duration=longest` handles it; do not assume they align by length.
- **`-g` too high is the number one cause of a bad-sounding render.** Distortion from a
  clipped stem survives everything downstream.
- **Polyphony limit.** Dense rolls will exceed 256 voices and drop notes with no warning
  and no error. Set `synth.polyphony=768`.
- **Percussion silently plays as a piano** if the part is not on channel 10. See
  `06-midi-deep.md`; pass `channels=[..., 10]`.
- **`loudnorm`'s `LRA` compresses toward its target.** It is not a report and not a ceiling:
  request 9 on material that spans 11 and it flattens the difference out of your dynamic
  arc, downstream of the compressor, where every stem still measures correctly. Request
  more range than the music has. Diagnose with a gain/EQ-only mix.

---

## Checking the result

You cannot listen. So measure — see `15-verifying-without-listening.md`:

```python
from m21kit import verify
verify.audio_stats('out.mp3')          # clipping, LUFS, true peak
verify.pulse('out.mp3')                # is there a beat, and at what tempo
verify.section_levels('out.mp3', [('intro',0,15), ('climax',95,120)])
verify.harmony_match('out.mp3', [(0, 2.4, 'Dm'), (2.4, 4.8, 'A7')])
```

`section_levels` marks `is_peak`. If your climax is not it, the mix is wrong however good
the notes are.
