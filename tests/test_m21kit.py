#!/usr/bin/env python3
"""
Tests for m21kit. Run:  python -m pytest tests/ -q      (or just: python tests/test_m21kit.py)

The audio tests are skipped automatically when fluidsynth/ffmpeg or a soundfont
are unavailable, so the symbolic half runs anywhere.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pytest                                             # noqa: E402
from music21 import instrument, stream                    # noqa: E402
from m21kit import drums, midiio, perform, render, scales, verify   # noqa: E402


# ---------------------------------------------------------------- scales ---
def test_known_scales_are_right():
    assert scales.pitches('major', 'C4') == [60, 62, 64, 65, 67, 69, 71]
    # Maqam Hijaz on D: D Eb F# G A Bb C -- the augmented 2nd is the identity
    assert scales.pitches('hijaz', 'D4') == [62, 63, 66, 67, 69, 70, 72]
    assert scales.pitches('malkauns', 'C4') == [60, 63, 65, 68, 70]
    # flamenco == phrygian dominant == maqam hijaz, same intervals
    assert scales.SCALES['flamenco'][0] == scales.SCALES['maqam_hijaz'][0]


def test_melakarta_formula():
    assert scales.melakarta(29) == (0, 2, 4, 5, 7, 9, 11)     # major
    assert scales.melakarta(65) == (0, 2, 4, 6, 7, 9, 11)     # lydian
    assert scales.melakarta(8) == (0, 1, 3, 5, 7, 8, 10)      # todi/phrygian
    assert len([k for k in scales.SCALES if k.startswith('melakarta_')]) == 72


def test_maqam_from_ajnas():
    assert scales.build_maqam('hijaz', 'nahawand') == scales.SCALES['maqam_hijaz'][0]


def test_microtonal_detection():
    assert scales.is_microtonal('maqam_rast')
    assert not scales.is_microtonal('maqam_hijaz')
    # exact quarter tones round consistently downward by default
    assert scales.nearest_12tet('maqam_rast') == (0, 2, 3, 5, 7, 9, 10)
    assert scales.nearest_12tet('maqam_rast', 'up') == (0, 2, 4, 5, 7, 9, 11)


def test_scale_name_resolution_and_errors():
    assert scales.resolve('hijaz') == 'maqam_hijaz'
    assert scales.resolve('malkauns') == 'raga_malkauns'
    with pytest.raises(KeyError) as e:
        scales.pitches('nonexistent-scale', 'C4')
    assert 'Did you mean' in str(e.value)


def test_m21_scale_roundtrip():
    sc = scales.m21_scale('hijaz', 'D4')
    got = [p.nameWithOctave for p in sc.getPitches('D4', 'D5')]
    assert got == ['D4', 'E-4', 'F#4', 'G4', 'A4', 'B-4', 'C5', 'D5']


def test_diatonic_chord_building():
    assert scales.degrees_to_chord('major', 'C4', 5, size=4) == [67, 71, 74, 77]  # G7
    assert scales.degrees_to_chord('major', 'C4', 1, size=3) == [60, 64, 67]      # C


# ----------------------------------------------------------------- drums ---
def test_gm_map_and_grooves():
    assert drums.GM['kick'] == 36 and drums.GM['snare'] == 38
    assert drums.GM['hand_clap'] == 39 and drums.GM['side_stick'] == 37
    assert len(drums.GROOVES) >= 30
    for name, g in drums.GROOVES.items():
        assert g['hits'], f'{name} has no hits'
        span = g['bar'] * g['bars']
        for off, key, scal in g['hits']:
            assert 0 <= off < span + 1e-6, f'{name}: hit at {off} outside {span}'
            assert 0 < scal <= 1.0, f'{name}: bad velocity scalar {scal}'
            assert drums._k(key) in range(27, 88), f'{name}: {key} not a GM drum key'


def test_groove_places_notes():
    p = stream.Part()
    end = drums.groove(p, 0.0, 'rock_basic', vel=80, repeats=2)
    assert end == 8.0
    assert len(p.flatten().notes) == 2 * len(drums.GROOVES['rock_basic']['hits'])


def test_groove_filtering():
    p = stream.Part()
    drums.groove(p, 0.0, 'tangos_flamencos', only=['hand_clap'])
    keys = {n.pitch.midi for n in p.flatten().notes}
    assert keys == {drums.GM['hand_clap']}


# --------------------------------------------------------------- perform ---
def test_strum_is_spread_in_time_and_ordered():
    p = stream.Part()
    perform.strum(p, 4.0, [40, 47, 52, 56], dur=1.0, vel=90, spread=0.04, jitter=0)
    ns = sorted(p.flatten().notes, key=lambda n: n.offset)
    assert [n.pitch.midi for n in ns] == [40, 47, 52, 56]        # low to high
    assert abs(float(ns[-1].offset) - 4.12) < 1e-6               # 3 * 0.04
    assert ns[0].quarterLength > ns[-1].quarterLength            # first rings longest


def test_upstrum_reverses():
    p = stream.Part()
    perform.strum(p, 0.0, [40, 47, 52], dur=0.5, vel=80, up=True, jitter=0)
    ns = sorted(p.flatten().notes, key=lambda n: n.offset)
    assert [n.pitch.midi for n in ns] == [52, 47, 40]


def test_tremolo_repeats_and_shapes():
    p = stream.Part()
    perform.tremolo(p, 0.0, 72, dur=1.0, vel=80, rate=0.1, jitter=0)
    ns = list(p.flatten().notes)
    assert 9 <= len(ns) <= 11
    assert all(n.pitch.midi == 72 for n in ns)
    assert len({n.volume.velocity for n in ns}) > 3        # it breathes


def test_swing_moves_offbeats_only():
    p = stream.Part()
    for i in range(4):
        perform.put(p, i * 0.5, 60, 0.5, 80, jitter=0)
    perform.swing(p, ratio=0.667, unit=0.5)
    offs = sorted(round(float(n.offset), 3) for n in p.flatten().notes)
    assert offs[0] == 0.0 and offs[2] == 1.0               # downbeats unmoved
    assert abs(offs[1] - 0.667) < 0.01                     # offbeats pushed late


def test_crescendo_ramps_velocity():
    p = stream.Part()
    for i in range(9):
        perform.put(p, float(i), 60, 1.0, 64, jitter=0)
    perform.crescendo(p, 0, 8, 40, 120)
    ns = sorted(p.flatten().notes, key=lambda n: n.offset)
    assert ns[0].volume.velocity == 40 and ns[-1].volume.velocity == 120
    assert ns[4].volume.velocity == 80


# ---------------------------------------------------------------- midiio ---
def test_tempo_map_math():
    tm = midiio.TempoMap([(0, 60), (8, 120)])
    assert tm.seconds(8) == 8.0
    assert tm.seconds(16) == 12.0
    assert abs(tm.offset(12.0) - 16.0) < 1e-6
    assert tm.bpm_at(0) == 60 and tm.bpm_at(10) == 120


def _tiny_score():
    a = stream.Part(id='a'); b = stream.Part(id='b'); d = stream.Part(id='d')
    for p in (a, b):
        i = instrument.AcousticGuitar(); i.midiProgram = 24; p.insert(0, i)
    midiio.add_tempo_map([a, b, d], [(0, 120)])
    for t in range(4):
        perform.put(a, float(t), 60 + t, 0.9, 90)
        perform.strum(b, float(t), [48, 55, 60], 0.9, 80)
        drums.groove(d, t * 1.0, 'tresillo', vel=80)
    s = stream.Score()
    for p in (a, b, d):
        s.insert(0, p)
    return s


def test_channels_are_not_folded():
    """The bug this whole package exists for: two Parts with the same
    instrument otherwise land on one channel and cut each other off."""
    sc = _tiny_score()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 't.mid')
        midiio.write_midi(sc, path, channels=[1, 2, 10])
        tracks = midiio.describe_midi(path)
        note_tracks = [t for t in tracks if t['notes']]
        assert len(note_tracks) == 3
        used = [c for t in note_tracks for c in t['channels']]
        assert sorted(used) == [1, 2, 10], f'channel folding: {used}'


def test_percussion_track_has_no_program_change():
    sc = _tiny_score()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 't.mid')
        midiio.write_midi(sc, path, channels=[1, 2, 10])
        perc = [t for t in midiio.describe_midi(path) if 10 in t['channels']]
        assert perc and perc[0]['programs'] == []


def test_stems_are_one_part_each():
    sc = _tiny_score()
    with tempfile.TemporaryDirectory() as td:
        paths = midiio.write_stems(sc, td, channels=[1, 2, 10],
                                   names=['a', 'b', 'd'])
        assert len(paths) == 3
        for p, ch in zip(paths, (1, 2, 10)):
            nt = [t for t in midiio.describe_midi(p) if t['notes']]
            assert len(nt) == 1 and nt[0]['channels'] == [ch]


# ---------------------------------------------------------------- verify ---
def test_outside_mode_finds_the_wrong_note():
    p = stream.Part()
    for m in [60, 62, 64, 65, 67, 69, 71]:      # C major
        perform.put(p, 0, m, 1, 80, jitter=0)
    perform.put(p, 8, 61, 1, 80, jitter=0)      # a C# that should not be there
    r = verify.outside_mode(p, [x % 12 for x in scales.pitches('major', 'C4')])
    assert r['outside'] == {'C#': 1}
    assert r['outside_count'] == 1


def test_range_check_catches_subrange_notes():
    p = stream.Part()
    perform.put(p, 0, 33, 1, 80, jitter=0)      # A1 -- below a guitar's low E
    perform.put(p, 1, 60, 1, 80, jitter=0)
    r = verify.range_check(p, instrument.AcousticGuitar())
    if r['checked']:
        assert r['out_of_range'] >= 1
    r2 = verify.range_check(p, low=40, high=88)
    assert r2['out_of_range'] == 1 and r2['examples'][0]['midi'] == 33


def test_pitched_parts_drops_percussion():
    sc = _tiny_score()
    assert len(sc.parts) == 3
    assert len(verify.pitched_parts(sc).parts) == 2


def test_rhythm_report_flags_a_grid():
    p = stream.Part()
    for i in range(16):
        perform.put(p, float(i), 60, 1.0, 80, jitter=0)     # identical everything
    r = verify.rhythm_report(p)
    assert r['distinct_durations'] == 1
    assert r['velocity_distinct'] == 1
    assert r['offset_grid_pct'] == 100.0


def test_melody_match_pitch_sequence():
    p = stream.Part()
    for i, m in enumerate([64, 69, 71, 72, 69]):
        perform.put(p, float(i), m, 1, 80, jitter=0)
    assert verify.melody_match(p, [64, 69, 71, 72, 69])['pct'] == 100.0
    assert verify.melody_match(p, [64, 69, 99, 72, 69])['pct'] == 80.0


# ----------------------------------------------------------------- audio ---
_tools = render.have_tools()
_sf = render.find_soundfont(['/tmp/sf.sf2'])
audio_ok = all(_tools.values()) and _sf
skip_audio = pytest.mark.skipif(not audio_ok,
                                reason='needs fluidsynth, ffmpeg and a soundfont')


@skip_audio
def test_end_to_end_render_and_measure():
    sc = _tiny_score()
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'x.mp3')
        render.score_to_mp3(sc, out, sf2=_sf, channels=[1, 2, 10],
                            workdir=td, verbose=False,
                            stems=[render.Stem('a', 3), render.Stem('b', -3),
                                   render.Stem('d', -6)])
        st = verify.audio_stats(out)
        assert st['duration_s'] > 1
        assert not st['clipped']
        assert st['peak_dbfs'] < -0.5


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))


# ------------------------------------------------- library behaviour guards ---
def test_dynamic_rescales_explicit_velocity():
    """Regression guard for the trap documented in SKILL.md rule 3: a Dynamic
    multiplies velocities you set yourself rather than deferring to them."""
    from music21 import dynamics, midi, note as m21note

    def vels(part):
        s = stream.Score(); s.insert(0, part)
        mf = midi.translate.streamToMidiFile(s)
        return [e.velocity for t in mf.tracks for e in t.events
                if e.type == midi.ChannelVoiceMessages.NOTE_ON and e.velocity]

    plain = stream.Part()
    plain.insert(0, m21note.Note('C4', quarterLength=1))
    assert vels(plain) == [90], 'music21 default velocity is 90, not 64 or 127'

    quiet = stream.Part()
    quiet.insert(0, dynamics.Dynamic('pp'))
    n = m21note.Note('C4', quarterLength=1)
    n.volume.velocity = 100
    quiet.insert(0, n)
    assert vels(quiet) == [50], 'a Dynamic scales an explicit velocity'

    hairpin = stream.Part()
    ns = [m21note.Note('C4', quarterLength=1) for _ in range(3)]
    for i, x in enumerate(ns):
        hairpin.insert(i, x)
    hairpin.insert(0, dynamics.Crescendo(ns[0], ns[-1]))
    assert vels(hairpin) == [90, 90, 90], 'hairpins do not affect MIDI at all'


# ------------------------------------------------- regressions: verify ---
def test_chord_root_pc_handles_flats_and_any_suffix():
    # Flats used to be unrepresentable: the template table is spelled with
    # sharps, so an expected 'Eb' could never match a detected 'D#'.
    assert verify.chord_root_pc('Eb') == verify.chord_root_pc('D#') == 3
    assert verify.chord_root_pc('Bb') == verify.chord_root_pc('A#') == 10
    assert verify.chord_root_pc('Cb') == 11 and verify.chord_root_pc('B#') == 0
    # The suffix is ignored, whatever it is. The old rstrip('m7dim') read
    # 'Cmaj7' as 'Cmaj' and 'Gsus4' as 'Gsus4', neither of which can equal a
    # detected root, so both scored zero in silence.
    for name, pc in [('C', 0), ('Cm', 0), ('C7', 0), ('Cdim', 0), ('Cmaj7', 0),
                     ('Cm6', 0), ('Csus4', 0), ('Cadd9', 0), ('Cm7b5', 0),
                     ('F#m7b5', 6), ('Abmaj7', 8)]:
        assert verify.chord_root_pc(name) == pc, name
    assert verify.chord_root_pc('H7') is None
    assert verify.chord_root_pc('') is None


def test_harmony_match_reports_unparsable_names():
    rows = [(0.0, 1.0, 'not-a-chord')]
    out = verify.harmony_match(_silence_wav(), rows)
    assert out['unparsed_names'] == ['not-a-chord']


def _silence_wav():
    """A short silent wav, for checks that must not depend on a soundfont."""
    import struct
    import wave as _wave
    path = os.path.join(tempfile.mkdtemp(), 'silence.wav')
    with _wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(struct.pack('<' + 'h' * 22050, *([0] * 22050)))
    return path


def test_silent_segment_is_reported_not_guessed():
    out = verify.harmony_match(_silence_wav(), [(0.0, 1.0, 'Cm')])
    assert out['rows'][0]['detected'] is None
    assert out['rows'][0]['note'] == 'silent segment'
    assert out['root_matches'] == 0


def test_decode_cache_avoids_redecoding_the_same_file():
    path = _silence_wav()
    calls = []
    real = verify._decode

    def counting(p, sr=22050):
        calls.append(p)
        return real(p, sr)

    verify._decode = counting
    verify._DECODE_CACHE.clear()
    try:
        for i in range(8):
            verify.chroma(path, 0.0, 0.5)
        assert len(calls) == 1, f'decoded {len(calls)} times, expected 1'
    finally:
        verify._decode = real
        verify._DECODE_CACHE.clear()


# ------------------------------------------------- regressions: midiio ---
def test_default_channels_skips_ten_and_refuses_to_overflow():
    assert midiio.default_channels(3) == [1, 2, 3]
    assert midiio.default_channels(11) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12]
    assert midiio.default_channels(15)[-1] == 16
    # Sixteen melodic parts do not fit. This used to hand back channel 17.
    with pytest.raises(ValueError, match='melodic MIDI channels'):
        midiio.default_channels(16)


def test_retrack_rejects_channels_outside_1_16():
    from music21 import note as m21note
    sc = stream.Score()
    p = stream.Part(id='p')
    p.insert(0, m21note.Note('C4', quarterLength=1))
    sc.insert(0, p)
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError, match='must be 1-16'):
            midiio.write_midi(sc, os.path.join(d, 'x.mid'), channels=[17])
        with pytest.raises(ValueError, match='must be 1-16'):
            midiio.write_midi(sc, os.path.join(d, 'x.mid'), channels=[0])


# -------------------------------------------------- regressions: drums ---
def test_groove_fill_respects_only_and_skip():
    from music21 import stream as _s
    keys = lambda p: sorted({int(n.pitch.midi) for n in p.notes})

    # rock_basic has no hand_clap at all, so only=['hand_clap'] must be silent.
    # The fill used to ignore the filter and emit snares -- the sole output was
    # the one instrument the caller had excluded.
    p = _s.Part()
    drums.groove(p, 0, 'rock_basic', only=['hand_clap'], fill=True)
    assert keys(p) == []

    p = _s.Part()
    drums.groove(p, 0, 'rock_basic', skip=['snare'], fill=True)
    assert drums.GM['snare'] not in keys(p)

    # ...and an unfiltered fill still fills.
    p = _s.Part()
    drums.groove(p, 0, 'rock_basic', fill=True)
    assert drums.GM['snare'] in keys(p)


def test_every_groove_is_internally_consistent():
    """Hits must fit the cycle, and the bar length must match the meter."""
    from fractions import Fraction
    for name, g in drums.GROOVES.items():
        span = g['bar'] * g['bars']
        offs = [o for o, _, _ in g['hits']]
        assert min(offs) >= 0, name
        assert max(offs) < span, f'{name}: hit at {max(offs)} outside {span}'
        if '/' in g['meter']:
            num, den = g['meter'].split('/')
            implied = float(Fraction(int(num) * 4, int(den)))
            assert abs(implied - g['bar']) < 1e-9, \
                f"{name}: bar {g['bar']} but meter {g['meter']} implies {implied}"


# ------------------------------------------------ regressions: scripts ---
def _load_script(stem):
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'scripts', f'{stem}.py')
    spec = importlib.util.spec_from_file_location(stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_analyze_score_reads_tempo_offsets_from_the_hierarchy():
    """A tempo map must not collapse onto bar 1.

    `mm.offset` is the offset inside the mark's immediate container. Once a
    score has measures that container is a Measure, so every mark on a barline
    reads 0.0 and the whole map lands on the downbeat.
    """
    from music21 import note as m21note
    analyze = _load_script('analyze_score')
    sc = stream.Score()
    p = stream.Part()
    for i in range(4):
        p.insert(i * 4.0, m21note.Note('C4', quarterLength=4))
    midiio.add_tempo_map([p], [(0.0, 60), (4.0, 90), (8.0, 120), (12.0, 150)])
    p.makeMeasures(inPlace=True)          # this is what breaks mm.offset
    sc.insert(0, p)
    got = [(t['offset'], t['bpm']) for t in analyze.tempos(sc)]
    assert got == [(0.0, 60.0), (4.0, 90.0), (8.0, 120.0), (12.0, 150.0)], got


def test_check_ranges_does_not_double_report_parts_sharing_a_name():
    """Violations were matched to parts by NAME, so duplicate names each
    printed the other's and the listing did not add up to the total."""
    import subprocess
    from music21 import note as m21note
    sc = stream.Score()
    for _ in range(2):
        p = stream.Part()
        p.partName = 'Acoustic Guitar'          # deliberately the same name
        p.insert(0, instrument.AcousticGuitar())
        p.insert(0, m21note.Note('C2', quarterLength=1))   # below E2
        sc.insert(0, p)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 's.musicxml')
        sc.write('musicxml', fp=path)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'scripts', 'check_ranges.py')
        out = subprocess.run([sys.executable, script, path],
                             capture_output=True, text=True).stdout
    listed = sum(1 for ln in out.splitlines() if 'semitone(s)' in ln)
    total = int([ln for ln in out.splitlines()
                 if 'out of range' in ln][0].split()[0])
    assert listed == total == 2, f'listed {listed}, total {total}\n{out}'


