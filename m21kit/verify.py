"""
Checking your own music when you cannot listen to it.

This is the module that matters most if you are an agent. You can write a
beautiful score, render a clean mp3, and have produced something that is in the
wrong key, has the melody buried, peaks in the wrong section, or lost half its
notes to a MIDI channel collision -- and you will not know, because you cannot
hear it.

So measure it. Everything here answers a specific question with a number:

  symbolic   is it in the mode I intended? in range? too rhythmically uniform?
             did I actually quote the tune correctly?
  midi       did every part get its own channel? are the drums on 10?
  audio      does it clip? where is the loudest section? is there a pulse, and
             at what tempo? does the rendered harmony match what I wrote?

Run these before you tell anyone the piece is finished.
See references/15-verifying-without-listening.md.
"""

from __future__ import annotations

import math
import re
import subprocess
import wave
from collections import Counter
from typing import Iterable, Sequence

from music21 import analysis, chord, instrument, key, stream

__all__ = [
    'pitched_parts', 'pitch_report', 'outside_mode', 'range_check', 'key_check', 'rhythm_report',
    'voice_leading_report', 'density_by_part',
    'audio_stats', 'section_levels', 'pulse', 'cycle', 'chroma', 'harmony_match',
    'melody_match', 'full_report',
]

NAMES = 'C C# D D# E F F# G G# A A# B'.split()


def _nm(p: int) -> str:
    return f'{NAMES[p % 12]}{p // 12 - 1}'


# ===========================================================================
# Symbolic checks -- on the music21 Stream, before you render
# ===========================================================================
def pitched_parts(sc: stream.Score) -> stream.Score:
    """A copy of the Score with percussion parts dropped.

    Percussion "pitches" are GM key numbers -- 38 is a snare, not a D2 -- so
    including a drum part in any pitch or key analysis produces nonsense. Run
    every harmonic check on ``pitched_parts(score)``, not on the score.
    """
    out = stream.Score()
    for p in sc.parts:
        if getattr(p, 'm21kit_percussion', False):        # set by drums.hit()
            continue
        insts = list(p.recurse().getElementsByClass(instrument.Instrument))
        if any(isinstance(i, instrument.UnpitchedPercussion) for i in insts):
            continue
        if any(w in str(p.id).lower()
               for w in ('perc', 'drum', 'cajon', 'palmas', 'kit', 'tabla',
                         'darbuka', 'cymbal', 'bateria')):
            continue
        if p.recurse().getElementsByClass('Unpitched'):
            continue
        out.insert(0, p)
    return out


def pitch_report(s: stream.Stream) -> dict:
    """Pitch classes used, ambitus, and the note count."""
    ps = [q.midi for n in s.recurse().notes for q in n.pitches]
    if not ps:
        return {'notes': 0}
    return {
        'notes': len(ps),
        'lowest': _nm(min(ps)), 'lowest_midi': min(ps),
        'highest': _nm(max(ps)), 'highest_midi': max(ps),
        'ambitus_semitones': max(ps) - min(ps),
        'pitch_classes': sorted({p % 12 for p in ps}),
        'pitch_class_names': [NAMES[p] for p in sorted({p % 12 for p in ps})],
    }


def outside_mode(s: stream.Stream, allowed_pcs: Iterable[int],
                 ignore_parts: Sequence[str] = ()) -> dict:
    """Every note whose pitch class is not in the mode you intended.

    ``allowed_pcs`` is pitch classes 0-11 (C=0). Build it from
    ``m21kit.scales.pitches(name, tonic)`` mod 12.

    A handful of chromatic passing tones is fine and expected. A systematic
    offender -- one pitch class appearing hundreds of times -- means you used
    the wrong chord somewhere, and this will find it.
    """
    allowed = set(int(x) % 12 for x in allowed_pcs)
    bad = Counter()
    where: dict[int, list[float]] = {}
    total = 0
    for n in s.recurse().notes:
        site = n.activeSite
        if site is not None and str(getattr(site, 'id', '')) in ignore_parts:
            continue
        for q in n.pitches:
            total += 1
            pc = q.midi % 12
            if pc not in allowed:
                bad[pc] += 1
                where.setdefault(pc, []).append(float(n.offset))
    return {
        'total_notes': total,
        'outside': {NAMES[pc]: c for pc, c in bad.most_common()},
        'outside_count': sum(bad.values()),
        'outside_pct': round(100 * sum(bad.values()) / max(1, total), 2),
        'first_offsets': {NAMES[pc]: sorted(v)[:5] for pc, v in where.items()},
    }


