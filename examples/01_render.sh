#!/usr/bin/env bash
# Render the music21 stems with fluidsynth, mix them like a flamenco session
# (one guitar close-miked, palmas a little wider), master, and encode to MP3.
set -euo pipefail
cd "$(dirname "$0")"

SF2=FluidR3_GM.sf2
OUT=una_mattina_bella_ciao_flamenco.mp3
SR=48000

mkdir -p wav

# --- 1. render each stem dry-ish; low gain leaves plenty of headroom --------
render() {  # name gain reverb
  fluidsynth -ni -F "wav/$1.wav" -r $SR -g "$2" -R "$3" -C 1 \
    -o synth.reverb.room-size=0.62 -o synth.reverb.damp=0.4 \
    -o synth.reverb.width=0.7 -o synth.reverb.level=0.55 \
    -o synth.polyphony=512 \
    "$SF2" "stems/$4" >/dev/null 2>&1
  printf '  %-8s %s\n' "$1" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "wav/$1.wav")"
}

echo "rendering stems:"
render melody  0.45 1 0_melody.mid
render harmony 0.40 1 1_harmony.mid
render bass    0.45 1 2_bass.mid
render octave  0.40 1 3_octave.mid
render perc    0.45 1 4_perc.mid

# --- 2. mix ----------------------------------------------------------------
# Levels favour the singing top line over the strummed body of the guitar.
# Panning is subtle: it is meant to read as one instrument in a room, with the
# palmas and cajon sitting a touch wider behind it.
echo "mixing..."
ffmpeg -y -hide_banner -v error \
  -i wav/melody.wav -i wav/harmony.wav -i wav/bass.wav \
  -i wav/octave.wav -i wav/perc.wav \
  -filter_complex "
   [0:a]volume=3.2dB,  stereotools=balance_out=0.10,
        highpass=f=110, equalizer=f=2600:t=q:w=1.1:g=2.6 [mel];
   [1:a]volume=-2.6dB, stereotools=balance_out=-0.14,
        highpass=f=85,  equalizer=f=3400:t=q:w=1.4:g=1.8,
                        equalizer=f=330:t=q:w=1.1:g=-2.2 [har];
   [2:a]volume=1.0dB,  highpass=f=55,
                        equalizer=f=110:t=q:w=1.0:g=2.0 [bas];
   [3:a]volume=-5.5dB, stereotools=balance_out=-0.30, highpass=f=100 [oct];
   [4:a]volume=-4.5dB, stereotools=balance_out=0.22,
                        highpass=f=70,
                        equalizer=f=1800:t=q:w=1.2:g=2.0 [prc];
   [mel][har][bas][oct][prc]amix=inputs=5:duration=longest:normalize=0[mix];
   [mix]acompressor=threshold=-17dB:ratio=2.4:attack=12:release=220:makeup=2,
        aformat=sample_fmts=fltp,
        loudnorm=I=-14:TP=-1.2:LRA=11,
        afade=t=in:st=0:d=0.35,
        afade=t=out:st=168.6:d=4.6
   " -ar $SR -ac 2 -c:a pcm_s24le wav/master.wav

# --- 3. encode -------------------------------------------------------------
echo "encoding mp3..."
ffmpeg -y -hide_banner -v error -i wav/master.wav \
  -codec:a libmp3lame -b:a 320k -ar 44100 \
  -metadata title="Una Mattina / Bella Ciao (Rumba Flamenca)" \
  -metadata artist="Spanish Guitar arrangement" \
  -metadata album="Generated with music21" \
  -metadata genre="Flamenco" \
  -metadata comment="Arranged and sequenced with music21; rendered with FluidSynth (FluidR3 GM)" \
  "$OUT"

echo
echo "done -> $OUT"
ffprobe -v error -show_entries format=duration,bit_rate -of default=nw=1 "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
