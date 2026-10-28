#!/usr/bin/env python3
"""Explainer-video engine: 3b1b-style scenes drawn frame by frame with matplotlib, narrated with Kokoro-82M
(local CPU, Apache-2.0), piped to ffmpeg. Skill: skills/explainer-video.

A project is a folder holding scenes*.py (exec'd here, so they use the helpers below without imports),
FACTS.md (every on-screen number -> its source) and optional spoken.py (SPOKEN, SAY; see template/).

  engine.py <project> info                 scene list + durations
  engine.py <project> still <i> <t>...     PNG frames to review (scene index i, times t in s)
  engine.py <project> tts                  narration wav per caption + timing.json (needs KOKORO_DIR)
  engine.py <project> check                every caption has audio from the current text
  engine.py <project> render [workers] [i,j..]
  engine.py <project> concat               -> <project>/<project name>.mp4 (with audio if tts ran)

Scratch (segments, stills, audio) goes to $VIDEO_OUT (default /tmp/video-<project name>/).
"""
import json
import os
import re
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image
import imageio_ffmpeg

if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
    sys.exit(__doc__)
PROJ = os.path.abspath(sys.argv[1]) + '/'
NAME = os.path.basename(PROJ.rstrip('/'))
OUT = os.environ.get('VIDEO_OUT', f'/tmp/video-{NAME}').rstrip('/') + '/'
plt.rcParams['font.family'] = 'DejaVu Sans'
W, H, FPS = 1920, 1080, 30

# palette: give each concept one colour and keep it for the whole video
BG, WHITE, GREY, DIM = '#1C1C1C', '#ECECEC', '#8A8A8A', '#3A3A3A'
BLUE, ORANGE, PURPLE, RED = '#58C4DD', '#FF862F', '#B189C6', '#FC6255'
GREEN, YELLOW, TEAL = '#83C167', '#F7D96F', '#5CD0B3'
GOLD, SILVER, BRONZE, NEUTRAL = '#F0C75E', '#C9CED6', '#CD7F32', '#BBBBBB'


# ---------- easing / timing ----------
def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def P(t, a, d=0.8):
    """eased progress 0->1 starting at a over d seconds"""
    return float(sm((t - a) / d))


def A(t, a, b=None, f=0.35):
    """alpha: fade in at a; fade out ending at b"""
    v = sm((t - a) / f)
    if b is not None:
        v = v * sm((b - t) / f)
    return float(v)


def lerp(a, b, u):
    return a + (b - a) * u


def mix(c1, c2, k):
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * float(np.clip(k, 0, 1)))


# ---------- drawing helpers (canvas is 16 x 9 units; captions own y < 1.2) ----------
def T(ax, x, y, s, fs=24, c=WHITE, a=1.0, ha='center', va='center', w='normal', z=10, **kw):
    if a <= 0.005:
        return None
    return ax.text(x, y, s, fontsize=fs, color=c, alpha=min(1.0, float(a)), ha=ha, va=va,
                   fontweight=w, zorder=z, **kw)


def rbox(ax, cx, cy, w, h, ec=WHITE, fc=None, fa=0.15, a=1.0, lw=2, r=0.12, z=4, ls='-'):
    if a <= 0.005:
        return
    st = f'round,pad=0,rounding_size={r}'
    if fc:
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle=st, fc=fc, ec='none',
                                    alpha=a * fa, zorder=z))
    if ec:
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle=st, fc='none', ec=ec,
                                    lw=lw, alpha=a, zorder=z + 0.1, ls=ls))


def bar(ax, x, y, w, h, c, a=1.0, z=5):
    if a <= 0.005 or abs(h) < 1e-4 or w <= 0:
        return
    ax.add_patch(Rectangle((x, y), w, h, fc=c, ec='none', alpha=a, zorder=z))


def ln(ax, xs, ys, c=WHITE, a=1.0, lw=2, ls='-', z=4):
    if a <= 0.005:
        return
    ax.plot(xs, ys, color=c, alpha=a, lw=lw, ls=ls, zorder=z, solid_capstyle='round')


def dot(ax, x, y, r, c, a=1.0, z=6):
    if a <= 0.005:
        return
    ax.add_patch(Circle((x, y), r, color=c, alpha=a, zorder=z))


def ring(ax, x, y, r, c, a=1.0, lw=2.5, z=7):
    if a <= 0.005:
        return
    ax.add_patch(Circle((x, y), r, fc='none', ec=c, lw=lw, alpha=a, zorder=z))


def arr(ax, x0, y0, x1, y1, c=GREY, a=1.0, u=1.0, lw=2.5, ms=18, z=5, cs=None):
    if a <= 0.01 or u <= 0.02:
        return
    xe, ye = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    kw = dict(connectionstyle=cs) if cs else {}
    ax.add_patch(FancyArrowPatch((x0, y0), (xe, ye), arrowstyle='-|>', mutation_scale=ms, color=c,
                                 alpha=a, lw=lw, shrinkA=0, shrinkB=0, zorder=z, **kw))


