# Worked examples

Three complete pieces, each written and rendered end to end. They are here because they
are *real* — several minutes long, multi-section, verified — not because they are tidy.
They predate `m21kit` and use raw music21 throughout, which makes them useful in a second
way: you can see exactly what the toolkit replaced.

Each has a `NN_render.sh` that renders stems, mixes and masters it.

---

## 01 — Una Mattina / Bella Ciao, rumba flamenca

`01_una_mattina_bella_ciao_flamenco.py` · 2:53 · A minor

**What it demonstrates:** mashing two tunes that share a motivic cell. Einaudi's ostinato
and the opening of *Bella Ciao* are both built from **E–A–B–C**, so the final section
stacks the tune verbatim over the ostinato. Finding that kind of shared cell *before*
writing is what makes a mashup work rather than a medley.

Also: strum micro-timing with an *abanico* direction flip, the rumba 3+3+2 in the cajón,
palmas in compás, and a 64-bar sonata-ish arc with the climax placed deliberately.

**Bug it caught:** all four guitar voices landed on MIDI channel 1 and were cutting each
other off — the reason `midiio.retrack` exists. Also a bass line an octave below a
guitar's low E, which `verify.range_check` would now catch.

**Verified:** melody matches the transcription note-for-note; chroma analysis agrees with
the intended chord in 44/47 bars.

---

## 02 — Adhan por Granaína, free rhythm

`02_adhan_free_rhythm.py` · 4:01 · Maqam Hijaz on E

**What it demonstrates:** **non-metric music done properly.** The adhan is *mursala* —
unmetered — so tempo is fixed at 60 bpm and the whole piece is composed in *seconds*.
Phrase lengths (4.0, 4.6, 4.3, 5.9, 7.0, 6.8, 8.2 … 11.7 s) come from breath and Arabic
prosody, and the silences between them are real and structural. Flamenco's free forms
(*granaína*, *taranta*) put the guitar's answer in exactly those silences, which is how
the two traditions meet without either bending.

The mode is the argument: flamenco's *por arriba* Phrygian dominant **is** maqam Hijaz.

Also: a vocal line played as guitar tremolo with an attack swell, decay and 5 Hz vibrato;
ligado melismas; grace-note portamento.

**Verified:** onset-envelope autocorrelation at beat-length lags reads **0.069** in the
free sections against **0.173** in the one metered interlude — measured proof that the
call is unmetered rather than an assertion that it is. This is what `verify.pulse` does.

---

## 03 — Mozart por Tangos, K.550/i

`03_mozart40_arrangement.py` · 3:30 · D minor

**What it demonstrates:** arranging from a **real score, not from memory**. The Violin I
line is read out of a MIDI of the movement with music21, snapped to a sixteenth grid,
transposed, and played verbatim — **397 notes, 100 % of them at the correct offset**,
checked programmatically. The arrangement is entirely in the accompaniment and compás.

The transposition is the argument. G minor down a fourth is D minor, whose Andalusian
cadence Dm–C–B♭–A is flamenco *por medio*. Then Mozart cooperates: his E♭–D sigh becomes
B♭–A, the Phrygian ♭2–1; his first subject is Dm answered by A7, i answered by the
Phrygian tonic; and the bass of his transition walks F–E–D–C–B♭–A, whose last four steps
are the Andalusian cadence itself. Look for that kind of alignment before choosing a key.

Also: harmony derived bar-by-bar from Mozart's own bass line rather than invented, and a
development section reduced to bare picado plus bass octaves because his remote keys
(C♯ minor, F♯) have no idiomatic flamenco voicing — which is what a falseta does anyway.

**Verified:** 397/397 source notes present; audio pulses at exactly the written 152 bpm.

---

## What they have in common

Every one of them:

1. names its form, mode and climax before any code;
2. finds a *reason* the two things being combined belong together, rather than
   layering them;
3. writes at absolute offsets, not in measures;
4. renders per-voice stems and balances in dB;
5. is checked numerically, because nobody could listen to it.

The third and fifth are now `m21kit.midiio` and `m21kit.verify`. The first two are not
automatable and are most of the difference between music and output.
