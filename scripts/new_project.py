#!/usr/bin/env python3
"""
Scaffold a composition project from one of the templates.

    python scripts/new_project.py my-piece
    python scripts/new_project.py taqsim --template free_rhythm
    python scripts/new_project.py bach-flamenco --template arrangement

Creates a directory with the chosen template as compose.py, a Makefile-ish
run script, and a PLAN.md that asks the five questions worth answering before
you generate a note.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATES = os.path.join(ROOT, 'templates')

PLAN = """# {name}

Answer these before writing code. A style you can only describe as a vibe comes
out as a vibe.

## 1. Mode / scale
Which one, on what tonic? Microtonal?  `python -c "from m21kit import scales; print(scales.find('...'))"`

## 2. Harmony
Triadic, modal, quartal, drone, or none? Write the progression out.
Voicings must be real instrument shapes, not `chord.Chord([...])`.

## 3. Rhythmic cell
The smallest repeating unit and where the accents fall.
`python -c "from m21kit import drums; [print(g) for g in drums.list_grooves()]"`

## 4. Characteristic gesture
The thing a player of this music does that a sequencer never would.
(rasgueado / ghost note / bend / ornament / breath / ligado)

## 5. Form
Sections, bar counts, and **where it peaks and why**.

| section | bars | what changes |
|---|---|---|
|  |  |  |

## Instrumentation
| part | instrument | GM program | range | stem gain |
|---|---|---|---|---|
|  |  |  |  |  |

## Before shipping
- [ ] every part on its own MIDI channel, percussion on 10
- [ ] no notes below any instrument's real range
- [ ] velocities vary; nothing nailed to the grid
- [ ] `verify.section_levels` says the climax is the loudest section
- [ ] not clipping, LUFS on target
- [ ] if you quoted a source, `verify.melody_match` proves it
"""

RUN = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="{root}:${{PYTHONPATH:-}}"
python compose.py -o "${{1:-out.mp3}}"
python "{root}/scripts/verify_music.py" "${{1:-out.mp3}}"
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('name')
    ap.add_argument('--template', default='groove_piece',
                    choices=[f[:-3] for f in sorted(os.listdir(TEMPLATES))
                             if f.endswith('.py')])
    ap.add_argument('--dir', default='.')
    a = ap.parse_args()

    dest = os.path.join(a.dir, a.name)
    if os.path.exists(dest):
        print(f'error: {dest} already exists', file=sys.stderr)
        return 1
    os.makedirs(dest)

    shutil.copy(os.path.join(TEMPLATES, a.template + '.py'),
                os.path.join(dest, 'compose.py'))
    with open(os.path.join(dest, 'PLAN.md'), 'w') as f:
        f.write(PLAN.format(name=a.name))
    run = os.path.join(dest, 'run.sh')
    with open(run, 'w') as f:
        f.write(RUN.format(root=ROOT))
    os.chmod(run, 0o755)

    print(f'{dest}/')
    print('  compose.py   <- from templates/%s.py; edit the CONFIG block' % a.template)
    print('  PLAN.md      <- answer these five questions first')
    print('  run.sh       <- ./run.sh out.mp3')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