def img(ax, arr_, cx, cy, w, a=1.0, z=3):
    if a <= 0.01:
        return
    h = w * arr_.shape[0] / arr_.shape[1]
    ax.imshow(arr_, extent=(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2), alpha=float(a), zorder=z,
              interpolation='bilinear', aspect='auto')


def sec(ax, s, t):
    """section label, top left"""
    T(ax, 0.5, 8.55, s, fs=17, c=GREY, a=A(t, 0.2), ha='left', w='bold')


def toy_tag(ax, a):
    """mark an illustrative (made-up) picture so nobody reads it as data"""
    rbox(ax, 14.55, 8.5, 2.1, 0.5, ec=GREY, a=a, lw=1.5, r=0.1)
    T(ax, 14.55, 8.5, 'toy example', fs=17, c=GREY, a=a)


# ---------- scenes ----------
SC = []


def scene(name, caps, tail=0.8):
    """caps: one string per narrated line, or (string, extra seconds to hold). draw(ax, t, cues): cues[k] = start of caption k."""
    def deco(f):
        SC.append(dict(name=name, caps=caps, draw=f, tail=tail))
        return f
    return deco


for _f in sorted(f for f in os.listdir(PROJ) if re.fullmatch(r'scenes.*\.py', f)):
    exec(compile(open(PROJ + _f).read(), PROJ + _f, 'exec'))

SPOKEN, SAY = {}, []        # spoken.py: SPOKEN {'<scene>_<k>': text}, SAY [(written, spoken), ...]
if os.path.exists(PROJ + 'spoken.py'):
    _ns = {}
    exec(open(PROJ + 'spoken.py').read(), _ns)
    SPOKEN, SAY = _ns.get('SPOKEN', {}), _ns.get('SAY', [])
DIG = 'zero one two three four five six seven eight nine'.split()


def cap_text(it):
    return it[0] if isinstance(it, tuple) else it


def say(name, j, cap):
    if f'{name}_{j}' in SPOKEN:
        return SPOKEN[f'{name}_{j}']
    s = re.sub(r'(\+?)(?<![\d,])\.(\d+)', lambda m: ('plus ' if m.group(1) else '') + 'point ' +
               ' '.join(DIG[int(d)] for d in m.group(2)), cap)
    for a, b in SAY:
        s = s.replace(a, b)
    return s


# ---------- timing: each caption lasts its audio + GAP; without audio, a reading-speed estimate ----------
_TJ = OUT + 'audio/timing.json'
AUDIO = json.load(open(_TJ)) if os.path.exists(_TJ) else None
GAP, LEAD = 0.5, 0.6


def audio_ok(sc, j):
    k = f"{sc['name']}_{j}"
    return AUDIO and k in AUDIO['dur'] and AUDIO['text'].get(k) == say(sc['name'], j, cap_text(sc['caps'][j]))


for _sc in SC:
    _t, _cues, _caps = LEAD, [], []
    for _j, _it in enumerate(_sc['caps']):
        _s, _x = _it if isinstance(_it, tuple) else (_it, 0.0)
        _k = f"{_sc['name']}_{_j}"
        _d = (AUDIO['dur'][_k] + GAP if audio_ok(_sc, _j) else max(3.0, len(_s.split()) / 2.5 + 0.2)) + _x
        _cues.append(_t)
        _caps.append((_s, _t, _t + _d))
        _t += _d
    _sc['cues'], _sc['capt'], _sc['D'] = _cues, _caps, _t + _sc['tail']


def wrap2(s, n=80):
    if len(s) <= n:
        return [s]
    mid = len(s) // 2
    sp = [i for i, ch in enumerate(s) if ch == ' ']
    b = min(sp, key=lambda i: abs(i - mid))
    return [s[:b], s[b + 1:]]


def draw_frame(ax, sc, t):
    ax.cla()
    ax.axis('off')
    sc['draw'](ax, t, sc['cues'])
    for s, t0, t1 in sc['capt']:
        a = A(t, t0, t1, f=0.22)
        if a > 0.005:
            lines = wrap2(s)
            ys = [0.62] if len(lines) == 1 else [0.86, 0.38]
            for yy, l in zip(ys, lines):
                T(ax, 8, yy, l, fs=28, c=WHITE, a=a, z=50)
    cover = 1 - min(P(t, 0, 0.45), P(sc['D'] - t, 0, 0.45))
    if cover > 0.003:
        ax.add_patch(Rectangle((0, 0), 16, 9, fc=BG, ec='none', alpha=cover, zorder=1000))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)


def new_fig():
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    return fig, ax


def grab(fig):
    fig.canvas.draw()
    return np.ascontiguousarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3])


