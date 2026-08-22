# The MIDI Layer: How Your Music Becomes Audible

MIDI is the only path from a music21 Stream to sound, and where correct-looking scores turn into
wrong-sounding audio. This chapter documents `music21/midi/` exhaustively: channel allocation
(which silently truncates notes), channel-10 percussion, the conductor track, the velocity
pipeline, program changes, tick quantization, and round-trip loss. Citations are git HEAD
(v11.0.0b8, `midi/base.py` + `midi/translate.py`); **every example was executed on music21
10.5.0** (line numbers differ by ≤6), audio claims rendered with fluidsynth + FluidR3_GM.sf2.

## Module map

| File | Role |
|---|---|
| `midi/__init__.py` | Re-export shim (90 lines). Code moved to `base.py` in 2025; `midi.MidiFile` etc. still resolve. |
| `midi/base.py` | Byte layer: `MidiFile`, `MidiTrack`, `MidiEvent`, `DeltaTime`, the four message enums, varlen encoding. Knows nothing about Streams. |
| `midi/translate.py` | Stream ⟷ MidiFile. 3068 lines. Everything that can go wrong lives here. |
| `midi/percussion.py` | `PercussionMapper` (GM key ↔ `instrument` class), `MIDIPercussionException`. 221 lines, no channel logic. |
| `midi/realtime.py` | `StreamPlayer` via pygame. **Unavailable here**: `StreamPlayerException: StreamPlayer requires pygame. Install first`. Render offline. |

`midi.ChannelVoiceMessages` (`base.py:364`): `NOTE_OFF NOTE_ON POLYPHONIC_KEY_PRESSURE
CONTROLLER_CHANGE PROGRAM_CHANGE CHANNEL_KEY_PRESSURE PITCH_BEND`. `midi.MetaEvents`
(`base.py:389`): `SEQUENCE_TRACK_NAME INSTRUMENT_NAME LYRIC END_OF_TRACK SET_TEMPO
TIME_SIGNATURE KEY_SIGNATURE UNKNOWN`. Also `ChannelModeMessages`, `SysExEvents`.

**Channel indexing is inconsistent and this bites constantly.** `MidiEvent.channel` is
**1-indexed** (1–16); `instrument.Instrument.midiChannel` is **0-indexed** (0–15). GM drums are
"channel 10" = `MidiEvent.channel == 10` = `Instrument.midiChannel == 9`; the conversion is at
`translate.py:2470`. Warned about at `base.py:465-470` and `translate.py:2424-2428`.

## 1. Channel allocation — music21 folds Parts onto shared channels

**music21 assigns MIDI channels by MIDI *program number*, not by Part.** Two Parts with the same
instrument get the *same* channel. This is not a bug report; it is the documented design of
`channelInstrumentData` (`translate.py:2395`), whose return value is
`channelByInstrument: dict[midiProgram, channel]` — the key is the program, so a program can only
ever map to one channel.

The pipeline (`streamHierarchyToMidiTracks`, `translate.py:2651`):

1. `prepareStreamForMidi` (`:2267`) — deepcopy, expand repeats, build the conductor Part,
   realize volumes.
2. `channelInstrumentData` (`:2395`) — build `{midiProgram: channel}`. Channels default to
   `range(1,10) + range(11,17)` (`:2435`) — **15 channels, 10 excluded**.
3. `packetStorageFromSubstreamList` (`:2518`) — flatten each Part into "packets"
   (trackId / offset-in-ticks / MidiEvent / source object / duration).
4. `updatePacketStorageWithChannelInfo` (`:2620`) — stamp `initChannel` per packet:
   `UnpitchedPercussion → 10`, `Conductor → None`, else `channelByInstrument[inst.midiProgram]`.
5. `assignPacketsToChannels` (`:1501`) — only *microtonal* notes move channel; everything else
   keeps `initChannel` unconditionally (`:1574`).

Step 5 is the crux: **nothing in the pipeline separates two same-program Parts.**

### Experiment: proving the fold

```python
def build(factories, pitches):          # one Part per factory, one note each
    sc = stream.Score()
    for fac, pi in zip(factories, pitches):
        p = stream.Part(); p.insert(0, fac()); p.insert(0, note.Note(pi)); sc.insert(0, p)
    return sc

for label, sc in [
    ('Flute+Oboe',    build([instrument.Flute, instrument.Oboe], ['C5', 'E4'])),
    ('Violin+Violin', build([instrument.Violin, instrument.Violin], ['C5', 'E4'])),
    ('4x Piano',      build([instrument.Piano] * 4, ['C4', 'E4', 'G4', 'B4'])),
]:
    print(label, [t.getChannels() for t in midi.translate.streamToMidiFile(sc).tracks])
```

```
Flute+Oboe    [[], [1], [2]]
Violin+Violin [[], [1], [1]]     <-- FOLDED
4x Piano      [[], [1], [1], [1], [1]]   <-- ALL FOUR FOLDED
```

Two Parts with **no** instrument fold too (both key on `midiProgram is None` → channel 1).
Setting `inst.midiChannel` per Part does **not** help — the second Violin's `midiProgram` is
already in `channelByInstrument`, so the guard at `translate.py:2467` skips it (verified: still
`[[], [1], [1]]`). Nor does `acceptableChannelList=[3,5,7,9]`: three Violins all land on `[3]`.

### Experiment: the fold truncates notes

Part A (Violin) holds C4 for 4 beats from offset 0; Part B (also Violin) plays the same C4 for
1 beat from offset 1. Tempo 60, so 1 quarter = 1 second. Absolute events in the written file:

```
   tick    ql trk ch pitch kind vel
      0  0.00   1  1    60 ON   90
  10080  1.00   2  1    60 ON   90
  20160  2.00   2  1    60 OFF  0     <-- Part B's note-off
  40320  4.00   1  1    60 OFF  0     <-- Part A's note-off, arrives too late
```

