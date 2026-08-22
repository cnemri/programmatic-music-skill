#!/usr/bin/env python3
"""Audio file in -> editable music21 Score out.

Picks the best transcription backend available in the current interpreter and
degrades gracefully when optional dependencies are missing:

    basic-pitch  polyphonic, neural, best quality      (needs Python <=3.12)
    pyin         monophonic, librosa, no model needed  (works on 3.14)
    audiosearch  monophonic, music21 built-in, weak    (always available)

Everything after transcription -- tempo mapping, note-event cleanup, quantize,
key/meter inference, chordify, harmonic reduction -- is pure music21 and runs
anywhere music21 does.

    python audio_to_score.py song.mp3 -o song.musicxml
    python audio_to_score.py solo.wav --backend pyin --monophonic
    python audio_to_score.py song.mp3 --tempo 152 --quantize 4,3 --reduce
    python audio_to_score.py song.mp3 --max-seconds 30 --transpose 3 --show

Verified on music21 10.5.0 / Python 3.14 (pyin + audiosearch backends) and
basic-pitch 0.3.0 / Python 3.12 (basic-pitch backend).
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter

from music21 import chord, instrument
from music21 import key as m21key
from music21 import metadata, meter, note, pitch, roman, stream, tempo


# --------------------------------------------------------------- utilities


def _have(mod: str) -> bool:
    """True if `mod` is importable, without keeping it imported."""
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, file=sys.stderr)


def decode_to_wav(src: str, sr: int = 44100, mono: bool = True,
                  max_seconds: float | None = None) -> str:
    """ffmpeg -> 16-bit PCM wav in a temp file. Returns the new path.

    music21's own audioSearch reads via the stdlib `wave` module, which cannot
    open mp3/m4a/flac at all, and mis-reads anything that is not mono/16-bit.
    """
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg not on PATH; cannot decode ' + src)
    fd, out = tempfile.mkstemp(suffix='.wav', prefix='a2s_')
    os.close(fd)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', src,
           '-ac', '1' if mono else '2', '-ar', str(sr), '-sample_fmt', 's16']
    if max_seconds:
        cmd += ['-t', str(max_seconds)]
    subprocess.run(cmd + [out], check=True)
    return out


# ------------------------------------------------------------- transcribe
# Every backend returns a list of note events:
#     (start_sec, end_sec, midi_pitch:int, amplitude:float 0..1)


def transcribe_basic_pitch(src: str, quiet: bool = False, **kw) -> list[tuple]:
    """Spotify basic-pitch. Polyphonic, instrument-agnostic, ~90x realtime."""
    import warnings
    warnings.filterwarnings('ignore')
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    model = str(ICASSP_2022_MODEL_PATH)
    # 0.3.x ships a TF SavedModel that Keras 3 refuses to load; the bundled
    # .onnx works everywhere onnxruntime is installed.
    if _have('onnxruntime') and os.path.exists(model + '.onnx'):
        model = model + '.onnx'
    t = time.time()
    _out, _midi, events = predict(
        src, model,
        onset_threshold=kw.get('onset_threshold', 0.5),
        frame_threshold=kw.get('frame_threshold', 0.3),
        minimum_note_length=kw.get('minimum_note_length', 127.7),
    )
    log(f'  basic-pitch: {len(events)} events in {time.time() - t:.1f}s', quiet)
    # events are (start, end, midi, amplitude, bends) and are NOT time-sorted
    return sorted([(e[0], e[1], int(e[2]), float(e[3])) for e in events])


def transcribe_pyin(src: str, quiet: bool = False, **kw) -> list[tuple]:
    """librosa pYIN f0 -> monophonic note events. No model download."""
    import numpy as np
    import librosa

    t = time.time()
    y, sr = librosa.load(src, sr=22050, mono=True)
    f0, voiced, _prob = librosa.pyin(
        y, sr=sr,
        fmin=kw.get('fmin', librosa.note_to_hz('C2')),
        fmax=kw.get('fmax', librosa.note_to_hz('C7')))
    times = librosa.times_like(f0, sr=sr)
    rms = librosa.feature.rms(y=y)[0]

    events, cur, start, i0 = [], None, 0.0, 0
    for i, (hz, ok) in enumerate(zip(f0, voiced)):
        m = int(round(librosa.hz_to_midi(hz))) if (ok and hz and not np.isnan(hz)) else None
        if m != cur:
            if cur is not None and times[i] - start > 0.04:
                amp = float(np.mean(rms[i0:max(i0 + 1, i)])) if len(rms) else 0.5
                events.append((float(start), float(times[i]), cur, amp))
            cur, start, i0 = m, float(times[i]), i
    if cur is not None and times[-1] - start > 0.04:
        events.append((float(start), float(times[-1]), cur, 0.5))
    log(f'  pyin: {len(events)} events in {time.time() - t:.1f}s', quiet)
    return events


def transcribe_audiosearch(src: str, quiet: bool = False, **kw) -> list[tuple]:
    """music21's built-in autocorrelation transcriber. Weakest option.

    Requires a MONO 16-bit 44100 Hz wav: the sample rate is hardcoded to 44100
    in audioSearch, so any other rate comes out transposed, and stereo is read
    as interleaved garbage.
    """
    from music21.audioSearch import transcriber
    if not _have('scipy'):
        # Without scipy, autocorrelationFunction falls back to numpy.convolve, which
        # keeps the int16 dtype; the autocorrelation peak overflows and the result is
        # near-empty rather than merely imprecise.
        log('  WARNING: scipy is missing -- audioSearch will return garbage. '
            'pip install scipy', quiet)
    wav = decode_to_wav(src, sr=44100, mono=True, max_seconds=kw.get('max_seconds'))
    try:
        t = time.time()
        part = transcriber.monophonicStreamFromFile(wav)
        log(f'  audioSearch: {len(part.flatten().notes)} notes in '
            f'{time.time() - t:.1f}s', quiet)
        # audioSearch emits quarterLengths directly, not seconds. Re-express as
        # events at a nominal 120bpm so the rest of the pipeline is uniform.
        events, off = [], 0.0
        for n in part.flatten().notesAndRests:
            dur = float(n.quarterLength) * 0.5
            if isinstance(n, note.Note):
                events.append((off, off + dur, int(n.pitch.midi), 0.6))
            off += dur
        return events
    finally:
        os.unlink(wav)


BACKENDS = {
    'basic-pitch': (transcribe_basic_pitch, 'basic_pitch', 'polyphonic'),
    'pyin': (transcribe_pyin, 'librosa', 'monophonic'),
    'audiosearch': (transcribe_audiosearch, 'music21', 'monophonic'),
}


def pick_backend(requested: str, monophonic: bool, quiet: bool = False) -> str:
    if requested != 'auto':
        fn, mod, _ = BACKENDS[requested]
        if not _have(mod):
            raise SystemExit(
                f'backend {requested!r} needs {mod!r}, which is not installed.\n'
                f'  pip install {"basic-pitch onnxruntime" if mod == "basic_pitch" else mod}')
        return requested
    order = ['pyin', 'basic-pitch', 'audiosearch'] if monophonic else \
            ['basic-pitch', 'pyin', 'audiosearch']
    for name in order:
        if _have(BACKENDS[name][1]):
            log(f'  auto-selected backend: {name}', quiet)
            return name
    return 'audiosearch'


# ------------------------------------------------------------ tempo / grid


def estimate_tempo(src: str, default: float = 120.0, quiet: bool = False) -> float:
    """librosa beat tracker, falling back to `default` when librosa is absent."""
    if not _have('librosa'):
        log(f'  librosa missing; assuming {default} bpm', quiet)
        return default
    import numpy as np
    import librosa
    y, sr = librosa.load(src, sr=22050, mono=True, duration=120)
    bpm = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    log(f'  estimated tempo: {bpm:.1f} bpm', quiet)
    return bpm


# --------------------------------------------------------------- cleanup


def clean_events(events: list[tuple], min_duration: float = 0.05,
                 min_amplitude: float = 0.0, merge_gap: float = 0.03,
                 quiet: bool = False) -> list[tuple]:
    """Drop blips and quiet noise, then merge repeated identical pitches."""
    n0 = len(events)
    kept = [e for e in events
            if (e[1] - e[0]) >= min_duration and e[3] >= min_amplitude]
    kept.sort()

    merged: list[list] = []
    by_pitch: dict[int, list] = {}
    for s, e, m, a in kept:
        prev = by_pitch.get(m)
        if prev is not None and s - prev[1] <= merge_gap:
            prev[1] = max(prev[1], e)          # extend in place
            prev[3] = max(prev[3], a)
            continue
        row = [s, e, m, a]
        merged.append(row)
        by_pitch[m] = row
    log(f'  cleanup: {n0} -> {len(kept)} after threshold -> {len(merged)} after merge',
        quiet)
    return [tuple(r) for r in sorted(merged)]


def events_to_score(events: list[tuple], bpm: float, monophonic: bool = False,
                    title: str = 'Transcription') -> stream.Score:
    """Note events (seconds) -> a music21 Score in quarterLength space."""
    qps = bpm / 60.0                            # quarter notes per second
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=title)
    p = stream.Part()
    p.insert(0, tempo.MetronomeMark(number=bpm))
    p.insert(0, instrument.Piano())

    if monophonic:
        # collapse to the loudest note at each onset, then forbid overlap
        events = sorted(events)
        best: dict[float, tuple] = {}
        for ev in events:
            k = round(ev[0], 4)
            if k not in best or ev[3] > best[k][3]:
                best[k] = ev
        events = sorted(best.values())
        for i, ev in enumerate(events[:-1]):
            events[i] = (ev[0], min(ev[1], events[i + 1][0]), ev[2], ev[3])

    for s, e, m, a in events:
        ql = (e - s) * qps
        if ql <= 0:
            continue
        n = note.Note(m)
        n.quarterLength = ql
        n.volume.velocity = max(1, min(127, int(a * 127)))
        p.insert(s * qps, n)
    sc.insert(0, p)
    return sc


def finalize(sc: stream.Score, divisors=(4, 3), time_signature: str | None = None,
             detect_key: bool = True, quiet: bool = False) -> stream.Score:
    """Quantize onto a grid, add meter/key, and bar the result."""
    t = time.time()
    sc.quantize(quarterLengthDivisors=divisors, processOffsets=True,
                processDurations=True, inPlace=True, recurse=True)
    log(f'  quantize{divisors}: {time.time() - t:.2f}s', quiet)

    for p in sc.parts:
        if not p.getElementsByClass(meter.TimeSignature):
            p.insert(0, meter.TimeSignature(time_signature or '4/4'))
    if detect_key:
        k = sc.analyze('key')
        log(f'  key: {k} (r={k.correlationCoefficient:.2f})', quiet)
        for p in sc.parts:
            p.insert(0, m21key.Key(k.tonic.name, k.mode))
    sc.makeNotation(inPlace=True)
    return sc


# --------------------------------------------------------------- harmony


def harmonic_reduction(sc: stream.Score, per: str = 'measure',
                       max_pitches: int = 3) -> stream.Part:
    """One chord per measure, from duration-weighted pitch-class mass.

    Chordifying a raw transcription yields thousands of one-tick verticalities;
    this collapses each bar to the pitch classes that actually sounded longest.
    """
    ch = sc.chordify()
    if not ch.getElementsByClass(stream.Measure):
        ch.makeMeasures(inPlace=True)
    k = sc.analyze('key')
    out = stream.Part(id='reduction')
    out.insert(0, m21key.Key(k.tonic.name, k.mode))
    for m in ch.getElementsByClass(stream.Measure):
        weight: dict[int, float] = {}
        for el in m.recurse().notes:
            for pp in el.pitches:
                weight[pp.pitchClass] = weight.get(pp.pitchClass, 0.0) + float(el.quarterLength)
        if not weight:
            out.append(note.Rest(quarterLength=4.0))
            continue
        top = sorted(weight, key=weight.get, reverse=True)[:max_pitches]
        c = chord.Chord(sorted(top))
        c.quarterLength = m.barDuration.quarterLength
        try:
            c.addLyric(roman.romanNumeralFromChord(c, k).figure)
        except Exception:
            pass
        out.append(c)
    return out


# ------------------------------------------------------------------- main


def build(path: str, args) -> stream.Score:
    quiet = args.quiet
    log(f'[1/5] source: {path}', quiet)

    src = path
    tmp = None
    if args.max_seconds and args.backend != 'audiosearch':
        tmp = src = decode_to_wav(path, max_seconds=args.max_seconds)

    try:
        first = pick_backend(args.backend, args.monophonic, quiet)
        # Try the chosen backend, then fall through the others. music21's own
        # audioSearch in particular raises on silence (an infinite frequency
        # reaches int()), so a hard failure here must not end the run.
        order = [first] if args.backend != 'auto' else \
            [first] + [b for b in BACKENDS if b != first]
        events, backend, errors = [], None, []
        for cand in order:
            if not _have(BACKENDS[cand][1]):     # module present?
                continue
            log(f'[2/5] transcribing with {cand}', quiet)
            try:
                events = BACKENDS[cand][0](src, quiet=quiet,
                                           max_seconds=args.max_seconds)
            except Exception as e:               # noqa: BLE001
                errors.append(f'{cand}: {type(e).__name__}: {e}')
                log(f'  {cand} failed ({type(e).__name__}) -- trying the next backend',
                    quiet)
                continue
            if events:
                backend = cand
                break
            errors.append(f'{cand}: produced no events')
        if not events:
            detail = '\n  '.join(errors) or 'no backend available'
            raise SystemExit(
                'transcription failed; nothing usable was produced.\n  ' + detail
                + '\n\nInstall a better backend:  pip install librosa'
                '  (or basic-pitch on Python <=3.12)')

        log('[3/5] cleaning events', quiet)
        events = clean_events(events, args.min_duration, args.min_amplitude,
                              args.merge_gap, quiet)

        bpm = args.tempo if args.tempo else estimate_tempo(src, quiet=quiet)

        log('[4/5] building Score', quiet)
        sc = events_to_score(events, bpm, args.monophonic,
                             title=os.path.basename(path))

        log('[5/5] quantize / key / meter', quiet)
        divisors = tuple(int(x) for x in args.quantize.split(','))
        sc = finalize(sc, divisors, args.time_signature, not args.no_key, quiet)
    finally:
        if tmp:
            os.unlink(tmp)

    if args.transpose:
        sc = sc.transpose(int(args.transpose))
    if args.reduce:
        sc.insert(0, harmonic_reduction(sc))
    elif args.chordify:
        sc.insert(0, sc.chordify())
    return sc


def summarize(sc: stream.Score) -> None:
    flat = sc.flatten()
    ns = list(flat.notes)
    print(f'parts        : {len(sc.parts)}')
    print(f'objects      : {len(ns)} notes/chords')
    if not ns:
        return
    ps = [p.midi for n in ns for p in n.pitches]
    print(f'range        : {pitch.Pitch(min(ps))} - {pitch.Pitch(max(ps))}')
    print(f'measures     : {len(sc.parts[0].getElementsByClass(stream.Measure))}')
    k = sc.analyze('key')
    print(f'key          : {k} (r={k.correlationCoefficient:.2f})')
    qls = Counter(round(float(n.quarterLength), 3) for n in ns)
    print(f'quarterLength: {qls.most_common(6)}')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='Transcribe an audio file into an editable music21 Score.',
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('audio', help='wav/mp3/flac/m4a -- anything ffmpeg can read')
    ap.add_argument('-o', '--output', help='.musicxml / .mid / .txt (default: stdout summary)')
    ap.add_argument('--backend', default='auto',
                    choices=['auto', 'basic-pitch', 'pyin', 'audiosearch'])
    ap.add_argument('--monophonic', action='store_true',
                    help='keep one note at a time (melody extraction)')
    ap.add_argument('--tempo', type=float, help='bpm; omit to estimate with librosa')
    ap.add_argument('--quantize', default='4,3',
                    help='quarterLengthDivisors, comma separated (default 4,3)')
    ap.add_argument('--time-signature', help='e.g. 3/4 (default 4/4)')
    ap.add_argument('--min-duration', type=float, default=0.05,
                    help='drop notes shorter than this many seconds')
    ap.add_argument('--min-amplitude', type=float, default=0.0,
                    help='drop notes quieter than this (0..1)')
    ap.add_argument('--merge-gap', type=float, default=0.03,
                    help='merge same-pitch notes separated by less than this')
    ap.add_argument('--max-seconds', type=float, help='only transcribe the first N seconds')
    ap.add_argument('--transpose', help='semitones to transpose the result')
    ap.add_argument('--chordify', action='store_true', help='append a chordified part')
    ap.add_argument('--reduce', action='store_true',
                    help='append a one-chord-per-bar harmonic reduction')
    ap.add_argument('--no-key', action='store_true', help='skip key detection')
    ap.add_argument('--show', action='store_true', help="print show('text')")
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    if not os.path.exists(args.audio):
        raise SystemExit(f'no such file: {args.audio}')

    t0 = time.time()
    sc = build(args.audio, args)
    log(f'done in {time.time() - t0:.1f}s', args.quiet)

    if args.output:
        fmt = ('midi' if args.output.endswith(('.mid', '.midi'))
               else 'text' if args.output.endswith('.txt') else 'musicxml')
        sc.write(fmt, fp=args.output)
        print(f'wrote {args.output}')
    if args.show:
        sc.show('text')
    if not args.output or args.show is False:
        summarize(sc)
    return 0


if __name__ == '__main__':
    sys.exit(main())
