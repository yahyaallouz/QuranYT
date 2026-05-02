import os
import requests
import subprocess
import random
import json
import textwrap
from PIL import Image, ImageDraw, ImageFont
from variation_engine import (
    load_history, save_history, pick_unique, record,
    pick_background_query, get_subtitle_offset, get_ken_burns_params,
)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
USED_BGS_PATH = os.path.join(DATA_DIR, "data", "used_backgrounds.json")

BG_MEMORY = 20  # avoid reusing a Pexels video within the last N videos

os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Detect the best PIL layout engine available.
# Check if the actual libraqm C library is installed (not just the enum).
# ---------------------------------------------------------------------------
try:
    from PIL import features as _pil_features
    _RAQM_AVAILABLE = _pil_features.check("raqm")
except Exception:
    _RAQM_AVAILABLE = False

if _RAQM_AVAILABLE:
    _LAYOUT = ImageFont.Layout.RAQM
    print("[font] RAQM layout engine available ✓ (HarfBuzz Arabic shaping)")
else:
    _LAYOUT = ImageFont.Layout.BASIC
    print("[font] RAQM not available — using arabic_reshaper + bidi for shaping")


def get_audio_duration(mp3_path):
    """Return duration in seconds using mutagen (pure Python, no ffprobe)."""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(mp3_path)
        return audio.info.length
    except Exception:
        return 0.0


def download_audio_for_check(audio_url):
    """Download primary audio to assets/audio.mp3 and return path."""
    mp3_path = os.path.join(ASSETS_DIR, "audio.mp3")
    r = requests.get(audio_url, timeout=30)
    r.raise_for_status()
    with open(mp3_path, "wb") as f:
        f.write(r.content)
    return mp3_path


def get_arabic_font_path():
    """Download and return the Amiri font for proper Qur'anic Arabic rendering.
    Amiri has full tashkeel/diacritics support and works with RAQM/HarfBuzz."""
    import platform
    import glob

    # Try to use a cached Amiri font first
    amiri_path = os.path.join(ASSETS_DIR, "Amiri-Regular.ttf")
    if os.path.exists(amiri_path):
        print(f"[font] Using cached Amiri: {amiri_path}")
        return amiri_path

    # Check system-installed Amiri (Linux, installed via fonts-hosny-amiri)
    if platform.system() != "Windows":
        hits = glob.glob("/usr/share/fonts/**/Amiri*.ttf", recursive=True)
        if hits:
            for f in sorted(hits):
                if "Regular" in f:
                    print(f"[font] Using system Amiri: {f}")
                    return f
            print(f"[font] Using system Amiri: {hits[0]}")
            return hits[0]

    # Auto-download Amiri font (works on all platforms)
    print("[font] Downloading Amiri font for Arabic rendering...")
    try:
        url = "https://github.com/aliftype/amiri/releases/download/1.000/Amiri-1.000.zip"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        import zipfile
        import io
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for name in zf.namelist():
                if name.endswith("Amiri-Regular.ttf"):
                    with open(amiri_path, "wb") as f:
                        f.write(zf.read(name))
                    print(f"[font] Downloaded Amiri: {amiri_path}")
                    return amiri_path
    except Exception as e:
        print(f"[font] Amiri download failed: {e}")

    # Fallback: try system Arabic fonts
    if platform.system() == "Windows":
        for p in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/times.ttf"]:
            if os.path.exists(p):
                print(f"[font] Fallback: {p}")
                return p
    else:
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
            if os.path.exists(p):
                print(f"[font] Fallback: {p}")
                return p

    raise Exception("No Arabic-capable font found!")


def download_english_font():
    """Download a clean sans-serif font for English text."""
    font_path = os.path.join(ASSETS_DIR, "Roboto-Regular.ttf")
    if os.path.exists(font_path):
        return font_path
    try:
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto%5Bwdth%2Cwght%5D.ttf"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(font_path, "wb") as f:
            f.write(r.content)
        return font_path
    except Exception:
        return None


