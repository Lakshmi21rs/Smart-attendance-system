
import face_recognition
import os
import pickle
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Union
from PIL import Image
from joblib import Parallel, delayed
import warnings
import gc

# Suppress unnecessary warnings
warnings.filterwarnings("ignore")

class FaceRecognitionSystem:
    def __init__(self, model_path=r"C:\smart-attendance-system\models\face_encodings.pkl"):
        self.known_encodings = []
        self.known_metadata = []
        self.model_path = model_path
        os.makedirs(os.path.dirname(model_path), exist_ok=True)

    def _fast_load_image(self, img_path: Union[str, np.ndarray], max_size: int = 400) -> np.ndarray:
        if isinstance(img_path, np.ndarray):
            return img_path
        try:
            with Image.open(img_path) as img:
                img.thumbnail((max_size, max_size))
                return np.array(img)
        except Exception as e:
            print(f"Failed to load {img_path}: {str(e)}")
            raise

    def _optimized_face_locations(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        face_locations = face_recognition.face_locations(
            image, model="hog", number_of_times_to_upsample=1
        )
        
        if not face_locations:
            face_locations = face_recognition.face_locations(
                image, model="cnn", number_of_times_to_upsample=1
            )
        return face_locations

    def _apply_nms(self, boxes: List[Tuple[int, int, int, int]], threshold: float = 0.3) -> List[int]:
        if len(boxes) == 0:
            return []

        boxes_np = np.array([(left, top, right, bottom) for (top, right, bottom, left) in boxes])
        areas = (boxes_np[:, 2] - boxes_np[:, 0] + 1) * (boxes_np[:, 3] - boxes_np[:, 1] + 1)
        pick = []
        x1 = boxes_np[:, 0]
        y1 = boxes_np[:, 1]
        x2 = boxes_np[:, 2]
        y2 = boxes_np[:, 3]
        idxs = np.argsort(y2)
        
        while len(idxs) > 0:
            last = len(idxs) - 1
            i = idxs[last]
            pick.append(i)
            xx1 = np.maximum(x1[i], x1[idxs[:last]])
            yy1 = np.maximum(y1[i], y1[idxs[:last]])
            xx2 = np.minimum(x2[i], x2[idxs[:last]])
            yy2 = np.minimum(y2[i], y2[idxs[:last]])
            w = np.maximum(0, xx2 - xx1 + 1)
            h = np.maximum(0, yy2 - yy1 + 1)
            overlap = (w * h) / areas[idxs[:last]]
            idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > threshold)[0])))
        
        return pick

    def recognize_faces(self, image_input, min_confidence: float = 0.5) -> Tuple[
        Dict[Tuple[str, str], float],
        List[Tuple[str, str]],
        int,
        float,
        List[Tuple[int, int, int, int]],
        List[Tuple[int, int, int, int]],
        List[np.ndarray],
        np.ndarray
    ]:
        if not self.known_encodings and not self.load_model():
            return {}, [], 0, 0.0, [], [], [], np.array([])

        try:
            image = self._fast_load_image(image_input)
            unique_face_locations = set()
            
            for scale in [1.0, 1.25]:
                scaled_img = cv2.resize(image, (0, 0), fx=scale, fy=scale) if scale != 1.0 else image
                locations = self._optimized_face_locations(scaled_img)
                
                for (top, right, bottom, left) in locations:
                    orig_coords = (
                        int(top/scale),
                        int(right/scale),
                        int(bottom/scale), 
                        int(left/scale)
                    )
                    unique_face_locations.add(orig_coords)
            
            all_face_locations = list(unique_face_locations)
            keep_indices = self._apply_nms(all_face_locations)
            all_face_locations = [all_face_locations[i] for i in keep_indices]
            total_faces = len(all_face_locations)
            
            if total_faces == 0:
                return {}, [], 0, 0.0, [], [], [], image
                
            face_encodings = face_recognition.face_encodings(image, all_face_locations)
            present = {}
            recognized_face_locations = []
            recognition_status = [False] * total_faces
            unrecognized_faces = []

            for i, (face_encoding, face_location) in enumerate(zip(face_encodings, all_face_locations)):
                face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                best_match_idx = face_distances.argmin()
                confidence = 1 - face_distances[best_match_idx]

                if confidence > min_confidence:
                    student = self.known_metadata[best_match_idx]
                    key = (student['roll_no'], student['name'])
                    
                    if key not in present or present[key] < confidence:
                        present[key] = confidence
                        recognition_status[i] = True
                        recognized_face_locations.append(face_location)
                else:
                    top, right, bottom, left = face_location
                    face_img = image[top:bottom, left:right]
                    unrecognized_faces.append(face_img)

            unrecognized_count = total_faces - sum(recognition_status)
            all_students = {(m['roll_no'], m['name']) for m in self.known_metadata}
            absent = list(all_students - present.keys())
            avg_conf = sum(present.values())/len(present) if present else 0

            return (
                present, 
                absent, 
                unrecognized_count, 
                avg_conf, 
                all_face_locations,
                recognized_face_locations,
                unrecognized_faces,
                image
            )

        except Exception as e:
            print(f"Recognition error: {str(e)}")
            return {}, [], 0, 0.0, [], [], [], np.array([])
        finally:
            gc.collect()

    def recognize_single_face(self, face_image: np.ndarray, min_confidence: float = 0.5) -> Optional[Tuple[Tuple[str, str], float]]:
        if not self.known_encodings:
            return None

        try:
            face_encodings = face_recognition.face_encodings(face_image)
            if not face_encodings:
                return None

            face_distances = face_recognition.face_distance(self.known_encodings, face_encodings[0])
            best_match_idx = face_distances.argmin()
            confidence = 1 - face_distances[best_match_idx]

            if confidence > min_confidence:
                student = self.known_metadata[best_match_idx]
                return ((student['roll_no'], student['name'])), confidence
            return None
        except Exception as e:
            print(f"Single face recognition error: {str(e)}")
            return None

    def _process_single_image(self, args: Tuple[str, str, str]) -> Optional[Tuple[np.ndarray, str, str, str]]:
        img_path, roll_no, name = args
        try:
            image = self._fast_load_image(img_path)
            if len(image.shape) == 4:
                image = image[..., :3]

            face_locations = self._optimized_face_locations(image)
            if face_locations:
                keep_indices = self._apply_nms(face_locations)
                if keep_indices:
                    face_location = face_locations[keep_indices[0]]
                    encodings = face_recognition.face_encodings(image, [face_location])
                    if encodings:
                        return (encodings[0], roll_no, name, img_path)
        except Exception as e:
            print(f"Error processing {img_path}: {str(e)}")
        return None

    def train_model(self, data_dir: str, n_jobs: int = -1) -> bool:
        self.known_encodings = []
        self.known_metadata = []

        image_paths = []
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        rel_path = os.path.relpath(root, data_dir)
                        if rel_path == '.':
                            roll_no, name = os.path.splitext(file)[0].split('_', 1)
                        else:
                            roll_no, name = rel_path.split('_', 1)
                        image_paths.append((os.path.join(root, file), roll_no, name))
                    except ValueError:
                        print(f"Skipping malformed item: {file}")
                        continue

        print(f"Processing {len(image_paths)} images...")
        results = Parallel(n_jobs=n_jobs)(
            delayed(self._process_single_image)(args)
            for args in image_paths
        )

        valid_results = [r for r in results if r is not None]
        for encoding, roll_no, name, img_path in valid_results:
            self.known_encodings.append(encoding)
            self.known_metadata.append({
                "roll_no": roll_no,
                "name": name.replace('_', ' ').title(),
                "image_path": os.path.abspath(img_path)
            })

        if self.known_encodings:
            self._save_model()
            print(f"Trained on {len(self.known_encodings)} face encodings")
            return True
        
        print("No valid faces found for training")
        return False

    def _save_model(self) -> bool:
        try:
            with open(self.model_path, "wb") as f:
                pickle.dump({
                    "encodings": self.known_encodings,
                    "metadata": self.known_metadata
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception as e:
            print(f"Failed to save model: {str(e)}")
            return False

    def load_model(self) -> bool:
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                    self.known_encodings = data["encodings"]
                    self.known_metadata = data["metadata"]
                print(f"Loaded model with {len(self.known_metadata)} faces")
                return True
            print("No trained model found")
            return False
        except Exception as e:
            print(f"Error loading model: {str(e)}")
            return False

    def backup_to_drive(self, drive_manager, local_dir: str, drive_folder_id: str) -> bool:
        try:
            if not drive_manager.upload_folder(local_dir, drive_folder_id):
                return False
            if os.path.exists(self.model_path):
                if not drive_manager.upload_file(self.model_path, drive_folder_id):
                    return False
            return True
        except Exception as e:
            print(f"Backup failed: {str(e)}")
            return False

    def load_from_drive(self, drive_manager, drive_folder_id: str, local_dir: str = "student") -> bool:
        try:
            if not drive_manager.download_folder(drive_folder_id, local_dir):
                return False

            model_file_name = os.path.basename(self.model_path)
            model_file_id = drive_manager.find_file_by_name(model_file_name, drive_folder_id)

            if model_file_id and not drive_manager.download_file(model_file_id, self.model_path):
                return False

            if os.path.exists(self.model_path):
                return self.load_model()
            return self.train_model(local_dir)
        except Exception as e:
            print(f"Sync failed: {str(e)}")
            return False
        