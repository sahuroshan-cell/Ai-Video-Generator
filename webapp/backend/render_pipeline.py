"""Storyboard -> real talking-head video.

Piper TTS narration + Wav2Lip photoreal lip-sync, composited as a circular
picture-in-picture inside Reel-Forge-style animated scene templates
(title / bullets / flow / stat / outro), rendered frame-by-frame with
Pillow and muxed with ffmpeg. No network calls at render time -- everything
needed (Wav2Lip weights, Piper voices) is baked into the Docker image at
build time.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont

WAV2LIP_DIR = os.environ.get("WAV2LIP_DIR", "/opt/wav2lip/repo")
VOICES_DIR = os.environ.get("VOICES_DIR", "/opt/wav2lip/voices")
PYTHON_BIN = sys.executable

VOICES = {
    "en": f"{VOICES_DIR}/en_US-amy-medium.onnx",
    "hi": f"{VOICES_DIR}/hi_IN-pratham-medium.onnx",
}

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_BOLD, F_REG = f"{FONT_DIR}/DejaVuSans-Bold.ttf", f"{FONT_DIR}/DejaVuSans.ttf"

W, H, FPS = 1280, 720, 25
PIP_R = 92
PIP_CX, PIP_CY = W - PIP_R - 40, H - 210

PAL = {
    "bg": (22, 26, 36), "surface2": (38, 45, 64),
    "text": (237, 240, 247), "dim": (154, 162, 189),
    "amber": (255, 176, 32), "teal": (79, 209, 197),
}

KIND_LABEL = {"title": "Title card", "bullets": "Bullet list", "flow": "Process flow",
              "stat": "Stat / quote", "outro": "Outro"}


class RenderError(RuntimeError):
    pass


def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RenderError(f"{' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def _ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap_text(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def _make_base_bg():
    img = Image.new("RGB", (W, H), PAL["bg"])
    d = ImageDraw.Draw(img)
    cx, cy, maxr = W * 0.5, H * 0.42, W * 0.75
    for i in range(40, 0, -1):
        r, t = maxr * i / 40, i / 40
        col = tuple(int(PAL["surface2"][k] * t + PAL["bg"][k] * (1 - t)) for k in range(3))
        d.ellipse([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], fill=col)
    for side in (24, W - 24):
        y = 20
        while y < H:
            d.ellipse([side - 8, y - 8, side + 8, y + 8], fill=PAL["surface2"])
            y += 34
    return img.convert("RGBA")


_BASE_BG = None


def _base_bg():
    global _BASE_BG
    if _BASE_BG is None:
        _BASE_BG = _make_base_bg()
    return _BASE_BG


def _text_alpha(frame, xy, text, fnt, rgb, alpha, anchor="la"):
    if alpha <= 0.003 or not text:
        return
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=fnt, fill=rgb + (max(0, min(255, int(alpha * 255))),), anchor=anchor)
    frame.alpha_composite(layer)


def _ring(frame, cx, cy, r, rgb, alpha=1.0):
    if alpha <= 0.003:
        return
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    a = max(0, min(255, int(alpha * 255)))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb + (a,))
    frame.alpha_composite(layer)


def _timecode_badge(frame, label):
    _text_alpha(frame, (46, 22), label, _font(F_BOLD, 15), PAL["dim"], 1.0)


def _caption_band(frame, text):
    if not text:
        return
    fnt = _font(F_BOLD, 24)
    lines = _wrap_text(ImageDraw.Draw(frame), text, fnt, W - 140)[:3]
    line_h, pad = 32, 16
    box_h = len(lines) * line_h + pad * 2 - 6
    y0 = H - 20 - box_h
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle([0, y0, W, y0 + box_h], fill=(6, 8, 14, 158))
    frame.alpha_composite(layer)
    ty = y0 + pad + 6
    for l in lines:
        _text_alpha(frame, (W / 2, ty), l, fnt, (245, 247, 251), 1.0, anchor="ma")
        ty += line_h


def _draw_title(frame, s, t):
    e = _ease_out_cubic(_clamp01(t / 0.5))
    _text_alpha(frame, (W / 2, H * 0.30), "REEL FORGE — TITLE", _font(F_BOLD, 16), PAL["amber"], e, "mm")
    fnt = _font(F_BOLD, 56)
    lines = _wrap_text(ImageDraw.Draw(frame), s["heading"], fnt, W * 0.62)
    ly = H * 0.38 - (len(lines) - 1) * 32
    for line in lines:
        _text_alpha(frame, (W / 2, ly), line, fnt, PAL["text"], e, "mm")
        ly += 64
    barw = int(220 * e)
    if barw > 0:
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle([W / 2 - barw / 2, ly + 4, W / 2 + barw / 2, ly + 9], fill=PAL["teal"] + (255,))
        frame.alpha_composite(layer)


def _draw_bullets(frame, s, t):
    fnt_h, fnt_b = _font(F_BOLD, 38), _font(F_REG, 27)
    head_e = _ease_out_cubic(_clamp01(t / 0.3))
    _text_alpha(frame, (100, 116), s["heading"], fnt_h, PAL["text"], head_e, "lm")
    if head_e > 0:
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle([100, 150, 100 + 70 * head_e, 155], fill=PAL["teal"] + (255,))
        frame.alpha_composite(layer)
    bullets = s.get("bullets") or []
    n = max(1, len(bullets))
    per = 0.6 / n
    for i, b in enumerate(bullets):
        start = 0.28 + i * per
        e = _ease_out_cubic(_clamp01((t - start) / 0.28))
        if e <= 0:
            continue
        y = 230 + i * 82
        dx = (1 - e) * 40
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse([112 + dx - 7, y - 16, 112 + dx + 7, y - 2], fill=PAL["amber"] + (int(e * 255),))
        frame.alpha_composite(layer)
        _text_alpha(frame, (140 + dx, y), b, fnt_b, PAL["text"], e, "lm")


def _draw_flow(frame, s, t):
    fnt_h, fnt_n, fnt_l = _font(F_BOLD, 34), _font(F_BOLD, 22), _font(F_REG, 19)
    head_e = _ease_out_cubic(_clamp01(t / 0.25))
    _text_alpha(frame, (100, 90), s["heading"], fnt_h, PAL["text"], head_e, "lm")
    nodes = s.get("nodes") or []
    n = max(1, len(nodes))
    margin, usable = 160, W - 320
    step_x = usable / (n - 1) if n > 1 else 0
    cy, r = H * 0.58, 56
    line_e = _ease_out_cubic(_clamp01((t - 0.25) / 0.3))
    if n > 1 and line_e > 0:
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).line([margin, cy, margin + usable * line_e, cy], fill=(58, 65, 96, 255), width=4)
        frame.alpha_composite(layer)
    for i, label in enumerate(nodes):
        cx = margin + step_x * i
        start = 0.35 + i * 0.12
        e = _ease_out_cubic(_clamp01((t - start) / 0.25))
        if e <= 0:
            continue
        rr = r * e
        col = PAL["amber"] if i % 2 == 0 else PAL["teal"]
        _ring(frame, cx, cy, rr, col, 1.0)
        _text_alpha(frame, (cx, cy), str(i + 1), fnt_n, PAL["bg"], 1.0, "mm")
        lines = _wrap_text(ImageDraw.Draw(frame), label, fnt_l, 190)
        ly = cy + r + 34
        for l in lines:
            _text_alpha(frame, (cx, ly), l, fnt_l, PAL["text"], e, "mm")
            ly += 24


def _draw_stat(frame, s, t):
    fnt_lbl, fnt_big = _font(F_BOLD, 17), _font(F_BOLD, 44)
    e = _ease_out_cubic(_clamp01(t / 0.4))
    _text_alpha(frame, (W / 2, H * 0.36), s["heading"].upper(), fnt_lbl, PAL["teal"], e, "mm")
    lines = _wrap_text(ImageDraw.Draw(frame), s.get("stat") or s["heading"], fnt_big, W * 0.55)
    e2 = _ease_out_cubic(_clamp01((t - 0.15) / 0.4))
    ly = H * 0.36 + 70 - (len(lines) - 1) * 28
    for l in lines:
        _text_alpha(frame, (W / 2, ly), l, fnt_big, PAL["text"], e2, "mm")
        ly += 56


def _draw_outro(frame, s, t):
    fnt = _font(F_BOLD, 40)
    e = _ease_out_cubic(_clamp01(t / 0.5))
    lines = _wrap_text(ImageDraw.Draw(frame), s["heading"], fnt, W * 0.65)
    ly = H * 0.46 - (len(lines) - 1) * 28
    for l in lines:
        _text_alpha(frame, (W / 2, ly), l, fnt, PAL["text"], e, "mm")
        ly += 54
    _text_alpha(frame, (W / 2, ly + 10), "MADE WITH REEL FORGE", _font(F_BOLD, 15), PAL["dim"], e, "mm")


_DRAW = {"title": _draw_title, "bullets": _draw_bullets, "flow": _draw_flow, "stat": _draw_stat, "outro": _draw_outro}


def _wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def _synth(text, lang, out_wav):
    voice = VOICES.get(lang)
    if not voice or not os.path.exists(voice):
        raise RenderError(f"no Piper voice for language '{lang}'")
    p = subprocess.run(["piper", "-m", voice, "-f", out_wav], input=text, text=True, capture_output=True)
    if p.returncode != 0 or not os.path.exists(out_wav):
        raise RenderError(f"piper TTS failed: {p.stderr[-1500:]}")


def _make_circle_mask(path, size):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([1, 1, size - 2, size - 2], fill=255)
    m.save(path)


def _render_bg_video(scene, idx, duration, workdir):
    n_frames = max(1, round(duration * FPS))
    framedir = f"{workdir}/s{idx}_frames"
    os.makedirs(framedir, exist_ok=True)
    accent = PAL["amber"] if idx % 2 == 0 else PAL["teal"]
    for f in range(n_frames):
        t = _clamp01(f / max(1, n_frames - 1))
        frame = _base_bg().copy()
        _DRAW[scene["kind"]](frame, scene, t)
        entrance = _ease_out_cubic(_clamp01(t / 0.12))
        _ring(frame, PIP_CX, PIP_CY, (PIP_R + 6) * (0.9 + 0.1 * entrance), accent, entrance)
        _caption_band(frame, scene["narration"])
        _timecode_badge(frame, f"SCENE {idx + 1} · {KIND_LABEL[scene['kind']]}")
        frame.convert("RGB").save(f"{framedir}/f{f:04d}.png")
    bgvid = f"{workdir}/s{idx}_bg.mp4"
    _run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{framedir}/f%04d.png",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", bgvid])
    return bgvid


def _build_scene(idx, scene, face, lang, mask_path, workdir):
    wav = f"{workdir}/s{idx}_audio.wav"
    _synth(scene["narration"], lang, wav)
    duration = _wav_duration(wav)

    raw_mp4 = f"{workdir}/s{idx}_raw.mp4"
    _run([PYTHON_BIN, "inference.py", "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
          "--face", face, "--audio", wav, "--outfile", raw_mp4], cwd=WAV2LIP_DIR)

    bgvid = _render_bg_video(scene, idx, duration, workdir)

    pip_d = PIP_R * 2 - 8
    final_mp4 = f"{workdir}/s{idx}_final.mp4"
    filt = (
        f"[1:v]crop='min(iw\\,ih)':'min(iw\\,ih)':(iw-min(iw\\,ih))/2:(ih-min(iw\\,ih))/2,"
        f"scale={pip_d}:{pip_d}[pipsq];"
        f"[pipsq][2:v]alphamerge[pipc];"
        f"[0:v][pipc]overlay=x={PIP_CX - pip_d / 2}:y={PIP_CY - pip_d / 2}[outv]"
    )
    _run(["ffmpeg", "-y", "-i", bgvid, "-i", raw_mp4, "-i", mask_path,
          "-filter_complex", filt, "-map", "[outv]", "-map", "1:a",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac",
          "-shortest", final_mp4])
    return final_mp4


def render_video(face_path, language, scenes, out_path, on_progress=None):
    """Render a full storyboard to out_path. Returns out_path.

    face_path: local path to a single-face image (caller crops/composites as needed).
    language: 'en' or 'hi'.
    scenes: list of {kind, heading, bullets?, nodes?, stat?, narration}.
    on_progress(i, n, scene): optional callback invoked before each scene renders.
    """
    if language not in VOICES:
        raise RenderError(f"unsupported language '{language}', expected one of {list(VOICES)}")
    if not scenes:
        raise RenderError("scenes must be a non-empty list")

    workdir = tempfile.mkdtemp(prefix="reelforge_render_")
    pip_d = PIP_R * 2 - 8
    mask_path = f"{workdir}/mask.png"
    _make_circle_mask(mask_path, pip_d)

    clips = []
    for i, scene in enumerate(scenes):
        if on_progress:
            on_progress(i, len(scenes), scene)
        clips.append(_build_scene(i, scene, face_path, language, mask_path, workdir))

    listfile = f"{workdir}/list.txt"
    open(listfile, "w").write("\n".join(f"file '{c}'" for c in clips))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_path])
    return out_path


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    render_video(cfg["face"], cfg["language"], cfg["scenes"], cfg["out"],
                 on_progress=lambda i, n, s: print(f"--- scene {i+1}/{n}: {s['heading']} ({s['kind']}) ---"))
    print("DONE")
