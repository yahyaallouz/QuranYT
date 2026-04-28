import os
import requests
import subprocess
import random
import json
import textwrap
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
USED_BGS_PATH = os.path.join(DATA_DIR, "data", "used_backgrounds.json")

# Avoid reusing a background within the last N videos
BG_MEMORY = 20

os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Detect the best PIL layout engine available.
# RAQM (via libraqm + HarfBuzz) handles Arabic OpenType shaping natively —
# tashkeel, ligatures, RTL — all perfect.  Falls back to BASIC if unavailable.
# ---------------------------------------------------------------------------
try:
    _LAYOUT = ImageFont.Layout.RAQM
    print("[font] RAQM layout engine available ✓ (HarfBuzz Arabic shaping)")
except AttributeError:
    _LAYOUT = ImageFont.Layout.BASIC
    print("[font] RAQM not available, using BASIC layout")


def get_audio_duration(mp3_path):
    """Return duration in seconds using mutagen (pure Python, no ffprobe needed)."""
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
    """Find Amiri or another Arabic-capable font on the system."""
    import platform
    import glob

    if platform.system() == "Windows":
        for p in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/times.ttf"]:
            if os.path.exists(p):
                print(f"[font] Using: {p}")
                return p
    else:
        # Search for Amiri (installed via apt: fonts-hosny-amiri)
        hits = glob.glob("/usr/share/fonts/**/Amiri*.ttf", recursive=True)
        if hits:
            # Prefer Regular
            for f in sorted(hits):
                if "Regular" in f:
                    print(f"[font] Using: {f}")
                    return f
            print(f"[font] Using: {hits[0]}")
            return hits[0]
        # Fallback
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


def fetch_pexels_video(api_key):
    """Fetch and download a nature portrait video from Pexels."""
    print("Fetching background video from Pexels...")
    headers = {"Authorization": api_key}
    queries = ["nature", "ocean waves", "forest", "night sky", "mountains",
               "rain", "river", "sunset"]
    url = (f"https://api.pexels.com/videos/search"
           f"?query={random.choice(queries)}&orientation=portrait&size=medium&per_page=20")

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise Exception(f"Pexels API error: {r.status_code} {r.text}")

    videos = r.json().get("videos", [])

    used_bgs = []
    if os.path.exists(USED_BGS_PATH):
        with open(USED_BGS_PATH, "r") as f:
            used_bgs = json.load(f)
    used_bgs = used_bgs[-BG_MEMORY:]

    available = [v for v in videos if v["id"] not in used_bgs]
    if not available:
        available = videos

    selected = random.choice(available)
    used_bgs.append(selected["id"])
    with open(USED_BGS_PATH, "w") as f:
        json.dump(used_bgs, f)

    video_files = [vf for vf in selected["video_files"] if vf.get("height")]
    video_files.sort(key=lambda x: x["height"], reverse=True)
    best_link = video_files[0]["link"]

    vid_path = os.path.join(ASSETS_DIR, "bg.mp4")
    print(f"Downloading Pexels video ID {selected['id']}...")
    req = requests.get(best_link, timeout=60)
    with open(vid_path, "wb") as f:
        f.write(req.content)
    return vid_path


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
#  TEXT OVERLAY — rendered as a transparent PNG via PIL
#  With RAQM: HarfBuzz handles Arabic shaping + tashkeel natively.
#  Without RAQM: falls back to arabic_reshaper + python-bidi.
# ────────────────────────────────────────────────────────────────────────────

def _reshape_arabic(text):
    """Reshape + bidi-reorder Arabic text for display.
    With RAQM this is a no-op (HarfBuzz handles everything).
    Without RAQM we need arabic_reshaper + python-bidi."""
    if _LAYOUT == ImageFont.Layout.RAQM:
        # RAQM handles shaping + bidi natively — pass raw text
        return text
    else:
        # Fallback: use arabic_reshaper + bidi
        try:
            from arabic_reshaper import ArabicReshaper
            from bidi.algorithm import get_display
            reshaper = ArabicReshaper(configuration={
                'delete_harakat': False,
                'delete_tatweel': False,
            })
            return get_display(reshaper.reshape(text))
        except ImportError:
            return text


