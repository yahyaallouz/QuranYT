import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# The YouTube API requires token.json generated from OAuth locally.
# It should be injected by GitHub Actions into the runner environment.

def get_authenticated_service():
    if not os.path.exists('token.json'):
        raise Exception("token.json not found! You must authenticate locally first and supply it.")
    
    creds = Credentials.from_authorized_user_file('token.json')
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)

def upload_video(file_path, title, description):
    youtube = get_authenticated_service()

    body = {
        'snippet': {
            'title': title[:100],  # Title limit is 100 char
            'description': description[:5000], 
            'tags': ['quran', 'islam', 'shorts', 'recitation', 'peace'],
            'categoryId': '22'  # People & Blogs
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    print(f"Uploading {file_path} to YouTube Shorts...")
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
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