# ------------------------------------- regressions: microtonal pitch bend ---
def _microtone_score():
    """A plain note and a quarter-flat sounding together -- music21 puts the
    second on its own channel so the bend does not touch the first."""
    from music21 import note as m21note
    p = stream.Part()
    p.insert(0, instrument.Flute())
    p.insert(0, m21note.Rest(quarterLength=1))
    p.insert(1, m21note.Note('C4', quarterLength=1))
    p.insert(1, m21note.Note('E`4', quarterLength=1))
    sc = stream.Score()
    sc.insert(0, p)
    return sc


def test_retrack_refuses_to_flatten_a_microtone_spill():
    """Collapsing those two channels applies the -50c bend to the plain C4 and
    cancels it under the quarter tone. Silent detuning; refuse instead."""
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError, match='microtonal pitch-bend spill'):
            midiio.write_midi(_microtone_score(), os.path.join(d, 'a.mid'),
                              channels=[1])
        # explicit opt-in still works, for callers who know the bends agree
        midiio.write_midi(_microtone_score(), os.path.join(d, 'b.mid'),
                          channels=[1], allow_microtone_collapse=True)


def test_set_channel_bend_pins_the_channel():
    """A constant channel detuning is how you play a maqam: the quarter-flat
    degree is written as its natural and the channel is held at -50 cents."""
    from music21 import midi as m21midi
    from music21 import note as m21note
    p = stream.Part()
    p.insert(0, instrument.Flute())
    p.insert(0, m21note.Note('E4', quarterLength=2))
    p.insert(2, m21note.Note('B4', quarterLength=2))
    sc = stream.Score()
    sc.insert(0, p)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'bent.mid')
        midiio.write_midi(sc, path, channels=[3], bends={3: -50})
        mf = m21midi.MidiFile()
        mf.open(path)
        mf.read()
        mf.close()

    CVM = m21midi.ChannelVoiceMessages
    evs = [e for t in mf.tracks for e in t.events]
    bends = [e.parameter2 for e in evs if e.type == CVM.PITCH_BEND]
    # 8192 - (50/200)*8192 = 6144 -> MSB 48. Every bend on the channel must be
    # that value: music21 appends a neutral one at offset 0 that would
    # otherwise cancel ours (translate.py:1699-1715).
    assert bends and set(bends) == {48}, bends
    # RPN 0 pins the bend range, which music21 never emits
    cc = [(e.parameter1, e.parameter2) for e in evs
          if e.type == CVM.CONTROLLER_CHANGE]
    assert (101, 0) in cc and (100, 0) in cc and (6, 2) in cc, cc


