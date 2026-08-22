"""
General MIDI percussion, and a library of real grooves.

Two things here:

* :data:`GM` -- the complete General MIDI percussion key map, by name. Channel
  10 ignores pitch and treats the key number as an instrument selector, so
  ``GM['side_stick']`` is 37 and that is a rim click on every GM device.
* :data:`GROOVES` -- rhythm patterns from a range of traditions, written as
  ``(offset_in_quarter_lengths, key, velocity_scalar)``. These are the part
  that is genuinely hard to get right from first principles: a bulería is not
  a 4/4 with accents moved, and a maqsum is not a rock beat with congas.

Percussion **must** be written to MIDI channel 10 or it plays as a piano.
See :func:`m21kit.midiio.retrack` -- pass 10 for the percussion part's channel.

    from music21 import stream
    from m21kit import drums
    p = stream.Part(id='perc')
    for b in range(8):
        drums.groove(p, b * 4.0, 'tangos_flamencos', vel=82)
"""

from __future__ import annotations

import random
from typing import Sequence

from music21 import duration, note, stream

__all__ = ['GM', 'GM_NAMES', 'GROOVES', 'groove', 'hit', 'list_grooves',
           'clave', 'mark_percussion']

# ---------------------------------------------------------------------------
# The General MIDI percussion map (channel 10). Keys 35-81 are GM Level 1;
# 27-34 and 82-87 are the GM2 / Roland GS extensions that FluidR3 and most
# modern soundfonts also provide.
# ---------------------------------------------------------------------------
GM = {
    # GM2 extensions (low)
    'high_q': 27, 'slap': 28, 'scratch_push': 29, 'scratch_pull': 30,
    'sticks': 31, 'square_click': 32, 'metronome_click': 33, 'metronome_bell': 34,
    # GM Level 1
    'acoustic_bass_drum': 35, 'bass_drum': 36, 'kick': 36,
    'side_stick': 37, 'rimshot': 37, 'golpe': 37,
    'acoustic_snare': 38, 'snare': 38,
    'hand_clap': 39, 'palmas': 39,
    'electric_snare': 40,
    'low_floor_tom': 41, 'closed_hihat': 42, 'high_floor_tom': 43,
    'pedal_hihat': 44, 'low_tom': 45, 'open_hihat': 46,
    'low_mid_tom': 47, 'hi_mid_tom': 48, 'crash': 49, 'crash_1': 49,
    'high_tom': 50, 'ride': 51, 'ride_1': 51, 'chinese_cymbal': 52,
    'ride_bell': 53, 'tambourine': 54, 'splash': 55, 'cowbell': 56,
    'crash_2': 57, 'vibraslap': 58, 'ride_2': 59,
    'hi_bongo': 60, 'low_bongo': 61,
    'mute_hi_conga': 62, 'open_hi_conga': 63, 'low_conga': 64,
    'high_timbale': 65, 'low_timbale': 66,
    'high_agogo': 67, 'low_agogo': 68,
    'cabasa': 69, 'maracas': 70,
    'short_whistle': 71, 'long_whistle': 72,
    'short_guiro': 73, 'long_guiro': 74,
    'claves': 75, 'hi_wood_block': 76, 'low_wood_block': 77,
    'mute_cuica': 78, 'open_cuica': 79,
    'mute_triangle': 80, 'open_triangle': 81,
    # GM2 extensions (high)
    'shaker': 82, 'jingle_bell': 83, 'belltree': 84, 'castanets': 85,
    'mute_surdo': 86, 'open_surdo': 87,
}

#: Reverse lookup, first canonical name wins.
GM_NAMES = {}
for _k, _v in GM.items():
    GM_NAMES.setdefault(_v, _k)

# Handy aliases for traditions GM never anticipated. A cajón is not in GM; the
# congas are the closest usable stand-in and are what everyone uses.
GM['cajon_bass'] = GM['low_conga']
GM['cajon_slap'] = GM['open_hi_conga']
GM['cajon_ghost'] = GM['mute_hi_conga']
GM['palmas_sordas'] = GM['shaker']      # muffled claps read better as a shaker
GM['darbuka_dum'] = GM['low_conga']
GM['darbuka_tek'] = GM['mute_hi_conga']
GM['darbuka_ka'] = GM['hi_bongo']
GM['tabla_na'] = GM['mute_hi_conga']
GM['tabla_ge'] = GM['low_conga']
GM['tabla_tin'] = GM['hi_bongo']