def fetch_pexels_video(api_key, history=None):
    """Fetch and download a nature portrait video from Pexels."""
    if not api_key:
        raise Exception("PEXELS_API_KEY environment variable is missing!")

    print("Fetching background video from Pexels...")

    if history is None:
        history = load_history()

    query = pick_background_query(history=history, memory=BG_MEMORY)
    record(history, "bg_queries", query, memory=BG_MEMORY)
    print(f"[bg] Using query: {query}")

    headers = {"Authorization": api_key}
    url = (f"https://api.pexels.com/videos/search"
           f"?query={query}&orientation=portrait&size=medium&per_page=20")

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise Exception(f"Pexels API error: {r.status_code} {r.text}")

    videos = r.json().get("videos", [])

    # Load used background IDs
    used_bgs = []
    if os.path.exists(USED_BGS_PATH):
        try:
            with open(USED_BGS_PATH, "r") as f:
                used_bgs = json.load(f)
        except (json.JSONDecodeError, Exception):
            used_bgs = []
    used_bgs = used_bgs[-BG_MEMORY:]

    available = [v for v in videos if v["id"] not in used_bgs]
    if not available:
        available = videos

    selected = random.choice(available)
    used_bgs.append(selected["id"])
    with open(USED_BGS_PATH, "w") as f:
        json.dump(used_bgs, f)

    record(history, "backgrounds", selected["id"], memory=BG_MEMORY)

    video_files = [vf for vf in selected["video_files"] if vf.get("height")]
    video_files.sort(key=lambda x: x["height"], reverse=True)
    best_link = video_files[0]["link"]

    vid_path = os.path.join(ASSETS_DIR, "bg.mp4")
    print(f"Downloading Pexels video ID {selected['id']}...")
    req = requests.get(best_link, timeout=60)
    with open(vid_path, "wb") as f:
        f.write(req.content)
    return vid_path, history


def concatenate_audio(audio1_path, audio2_url):
    """Download second audio and concatenate both into audio_combined.mp3."""
    audio2_path = os.path.join(ASSETS_DIR, "audio2.mp3")
    print("Downloading second ayah audio...")
    r = requests.get(audio2_url, timeout=30)
    r.raise_for_status()
    with open(audio2_path, "wb") as f:
        f.write(r.content)

    combined_path = os.path.join(ASSETS_DIR, "audio_combined.mp3")
    concat_list = os.path.join(ASSETS_DIR, "concat.txt")
    with open(concat_list, "w") as f:
        f.write(f"file '{audio1_path}'\n")
        f.write(f"file '{audio2_path}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", combined_path
    ], check=True, capture_output=True)

    os.remove(concat_list)
    return combined_path


# ────────────────────────────────────────────────────────────────────────────
#  TEXT OVERLAY — rendered as transparent PNGs via PIL
# ────────────────────────────────────────────────────────────────────────────

def _reshape_arabic(text):
    """Reshape + bidi-reorder Arabic text for display.
    With RAQM (libraqm installed): HarfBuzz handles shaping natively — pass raw text.
    Without RAQM: use arabic_reshaper + python-bidi for proper RTL connected letters."""
    if _RAQM_AVAILABLE:
        return text
    else:
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            reshaper_config = {
                'delete_harakat': False,
                'delete_tatweel': False,
            }
            reshaper = arabic_reshaper.ArabicReshaper(configuration=reshaper_config)
            reshaped = reshaper.reshape(text)
            return get_display(reshaped)
        except ImportError:
            print("[warning] arabic_reshaper/python-bidi not installed — Arabic may render incorrectly")
            return text


