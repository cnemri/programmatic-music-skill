#!/usr/bin/env bash
# Render "Mozart por Tangos": FluidSynth per voice, mixed like a tablao --
# one guitar close and present, cajon and palmas behind it.
set -euo pipefail
cd "$(dirname "$0")"

SF2=FluidR3_GM.sf2
OUT=mozart40_flamenco.mp3
SR=48000
mkdir -p wav_mozart

render() {  # name gain stem
  fluidsynth -ni -F "wav_mozart/$1.wav" -r $SR -g "$2" -R 1 -C 1 \
    -o synth.reverb.room-size=0.58 -o synth.reverb.damp=0.42 \
    -o synth.reverb.width=0.7 -o synth.reverb.level=0.52 \
    -o synth.polyphony=768 \
    "$SF2" "stems_mozart/$3" >/dev/null 2>&1
  printf '  %-4s %8.2fs\n' "$1" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "wav_mozart/$1.wav")"
}

echo "rendering voices:"
render mel 0.46 0_mel.mid
render har 0.36 1_har.mid
render bas 0.44 2_bas.mid
render oct 0.38 3_oct.mid
render prc 0.42 4_prc.mid

echo "mixing..."
ffmpeg -y -hide_banner -v error \
  -i wav_mozart/mel.wav -i wav_mozart/har.wav -i wav_mozart/bas.wav \
  -i wav_mozart/oct.wav -i wav_mozart/prc.wav \
  -filter_complex "
   [0:a]volume=3.8dB, highpass=f=115,
        equalizer=f=2700:t=q:w=1.2:g=3.0,
        equalizer=f=480:t=q:w=1.0:g=-1.6,
        stereotools=balance_out=0.08 [mel];
   [1:a]volume=-3.4dB, highpass=f=88,
        equalizer=f=3300:t=q:w=1.4:g=1.6,
        equalizer=f=330:t=q:w=1.1:g=-2.6,
        stereotools=balance_out=-0.16 [har];
   [2:a]volume=0.8dB, highpass=f=55, equalizer=f=108:t=q:w=1.0:g=2.0 [bas];
   [3:a]volume=-6.5dB, highpass=f=100, stereotools=balance_out=-0.30 [oct];
   [4:a]volume=-6.0dB, highpass=f=70,
        equalizer=f=1900:t=q:w=1.2:g=1.8, stereotools=balance_out=0.22 [prc];
   [mel][har][bas][oct][prc]amix=inputs=5:duration=longest:normalize=0[mix];
   [mix]acompressor=threshold=-18dB:ratio=2.3:attack=14:release=240:makeup=2,
        aformat=sample_fmts=fltp,
        loudnorm=I=-14:TP=-1.2:LRA=11,
        afade=t=in:st=0:d=0.3
   " -ar $SR -ac 2 -c:a pcm_s24le wav_mozart/master_nf.wav

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 wav_mozart/master_nf.wav)
FST=$(python3 -c "print(max(0, $DUR - 4.5))")
ffmpeg -y -hide_banner -v error -i wav_mozart/master_nf.wav \
  -af "afade=t=out:st=$FST:d=4.5" -c:a pcm_s24le wav_mozart/master.wav
rm -f wav_mozart/master_nf.wav

echo "encoding mp3..."
ffmpeg -y -hide_banner -v error -i wav_mozart/master.wav \
  -codec:a libmp3lame -b:a 320k -ar 44100 \
  -metadata title="Mozart por Tangos (Symphony No. 40, i. Molto Allegro)" \
  -metadata artist="Flamenco guitar, por medio" \
  -metadata album="Generated with music21" \
  -metadata genre="Flamenco" \
  -metadata comment="K.550/i transposed G minor -> D minor (por medio). Violin I read from score with music21; accompaniment and compas arranged. Rendered with FluidSynth." \
  "$OUT"

echo
echo "done -> $OUT"
ffprobe -v error -show_entries format=duration,bit_rate -of default=nw=1 "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
