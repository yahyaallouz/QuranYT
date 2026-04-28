import os
import json
import random
import time
import subprocess
from video_generator import generate_video, get_audio_duration, download_audio_for_check
from uploader import upload_video

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QURAN_PATH = os.path.join(DATA_DIR, "data", "quran.json")
USED_AYAHS_PATH = os.path.join(DATA_DIR, "data", "used_ayahs.json")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

# Emotional explanation templates that are sincere and human-like
EMOTIONAL_PREFIXES = [
    "This verse is a reminder that",
    "Subhan'Allah —",
    "Let this verse speak to your heart:",
    "One of the most beautiful reminders in the Qur'an:",
    "Reflect on this —",
    "This ayah carries a deep meaning:",
    "A gentle reminder from Allah:",
    "May these words bring you peace:",
]

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def commit_changes():
    """Commit tracking files back to GitHub with retry logic for conflicts."""
    if not os.environ.get("GITHUB_ACTIONS"):
        print("Not in GitHub Actions, skipping commit.")
        return

    print("Committing tracking files back to repository...")
    for attempt in range(5):
        try:
            subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)
            subprocess.run(["git", "add", "data/used_ayahs.json", "data/used_backgrounds.json"], check=True)
            res = subprocess.run(["git", "commit", "-m", "chore: update ayah and background trackers [skip ci]"],
                                 capture_output=True)
            if b"nothing to commit" in res.stdout or b"nothing to commit" in res.stderr:
                print("Nothing to commit.")
                return
            # Pull with rebase to handle race conditions when multiple runs overlap
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Successfully committed and pushed tracking files.")
            return
        except subprocess.CalledProcessError:
            wait = 10 * (attempt + 1)
            print(f"Git conflict or error, retrying {attempt+1}/5 in {wait}s...")
            time.sleep(wait)

def build_ayah_index(quran):
    """Build a fast lookup: (surah_number, ayah_number) -> ayah dict"""
    return {(a["surah_number"], a["ayah_number"]): a for a in quran}

def make_emotional_explanation(translation):
    """Wrap the translation in an emotional, human-like sentence."""
    prefix = random.choice(EMOTIONAL_PREFIXES)
    # Truncate very long translations to keep it short (1-2 sentences)
    sentences = translation.replace("?", ".").replace("!", ".").split(".")
    short = ". ".join(s.strip() for s in sentences[:2] if s.strip())
    return f"{prefix} {short}."

def select_ayahs():
    """
    Select one or two consecutive same-surah ayahs for a 10–25s video.
    Returns a list of one or two ayah dicts and their combined audio URLs.
    """
    quran = load_json(QURAN_PATH)
    used = load_json(USED_AYAHS_PATH)
    used_set = set(used)
    ayah_index = build_ayah_index(quran)

    available = [a for a in quran if f"{a['surah_number']}:{a['ayah_number']}" not in used_set]

    if not available:
        print("All ayahs used! Resetting tracker...")
        used = []
        used_set = set()
        available = quran

    # Prefer shorter ayahs (<120 chars) that are more suitable for Shorts
    short_available = [a for a in available if a['character_count'] < 120]
    pool = short_available if short_available else available
    selected = random.choice(pool)

    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Check if the single ayah audio is too short (< 8 seconds)
    mp3_path = download_audio_for_check(selected["audio_url"])
    duration = get_audio_duration(mp3_path)
    print(f"Ayah duration: {duration:.1f}s")

    ayahs = [selected]
    ids_to_mark = [f"{selected['surah_number']}:{selected['ayah_number']}"]

    if duration < 8:
        # Try to combine with the next ayah in the same surah
        next_key = (selected["surah_number"], selected["ayah_number"] + 1)
        next_ayah = ayah_index.get(next_key)
        if next_ayah:
            print(f"Ayah too short ({duration:.1f}s), combining with next ayah: {next_key}")
            next_id = f"{next_ayah['surah_number']}:{next_ayah['ayah_number']}"
            ayahs.append(next_ayah)
            ids_to_mark.append(next_id)
        else:
            print("No next ayah in same surah, using single ayah as-is.")

    return ayahs, ids_to_mark

def main():
    ayahs, ids_to_mark = select_ayahs()

    surah_num = ayahs[0]['surah_number']
    surah_name = ayahs[0]['surah_name_en']

    if len(ayahs) == 2:
        ayah_range = f"{ayahs[0]['ayah_number']}-{ayahs[1]['ayah_number']}"
        arabic_text = ayahs[0]['arabic_text'] + "\n" + ayahs[1]['arabic_text']
        # Combine translation for explanation
        combined_translation = ayahs[0]['english_translation'] + " " + ayahs[1]['english_translation']
        ref_text = f"Surah {surah_name} [{surah_num}:{ayah_range}]"
        audio_url = ayahs[0]['audio_url']  # Primary audio; second will be concatenated inside video_generator
        audio_url_2 = ayahs[1]['audio_url']
    else:
        ayah_range = str(ayahs[0]['ayah_number'])
        arabic_text = ayahs[0]['arabic_text']
        combined_translation = ayahs[0]['english_translation']
        ref_text = f"Surah {surah_name} [{surah_num}:{ayah_range}]"
        audio_url = ayahs[0]['audio_url']
        audio_url_2 = None

    explanation = make_emotional_explanation(combined_translation)

    print(f"Selected: {ref_text}")

    title = f"Beautiful Qur'an Recitation 🤍 {ref_text} #shorts #quran"
    description = (
        f"Experience the peace of the Holy Qur'an with this beautiful recitation of {ref_text}.\n\n"
        f"✨ Reciter: Mishary Rashid Alafasy\n"
        f"📖 Translation:\n\"{combined_translation[:300]}\"\n\n"
        f"May this bring peace to your heart. Don't forget to like, subscribe, and share for more daily Qur'an verses! 🤍\n\n"
        f"Keywords: quran recitation, beautiful quran, soothing quran recitation, "
        f"quran shorts, daily ayah, islamic reminders, mishary rashid alafasy, peaceful quran\n\n"
        f"#quran #islam #quranrecitation #peace #shorts"
    )

    try:
        video_path = generate_video(
            arabic_text,
            explanation,
            ref_text,
            audio_url,
            audio_url_2=audio_url_2
        )

        if os.environ.get("DRY_RUN") != "1":
            upload_video(video_path, title, description)
            used = load_json(USED_AYAHS_PATH)
            for ayah_id in ids_to_mark:
                if ayah_id not in used:
                    used.append(ayah_id)
            save_json(USED_AYAHS_PATH, used)
            commit_changes()
        else:
            print("Dry run enabled, skipping upload and git commit.")

    except Exception as e:
        import traceback
        print(f"Workflow failed: {e}")
        traceback.print_exc()
    finally:
        assets_dir = os.path.join(DATA_DIR, "assets")
        cleanup_files = ["bg.mp4", "audio.mp3", "audio2.mp3", "audio_combined.mp3", "subtitles.ass"]
        if os.environ.get("DRY_RUN") != "1" and 'video_path' in locals():
            cleanup_files.append("final_short.mp4")
        for f in cleanup_files:
            path = os.path.join(assets_dir, f)
            if os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    main()
