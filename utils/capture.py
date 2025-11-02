import cv2
import os
import uuid
from datetime import datetime

def capture_student_images(student_name, roll_no, num_angles=5):
    """
    Captures multiple angles of a student's face
    :param student_name: Name of the student
    :param roll_no: Roll number of the student
    :param num_angles: Number of angles to capture (default 5)
    """
    cap = cv2.VideoCapture(0)
    base_dir = "../student_data"
    os.makedirs(base_dir, exist_ok=True)
    
    print(f"\nCapturing {num_angles} angles for {student_name} (Roll No: {roll_no})")
    print("Press 's' to capture, 'q' to quit...")
    
    angle_count = 0
    while angle_count < num_angles:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture image")
            break
            
        # Display instructions on the frame
        instructions = f"Angle {angle_count+1}/{num_angles} - Press 's' to capture"
        cv2.putText(frame, instructions, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow('Student Capture', frame)
        
        key = cv2.waitKey(1)
        if key == ord('s'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_name = f"{base_dir}/{roll_no}_{student_name}_{timestamp}_{uuid.uuid4().hex[:6]}.jpg"
            cv2.imwrite(img_name, frame)
            print(f"Saved: {img_name}")
            angle_count += 1
            
            # Show confirmation
            cv2.putText(frame, "CAPTURED!", (50, 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
            cv2.imshow('Student Capture', frame)
            cv2.waitKey(500)
            
        elif key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("=== Student Data Capture ===")
    name = input("Enter student name: ").strip().replace(" ", "_")
    roll = input("Enter roll number: ").strip()
    angles = int(input("Number of angles to capture (default 5): ") or "5")
    
    capture_student_images(name, roll, angles)