def _wrap_arabic(text, font, draw, max_width):
    """Wrap Arabic text on WORD boundaries using pixel-width measurement."""
    words = text.strip().split()
    if not words:
        return [text]

    lines = []
    current_words = []

    for word in words:
        test_line = ' '.join(current_words + [word])
        display_line = _reshape_arabic(test_line)
        bbox = draw.textbbox((0, 0), display_line, font=font)
        line_w = bbox[2] - bbox[0]

        if line_w > max_width and current_words:
            final = ' '.join(current_words)
            lines.append(_reshape_arabic(final))
            current_words = [word]
        else:
            current_words.append(word)

    if current_words:
        final = ' '.join(current_words)
        lines.append(_reshape_arabic(final))

    return lines


def render_hook_overlay(hook_text, font_path):
    """Render the hook text with a soft dark gradient backdrop.
    Positioned at top-third to avoid Arabic subtitle zone.
    Full opacity from frame 0 — no fade-in delay."""
    print(f"Rendering hook overlay: '{hook_text}'")
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    eng_font_path = download_english_font()
    hook_size = 54
    try:
        hook_font = ImageFont.truetype(eng_font_path or font_path, hook_size)
    except Exception:
        hook_font = ImageFont.truetype(font_path, hook_size)

    # Wrap if needed
    lines = textwrap.wrap(hook_text, width=26)
    lh = int(hook_size * 1.7)
    total_h = len(lines) * lh

    # Position: top-third of screen (well above Arabic zone at ~40%)
    text_center_y = int(H * 0.22)
    y0 = text_center_y - total_h // 2

    # Soft gradient backdrop (dark → transparent, top-down)
    gradient_top = max(0, y0 - 80)
    gradient_bottom = y0 + total_h + 80
    for gy in range(gradient_top, min(gradient_bottom, H)):
        # Smooth falloff from center of text
        dist_from_center = abs(gy - text_center_y) / (total_h // 2 + 80)
        alpha = int(120 * max(0, 1.0 - dist_from_center ** 1.5))
        draw.rectangle([(0, gy), (W, gy + 1)], fill=(0, 0, 0, alpha))

    for i, line in enumerate(lines):
        y = y0 + i * lh
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        # Double shadow for strong readability
        draw.text((x + 3, y + 3), line, font=hook_font, fill=(0, 0, 0, 230))
        draw.text((x + 1, y + 1), line, font=hook_font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=hook_font, fill=(255, 255, 255, 255))

    path = os.path.join(ASSETS_DIR, "hook_overlay.png")
    img.save(path, "PNG")
    return path


def render_arabic_overlay(arabic_text, ref_text, font_path, subtitle_offset=0):
    """Render Arabic ayah + surah reference onto a transparent 1080×1920 PNG.
    ⚠️ LOCKED — Arabic rendering must remain pixel-identical. Do NOT modify."""
    print("Rendering Arabic overlay (LOCKED rendering)...")
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Arabic (LOCKED — do not change font, size, position, style) ──
    ar_size = 72
    ar_font = ImageFont.truetype(font_path, ar_size, layout_engine=_LAYOUT)
    max_w = W - 140

    ayah_parts = arabic_text.split("\n")
    ar_lines = []
    for part in ayah_parts:
        ar_lines.extend(_wrap_arabic(part, ar_font, draw, max_w))

    lh_ar = int(ar_size * 2.4)
    total_h = len(ar_lines) * lh_ar
    y0 = int(H * 0.28) - total_h // 2 + subtitle_offset

    for i, line in enumerate(ar_lines):
        y = y0 + i * lh_ar
        bbox = draw.textbbox((0, 0), line, font=ar_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x + 3, y + 3), line, font=ar_font, fill=(0, 0, 0, 190))
        draw.text((x, y), line, font=ar_font, fill=(255, 255, 255, 255))

    # ── Surah reference (LOCKED) ─────────────────────────────────
    eng_font_path = download_english_font()
    ref_size = 32
    try:
        ref_font = ImageFont.truetype(eng_font_path or font_path, ref_size)
    except Exception:
        ref_font = ImageFont.truetype(font_path, ref_size)
    ref_bbox = draw.textbbox((0, 0), ref_text, font=ref_font)
    ref_x = (W - (ref_bbox[2] - ref_bbox[0])) // 2
    ref_y = int(H * 0.88)
    draw.text((ref_x + 2, ref_y + 2), ref_text, font=ref_font, fill=(0, 0, 0, 120))
    draw.text((ref_x, ref_y), ref_text, font=ref_font, fill=(180, 180, 180, 255))

    overlay_path = os.path.join(ASSETS_DIR, "arabic_overlay.png")
    img.save(overlay_path, "PNG")
    print(f"Arabic overlay saved: {overlay_path}")
    return overlay_path