_RANGE_TABLE: dict | None = None


def _table_range(class_name: str) -> tuple[int | None, int | None]:
    """Range from references/instrument_table.json, which has more filled in
    than the music21 classes do (many have no lowestNote at all)."""
    global _RANGE_TABLE
    if _RANGE_TABLE is None:
        import json
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'references', 'instrument_table.json')
        try:
            with open(path) as f:
                data = json.load(f)
            _RANGE_TABLE = {i['class']: i for i in data.get('instruments', [])}
        except Exception:
            _RANGE_TABLE = {}
    e = _RANGE_TABLE.get(class_name) or {}
    return e.get('lowestWrittenMidi'), e.get('highestWrittenMidi')


def range_check(part: stream.Stream, inst=None,
                low: int | None = None, high: int | None = None) -> dict:
    """Notes outside an instrument's playable range.

    Pass a music21 Instrument (its ``lowestNote``/``highestNote``) or explicit
    MIDI bounds. This catches the single most common realism error: writing a
    bass line below the instrument's lowest string. A guitar cannot play below
    E2 (40); a violin cannot play below G3 (55). Sampled soundfonts will happily
    render those notes, and they will sound synthetic and wrong.
    """
    if inst is not None:
        if isinstance(inst, str):
            inst = getattr(instrument, inst, None) or instrument.fromString(inst)
            inst = inst() if isinstance(inst, type) else inst
        lo = inst.lowestNote.midi if getattr(inst, 'lowestNote', None) else None
        hi = inst.highestNote.midi if getattr(inst, 'highestNote', None) else None
        if lo is None or hi is None:
            tlo, thi = _table_range(type(inst).__name__)
            lo, hi = (lo if lo is not None else tlo), (hi if hi is not None else thi)
        lo = lo if lo is not None else low
        hi = hi if hi is not None else high
    else:
        lo, hi = low, high
    if lo is None and hi is None:
        return {'checked': False,
                'reason': 'no range defined for this instrument -- set low/high yourself'}
    bad = []
    for n in part.recurse().notes:
        for q in n.pitches:
            if (lo is not None and q.midi < lo) or (hi is not None and q.midi > hi):
                bad.append({'offset': float(n.offset), 'pitch': q.nameWithOctave,
                            'midi': q.midi})
    return {'checked': True, 'low': lo, 'high': hi,
            'out_of_range': len(bad), 'examples': bad[:12]}


def key_check(s: stream.Stream, expected: str | None = None) -> dict:
    """Run music21's key finder and compare with what you intended.

    Low confidence is not automatically a problem -- modal and non-Western
    music confuses a Krumhansl profile built on common-practice tonality. But
    if you wrote D minor and it says F# major, look again.
    """
    k = s.analyze('key')
    out = {'detected': str(k), 'tonic': k.tonic.name, 'mode': k.mode,
           'confidence': round(float(getattr(k, 'correlationCoefficient', 0)), 3),
           'alternatives': [str(a) for a in list(getattr(k, 'alternateInterpretations', []))[:3]]}
    if expected:
        want = key.Key(expected) if isinstance(expected, str) else expected
        out['expected'] = str(want)
        out['match'] = (k.tonic.name == want.tonic.name and k.mode == want.mode)
    return out


def rhythm_report(s: stream.Stream) -> dict:
    """Is the rhythm alive or is it a grid?

    ``distinct_durations`` under about 3 and ``offset_grid_pct`` near 100 means
    every note is the same length on the beat: technically music, audibly a
    sequencer demo.
    """
    ns = list(s.recurse().notes)
    if not ns:
        return {'notes': 0}
    durs = Counter(round(float(n.quarterLength), 4) for n in ns)
    offs = [float(n.offset) for n in ns]
    on_grid = sum(1 for o in offs if abs(o - round(o)) < 1e-6)
    on_half = sum(1 for o in offs if abs(o * 2 - round(o * 2)) < 1e-6)
    vels = [n.volume.velocity for n in ns if n.volume.velocity is not None]
    return {
        'notes': len(ns),
        'distinct_durations': len(durs),
        'top_durations': durs.most_common(5),
        'offset_grid_pct': round(100 * on_grid / len(offs), 1),
        'offset_eighth_grid_pct': round(100 * on_half / len(offs), 1),
        'velocity_min': min(vels) if vels else None,
        'velocity_max': max(vels) if vels else None,
        'velocity_spread': (max(vels) - min(vels)) if vels else 0,
        'velocity_distinct': len(set(vels)),
    }