def render_scene(i):
    sc = SC[i]
    n = int(round(sc['D'] * FPS))
    fig, ax = new_fig()
    os.makedirs(OUT + 'segments', exist_ok=True)
    w = imageio_ffmpeg.write_frames(OUT + f'segments/s{i:02d}.mp4', (W, H), fps=FPS, codec='libx264',
                                    pix_fmt_in='rgb24', pix_fmt_out='yuv420p', quality=None, bitrate=None,
                                    macro_block_size=8, ffmpeg_log_level='error',
                                    output_params=['-crf', '18', '-preset', 'medium'])
    w.send(None)
    for f in range(n):
        draw_frame(ax, sc, f / FPS)
        w.send(grab(fig).tobytes())
    w.close()
    plt.close(fig)
    return i, n


def tts():
    import soundfile as sf
    from kokoro_onnx import Kokoro
    kdir = os.environ.get('KOKORO_DIR', os.path.expanduser('~/.cache/kokoro')).rstrip('/') + '/'
    voice, speed = os.environ.get('VOICE', 'af_heart'), float(os.environ.get('SPEED', '1.0'))
    k = Kokoro(kdir + 'kokoro-v1.0.fp16.onnx', kdir + 'voices-v1.0.bin')
    os.makedirs(OUT + 'audio', exist_ok=True)
    dur, text, sr = {}, {}, 24000
    for sc in SC:
        for j, cap in enumerate(sc['caps']):
            key, s_txt = f"{sc['name']}_{j}", say(sc['name'], j, cap_text(cap))
            s, sr = k.create(s_txt, voice=voice, speed=speed, lang='en-us')
            loud = np.where(np.abs(s) > 0.01)[0]      # trim edge silence; GAP sets the pauses
            s = s[max(0, loud[0] - 600): loud[-1] + 1800]
            sf.write(OUT + f'audio/{key}.wav', s, sr)
            dur[key], text[key] = len(s) / sr, s_txt
            print(f'{key:14s} {dur[key]:5.2f}s  {s_txt}', flush=True)
    json.dump({'sr': sr, 'dur': dur, 'text': text}, open(_TJ, 'w'), indent=1)


def main():
    cmd = sys.argv[2] if len(sys.argv) > 2 else 'info'
    if cmd == 'info':
        tot = 0
        for i, sc in enumerate(SC):
            tot += sc['D']
            print(f"{i:2d} {sc['name']:14s} {sc['D']:6.1f}s  caps={len(sc['caps'])}")
        print(f'total {tot:.1f}s  ({"narrated" if AUDIO else "no audio yet: reading-speed estimate"})')
    elif cmd == 'still':
        i = int(sys.argv[3])
        fig, ax = new_fig()
        os.makedirs(OUT + 'stills', exist_ok=True)
        for t in map(float, sys.argv[4:]):
            draw_frame(ax, SC[i], t)
            p = OUT + f'stills/s{i:02d}_{t:05.1f}.png'
            Image.fromarray(grab(fig)).save(p)
            print(p)
    elif cmd == 'tts':
        tts()
    elif cmd == 'check':
        bad = [f"{sc['name']}_{j}" for sc in SC for j in range(len(sc['caps'])) if not audio_ok(sc, j)]
        print('audio OK for all captions' if not bad else f'missing or stale audio (re-run tts): {bad}')
        sys.exit(1 if bad else 0)
    elif cmd == 'render':
        import multiprocessing as mp
        nw = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        idx = [int(k) for k in sys.argv[4].split(',')] if len(sys.argv) > 4 else range(len(SC))
        with mp.Pool(nw) as pool:
            for i, n in pool.imap_unordered(render_scene, sorted(idx, key=lambda k: -SC[k]['D'])):
                print(f'scene {i} done, {n} frames', flush=True)
    elif cmd == 'concat':
        lst = OUT + 'segments/list.txt'
        with open(lst, 'w') as fh:
            for i in range(len(SC)):
                fh.write(f"file '{OUT}segments/s{i:02d}.mp4'\n")
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        out = PROJ + NAME + '.mp4'
        subprocess.run([ff, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
                        '-movflags', '+faststart', out], check=True)
        if AUDIO:
            import soundfile as sf
            sr = AUDIO['sr']
            starts, t0 = [], 0.0
            for sc in SC:
                starts.append(t0)
                t0 += int(round(sc['D'] * FPS)) / FPS
            track = np.zeros(int(t0 * sr) + sr, dtype=np.float32)
            for i, sc in enumerate(SC):
                for j, (_, c0, _) in enumerate(sc['capt']):
                    if audio_ok(sc, j):
                        w, _ = sf.read(OUT + f"audio/{sc['name']}_{j}.wav", dtype='float32')
                        k0 = int((starts[i] + c0) * sr)
                        track[k0:k0 + len(w)] += w
            track = track[:int(t0 * sr)]
            track *= 0.9 / max(1e-6, np.abs(track).max())
            sf.write(OUT + 'audio/track.wav', track, sr)
            tmp = out + '.tmp.mp4'
            subprocess.run([ff, '-y', '-loglevel', 'error', '-i', out, '-i', OUT + 'audio/track.wav', '-map', '0:v',
                            '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest',
                            '-movflags', '+faststart', tmp], check=True)
            os.replace(tmp, out)
        print(out)


if __name__ == '__main__':
    main()