def render_explanation_overlay(explanation_text, font_path):
    """Render English explanation onto a transparent 1080×1920 PNG.
    Positioned at 60% height, separate from Arabic zone."""
    print(f"Rendering explanation overlay: '{explanation_text[:50]}...'")
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    eng_font_path = download_english_font()
    eng_size = 36
    try:
        eng_font = ImageFont.truetype(eng_font_path or font_path, eng_size)
    except Exception:
        eng_font = ImageFont.truetype(font_path, eng_size)

    eng_lines = textwrap.wrap(explanation_text, width=40)
    lh_en = int(eng_size * 1.5)
    en_y0 = int(H * 0.60)

    for i, line in enumerate(eng_lines):
        y = en_y0 + i * lh_en
        bbox = draw.textbbox((0, 0), line, font=eng_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x + 2, y + 2), line, font=eng_font, fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=eng_font, fill=(230, 230, 230, 255))

    overlay_path = os.path.join(ASSETS_DIR, "explanation_overlay.png")
    img.save(overlay_path, "PNG")
    print(f"Explanation overlay saved: {overlay_path}")
    return overlay_path


# ────────────────────────────────────────────────────────────────────────────
#  SILENCE PADDING
# ────────────────────────────────────────────────────────────────────────────

def generate_silence(duration_sec):
    """Generate a short silence audio file."""
    silence_path = os.path.join(ASSETS_DIR, "silence.mp3")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(duration_sec),
        "-c:a", "libmp3lame", "-q:a", "9",
        silence_path
    ], check=True, capture_output=True)
    return silence_path


def prepend_silence(audio_path, silence_sec):
    """Prepend silence to the audio file for hook phase."""
    silence_path = generate_silence(silence_sec)
    padded_path = os.path.join(ASSETS_DIR, "audio_padded.mp3")
    concat_list = os.path.join(ASSETS_DIR, "pad_concat.txt")
    with open(concat_list, "w") as f:
        f.write(f"file '{silence_path}'\n")
        f.write(f"file '{audio_path}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", padded_path
    ], check=True, capture_output=True)

    os.remove(concat_list)
    return padded_path


# ────────────────────────────────────────────────────────────────────────────
#  MAIN VIDEO GENERATION PIPELINE
# ────────────────────────────────────────────────────────────────────────────