def density_by_part(sc: stream.Score) -> list[dict]:
    """Notes per part. A part with 10x the notes of another will dominate the
    mix no matter what velocities you gave it -- this tells you where to set
    stem levels before you render."""
    out = []
    for i, p in enumerate(sc.parts):
        ns = list(p.recurse().notes)
        span = float(p.highestTime) or 1.0
        out.append({'index': i, 'id': str(p.id), 'notes': len(ns),
                    'notes_per_quarter': round(len(ns) / span, 3)})
    return out


def voice_leading_report(sc: stream.Score, limit: int = 20) -> dict:
    """Parallel fifths and octaves between every pair of parts.

    Only meaningful if you are writing in a style that forbids them. Ignore it
    for guitar, rock or anything homophonic-by-design.
    """
    from music21 import voiceLeading
    parts = list(sc.parts)
    found = []
    for a in range(len(parts)):
        for b in range(a + 1, len(parts)):
            na = list(parts[a].flatten().notes)
            nb = list(parts[b].flatten().notes)
            m = min(len(na), len(nb)) - 1
            for i in range(m):
                try:
                    q = voiceLeading.VoiceLeadingQuartet(
                        na[i].pitches[0], na[i + 1].pitches[0],
                        nb[i].pitches[0], nb[i + 1].pitches[0])
                    if q.parallelFifth():
                        found.append(('P5', a, b, float(na[i].offset)))
                    elif q.parallelOctave():
                        found.append(('P8', a, b, float(na[i].offset)))
                except Exception:
                    continue
    return {'count': len(found), 'examples': found[:limit]}


def melody_match(s: stream.Stream, expected: Sequence,
                 transpose: int = 0, tolerance: float = 0.26) -> dict:
    """Did the tune you meant to quote survive into the stream?

    ``expected`` is a sequence of ``(offset, midi)`` pairs or bare midi numbers
    (in which case only the pitch sequence is compared, order-sensitive).
    Use this whenever you arrange existing material -- it is the difference
    between "I transcribed Bella Ciao" and "I think I transcribed Bella Ciao".
    """
    got = sorted((float(n.offset), q.midi)
                 for n in s.recurse().notes for q in n.pitches)
    if expected and not isinstance(expected[0], (tuple, list)):
        seq = [p for _, p in got]
        want = [int(p) + transpose for p in expected]
        # Longest common subsequence, not a greedy scan: a greedy matcher that
        # hits one wrong note runs off the end of the stream and reports a
        # catastrophic score for a single-note error.
        n, m = len(want), len(seq)
        prev = [0] * (m + 1)
        for i in range(1, n + 1):
            cur = [0] * (m + 1)
            wi = want[i - 1]
            for j in range(1, m + 1):
                cur[j] = prev[j - 1] + 1 if wi == seq[j - 1] else max(prev[j], cur[j - 1])
            prev = cur
        hits = prev[m]
        return {'mode': 'pitch-sequence (LCS)', 'expected': n, 'matched': hits,
                'pct': round(100 * hits / max(1, n), 1)}
    idx: dict[float, list[int]] = {}
    for o, p in got:
        idx.setdefault(round(o / tolerance) * tolerance, []).append(p)
    hits = 0
    misses = []
    for o, p in expected:
        want = int(p) + transpose
        key_ = round(float(o) / tolerance) * tolerance
        near = idx.get(key_, []) + idx.get(key_ + tolerance, []) + idx.get(key_ - tolerance, [])
        if want in near:
            hits += 1
        else:
            misses.append((float(o), want))
    return {'mode': 'offset+pitch', 'expected': len(expected), 'matched': hits,
            'pct': round(100 * hits / max(1, len(expected)), 1),
            'first_misses': misses[:10]}


