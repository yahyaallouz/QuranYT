import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# YouTube API requires token.json generated from OAuth locally.
# Injected by GitHub Actions into the runner environment.


def get_authenticated_service():
    if not os.path.exists('token.json'):
        raise Exception("token.json not found! You must authenticate locally first and supply it.")

    creds = Credentials.from_authorized_user_file('token.json')
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)


def upload_video(file_path, title, description, tags=None):
    """Upload a video to YouTube Shorts.

    Args:
        file_path: Path to the video file.
        title: Video title (no hashtags, ≤65 chars recommended).
        description: Full description including hashtags.
        tags: Optional list of tags. Defaults to a standard set.
    """
    youtube = get_authenticated_service()

    if tags is None:
        tags = ['quran', 'islam', 'shorts', 'recitation', 'peace']

    body = {
        'snippet': {
            'title': title[:100],  # YouTube API title limit
            'description': description[:5000],
            'tags': tags,
            'categoryId': '27',  # Education
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        },
    }

    print(f"Uploading {file_path} to YouTube Shorts...")

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except Exception as e:
            print(f"An error occurred during upload: {e}")
            raise

    print("Upload Complete!")
    return response.get('id')
