import os
from google_auth_oauthlib.flow import InstalledAppFlow

# The scopes required for YouTube uploading
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def generate_token():
    if not os.path.exists('client_secrets.json'):
        print("Error: client_secrets.json not found!")
        print("Please download it from google cloud console and place it here.")
        return
        
    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("token.json created successfully! You can now copy its contents to GitHub secrets.")

if __name__ == '__main__':
    generate_token()