# ===========================================================================
# Audio checks -- on the rendered file
# ===========================================================================
def _decode(path: str, sr: int = 22050):
    """Mono float samples via ffmpeg. Avoids a scipy/librosa dependency."""
    import numpy as np
    p = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr),
         '-f', 's16le', '-'], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:400])
    return np.frombuffer(p.stdout, dtype='<i2').astype('float32') / 32768.0, sr


_DECODE_CACHE: dict = {}


def _decode_cached(path: str, sr: int = 22050):
    """:func:`_decode` with a one-entry memo, keyed on the file's identity.

    Every audio check here decodes the whole file and then slices it, and
    :func:`harmony_match` calls :func:`chroma` once per bar. On a three-minute
    mp3 that was forty full decodes -- 9.4s of ffmpeg to answer a question one
    0.4s decode already had the data for.
    """
    import os
    try:
        st = os.stat(path)
        k = (os.path.abspath(path), sr, st.st_mtime_ns, st.st_size)
    except OSError:
        return _decode(path, sr)
    got = _DECODE_CACHE.get(k)
    if got is None:
        got = _decode(path, sr)
        _DECODE_CACHE.clear()        # these arrays are tens of MB; keep one
        _DECODE_CACHE[k] = got
    return got


def audio_stats(path: str) -> dict:
    """Duration, peak, integrated loudness, and whether it clips.

    Peak at exactly 0.0 dBFS means it clipped -- re-render with lower synth
    gain. Integrated LUFS tells you whether the master hit its target.
    """
    import numpy as np
    x, sr = _decode_cached(path)
    peak = float(np.abs(x).max()) if len(x) else 0.0
    out = {'duration_s': round(len(x) / sr, 2),
           'peak_dbfs': round(20 * math.log10(peak + 1e-12), 2),
           'clipped': peak >= 0.999,
           'rms_dbfs': round(20 * math.log10(float(np.sqrt((x ** 2).mean())) + 1e-12), 2)}
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path,
                        '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    for line in r.splitlines():
        if 'Input Integrated' in line:
            out['lufs'] = float(line.split(':')[1].strip().split()[0])
        elif 'Input True Peak' in line:
            out['true_peak_dbtp'] = float(line.split(':')[1].strip().split()[0])
        elif 'Input LRA' in line:
            out['lra'] = float(line.split(':')[1].strip().split()[0])
    return out


def section_levels(path: str, sections: Sequence[tuple[str, float, float]]) -> list[dict]:
    """RMS per named section, so you can see the shape of the piece.

    ``sections`` is ``(name, start_seconds, end_seconds)``. Use
    :class:`m21kit.midiio.TempoMap` to turn bar numbers into seconds -- under a
    tempo map they are NOT proportional, and eyeballing them is how you end up
    measuring the wrong bars.

    The question this answers: is my climax actually the loudest thing? Very
    often it is not, because a dense accompaniment section out-shouts it.
    """
    import numpy as np
    x, sr = _decode_cached(path)
    out = []
    for name, a, b in sections:
        seg = x[int(a * sr):int(b * sr)]
        rms = 20 * math.log10(float(np.sqrt((seg ** 2).mean())) + 1e-12) if len(seg) else -120
        out.append({'section': name, 'start': a, 'end': b, 'rms_db': round(rms, 1)})
    if out:
        top = max(out, key=lambda d: d['rms_db'])
        for d in out:
            d['is_peak'] = (d is top)
    return out