A synth tracks one voice per `(channel, pitch)`. Part B's OFF at ql 2.0 kills Part A's still-held
C4; Part A's OFF at 4.0 hits nothing. **Rendered and measured with fluidsynth** (RMS envelope,
0.1 s bins, reverb/chorus off):

```
FOLDED   (Violin + Violin)  peak RMS 0.0178   audible 0.0s -> 2.0s   <-- 2 seconds lost
UNFOLDED (Violin + Viola)   peak RMS 0.0236   audible 0.0s -> 4.0s
```

The music is objectively wrong and nothing in music21 warns.

### The fix: `retrack()`

Post-process `MidiFile.tracks` before writing — full source in **Reusable helpers**. It walks
tracks, skips note-less ones (`hasNotes()`, `base.py:1583`), pins percussion to 10, and hands
every other track the next channel from the pool. `MidiTrack.setChannel` (`base.py:1602`) looks
like the tool for this but rewrites `.channel` on *every* event including DeltaTimes; `retrack`
filters on `isChannelEvent()` (`base.py:628`), so only real channel messages move and the
PROGRAM_CHANGE travels with its notes.

```python
mf = midi.translate.streamToMidiFile(score)
retrack(mf, verbose=True)
mf.open('out.mid', 'wb'); mf.write(); mf.close()
```

Tested on the collision case:

```
before: [[], [1], [1]]
  track 1: [1] -> [1]
  track 2: [1] -> [2]
after : [[], [1], [2]]
programs preserved: [[], [40], [40]]
RETRACKED: peak RMS 0.0334   audible 0.0s -> 4.0s      <-- full 4 seconds
```

The PROGRAM_CHANGE moves with the notes, so both parts still sound like violins.

### Channel exhaustion

With 20 distinct programs (`translate.py:2499-2508`), 14 get real channels; the rest collapse onto
`acceptableChannels[0]`:

```
[[], [1], [2], [3], [4], [5], [6], [7], [8], [9], [11], [12], [13], [14], [15],
 [1], [1], [1], [1], [1], [1]]
```

Only 14, not 15: `if i < len(acceptableChannels) - 1` deliberately reserves one dynamic channel
(here 16) for microtonal spill. **A 15+ part score cannot be correct in one MIDI file.** Split
into multiple files, or accept that some parts share.

## 2. Percussion and channel 10

`instrument.UnpitchedPercussion.__init__` sets `self.midiChannel = 9` (0-indexed → channel 10);
`updatePacketStorageWithChannelInfo` hardcodes `initCh = 10` for any `UnpitchedPercussion`
(`translate.py:2638`). `elementToMidiEventList` also passes `channel=10` for `note.Unpitched` and
`percussion.PercussionChord` (`translate.py:1396, 1401`). Four routes, all measured:

| Route | Construction | Channel | Rendered |
|---|---|---|---|
| A | `note.Unpitched(storedInstrument=instrument.SnareDrum())` | **10** | drums ✓ |
| B | `percussion.PercussionChord([Unpitched(...), Unpitched(...)])` | **10** | drums ✓ |
| C | plain `note.Note(midi=36)`, no percussion instrument | 1 | **piano** ✗ |
| D | plain Notes + `retrack(mf, percussionTracks=[1])` | **10** | drums ✓ |
| E | plain Notes + `part.insert(0, instrument.UnpitchedPercussion())` | **10** | drums ✓ |

Envelopes confirm it: A/B/D/E give sharp transients dying by 1.5 s, C gives sustained pitched
tones out to 1.8 s. **Route C is the failure mode an agent falls into by default.**

**The supported route (A/B).** `_get_unpitched_pitch_value` (`translate.py:828`) reads
`storedInstrument.percMapPitch`, falls back to the enclosing `UnpitchedPercussion` context, and
**returns 60 if nothing is found** — a silent wrong note. Default modifiers surprise:

```
BassDrum      modifier='acoustic'   percMapPitch=35   (not 36!)
SnareDrum     modifier='acoustic'   percMapPitch=38
HiHatCymbal   modifier='pedal'      percMapPitch=44   (not 42!)
TomTom        modifier='low floor'  percMapPitch=41
CrashCymbals  modifier='1'          percMapPitch=49
Cowbell/Tambourine/Maracas/Vibraslap/Agogo: 56 / 54 / 70 / 58 / 67
```

Set `.modifier` to steer: `HiHatCymbal().modifier = 'closed'` → 42, `'open'` → 46;
`BassDrum().modifier = '1'` → 36; `SnareDrum` accepts `acoustic/side/electric` → 38/37/40;
`TomTom` accepts `low floor/high floor/low/low-mid/high-mid/high` → 41/43/45/47/48/50.
`PercussionMapper` (`percussion.py:25`) maps in both directions but its table is **incomplete** —
GM keys 39 (hand clap), 51/52/53 (rides), 55, 69, 73–75, 78–79 have no music21 class:

```python
midi.percussion.PercussionMapper().midiPitchToInstrument(39)
# MIDIPercussionException: 39 does not map to a valid instrument!
```

**Route E is what you want for real drum programming**: ordinary `Note`s at GM key numbers on a
Part tagged with a bare `UnpitchedPercussion()`. All 47 GM keys (including those
`PercussionMapper` cannot express), per-hit velocity, micro-timed offsets — and music21 still gives
the track channel 10 to itself; `drumPart()` below wraps it. **Never mix drums and pitched notes
in one Part**: the whole Part gets one `initChannel`.

## 3. Tempo, the conductor track, and wall-clock time

`prepareStreamForMidi` calls `conductorStream` (`translate.py:2325`), which **strips every
`MetronomeMark`, `TimeSignature` and `KeySignature` out of all Parts** into a new Part carrying
`Conductor()`, priority `min(partPriority) - 1` so it sorts first. That becomes track 0 — always
exported (v6.5+), always channel `None`. Missing marks are defaulted to
`MetronomeMark(120)` / `TimeSignature('4/4')` (`:2387-2390`). `tempoToMidiEvents` (`:1229`) emits
`SET_TEMPO` as 3 bytes of `int(round(60_000_000 / mm.getQuarterBPM()))` µs-per-quarter.

