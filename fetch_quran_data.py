import requests
import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QURAN_JSON_PATH = os.path.join(DATA_DIR, "data", "quran.json")

def fetch_quran_data():
    print("Fetching Arabic text and audio (Alafasy)...")
    base_ar_url = "https://api.alquran.cloud/v1/quran/ar.alafasy"
    resp_ar = requests.get(base_ar_url)
    if resp_ar.status_code != 200:
        print("Failed to fetch Arabic Quran data")
        return
    ar_data = resp_ar.json()["data"]["surahs"]

    # We will use Saheeh International as a base explanation/translation.
    # The user asked for "emotional and engaging" instead of generic, but since we cannot
    # automatically generate 6236 emotional variations offline, we'll use a reliable translation
    # and provide a template wrapper in the final video to make it engaging.
    print("Fetching English translation (Sahih)...")
    base_en_url = "https://api.alquran.cloud/v1/quran/en.sahih"
    resp_en = requests.get(base_en_url)
    if resp_en.status_code != 200:
        print("Failed to fetch English Quran data")
        return
    en_data = resp_en.json()["data"]["surahs"]

    print("Merging data...")
    merged_ayahs = []

    for surah_idx, surah_ar in enumerate(ar_data):
        surah_en = en_data[surah_idx]
        surah_number = surah_ar["number"]
        surah_name_ar = surah_ar["name"]
        surah_name_en = surah_ar["englishName"]

        for ayah_idx, ayah_ar in enumerate(surah_ar["ayahs"]):
            ayah_en = surah_en["ayahs"][ayah_idx]
            
            # Prefer shorter Ayahs for YouTube Shorts format.
            # We add a length heuristic to filter them later.
            ar_text = ayah_ar["text"]
            en_text = ayah_en["text"]
            audio_url = ayah_ar["audio"]
            ayah_num_in_surah = ayah_ar["numberInSurah"]
            ayah_global_num = ayah_ar["number"]

            merged_ayahs.append({
                "surah_number": surah_number,
                "surah_name_ar": surah_name_ar,
                "surah_name_en": surah_name_en,
                "ayah_number": ayah_num_in_surah,
                "global_number": ayah_global_num,
                "arabic_text": ar_text,
                "english_translation": en_text,
                "audio_url": audio_url,
                "character_count": len(ar_text)
            })

    # Save to data/quran.json
    os.makedirs(os.path.join(DATA_DIR, "data"), exist_ok=True)
    with open(QURAN_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(merged_ayahs, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(merged_ayahs)} ayahs to {QURAN_JSON_PATH}")

if __name__ == "__main__":
    fetch_quran_data()
