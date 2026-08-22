"""
Writing MIDI from music21 that actually plays back the way you wrote it.

Three problems this module exists to solve, all of which will silently ruin a
piece if you do not handle them:

1. **Channel folding.** ``streamToMidiFile`` assigns MIDI channels by
   instrument. Several Parts sharing one instrument get folded onto ONE channel,
   and then a note-off from one voice kills a still-sounding identical pitch in
   another. A four-guitar arrangement loses notes. :func:`retrack` fixes it.
2. **Stems.** Mixing five voices by MIDI velocity alone is hopeless. Render one
   audio stem per voice and balance in dB. :func:`write_stems` produces them.
3. **Wall-clock time.** Offsets are in quarter-lengths; audio analysis needs
   seconds. Under a tempo map those are not proportional. :class:`TempoMap`
   converts either way.

See references/06-midi-deep.md for the experiments behind all of this.
"""

from __future__ import annotations

import os
from bisect import bisect_right
from typing import Iterable, Sequence

from music21 import midi, stream, tempo

__all__ = [
    'TempoMap',
    'add_tempo_map',
    'retrack',
    'write_midi',
    'write_stems',
    'DRUM_CHANNEL',
]

#: music21's MidiEvent.channel is **1-based**: the GM drum channel is 10, not 9.
DRUM_CHANNEL = 10


# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------
class TempoMap:
    """Convert between quarter-length offsets and wall-clock seconds.

    Build it from the same ``(offset_ql, bpm)`` list you fed to
    :func:`add_tempo_map`, or from a Score with :meth:`from_score`.

    >>> tm = TempoMap([(0, 60), (8, 120)])
    >>> tm.seconds(8)      # 8 quarters at 60bpm
    8.0
    >>> tm.seconds(16)     # + 8 quarters at 120bpm
    12.0
    >>> round(tm.offset(12.0), 3)
    16.0
    """

    def __init__(self, points: Sequence[tuple[float, float]]):
        pts = sorted((float(o), float(b)) for o, b in points)
        if not pts:
            pts = [(0.0, 120.0)]
        if pts[0][0] > 0:
            pts.insert(0, (0.0, pts[0][1]))
        self.points = pts
        # cumulative seconds at the start of each tempo region
        self._cum = [0.0]
        for i in range(1, len(pts)):
            span = pts[i][0] - pts[i - 1][0]
            self._cum.append(self._cum[-1] + span * 60.0 / pts[i - 1][1])
        self._offsets = [o for o, _ in pts]

    @classmethod
    def from_score(cls, sc: stream.Stream) -> 'TempoMap':
        """Read every MetronomeMark out of a Score (deduplicated by offset)."""
        pts: dict[float, float] = {}
        for mm in sc.recurse().getElementsByClass(tempo.MetronomeMark):
            q = mm.getQuarterBPM()
            if q:
                pts[float(mm.getOffsetInHierarchy(sc))] = float(q)
        return cls(sorted(pts.items()) or [(0.0, 120.0)])

    def seconds(self, offset_ql: float) -> float:
        """Wall-clock seconds at a quarter-length offset."""
        i = max(0, bisect_right(self._offsets, float(offset_ql)) - 1)
        o0, bpm = self.points[i]
        return self._cum[i] + (float(offset_ql) - o0) * 60.0 / bpm

    def offset(self, seconds: float) -> float:
        """Inverse of :meth:`seconds`."""
        i = max(0, bisect_right(self._cum, float(seconds)) - 1)
        o0, bpm = self.points[i]
        return o0 + (float(seconds) - self._cum[i]) * bpm / 60.0

    def bpm_at(self, offset_ql: float) -> float:
        i = max(0, bisect_right(self._offsets, float(offset_ql)) - 1)
        return self.points[i][1]

    def __repr__(self) -> str:
        return f'<TempoMap {len(self.points)} regions, {self.points[:3]}...>'


def add_tempo_map(parts: Iterable[stream.Stream],
                  points: Sequence[tuple[float, float]]) -> TempoMap:
    """Insert MetronomeMarks at ``(offset_ql, bpm)`` into **every** part.

    Put them in every part, not just the first. music21 will happily write one
    conductor track, but if you later export a single Part as a stem it must
    carry its own tempo or the stem drifts out of sync with the others.
    """
    parts = list(parts)
    for off, bpm in points:
        for p in parts:
            p.insert(float(off), tempo.MetronomeMark(number=float(bpm)))
    return TempoMap(points)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
