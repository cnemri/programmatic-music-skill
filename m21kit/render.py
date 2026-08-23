"""
Score -> audio. The part music21 does not do.

``score.show('midi')`` needs a GUI; ``score.write('midi')`` gives you a file no
one can listen to without a synth. This module is the missing back end:
FluidSynth turns MIDI into audio against a General MIDI soundfont, and ffmpeg
mixes and masters it.

The important idea is **stems**. Rendering all parts in one pass leaves you no
control: a five-note rasgueado always buries a single-note melody, whatever you
do with velocity, because velocity is not level. Render one wav per voice and
balance them in dB, exactly as a mix engineer would.

    from m21kit import render
    render.score_to_mp3(score, 'out.mp3',
                        stems=[render.Stem('melody', gain_db=4),
                               render.Stem('chords', gain_db=-3, pan=-0.2),
                               render.Stem('drums',  gain_db=-6, pan=0.2)])

Requires ``fluidsynth`` and ``ffmpeg`` on PATH, plus a .sf2 soundfont.
See references/11-audio-rendering.md.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Sequence

from m21kit import midiio

__all__ = ['Stem', 'find_soundfont', 'ensure_soundfont', 'render_midi',
           'mix_stems', 'to_mp3', 'score_to_mp3', 'audio_info', 'have_tools']

SOUNDFONT_URL = 'https://github.com/urish/cinto/raw/master/media/FluidR3%20GM.sf2'
SOUNDFONT_SIZE_MB = 141

_SF_SEARCH = [
    './FluidR3_GM.sf2', './soundfont.sf2',
    '~/.local/share/soundfonts/FluidR3_GM.sf2',
    '/usr/share/sounds/sf2/FluidR3_GM.sf2',
    '/usr/share/soundfonts/FluidR3_GM.sf2',
    '/opt/homebrew/share/soundfonts/default.sf2',
    '/Library/Audio/Sounds/Banks/FluidR3_GM.sf2',
]


# ---------------------------------------------------------------------------
@dataclass
class Stem:
    """One voice in the mix.

    gain_db  level. Melody typically +3..+5, strummed chords -2..-5,
             percussion -4..-10. These are big numbers; note density matters
             far more than velocity for perceived loudness.
    pan      -1 (hard left) .. +1 (hard right). Keep a solo instrument's
             voices within +/-0.3 or it stops sounding like one instrument.
    hp       high-pass in Hz -- clears mud from anything that is not the bass.
    eq       list of (freq_hz, q, gain_db) peaking bands. A +3dB bell at
             2.5-3kHz is what makes a melody read over an accompaniment.
    reverb   0..1 FluidSynth reverb level for this stem's render pass.
    """
    name: str
    gain_db: float = 0.0
    pan: float = 0.0
    hp: float | None = 90.0
    eq: list[tuple[float, float, float]] = field(default_factory=list)
    reverb: float = 0.55
    synth_gain: float = 0.42
    echo: tuple[float, float] | None = None   # (delay_ms, decay) e.g. (900, .17)


def have_tools() -> dict[str, str | None]:
    return {'fluidsynth': shutil.which('fluidsynth'),
            'ffmpeg': shutil.which('ffmpeg'),
            'ffprobe': shutil.which('ffprobe')}


def find_soundfont(extra: Sequence[str] = ()) -> str | None:
    for c in list(extra) + _SF_SEARCH:
        p = os.path.expanduser(c)
        if os.path.isfile(p):
            return os.path.abspath(p)
    for root in ('/usr/share/soundfonts', '/usr/share/sounds/sf2',
                 '/opt/homebrew/share', os.path.expanduser('~/.local/share/soundfonts')):
        if os.path.isdir(root):
            for dirpath, _, files in os.walk(root):
                for f in files:
                    if f.lower().endswith(('.sf2', '.sf3')):
                        return os.path.join(dirpath, f)
    return None


def ensure_soundfont(dest: str = 'FluidR3_GM.sf2') -> str:
    """Return a usable soundfont, downloading FluidR3 GM (~141MB) if needed."""
    found = find_soundfont([dest])
    if found:
        return found
    print(f'downloading FluidR3 GM (~{SOUNDFONT_SIZE_MB}MB) -> {dest}')
    subprocess.run(['curl', '-sL', '--fail', '-o', dest, SOUNDFONT_URL], check=True)
    if os.path.getsize(dest) < 10_000_000:
        raise RuntimeError('soundfont download looks truncated')
    return os.path.abspath(dest)


# ---------------------------------------------------------------------------
def render_midi(midi_path: str, wav_path: str, sf2: str, gain: float = 0.42,
                reverb: float = 0.55, room: float = 0.6, damp: float = 0.4,
                width: float = 0.7, sample_rate: int = 48000,
                polyphony: int = 768, chorus: bool = False) -> str:
    """FluidSynth one MIDI file to wav.

    ``gain`` low (0.35-0.5) on purpose: headroom is free before the mix, and
    clipping in a stem can never be undone. Check the master's peak afterwards,
    not the stems'.
    """
    cmd = ['fluidsynth', '-ni', '-F', wav_path, '-r', str(sample_rate),
           '-g', str(gain), '-R', '1', '-C', '1' if chorus else '0',
           '-o', f'synth.reverb.room-size={room}',
           '-o', f'synth.reverb.damp={damp}',
           '-o', f'synth.reverb.width={width}',
           '-o', f'synth.reverb.level={reverb}',
           '-o', f'synth.polyphony={polyphony}',
           sf2, midi_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
        raise RuntimeError(f'fluidsynth produced nothing:\n{r.stdout}\n{r.stderr}')
    return wav_path


def _stem_filter(i: int, s: Stem) -> str:
    parts = [f'volume={s.gain_db}dB']
    if s.hp:
        parts.append(f'highpass=f={s.hp}')
    for f, q, g in s.eq:
        parts.append(f'equalizer=f={f}:t=q:w={q}:g={g}')
    if s.echo:
        d, dec = s.echo
        parts.append(f'aecho=0.92:0.75:{d}:{dec}')
    if abs(s.pan) > 1e-6:
        parts.append(f'stereotools=balance_out={s.pan}')
    return f'[{i}:a]' + ', '.join(parts) + f'[s{i}]'


def _measure_loudnorm(inputs: Sequence[str], graph: str, target_lufs: float,
                      true_peak: float, lra: float) -> dict | None:
    """Pass 1 of a two-pass loudnorm: measure, so pass 2 can be exact."""
    import json as _json
    cmd = ['ffmpeg', '-hide_banner', '-nostats']
    for w in inputs:
        cmd += ['-i', w]
    cmd += ['-filter_complex', graph + f',loudnorm=I={target_lufs}:TP={true_peak}'
            f':LRA={lra}:print_format=json', '-f', 'null', '-']
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    start = err.rfind('{')
    if start < 0:
        return None
    try:
        return _json.loads(err[start:err.rfind('}') + 1])
    except Exception:
        return None


def mix_stems(wavs: Sequence[str], stems: Sequence[Stem], out_wav: str,
              target_lufs: float = -14.0, true_peak: float = -1.2,
              lra: float = 11.0, comp_threshold_db: float = -18.0,
              comp_ratio: float = 2.3, fade_in: float = 0.3,
              fade_out: float = 4.0, sample_rate: int = 48000,
              two_pass: bool = True) -> str:
    """Mix rendered stems, compress gently, and normalise to a loudness target.

    ``target_lufs`` -14 is streaming-normal and right for driving music; use
    -16 with ``lra=14`` for something dynamic and quiet like a free-rhythm
    piece, so the compressor does not flatten the shape you composed.
    """
    if len(wavs) != len(stems):
        raise ValueError('wavs and stems must be the same length')
    # One ffprobe per stem. The old form called audio_info inside max()'s key
    # and then once more on the winner: n+1 subprocesses to read n numbers.
    dur = max(audio_info(w)['duration'] for w in wavs)
    fstart = max(0.0, dur - fade_out)

    chains = [_stem_filter(i, s) for i, s in enumerate(stems)]
    labels = ''.join(f'[s{i}]' for i in range(len(stems)))
    pre = (';'.join(chains) + ';'
           + f'{labels}amix=inputs={len(stems)}:duration=longest:normalize=0[m];'
           + f'[m]acompressor=threshold={comp_threshold_db}dB:ratio={comp_ratio}'
             ':attack=14:release=240:makeup=2,'
           + 'aformat=sample_fmts=fltp')

    # Single-pass loudnorm is a live estimate and routinely misses the target by
    # 1-2 LU. Measuring first and feeding the measurements back makes it exact.
    ln = f'loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}'
    if two_pass:
        m = _measure_loudnorm(wavs, pre, target_lufs, true_peak, lra)
        if m:
            ln += (f':measured_I={m["input_i"]}:measured_TP={m["input_tp"]}'
                   f':measured_LRA={m["input_lra"]}:measured_thresh={m["input_thresh"]}'
                   f':offset={m["target_offset"]}:linear=true')
    graph = (pre + ',' + ln + ','
             + f'afade=t=in:st=0:d={fade_in},'
             + f'afade=t=out:st={fstart:.3f}:d={fade_out}')

    cmd = ['ffmpeg', '-y', '-hide_banner', '-v', 'error']
    for w in wavs:
        cmd += ['-i', w]
    cmd += ['-filter_complex', graph, '-ar', str(sample_rate), '-ac', '2',
            '-c:a', 'pcm_s24le', out_wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out_wav):
        raise RuntimeError(f'ffmpeg mix failed:\n{r.stderr}')
    return out_wav


def to_mp3(wav: str, mp3: str, bitrate: str = '320k', tags: dict | None = None) -> str:
    cmd = ['ffmpeg', '-y', '-hide_banner', '-v', 'error', '-i', wav,
           '-codec:a', 'libmp3lame', '-b:a', bitrate, '-ar', '44100']
    for k, v in (tags or {}).items():
        cmd += ['-metadata', f'{k}={v}']
    cmd.append(mp3)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'ffmpeg encode failed:\n{r.stderr}')
    return mp3


def audio_info(path: str) -> dict:
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries',
         'format=duration,bit_rate,size', '-of', 'default=nw=1:nk=0', path],
        capture_output=True, text=True).stdout
    d = {}
    for line in out.strip().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            try:
                d[k] = float(v)
            except ValueError:
                d[k] = v
    d.setdefault('duration', 0.0)
    return d


# ---------------------------------------------------------------------------
def score_to_mp3(score, out_mp3: str, stems: Sequence[Stem] | None = None,
                 sf2: str | None = None, channels: Sequence[int] | None = None,
                 bends: dict[int, float] | None = None,
                 tags: dict | None = None, target_lufs: float = -14.0,
                 lra: float = 11.0, fade_out: float = 4.0,
                 workdir: str | None = None, keep: bool = False,
                 two_pass: bool = True, verbose: bool = True) -> dict:
    """The whole pipeline: music21 Score -> mastered mp3.

    One :class:`Stem` per Part, in order. Omit ``stems`` for a flat mix at unity.
    Set ``channels`` with 10 for any percussion Part. ``bends`` is
    ``{channel: cents}`` for microtonal work -- see
    :func:`m21kit.midiio.set_channel_bend`.

    Returns a dict of the paths produced and the final audio stats.
    """
    tools = have_tools()
    missing = [k for k, v in tools.items() if not v]
    if missing:
        raise RuntimeError(f'missing on PATH: {missing}. brew/apt install fluidsynth ffmpeg')
    sf2 = sf2 or ensure_soundfont()

    tmp = workdir or tempfile.mkdtemp(prefix='m21kit-')
    os.makedirs(tmp, exist_ok=True)
    parts = list(score.parts) or [score]
    if stems is None:
        stems = [Stem(name=str(p.id or f'part{i}')) for i, p in enumerate(parts)]
    if len(stems) != len(parts):
        raise ValueError(f'{len(parts)} parts but {len(stems)} stems')

    mids = midiio.write_stems(score, os.path.join(tmp, 'mid'),
                              channels=channels, bends=bends,
                              names=[s.name for s in stems])
    wavs = []
    for m, s in zip(mids, stems):
        w = os.path.join(tmp, f'{s.name}.wav')
        if verbose:
            print(f'  render {s.name}')
        render_midi(m, w, sf2, gain=s.synth_gain, reverb=s.reverb)
        wavs.append(w)

    master = os.path.join(tmp, 'master.wav')
    if verbose:
        print('  mix + master')
    mix_stems(wavs, stems, master, target_lufs=target_lufs, lra=lra,
              fade_out=fade_out, two_pass=two_pass)
    to_mp3(master, out_mp3, tags=tags)

    full_mid = os.path.join(tmp, 'full.mid')
    midiio.write_midi(score, full_mid, channels=channels, bends=bends)

    info = audio_info(out_mp3)
    if verbose:
        print(f'  -> {out_mp3}  {info["duration"]:.1f}s')
    # `keep` means keep, whether or not the caller named the workdir. Gating
    # this on `workdir is None` silently left every stem wav on disk for anyone
    # who passed one -- which is everyone who wants a reproducible build dir.
    if not keep:
        for w in wavs:
            try:
                os.remove(w)
            except OSError:
                pass
    return {'mp3': out_mp3, 'master_wav': master, 'midi': full_mid,
            'stem_midis': mids, 'workdir': tmp, **info}