def test_samai_and_yuruk_grooves_match_their_iqa():
    """The two cycles the samai / muwashshah repertoire is built on."""
    thaqil = drums.GROOVES['samai_thaqil']
    assert thaqil['meter'] == '10/8' and thaqil['bar'] == 5.0
    strong = sorted(o for o, k, _ in thaqil['hits'] if k != 'darbuka_ka')
    # D . . T . D D T . .  -> beats 1, 4, 6, 7, 8 of ten eighths
    assert strong == [0.0, 1.5, 2.5, 3.0, 3.5], strong

    yuruk = drums.GROOVES['yuruk_samai']
    assert yuruk['meter'] == '6/8' and yuruk['bar'] == 3.0
    strong = sorted(o for o, k, _ in yuruk['hits'] if k != 'darbuka_ka')
    assert strong == [0.0, 1.5, 2.5], strong


# ------------------------------------------- regressions: cycle detection ---
@skip_audio
def test_cycle_finds_a_long_iqa_that_pulse_cannot():
    """`pulse` searches 0.27-1.33s because it is hunting a beat. A samai
    thaqil cycle is ten eighths with strokes on five of them, so at any real
    tempo it is 4-6 seconds long and falls entirely outside that window."""
    from music21 import tempo as m21tempo
    perc = stream.Part()
    drums.mark_percussion(perc)
    perc.insert(0, m21tempo.MetronomeMark(number=72))
    for b in range(14):                       # 14 cycles of samai thaqil
        drums.groove(perc, b * 5.0, 'samai_thaqil', vel=100)
    sc = stream.Score()
    sc.insert(0, perc)

    with tempfile.TemporaryDirectory() as td:
        mid = os.path.join(td, 'c.mid')
        wav = os.path.join(td, 'c.wav')
        midiio.write_midi(sc, mid, channels=[10])
        render.render_midi(mid, wav, _sf, gain=0.7, reverb=0.0)

        want = 5.0 * 60.0 / 72.0              # 4.167 s per cycle
        got = verify.cycle(wav, 1.0, 50.0, 3.0, 6.0)
        assert abs(got['period_s'] - want) < 0.15, (got, want)
        assert got['metered'] and got['strength'] > 0.25, got

        # the same cycle is invisible to pulse(): its window stops at 1.33s
        beat = verify.pulse(wav, 1.0, 50.0)
        assert beat['period_s'] < 1.4


@skip_audio
def test_cycle_reports_free_rhythm_as_unmetred():
    """The point of the strength number: proving a taqsim really is free."""
    import random as _r
    rng = _r.Random(3)
    p = stream.Part()
    p.insert(0, instrument.Flute())
    t = 0.0
    while t < 40.0:                            # deliberately irregular
        d = rng.uniform(1.2, 3.4)
        perform.put(p, t, rng.choice([60, 62, 64, 65, 67]), d * 0.9, 80)
        t += d
    sc = stream.Score()
    sc.insert(0, p)
    with tempfile.TemporaryDirectory() as td:
        mid, wav = os.path.join(td, 'f.mid'), os.path.join(td, 'f.wav')
        midiio.write_midi(sc, mid, channels=[1])
        render.render_midi(mid, wav, _sf, gain=0.7, reverb=0.0)
        got = verify.cycle(wav, 1.0, 38.0, 3.0, 6.0)
        assert not got['metered'], got
