# services/gdrive_storage.py

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

from DataAccessLayer.storage.base import StorageStrategy


class GoogleDriveStorage(StorageStrategy):
    def __init__(self):
        SCOPES = ['https://www.googleapis.com/auth/drive']
        SERVICE_ACCOUNT_FILE = 'secrets/service_account.json'  # path to your service account file

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.service = build('drive', 'v3', credentials=creds)

    def upload_file(self, file, filename: str):
        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(file.file, mimetype=file.content_type)
        uploaded = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return {"message": "Uploaded to Google Drive", "file_id": uploaded.get('id')}

    def get_file(self, filename: str):
        # Find the file by name
        results = self.service.files().list(q=f"name='{filename}'", fields="files(id, name)").execute()
        files = results.get('files', [])
        if not files:
            return {"error": "File not found"}

        file_id = files[0]['id']
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)
        return {"filename": filename, "content": fh.read().decode('utf-8')}

    def delete_file(self, filename: str):
        results = self.service.files().list(q=f"name='{filename}'", fields="files(id)").execute()
        files = results.get('files', [])
        if not files:
            return {"error": "File not found"}
        file_id = files[0]['id']
        self.service.files().delete(fileId=file_id).execute()
        return {"message": "Deleted from Google Drive"}

    def update_file(self, filename: str, new_file):
        self.delete_file(filename)
        return self.upload_file(new_file, filename)
    def list_files(self):
        pass