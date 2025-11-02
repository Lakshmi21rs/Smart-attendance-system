# Smart-attendance-system
The Smart Attendance System is a Python-based AI solution that automates attendance marking using facial recognition and Google Drive cloud integration. The system processes a classroom group photo to generate instant lists of present, absent, and unrecognized students by comparing detected faces against a stored dataset of four reference images per student. The dataset is securely stored and managed on Google Drive for easy access and scalability, with options for uploading, downloading, and updating student images. An interactive Streamlit interface allows users to reupload photos of unrecognized students, immediately updating the attendance list. Built with OpenCV, face_recognition, and Google API Client, the system ensures fast, accurate, and reliable attendance tracking for modern educational environments.

## Features
1.	Facial Recognition-Based Attendance – Automatically detects and matches student faces from a classroom group photo using AI-powered recognition.
2.	Multiple Reference Images per Student – Uses four stored images for each student to improve accuracy and reduce false negatives.
3.	Cloud Dataset Storage – Stores and manages student datasets in Google Drive for secure, centralized, and easily accessible storage.
4.	Group Photo Processing – Accepts a single group image as input and generates lists of Present, Absent, and Unrecognized students.
5.	Reupload Functionality – Allows reuploading a photo of an unrecognized student to instantly update the attendance record.
6.	Interactive Web Interface – Built with Streamlit for a simple, user-friendly experience.
7.	Real-Time Attendance Reports – Displays updated attendance lists immediately after processing.
8.	Cross-Platform Support – Works on any system with Python and a browser, with no platform restrictions.
9.	Scalability – Capable of handling larger class sizes and expanding datasets without major performance loss.
10.	Data Security – Uses Google Drive API for secure cloud operations with controlled access.

## Technologies Used
1.	Python – Core programming language for building the application.
2.	Streamlit – For creating the interactive and user-friendly web interface.
3.	face_recognition (based on dlib) – For detecting and recognizing student faces.
4.	OpenCV – For image processing, resizing, and handling photo inputs.
5.	NumPy – For numerical operations and handling face encodings.
6.	Google Drive API – For storing and retrieving the student dataset in the cloud.
7.	Pickle / Joblib – For saving and loading pre-trained face encodings.
8.	Pandas – For managing student data and generating attendance lists.
9.	OS & Pathlib – For file handling and directory management.

## Installation steps
1.	Install Python 3.8 
2.	Install dependencies: 
pip install -r requirements.txt
3.	Set Up Google Drive API:
4.	Download wheel file.
5.	Train : 
python -c "from utils.facerec import FaceRecognitionSystem; fr = FaceRecognitionSystem(); fr.train_model('student', n_jobs=2)"
6.	Launch Streamlit:
  streamlit run app.py
7.	To sync with google drive enter drive folder id.