def _k(key) -> int:
    """Accept a key number or a GM name."""
    if isinstance(key, str):
        return GM[key]
    return int(key)


def mark_percussion(part: stream.Stream) -> stream.Stream:
    """Tag a Part as percussion so analysis tools skip it.

    Drum "pitches" are GM key numbers -- 38 is a snare, not a D2 -- so a drum
    part silently poisons any key or mode analysis. hit() tags automatically;
    call this yourself if you write drum notes by hand.
    """
    part.m21kit_percussion = True
    return part


def hit(part: stream.Stream, offset: float, key, vel: float = 80,
        dur: float = 0.25, jitter: float = 0.006) -> None:
    """One percussion stroke. Tags the part as percussion on first use."""
    if not getattr(part, 'm21kit_percussion', False):
        mark_percussion(part)
    n = note.Note(_k(key))
    n.duration = duration.Duration(quarterLength=dur)
    n.volume.velocity = max(1, min(127, int(round(vel))))
    part.insert(max(0.0, float(offset) + random.uniform(-jitter, jitter)), n)


# ---------------------------------------------------------------------------
# Grooves. Each entry: bar length in quarter-lengths, pattern length in bars,
# and hits as (offset_ql_from_pattern_start, key, velocity_scalar 0..1).
# ---------------------------------------------------------------------------
def _g(about, barlen, bars, hits, meter='4/4'):
    return {'about': about, 'bar': barlen, 'bars': bars, 'hits': hits,
            'meter': meter}


K, S, HH, OH, RD, CR = 'kick', 'snare', 'closed_hihat', 'open_hihat', 'ride', 'crash'
SS, CP, TM = 'side_stick', 'hand_clap', 'tambourine'

