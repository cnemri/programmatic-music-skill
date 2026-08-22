"""
A world scale library, and how to make music21 use it.

music21 ships the Western modes and a handful of others. It does not ship maqam
Hijaz, raga Malkauns, hirajoshi, or the 72 melakarta. It does not need to: a
scale is just a list of intervals, and :func:`m21_scale` turns any list here
into a real ``ConcreteScale`` with working ``.pitchFromDegree``, ``.next()`` and
``.getScaleDegreeFromPitch``.

Intervals are semitones from the tonic. **Floats mean microtones** -- 3.5 is a
half-flat third, the sound of maqam Rast. Those will not survive plain MIDI
export (see :func:`is_microtonal` and references/02-pitch-notes-chords.md); use
:func:`nearest_12tet` or per-channel pitch bend.

    from m21kit import scales
    scales.pitches('hijaz', 'D4', octaves=2)      # [62, 63, 66, 67, 69, ...]
    scales.m21_scale('malkauns', 'C4').getPitches('C4', 'C6')
    scales.find('maqam')                          # search the library
"""

from __future__ import annotations

from typing import Iterable, Sequence

from music21 import pitch as m21pitch
from music21 import scale as m21scale

__all__ = ['SCALES', 'AJNAS', 'pitches', 'm21_scale', 'find', 'is_microtonal',
           'nearest_12tet', 'degrees_to_chord', 'melakarta', 'describe',
           'resolve', 'build_maqam']