Measured (`(track, tick, ql, bpm)`):

| Score | SET_TEMPO events |
|---|---|
| no MetronomeMark anywhere | `[(0, 0, 0.0, 120.0)]` |
| MM=72 in part 1 only | `[(0, 0, 0.0, 72.0)]` |
| MM=72 in **both** parts @0 | `[(0, 0, 0.0, 72.0)]` — deduped, good |
| 60 @0 and 180 @4, one part | `[(0, 0, 0.0, 60.0), (0, 40320, 4.0, 180.0)]` |
| `MetronomeMark(number=None, text='Andante')` | `[(0, 0, 0.0, 72.0)]` — text implies a number |
| `MetronomeMark(number=100, referent=half)` | `[(0, 0, 0.0, 200.0)]` — converted to quarter BPM |

**Marks do NOT need to be in every part — put them in exactly one.** Duplicating across parts is
harmless *only* if every part carries the same marks at the same offsets.

### The dropped-tempo trap

`conductorStream` dedupes with one running `lastOffset` (`translate.py:2376-2382`):
`if offset_in_s > lastOffset: conductorPart.insert(...)` — then `lastOffset = offset_in_s`
unconditionally. But `s[klass]` yields in **hierarchy order (part by part)**, not global offset
order, so a mark in a later Part at an earlier offset is **silently discarded**:

```
p1: MM 60 @0, MM 200 @8      p2: MM 120 @4
  -> [(0, 0.0, 60.0), (0, 8.0, 200.0)]      120 @4 GONE
same three marks all in p1
  -> [(0, 0.0, 60.0), (0, 4.0, 120.0), (0, 8.0, 200.0)]   correct
```

Fix: `consolidateTempi(score)` (helpers below) moves every mark into the first Part in offset
order before export — verified to restore the missing 120 @4.

### Wall-clock seconds under a tempo map

`tempoMap(mf)` / `secondsAtOffset(marks, ql)` / `offsetAtSeconds(marks, s)` are in **Reusable
helpers**. `tempoMap` reads the map back **from the MidiFile**, not the Stream, so you see what
actually got written — and it prepends the MIDI default of 120 bpm when nothing sits at offset 0.

**Verified against rendered audio.** Xylophone, 12 quarter notes, tempo 60 @0 → 240 @4, onsets
detected from the wav by envelope rise:

```
predicted [0.0, 1.0, 2.0, 3.0, 4.0, 4.25, 4.5, 4.75, 5.0, 5.25, 5.5, 5.75]
measured  [0.002, 1.004, 2.006, 3.008, 4.012, 4.264, 4.514, 4.764, 5.014, 5.264, 5.516, 5.766]
max error 0.016 s  (sample attack + detector hop)
```

## 4. Velocity: the exact path

`noteToMidiEvents` (`translate.py:552`) is one line:

`me1.velocity = int(round(n.volume.cachedRealized * 127))`. `cachedRealized` is filled by
`volume.realizeVolume(part)` from `prepareStreamForMidi` (`:2311`), which calls
`Volume.getRealized(useDynamicContext, useVelocity, useArticulations)` (`volume.py:165`). That
computes, in order:

1. `val = baseLevel = 0.5`.
2. If `_velocityScalar is None`: `val += 0.20866` → **0.70866 → velocity 90**. This is the
   default for every note you never touch.
3. Else if `velocityIsRelative` (the default): `val = 0.5 * (velocityScalar * 2.0)` = the scalar
   exactly → `round(v/127*127) == v`. **Velocity round-trips exactly.**
4. Else (`velocityIsRelative = False`): `val = velocityScalar`, and steps 5–6 are skipped.
5. Dynamic in context: `val *= dynamic.volumeScalar * 2.0`.
6. Each articulation: `val += articulation.volumeShift`.
7. Clip to [0, 1], cache, `* 127`, round.

Measured velocities:

```
nothing set                                    -> 90
volume.velocity = 1,16,32,64,90,100,126,127    -> 1,16,32,64,90,100,126,127   (exact)
volume.velocityScalar = .25,.5,.75,1           -> 32, 64, 95, 127
Dynamic ppp pp p mp mf f ff fff (vel unset)    -> 27, 45, 63, 81, 99, 126, 127, 127
Dynamic ff + velocity 40, relative              -> 68
Dynamic ff + velocity 40, velocityIsRelative=False -> 40
articulations none/accent/strongAccent/staccato/tenuto -> 90, 103, 109, 96, 84
chord whole-chord velocity 100                 -> 100, 100, 100
chord per-note volumes 30/70/110               -> 30, 70, 110   (setVolumes works)
```

Constants: `volumeScalar` ppp .15 / pp .25 / p .35 / mp .45 / mf .55 / f .70 / ff .85 / fff .90;
`volumeShift` Accent +.10, StrongAccent +.15, Staccato +.05, Staccatissimo +.05, Tenuto −.05.

**`ff` and `fff` both clip to 127** (0.70866 × 1.7 = 1.20 > 1) — set velocities directly rather
than layering dynamics on unset notes if you want usable range. And **`volume.velocity = 0` is a
trap**: it emits `NOTE_ON` velocity 0, which every synth reads as a note-off, and
`MidiEvent.isNoteOn()` returns False for it (`base.py:1094`), so music21 loses the note on
re-import too. Floor at 1.

## 5. Program changes

`instrumentToMidiEvents` (`translate.py:844`) emits one `PROGRAM_CHANGE` whose `.data` is
`inst.midiProgram`, **or 0 if `midiProgram is None`** (`:868`). `Conductor` returns no events.

