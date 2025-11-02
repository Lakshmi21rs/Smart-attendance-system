# for the further use if using of firebase data base is required.
import firebase_admin
from firebase_admin import credentials, storage
import os
from typing import Optional

class FirebaseStorage:
    def __init__(self, cred_path: str, bucket_name: str):
        """
        Initialize Firebase Storage
        :param cred_path: Path to Firebase service account JSON
        :param bucket_name: Firebase storage bucket name
        """
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
        self.bucket = storage.bucket()
    
    def upload_folder(self, local_path: str, remote_path: str = "student") -> None:
        """
        Upload a folder to Firebase Storage
        :param local_path: Local folder path to upload
        :param remote_path: Remote path in Firebase
        """
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file = os.path.join(root, file)
                remote_file = os.path.join(remote_path, os.path.relpath(local_file, local_path))
                
                blob = self.bucket.blob(remote_file)
                blob.upload_from_filename(local_file)
                print(f"Uploaded {local_file} to {remote_file}")
    
    def download_folder(self, remote_path: str, local_path: str) -> None:
        """
        Download a folder from Firebase Storage
        :param remote_path: Remote folder path in Firebase
        :param local_path: Local path to download to
        """
        blobs = self.bucket.list_blobs(prefix=remote_path)
        
        for blob in blobs:
            # Create local directory structure
            local_file = os.path.join(local_path, os.path.relpath(blob.name, remote_path))
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            
            blob.download_to_filename(local_file)
            print(f"Downloaded {blob.name} to {local_file}")
    
    def get_file_url(self, remote_path: str) -> Optional[str]:
        """
        Get download URL for a file
        :param remote_path: Path to file in Firebase
        :return: Download URL or None if not found
        """
        blob = self.bucket.blob(remote_path)
        if blob.exists():
            return blob.generate_signed_url(expiration=3600)  # 1 hour URL
        return None