GROOVES: dict[str, dict] = {

    # ---------------- rock / pop / funk ----------------
    'rock_basic': _g(
        'The default backbeat: kick 1 and 3, snare 2 and 4, eighth hats.',
        4.0, 1,
        [(0, K, 1.0), (2, K, .95), (1, S, 1.0), (3, S, 1.0)]
        + [(i * .5, HH, .55 if i % 2 else .7) for i in range(8)]),

    'rock_16': _g(
        'Sixteenth hats, syncopated kick. Busier, drives harder.',
        4.0, 1,
        [(0, K, 1.0), (1.5, K, .85), (2.5, K, .9), (1, S, 1.0), (3, S, 1.0)]
        + [(i * .25, HH, .68 if i % 4 == 0 else (.5 if i % 2 else .58))
           for i in range(16)]),

    'funk_16': _g(
        'Ghost-note funk: the sixteenth snares between the backbeats are the '
        'whole point, and they must be much quieter than the backbeat.',
        4.0, 1,
        [(0, K, 1.0), (0.75, K, .8), (2.5, K, .9), (3.25, K, .75),
         (1, S, 1.0), (3, S, 1.0),
         (0.5, S, .25), (1.75, S, .3), (2.25, S, .22), (3.75, S, .28)]
        + [(i * .25, HH, .62 if i % 4 == 0 else .42) for i in range(16)]),

    'disco': _g(
        'Four on the floor with the hat opening on every offbeat.',
        4.0, 1,
        [(i, K, 1.0) for i in range(4)] + [(1, S, .95), (3, S, .95)]
        + [(i * .5, OH if i % 2 else HH, .6) for i in range(8)]),

    'half_time': _g(
        'Backbeat on 3 only. Instantly makes anything feel twice as slow.',
        4.0, 1,
        [(0, K, 1.0), (1.5, K, .8), (2, S, 1.0)]
        + [(i * .5, HH, .55) for i in range(8)]),

    'boom_bap': _g(
        'Hip-hop: laid-back kick, hard snare, swung-ish hats.',
        4.0, 1,
        [(0, K, 1.0), (0.75, K, .7), (2.25, K, .9),
         (1, S, 1.0), (3, S, 1.0)]
        + [(i * .5, HH, .6 if i % 2 == 0 else .4) for i in range(8)]),

    'march': _g('Duple military march.', 4.0, 1,
                [(0, K, 1.0), (2, K, .9), (1, S, .8), (3, S, .8),
                 (1.5, S, .4), (1.75, S, .4), (3.5, S, .4), (3.75, S, .45)]),

    # ---------------- swing / jazz ----------------
    'jazz_swing': _g(
        'Ride "ding, ding-a-ding", hats closing on 2 and 4. Apply '
        'perform.swing() or place the triplet offbeats at 2/3.',
        4.0, 1,
        [(0, RD, .85), (1, RD, .8), (1 + 2 / 3, RD, .6),
         (2, RD, .85), (3, RD, .8), (3 + 2 / 3, RD, .6),
         (1, 'pedal_hihat', .55), (3, 'pedal_hihat', .55),
         (0, K, .35), (2, K, .3)]),

    'jazz_waltz': _g('3/4 jazz: ride in a lilting three.', 3.0, 1,
                     [(0, RD, .85), (1, RD, .6), (1 + 2 / 3, RD, .5),
                      (2, RD, .7), (2 + 2 / 3, RD, .5),
                      (1, 'pedal_hihat', .5)], meter='3/4'),

    'shuffle': _g('Triplet shuffle, blues and boogie.', 4.0, 1,
                  [(0, K, 1.0), (2, K, .95), (1, S, 1.0), (3, S, 1.0)]
                  + [(b + o, HH, .65 if o == 0 else .45)
                     for b in range(4) for o in (0, 2 / 3)]),

    # ---------------- Afro-Cuban / Brazilian ----------------
    'clave_son_32': _g(
        'Son clave, 3-2. Two bars: three strokes then two. The organising '
        'cell of most Cuban music -- everything else is felt against it.',
        4.0, 2, [(0, 'claves', 1.0), (1.5, 'claves', .9), (3, 'claves', .95),
                 (5, 'claves', 1.0), (6, 'claves', .95)]),

    'clave_rumba_32': _g(
        'Rumba clave, 3-2. Differs from son only in the third stroke, which '
        'falls on the "and" of 4 instead of on 4 -- and changes everything.',
        4.0, 2, [(0, 'claves', 1.0), (1.5, 'claves', .9), (3.5, 'claves', .95),
                 (5, 'claves', 1.0), (6, 'claves', .95)]),

    'tresillo': _g(
        'The 3+3+2 cell. Underlies habanera, reggaeton, rumba flamenca, and '
        'half of popular music worldwide.',
        4.0, 1, [(0, K, 1.0), (1.5, K, .9), (3, K, .95)]),

    'bossa_nova': _g('Side-stick bossa pattern with a soft kick and shaker.',
                     4.0, 2,
                     [(0, SS, .85), (1.5, SS, .8), (3, SS, .85),
                      (5, SS, .85), (6, SS, .8),
                      (0, K, .8), (1.5, K, .6), (4, K, .8), (5.5, K, .6)]
                     + [(i * .5, 'shaker', .4) for i in range(16)]),

    'samba': _g('Surdo on 2, agogo and shaker sixteenths.', 4.0, 2,
                [(1, 'open_surdo', 1.0), (3, 'mute_surdo', .7),
                 (5, 'open_surdo', 1.0), (7, 'mute_surdo', .7)]
                + [(i * .25, 'shaker', .45 if i % 2 else .6) for i in range(32)]
                + [(0, 'high_agogo', .7), (1.5, 'low_agogo', .6),
                   (3, 'high_agogo', .7), (4.5, 'low_agogo', .6)]),

    'reggae_one_drop': _g('Nothing on 1. Kick and snare together on 3.',
                          4.0, 1,
                          [(2, K, 1.0), (2, S, .95), (1, SS, .45), (3, SS, .45)]
                          + [(i * .5 + .5, HH, .5) for i in range(0, 7, 2)]),

    'reggaeton': _g('Dembow: kick on the tresillo, snare answering off it.',
                    4.0, 1,
                    [(0, K, 1.0), (1.5, K, .9), (3, K, .9),
                     (0.75, S, .85), (1.75, S, .9), (2.75, S, .85), (3.75, S, .9)]
                    + [(i * .5, HH, .4) for i in range(8)]),

    'cumbia': _g('Guiro and cowbell over a two-beat.', 4.0, 1,
                 [(0, K, 1.0), (2, K, .9), (1, S, .8), (3, S, .85),
                  (0, 'long_guiro', .6), (1, 'short_guiro', .5),
                  (2, 'long_guiro', .6), (3, 'short_guiro', .5)]),

    'afro_68': _g('The standard 6/8 bell pattern of West Africa and its '
                  'diaspora. Seven strokes across twelve eighths.',
                  3.0, 2,
                  [(0, 'cowbell', 1.0), (0.5, 'cowbell', .7), (1.5, 'cowbell', .85),
                   (2, 'cowbell', .7), (3, 'cowbell', .9), (4, 'cowbell', .7),
                   (4.5, 'cowbell', .8)], meter='6/8'),

    # ---------------- flamenco ----------------
    'tangos_flamencos': _g(
        'Tangos: beat 1 is ghosted, 2 3 and 4 drive. Palmas in eighths, '
        'golpe (soundboard knock) on 2 and 4.',
        4.0, 1,
        [(0, 'cajon_bass', .7), (1, 'cajon_bass', 1.0),
         (2, 'cajon_slap', .9), (2.5, 'cajon_bass', .75),
         (3, 'cajon_slap', .95),
         (0.5, 'cajon_ghost', .4), (1.5, 'cajon_ghost', .4), (3.5, 'cajon_ghost', .4),
         (1, 'golpe', .8), (3, 'golpe', .85)]
        + [(i * .5, CP, (.9 if i * .5 in (1, 2, 3) else .6)) for i in range(8)]),

    'rumba_flamenca': _g('Rumba: the 3+3+2 tresillo in the bass, backbeat slaps.',
                         4.0, 1,
                         [(0, 'cajon_bass', 1.0), (1.5, 'cajon_bass', .95),
                          (3, 'cajon_bass', .95),
                          (1, 'cajon_ghost', .6), (2, 'cajon_ghost', .6),
                          (2.5, 'cajon_slap', .8), (3.5, 'cajon_ghost', .6),
                          (1, 'golpe', .75), (3, 'golpe', .75)]
                         + [(i * .5, CP, .7 if i % 3 else .9) for i in range(8)]),

    'bulerias': _g(
        'Twelve beats, accents on 12, 3, 6, 8 and 10 -- so the cycle starts on '
        'beat 12 and the "1" you feel is the second stroke. Written here as '
        'one 12-quarter cycle beginning on 12.',
        12.0, 1,
        [(0, 'cajon_bass', 1.0), (3, 'cajon_slap', .95), (6, 'cajon_slap', .95),
         (8, 'cajon_bass', .9), (10, 'cajon_slap', .9)]
        + [(i, CP, .95 if i in (0, 3, 6, 8, 10) else .55) for i in range(12)],
        meter='12'),

    'solea': _g('Twelve beats like bulerías but slow and weighted; accents on '
                '3, 6, 8, 10, 12.',
                12.0, 1,
                [(0, 'cajon_bass', 1.0), (3, 'cajon_slap', .9), (6, 'cajon_slap', .9),
                 (8, 'cajon_bass', .85), (10, 'cajon_slap', .85)]
                + [(i, 'palmas_sordas', .8 if i in (0, 3, 6, 8, 10) else .45)
                   for i in range(12)], meter='12'),

    'sevillanas': _g('3/4 with the characteristic castanet lift.', 3.0, 1,
                     [(0, 'cajon_bass', 1.0), (1, 'cajon_slap', .8),
                      (2, 'cajon_slap', .8), (2.5, 'castanets', .7),
                      (0, CP, .9), (1, CP, .7), (2, CP, .7)], meter='3/4'),

    # ---------------- Middle Eastern iqa'at ----------------
    'maqsum': _g('D T - T | D - T -. The default Arabic 4/4.', 4.0, 1,
                 [(0, 'darbuka_dum', 1.0), (0.5, 'darbuka_tek', .7),
                  (1.5, 'darbuka_tek', .7), (2, 'darbuka_dum', .95),
                  (3, 'darbuka_tek', .75)]
                 + [(i * .5, 'darbuka_ka', .3) for i in range(8)]),

    'baladi': _g('D D - T | D - T -. Maqsum with a doubled first dum: heavier.',
                 4.0, 1,
                 [(0, 'darbuka_dum', 1.0), (0.5, 'darbuka_dum', .85),
                  (1.5, 'darbuka_tek', .7), (2, 'darbuka_dum', .9),
                  (3, 'darbuka_tek', .75)]),

    'saidi': _g('D - T D | D - T -. The two dums in the middle are the '
                'signature; the Saidi lift.',
                4.0, 1,
                [(0, 'darbuka_dum', 1.0), (1, 'darbuka_tek', .7),
                 (1.5, 'darbuka_dum', .9), (2, 'darbuka_dum', .95),
                 (3, 'darbuka_tek', .75)]),

    'ayyub': _g('D - - T | D T -. Fast 2/4, the zar / saidi-shaabi engine.',
                2.0, 1,
                [(0, 'darbuka_dum', 1.0), (0.75, 'darbuka_tek', .7),
                 (1, 'darbuka_dum', .9), (1.5, 'darbuka_tek', .75)],
                meter='2/4'),

    'karsilama': _g('9/8 as 2+2+2+3 -- Turkish/Balkan.', 4.5, 1,
                    [(0, 'darbuka_dum', 1.0), (1, 'darbuka_tek', .7),
                     (2, 'darbuka_dum', .9), (3, 'darbuka_tek', .7),
                     (3.5, 'darbuka_tek', .6), (4, 'darbuka_ka', .55)],
                    meter='9/8'),

    'balkan_78': _g('7/8 as 2+2+3. Accent the long group.', 3.5, 1,
                    [(0, K, 1.0), (1, S, .8), (2, K, .9), (2.5, S, .6),
                     (3, S, .7)]
                    + [(i * .5, HH, .55 if i in (0, 2, 4) else .4) for i in range(7)],
                    meter='7/8'),

    # ---------------- Indian tala (as clap patterns) ----------------
    'keherwa': _g('8-beat tala. Dha Ge Na Ti | Na Ka Dhi Na.', 4.0, 1,
                  [(0, 'tabla_ge', 1.0), (0.5, 'tabla_ge', .6),
                   (1, 'tabla_na', .8), (1.5, 'tabla_tin', .6),
                   (2, 'tabla_na', .9), (2.5, 'tabla_tin', .6),
                   (3, 'tabla_ge', .8), (3.5, 'tabla_na', .6)]),

    'dadra': _g('6-beat tala, 3+3.', 3.0, 1,
                [(0, 'tabla_ge', 1.0), (0.5, 'tabla_na', .6), (1, 'tabla_tin', .7),
                 (1.5, 'tabla_na', .8), (2, 'tabla_na', .7), (2.5, 'tabla_tin', .6)],
                meter='6/8'),

    'teental': _g('16-beat tala, the most common in Hindustani music. '
                  'Vibhag 4+4+4+4, khali (empty) on beat 9.',
                  4.0, 4,
                  [(0, 'tabla_ge', 1.0)]
                  + [(i * .5, 'tabla_na' if i % 2 else 'tabla_tin',
                      .35 if 8 <= i * .5 < 12 else .6) for i in range(1, 32)],
                  meter='16'),

    # ---------------- waltz / classical ----------------
    'waltz': _g('Oom-pah-pah.', 3.0, 1,
                [(0, K, 1.0), (1, S, .55), (2, S, .55)], meter='3/4'),
}


