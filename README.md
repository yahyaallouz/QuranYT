# Automated Quran Shorts System 🤍

A fully automated, GitHub Actions driven pipeline to create and upload beautiful 9:16 vertical YouTube Shorts of Quran verses, using real recitation audio from Mishary Rashid Alafasy, synchronized Arabic subtitles, and Pexels nature backgrounds.

## Local Setup & First Run

Before pushing to GitHub, you need to generate `token.json` for YouTube API.

1. **Get YouTube API Credentials:**
   * Go to Google Cloud Console.
   * Enable the **YouTube Data API v3**.
   * Go to Credentials > Create Credentials > OAuth client ID (Select Desktop app).
   * Download the JSON file and rename it to `client_secrets.json`. Place it in the root folder (`d:/QuranYT/`).

2. **Generate Token:**
   * Open your terminal in this folder and run `pip install -r requirements.txt`.
   * Run `python auth_setup.py`. 
   * A browser window will open asking you to log into your YouTube account and authorize the app. This creates `token.json`.

3. **Get Pexels API Key:**
   * Create a free account on Pexels and generate an API key.

## Deploying to GitHub Actions

1. Initialize a git repository and push this code to GitHub.
2. In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
3. Create the following repository secrets:
   * `PEXELS_API_KEY`: Paste your Pexels Key here.
   * `YOUTUBE_TOKEN_JSON`: Open `token.json` with a text editor and paste the **entire JSON string** here.
4. Go to **Settings > Actions > General** and ensure **Workflow permissions** is set to "Read and write permissions" so the bot can commit `used_ayahs.json` back to the repository.

Once deployed, the bot will automatically run at 09:00, 13:00, and 17:00 UTC daily!