def pulse(path: str, start: float = 0.0, end: float | None = None,
          min_bpm: float = 45, max_bpm: float = 220) -> dict:
    """Is there a beat, and how strong is it?

    Autocorrelation of the log onset envelope, restricted to plausible beat
    periods so it cannot lock onto a tremolo or a strum's internal spacing --
    which is exactly the mistake that makes naive tempo detection useless here.

    ``strength`` well under 0.1 means genuinely free rhythm; 0.3+ means a clear
    pulse. Use it to prove a rubato passage really is unmetered, or that your
    groove actually landed at the tempo you wrote.
    """
    import numpy as np
    x, sr = _decode_cached(path)
    if end is None:
        end = len(x) / sr
    x = x[int(start * sr):int(end * sr)]
    if len(x) < sr:
        return {'strength': 0.0, 'bpm': None, 'note': 'segment too short'}
    hop = 256
    fps = sr / hop
    env = np.sqrt(np.array([(x[i:i + hop] ** 2).mean()
                            for i in range(0, len(x) - hop, hop)]))
    on = np.maximum(0, np.diff(np.log(env + 1e-6)))
    on = on - on.mean()
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    ac /= (ac[0] + 1e-9)
    lo, hi = int(fps * 60 / max_bpm), int(fps * 60 / min_bpm)
    lo, hi = max(1, lo), min(len(ac) - 1, hi)
    if hi <= lo:
        return {'strength': 0.0, 'bpm': None}
    k = lo + int(np.argmax(ac[lo:hi]))
    return {'strength': round(float(ac[lo:hi].max()), 3),
            'period_s': round(k / fps, 3),
            'bpm': round(60 / (k / fps), 1),
            'metered': bool(ac[lo:hi].max() > 0.15)}


def cycle(path: str, start: float = 0.0, end: float | None = None,
          low_s: float = 1.0, high_s: float = 8.0) -> dict:
    """Find the long rhythmic CYCLE, the thing :func:`pulse` cannot see.

    ``pulse`` searches 0.27-1.33s because it is looking for a beat, and that is
    the right window for a groove. It is the wrong instrument for an iqa' or a
    tala: samai thaqil is ten eighths grouped 3+2+2+3 with strokes on only five
    of them, so at any sane tempo its cycle is 4-6 seconds long and only five
    events wide. ``pulse`` reports near-zero strength and ``metered: False`` for
    music that is perfectly, audibly metred.

    This autocorrelates the onset-strength envelope over a window sized for
    cycles instead. Point it at a percussion stem where you have one -- a full
    mix full of legato strings will bury the strokes.

        cycle('darbouka.wav', 40, 120, 3.0, 6.0)
        # {'period_s': 4.168, 'strength': 0.5, 'bpm_cycle': 14.4, 'metered': True}

    ``strength`` is the normalised autocorrelation at the peak: above ~0.25 the
    cycle is really there, and below ~0.1 the passage is free rhythm. That
    comparison is how you *prove* a taqsim is unmetred rather than asserting it.
    """
    import numpy as np
    x, sr = _decode_cached(path)
    if end is None:
        end = len(x) / sr
    x = x[int(start * sr):int(end * sr)]
    if len(x) < sr * max(2.0, low_s * 2):
        return {'strength': 0.0, 'period_s': None, 'note': 'segment too short'}
    hop = 256
    fps = sr / hop
    env = np.sqrt(np.array([(x[i:i + hop] ** 2).mean()
                            for i in range(0, len(x) - hop, hop)]))
    on = np.maximum(0.0, np.diff(np.log(env + 1e-6)))
    on = on - on.mean()
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    ac /= (ac[0] + 1e-9)
    lo, hi = int(low_s * fps), min(len(ac) - 1, int(high_s * fps))
    if hi <= lo:
        return {'strength': 0.0, 'period_s': None}
    k = lo + int(np.argmax(ac[lo:hi]))
    strength = float(ac[lo:hi].max())
    return {'period_s': round(k / fps, 3),
            'strength': round(strength, 3),
            'bpm_cycle': round(60.0 / (k / fps), 2),
            'metered': bool(strength > 0.25)}


def chroma(path: str, start: float, end: float) -> list[float]:
    """Normalised 12-bin pitch-class energy of an audio segment."""
    import numpy as np
    x, sr = _decode_cached(path)
    seg = x[int(start * sr):int(end * sr)]
    if len(seg) < 512:
        return [0.0] * 12
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    ok = (f > 70) & (f < 2200)
    midi = 69 + 12 * np.log2(np.maximum(f[ok], 1e-9) / 440.0)
    c = np.zeros(12)
    np.add.at(c, (np.round(midi).astype(int) % 12), S[ok])
    tot = c.sum() or 1.0
    return [round(float(v / tot), 4) for v in c]