| Score | Emitted |
|---|---|
| no Instrument object | `TRACK_NAME b''`, **no PROGRAM_CHANGE** (synth default = piano) |
| `Trumpet()` @0 | `TRACK_NAME b'Trumpet'`, **PROGRAM 56 twice** at tick 0 |
| `Trumpet()` @1.0 only | PROGRAM 56 @0 *and* @1.0 (start events still name it) |
| Flute @0, Trumpet @2 | PROGRAM 73 @0 ×2, PROGRAM 56 @2.0, same channel |
| bare `Instrument()`, `midiProgram=88` | PROGRAM 88 |
| bare `Instrument()`, `midiProgram=None` | **PROGRAM 0** (silently becomes piano) |

The duplicate at offset 0 is intentional (`translate.py:243-246`): one from `getStartEvents`,
one from the Instrument in the flattened stream. Harmless.

**Mid-part instrument changes work** — insert another Instrument at the offset. But the program
change lands on the Part's *channel*, so if that channel is shared it stomps the other Part.
Proven by spectral centroid of a *Flute* note in Part 1 at t=3 s while Part 2 (also Flute, same
channel) inserts a Trumpet at ql 2 and plays nothing after:

```
no change      channels [[], [1], [1]]  centroid 1239 Hz
Trumpet stomp  channels [[], [1], [1]]  centroid 2115 Hz   <-- Part 1 turned into a trumpet
retracked      channels [[], [1], [2]]  centroid 1239 Hz   <-- fixed
```

`instrument.instrumentFromMidiProgram(n)` covers all 128 GM programs
(`instrument.MIDI_PROGRAM_TO_INSTRUMENT`, `instrument.py:1933`) but onto only **63 distinct
classes** — 88–127 nearly all collapse to `Sampler`, 0/1/3 to `Piano`, so
`Instrument → program → Instrument` is lossy above 87. There is **no
`instrument.deducePartName`** in v10/v11; use `Instrument.bestName()` and
`instrument.deduplicate(stream)`.

## 6. Ticks, rounding, and the finest usable offset

`defaults.ticksPerQuarter = 10080` (= 2⁵·3²·5·7), `defaults.ticksAtStart = 10080`,
`defaults.limitOffsetDenominator = 65535`. 10080 divides evenly by 2–10, 12, 14, 16, … so triplets, quintuplets and septuplets are all
exact. `offsetToMidiTicks` (`translate.py:100`) is `int(round(o * 10080))` — Python's **banker's
rounding**, so exactly 0.5 ticks rounds *down* to even.

```
offset            ticks     back to ql
1/3           ->   3360     0.33333333   exact
1/7           ->   1440     0.14285714   exact
0.1           ->   1008     0.10000000   exact
0.01          ->    101     0.01001984   +0.2 tick (0.0099 ms @120bpm)
0.001         ->     10     0.00099206
1/10080       ->      1     0.00009921   <-- one tick
1/20160       ->      0     0.0          <-- half a tick VANISHES
```

**Smallest reliably distinct offset: 1/10080 ql = 0.0496 ms at 120 bpm.** Anything finer
collides with the previous event. Verified end to end — notes inserted at
`[0, 1/10080, 2/10080, 0.001, 0.01, 0.02, 0.05, 0.1]` came back from the written file at ticks
`[0, 1, 2, 10, 101, 202, 504, 1008]`. So micro-timing is effortless: a 12 ms strum at 120 bpm
(0.024 ql per string) lands at ticks/ms `[(0, 0.00), (242, 12.00), (484, 24.01), (726, 36.01),
(968, 48.02), (1210, 60.02)]` — under 0.02 ms of error across the whole gesture.

Store offsets through `opFrac` (`from music21.common.numberTools import opFrac`) so music21 keeps
them as exact `Fraction`s: `opFrac(0.01) → Fraction(1,100)`, `opFrac(1/3) → Fraction(1,3)`.

`streamToMidiFile` sets `mf.ticksPerQuarterNote = defaults.ticksPerQuarter` (`translate.py:2844`)
**after** all delta times were computed at 10080. **Never assign a different value afterwards** —
480 leaves the deltas at 10080 and playback runs 21× slow. For a different resolution, build the
MidiFile by hand (§10).

## 7. Round trip: what survives `midiFileToStream`

Source Part: Clarinet, MM 96, 3/4, `KeySignature(-3)`, `Dynamic('pp')`, a C#4/D-4/E4 triplet, a
C-minor chord, a rest, notes at 4.0 and 4.13. Written with `.write('midi')`, read back with
`converter.parse`.

```
 original                                     after round trip
 0.0   Note  1/3      C#4  lyric='la'         0.0   Note  1/3   C#4  lyric='la'  vel=58
 1/3   Note  1/3      D-4                     1/3   Note  1/3   C#4              vel=45
 2/3   Note  1/3      E4                      2/3   Note  1/3   E4               vel=45
 1.0   Chord 2.0      C-minor triad           1.0   Chord 2.0   C-minor triad    vel=45
 3.0   Rest  1.0                              3.0   Rest  1.0
 4.0   Note  13/100   C4                      4.0   Note  0.25  C4               vel=45
 4.13  Note  187/100  G4                      4.25  Note  1.75  G4               vel=45
```

| Survives | Lost |
|---|---|
| pitch (as MIDI key), rhythm, chords | enharmonic spelling — **D-4 came back as C#4** |
| lyrics (`MetaEvents.LYRIC`) | dynamics — baked into velocity, `Dynamic` objects gone |
| time signature, key signature (as a `Key`) | articulations — baked into velocity |
| tempo / all SET_TEMPO marks | slurs, ties (re-derived by `makeTies`), beams, metadata |
| instrument (via program + track name) | exact offsets, unless you disable quantization |
| velocity (per note) | voice identity (voices are flattened on export) |

