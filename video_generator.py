import os
import requests
import subprocess
import random
import json
import textwrap
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
USED_BGS_PATH = os.path.join(DATA_DIR, "data", "used_backgrounds.json")

# Avoid reusing a background within the last N videos
BG_MEMORY = 20

os.makedirs(ASSETS_DIR, exist_ok=True)


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
    """Find a working Arabic font on the system. No download needed."""
    import platform
    candidates = []
    
    if platform.system() == "Windows":
        # Windows has Arial which supports Arabic
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
        ]
    else:
        # Linux/GitHub Actions — installed via apt: fonts-hosny-amiri
        candidates = [
            "/usr/share/fonts/truetype/hosny-amiri/Amiri-Regular.ttf",
            "/usr/share/fonts/truetype/hosny-amiri/Amiri-Bold.ttf",
            # Ubuntu fallback
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    
    for path in candidates:
        if os.path.exists(path):
            print(f"Using font: {path}")
            return path
    
    raise Exception("No Arabic-capable font found on this system!")


def download_english_font():
    """Download a clean sans-serif font for English text."""
    font_path = os.path.join(ASSETS_DIR, "Roboto-Regular.ttf")
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto%5Bwdth%2Cwght%5D.ttf"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(r.content)
        except Exception:
            return None
    return font_path


def fetch_pexels_video(api_key):
    """Fetch and download a nature portrait video from Pexels."""
    print("Fetching background video from Pexels...")
    headers = {"Authorization": api_key}
    queries = ["nature", "ocean waves", "forest", "night sky", "mountains", "rain", "river", "sunset"]
    url = (
        f"https://api.pexels.com/videos/search"
        f"?query={random.choice(queries)}&orientation=portrait&size=medium&per_page=20"
    )

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


def render_text_overlay(arabic_text, explanation_text, ref_text, font_path):
    """
    Render Arabic + English text onto a transparent 1080x1920 PNG using PIL.
    This bypasses all ASS/libass RTL bugs by using arabic_reshaper + python-bidi.
    """
    print("Rendering text overlay image with PIL...")
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Arabic text ---
    arabic_font_size = 85
    arabic_font = ImageFont.truetype(font_path, arabic_font_size)
    
    # Split multi-ayah text
    ayah_parts = arabic_text.split("\n")
    arabic_lines = []
    for part in ayah_parts:
        # Reshape and reorder Arabic for correct display
        reshaped = arabic_reshaper.reshape(part.strip())
        bidi_text = get_display(reshaped)
        # Wrap long lines (approx 28 chars per line at this font size)
        wrapped = textwrap.wrap(bidi_text, width=28)
        if not wrapped:
            wrapped = [bidi_text]
        arabic_lines.extend(wrapped)

    # Calculate total arabic block height
    line_height_ar = int(arabic_font_size * 1.6)
    total_ar_height = len(arabic_lines) * line_height_ar

    # Start Arabic at roughly 30% from top
    ar_y_start = int(H * 0.28) - total_ar_height // 2

    for i, line in enumerate(arabic_lines):
        y = ar_y_start + i * line_height_ar
        bbox = draw.textbbox((0, 0), line, font=arabic_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2

        # Draw shadow
        draw.text((x + 3, y + 3), line, font=arabic_font, fill=(0, 0, 0, 180))
        # Draw main text
        draw.text((x, y), line, font=arabic_font, fill=(255, 255, 255, 255))

    # --- English explanation text ---
    eng_font_path = download_english_font()
    eng_font_size = 38
    if eng_font_path:
        try:
            eng_font = ImageFont.truetype(eng_font_path, eng_font_size)
        except Exception:
            eng_font = ImageFont.truetype(font_path, eng_font_size)
    else:
        eng_font = ImageFont.truetype(font_path, eng_font_size)

    eng_lines = textwrap.wrap(explanation_text, width=38)
    line_height_en = int(eng_font_size * 1.5)
    en_y_start = int(H * 0.58)

    for i, line in enumerate(eng_lines):
        y = en_y_start + i * line_height_en
        bbox = draw.textbbox((0, 0), line, font=eng_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2

        draw.text((x + 2, y + 2), line, font=eng_font, fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=eng_font, fill=(230, 230, 230, 255))

    # --- Reference text (surah name) ---
    ref_font_size = 34
    ref_font = eng_font.font_variant(size=ref_font_size) if eng_font_path else ImageFont.truetype(font_path, ref_font_size)
    ref_bbox = draw.textbbox((0, 0), ref_text, font=ref_font)
    ref_tw = ref_bbox[2] - ref_bbox[0]
    ref_x = (W - ref_tw) // 2
    ref_y = int(H * 0.88)

    draw.text((ref_x + 2, ref_y + 2), ref_text, font=ref_font, fill=(0, 0, 0, 120))
    draw.text((ref_x, ref_y), ref_text, font=ref_font, fill=(180, 180, 180, 255))

    overlay_path = os.path.join(ASSETS_DIR, "text_overlay.png")
    img.save(overlay_path, "PNG")
    print(f"Text overlay saved: {overlay_path}")
    return overlay_path


def generate_video(arabic_text, explanation_text, ref_text, audio_url, audio_url_2=None):
    """Full pipeline: fetch background, audio, render text overlay, compose via FFmpeg."""
    pexels_key = os.environ.get("PEXELS_API_KEY", "GuLw0mgXERqcuzZeHixe676PraSOXxdWfJF3ABoN8cPzHSJOVWTXsOXJ")
    if not pexels_key:
        raise Exception("PEXELS_API_KEY environment variable is missing")

    font_path = get_arabic_font_path()
    bg_video = fetch_pexels_video(pexels_key)

    # Audio is already downloaded by main.py for duration check
    audio_file = os.path.join(ASSETS_DIR, "audio.mp3")
    if not os.path.exists(audio_file):
        download_audio_for_check(audio_url)

    # If 2-ayah mode, concatenate audio
    if audio_url_2:
        audio_file = concatenate_audio(audio_file, audio_url_2)

    # Render text as transparent PNG using PIL (bulletproof Arabic rendering)
    overlay_path = render_text_overlay(arabic_text, explanation_text, ref_text, font_path)

    out_file = os.path.join(ASSETS_DIR, "final_short.mp4")
    if os.path.exists(out_file):
        os.remove(out_file)

    print("Running FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",           # Loop background video
        "-i", bg_video,
        "-i", audio_file,
        "-i", overlay_path,             # Text overlay PNG
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
