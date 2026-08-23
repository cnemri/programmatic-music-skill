# 13 — Idioms and grooves

Style is not a preset. It is a specific set of choices about mode, voicing, rhythmic cell,
articulation and form, and getting a genre right means getting those five things right
rather than picking a drum loop.

This chapter is a set of concrete recipes. Each gives the mode, the harmony, the groove,
the characteristic gesture, and the thing that most often gives away a fake.

---

## Flamenco

**Mode.** Phrygian dominant — `scales.pitches('flamenco', 'A4')` → A B♭ C♯ D E F G. The
two standard keys are ***por arriba*** (E Phrygian: cadence Am–G–F–E) and ***por medio***
(A Phrygian: cadence Dm–C–B♭–A). Por medio is the more idiomatic; the open A and D strings
do the work.

The Andalusian cadence is the entire harmonic language: **i–VII–VI–V**, descending, landing
on a *major* chord a semitone above the ♭II. It resolves to the V, not to the i — a
flamenco piece ends on E (por arriba) or A (por medio).

**Voicings** — real shapes, with the open strings ringing:
```python
Am   = [45, 52, 57, 60, 64]           # x02210
E7b9 = [40, 47, 52, 56, 59, 65]       # 0-2-2-1-0-1  ← the F on top is the sound
Dm   = [45, 50, 57, 62, 65]
A7   = [45, 52, 57, 61, 64, 70]       # with the B♭ ♭9 on top
```

**Compás.** `drums.GROOVES`: `tangos_flamencos` (4/4, beat 1 ghosted, 2-3-4 drive),
`rumba_flamenca` (3+3+2), `bulerias` and `solea` (12 beats, accented 12-3-6-8-10 — the
cycle *starts on 12*, so the "1" you feel is the second stroke), `sevillanas` (3/4).

**Gestures.** `perform.rasgueado` (the roll, alternating direction, crescendo into the
beat), *golpe* = `drums.GM['golpe']` (37) on 2 and 4, *palmas* in eighths accenting 2-3-4,
`perform.tremolo` for anything sustained, and fast `perform.run` picado in the mode.

**The giveaway.** Straight, evenly-accented strumming with no rasgueado, no golpe and no
palmas; and ending on the minor tonic instead of the Phrygian one.

**Free-rhythm forms.** *Granaína*, *taranta*, *malagueña* are **libre** — no compás at all.
The guitar answers the singer in the silences. Do not put a beat under them; `verify.pulse`
should read under 0.1.

---

## Jazz

**Harmony.** Think in ii–V–I and chord-scale pairs, not triads. Voice in **fourths and
rootless shells** — the bass has the root, so the piano plays 3rd/7th plus extensions:

```python
# Dm7-G7-Cmaj7 rootless left-hand voicings
Dm7  = [53, 60, 62, 65]      # F Bb? no: F C D A -> 3,7,9,5
G7   = [53, 59, 62, 65]      # F B D F#? use 3,7 + alterations
Cmaj7= [52, 59, 62, 64]
```
Scales: `bebop_dominant`, `altered` (over a V going to minor), `lydian_dominant` (over a
♭II substitution), `melodic_minor`.

**Groove.** `jazz_swing` (ride "ding, ding-a-ding", hats closing on 2 and 4), then
`perform.swing(score, ratio=0.6)`. Walking bass: quarter notes, chord tones on 1 and 3,
chromatic approach into the next root.

**The giveaway.** Straight eighths; a drum part that plays the kick on every beat; and
comping on the beat instead of between the beats.

---

## Orchestral / cinematic

**Scoring.** Range and doubling are the craft. Use the real ranges
(`references/instrument_table.json`), and remember `verify.range_check` before you commit.
Doublings that always work: melody in octaves violins I+II; horns doubling cellos at the
octave for weight; woodwinds filling inner harmony.

**Texture.** Do not write everything all the time. Entries are events: bring the brass in
where the form turns, not from bar 1. Staggered entries (10–30 ms apart) read as an
ensemble; simultaneous ones read as a sampler.

**Motion.** Tremolo strings (`perform.tremolo`, `rate=0.08`), pizzicato ostinati, and a
timpani roll under a build. Crescendo with `perform.crescendo`, not with a Dynamic mark.

**The giveaway.** Everything in the same octave; no rests; a "string section" that is one
MIDI channel playing block chords.

---

## Arabic maqam