# ---------------------------------------------------------------------------
# name -> (semitone offsets from the tonic, one octave, ascending; description)
# ---------------------------------------------------------------------------
SCALES: dict[str, tuple[tuple[float, ...], str]] = {

    # ---- Western diatonic modes ----
    'major':          ((0, 2, 4, 5, 7, 9, 11), 'Ionian.'),
    'ionian':         ((0, 2, 4, 5, 7, 9, 11), 'Major.'),
    'dorian':         ((0, 2, 3, 5, 7, 9, 10), 'Minor with a raised 6th; modal jazz, folk.'),
    'phrygian':       ((0, 1, 3, 5, 7, 8, 10), 'Minor with a flat 2nd; Spanish, metal.'),
    'lydian':         ((0, 2, 4, 6, 7, 9, 11), 'Major with a sharp 4th; floating, filmic.'),
    'mixolydian':     ((0, 2, 4, 5, 7, 9, 10), 'Major with a flat 7th; blues, rock, folk.'),
    'aeolian':        ((0, 2, 3, 5, 7, 8, 10), 'Natural minor.'),
    'minor':          ((0, 2, 3, 5, 7, 8, 10), 'Natural minor.'),
    'locrian':        ((0, 1, 3, 5, 6, 8, 10), 'Diminished tonic; unstable.'),

    # ---- minor variants ----
    'harmonic_minor': ((0, 2, 3, 5, 7, 8, 11), 'Raised 7th: the augmented 2nd is the sound.'),
    'melodic_minor':  ((0, 2, 3, 5, 7, 9, 11), 'Jazz minor (ascending form used throughout).'),
    'harmonic_major': ((0, 2, 4, 5, 7, 8, 11), 'Major with a flat 6th.'),
    'double_harmonic': ((0, 1, 4, 5, 7, 8, 11), 'Byzantine / Gypsy major; two augmented 2nds.'),
    'hungarian_minor': ((0, 2, 3, 6, 7, 8, 11), 'Gypsy minor.'),
    'neapolitan_major': ((0, 1, 3, 5, 7, 9, 11), ''),
    'neapolitan_minor': ((0, 1, 3, 5, 7, 8, 11), ''),

    # ---- modes of melodic minor (jazz) ----
    'dorian_b2':      ((0, 1, 3, 5, 7, 9, 10), 'Melodic minor mode 2; phrygian #6.'),
    'lydian_augmented': ((0, 2, 4, 6, 8, 9, 11), 'Melodic minor mode 3.'),
    'lydian_dominant': ((0, 2, 4, 6, 7, 9, 10), 'Melodic minor mode 4; the "acoustic" scale.'),
    'mixolydian_b6':  ((0, 2, 4, 5, 7, 8, 10), 'Melodic minor mode 5; hindu scale.'),
    'locrian_sharp2': ((0, 2, 3, 5, 6, 8, 10), 'Melodic minor mode 6; over half-diminished.'),
    'altered':        ((0, 1, 3, 4, 6, 8, 10), 'Super-locrian; the altered dominant scale.'),

    # ---- modes of harmonic minor ----
    'locrian_6':      ((0, 1, 3, 5, 6, 9, 10), 'Harmonic minor mode 2.'),
    'ionian_sharp5':  ((0, 2, 4, 5, 8, 9, 11), 'Harmonic minor mode 3.'),
    'ukrainian_dorian': ((0, 2, 3, 6, 7, 9, 10), 'Dorian #4; klezmer "misheberakh".'),
    'phrygian_dominant': ((0, 1, 4, 5, 7, 8, 10),
                          'Harmonic minor mode 5. The flamenco mode, maqam Hijaz, '
                          'and klezmer freygish are all this scale.'),
    'lydian_sharp2':  ((0, 3, 4, 6, 7, 9, 11), 'Harmonic minor mode 6.'),

    # ---- flamenco ----
    'flamenco':       ((0, 1, 4, 5, 7, 8, 10), 'Phrygian dominant; "por medio"/"por arriba".'),
    'flamenco_mixed': ((0, 1, 3, 4, 5, 7, 8, 10),
                       'Both thirds present -- what cante actually uses, sliding '
                       'between the minor and major 3rd.'),

    # ---- symmetric ----
    'whole_tone':     ((0, 2, 4, 6, 8, 10), 'Messiaen mode 1.'),
    'octatonic_hw':   ((0, 1, 3, 4, 6, 7, 9, 10), 'Half-whole diminished; Messiaen mode 2.'),
    'octatonic_wh':   ((0, 2, 3, 5, 6, 8, 9, 11), 'Whole-half diminished.'),
    'augmented':      ((0, 3, 4, 7, 8, 11), 'Alternating m3 and semitone.'),
    'chromatic':      (tuple(range(12)), ''),
    'messiaen_3':     ((0, 2, 3, 4, 6, 7, 8, 10, 11), ''),
    'messiaen_4':     ((0, 1, 2, 5, 6, 7, 8, 11), ''),
    'messiaen_5':     ((0, 1, 5, 6, 7, 11), ''),
    'messiaen_6':     ((0, 2, 4, 5, 6, 8, 10, 11), ''),
    'messiaen_7':     ((0, 1, 2, 3, 5, 6, 7, 8, 9, 11), ''),
    'tritone':        ((0, 1, 4, 6, 7, 10), 'Petrushka-ish.'),
    'prometheus':     ((0, 2, 4, 6, 9, 10), 'Scriabin.'),
    'enigmatic':      ((0, 1, 4, 6, 8, 10, 11), 'Verdi.'),

    # ---- pentatonic and blues ----
    'major_pentatonic': ((0, 2, 4, 7, 9), ''),
    'minor_pentatonic': ((0, 3, 5, 7, 10), ''),
    'blues':          ((0, 3, 5, 6, 7, 10), 'Minor pentatonic + the flat 5.'),
    'major_blues':    ((0, 2, 3, 4, 7, 9), ''),
    'egyptian':       ((0, 2, 5, 7, 10), 'Suspended pentatonic.'),
    'man_gong':       ((0, 3, 5, 8, 10), ''),
    'ritusen':        ((0, 2, 5, 7, 9), ''),

    # ---- bebop (8-note, the chromatic passing tone is the point) ----
    'bebop_dominant': ((0, 2, 4, 5, 7, 9, 10, 11), 'Mixolydian + natural 7.'),
    'bebop_major':    ((0, 2, 4, 5, 7, 8, 9, 11), 'Major + sharp 5.'),
    'bebop_dorian':   ((0, 2, 3, 4, 5, 7, 9, 10), 'Dorian + natural 3.'),
    'bebop_melodic_minor': ((0, 2, 3, 5, 7, 8, 9, 11), ''),

    # ---- Arabic maqamat.  Half-integers are quarter tones. ----
    # Regional and performer variation is real; these are the common Egyptian/
    # Levantine forms, built from the ajnas in AJNAS below.
    'maqam_ajam':     ((0, 2, 4, 5, 7, 9, 11), 'Ajam = major, but phrased very differently.'),
    'maqam_nahawand': ((0, 2, 3, 5, 7, 8, 10), 'Nahawand = natural minor (often #7 ascending).'),
    'maqam_kurd':     ((0, 1, 3, 5, 7, 8, 10), 'Kurd = phrygian.'),
    'maqam_hijaz':    ((0, 1, 4, 5, 7, 8, 10),
                       'Jins Hijaz + jins Nahawand. Identical to phrygian dominant, '
                       'which is why flamenco and Arabic music share a mode.'),
    'maqam_hijazkar': ((0, 1, 4, 5, 7, 8, 11), 'Hijaz on both tetrachords.'),
    'maqam_nikriz':   ((0, 2, 3, 6, 7, 9, 10), 'Jins Nikriz; = ukrainian dorian.'),
    'maqam_athar_kurd': ((0, 1, 3, 6, 7, 8, 11), ''),
    'maqam_rast':     ((0, 2, 3.5, 5, 7, 9, 10.5),
                       'MICROTONAL. The half-flat 3rd and 7th are the whole identity.'),
    'maqam_bayati':   ((0, 1.5, 3, 5, 7, 8, 10), 'MICROTONAL. Half-flat 2nd.'),
    'maqam_saba':     ((0, 1.5, 3, 4, 7, 8, 10), 'MICROTONAL. The diminished 4th is unique.'),
    'maqam_sikah':    ((0, 1.5, 3.5, 5.5, 7, 8.5, 10.5), 'MICROTONAL. Built on a half-flat degree.'),
    'maqam_huzam':    ((0, 1.5, 2.5, 5.5, 6.5, 8.5, 10.5), 'MICROTONAL.'),

    # ---- Turkish makam (12-TET approximations of Ottoman comma theory) ----
    'makam_hicaz':    ((0, 1, 4, 5, 7, 8, 10), '12-TET approximation.'),
    'makam_kurdi':    ((0, 1, 3, 5, 7, 8, 10), '12-TET approximation.'),
    'makam_nihavend': ((0, 2, 3, 5, 7, 8, 10), '12-TET approximation.'),
    'makam_saba':     ((0, 1.5, 3, 4, 7, 8, 10), 'MICROTONAL approximation.'),

    # ---- Hindustani thaats ----
    'bilawal':        ((0, 2, 4, 5, 7, 9, 11), 'Thaat = major.'),
    'khamaj':         ((0, 2, 4, 5, 7, 9, 10), 'Thaat = mixolydian.'),
    'kafi':           ((0, 2, 3, 5, 7, 9, 10), 'Thaat = dorian.'),
    'asavari':        ((0, 2, 3, 5, 7, 8, 10), 'Thaat = aeolian.'),
    'bhairavi':       ((0, 1, 3, 5, 7, 8, 10), 'Thaat = phrygian.'),
    'bhairav':        ((0, 1, 4, 5, 7, 8, 11), 'Thaat = double harmonic.'),
    'kalyan':         ((0, 2, 4, 6, 7, 9, 11), 'Thaat = lydian.'),
    'marwa':          ((0, 1, 4, 6, 7, 9, 11), 'Thaat.'),
    'purvi':          ((0, 1, 4, 6, 7, 8, 11), 'Thaat.'),
    'todi':           ((0, 1, 3, 6, 7, 8, 11), 'Thaat.'),

    # ---- common ragas (aroha; many ragas differ descending -- see Gotchas) ----
    'raga_yaman':     ((0, 2, 4, 6, 7, 9, 11), 'Kalyan thaat; evening.'),
    'raga_bhupali':   ((0, 2, 4, 7, 9), 'Pentatonic, no ma or ni.'),
    'raga_malkauns':  ((0, 3, 5, 8, 10), 'Pentatonic, late night, no re or pa.'),
    'raga_durga':     ((0, 2, 5, 7, 9), 'Pentatonic.'),
    'raga_hamsadhwani': ((0, 2, 4, 7, 11), 'Pentatonic, Carnatic origin.'),
    'raga_charukeshi': ((0, 2, 4, 5, 7, 8, 10), ''),
    'raga_kirwani':   ((0, 2, 3, 5, 7, 8, 11), '= harmonic minor.'),
    'raga_shivaranjani': ((0, 2, 3, 7, 9), 'Pentatonic, plaintive.'),
    'raga_madhuvanti': ((0, 2, 3, 6, 7, 9, 11), ''),

    # ---- Japanese ----
    'hirajoshi':      ((0, 2, 3, 7, 8), 'Koto tuning.'),
    'kumoi':          ((0, 2, 3, 7, 9), ''),
    'in_sen':         ((0, 1, 5, 7, 10), ''),
    'iwato':          ((0, 1, 5, 6, 10), ''),
    'yo':             ((0, 2, 5, 7, 9), 'Anhemitonic; folk song.'),
    'ryukyu':         ((0, 4, 5, 7, 11), 'Okinawan.'),

    # ---- Chinese pentatonic modes ----
    'gong':           ((0, 2, 4, 7, 9), ''),
    'shang':          ((0, 2, 5, 7, 10), ''),
    'jue':            ((0, 3, 5, 8, 10), ''),
    'zhi':            ((0, 2, 5, 7, 9), ''),
    'yu':             ((0, 3, 5, 7, 10), ''),

    # ---- Indonesian (NOT 12-TET; these are rough equal-step models) ----
    'slendro':        ((0, 2.4, 4.8, 7.2, 9.6),
                       'MICROTONAL, approximate: five roughly equal steps per octave. '
                       'Real gamelan tunings vary per instrument set.'),
    'pelog_bem':      ((0, 1, 3, 7, 8),
                       'Approximate 12-TET reduction of a common pelog pathet.'),

    # ---- Jewish / klezmer ----
    'freygish':       ((0, 1, 4, 5, 7, 8, 10), 'Ahava Rabba = phrygian dominant.'),
    'misheberakh':    ((0, 2, 3, 6, 7, 9, 10), 'Ukrainian dorian.'),
    'adonai_malakh':  ((0, 2, 4, 5, 7, 9, 10), ''),

    # ---- other ----
    'persian':        ((0, 1, 4, 5, 6, 8, 11), ''),
    'arabic_gypsy':   ((0, 1, 4, 5, 7, 8, 11), '= double harmonic.'),
    'romanian_minor': ((0, 2, 3, 6, 7, 9, 10), ''),
    'spanish_8':      ((0, 1, 3, 4, 5, 7, 8, 10), 'Phrygian with both thirds.'),
    'scottish_pent':  ((0, 2, 5, 7, 9), ''),
    'hexatonic_blues': ((0, 3, 5, 6, 7, 10), ''),
}

