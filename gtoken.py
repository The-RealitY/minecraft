import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

token_path = "token.json"
credential_path = "credentials.json"
scopes = ["https://www.googleapis.com/auth/drive.file", ]

if not os.path.exists(token_path):
    flow = InstalledAppFlow.from_client_secrets_file(credential_path, scopes)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w") as token:
        token.write(creds.to_json())

creds = Credentials.from_authorized_user_file(token_path, scopes)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(credential_path, scopes)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