**Mode.** `scales` has the ajnas and the maqamat. Hijaz, Nahawand, Kurd, Ajam and Nikriz
are 12-TET and render fine. **Rast, Bayati, Saba and Sikah are microtonal** — the half-flat
degree is their identity, `scales.is_microtonal` says so, and plain MIDI cannot carry it.
Either accept `scales.nearest_12tet` and say you approximated, or give the melodic voice
its own channel and use pitch bend.

**Structure.** Melody is monophonic and heterophonic, not harmonised. The *sayr* — the
path through the maqam — is the form: establish the tonic jins, move to the upper jins,
peak, descend, cadence (*qafla*) back to the tonic.

**Rhythm.** The *iqa'at* in `drums.GROOVES`: `maqsum`, `baladi`, `saidi`, `ayyub`,
`karsilama` (9/8 as 2+2+2+3). Dum (low) and tek (high) are the two strokes and the
pattern of them is the rhythm's name. Thin one out for a quiet section with
`groove(..., skip=['darbuka_ka'])` rather than by dropping the velocity — a section is
loud because of how many strokes it spends, not how hard each one lands.

**The giveaway.** Western triadic harmony under a maqam melody; rounding a microtonal
maqam and calling it authentic.

---

## Hindustani / Carnatic

**Mode.** `scales` has the ten thaats, common ragas, and all 72 melakarta generated from
the formula (`scales.melakarta(n)`).

**A raga is not a scale.** It has an ascending form (*aroha*) and a descending form
(*avaroha*) that often differ, characteristic phrases (*pakad*), a resting note (*vadi*),
and notes you may only approach in one direction. The library gives you the pitch set;
the behaviour is yours to write.

**Form.** *Alap* — free rhythm, no tala, exploring the raga from the low register upward.
Then *jor*, then the composition over a tala. `drums.GROOVES` has `teental` (16),
`keherwa` (8), `dadra` (6). Keep a tanpura drone (tonic + fifth, `perform.sustain` with
`retrigger`) under everything.

**The giveaway.** Chord changes. There are none.

---

## Latin

**Everything is felt against the clave.** Lay `drums.clave(part, 0, 'son_32')` or
`'rumba_32'` down first and write against it. 3-2 and 2-3 are different pieces; do not
switch mid-phrase.

`drums.GROOVES`: `bossa_nova`, `samba`, `cumbia`, `reggaeton` (dembow),
`reggae_one_drop`, `tresillo`, `afro_68` (the 6/8 bell). Montuno piano: syncopated
two-bar arpeggio pattern, anticipating the beat.

**The giveaway.** Everything on the beat; a bass that plays on 1 (in salsa the bass
famously does not).

---

## Rock / pop / electronic

**Form is the craft**: intro, verse, pre-chorus, chorus, verse, chorus, bridge, chorus.
The chorus must be *different* — higher melody, fuller texture, faster harmonic rhythm —
not just louder.

`drums.GROOVES`: `rock_basic`, `rock_16`, `funk_16` (the ghost notes are the point),
`disco`, `half_time`, `boom_bap`.

Guitar: power chords are root+fifth+octave, no third. Distortion and thirds fight.

**The giveaway.** No dynamic difference between verse and chorus; a drum part with no
ghost notes and one velocity per instrument; a bass that only plays roots on downbeats.

---

## Baroque / classical pastiche

**Counterpoint, not chords.** Each voice is a line with its own shape. Use
`voiceLeading.VoiceLeadingQuartet` (`verify.voice_leading_report`) to catch parallel
fifths and octaves — here they *are* errors.

Continuo: figured bass realisation is built in (`figuredBass.realizer`). Alberti bass is
`perform.arpeggio(..., 'alberti')`. Ornaments must be realised to sound:
`stream.realizeOrnaments()`.

Harmonic rhythm is regular and cadences are structural — write the cadence points first.

**The giveaway.** Static harmony; ornaments that don't sound; a "harpsichord" holding
pedal notes it physically cannot sustain.

---

## Building a style that isn't listed

Answer these five, in order, before writing a note:

1. **Mode/scale** — and does it need microtones?
2. **Harmony** — is there any? triadic, quartal, modal, drone, none?
3. **Rhythmic cell** — the smallest repeating unit, and where the accents fall.
4. **Characteristic gesture** — the thing a player of this music does that a sequencer
   never would (rasgueado, ghost note, bend, glissando, ornament, breath).
5. **Form** — and specifically where and why it peaks.

If you cannot answer all five, research the tradition before generating. A style you can
only describe as a vibe will come out as a vibe.
