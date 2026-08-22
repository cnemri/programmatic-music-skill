"""
m21kit -- the missing performance layer for music21.

music21 is a superb model of *notation*. It is not a model of *performance*, and
it is not a renderer. This package fills the gap between "a Stream that is
theoretically correct" and "an mp3 that sounds like music":

    midiio    writing MIDI that actually plays back correctly (channels, stems,
              tempo maps, wall-clock timing)
    perform   the gestures notation leaves out -- strums, rolls, tremolo,
              arpeggios, humanised timing and velocity, swing
    drums     the full General MIDI percussion map plus a library of real
              grooves in many traditions
    scales    a large world-scale/maqam/raga library, and how to make music21
              understand them
    render    score -> wav -> mastered mp3 via FluidSynth and ffmpeg
    verify    how to check your own music when you cannot listen to it

Everything here is plain functions over music21 objects. Nothing subclasses
music21, nothing monkeypatches it, and you can vendor any single module.

    from m21kit import perform, drums, midiio, render, verify, scales
"""

__version__ = '1.0.0'

from m21kit import drums, midiio, perform, render, scales, verify

__all__ = ['drums', 'midiio', 'perform', 'render', 'scales', 'verify']