def generate_video(arabic_text, explanation_text, ref_text, audio_url,
                   audio_url_2=None, hook_text=None, history=None):
    """Full pipeline: background + audio + 3 overlay layers → final_short.mp4

    Timing structure:
      0:00 → hook_end        Hook overlay (2.3–2.8s, randomized)
      hook_end → meaning_end English meaning overlay (4–5s total from start)
      meaning_end+pad →      Arabic subtitle + recitation audio begins
      last 0.5s              Fade-out for loop-friendly ending
    """
    pexels_key = os.environ.get("PEXELS_API_KEY")
    if not pexels_key:
        raise Exception("PEXELS_API_KEY environment variable is missing!")

    if history is None:
        history = load_history()

    font_path = get_arabic_font_path()
    bg_video, history = fetch_pexels_video(pexels_key, history=history)

    # Audio (already downloaded by main.py for duration check)
    audio_file = os.path.join(ASSETS_DIR, "audio.mp3")
    if not os.path.exists(audio_file):
        download_audio_for_check(audio_url)

    if audio_url_2:
        audio_file = concatenate_audio(audio_file, audio_url_2)

    # ── Timing calculations ──────────────────────────────────────
    hook_duration = round(random.uniform(2.3, 2.8), 2)
    meaning_end = round(random.uniform(4.0, 5.0), 1)  # meaning visible until this time
    silence_pad = round(random.uniform(0.3, 0.6), 2)  # gap between meaning and recitation
    recitation_start = round(meaning_end + silence_pad, 2)

    print(f"[timing] Hook: 0–{hook_duration}s | "
          f"Meaning: 0–{meaning_end}s | "
          f"Silence pad: {silence_pad}s | "
          f"Recitation starts: {recitation_start}s")

    # Prepend silence so audio aligns with recitation_start
    audio_file = prepend_silence(audio_file, recitation_start)

    # Get audio duration (with silence prepended)
    audio_duration = get_audio_duration(audio_file)
    # Target 17–23s total
    video_duration = min(max(audio_duration + 2, 17), 23)
    print(f"[timing] Audio (padded): {audio_duration:.1f}s → Video: {video_duration:.1f}s")

    # Subtitle offset (±20px safe zone)
    sub_offset = get_subtitle_offset()

    # Ken Burns (logged for reference)
    kb = get_ken_burns_params()
    print(f"[fx] Ken Burns: {kb['direction']} zoom {kb['zoom_start']}→{kb['zoom_end']}")

    # ── Render overlays ──────────────────────────────────────────
    arabic_overlay = render_arabic_overlay(arabic_text, ref_text,
                                           font_path, subtitle_offset=sub_offset)
    explanation_overlay = render_explanation_overlay(explanation_text, font_path)

    hook_overlay = None
    if hook_text:
        hook_overlay = render_hook_overlay(hook_text, font_path)

    out_file = os.path.join(ASSETS_DIR, "final_short.mp4")
    if os.path.exists(out_file):
        os.remove(out_file)

    # ── Build FFmpeg filter chain ────────────────────────────────
    print("Running FFmpeg...")

    fade_start = round(video_duration - 0.5, 2)
    filters = []

    # Background: darken, scale, crop, fade-out at end
    filters.append(
        f"[0:v]colorlevels=romax=0.55:gomax=0.55:bomax=0.55,"
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"fade=t=out:st={fade_start}:d=0.5[bg]"
    )

    # Layer 1: Arabic subtitle — appears when recitation starts
    filters.append(
        f"[bg][2:v]overlay=0:0:enable='gte(t,{recitation_start})'[v1]"
    )

    # Layer 2: English meaning — visible from 0 to meaning_end
    filters.append(
        f"[v1][3:v]overlay=0:0:enable='lte(t,{meaning_end})'[v2]"
    )

    if hook_overlay:
        # Layer 3: Hook — visible from frame 0 to hook_duration
        filters.append(
            f"[v2][4:v]overlay=0:0:enable='lte(t,{hook_duration})'[out]"
        )
        out_label = "[out]"
    else:
        out_label = "[v2]"

    # Audio normalization via loudnorm
    filters.append(
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[anorm]"
    )

    filter_complex = ";".join(filters)

    # Inputs: [0]=bg, [1]=audio, [2]=arabic, [3]=explanation, [4]=hook (optional)
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", bg_video,
        "-i", audio_file,
        "-i", arabic_overlay,
        "-i", explanation_overlay,
    ]

    if hook_overlay:
        cmd.extend(["-i", hook_overlay])

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", out_label,
        "-map", "[anorm]",
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-t", str(video_duration),
        "-shortest",
        out_file
    ])

    print("Executing:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=DATA_DIR)
    print(f"Video generated at {out_file}")
    return out_file, history