Rests are **not** stored — regenerated by `makeRests(fillGaps=True)` (`translate.py:2263`);
Measures are made on import since v7 (`makeMeasures`, `:2256`).

### Quantization on import

`midiTrackToStream` quantizes with `defaults.quantizationQuarterLengthDivisors == (4, 3)` —
16ths and triplet-8ths (`translate.py:2161-2162`, `:2228`). Same file, three ways:

```
default                          offsets [0.0, 1/3, 2/3, 1.0, 4.0, 4.25]
quantizePost=False               offsets [0.0, 0.3333333333, 0.6666666667, 1.0, 4.0, 4.129960]
quarterLengthDivisors=(8,)       offsets [0.0, 0.375, 0.625, 1.0, 4.0, 4.125]
```

Both keywords ride through `converter.parse(fp, quantizePost=False)` /
`converter.parse(fp, quarterLengthDivisors=(4,3,5,7))` — `ConverterMidi.parseFile` forwards
`**keywords` (`subConverters.py:1034`). The same divisor also sets the **chord grouping
tolerance**, `chunkTolerance = ticksPerQuarter / max(divisors)` (`:2170`): notes starting within
that window merge into a Chord (fallback a 64th when unquantized), so **a micro-timed strum
re-imports as a single chord** unless you raise the divisors.

## 8. `streamToMidiFile` directly vs `.write('midi')` — they are identical

`ConverterMidi.write` (`subConverters.py:1063`) is four lines: `music21ObjectToMidiFile(obj)` →
`mf.open(fp,'wb')` → `mf.write()` → `mf.close()`, and `music21ObjectToMidiFile`
(`translate.py:300`) calls `toSoundingPitch()` if needed then `streamToMidiFile`.
**`.write('midi')` does NOT call `makeNotation`** — unlike MusicXML there is no
`makeNotation=False` escape hatch, because there is nothing to escape. Verified byte-for-byte on
a Part with unnotatable offsets (0.13, 0.37, 1.07, 2.5333):

```
.write("midi") sha256[:16]  77b4e2280b23acc8
streamToMidiFile            77b4e2280b23acc8
identical bytes: True
note-on ticks   [0, 1310, 3730, 10080, 10786, 25200, 25536]
exact ql        [0.0, 0.12996, 0.37004, 1.0, 1.07004, 2.5, 2.533333]
offsets asked   [0.0, 0.13,    0.37,    1.0, 1.07,    2.5, 2.5333]
```

Precise offsets survive to tick precision, and Measures are **not** added to the source
(`before write: measures? False` / `after write: measures? False`) — `prepareStreamForMidi`
deep-copies.

What both paths *do* do, via `prepareStreamForMidi` (so switching does not avoid them): sort the
stream (`stream/base.py:410`); **`expandRepeats()` whenever Measures are present**
(`translate.py:2298` — `|: C :| D` exports as `[60, 60, 62]`; without Measures repeats are
ignored); `stripTies(matchByPitch=True)` per Part (`:2707`); `realizeVolume` per Part (`:2311`,
which fills `cachedRealized`); and conductor extraction, which strips all MM/TS/KS from the Parts
of the copy.

**Use `streamToMidiFile` directly** whenever you need to touch the events before they hit disk —
per §1, essentially always:

```python
mf = midi.translate.streamToMidiFile(score)   # or with acceptableChannelList=[...]
retrack(mf)                                    # or any other event surgery
mf.open(str(fp), 'wb'); mf.write(); mf.close()
```

Keywords: `addStartDelay=False` (prepend `ticksAtStart` before the first note), `addEndDelay=True`
(trailing quarter-rest before `END_OF_TRACK`, v10.3+), `acceptableChannelList=None`,
`encoding='utf-8'`.

## 9. Overlapping identical pitches inside one Part

Same failure as §1, same cause, and **voices do not help** — `packetStorageFromSubstreamList`
calls `subs.flatten()` (`translate.py:2594`), so Voices collapse into the Part's single channel.

| Case | Events | Result |
|---|---|---|
| C4 (0→4) + C4 (1→2) in one Part | ON 0, ON 1, OFF 2, OFF 4 | first note cut at 2.0, orphan OFF at 4.0 |
| same two notes in two `stream.Voice`s | identical | identical — no help |
| `Chord(['C4','C4','E4'])` | ON 60, ON 60, ON 64, OFF 60, OFF 60, OFF 64 | duplicate 60 is wasted |
| C4 (0→4) + **B#3** (1→2) | identical to case 1 | enharmonics collide — MIDI has no spelling |

Three fixes, best first: **(1) don't write it** — same pitch, same timbre, overlapping is one
note, so merge them; **(2) `trimOverlaps(part)`**, which shortens the earlier note to end just
before the later one starts (tested: `C4 ql 4.0` → `0.984375` = 63/64, file then verifies clean);
**(3) split into two Parts + `retrack`**, correct but costs a channel and a track, and only right
if the lines are genuinely independent.

Microtones are the one case where music21 *does* allocate a second channel
(`assignPacketsToChannels`, `translate.py:1615-1644`): two simultaneous C4s, one with
`microtone = 50`, give `track 1 channels [1, 2]` plus three `PITCH_BEND` events. `retrack` refuses
such a track by default rather than merging incompatible bends.

## 10. Building a MidiFile by hand

Bypasses Streams entirely — for a non-default `ticksPerQuarterNote`, controller messages, or
anything music21 will not emit. **Every MidiEvent must be preceded by its own DeltaTime**:
`getTimeForEvents` (`translate.py:1837`) pairs them strictly and skips unpaired ones.