def retrack(mf: midi.MidiFile, channels: Sequence[int]) -> midi.MidiFile:
    """Force one MIDI channel per track, in order, on tracks 1..n.

    ``channels[i]`` is applied to ``mf.tracks[i + 1]`` (track 0 is the conductor
    track music21 writes for tempo/meta). A channel of :data:`DRUM_CHANNEL` (10)
    also strips that track's program-change events, so the GM drum kit is used
    instead of whatever melodic patch music21 inferred.

    This is the single most important function in the package. Without it, four
    guitar Parts all land on channel 1 and cut each other off.
    """
    for idx, ch in enumerate(channels, start=1):
        if idx >= len(mf.tracks):
            break
        keep = []
        for ev in mf.tracks[idx].events:
            if ch == DRUM_CHANNEL and ev.type == midi.ChannelVoiceMessages.PROGRAM_CHANGE:
                continue
            if ev.channel is not None:
                ev.channel = ch
            keep.append(ev)
        mf.tracks[idx].events = keep
    return mf


def _dump(mf: midi.MidiFile, path: str) -> str:
    mf.open(path, 'wb')
    try:
        mf.write()
    finally:
        mf.close()
    return path


def write_midi(score: stream.Score,
               path: str,
               channels: Sequence[int] | None = None) -> str:
    """Write a Score to MIDI with explicit per-part channels.

    Goes through ``midi.translate.streamToMidiFile`` directly rather than
    ``score.write('midi')``, because the converter path can run makeNotation and
    disturb the precise sub-beat offsets that strums and rolls depend on.

    ``channels`` defaults to ``[1, 2, 3, ...]``, skipping 10. Pass 10 explicitly
    for a percussion part.
    """
    parts = list(score.parts) or [score]
    if channels is None:
        channels = []
        nxt = 1
        for _ in parts:
            if nxt == DRUM_CHANNEL:
                nxt += 1
            channels.append(nxt)
            nxt += 1
    mf = midi.translate.streamToMidiFile(score)
    retrack(mf, channels)
    return _dump(mf, path)


def write_stems(score: stream.Score,
                out_dir: str,
                channels: Sequence[int] | None = None,
                names: Sequence[str] | None = None) -> list[str]:
    """Write one single-part MIDI file per Part, for stem rendering.

    Each stem keeps its own channel assignment, so a percussion stem still
    renders as drums on its own. Returns the paths in part order.

    Every Part must already carry the tempo map (see :func:`add_tempo_map`) or
    the stems will not line up.
    """
    os.makedirs(out_dir, exist_ok=True)
    parts = list(score.parts) or [score]
    if channels is None:
        channels = []
        nxt = 1
        for _ in parts:
            if nxt == DRUM_CHANNEL:
                nxt += 1
            channels.append(nxt)
            nxt += 1
    if names is None:
        names = [(p.id if isinstance(p.id, str) else f'part{i}')
                 for i, p in enumerate(parts)]

    paths = []
    for i, (p, ch, nm) in enumerate(zip(parts, channels, names)):
        one = stream.Score()
        one.insert(0, p)
        mf = midi.translate.streamToMidiFile(one)
        retrack(mf, [ch])
        paths.append(_dump(mf, os.path.join(out_dir, f'{i}_{nm}.mid')))
    return paths


def describe_midi(path: str) -> list[dict]:
    """Read a MIDI back and report per-track channels, programs and note counts.

    Always run this on your own output. It is how you catch channel folding
    before you waste a render.
    """
    mf = midi.MidiFile()
    mf.open(path)
    try:
        mf.read()
    finally:
        mf.close()
    out = []
    for i, tr in enumerate(mf.tracks):
        chans, progs, notes, name = set(), set(), 0, ''
        for ev in tr.events:
            if ev.type == midi.ChannelVoiceMessages.NOTE_ON and ev.velocity:
                notes += 1
                chans.add(ev.channel)
            elif ev.type == midi.ChannelVoiceMessages.PROGRAM_CHANGE:
                progs.add(ev.parameter1)
                chans.add(ev.channel)
            elif ev.type == midi.MetaEvents.SEQUENCE_TRACK_NAME:
                name = ev.data.decode('utf-8', 'replace') if isinstance(ev.data, bytes) else str(ev.data)
        out.append({'track': i, 'name': name, 'channels': sorted(c for c in chans if c),
                    'programs': sorted(progs), 'notes': notes})
    return out
