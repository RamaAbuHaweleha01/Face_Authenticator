import cv2
import numpy as np
import os
import json
from datetime import datetime
import time

class FaceRecognitionSystem:
    def __init__(self, encodings_dir='face_encodings', model_dir='face_models'):
        self.encodings_dir = encodings_dir
        self.model_dir = model_dir
        os.makedirs(encodings_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)
        
        # Load OpenCV face detector
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        
        # Initialize LBPH face recognizer with multiple fallback options
        self.recognizer = None
        try:
            # Try the newer OpenCV version
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            print("✓ Using cv2.face.LBPHFaceRecognizer_create()")
        except AttributeError:
            try:
                # Try the older OpenCV version
                self.recognizer = cv2.face.createLBPHFaceRecognizer()
                print("✓ Using cv2.face.createLBPHFaceRecognizer()")
            except AttributeError:
                try:
                    # Try another fallback
                    self.recognizer = cv2.face_LBPHFaceRecognizer.create()
                    print("✓ Using cv2.face_LBPHFaceRecognizer.create()")
                except:
                    print("⚠ Warning: Could not initialize LBPH face recognizer")
                    print("Please install opencv-contrib-python: pip install opencv-contrib-python")
                    self.recognizer = None
        
        # Store user labels and face data
        self.user_labels = {}
        self.user_face_data = {}  # Store multiple face images for comparison
        self.load_user_data()
        
        # Stricter verification thresholds
        self.CONFIDENCE_THRESHOLD = 60  # Lower = stricter (0 is perfect match)
        self.MIN_MATCHES_REQUIRED = 5   # Need 5 good matches
        self.VERIFICATION_ATTEMPTS = 80  # Number of frames to analyze
    
    def load_user_data(self):
        """Load user data from files"""
        label_map_path = os.path.join(self.model_dir, "label_map.json")
        if os.path.exists(label_map_path):
            try:
                with open(label_map_path, 'r') as f:
                    self.user_labels = json.load(f)
            except:
                self.user_labels = {}
    
    def save_user_data(self):
        """Save user data to files"""
        label_map_path = os.path.join(self.model_dir, "label_map.json")
        with open(label_map_path, 'w') as f:
            json.dump(self.user_labels, f)
    
    def get_user_label(self, user_id):
        """Get or create a numeric label for the user"""
        if user_id not in self.user_labels:
            if user_id.isdigit():
                label = int(user_id)
            else:
                label = abs(hash(user_id)) % 10000
            self.user_labels[user_id] = label
            self.save_user_data()
        return self.user_labels[user_id]
    
    def preprocess_face(self, face_roi):
        """Advanced face preprocessing for better matching"""
        # Resize to standard size
        face_resized = cv2.resize(face_roi, (200, 200))
        
        # Apply histogram equalization for better contrast
        face_equalized = cv2.equalizeHist(face_resized)
        
        # Apply Gaussian blur to reduce noise
        face_blurred = cv2.GaussianBlur(face_equalized, (3, 3), 0)
        
        return face_blurred
    
    def detect_and_validate_face(self, gray_frame):
        """Detect face and validate it's a real face"""
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray_frame, 
            scaleFactor=1.05,
            minNeighbors=8,
            minSize=(100, 100),
            maxSize=(400, 400)
        )
        
        if len(faces) == 0:
            return None, None, None
        
        # Get the largest face
        largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
        (x, y, w, h) = largest_face
        
        # Validate face aspect ratio
        aspect_ratio = w / h
        if aspect_ratio < 0.7 or aspect_ratio > 1.3:
            return None, None, "Invalid face shape"
        
        # Extract face ROI
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(gray_frame.shape[1] - x, w + 2*margin)
        h = min(gray_frame.shape[0] - y, h + 2*margin)
        
        face_roi = gray_frame[y:y+h, x:x+w]
        
        # Check for eyes (liveness detection)
        eyes = self.eye_cascade.detectMultiScale(face_roi, minNeighbors=10)
        if len(eyes) < 2:
            return None, None, "Eyes not detected"
        
        return (x, y, w, h), face_roi, None
    
    def capture_face(self, num_samples=30):
        """Capture face images from webcam with strict quality control"""
        if self.recognizer is None:
            raise Exception("Face recognizer not initialized. Please install opencv-contrib-python")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise Exception("Could not open webcam. Please check your camera.")
        
        face_images = []
        face_quality_scores = []
        samples_taken = 0
        start_time = time.time()
        
        print("\n" + "="*50)
        print("FACE REGISTRATION PROCESS")
        print("="*50)
        print("Please follow these guidelines:")
        print("• Look directly at the camera")
        print("• Ensure good lighting")
        print("• Remove glasses if possible")
        print("• Keep your face centered")
        print("• Press 'Q' to cancel")
        print("="*50 + "\n")
        
        while samples_taken < num_samples and (time.time() - start_time) < 45:
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect and validate face
            face_coords, face_roi, error = self.detect_and_validate_face(gray)
            
            if face_coords and face_roi is not None:
                # Preprocess face
                processed_face = self.preprocess_face(face_roi)
                
                # Calculate face quality (variance of Laplacian for sharpness)
                sharpness = cv2.Laplacian(processed_face, cv2.CV_64F).var()
                
                # Only accept sharp faces
                if sharpness > 50:  # Sharpness threshold
                    face_images.append(processed_face)
                    face_quality_scores.append(sharpness)
                    samples_taken += 1
                    
                    x, y, w, h = face_coords
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Show quality indicator
                    quality_percent = min(100, int(sharpness / 10))
                    cv2.putText(frame, f'Quality: {quality_percent}%', 
                               (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    # Show progress
                    progress = int((samples_taken / num_samples) * 100)
                    cv2.putText(frame, f'Progress: {progress}% ({samples_taken}/{num_samples})', 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, 'Face too blurry, hold still', 
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    if face_coords:
                        x, y, w, h = face_coords
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            else:
                if error:
                    cv2.putText(frame, error, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(frame, 'Please look at the camera', 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            cv2.imshow('Face Registration - Press Q to cancel', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if len(face_images) == 0:
            raise Exception("No valid faces captured. Please ensure good lighting and face visibility.")
        
        print(f"\n✓ Successfully captured {len(face_images)} high-quality face images")
        print(f"✓ Average quality score: {np.mean(face_quality_scores):.0f}\n")
        
        return face_images
    
    def train_model(self, user_id, face_images):
        """Train LBPH model with multiple samples"""
        if self.recognizer is None:
            raise Exception("Face recognizer not initialized")
        
        label = self.get_user_label(user_id)
        
        # Create labels array
        labels = np.array([label for _ in range(len(face_images))])
        
        # Convert face images to numpy array
        faces_array = np.array(face_images)
        
        # Train recognizer
        self.recognizer.train(faces_array, labels)
        
        # Save the model
        model_path = os.path.join(self.model_dir, f"user_{user_id}.yml")
        self.recognizer.save(model_path)
        
        # Also save face images for reference
        user_dir = os.path.join(self.encodings_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        for i, face_img in enumerate(face_images[:10]):  # Save first 10 faces
            cv2.imwrite(os.path.join(user_dir, f"face_{i}.jpg"), face_img)
        
        return model_path
    
    def save_encoding(self, user_id, face_images):
        """Save face data and train model"""
        return self.train_model(user_id, face_images)
    
    def load_encoding(self, user_id):
        """Load face model for verification"""
        if self.recognizer is None:
            return None
            
        model_path = os.path.join(self.model_dir, f"user_{user_id}.yml")
        if os.path.exists(model_path):
            try:
                # Create a new recognizer instance for loading
                try:
                    recognizer = cv2.face.LBPHFaceRecognizer_create()
                except:
                    recognizer = cv2.face.createLBPHFaceRecognizer()
                recognizer.read(model_path)
                return recognizer
            except Exception as e:
                print(f"Error loading model: {e}")
                return None
        return None
    
    def load_reference_faces(self, user_id):
        """Load reference face images for comparison"""
        user_dir = os.path.join(self.encodings_dir, user_id)
        reference_faces = []
        
        if os.path.exists(user_dir):
            for i in range(10):
                face_path = os.path.join(user_dir, f"face_{i}.jpg")
                if os.path.exists(face_path):
                    face = cv2.imread(face_path, cv2.IMREAD_GRAYSCALE)
                    if face is not None:
                        reference_faces.append(face)
        
        return reference_faces
    
    def verify_face(self, user_id, model=None):
        """Enhanced face verification with multiple checks and strict matching"""
        if self.recognizer is None:
            raise Exception("Face recognizer not initialized")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise Exception("Could not open webcam. Please check your camera.")
        
        # Load model if not provided
        if model is None:
            model = self.load_encoding(user_id)
            if model is None:
                cap.release()
                raise Exception("No face model found for user")
        
        # Load reference faces for additional verification
        reference_faces = self.load_reference_faces(user_id)
        
        expected_label = self.get_user_label(user_id)
        
        print("\n" + "="*50)
        print("FACE VERIFICATION PROCESS")
        print("="*50)
        print("Please follow these guidelines:")
        print("• Look directly at the camera")
        print("• Hold still for 5 seconds")
        print("• Ensure good lighting")
        print("• Press 'Q' to cancel")
        print("="*50 + "\n")
        
        successful_matches = []
        failed_matches = []
        total_attempts = 0
        best_confidence = float('inf')
        best_label = None
        face_detected_count = 0
        
        start_time = time.time()
        max_duration = 8  # Maximum 8 seconds
        
        while total_attempts < self.VERIFICATION_ATTEMPTS and (time.time() - start_time) < max_duration:
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect and validate face
            face_coords, face_roi, error = self.detect_and_validate_face(gray)
            
            if face_coords and face_roi is not None:
                face_detected_count += 1
                x, y, w, h = face_coords
                
                # Preprocess face
                processed_face = self.preprocess_face(face_roi)
                
                # Check face sharpness
                sharpness = cv2.Laplacian(processed_face, cv2.CV_64F).var()
                if sharpness < 40:
                    cv2.putText(frame, 'Face too blurry, hold still', 
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                    continue
                
                try:
                    # Predict with LBPH
                    label, confidence = model.predict(processed_face)
                    
                    total_attempts += 1
                    
                    # Update best match
                    if confidence < best_confidence:
                        best_confidence = confidence
                        best_label = label
                    
                    # Calculate match percentage
                    match_percent = max(0, min(100, (1 - confidence/150) * 100))
                    
                    # Debug output
                    print(f"Frame {total_attempts}: Label={label}, Expected={expected_label}, "
                          f"Confidence={confidence:.1f} ({match_percent:.0f}%)")
                    
                    # Strict matching criteria
                    is_correct_label = (label == expected_label)
                    is_confident = confidence < self.CONFIDENCE_THRESHOLD
                    
                    if is_correct_label and is_confident:
                        successful_matches.append(confidence)
                        cv2.putText(frame, f'✓ GOOD MATCH! ({match_percent:.0f}%)', 
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        
                        # Check if we have enough good matches
                        if len(successful_matches) >= self.MIN_MATCHES_REQUIRED:
                            cv2.putText(frame, 'VERIFICATION SUCCESSFUL!', 
                                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            break
                    else:
                        failed_matches.append(confidence)
                        if not is_correct_label:
                            message = f'✗ WRONG PERSON DETECTED!'
                        else:
                            message = f'✗ WEAK MATCH! ({match_percent:.0f}%)'
                        
                        cv2.putText(frame, message, 
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                    
                    # Show confidence bar
                    confidence_percent = match_percent
                    bar_width = int((confidence_percent / 100) * w)
                    color = (0, 255, 0) if is_correct_label and is_confident else (0, 0, 255)
                    cv2.rectangle(frame, (x, y + h + 5), (x + bar_width, y + h + 15), color, -1)
                    
                except Exception as e:
                    print(f"Prediction error: {e}")
            else:
                if error:
                    cv2.putText(frame, error, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(frame, 'Position your face in the frame', 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Show progress
            remaining_time = max(0, int(max_duration - (time.time() - start_time)))
            cv2.putText(frame, f'Time: {remaining_time}s | Good matches: {len(successful_matches)}/{self.MIN_MATCHES_REQUIRED}', 
                       (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow('Face Verification - Press Q to cancel', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Final verification decision with strict criteria
        print("\n" + "="*50)
        print("VERIFICATION RESULTS")
        print("="*50)
        print(f"Total frames analyzed: {total_attempts}")
        print(f"Faces detected: {face_detected_count}")
        print(f"Successful matches: {len(successful_matches)}")
        print(f"Failed matches: {len(failed_matches)}")
        
        if successful_matches:
            avg_confidence = np.mean(successful_matches)
            avg_match_percent = max(0, min(100, (1 - avg_confidence/150) * 100))
            print(f"Average confidence: {avg_confidence:.1f} ({avg_match_percent:.0f}% match)")
            print(f"Best confidence: {min(successful_matches):.1f}")
        
        # VERY STRICT verification - must meet ALL criteria
        verification_success = False
        
        if len(successful_matches) >= self.MIN_MATCHES_REQUIRED:
            avg_success_conf = np.mean(successful_matches)
            if avg_success_conf < 55:  # Very strict average confidence
                verification_success = True
                print("✓ SUCCESS: Multiple high-quality matches")
            else:
                print("✗ FAILED: Average confidence too low")
        elif len(successful_matches) >= 3 and best_confidence < 45:
            verification_success = True
            print("✓ SUCCESS: Excellent matches with high confidence")
        elif len(successful_matches) >= 2 and best_confidence < 40:
            verification_success = True
            print("✓ SUCCESS: Exceptional single matches")
        else:
            print("✗ FAILED: Insufficient match quality")
        
        print(f"\nFinal verdict: {'✓ VERIFICATION SUCCESSFUL' if verification_success else '✗ VERIFICATION FAILED'}")
        print("="*50 + "\n")
        
        return verification_success