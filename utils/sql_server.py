import pyodbc
import streamlit as st
from datetime import datetime
import sqlite3
import subprocess
import traceback

class SQLServerManager:
    def __init__(self, server=None, database="auto_attendance"):
        self.server = server
        self.database = database
        self.connection = None
        self.use_sqlite = False
    
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
            st.error(f"❌ All connection attempts failed")
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
            else:
                # SQL Server table creation
                cursor = self.connection.cursor()
                
                # Create attendance table if it doesn't exist
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='attendance' AND xtype='U')
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
                
                # Create attendance_details table
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='attendance_details' AND xtype='U')
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
            st.error(f"Table creation failed: {str(e)}")
            return False
    
    def save_attendance_report(self, class_name, present, absent, unrecognized_count, avg_conf, report_text):
        if not self.connection:
            st.error("No database connection available")
            return False
        
        try:
            if self.use_sqlite:
                # SQLite implementation
                cursor = self.connection.cursor()
                
                # Insert main attendance record
                cursor.execute("""
                    INSERT INTO attendance (class_name, attendance_date, present_count, absent_count, 
                                          unrecognized_count, average_confidence, report_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (class_name, datetime.now(), len(present), len(absent), 
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
                st.success(f"✅ Saved to SQLite database (ID: {attendance_id})")
                return attendance_id
                
            else:
                # SQL Server implementation
                cursor = self.connection.cursor()
                
                # Insert main attendance record
                cursor.execute("""
                    INSERT INTO attendance (class_name, attendance_date, present_count, absent_count, 
                                          unrecognized_count, average_confidence, report_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, class_name, datetime.now(), len(present), len(absent), 
                   unrecognized_count, avg_conf, report_text)
                
                # Get the inserted ID
                cursor.execute("SELECT SCOPE_IDENTITY()")
                result = cursor.fetchone()
                if result:
                    attendance_id = result[0]
                else:
                    st.error("Failed to get attendance ID from SQL Server")
                    return None
                
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
                st.success(f"✅ Saved to SQL Server database (ID: {attendance_id})")
                return attendance_id
        
        except Exception as e:
            st.error(f"Failed to save attendance: {str(e)}")
            # Add more detailed error information
            st.error(f"Error details: {traceback.format_exc()}")
            return None
    
    def test_database_operations(self):
        """Test basic database operations"""
        try:
            if self.use_sqlite:
                st.info("Testing SQLite operations...")
                cursor = self.connection.cursor()
                
                # Test insert
                cursor.execute("INSERT INTO attendance (class_name, attendance_date, present_count) VALUES (?, ?, ?)",
                             ("Test Class", datetime.now(), 1))
                attendance_id = cursor.lastrowid
                
                # Test select
                cursor.execute("SELECT * FROM attendance WHERE id = ?", (attendance_id,))
                result = cursor.fetchone()
                
                if result:
                    st.success("✅ SQLite operations test passed")
                    # Clean up
                    cursor.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,))
                    self.connection.commit()
                    return True
                else:
                    st.error("❌ SQLite test failed")
                    return False
            else:
                st.info("Testing SQL Server operations...")
                cursor = self.connection.cursor()
                
                # Test insert
                cursor.execute("INSERT INTO attendance (class_name, attendance_date, present_count) VALUES (?, ?, ?)",
                             "Test Class", datetime.now(), 1)
                
                # Test get ID
                cursor.execute("SELECT SCOPE_IDENTITY()")
                attendance_id = cursor.fetchone()[0]
                
                # Test select
                cursor.execute("SELECT * FROM attendance WHERE id = ?", attendance_id)
                result = cursor.fetchone()
                
                if result:
                    st.success("✅ SQL Server operations test passed")
                    # Clean up
                    cursor.execute("DELETE FROM attendance WHERE id = ?", attendance_id)
                    self.connection.commit()
                    return True
                else:
                    st.error("❌ SQL Server test failed")
                    return False
                    
        except Exception as e:
            st.error(f"Database test failed: {str(e)}")
            return False
    
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