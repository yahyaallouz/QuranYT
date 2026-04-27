import os
import json
import random
import time
import subprocess
from video_generator import generate_video
from uploader import upload_video

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QURAN_PATH = os.path.join(DATA_DIR, "data", "quran.json")
USED_AYAHS_PATH = os.path.join(DATA_DIR, "data", "used_ayahs.json")

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def commit_changes():
    """Commit tracking files back to GitHub to avoid conflicts."""
    if not os.environ.get("GITHUB_ACTIONS"):
        print("Not in GitHub Actions, skipping commit.")
        return

    print("Committing tracking files back to repository...")
    for attempt in range(5):
        try:
            subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)
            subprocess.run(["git", "add", "data/used_ayahs.json", "data/used_backgrounds.json"], check=True)
            # if no changes, commit will fail but we handle it
            res = subprocess.run(["git", "commit", "-m", "Auto-update tracked ayahs and backgrounds"], capture_output=True)
            if b"nothing to commit" in res.stdout:
                return # No changes made
            
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Successfully committed and pushed tracking files.")
            return
        except subprocess.CalledProcessError as e:
            print(f"Git conflict or error, retrying {attempt+1}/5...")
            time.sleep(10)

def select_ayah():
    quran = load_json(QURAN_PATH)
    used = load_json(USED_AYAHS_PATH)
    
    # Preference: Short ayahs (less than 70 chars) to fit 15-30s
    available = [a for a in quran if f"{a['surah_number']}:{a['ayah_number']}" not in used]
    
    if not available:
        print("All ayahs used! Resetting tracker...")
        used = []
        available = quran
        
    short_available = [a for a in available if a['character_count'] < 70]
    
    if short_available:
        selected = random.choice(short_available)
    else:
        selected = random.choice(available)
        
    return selected

def main():
    selected = select_ayah()
    surah_num = selected['surah_number']
    ayah_num = selected['ayah_number']
    ayah_id = f"{surah_num}:{ayah_num}"
    
    print(f"Selected Ayah: Surah {selected['surah_name_en']} [{ayah_id}]")
    
    ref_text = f"Surah {selected['surah_name_en']} {surah_num}:{ayah_num}"
    title = f"Listen to this beautiful Qur'an recitation 🤍 | {ref_text} #shorts #quran"
    description = f"Qur'an Recitation: Mishary Rashid Alafasy.\n\nSurah {selected['surah_name_en']} ({surah_num}:{ayah_num})\nTranslation:\n{selected['english_translation']}\n\n#quran #islam #allah #recitation #shorts"
    
    try:
        # 1. Generate Video
        video_path = generate_video(
            selected['arabic_text'], 
            selected['english_translation'],
            ref_text,
            selected['audio_url']
        )
        
        # 2. Upload Video
        if os.environ.get("DRY_RUN") != "1":
            upload_video(video_path, title, description)
            # Note: Only track if uploaded successfully
            used = load_json(USED_AYAHS_PATH)
            used.append(ayah_id)
            save_json(USED_AYAHS_PATH, used)
            commit_changes()
        else:
            print("Dry run enabled, skipping upload and git commit.")
            
    except Exception as e:
        print(f"Workflow failed: {e}")
    finally:
        # Cleanup temporary files (keep final_short.mp4 if dry run or failure for review)
        assets_dir = os.path.join(DATA_DIR, "assets")
        cleanup_files = ["bg.mp4", "audio.mp3", "subtitles.ass"]
        if os.environ.get("DRY_RUN") != "1" and 'video_path' in locals():
            # Only clean up the final video if we successfully uploaded it and aren't dry-running
            cleanup_files.append("final_short.mp4")
            
        for f in cleanup_files:
            path = os.path.join(assets_dir, f)
            if os.path.exists(path):
                os.remove(path)
                
if __name__ == "__main__":
    main()
