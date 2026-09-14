"""Blink detection module using MediaPipe FaceMesh"""

import cv2
import mediapipe as mp
import numpy as np
import time

class BlinkDetector:
    """Detects and monitors eye blinks using MediaPipe FaceMesh"""
    
    def __init__(self):
        # Initialize MediaPipe FaceMesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            refine_landmarks=True
        )
        
        # Eye landmark indices (MediaPipe FaceMesh)
        self.LEFT_EYE = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33, 160, 158, 133, 153, 144]
        
        # Tracking variables
        self.total_blinks = 0
        self.blink_threshold = 0.28  # EAR threshold for blink detection
        self.consecutive_frames = 2
        self.ear_history = []        
        self.start_time = time.time()
        self.blink_times = []

        self.last_blink_time = 0
        self.min_blink_interval = 0.4  # seconds

        # Auto-calibration
        self.ear_baseline = None         
        self.ear_samples = []            
        self.calibration_frames = 60
        
    def reset(self):
        """Reset all tracking variables"""
        self.total_blinks = 0
        self.consecutive_frames = 0
        self.start_time = time.time()
        self.blink_times = []
        self.last_blink_time = 0
        self.ear_baseline = None       
        self.ear_samples = []
    
    def calculate_ear(self, eye_points):
        """Calculate Eye Aspect Ratio (EAR)"""
        # Compute vertical distances
        A = np.linalg.norm(eye_points[1] - eye_points[5])
        B = np.linalg.norm(eye_points[2] - eye_points[4])
        
        # Compute horizontal distance
        C = np.linalg.norm(eye_points[0] - eye_points[3])
        
        # EAR formula
        ear = (A + B) / (2.0 * C)
        return ear
    
    def get_eye_points(self, landmarks, eye_indices, frame_shape):
        """Extract eye landmark points"""
        points = []
        for idx in eye_indices:
            landmark = landmarks[idx]
            x = int(landmark.x * frame_shape[1])
            y = int(landmark.y * frame_shape[0])
            points.append(np.array([x, y]))
        return np.array(points)
    
    def calculate_blink_rate(self):
        """Calculate blinks per minute"""
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            return (self.total_blinks / elapsed_time) * 60
        return 0
    
    def assess_fatigue(self, blink_rate):
        """Assess fatigue level based on blink rate"""
        # Normal blink rate: 15-20 blinks per minute
        # Low rate (< 10): Possible eye strain
        # High rate (> 30): Possible fatigue
        if blink_rate < 10:
            return 'Eye Strain'
        elif blink_rate > 30:
            return 'Fatigued'
        else:
            return 'Normal'
    
    def process_frame(self, frame):
        """Process video frame for blink detection"""
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        blink_data = {
            'total_blinks': self.total_blinks,
            'blink_rate': 0,
            'fatigue_level': 'Normal'
        }
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                landmarks = face_landmarks.landmark
                
                # Get eye points
                left_eye_points = self.get_eye_points(landmarks, self.LEFT_EYE, frame.shape)
                right_eye_points = self.get_eye_points(landmarks, self.RIGHT_EYE, frame.shape)
                
                # Calculate EAR for both eyes
                left_ear = self.calculate_ear(left_eye_points)
                right_ear = self.calculate_ear(right_eye_points)
                avg_ear = (left_ear + right_ear) / 2.0

                if self.ear_baseline is None:
                    self.ear_samples.append(avg_ear)
                    if len(self.ear_samples) >= self.calibration_frames:
                        self.ear_baseline = np.mean(self.ear_samples)
                        # Set threshold to 75% of baseline open-eye EAR
                        self.blink_threshold = self.ear_baseline * 0.75
                        print(f"[Blink] Calibrated EAR baseline: {self.ear_baseline:.3f}, threshold: {self.blink_threshold:.3f}")
                
                
                current_time = time.time()
                if avg_ear < self.blink_threshold:
                    self.consecutive_frames += 1
                else:
                    if (
                        self.consecutive_frames >= 1 and
                        (current_time - self.last_blink_time) > self.min_blink_interval
                    ):
                        self.total_blinks += 1
                        self.last_blink_time = current_time

                    self.consecutive_frames = 0
                
                # Calculate blink rate and fatigue
                blink_rate = self.calculate_blink_rate()
                fatigue_level = self.assess_fatigue(blink_rate)
                
                # Update data
                blink_data = {
                    'total_blinks': self.total_blinks,
                    'blink_rate': round(blink_rate, 1),
                    'fatigue_level': fatigue_level
                }
                
                # Draw eye landmarks
                for point in left_eye_points:
                    cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)
                for point in right_eye_points:
                    cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)
                
                # Draw blink info
                if self.ear_baseline is None:
                    cal_text = f'Calibrating... ({len(self.ear_samples)}/{self.calibration_frames})'
                    cv2.putText(frame, cal_text, (10, frame.shape[0] - 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                    cv2.putText(frame, f'EAR: {avg_ear:.3f}', (10, frame.shape[0] - 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
                    cv2.putText(frame, f'Blinks: {self.total_blinks}', (10, frame.shape[0] - 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(frame, f'Rate: {blink_rate:.1f}/min', (10, frame.shape[0] - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(frame, f'Status: {fatigue_level}', (10, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame, blink_data
    
    def __del__(self):
        """Cleanup"""
        self.face_mesh.close()
