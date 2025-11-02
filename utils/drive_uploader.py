
from utils.drive_integration import GoogleDriveManager
import os

def upload_student_photos(local_dir: str, drive_folder_id: str):
    drive = GoogleDriveManager('C:\smart-attendance-system\credentials\smartattendancesystem-465906-1d185d330be1.json')
    for filename in os.listdir(local_dir):
        if filename.endswith(('.jpg', '.jpeg', '.png')):
            file_path = os.path.join(local_dir, filename)
            drive.upload_file(file_path, drive_folder_id)
            print(f"Uploaded: {filename}")

# Run this once to upload existing photos
# upload_student_photos("local_student_photos", "DRIVE_FOLDER_ID")