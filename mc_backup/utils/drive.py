import os
import time
from datetime import datetime
from functools import wraps

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


def retry_request(func):
    """
    Retry decorator for requests, handles unauthorized error and retries up to 5 times.
    If any error occurs, it will return False.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        retry_count = 0
        while retry_count < 5:
            try:
                return func(self, *args, **kwargs)  # Pass 'self' as part of the function call
            except HttpError as error:
                if error.resp.status == 401:
                    # Unauthorized error, refresh token
                    self.log.error("Unauthorized access, refreshing token.")
                    self.webhook.edit_message("Unauthorized access, refreshing token.")
                    self.service = self._create_service()  # Refresh the service
                    retry_count += 1
                    time.sleep(2)  # Wait before retrying
                    continue
                else:
                    # Any other error, log and return False
                    self.log.error(f"An error occurred: {error}")
                    self.webhook.edit_message(f"An error occurred: {error}")
                    return False
        return False  # Return False after 5 retries

    return wrapper


class Gdrive:
    def __init__(self, wh, log, GDRIVE_ID, RETENTION, ARCHIVE, time_zone):
        self.webhook = wh
        self.log = log
        self.timezone = time_zone
        self.gdrive_folder_id = GDRIVE_ID
        self.retain_folder_name = "Retention"
        self.archive_folder_name = "Archive"
        self.token_path = os.path.join(os.getcwd(), "token.json")
        self.credential_path = os.path.join(os.getcwd(), "credentials.json")
        self.num_backup_retain = RETENTION
        self.min_arc_day = ARCHIVE
        self.scopes = ["https://www.googleapis.com/auth/drive.file", ]
        self.service = self._create_service()

    def _create_service(self):
        if not os.path.exists(self.token_path):
            self.log.error("Token file not found.")
            self.webhook.edit_message("Token file not found.")
            return None
        creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credential_path, self.scopes)
                creds = flow.run_local_server(port=0)
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
        return build('drive', 'v3', credentials=creds)

    def _get_folder_id(self, folder_name):
        try:
            response = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and parents='{self.gdrive_folder_id}'",
                spaces='drive', fields='files(id, name)', pageSize=1
            ).execute()
            return response.get('files')[0].get('id') if len(response.get('files')) > 0 else None
        except Exception as error:
            self.log.error(f"Error fetching folder '{folder_name}': {error}")
            self.webhook.edit_message(f"Error fetching folder '{folder_name}': {error}")
            return None

    @retry_request
    def create_folder(self, name):
        folder_id = self._get_folder_id(name)
        if folder_id:
            return folder_id
        folder_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [self.gdrive_folder_id]}
        try:
            response = self.service.files().create(body=folder_metadata, fields='id').execute()
            return response['id']
        except Exception as error:
            self.log.error(f"Error creating folder '{name}': {error}")
            self.webhook.edit_message(f"Error creating folder '{name}': {error}")
            return False

    @retry_request
    def upload_file(self, file_path, folder_id):
        if not os.path.exists(file_path):
            self.log.error(f"File not found: {file_path}")
            self.webhook.edit_message(f"File not found: {file_path}")
            return False
        file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        try:
            response = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            self.log.info(f"Uploaded file ID: {response['id']}")
            self.webhook.edit_message(f"Uploaded file ID: {response['id']}")
            return response['id']
        except Exception as error:
            self.log.error(f"Error uploading file '{file_path}': {error}")
            self.webhook.edit_messager(f"Error uploading file '{file_path}': {error}")
            return False

    @retry_request
    def get_files_in_folder(self, folder_id):
        try:
            response = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive', fields='files(id, name, createdTime)', orderBy='createdTime desc'
            ).execute()
            return response.get('files', [])
        except Exception as error:
            self.log.error(f"Error fetching files from folder {folder_id}: {error}")
            self.webhook.edit_message(f"Error fetching files from folder {folder_id}: {error}")
            return []

    @retry_request
    def delete_file(self, file_id):
        try:
            self.service.files().delete(fileId=file_id).execute()
            self.log.info(f"Deleted file ID: {file_id}")
            self.webhook.edit_message(f"Deleted file ID: {file_id}")
        except Exception as error:
            self.log.error(f"Error deleting file {file_id}: {error}")
            self.webhook.edit_message(f"Error deleting file {file_id}: {error}")
            return False

    def backup(self, output_filepath):
        try:
            retain_folder_id = self.create_folder(self.retain_folder_name)
            if not retain_folder_id:
                self.log.error("Failed to create 'Retention' folder.")
                self.webhook.edit_message("Failed to create 'Retention' folder.")
                return False

            archive_folder_id = self.create_folder(self.archive_folder_name)
            if not archive_folder_id:
                self.log.error("Failed to create 'Archive' folder.")
                self.webhook.edit_message("Failed to create 'Archive' folder.")
                return False

            response = self.upload_file(output_filepath, retain_folder_id)
            if not response:
                self.log.error(f"Failed to upload file to 'Retention' folder: {output_filepath}")
                self.webhook.edit_message(f"Failed to upload file to 'Retention' folder: {output_filepath}")
                return False

            files_in_retain = self.get_files_in_folder(retain_folder_id)
            if len(files_in_retain) > self.num_backup_retain:
                files_to_delete = files_in_retain[self.num_backup_retain:]
                for file in files_to_delete:
                    self.delete_file(file['id'])

            files_in_archive = self.get_files_in_folder(archive_folder_id)
            if not files_in_archive:
                self.log.info("Archive folder is empty. Uploading file to Archive.")
                self.webhook.edit_message("Archive folder is empty. Uploading file to Archive.")
                response = self.upload_file(output_filepath, archive_folder_id)
                if not response:
                    self.log.error(f"Failed to upload file to 'Archive' folder: {output_filepath}")
                    self.webhook.edit_message(f"Failed to upload file to 'Archive' folder: {output_filepath}")
                    return False
            else:
                latest_file = files_in_archive[0]
                latest_file_date = datetime.now(tz=self.timezone).strptime(latest_file['createdTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
                latest_file_date = self.timezone.localize(latest_file_date)  # Localize the naive datetime to aware datetime
                days_difference = (datetime.now(tz=self.timezone) - latest_file_date).days

                if days_difference >= self.min_arc_day:
                    self.log.info(f"Last archive file is older than {self.min_arc_day} days. Uploading new file to Archive.")
                    self.webhook.edit_message(f"Last archive file is older than {self.min_arc_day} days. Uploading new file to Archive.")
                    response = self.upload_file(output_filepath, archive_folder_id)
                    if not response:
                        self.log.error(f"Failed to upload file to 'Archive' folder: {output_filepath}")
                        self.webhook.edit_message(f"Failed to upload file to 'Archive' folder: {output_filepath}")
                        return False
                else:
                    self.log.info(f"Last archive file is recent ({days_difference} days old). Skipping upload to Archive.")
                    self.webhook.edit_message(f"Last archive file is recent ({days_difference} days old). Skipping upload to Archive.")
            return True
        except Exception as e:
            self.log.error(f"Error during backup: {e}")
            self.webhook.edit_message(f"Error during backup: {e}")
            return False