# ---------------------------------------------------------------------------
# Arabic ajnas -- the 3-to-5 note cells maqamat are actually built from. A maqam
# is a lower jins on the tonic plus an upper jins starting on its 4th or 5th
# degree, so with these you can construct any maqam, including ones not listed
# above.
# ---------------------------------------------------------------------------
AJNAS: dict[str, tuple[float, ...]] = {
    'rast':     (0, 2, 3.5, 5),
    'nahawand': (0, 2, 3, 5),
    'kurd':     (0, 1, 3, 5),
    'hijaz':    (0, 1, 4, 5),
    'bayati':   (0, 1.5, 3, 5),
    'saba':     (0, 1.5, 3, 4),
    'ajam':     (0, 2, 4, 5),
    'sikah':    (0, 1.5, 3.5),
    'nikriz':   (0, 2, 3, 6, 7),
    'athar_kurd': (0, 1, 3, 6, 7),
    'hijazkar': (0, 1, 4, 5, 6),
    'jiharkah': (0, 2, 4, 5),
    'mustaar':  (0, 1.5, 3.5, 4.5),
}


def build_maqam(lower: str, upper: str, on_degree: int = 4) -> tuple[float, ...]:
    """Compose a maqam from a lower and an upper jins.

    ``on_degree`` is which scale degree the upper jins starts on -- 4 for most
    maqamat (the upper jins begins on the 4th), 5 for those built on the fifth.

    >>> build_maqam('hijaz', 'nahawand')       # maqam Hijaz
    (0, 1, 4, 5, 7, 8, 10)
    """
    lo = AJNAS[lower]
    root = lo[on_degree - 1]
    up = tuple(root + x for x in AJNAS[upper][1:])
    return tuple(sorted(set(lo + up)))


