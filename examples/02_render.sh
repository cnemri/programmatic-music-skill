#!/usr/bin/env bash
# Render "Adhan por Granaina": FluidSynth per voice, then a mix that puts the
# muezzin's line in front in a stone courtyard and keeps the guitar behind it.
set -euo pipefail
cd "$(dirname "$0")"

SF2=FluidR3_GM.sf2
OUT=adhan_flamenco.mp3
SR=48000
mkdir -p wav_adhan

render() {  # name gain stem
  fluidsynth -ni -F "wav_adhan/$1.wav" -r $SR -g "$2" -R 1 -C 1 \
    -o synth.reverb.room-size=0.85 -o synth.reverb.damp=0.30 \
    -o synth.reverb.width=0.9 -o synth.reverb.level=0.70 \
    -o synth.polyphony=512 \
    "$SF2" "stems_adhan/$3" >/dev/null 2>&1
  printf '  %-5s %8.2fs\n' "$1" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "wav_adhan/$1.wav")"
}

echo "rendering voices:"
render voz 0.50 0_voz.mid
render har 0.42 1_har.mid
render bas 0.45 2_bas.mid
render eco 0.40 3_eco.mid
render prc 0.42 4_prc.mid

# The call carries a long, low echo -- the way an adhan actually reaches you,
# arriving off walls a beat behind itself.  Kept quiet enough to read as space.
echo "mixing..."
ffmpeg -y -hide_banner -v error \
  -i wav_adhan/voz.wav -i wav_adhan/har.wav -i wav_adhan/bas.wav \
  -i wav_adhan/eco.wav -i wav_adhan/prc.wav \
  -filter_complex "
   [0:a]volume=4.2dB, highpass=f=120,
        equalizer=f=2400:t=q:w=1.2:g=3.0,
        equalizer=f=520:t=q:w=1.0:g=-1.5,
        aecho=0.92:0.72:900|1830:0.17|0.085,
        stereotools=balance_out=0.04 [voz];
   [1:a]volume=-4.0dB, highpass=f=85,
        equalizer=f=3200:t=q:w=1.4:g=1.4,
        equalizer=f=340:t=q:w=1.1:g=-2.4,
        stereotools=balance_out=-0.16 [har];
   [2:a]volume=0.5dB, highpass=f=52, equalizer=f=105:t=q:w=1.0:g=1.8 [bas];
   [3:a]volume=-8.0dB, highpass=f=140, stereotools=balance_out=-0.34,
        aecho=0.9:0.7:1400:0.2 [eco];
   [4:a]volume=-10.0dB, highpass=f=70,
        equalizer=f=1900:t=q:w=1.2:g=1.6, stereotools=balance_out=0.24 [prc];
   [voz][har][bas][eco][prc]amix=inputs=5:duration=longest:normalize=0[mix];
   [mix]acompressor=threshold=-19dB:ratio=2.0:attack=25:release=380:makeup=2,
        aformat=sample_fmts=fltp,
        loudnorm=I=-16:TP=-1.2:LRA=14,
        afade=t=in:st=0:d=0.5
   " -ar $SR -ac 2 -c:a pcm_s24le wav_adhan/master_nofade.wav

# fade the tail out wherever the render actually stops
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 wav_adhan/master_nofade.wav)
FST=$(python3 -c "print(max(0, $DUR - 5.0))")
ffmpeg -y -hide_banner -v error -i wav_adhan/master_nofade.wav \
  -af "afade=t=out:st=$FST:d=5.0" -c:a pcm_s24le wav_adhan/master.wav
rm -f wav_adhan/master_nofade.wav

echo "encoding mp3..."
ffmpeg -y -hide_banner -v error -i wav_adhan/master.wav \
  -codec:a libmp3lame -b:a 320k -ar 44100 \
  -metadata title="Adhan por Granaina" \
  -metadata artist="Flamenco guitar, Maqam Hijaz" \
  -metadata album="Generated with music21" \
  -metadata genre="Flamenco" \
  -metadata comment="Free-rhythm setting of the Hijazi adhan for flamenco guitar; maqam Hijaz on E = por arriba. Sequenced with music21, rendered with FluidSynth." \
  "$OUT"

echo
echo "done -> $OUT"
ffprobe -v error -show_entries format=duration,bit_rate -of default=nw=1 "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
