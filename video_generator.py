import os
import requests
import subprocess
import random
import json

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

def download_font():
    """Download Amiri Bold font if not already cached in assets."""
    font_path = os.path.join(ASSETS_DIR, "Amiri-Bold.ttf")
    if not os.path.exists(font_path):
        print("Downloading Amiri font...")
        url = "https://raw.githubusercontent.com/alif-type/amiri/main/fonts/Amiri-Bold.ttf"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(font_path, "wb") as f:
            f.write(r.content)
        print(f"Font downloaded ({os.path.getsize(font_path)} bytes)")
    else:
        print("Font already present.")
    return font_path

def fetch_pexels_video(api_key):
    """Fetch and download a nature portrait video from Pexels, avoiding the last BG_MEMORY used."""
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

    # Load history and keep only the last BG_MEMORY entries
    used_bgs = []
    if os.path.exists(USED_BGS_PATH):
        with open(USED_BGS_PATH, "r") as f:
            used_bgs = json.load(f)
    used_bgs = used_bgs[-BG_MEMORY:]  # Rolling window of last 20

    available = [v for v in videos if v["id"] not in used_bgs]
    if not available:
        print("All backgrounds in window used, expanding pool...")
        available = videos

    selected = random.choice(available)
    used_bgs.append(selected["id"])

    with open(USED_BGS_PATH, "w") as f:
        json.dump(used_bgs, f)

    # Pick best portrait file (sort by height descending)
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
    # Write concat list for FFmpeg
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

def generate_ass_subtitle(arabic_text, explanation_text, ref_text):
    """Generate an Advanced SubStation Alpha subtitle file with large, beautiful styling."""
    print("Generating .ass subtitle file...")
    ass_path = os.path.join(ASSETS_DIR, "subtitles.ass")

    # Handle 2-ayah split: replace \n with {\N} (ASS line break)
    arabic_ass = arabic_text.replace("\n", "{\\N}")

    ass_content = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Arabic,Amiri,110,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,2,0,1,4,3,5,60,60,760,1
Style: English,Arial,52,&H00F0F0F0,&H000000FF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,2,2,2,60,60,260,1
Style: Ref,Arial,42,&H00AAAAAA,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,1,8,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:59:00.00,Arabic,,0,0,0,,{{\\q1}}{arabic_ass}
Dialogue: 0,0:00:00.00,0:59:00.00,English,,0,0,0,,{{\\q1}}{explanation_text}
Dialogue: 0,0:00:00.00,0:59:00.00,Ref,,0,0,0,,{ref_text}
"""
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return ass_path

def generate_video(arabic_text, explanation_text, ref_text, audio_url, audio_url_2=None):
    """Full pipeline: fetch background, audio, generate subtitles, render via FFmpeg."""
    pexels_key = os.environ.get("PEXELS_API_KEY", "GuLw0mgXERqcuzZeHixe676PraSOXxdWfJF3ABoN8cPzHSJOVWTXsOXJ")
    if not pexels_key:
        raise Exception("PEXELS_API_KEY environment variable is missing")

    download_font()
    bg_video = fetch_pexels_video(pexels_key)

    # Audio is already downloaded by main.py for duration check — no re-download needed
    audio_file = os.path.join(ASSETS_DIR, "audio.mp3")
    if not os.path.exists(audio_file):
        download_audio_for_check(audio_url)

    # If 2-ayah mode, concatenate the second audio into one file
    if audio_url_2:
        audio_file = concatenate_audio(audio_file, audio_url_2)

    ass_file = generate_ass_subtitle(arabic_text, explanation_text, ref_text)

    out_file = os.path.join(ASSETS_DIR, "final_short.mp4")
    if os.path.exists(out_file):
        os.remove(out_file)

    # Use relative paths — FFmpeg is launched with cwd=DATA_DIR so these resolve correctly
    # on both Windows and Linux without any drive-letter colon escaping issues
    ass_rel = os.path.relpath(ass_file, DATA_DIR).replace("\\", "/")
    fonts_rel = os.path.relpath(ASSETS_DIR, DATA_DIR).replace("\\", "/")

    vf_filter = (
        f"colorlevels=romax=0.65:gomax=0.65:bomax=0.65,"
        f"ass={ass_rel}:fontsdir={fonts_rel},"
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    )

    print("Running FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",       # Loop background video
        "-i", bg_video,
        "-i", audio_file,
        "-vf", vf_filter,
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "fast",
        "-t", "30",                 # Hard cap at 30 seconds
        "-shortest",                # End when the audio track ends
        out_file
    ]

    print("Executing:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=DATA_DIR)
    print(f"Video generated at {out_file}")
    return out_file
