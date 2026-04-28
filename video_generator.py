import os
import requests
import subprocess
import random
import json
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
USED_BGS_PATH = os.path.join(DATA_DIR, "data", "used_backgrounds.json")

# Ensure assets dir exists
os.makedirs(ASSETS_DIR, exist_ok=True)

def download_font():
    font_path = os.path.join(ASSETS_DIR, "Amiri-Bold.ttf")
    if not os.path.exists(font_path):
        print("Downloading Amiri font...")
        # Use the official GitHub release for reliability
        font_url = "https://github.com/alif-type/amiri/releases/download/1.000/Amiri-1.000.zip"
        # Fallback: direct raw file link
        fallback_url = "https://raw.githubusercontent.com/alif-type/amiri/main/fonts/Amiri-Bold.ttf"
        try:
            r = requests.get(fallback_url, timeout=30)
            r.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(r.content)
            print(f"Font downloaded: {font_path} ({os.path.getsize(font_path)} bytes)")
        except Exception as e:
            raise Exception(f"Failed to download Amiri font: {e}")
    else:
        print(f"Font already present: {font_path}")
    return font_path

def fetch_pexels_video(api_key):
    print("Fetching background video from Pexels...")
    headers = {"Authorization": api_key}
    queries = ["nature", "ocean", "forest", "sky", "mountains", "stars"]
    url = f"https://api.pexels.com/videos/search?query={random.choice(queries)}&orientation=portrait&size=medium&per_page=15"
    
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch Pexels: {r.status_code} {r.text}")
    
    videos = r.json().get("videos", [])
    
    # Load used backgrounds
    used_bgs = []
    if os.path.exists(USED_BGS_PATH):
        with open(USED_BGS_PATH, "r") as f:
            used_bgs = json.load(f)
            
    available = [v for v in videos if v["id"] not in used_bgs]
    if not available:
        # Reset if everything is used
        available = videos
        used_bgs = []
        
    selected = random.choice(available)
    used_bgs.append(selected["id"])
    
    # Save back the used tracker
    with open(USED_BGS_PATH, "w") as f:
        json.dump(used_bgs, f)
        
    # Find the best mp4 file link within the selected video
    video_files = selected["video_files"]
    # Sort by height to get 1080p or 720p at least
    video_files.sort(key=lambda x: x["height"] if x["height"] else 0, reverse=True)
    best_link = video_files[0]["link"]
    
    vid_path = os.path.join(ASSETS_DIR, "bg.mp4")
    print(f"Downloading Pexels ID {selected['id']}...")
    req = requests.get(best_link)
    with open(vid_path, "wb") as f:
        f.write(req.content)
        
    return vid_path

def download_audio(audio_url):
    print("Downloading Audio...")
    mp3_path = os.path.join(ASSETS_DIR, "audio.mp3")
    r = requests.get(audio_url)
    with open(mp3_path, "wb") as f:
        f.write(r.content)
    return mp3_path

def generate_ass_subtitle(arabic_text, explanation_text, ref_text):
    print("Generating .ass subtitle file...")
    ass_path = os.path.join(ASSETS_DIR, "subtitles.ass")
    # Emotional wrapper for explanation
    full_explanation = f"Reflection:\n{explanation_text}"
    
    # Base ASS structure
    ass_content = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Arabic,Amiri,90,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,50,50,800,1
Style: English,Arial,55,&H00E0E0E0,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,50,50,300,1
Style: Ref,Arial,45,&H00B0B0B0,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,1,8,50,50,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:59:00.00,Arabic,,0,0,0,,{{\\q1}}{arabic_text}
Dialogue: 0,0:00:00.00,0:59:00.00,English,,0,0,0,,{{\\q1}}{full_explanation}
Dialogue: 0,0:00:00.00,0:59:00.00,Ref,,0,0,0,,{ref_text}
"""
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return ass_path

def generate_video(arabic_text, explanation_text, ref_text, audio_url):
    pexels_key = os.environ.get("PEXELS_API_KEY", "GuLw0mgXERqcuzZeHixe676PraSOXxdWfJF3ABoN8cPzHSJOVWTXsOXJ")
    if not pexels_key:
        raise Exception("PEXELS_API_KEY environment variable is missing")
    
    # Prepare assets
    download_font() # ensures font is available
    bg_video = fetch_pexels_video(pexels_key)
    audio_file = download_audio(audio_url)
    ass_file = generate_ass_subtitle(arabic_text, explanation_text, ref_text)
    
    out_file = os.path.join(ASSETS_DIR, "final_short.mp4")
    if os.path.exists(out_file):
        os.remove(out_file)

    # Use ffmpeg via subprocess
    # 1. Dark overlay on video
    # 2. Add Audio
    # 3. Add ASS subtitles
    # 4. Truncate video to shortest (audio length)
    # We loop the video if it's shorter than audio. Pexels are usually 10-15s, but ayahs are short.
    # We add -vf "format=yuv420p,colorchannelmixer=aa=0.7" ? No, `eq=brightness=-0.3` is simpler.
    # Pass fontsdir directly in the ASS filter so FFmpeg finds Amiri-Bold.ttf
    # regardless of system fontconfig state (works on both local and GitHub Actions)
    fonts_dir = ASSETS_DIR.replace('\\', '/')
    # On Linux/CI use forward slashes; on Windows use forward slashes too for FFmpeg
    ass_abs = ass_file.replace('\\', '/')
    # Remove drive letter colon on Windows (e.g. D:/foo -> /foo) to avoid FFmpeg vf parser issues
    import platform
    if platform.system() == "Windows":
        ass_abs = '/' + ass_abs.replace(':', '')
        fonts_dir = '/' + fonts_dir.replace(':', '')

    vf_filter = (
        f"colorlevels=romax=0.7:gomax=0.7:bomax=0.7,"
        f"ass={ass_abs}:fontsdir={fonts_dir},"
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    )

    print("Running FFmpeg...")
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",           # Loop video if audio is longer
        "-i", bg_video,
        "-i", audio_file,
        "-vf", vf_filter,
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "fast",
        "-shortest",                    # Finish when audio ends
        out_file
    ]

    print("Executing command: ", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=DATA_DIR)
    print(f"Video generated at {out_file}")
    
    return out_file
