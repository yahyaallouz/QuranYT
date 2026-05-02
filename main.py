import os
import json
import random
import time
import subprocess
from video_generator import generate_video, get_audio_duration, download_audio_for_check
from uploader import upload_video
from hooks import get_hook
from content_strategy import generate_title, generate_description, make_short_explanation
from variation_engine import (
    load_history, save_history, record_post_time, hours_since_last_post,
)
from schedule_checker import should_post_now

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QURAN_PATH = os.path.join(DATA_DIR, "data", "quran.json")
USED_AYAHS_PATH = os.path.join(DATA_DIR, "data", "used_ayahs.json")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def commit_changes():
    """Commit tracking files back to GitHub with retry logic."""
    if not os.environ.get("GITHUB_ACTIONS"):
        print("Not in GitHub Actions, skipping commit.")
        return

    print("Committing tracking files back to repository...")
    for attempt in range(5):
        try:
            subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)
            subprocess.run([
                "git", "add",
                "data/used_ayahs.json",
                "data/used_backgrounds.json",
                "data/variation_history.json",
            ], check=True)
            res = subprocess.run(
                ["git", "commit", "-m", "chore: update tracking files [skip ci]"],
                capture_output=True,
            )
            if b"nothing to commit" in res.stdout or b"nothing to commit" in res.stderr:
                print("Nothing to commit.")
                return
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


def select_ayahs():
    """
    Select up to 4 consecutive same-surah ayahs.
    Targets ~20-30s audio (ideal for 28-32s video with hook).
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

    # Prefer shorter ayahs suitable for Shorts
    short_available = [a for a in available if a['character_count'] < 200]
    pool = short_available if short_available else available
    selected = random.choice(pool)

    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Check audio duration of first ayah
    mp3_path = download_audio_for_check(selected["audio_url"])
    duration = get_audio_duration(mp3_path)
    print(f"Ayah duration: {duration:.1f}s")

    ayahs = [selected]
    ids_to_mark = [f"{selected['surah_number']}:{selected['ayah_number']}"]

    # Collect up to 3 more consecutive ayahs from the same surah
    for offset in range(1, 4):
        next_key = (selected["surah_number"], selected["ayah_number"] + offset)
        next_ayah = ayah_index.get(next_key)
        if next_ayah:
            next_id = f"{next_ayah['surah_number']}:{next_ayah['ayah_number']}"
            ayahs.append(next_ayah)
            ids_to_mark.append(next_id)
        else:
            break

    print(f"Selected {len(ayahs)} ayahs: {ids_to_mark}")
    return ayahs, ids_to_mark


def main():
    history = load_history()

    # ── Schedule gate ────────────────────────────────────────────
    is_ci = bool(os.environ.get("GITHUB_ACTIONS"))
    is_dry = os.environ.get("DRY_RUN") == "1"

    if is_ci and not is_dry:
        # Check if we should post now
        if not should_post_now(tolerance_minutes=45):
            # 24h fallback: force-post if >24h since last upload
            gap = hours_since_last_post(history)
            if gap < 24:
                print(f"[schedule] Not time to post. Last post was {gap:.1f}h ago. Exiting.")
                return
            else:
                print(f"[schedule] ⚠ No post in {gap:.1f}h — forcing fallback upload.")

    # ── Select ayahs ─────────────────────────────────────────────
    ayahs, ids_to_mark = select_ayahs()

    surah_num = ayahs[0]['surah_number']
    surah_name = ayahs[0]['surah_name_en']

    # Build combined text and audio for all selected ayahs
    ayah_range = f"{ayahs[0]['ayah_number']}-{ayahs[-1]['ayah_number']}" if len(ayahs) > 1 else str(ayahs[0]['ayah_number'])
    arabic_text = "\n".join(a['arabic_text'] for a in ayahs)
    combined_translation = " ".join(a['english_translation'] for a in ayahs)
    ref_text = f"Surah {surah_name} [{surah_num}:{ayah_range}]"
    audio_urls = [a['audio_url'] for a in ayahs]

    # ── Generate content ─────────────────────────────────────────
    hook_text, history = get_hook(history)
    explanation = make_short_explanation(combined_translation)
    title = generate_title(hook_text, surah_name, surah_num, ayah_range)
    description, history = generate_description(combined_translation, ref_text, history)

    print(f"Selected: {ref_text}")
    print(f"Hook: {hook_text}")
    print(f"Title: {title}")
    print(f"Explanation: {explanation}")

    try:
        video_path, history = generate_video(
            arabic_text,
            explanation,
            ref_text,
            audio_urls,
            hook_text=hook_text,
            history=history,
        )

        if not is_dry:
            upload_video(video_path, title, description)

            # Record successful post
            history = record_post_time(history)
            save_history(history)

            used = load_json(USED_AYAHS_PATH)
            for ayah_id in ids_to_mark:
                if ayah_id not in used:
                    used.append(ayah_id)
            save_json(USED_AYAHS_PATH, used)
            commit_changes()
        else:
            # Still save history in dry run for testing
            save_history(history)
            print("Dry run enabled, skipping upload and git commit.")

    except Exception as e:
        import traceback
        print(f"Workflow failed: {e}")
        traceback.print_exc()
    finally:
        cleanup_files = [
            "bg.mp4", "audio.mp3", "audio_combined.mp3",
            "audio_0.mp3", "audio_1.mp3", "audio_2.mp3", "audio_3.mp3",
            "audio_padded.mp3", "silence.mp3", "subtitles.ass",
            "hook_overlay.png", "arabic_overlay.png", "explanation_overlay.png",
            "subtitle_anim.webm",
        ]
        if not is_dry and 'video_path' in locals():
            cleanup_files.append("final_short.mp4")
        for f in cleanup_files:
            path = os.path.join(ASSETS_DIR, f)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    main()
