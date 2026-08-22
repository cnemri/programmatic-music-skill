"""
Performance gestures -- everything a score implies but does not write down.

A Chord object is four pitches at one instant. A guitarist never plays that: the
strings are struck 20-40ms apart, low to high, and the last two ring loudest. A
half note held by a singer is not one MIDI event, it is a shape. Notation elides
all of this, and MIDI rendered straight from notation sounds like notation.

Every function here places notes at **absolute quarter-length offsets** into a
flat Part with ``insert()``. That is the composition style you want for anything
performance-shaped; see references/01-object-model.md for why, and
references/12-performance-realism.md for the musical reasoning.

    import random
    from music21 import stream
    from m21kit import perform as pf

    p = stream.Part()
    pf.strum(p, 0.0, [40, 47, 52, 56, 59, 64], dur=1.0, vel=90)
"""

from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

from music21 import duration, note, stream

__all__ = [
    'put', 'strum', 'rasgueado', 'roll', 'arpeggio', 'run', 'tremolo',
    'ligado', 'grace_into', 'sustain', 'humanize', 'swing', 'crescendo',
    'PATTERNS',
]

# Common arpeggio index patterns, indexes into the chord's pitch list.
PATTERNS = {
    'up': [0, 1, 2, 3],
    'down': [3, 2, 1, 0],
    'updown': [0, 1, 2, 3, 2, 1],
    'pima': [0, 1, 2, 3, 2, 1, 2, 3],        # classical guitar, 8ths
    'pimami': [0, 1, 2, 3, 2, 1, 2, 3, 0, 1, 2, 3, 4, 3, 2, 1],
    'alberti': [0, 3, 1, 3],                  # Alberti bass
    'waltz': [0, 2, 3, 0, 2, 3],
    'rolling': [0, 1, 2, 3, 4, 3, 2, 1],
}


def _v(x: float) -> int:
    return max(1, min(127, int(round(x))))


def put(part: stream.Stream, offset: float, pitch, dur: float, vel: float,
        jitter: float = 0.0) -> note.Note:
    """Insert one note at an absolute quarter-length offset.

    ``pitch`` may be a MIDI number, a name ('C#4'), or a music21 Pitch.
    ``jitter`` is +/- quarter-lengths of random timing noise; 0.008-0.015 is a
    good human range at moderate tempo. Never let jitter push an offset below 0.
    """
    n = note.Note(pitch)
    n.duration = duration.Duration(quarterLength=max(float(dur), 0.05))
    n.volume.velocity = _v(vel)
    t = float(offset) + (random.uniform(-jitter, jitter) if jitter else 0.0)
    part.insert(max(0.0, t), n)
    return n


# ---------------------------------------------------------------------------
# Plucked / strummed
# ---------------------------------------------------------------------------
def strum(part: stream.Stream, offset: float, pitches: Sequence,
          dur: float = 1.0, vel: float = 88, spread: float = 0.035,
          up: bool = False, top_boost: float = 5.0, decay: float = 1.3,
          jitter: float = 0.006) -> None:
    """One strum: chord tones fanned out in time like a real picking hand.

    ``spread`` is the gap between consecutive strings in quarter-lengths. At
    120bpm one quarter-length is 0.5s, so spread=0.035 is ~17ms per string --
    about right for a moderate down-strum. Fast up-strokes are tighter (0.02),
    a slow expressive rasgueo wider (0.05).

    The first string struck rings longest (``dur`` shrinks along the sweep) and
    the last two are loudest (``top_boost``), because that is what a real strum
    does and it is most of why a strum sounds like a strum.

    ``up=True`` sweeps high string to low.
    """
    ps = sorted(pitches, reverse=up)
    n = len(ps)
    for i, p in enumerate(ps):
        d = max(0.1, float(dur) - i * spread)
        v = vel + (top_boost if i >= n - 2 else 0.0) - i * decay
        put(part, float(offset) + i * spread, p, d, v, jitter=jitter)


def roll(part: stream.Stream, offset: float, pitches: Sequence,
         total: float = 1.0, hits: int = 5, vel: float = 90,
         spread: float = 0.028, crescendo_amt: float = 18.0,
         alternate: bool = True, thin_middle: bool = True) -> None:
    """A repeated strum -- a rasgueado, a mandolin tremolo, a banjo roll.

    ``hits`` strums packed into ``total`` quarter-lengths, each one slightly
    louder than the last so the figure drives into the beat rather than
    trailing off it. ``alternate`` flips sweep direction each hit (the flamenco
    *abanico*); ``thin_middle`` plays only the top strings on the inner hits,
    which is both what the hand does and what keeps the texture from clogging.
    """
    step = float(total) / (hits + 0.6)
    for k in range(hits):
        frac = k / max(1, hits - 1)
        v = vel - crescendo_amt + crescendo_amt * 2 * frac * 0.5 + crescendo_amt * frac * 0.5
        sub = pitches if (k in (0, hits - 1) or not thin_middle) else list(pitches)[-4:]
        strum(part, float(offset) + k * step, sub,
              dur=float(total) - k * step + 0.4, vel=v, spread=spread,
              up=(alternate and k % 2 == 1))