```python
from music21 import midi
from music21.midi import ChannelVoiceMessages as CVM, MetaEvents as ME

mf = midi.MidiFile(); mf.ticksPerQuarterNote = 480
trk = midi.MidiTrack(0); mf.tracks.append(trk)

def ev(track, dtTicks, e):                       # every event needs its own DeltaTime
    dt = midi.DeltaTime(track); dt.time = dtTicks
    track.events += [dt, e]

te = midi.MidiEvent(trk, type=ME.SET_TEMPO); te.data = midi.putNumber(500000, 3)  # 120 bpm
ev(trk, 0, te)
for p, dur in [(60, 480), (64, 480), (67, 960)]:
    on = midi.MidiEvent(trk, type=CVM.NOTE_ON, channel=1); on.pitch = p; on.velocity = 100
    off = midi.MidiEvent(trk, type=CVM.NOTE_OFF, channel=1); off.pitch = p; off.velocity = 0
    ev(trk, 0, on); ev(trk, dur, off)
eot = midi.MidiEvent(trk, type=ME.END_OF_TRACK); eot.data = b''
ev(trk, 0, eot)
mf.open('hand.mid', 'wb'); mf.write(); mf.close()   # 60 bytes, renders correctly
```

Byte layer: `mf.format` is 1 on write (`base.py:1714`), reading accepts 0 and 1 only;
`writeMThdStr` (`:1835`) rejects a `ticksPerQuarterNote` with bit 0x8000 set; `mf.writestr()` /
`mf.readstr(b)` / `mf.openFileLike(BytesIO())` work in memory; `putNumber` / `getNumber` /
`putVariableLengthNumber` are the varlen primitives; `MidiTrack.updateEvents()` back-links events.

## Reusable helpers

Tested as a unit on music21 10.5.0; extracted verbatim from this file and re-run against the
integration test below.

