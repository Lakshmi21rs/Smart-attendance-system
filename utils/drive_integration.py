
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from typing import List, Dict, Optional

class GoogleDriveManager:
    def __init__(self, credentials_path: str):
        """
        Initialize Google Drive API connection
        :param credentials_path: Path to your service account JSON credentials
        """
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self.SCOPES)
        self.service = build('drive', 'v3', credentials=self.credentials)
    
    def create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Create a folder in Google Drive"""
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        folder = self.service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        return folder.get('id')
    
    def upload_file(self, file_path: str, folder_id: str = None) -> str:
        """
        Upload a file to Google Drive
        Returns the file ID
        """
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
    
    def download_file(self, file_id: str, save_path: str) -> None:
        """Download a file from Google Drive"""
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(save_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")
    
    def list_files(self, folder_id: str = None) -> List[Dict]:
        """List all files in a folder"""
        query = f"'{folder_id}' in parents" if folder_id else None
        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType)"
        ).execute()
        return results.get('files', [])
    
    def find_file_by_name(self, name: str, folder_id: str = None) -> Optional[str]:
        """Find a file by name and return its ID"""
        query = f"name = '{name}'"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = self.service.files().list(
            q=query,
            pageSize=1,
            fields="files(id)"
        ).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    
    def list_folders(self, parent_folder_id: str) -> List[Dict]:
        """
        List all folders within a parent folder
        :param parent_folder_id: ID of the parent folder
        :return: List of folder dictionaries (id, name)
        """
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
        results = self.service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        return results.get('files', [])
    
    def create_folder_in_parent(self, folder_name: str, parent_folder_id: str) -> str:
        """
        Create a new folder within a specific parent folder
        :param folder_name: Name of the new folder
        :param parent_folder_id: ID of the parent folder
        :return: ID of the created folder
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        return folder.get('id')
    
    def upload_folder(self, local_folder_path: str, parent_folder_id: str = None) -> List[str]:
        """
        Upload an entire folder to Google Drive
        :param local_folder_path: Path to the local folder
        :param parent_folder_id: ID of the parent folder in Drive
        :return: List of uploaded file IDs
        """
        folder_name = os.path.basename(local_folder_path)
        folder_id = self.create_folder_in_parent(folder_name, parent_folder_id) if parent_folder_id else self.create_folder(folder_name)
        
        uploaded_ids = []
        for item in os.listdir(local_folder_path):
            item_path = os.path.join(local_folder_path, item)
            if os.path.isdir(item_path):
                uploaded_ids.extend(self.upload_folder(item_path, folder_id))
            else:
                uploaded_ids.append(self.upload_file(item_path, folder_id))
        
        return uploaded_ids
    
    def download_folder(self, folder_id: str, local_path: str) -> None:
        """
        Download an entire folder from Google Drive
        :param folder_id: ID of the folder to download
        :param local_path: Local path to save the folder
        """
        os.makedirs(local_path, exist_ok=True)
        items = self.list_files(folder_id)
        
        for item in items:
            item_path = os.path.join(local_path, item['name'])
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                self.download_folder(item['id'], item_path)
            else:
                self.download_file(item['id'], item_path)