# ---------------------------------------------------------------------------
# Carnatic melakarta -- 72 parent scales, generated from the formula rather
# than typed out, so there are no transcription errors.
# ---------------------------------------------------------------------------
_RI_GA = [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]
_DA_NI = [(8, 9), (8, 10), (8, 11), (9, 10), (9, 11), (10, 11)]
_MELA_NAMES = {
    1: 'kanakangi', 8: 'hanumatodi', 15: 'mayamalavagowla', 20: 'natabhairavi',
    22: 'kharaharapriya', 27: 'sarasangi', 28: 'harikambhoji', 29: 'dheerasankarabharanam',
    36: 'chalanata', 39: 'jhalavarali', 45: 'shubhapantuvarali', 51: 'pantuvarali',
    53: 'gamanashrama', 56: 'shanmukhapriya', 57: 'simhendramadhyamam',
    62: 'rishabhapriya', 64: 'vachaspati', 65: 'mechakalyani', 66: 'chitrambari',
    72: 'rasikapriya',
}


def melakarta(n: int) -> tuple[float, ...]:
    """The nth Carnatic melakarta raga (1-72) as semitone offsets.

    >>> melakarta(29)      # Dheerasankarabharanam = the major scale
    (0, 2, 4, 5, 7, 9, 11)
    >>> melakarta(65)      # Mechakalyani = lydian
    (0, 2, 4, 6, 7, 9, 11)
    """
    if not 1 <= n <= 72:
        raise ValueError('melakarta number must be 1..72')
    half = (n - 1) % 36
    ma = 5 if n <= 36 else 6
    ri, ga = _RI_GA[half // 6]
    da, ni = _DA_NI[half % 6]
    return (0, ri, ga, ma, 7, da, ni)


for _n in range(1, 73):
    _nm = _MELA_NAMES.get(_n)
    SCALES[f'melakarta_{_n}'] = (melakarta(_n), f'Carnatic melakarta {_n}'
                                 + (f' ({_nm})' if _nm else ''))
    if _nm:
        SCALES[_nm] = (melakarta(_n), f'Carnatic melakarta {_n}.')


# ---------------------------------------------------------------------------
# Using them
# ---------------------------------------------------------------------------
_PREFIXES = ('', 'maqam_', 'raga_', 'makam_', 'melakarta_')


def resolve(name: str) -> str:
    """Accept 'malkauns' for 'raga_malkauns', 'hijaz' for 'maqam_hijaz', etc.

    Raises with the closest matches rather than a bare KeyError, because an
    agent that guessed a name should be told the right one, not made to grep.
    """
    n = name.strip().lower().replace(' ', '_').replace('-', '_')
    for pre in _PREFIXES:
        if pre + n in SCALES:
            return pre + n
    if n.startswith(('maqam_', 'raga_', 'makam_')):
        bare = n.split('_', 1)[1]
        if bare in SCALES:
            return bare
    import difflib
    near = difflib.get_close_matches(n, SCALES, n=6, cutoff=0.5)
    raise KeyError(f'unknown scale {name!r}. Did you mean: {near or "(use scales.find())"}')


def _tonic_midi(tonic) -> float:
    if isinstance(tonic, (int, float)):
        return float(tonic)
    return float(m21pitch.Pitch(tonic).ps)


def is_microtonal(name: str) -> bool:
    """True if the scale needs pitches between the piano keys."""
    return any(float(x) != int(x) for x in SCALES[resolve(name)][0])


def pitches(name: str, tonic='C4', octaves: int = 1,
            include_octave: bool = False) -> list[float]:
    """Semitone (MIDI) values of the scale over ``octaves`` octaves.

    Returns floats when microtonal, ints otherwise.

    >>> pitches('hijaz' if 'hijaz' in SCALES else 'maqam_hijaz', 'D4')
    [62, 63, 66, 67, 69, 70, 72]
    """
    iv = SCALES[resolve(name)][0]
    base = _tonic_midi(tonic)
    out: list[float] = []
    for o in range(octaves):
        for x in iv:
            v = base + 12 * o + x
            out.append(int(v) if float(v) == int(v) else v)
    if include_octave:
        v = base + 12 * octaves
        out.append(int(v) if float(v) == int(v) else v)
    return out


def nearest_12tet(name: str, half_step: str = 'down') -> tuple[int, ...]:
    """Reduce a microtonal scale to 12-TET.

    A compromise, not a solution: maqam Rast reduced this way is a major scale
    with a flat 3rd and 7th, and the thing that made it Rast is gone. Use it
    when you must render to plain MIDI, and say in your write-up that you
    approximated.

    ``half_step`` decides where an exact quarter tone goes -- 'down' (toward the
    flat, which is how these degrees are conventionally notated in Western
    approximation), 'up', or 'nearest'. Do not use Python's ``round`` here: it
    is banker's rounding, so 3.5 goes to 4 and 10.5 goes to 10, and a scale
    comes out internally inconsistent.
    """
    import math
    iv = SCALES[resolve(name)][0]
    if half_step == 'up':
        f = lambda x: int(math.floor(x + 0.5))          # noqa: E731
    elif half_step == 'nearest':
        f = lambda x: int(round(x))                     # noqa: E731
    else:
        f = lambda x: int(math.ceil(x - 0.5))           # noqa: E731
    return tuple(f(x) for x in iv)


def m21_scale(name: str, tonic='C4') -> m21scale.ConcreteScale:
    """A real music21 ConcreteScale, so ``.next()``, ``.pitchFromDegree()``,
    ``.getScaleDegreeFromPitch()`` and ``.getPitches()`` all work.

    Microtonal scales are built with quarter-tone Accidentals, which music21
    models correctly but MIDI cannot carry.
    """
    name = resolve(name)
    ps = []
    base = _tonic_midi(tonic)
    for x in SCALES[name][0]:
        p = m21pitch.Pitch()
        p.ps = base + x
        ps.append(p)
    last = m21pitch.Pitch()
    last.ps = base + 12
    ps.append(last)
    sc = m21scale.ConcreteScale(pitches=ps)
    # ConcreteScale.name is a read-only property; stash ours alongside it.
    sc.m21kit_name = name
    return sc


def degrees_to_chord(name: str, tonic, degree: int, size: int = 3,
                     step: int = 2) -> list[float]:
    """Stack thirds (or any ``step``) on a scale degree -- diatonic harmony in
    any mode, including the exotic ones.

    ``degree`` is 1-based. ``size=3`` gives a triad, 4 a seventh chord.

    >>> degrees_to_chord('major', 'C4', 5, size=4)     # G7
    [67, 71, 74, 77]
    """
    iv = SCALES[resolve(name)][0]
    n = len(iv)
    base = _tonic_midi(tonic)
    out = []
    for k in range(size):
        idx = (degree - 1) + k * step
        octv, i = divmod(idx, n)
        v = base + 12 * octv + iv[i]
        out.append(int(v) if float(v) == int(v) else v)
    return out


def find(query: str) -> list[tuple[str, str]]:
    """Search the library by name or description substring."""
    q = query.lower()
    return sorted((k, v[1]) for k, v in SCALES.items()
                  if q in k.lower() or q in v[1].lower())


def describe(name: str) -> str:
    name = resolve(name)
    iv, about = SCALES[name]
    steps = [round(b - a, 2) for a, b in zip(iv, iv[1:] + (12,))]
    return (f'{name}: {len(iv)} notes, offsets {list(iv)}, steps {steps}'
            + (f'\n  {about}' if about else '')
            + ('\n  MICROTONAL -- will not survive plain MIDI export.'
               if is_microtonal(name) else ''))