def rasgueado(part: stream.Stream, offset: float, pitches: Sequence,
              total: float = 1.0, hits: int = 5, vel: float = 90,
              spread: float = 0.028) -> None:
    """Flamenco rasgueado -- :func:`roll` with the idiomatic defaults."""
    roll(part, offset, pitches, total=total, hits=hits, vel=vel,
         spread=spread, alternate=True, thin_middle=True)


def arpeggio(part: stream.Stream, offset: float, pitches: Sequence,
             pattern: Sequence[int] | str = 'pima', step: float = 0.25,
             vel: float = 68, dur: float | None = None,
             accents: Iterable[int] = (0,), accent_amt: float = 10.0,
             jitter: float = 0.008) -> float:
    """Broken chord. ``pattern`` indexes into ``pitches`` (or a key of PATTERNS).

    ``dur`` defaults to ``step * 2.6`` so notes overlap and the chord rings, the
    way it does on a guitar or harp where you do not damp between notes.
    Returns the offset just past the end.
    """
    if isinstance(pattern, str):
        pattern = PATTERNS[pattern]
    ps = list(pitches)
    accents = set(accents)
    for k, idx in enumerate(pattern):
        v = vel + (accent_amt if k in accents else 0.0) + random.uniform(-4, 4)
        put(part, float(offset) + k * step, ps[idx % len(ps)],
            dur if dur is not None else step * 2.6, v, jitter=jitter)
    return float(offset) + len(pattern) * step


def run(part: stream.Stream, offset: float, pitches: Sequence,
        step: float = 0.25, vel: float = 84, accent_every: int = 4,
        accent_amt: float = 9.0, legato: float = 1.15,
        jitter: float = 0.006) -> float:
    """A fast single-note line -- guitar *picado*, a scalar flourish, a lick.

    Accenting every Nth note is what keeps a run from sounding like a
    sequencer. Returns the offset just past the end.
    """
    for k, p in enumerate(pitches):
        v = vel + (accent_amt if k % accent_every == 0 else 0.0) + random.uniform(-3, 3)
        put(part, float(offset) + k * step, p, step * legato, v, jitter=jitter)
    return float(offset) + len(pitches) * step


def tremolo(part: stream.Stream, offset: float, pitch, dur: float,
            vel: float = 82, rate: float = 0.1, vibrato_hz: float = 5.0,
            vibrato_depth: float = 3.0, attack: float = 0.14,
            decay: float = 0.34, jitter: float = 0.006) -> float:
    """Sustain one pitch by repeating it -- how a guitar, mandolin or cimbalom
    holds a long note, and the only convincing way to make a plucked instrument
    "sing" a vocal line.

    The envelope matters more than the repetition: a swell in over ``attack``
    (as a fraction of the note), a gentle fall over the tail, and a few
    velocity cents of ~5Hz undulation that the ear reads as vibrato. Without
    the envelope it sounds like a stuck key.
    """
    n = max(2, int(round(float(dur) / rate)))
    for k in range(n):
        f = k / max(1, n - 1)
        env = 1.0 - decay * (max(0.0, f - (1 - decay - 0.1)) / max(0.05, decay + 0.1)) ** 2
        env *= (1 - 0.28) + 0.28 * min(1.0, f / max(1e-6, attack))
        vib = vibrato_depth * math.sin(2 * math.pi * vibrato_hz * k * rate)
        put(part, float(offset) + k * rate, pitch, rate * 1.9,
            vel * env + vib + random.uniform(-2, 2), jitter=jitter)
    return float(offset) + float(dur)


def guitar_tremolo(bass_part: stream.Stream, mel_part: stream.Stream,
                   offset: float, bass_pitches: Sequence, melody_pitch,
                   vel: float = 82, unit: float = 0.25) -> float:
    """Classical/flamenco tremolo proper: p-a-m-i. The thumb takes the bass on
    the beat, then three fast repeats of the melody note fill the beat."""
    strum(bass_part, offset, bass_pitches, unit * 4.2, vel - 6, spread=0.03)
    put(mel_part, offset, melody_pitch, unit * 0.9, vel + 4)
    for k in range(1, 4):
        put(mel_part, float(offset) + k * unit, melody_pitch, unit * 1.25,
            vel + (8 if k == 1 else 0) - k)
    return float(offset) + unit * 4


