import streamlit as st
import os
from PIL import Image
import numpy as np
import datetime
import shutil
import pyodbc
import sqlite3
import subprocess
import traceback
from utils.facerec import FaceRecognitionSystem
from utils.drive_integration import GoogleDriveManager

st.set_page_config(
    page_title="Smart Attendance System",
    page_icon="📊",
    layout="wide"
)

class SQLServerManager:
    def __init__(self, server=None, database="auto_attendance"):
        self.server = server
        self.database = database
        self.connection = None
        self.use_sqlite = False
        self.last_error = None
    
    def connect(self):
        try:
            # Try different server names if none specified
            servers_to_try = [
                "localhost",
                ".",
                ".\\SQLEXPRESS",
                "(local)",
                "localhost\\SQLEXPRESS"
            ]
            
            if self.server:
                servers_to_try = [self.server] + servers_to_try
            
            for server in servers_to_try:
                try:
                    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={self.database};Trusted_Connection=yes;'
                    self.connection = pyodbc.connect(conn_str)
                    st.success(f"✅ Connected to server: {server}")
                    return True
                except Exception as e:
                    continue
            
            # Fallback to SQLite
            st.warning("⚠️ SQL Server not available. Using SQLite as fallback.")
            self.connection = sqlite3.connect('attendance.db')
            self.use_sqlite = True
            return True
            
        except Exception as e:
            self.last_error = str(e)
            st.error(f"❌ All connection attempts failed: {str(e)}")
            st.info("""
            💡 Troubleshooting tips:
            1. Make sure SQL Server is running (check Services)
            2. Try enabling TCP/IP in SQL Server Configuration Manager
            3. Check if SQL Server Browser service is running
            4. Try using SQL Server Authentication instead
            """)
            return False
    
    def create_tables(self):
        if not self.connection:
            return False
        
        try:
            if self.use_sqlite:
                # SQLite table creation
                cursor = self.connection.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        class_name TEXT,
                        attendance_date DATETIME,
                        present_count INTEGER,
                        absent_count INTEGER,
                        unrecognized_count INTEGER,
                        average_confidence REAL,
                        report_text TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS attendance_details (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attendance_id INTEGER,
                        roll_no TEXT,
                        student_name TEXT,
                        status TEXT,
                        confidence REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (attendance_id) REFERENCES attendance (id)
                    )
                """)
                self.connection.commit()
                return True
            else:
                # SQL Server table creation
                cursor = self.connection.cursor()
                
                # Check if tables already exist
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = 'attendance'
                """)
                attendance_exists = cursor.fetchone()[0] > 0
                
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = 'attendance_details'
                """)
                details_exists = cursor.fetchone()[0] > 0
                
                # Create attendance table if it doesn't exist
                if not attendance_exists:
                    cursor.execute("""
                        CREATE TABLE attendance (
                            id INT IDENTITY(1,1) PRIMARY KEY,
                            class_name NVARCHAR(100),
                            attendance_date DATETIME,
                            present_count INT,
                            absent_count INT,
                            unrecognized_count INT,
                            average_confidence FLOAT,
                            report_text NVARCHAR(MAX),
                            created_at DATETIME DEFAULT GETDATE()
                        )
                    """)
                
                # Create attendance_details table if it doesn't exist
                if not details_exists:
                    cursor.execute("""
                        CREATE TABLE attendance_details (
                            id INT IDENTITY(1,1) PRIMARY KEY,
                            attendance_id INT FOREIGN KEY REFERENCES attendance(id),
                            roll_no NVARCHAR(50),
                            student_name NVARCHAR(100),
                            status NVARCHAR(20),
                            confidence FLOAT NULL,
                            created_at DATETIME DEFAULT GETDATE()
                        )
                    """)
                
                self.connection.commit()
                return True
            
        except Exception as e:
            self.last_error = str(e)
            st.error(f"Table creation failed: {str(e)}")
            return False
    
    def save_attendance_report(self, class_name, present, absent, unrecognized_count, avg_conf, report_text):
        if not self.connection:
            return False
        
        try:
            attendance_date = datetime.datetime.now()
            
            if self.use_sqlite:
                # SQLite implementation
                cursor = self.connection.cursor()
                
                # Insert main attendance record
                cursor.execute("""
                    INSERT INTO attendance (class_name, attendance_date, present_count, absent_count, 
                                          unrecognized_count, average_confidence, report_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (class_name, attendance_date, len(present), len(absent), 
                     unrecognized_count, avg_conf, report_text))
                
                # Get the inserted ID
                attendance_id = cursor.lastrowid
                
                # Insert present students
                for (roll, name), conf in present.items():
                    cursor.execute("""
                        INSERT INTO attendance_details (attendance_id, roll_no, student_name, status, confidence)
                        VALUES (?, ?, ?, 'present', ?)
                    """, (attendance_id, roll, name, conf))
                
                # Insert absent students
                for roll, name in absent:
                    cursor.execute("""
                        INSERT INTO attendance_details (attendance_id, roll_no, student_name, status)
                        VALUES (?, ?, ?, 'absent')
                    """, (attendance_id, roll, name))
                
                self.connection.commit()
                return attendance_id
                
            else:
                # SQL Server implementation
                cursor = self.connection.cursor()
                
                # Insert main attendance record
                cursor.execute("""
                    INSERT INTO attendance (class_name, attendance_date, present_count, absent_count, 
                                          unrecognized_count, average_confidence, report_text)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, class_name, attendance_date, len(present), len(absent), 
                   unrecognized_count, avg_conf, report_text)
                
                # Get the inserted ID
                attendance_id = cursor.fetchone()[0]
                
                # Insert present students
                for (roll, name), conf in present.items():
                    cursor.execute("""
                        INSERT INTO attendance_details (attendance_id, roll_no, student_name, status, confidence)
                        VALUES (?, ?, ?, 'present', ?)
                    """, attendance_id, roll, name, conf)
                
                # Insert absent students
                for roll, name in absent:
                    cursor.execute("""
                        INSERT INTO attendance_details (attendance_id, roll_no, student_name, status)
                        VALUES (?, ?, ?, 'absent')
                    """, attendance_id, roll, name)
                
                self.connection.commit()
                return attendance_id
            
        except Exception as e:
            self.last_error = str(e)
            st.error(f"Failed to save attendance: {str(e)}")
            # Show detailed error information
            with st.expander("Detailed Error Information"):
                st.code(traceback.format_exc())
            return None
    
    def get_attendance_history(self, days=30):
        if not self.connection:
            return []
        
        try:
            if self.use_sqlite:
                # SQLite implementation
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, class_name, attendance_date, present_count, 
                           absent_count, unrecognized_count, average_confidence
                    FROM attendance
                    WHERE attendance_date >= datetime('now', ?)
                    ORDER BY attendance_date DESC
                """, (f'-{days} days',))
                
                return cursor.fetchall()
                
            else:
                # SQL Server implementation
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT a.id, a.class_name, a.attendance_date, a.present_count, 
                           a.absent_count, a.unrecognized_count, a.average_confidence
                    FROM attendance a
                    WHERE a.attendance_date >= DATEADD(day, -?, GETDATE())
                    ORDER BY a.attendance_date DESC
                """, days)
                
                return cursor.fetchall()
            
        except Exception as e:
            self.last_error = str(e)
            st.error(f"Failed to fetch attendance history: {str(e)}")
            return []
    
    def close(self):
        if self.connection:
            self.connection.close()

def check_sql_server_status():
    """Check if SQL Server services are running"""
    st.info("🔍 Checking SQL Server status...")
    
    # Common SQL Server service names
    services = [
        "MSSQLSERVER",
        "MSSQL$SQLEXPRESS",
        "SQLSERVERAGENT",
        "SQLBrowser"
    ]
    
    results = []
    for service in services:
        try:
            result = subprocess.run(
                ['sc', 'query', service], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if "RUNNING" in result.stdout:
                results.append(f"✅ {service}: Running")
            else:
                results.append(f"❌ {service}: Not running")
        except:
            results.append(f"❓ {service}: Not found")
    
    st.write("**SQL Server Services Status:**")
    for result in results:
        st.write(result)

def test_sql_server_connection(server, database, use_windows_auth=True, username=None, password=None):
    """Test SQL Server connection with different methods"""
    try:
        if use_windows_auth:
            conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        else:
            conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};'
        
        connection = pyodbc.connect(conn_str)
        connection.close()
        return True, f"✅ Successfully connected to {server}"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)}"

@st.cache_resource
def init_system():
    fr = FaceRecognitionSystem()
    try:
        fr.load_model()
        if not fr.known_encodings:
            st.session_state.needs_training = True
    except Exception as e:
        st.error(f"Failed to load model: {str(e)}")
    return fr

def get_student_image(fr, roll_no):
    for student in fr.known_metadata:
        if student['roll_no'] == roll_no:
            try:
                img = Image.open(student['image_path'])
                img.thumbnail((100, 100))
                return img
            except:
                return None
    return None

def display_student_card(fr, roll_no, name, status, confidence=None):
    col1, col2 = st.columns([1, 4])
    with col1:
        student_img = get_student_image(fr, roll_no)
        if student_img:
            st.image(student_img, width=60)
        else:
            st.image(Image.new('RGB', (60, 60), color='gray'), width=60)
    
    with col2:
        if status == "present":
            st.markdown(f"**{roll_no}** - {name}  \n✅ Present ({confidence:.1%} confidence)" if confidence else f"**{roll_no}** - {name}  \n✅ Present")
        else:
            st.markdown(f"**{roll_no}** - {name}  \n❌ Absent")

def create_student_folder(class_name, roll_no, student_name, photo_files, drive=None, drive_folder_id=None):
    class_folder = os.path.join("student", f"Class_{class_name}")
    student_folder = os.path.join(class_folder, f"{roll_no}_{student_name}")
    
    if os.path.exists(student_folder):
        shutil.rmtree(student_folder)
    
    os.makedirs(student_folder, exist_ok=True)
    
    saved_paths = []
    for i, photo_file in enumerate(photo_files, 1):
        photo_path = os.path.join(student_folder, f"photo_{i}.jpg")
        with open(photo_path, "wb") as f:
            f.write(photo_file.getbuffer())
        saved_paths.append(photo_path)
    
    if drive and drive_folder_id:
        try:
            class_folders = drive.list_folders(drive_folder_id)
            class_folder_id = None
            
            for folder in class_folders:
                if folder['name'] == f"Class_{class_name}":
                    class_folder_id = folder['id']
                    break
            
            if not class_folder_id:
                class_folder_id = drive.create_folder(f"Class_{class_name}", drive_folder_id)
            
            student_folders = drive.list_folders(class_folder_id)
            student_folder_id = None
            
            for folder in student_folders:
                if folder['name'] == f"{roll_no}_{student_name}":
                    student_folder_id = folder['id']
                    break
            
            if not student_folder_id:
                student_folder_id = drive.create_folder(f"{roll_no}_{student_name}", class_folder_id)
            
            for photo_path in saved_paths:
                drive.upload_file(photo_path, student_folder_id)
            
            return saved_paths[0]
        except Exception as e:
            st.error(f"Drive sync error: {str(e)}")
            return saved_paths[0]
    
    return saved_paths[0]

def validate_student_inputs(class_name, roll_no, student_name, photo_files):
    if not class_name:
        return "Class name is required"
    if not roll_no:
        return "Roll number is required"
    if not student_name:
        return "Student name is required"
    if not photo_files or len(photo_files) == 0:
        return "At least one photo is required"
    if len(photo_files) > 4:
        return "Maximum 4 photos allowed per student"
    return None

def generate_report(present, absent, unrecognized_count, avg_conf):
    report = [
        f"Attendance Report - {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"Present: {len(present)} | Absent: {len(absent)} | Unrecognized: {unrecognized_count}",
        f"Average Confidence: {avg_conf:.1%}",
        "\nPRESENT STUDENTS:"
    ]
    report.extend(f"- {roll}: {name} ({conf:.1%})" for (roll, name), conf in sorted(present.items()))
    report.append("\nABSENT STUDENTS:")
    report.extend(f"- {roll}: {name}" for roll, name in sorted(absent))
    return "\n".join(report)

def display_attendance_history():
    if st.session_state.get('sql_enabled', False):
        if st.button("📊 View Attendance History"):
            sql_manager = SQLServerManager()
            
            if sql_manager.connect():
                history = sql_manager.get_attendance_history(30)
                
                st.subheader("Attendance History (Last 30 days)")
                
                if not history:
                    st.info("No attendance records found in the database.")
                else:
                    for record in history:
                        with st.expander(f"{record[2]:%Y-%m-%d %H:%M} - {record[1]} - Present: {record[3]}"):
                            st.write(f"**Class:** {record[1]}")
                            st.write(f"**Date:** {record[2]}")
                            st.write(f"**Present:** {record[3]}")
                            st.write(f"**Absent:** {record[4]}")
                            st.write(f"**Unrecognized:** {record[5]}")
                            st.write(f"**Avg Confidence:** {record[6]:.1%}")
                sql_manager.close()
            else:
                st.error("❌ Database connection failed")

def display_attendance_results(fr, attendance_data, is_updated=False):
    present = attendance_data['present']
    absent = attendance_data['absent']
    unrecognized_count = attendance_data['unrecognized_count']
    avg_conf = attendance_data['avg_conf']
    
    if is_updated:
        st.subheader("Updated Attendance Results")
    else:
        st.subheader("Attendance Results")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Present", len(present))
    col2.metric("❌ Absent", len(absent))
    col3.metric("❓ Unrecognized", unrecognized_count)
    
    if avg_conf > 0:
        st.success(f"Average confidence: {avg_conf:.1%}")
    
    with st.expander(f"Present Students ({len(present)})", expanded=True):
        if present:
            for (roll, name), conf in sorted(present.items()):
                display_student_card(fr, roll, name, "present", conf)
        else:
            st.info("No recognized students")
    
    with st.expander(f"Absent Students ({len(absent)})"):
        if absent:
            for roll, name in sorted(absent):
                display_student_card(fr, roll, name, "absent")
        else:
            st.info("All students present!")
    
    if unrecognized_count > 0 and 'unrecognized_faces' in attendance_data:
        with st.expander(f"Unrecognized Faces ({unrecognized_count})", expanded=True):
            st.warning(f"{unrecognized_count} faces couldn't be identified")
            
            cols = st.columns(3)
            for i, face_img in enumerate(attendance_data['unrecognized_faces']):
                with cols[i % 3]:
                    st.image(face_img, caption=f"Unrecognized Face {i+1}", use_container_width=True)
                    
                    with st.form(key=f"reupload_form_{i}_{st.session_state.form_key}"):
                        reuploaded = st.file_uploader(
                            f"Reupload better photo for Face {i+1}",
                            type=["jpg", "jpeg", "png"],
                            key=f"reupload_{i}_{st.session_state.form_key}"
                        )
                        
                        if st.form_submit_button(f"Update Recognition for Face {i+1}"):
                            if reuploaded:
                                try:
                                    reupload_img = Image.open(reuploaded)
                                    reupload_np = np.array(reupload_img)
                                    
                                    if reupload_np.shape[2] == 4:
                                        reupload_np = reupload_np[..., :3]
                                    
                                    recognition_result = fr.recognize_single_face(reupload_np)
                                    
                                    if recognition_result:
                                        (roll, name), conf = recognition_result
                                        
                                        # Update attendance data
                                        attendance_data['present'][(roll, name)] = conf
                                        
                                        if (roll, name) in attendance_data['absent']:
                                            attendance_data['absent'].remove((roll, name))
                                        
                                        # Remove from unrecognized faces
                                        updated_faces = attendance_data['unrecognized_faces'].copy()
                                        updated_faces.pop(i)
                                        attendance_data['unrecognized_faces'] = updated_faces
                                        attendance_data['unrecognized_count'] = len(updated_faces)
                                        
                                        st.session_state.attendance_data = attendance_data
                                        st.session_state.form_key += 1
                                        st.rerun()
                                    else:
                                        st.error("Still couldn't recognize this face. Please add as new student.")
                                except Exception as e:
                                    st.error(f"Error processing reupload: {str(e)}")
                            else:
                                st.warning("Please upload a photo first")
                    
                    if st.button(f"Add as New Student", key=f"add_face_{i}_{st.session_state.form_key}"):
                        st.session_state.new_student_img = face_img
                        st.session_state.show_add_student = True
                        st.rerun()
            
            st.info("Possible reasons:")
            st.markdown("""
            - New students not in system
            - Poor image quality
            - Significant appearance changes
            """)
    
    report = generate_report(present, absent, unrecognized_count, avg_conf)
    
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "📥 Download Report",
            report,
            file_name=f"attendance_{datetime.datetime.now():%Y%m%d_%H%M}.txt",
            use_container_width=True
        )

    with col2:
        if st.session_state.get('sql_enabled', False):
            if st.button("💾 Save to Database", use_container_width=True, key=f"save_db_{st.session_state.form_key}"):
                # Debug: Show what data we're trying to save
                with st.expander("Debug: Data being saved"):
                    st.write(f"Class: {st.session_state.get('current_class', 'Default Class')}")
                    st.write(f"Present students: {len(present)}")
                    st.write(f"Absent students: {len(absent)}")
                    st.write(f"Unrecognized: {unrecognized_count}")
                    st.write(f"Avg confidence: {avg_conf}")
                    
                sql_manager = SQLServerManager()
                
                if sql_manager.connect():
                    # First create tables if they don't exist
                    if sql_manager.create_tables():
                        st.success("✅ Tables created/verified successfully")
                    else:
                        st.error(f"❌ Failed to create tables: {sql_manager.last_error}")
                        sql_manager.close()
                        return
                    
                    class_name = st.session_state.get('current_class', 'Default Class')
                    
                    # Debug: Check if we're using SQLite or SQL Server
                    if sql_manager.use_sqlite:
                        st.info("📁 Using SQLite database (fallback)")
                    else:
                        st.info("🗄️ Using SQL Server database")
                    
                    attendance_id = sql_manager.save_attendance_report(
                        class_name,
                        present,
                        absent,
                        unrecognized_count,
                        avg_conf,
                        report
                    )
                    
                    if attendance_id:
                        st.success(f"✅ Attendance saved to database (ID: {attendance_id})")
                        # Refresh the form to prevent duplicate submissions
                        st.session_state.form_key += 1
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to save attendance: {sql_manager.last_error}")
                    sql_manager.close()
                else:
                    st.error("❌ Database connection failed")

def main():
    # Initialize session state
    if 'show_add_student' not in st.session_state:
        st.session_state.show_add_student = False
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
    if 'attendance_data' not in st.session_state:
        st.session_state.attendance_data = None
    if 'processed_img' not in st.session_state:
        st.session_state.processed_img = None
    if 'unrecognized_faces' not in st.session_state:
        st.session_state.unrecognized_faces = []
    if 'original_upload' not in st.session_state:
        st.session_state.original_upload = None
    if 'current_class' not in st.session_state:
        st.session_state.current_class = "Default Class"
    
    fr = init_system()
    drive = None
    
    with st.sidebar:
        st.header("⚙️ System Management")
        
        # Add class selection
        st.session_state.current_class = st.text_input("Current Class", value=st.session_state.current_class)
        
        with st.expander("➕ Add Students", expanded=False):
            with st.form(key=f'add_student_form_{st.session_state.form_key}'):
                class_name = st.text_input("Class Name", value=st.session_state.current_class, key=f"class_name_{st.session_state.form_key}")
                roll_no = st.text_input("Roll Number", key=f"roll_no_{st.session_state.form_key}")
                student_name = st.text_input("Student Name", key=f"student_name_{st.session_state.form_key}")
                
                photo_files = st.file_uploader(
                    "Upload Student Photos (up to 4, different angles)", 
                    type=["jpg", "jpeg", "png"], 
                    accept_multiple_files=True,
                    key=f"student_photos_{st.session_state.form_key}"
                )
                
                if st.form_submit_button("Add Student"):
                    error = validate_student_inputs(class_name, roll_no, student_name, photo_files)
                    if error:
                        st.error(error)
                    else:
                        try:
                            drive_instance = None
                            drive_folder_id = None
                            
                            if st.session_state.get('drive_enabled', False) and os.path.exists('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json'):
                                drive_instance = GoogleDriveManager('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json')
                                drive_folder_id = st.session_state.get('smartattendancesystem-465906')
                            
                            first_photo_path = create_student_folder(
                                class_name,
                                roll_no,
                                student_name,
                                photo_files[:4],
                                drive_instance,
                                drive_folder_id
                            )
                            
                            st.success(f"""
                            ✅ Successfully added student:
                            - Name: {student_name}
                            - Roll: {roll_no}
                            - Class: {class_name}
                            - Photos uploaded: {len(photo_files)}
                            """)
                            
                            if drive_instance and drive_folder_id:
                                st.success("Student data successfully synced to Google Drive")
                            
                            st.session_state.form_key += 1
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error adding student: {str(e)}")

        if st.button("🔄 Train Model", disabled=not os.path.exists("student")):
            with st.spinner("Training..."):
                try:
                    fr.train_model("student")
                    st.session_state.needs_training = False
                    st.success("Model trained!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Training failed: {str(e)}")
        
        if not os.path.exists("student"):
            st.warning("Create 'student' folder with photos")
        
        st.divider()
        st.subheader("Google Drive Sync")
        
        drive_enabled = st.toggle("Enable Google Drive", key="drive_enabled")
        if drive_enabled:
            if os.path.exists('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json'):
                drive = GoogleDriveManager('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json')
                drive_folder_id = st.text_input("Drive Folder ID", key="smartattendancesystem-465906")
                
                if st.button("⬇️ Sync from Drive"):
                    with st.spinner("Syncing..."):
                        try:
                            fr.load_from_drive(drive, drive_folder_id)
                            st.success("Sync complete!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Sync failed: {str(e)}")
            else:
                st.warning("Google Drive credentials not found")
                
        st.divider()
        st.subheader("SQL Server Configuration")
        
        sql_enabled = st.toggle("Enable SQL Server", key="sql_enabled")
        
        if sql_enabled:
            # Server selection
            server_option = st.selectbox(
                "Server Instance",
                ["Automatic Detection", "localhost", ".\\SQLEXPRESS", "Custom"],
                key="server_option"
            )
            
            custom_server = None
            if server_option == "Custom":
                custom_server = st.text_input("Custom Server Name", key="custom_server")
            
            # Database selection
            sql_database = st.text_input("Database", value="auto_attendance", key="sql_database")
            
            # Authentication options
            auth_method = st.radio(
                "Authentication Method",
                ["Windows Authentication", "SQL Server Authentication"],
                key="auth_method"
            )
            
            sql_username = None
            sql_password = None
            if auth_method == "SQL Server Authentication":
                sql_username = st.text_input("Username", value="sa", key="sql_username")
                sql_password = st.text_input("Password", type="password", key="sql_password")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Test Connection"):
                    # Determine which server to use
                    if server_option == "Automatic Detection":
                        server_to_try = None
                    elif server_option == "Custom":
                        server_to_try = custom_server
                    else:
                        server_to_try = server_option
                    
                    if auth_method == "SQL Server Authentication" and sql_username and sql_password:
                        # Test SQL Server Authentication
                        success, message = test_sql_server_connection(
                            server_to_try or "localhost", 
                            sql_database, 
                            False, 
                            sql_username, 
                            sql_password
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        # Test Windows Authentication
                        sql_manager = SQLServerManager(server_to_try, sql_database)
                        if sql_manager.connect():
                            st.success("✅ Connection successful!")
                            sql_manager.create_tables()
                            sql_manager.close()
            
            with col2:
                if st.button("Check SQL Status"):
                    check_sql_server_status()
            
            st.info("💡 Tip: If SQL Server fails, the app will automatically use SQLite as a fallback.")

    st.title("📊 Smart Attendance System")
    
    # Add attendance history button
    display_attendance_history()
    
    if not os.path.exists("student"):
        st.warning("### Setup Required")
        st.markdown("""
        <div style="background-color:#f0f2f6;padding:20px;border-radius:10px">
        <h4>To get started:</h4>
        <ol>
            <li>Create a folder named <code>student</code></li>
            <li>Add students using the 'Add Students' section</li>
            <li>Click "Train Model"</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        return
    
    if not fr.known_encodings:
        st.info("### Training Required")
        st.markdown("""
        <div style="background-color:#e6f3ff;padding:20px;border-radius:10px">
        <h4>Next Steps:</h4>
        <ol>
            <li>Add student photos using the sidebar</li>
            <li>Click "Train Model" in the sidebar</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        return

    uploaded_file = st.file_uploader(
        "Upload Class Photo", 
        type=["jpg", "jpeg", "png"],
        help="For best results, use clear photos with visible faces",
        key=f"uploader_{st.session_state.form_key}"
    )

    if uploaded_file:
        st.session_state.original_upload = uploaded_file
        try:
            img = Image.open(uploaded_file)
            img_np = np.array(img)
            
            if img_np.shape[2] == 4:
                img_np = img_np[..., :3]
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(img_np, caption="Uploaded Photo", use_container_width=True)
            
            with col2:
                with st.spinner("Recognizing faces..."):
                    present, absent, unrecognized_count, avg_conf, _, _, unrecognized_faces, _ = fr.recognize_faces(img_np)
                    
                    st.session_state.attendance_data = {
                        'present': dict(present),
                        'absent': list(absent),
                        'unrecognized_count': unrecognized_count,
                        'avg_conf': avg_conf,
                        'unrecognized_faces': unrecognized_faces
                    }
                    
                    display_attendance_results(fr, st.session_state.attendance_data)

        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    elif st.session_state.attendance_data:
        display_attendance_results(fr, st.session_state.attendance_data, is_updated=True)

    if st.session_state.get('show_add_student', False) and 'new_student_img' in st.session_state:
        with st.sidebar.expander("➕ Add Unrecognized Student", expanded=True):
            with st.form("add_unrecognized_student"):
                class_name = st.text_input("Class Name", value=st.session_state.current_class, key="new_class_name")
                roll_no = st.text_input("Roll Number", key="new_roll_no")
                student_name = st.text_input("Student Name", key="new_student_name")
                
                if st.form_submit_button("Add Student"):
                    try:
                        temp_path = "temp_face.jpg"
                        Image.fromarray(st.session_state.new_student_img).save(temp_path)
                        
                        drive_instance = None
                        drive_folder_id = None
                        
                        if st.session_state.get('drive_enabled', False) and os.path.exists('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json'):
                            drive_instance = GoogleDriveManager('C:/smart-attendance-system/credentials/smartattendancesystem-465906-1d185d330be1.json')
                            drive_folder_id = st.session_state.get('smartattendancesystem-465906')
                        
                        first_photo_path = create_student_folder(
                            class_name,
                            roll_no,
                            student_name,
                            [open(temp_path, "rb")],
                            drive_instance,
                            drive_folder_id
                        )
                        
                        st.success(f"Added new student: {student_name} (Roll: {roll_no})")
                        st.session_state.show_add_student = False
                        os.remove(temp_path)
                        
                        with st.spinner("Retraining model with new student..."):
                            fr.train_model("student")
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding student: {str(e)}")

if __name__ == "__main__":
    main()