def _wrap_arabic(text, font, draw, max_width):
    """Wrap Arabic text on WORD boundaries using pixel-width measurement.
    Each line is processed independently to preserve word integrity."""
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
            # Finalize current line
            final = ' '.join(current_words)
            lines.append(_reshape_arabic(final))
            current_words = [word]
        else:
            current_words.append(word)

    if current_words:
        final = ' '.join(current_words)
        lines.append(_reshape_arabic(final))

    return lines


def render_text_overlay(arabic_text, explanation_text, ref_text, font_path):
    """Render Arabic + English text onto a transparent 1080×1920 PNG.
    Uses RAQM/HarfBuzz for native Arabic shaping when available."""
    print("Rendering text overlay image with PIL...")
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Arabic ──────────────────────────────────────────────────
    ar_size = 72
    ar_font = ImageFont.truetype(font_path, ar_size, layout_engine=_LAYOUT)
    max_w = W - 140  # 70 px margin each side

    # Process each ayah part (supports 2-ayah mode)
    ayah_parts = arabic_text.split("\n")
    ar_lines = []
    for part in ayah_parts:
        ar_lines.extend(_wrap_arabic(part, ar_font, draw, max_w))

    # Generous line height for tashkeel (diacritics above + below)
    lh_ar = int(ar_size * 2.4)
    total_h = len(ar_lines) * lh_ar
    y0 = int(H * 0.28) - total_h // 2

    for i, line in enumerate(ar_lines):
        y = y0 + i * lh_ar
        bbox = draw.textbbox((0, 0), line, font=ar_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        # Shadow
        draw.text((x + 3, y + 3), line, font=ar_font, fill=(0, 0, 0, 190))
        # Main
        draw.text((x, y), line, font=ar_font, fill=(255, 255, 255, 255))

    # ── English explanation ─────────────────────────────────────
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

    # ── Surah reference ─────────────────────────────────────────
    ref_size = 32
    try:
        ref_font = eng_font.font_variant(size=ref_size)
    except Exception:
        ref_font = ImageFont.truetype(font_path, ref_size)
    ref_bbox = draw.textbbox((0, 0), ref_text, font=ref_font)
    ref_x = (W - (ref_bbox[2] - ref_bbox[0])) // 2
    ref_y = int(H * 0.88)
    draw.text((ref_x + 2, ref_y + 2), ref_text, font=ref_font, fill=(0, 0, 0, 120))
    draw.text((ref_x, ref_y), ref_text, font=ref_font, fill=(180, 180, 180, 255))

    overlay_path = os.path.join(ASSETS_DIR, "text_overlay.png")
    img.save(overlay_path, "PNG")
    print(f"Text overlay saved: {overlay_path}")
    return overlay_path


# ────────────────────────────────────────────────────────────────────────────
#  MAIN VIDEO GENERATION PIPELINE
# ────────────────────────────────────────────────────────────────────────────

def generate_video(arabic_text, explanation_text, ref_text, audio_url, audio_url_2=None):
    """Full pipeline: background + audio + text overlay → final_short.mp4"""
    pexels_key = os.environ.get("PEXELS_API_KEY",
                                "GuLw0mgXERqcuzZeHixe676PraSOXxdWfJF3ABoN8cPzHSJOVWTXsOXJ")
    if not pexels_key:
        raise Exception("PEXELS_API_KEY environment variable is missing")

    font_path = get_arabic_font_path()
    bg_video = fetch_pexels_video(pexels_key)

    # Audio (already downloaded by main.py for duration check)
    audio_file = os.path.join(ASSETS_DIR, "audio.mp3")
    if not os.path.exists(audio_file):
        download_audio_for_check(audio_url)

    if audio_url_2:
        audio_file = concatenate_audio(audio_file, audio_url_2)

    # Render text as transparent PNG (bulletproof Arabic rendering)
    overlay_path = render_text_overlay(arabic_text, explanation_text, ref_text, font_path)

    out_file = os.path.join(ASSETS_DIR, "final_short.mp4")
    if os.path.exists(out_file):
        os.remove(out_file)

    print("Running FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", bg_video,
        "-i", audio_file,
        "-i", overlay_path,
        "-filter_complex",
        "[0:v]colorlevels=romax=0.65:gomax=0.65:bomax=0.65,"
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"
        "[bg][2:v]overlay=0:0[out]",
        "-map", "[out]",
        "-map", "1:a",
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-t", "30",
        "-shortest",
        out_file
    ]

    print("Executing:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=DATA_DIR)
    print(f"Video generated at {out_file}")
    return out_file