```python
"""m21midi_helpers.py -- MIDI helpers for music21 composition."""
from __future__ import annotations
from music21 import midi as m21midi
from music21 import instrument, note, stream, tempo
from music21.common.numberTools import opFrac

TPQ = 10080
PITCHED_CHANNELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]
DRUM_CHANNEL = 10

# ---- 1. channels -----------------------------------------------------------
def retrack(mf, percussionTracks=(), channels=None,
            allowMicrotoneCollapse=False, verbose=False):
    """One MIDI channel per note-bearing track, in place. Returns {track: channel}."""
    pool = list(channels) if channels is not None else list(PITCHED_CHANNELS)
    percussionTracks = set(percussionTracks)
    assigned, nxt = {}, 0
    for i, trk in enumerate(mf.tracks):
        if not trk.hasNotes():
            continue
        used = trk.getChannels()
        if i in percussionTracks or used == [DRUM_CHANNEL]:
            ch = DRUM_CHANNEL
        else:
            if len(used) > 1 and not allowMicrotoneCollapse:
                raise ValueError(f'track {i} uses channels {used} (microtonal pitch-bend '
                                 'spill); pass allowMicrotoneCollapse=True to flatten')
            ch = pool[nxt % len(pool)]
            nxt += 1
        for e in trk.events:
            if e.isChannelEvent():
                e.channel = ch
        assigned[i] = ch
        if verbose:
            print(f'  track {i}: {used} -> [{ch}]')
    return assigned


def writeMidi(s, fp, *, perPartChannels=True, percussionParts=(), **kw):
    """streamToMidiFile + retrack + write. `percussionParts` indexes Parts, not tracks."""
    mf = m21midi.translate.streamToMidiFile(s, **kw)
    if perPartChannels:
        off = 1 if mf.tracks and not mf.tracks[0].hasNotes() else 0
        retrack(mf, percussionTracks=[p + off for p in percussionParts])
    mf.open(str(fp), 'wb'); mf.write(); mf.close()
    return mf

# ---- 2. percussion ---------------------------------------------------------
GM_DRUMS = {
    'kick': 36, 'kick2': 35, 'side': 37, 'snare': 38, 'clap': 39, 'esnare': 40,
    'tom_lf': 41, 'hh_closed': 42, 'tom_hf': 43, 'hh_pedal': 44, 'tom_low': 45,
    'hh_open': 46, 'tom_lmid': 47, 'tom_hmid': 48, 'crash': 49, 'tom_hi': 50,
    'ride': 51, 'china': 52, 'ride_bell': 53, 'tambourine': 54, 'splash': 55,
    'cowbell': 56, 'crash2': 57, 'vibraslap': 58, 'ride2': 59, 'bongo_hi': 60,
    'bongo_lo': 61, 'conga_mute': 62, 'conga_hi': 63, 'conga_lo': 64, 'timbale_hi': 65,
    'timbale_lo': 66, 'agogo_hi': 67, 'agogo_lo': 68, 'cabasa': 69, 'maracas': 70,
    'whistle': 71, 'whistle_lo': 72, 'guiro': 73, 'guiro_lo': 74, 'claves': 75,
    'wood_hi': 76, 'wood_lo': 77, 'cuica': 78, 'cuica_open': 79, 'tri_mute': 80,
    'tri_open': 81,
}

def drumPart(hits, partId='drums'):
    """hits: (offsetQL, drumNameOrKeyNumber, velocity[, quarterLength]). -> channel-10 Part."""
    p = stream.Part(id=partId)
    p.insert(0, instrument.UnpitchedPercussion())
    for hit in hits:
        off, name, vel = hit[0], hit[1], hit[2]
        ql = hit[3] if len(hit) > 3 else 0.25
        key = GM_DRUMS[name] if isinstance(name, str) else name
        n = note.Note(midi=key, quarterLength=ql)
        n.volume.velocity = vel
        p.insert(opFrac(off), n)
    return p

# ---- 3. tempo --------------------------------------------------------------
def tempoMap(mf):
    """[(quarterLengthOffset, quarterBPM), ...] read back from the written MidiFile."""
    tpq, marks = mf.ticksPerQuarterNote, []
    for trk in mf.tracks:
        tick = 0
        for e in trk.events:
            if e.isDeltaTime():
                tick += e.time
            elif e.type == m21midi.MetaEvents.SET_TEMPO:
                marks.append((tick / tpq, 60_000_000 / m21midi.getNumber(e.data, 3)[0]))
    marks.sort()
    if not marks or marks[0][0] > 0:
        marks.insert(0, (0.0, 120.0))
    return marks


def secondsAtOffset(marks, ql):
    secs, (prevOff, prevBpm) = 0.0, marks[0]
    for off, bpm in marks[1:]:
        if off >= ql:
            break
        secs += (off - prevOff) * 60.0 / prevBpm
        prevOff, prevBpm = off, bpm
    return secs + (ql - prevOff) * 60.0 / prevBpm


def offsetAtSeconds(marks, seconds):
    elapsed, (prevOff, prevBpm) = 0.0, marks[0]
    for off, bpm in marks[1:]:
        span = (off - prevOff) * 60.0 / prevBpm
        if elapsed + span >= seconds:
            return prevOff + (seconds - elapsed) * prevBpm / 60.0
        elapsed += span
        prevOff, prevBpm = off, bpm
    return prevOff + (seconds - elapsed) * prevBpm / 60.0


def consolidateTempi(score):
    """Move every MetronomeMark into the first Part in offset order, in place.

    Works around conductorStream()'s hierarchy-order lastOffset filter, which
    silently drops a mark that appears in a later Part at an earlier offset.
    """
    seen = {}
    for mm in score[tempo.MetronomeMark]:
        seen.setdefault(float(mm.getOffsetInHierarchy(score)), mm)
    for site in score.recurse(streamsOnly=True, includeSelf=True):
        site.removeByClass(tempo.MetronomeMark)
    target = score.parts.first() if score.parts else score
    for o, mm in sorted(seen.items()):
        target.insert(o, mm)
    return score

# ---- 9. overlaps -----------------------------------------------------------
def trimOverlaps(part, gapQL=1 / 64):
    """Shorten same-MIDI-key notes that overlap, in place. Returns count fixed."""
    flat = part.flatten()
    byKey = {}
    for n in flat.notes:
        o = float(flat.elementOffset(n))
        for p in n.pitches:
            byKey.setdefault(p.midi, []).append((o, n))
    fixed = 0
    for entries in byKey.values():
        entries.sort(key=lambda x: x[0])
        for (o1, n1), (o2, _) in zip(entries, entries[1:]):
            if o1 + float(n1.duration.quarterLength) > o2:
                newQL = opFrac(max(gapQL, o2 - o1 - gapQL))
                if newQL != n1.duration.quarterLength:
                    n1.duration.quarterLength = newQL
                    fixed += 1
    return fixed

# ---- verification ----------------------------------------------------------
def midiEventTable(fp_or_mf):
    """[(tick, trackIndex, channel, kind, a, b)]; kind in ON/ON0/OFF/PGM/TEMPO."""
    if isinstance(fp_or_mf, str):
        mf = m21midi.MidiFile(); mf.open(fp_or_mf); mf.read(); mf.close()
    else:
        mf = fp_or_mf
    rows = []
    for trk in mf.tracks:
        tick = 0
        for e in trk.events:
            if e.isDeltaTime():
                tick += e.time
                continue
            if e.type == m21midi.ChannelVoiceMessages.NOTE_ON and e.velocity == 0:
                rows.append((tick, trk.index, e.channel, 'ON0', e.pitch, 0))
            elif e.isNoteOn():
                rows.append((tick, trk.index, e.channel, 'ON', e.pitch, e.velocity))
            elif e.isNoteOff():
                rows.append((tick, trk.index, e.channel, 'OFF', e.pitch, 0))
            elif e.type == m21midi.ChannelVoiceMessages.PROGRAM_CHANGE:
                rows.append((tick, trk.index, e.channel, 'PGM', e.data, 0))
            elif e.type == m21midi.MetaEvents.SET_TEMPO:
                rows.append((tick, trk.index, 0, 'TEMPO',
                             round(60_000_000 / m21midi.getNumber(e.data, 3)[0], 3), 0))
    rows.sort(key=lambda r: (r[0], r[3] != 'TEMPO'))
    return rows, mf.ticksPerQuarterNote


def verifyMidi(fp_or_mf, verbose=True):
    """Static audit: stolen note-offs, retriggers, silent notes, program stomps.

    This is the substitute for listening. Run it on every file you write.
    """
    rows, tpq = midiEventTable(fp_or_mf)
    sounding = {}
    problems = {'retrigger': [], 'orphanOff': [], 'zeroVelocity': [],
                'stuckNote': [], 'sharedChannel': [], 'programStomp': []}
    chanOwners, chanProgram = {}, {}
    for tick, trk, ch, kind, a, b in rows:
        ql = round(tick / tpq, 4)
        if kind == 'ON0':
            problems['zeroVelocity'].append((ql, trk, ch, a))
        elif kind == 'ON':
            chanOwners.setdefault(ch, set()).add(trk)
            if (ch, a) in sounding:
                problems['retrigger'].append((ql, ch, a, sounding[(ch, a)][1]))
            sounding[(ch, a)] = (ql, trk)
        elif kind == 'OFF':
            if (ch, a) not in sounding:
                problems['orphanOff'].append((ql, trk, ch, a))
            else:
                _startQl, owner = sounding.pop((ch, a))
                if owner != trk:
                    problems['orphanOff'].append((ql, trk, ch, a))
        elif kind == 'PGM':
            if ch in chanProgram and chanProgram[ch][0] != a and chanProgram[ch][1] != trk:
                problems['programStomp'].append((ql, ch, chanProgram[ch], (a, trk)))
            chanProgram[ch] = (a, trk)
    problems['stuckNote'] = [(v[0], k[0], k[1]) for k, v in sounding.items()]
    problems['sharedChannel'] = [(ch, sorted(tr)) for ch, tr in chanOwners.items()
                                 if len(tr) > 1]
    if verbose:
        clean = True
        for name, items in problems.items():
            if items:
                clean = False
                print(f'  {name}: {len(items)}  e.g. {items[:3]}')
        if clean:
            print('  verifyMidi: clean')
    return problems
```