def ligado(part: stream.Stream, offset: float, pitches: Sequence,
           step: float = 0.145, vel: float = 80, overlap: float = 1.75,
           jitter: float = 0.005) -> float:
    """Hammer-ons and pull-offs / a vocal melisma: notes deliberately overlap,
    so each is still sounding as the next arrives. Only the first is really
    struck, so it is the loudest."""
    for k, p in enumerate(pitches):
        put(part, float(offset) + k * step, p, step * overlap,
            vel - 4 + (5 if k == 0 else 0) + random.uniform(-3, 3), jitter=jitter)
    return float(offset) + len(pitches) * step


def grace_into(part: stream.Stream, offset: float, grace_pitch, vel: float,
               lead: float = 0.075, dur: float = 0.16) -> None:
    """A grace note placed *before* the beat -- the guitar's portamento, a
    vocal scoop, an acciaccatura. Real music21 grace notes have zero MIDI
    duration and often do not sound; a short real note before the beat always
    does."""
    put(part, max(0.0, float(offset) - lead), grace_pitch, dur, vel - 22)


def sustain(part: stream.Stream, offset: float, pitch, dur: float,
            vel: float = 70, retrigger: float = 0.0) -> None:
    """A held note, optionally re-struck every ``retrigger`` quarter-lengths so
    a decaying sample (piano, guitar) does not fade to nothing under a long
    phrase."""
    if retrigger <= 0:
        put(part, offset, pitch, dur, vel)
        return
    t, end = float(offset), float(offset) + float(dur)
    k = 0
    while t < end - 1e-6:
        seg = min(retrigger, end - t)
        put(part, t, pitch, seg * 1.05, vel - k * 3)
        t += retrigger
        k += 1


# ---------------------------------------------------------------------------
# Whole-stream shaping
# ---------------------------------------------------------------------------
def humanize(s: stream.Stream, timing: float = 0.012, velocity: float = 5.0,
             seed: int | None = None) -> stream.Stream:
    """Nudge every note's offset and velocity by a small random amount.

    Use this on music you generated on a strict grid. It is a blunt instrument:
    it is no substitute for writing the accents in deliberately (see
    :func:`drums.groove` and the ``accent`` arguments above), but a piece with
    zero timing noise reads as mechanical no matter how good the notes are.

    Mutates and returns ``s``.
    """
    rng = random.Random(seed)
    for n in list(s.recurse().notes):
        site = n.activeSite
        if site is None:
            continue
        off = float(n.getOffsetBySite(site))
        site.setElementOffset(n, max(0.0, off + rng.uniform(-timing, timing)))
        cur = n.volume.velocity if n.volume.velocity is not None else 90  # m21 default
        n.volume.velocity = _v(cur + rng.uniform(-velocity, velocity))
    return s


def swing(s: stream.Stream, ratio: float = 0.62, unit: float = 0.5) -> stream.Stream:
    """Push every off-beat subdivision later, turning straight eighths into
    swung ones.

    ``ratio`` is where the off-beat lands inside its pair: 0.5 is straight,
    0.667 is triplet swing, 0.58-0.62 is the light swing of most jazz at
    medium-up tempo. ``unit`` is the beat being subdivided (0.5 = swing the
    eighths, 0.25 = swing the sixteenths).

    Mutates and returns ``s``.
    """
    pair = unit * 2
    for n in list(s.recurse().notes):
        site = n.activeSite
        if site is None:
            continue
        off = float(n.getOffsetBySite(site))
        pos = off % pair
        if abs(pos - unit) < 1e-6:
            site.setElementOffset(n, off - unit + pair * ratio)
    return s


def crescendo(s: stream.Stream, start_off: float, end_off: float,
              v0: float = 50, v1: float = 110) -> stream.Stream:
    """Ramp velocity linearly across an offset window.

    Hairpin spanners (``Crescendo``/``Diminuendo``) have no effect on MIDI at
    all, so a crescendo has to be written as velocities. Note that a ``Dynamic``
    object in the Part would then *rescale* everything this function wrote --
    they multiply rather than defer -- so do not mix the two approaches.
    """
    span = max(1e-6, float(end_off) - float(start_off))
    for n in list(s.recurse().notes):
        site = n.activeSite
        if site is None:
            continue
        off = float(n.getOffsetBySite(site))
        if start_off <= off <= end_off:
            f = (off - start_off) / span
            n.volume.velocity = _v(v0 + (v1 - v0) * f)
    return s