def list_grooves() -> list[tuple[str, str, str]]:
    """(name, meter, description) for every groove, for quick discovery."""
    return sorted((k, v['meter'], v['about'].split('.')[0] + '.')
                  for k, v in GROOVES.items())


def groove(part: stream.Stream, offset: float, name: str, vel: float = 80,
           repeats: int = 1, fill: bool = False, humanise: float = 0.008,
           only: Sequence[str] | None = None,
           skip: Sequence[str] | None = None) -> float:
    """Lay one (or ``repeats``) cycles of a named groove starting at ``offset``.

    ``vel`` is the loud-stroke velocity; every hit is scaled by its own
    velocity scalar. ``only`` / ``skip`` filter by instrument name, which is how
    you thin a groove out for a quiet section -- e.g. ``only=['hand_clap']`` for
    palmas alone. ``fill`` adds a sixteenth pickup at the end of the last cycle.

    Returns the offset just past the last cycle.
    """
    g = GROOVES[name]
    span = g['bar'] * g['bars']
    for r in range(repeats):
        base = float(offset) + r * span
        for off, key, scal in g['hits']:
            if only and key not in only:
                continue
            if skip and key in skip:
                continue
            hit(part, base + off, key, vel * scal + random.uniform(-3, 3),
                jitter=humanise)
        if fill and r == repeats - 1:
            for j, o in enumerate((span - 0.75, span - 0.5, span - 0.25)):
                hit(part, base + o, 'snare' if 'snare' in str(g['hits']) else 'cajon_slap',
                    vel * (0.55 + 0.15 * j), jitter=humanise)
    return float(offset) + repeats * span


def clave(part: stream.Stream, offset: float, kind: str = 'son_32',
          vel: float = 88, repeats: int = 1) -> float:
    """Just the clave, for layering under anything."""
    return groove(part, offset, f'clave_{kind}', vel=vel, repeats=repeats)