_TPL = {}
for _r in range(12):
    _TPL[NAMES[_r]] = [(_r + i) % 12 for i in (0, 4, 7)]
    _TPL[NAMES[_r] + 'm'] = [(_r + i) % 12 for i in (0, 3, 7)]
    _TPL[NAMES[_r] + '7'] = [(_r + i) % 12 for i in (0, 4, 7, 10)]
    _TPL[NAMES[_r] + 'dim'] = [(_r + i) % 12 for i in (0, 3, 6)]

_ROOT_RE = re.compile(r'^\s*([A-Ga-g])([#b\u266f\u266d]*)')
_LETTER_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def chord_root_pc(name: str) -> int | None:
    """Pitch class 0-11 of a chord symbol's root, or None if it does not parse.

    Accepts flats as readily as sharps and ignores the suffix entirely, so
    ``Eb``, ``D#``, ``Cmaj7``, ``F#m7b5``, ``Gsus4`` and ``Am`` all resolve.
    Comparing roots as pitch classes is the only way to do it: matching the
    printed name means ``Eb`` never equals ``D#``, and stripping a suffix by
    characters mangles anything but the four shortest ones.
    """
    m = _ROOT_RE.match(str(name))
    if not m:
        return None
    pc = _LETTER_PC[m.group(1).upper()]
    for ch in m.group(2):
        pc += 1 if ch in '#\u266f' else -1
    return pc % 12


def harmony_match(path: str, expected: Sequence[tuple[float, float, str]]) -> dict:
    """Did the harmony you wrote survive into the audio?

    ``expected`` is ``(start_s, end_s, chord_name)`` -- e.g. ``('Dm', 'A7')``
    names in any common spelling -- 'Eb', 'D#', 'Cmaj7', 'F#m7b5' all work, and
    the suffix is ignored. Compares only the ROOT, because a chroma estimate
    cannot reliably tell a triad from its relative. Anything above ~85% root
    agreement means the render is playing what you wrote.

    A name that cannot be parsed is reported under ``unparsed_names`` rather
    than quietly counting as a mismatch.
    """
    hits = 0
    rows = []
    unparsed = []
    for a, b, want in expected:
        c = chroma(path, a, b)
        want_pc = chord_root_pc(want)
        if want_pc is None:
            unparsed.append(str(want))
        if not any(c):
            rows.append({'start': a, 'expected': want, 'detected': None,
                         'root_ok': False, 'note': 'silent segment'})
            continue
        got = max(_TPL, key=lambda k: sum(c[p] for p in _TPL[k]) / len(_TPL[k]))
        ok = want_pc is not None and chord_root_pc(got) == want_pc
        hits += ok
        rows.append({'start': a, 'expected': want, 'detected': got, 'root_ok': ok})
    out = {'bars': len(expected), 'root_matches': hits,
           'pct': round(100 * hits / max(1, len(expected)), 1), 'rows': rows}
    if unparsed:
        # Loud, because the old behaviour was to score these 0 in silence.
        out['unparsed_names'] = sorted(set(unparsed))
    return out


# ===========================================================================
def full_report(sc: stream.Score | None = None, audio: str | None = None,
                midi_path: str | None = None,
                allowed_pcs: Iterable[int] | None = None,
                expected_key: str | None = None,
                sections: Sequence[tuple[str, float, float]] | None = None) -> dict:
    """Run everything that applies and return one dict. Print it and read it."""
    rep: dict = {}
    if sc is not None:
        rep['pitch'] = pitch_report(sc)
        rep['rhythm'] = rhythm_report(sc)
        rep['density'] = density_by_part(sc) if hasattr(sc, 'parts') else None
        if allowed_pcs is not None:
            rep['mode'] = outside_mode(sc, allowed_pcs)
        try:
            rep['key'] = key_check(sc, expected_key)
        except Exception as e:
            rep['key'] = {'error': str(e)}
    if midi_path:
        from m21kit.midiio import describe_midi
        rep['midi_tracks'] = describe_midi(midi_path)
        chans = [t['channels'] for t in rep['midi_tracks'] if t['notes']]
        flat = [c for cs in chans for c in cs]
        rep['midi_channel_collision'] = len(flat) != len(set(flat))
    if audio:
        rep['audio'] = audio_stats(audio)
        rep['pulse'] = pulse(audio)
        if sections:
            rep['sections'] = section_levels(audio, sections)
    return rep