### Integration test (actually run)

Drums + bass + two identical electric guitars (the folding trap, 20 ms apart), written both ways:

```
WITH retrack     channels [[], [10], [1], [2], [3]]   verifyMidi: clean
                 tempoMap [(0.0, 96.0)] | bar 3 at 5.000 s | peak RMS 0.2084, 0.0 -> 5.0 s
WITHOUT retrack  channels [[], [10], [1], [2], [2]]   peak RMS 0.1779 (15% of energy lost)
                 retrigger: 12  e.g. [(0.02, 2, 57, 3), (0.02, 2, 60, 3), (0.02, 2, 64, 3)]
                 orphanOff: 24  e.g. [(1.8, 3, 2, 57), (1.8, 3, 2, 60), (1.8, 3, 2, 64)]
                 sharedChannel: 1  e.g. [(2, [3, 4])]
```

## Gotchas

1. **Two Parts with the same instrument share a MIDI channel and cut each other's notes short.**
   `channelByInstrument` is keyed by `midiProgram` (`translate.py:2395`). Neither
   `inst.midiChannel` nor `acceptableChannelList` fixes it. Parts with *no* instrument fold too
   (all key on `midiProgram is None` → channel 1). Always `retrack()`.
2. **Voices do not separate channels.** `packetStorageFromSubstreamList` flattens every Part
   (`:2594`), so two Voices collide exactly like two notes in one Voice.
3. **Enharmonics collide in MIDI.** C4 and B#3 are both key 60; overlapping them truncates.
4. **Beyond 14 distinct programs, every further Part is dumped on channel 1** (`:2506`). 15+ voice
   scores need multiple files.
5. **`Instrument.midiChannel` is 0-indexed; `MidiEvent.channel` is 1-indexed.** Drums are
   `midiChannel = 9` and `MidiEvent.channel = 10`.
6. **Plain `note.Note(midi=36)` on an untagged Part plays a piano, not a kick.** Tag the Part
   with `instrument.UnpitchedPercussion()` or force channel 10 post-hoc, and never mix drums and
   pitched notes in one Part — a Part gets a single `initChannel`.
7. **Percussion default modifiers are not the obvious drums**: `BassDrum` → key 35 (not 36),
   `HiHatCymbal` → 44 pedal (not 42 closed), `TomTom` → 41. Set `.modifier` explicitly.
8. **`_get_unpitched_pitch_value` returns 60 when it finds no `percMapPitch`** (`:840`) — a silent
   wrong note, not an exception. And `PercussionMapper` cannot express GM keys 39, 51–53, 55, 69,
   73–75, 78, 79 at all; use raw key numbers for those.
9. **A MetronomeMark in a later Part at an earlier offset is silently dropped** by
   `conductorStream`'s hierarchy-order `lastOffset` filter (`:2376`). Put all tempo marks in one
   Part, or call `consolidateTempi()`. That same function strips all MM/TS/KS out of every Part.
10. **Default velocity is 90**, from `0.5 + 0.20866` in `Volume.getRealized` — not 64, not 127.
11. **`Dynamic('ff')` and `Dynamic('fff')` both clip to velocity 127** on notes with no explicit
    velocity. Set velocities directly if you want real dynamic range.
12. **`volume.velocity = 0` emits a velocity-0 NOTE_ON**, which is a note-off. The note is
    inaudible *and* invisible to `isNoteOn()` on re-import. Floor at 1.
13. **An `Instrument` with `midiProgram = None` emits PROGRAM_CHANGE 0** (`:868`) — silently a
    piano. No instrument at all emits no program change, which is usually what you want.
14. **A mid-part instrument change stomps every Part sharing that channel** (measured: a flute
    note's spectral centroid jumped 1239 → 2115 Hz). `retrack()` before writing.
15. **`instrumentFromMidiProgram` maps 128 programs onto 63 classes** — programs 88+ nearly all
    become `Sampler`, so `Instrument → program → Instrument` is lossy. There is **no
    `instrument.deducePartName`** in v10/v11; use `Instrument.bestName()`.
16. **Half a tick (1/20160 ql) rounds to zero** and collides with the previous event. 1/10080 ql
    is the floor, and `int(round(...))` is banker's rounding.
17. **Never change `mf.ticksPerQuarterNote` after `streamToMidiFile`** — the deltas were already
    computed at 10080; setting 480 makes playback 21× slow.
18. **`.write('midi')` does not call `makeNotation`** and is byte-identical to `streamToMidiFile`.
    No offset mangling, and no `makeNotation=False` keyword either. But both paths run
    `expandRepeats()` whenever Measures are present, silently doubling repeated bars; without
    Measures, repeats are ignored entirely.
19. **Import quantizes to 16ths and triplet-8ths by default** (`quarterLengthDivisors=(4,3)`), and
    the same divisor sets the chord-grouping window — a micro-timed strum re-imports as one chord.
    Pass `quantizePost=False` to keep exact offsets.
20. **Round trip loses enharmonic spelling, dynamics, articulations, slurs, beams and metadata.**
    Never use MIDI as your working format — keep the Stream, or `converter.freeze` it.
21. **`midi/realtime.py` needs pygame**, which is absent here. Render with fluidsynth and measure
    the wav instead.
22. **Every `MidiEvent` you append by hand must be preceded by its own `DeltaTime`** or
    `getTimeForEvents` (`:1837`) will skip it on re-read.
23. **`MidiTrack.setChannel` rewrites `.channel` on every event, DeltaTimes included.** Filter on
    `isChannelEvent()` instead, as `retrack` does.
24. **Run `verifyMidi()` on every file you write.** It catches the exact class of error you cannot
    see in a score and cannot hear: stolen note-offs, retriggers, silent notes, program stomps.
