"""Posture detection module using MediaPipe Pose"""

import cv2
import mediapipe as mp
import numpy as np
import time


class PostureDetector:
    """Detects and monitors posture using MediaPipe Pose landmarks"""

    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Tracking variables
        self.good_posture_start = None
        self.bad_posture_start = None
        self.total_good_time = 0
        self.total_bad_time = 0
        self.current_status = 'Unknown'
        self.alert_threshold = 45
        self.show_alert = False

        # ── Calibration ──────────────────────────────────────────────
        # We capture the user's "good posture" baseline for the first
        # N frames so thresholds adapt to their body proportions and
        # camera angle instead of using fixed magic numbers.
        self.calibration_frames   = 60        # ~3 s at 20 fps
        self.calibration_samples  = []
        self.baseline             = None      # dict set after calibration

    # ─────────────────────────────────────────────────────────────────
    def reset(self):
        self.good_posture_start  = None
        self.bad_posture_start   = None
        self.total_good_time     = 0
        self.total_bad_time      = 0
        self.current_status      = 'Unknown'
        self.show_alert          = False
        self.calibration_samples = []
        self.baseline            = None

    def set_alert_threshold(self, seconds):
        self.alert_threshold = seconds

    # ─────────────────────────────────────────────────────────────────
    # Geometry helpers
    # ─────────────────────────────────────────────────────────────────
    def _pt(self, landmarks, lm_enum):
        """Return (x, y) normalised coords for a landmark enum."""
        lm = landmarks[lm_enum]
        return np.array([lm.x, lm.y])

    def calculate_angle(self, point1, point2, point3):
        """Angle at point2 formed by point1-point2-point3 (degrees)."""
        a = np.array([point1.x, point1.y])
        b = np.array([point2.x, point2.y])
        c = np.array([point3.x, point3.y])
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(np.degrees(radians))
        if angle > 180:
            angle = 360 - angle
        return angle

    def calculate_head_tilt(self, landmarks):
        """
        Return head tilt angle in 0-90° range.
        0° = perfectly level, 90° = fully tilted.
        """
        PL = self.mp_pose.PoseLandmark
        left_ear  = landmarks[PL.LEFT_EAR]
        right_ear = landmarks[PL.RIGHT_EAR]
        dx = right_ear.x - left_ear.x
        dy = right_ear.y - left_ear.y
        angle = abs(np.degrees(np.arctan2(dy, dx)))
        if angle > 90:
            angle = 180 - angle
        return angle

    # ─────────────────────────────────────────────────────────────────
    # Metric extraction  (all values independent of person size)
    # ─────────────────────────────────────────────────────────────────
    def _extract_metrics(self, landmarks):
        """
        Returns a dict of normalised posture metrics.

        Metrics
        -------
        neck_angle      : average ear-shoulder-hip angle (both sides)
                          Good posture ~160-175°, slouch <150°
        shoulder_slope  : |Δy| between left & right shoulder
                          Large = rolled/uneven shoulders
        ear_fwd_offset  : how far ears are in front of shoulders (x-axis)
                          Positive = head forward. Good ≈ 0, bad > 0.07
        ear_y_rel       : ear y relative to shoulder y (normalised)
                          Drops when head tilts down / hunches
        """
        PL = self.mp_pose.PoseLandmark
        lm = landmarks

        L_SH  = self._pt(lm, PL.LEFT_SHOULDER)
        R_SH  = self._pt(lm, PL.RIGHT_SHOULDER)
        L_HIP = self._pt(lm, PL.LEFT_HIP)
        R_HIP = self._pt(lm, PL.RIGHT_HIP)
        L_EAR = self._pt(lm, PL.LEFT_EAR)
        R_EAR = self._pt(lm, PL.RIGHT_EAR)

        # Neck angle — both sides, averaged
        left_neck  = self.calculate_angle(lm[PL.LEFT_EAR],
                                          lm[PL.LEFT_SHOULDER],
                                          lm[PL.LEFT_HIP])
        right_neck = self.calculate_angle(lm[PL.RIGHT_EAR],
                                          lm[PL.RIGHT_SHOULDER],
                                          lm[PL.RIGHT_HIP])
        neck_angle = (left_neck + right_neck) / 2.0

        # Shoulder slope
        shoulder_slope = abs(L_SH[1] - R_SH[1])

        # Head-forward offset: ear midpoint x vs shoulder midpoint x
        ear_mid_x = (L_EAR[0] + R_EAR[0]) / 2
        sh_mid_x  = (L_SH[0]  + R_SH[0])  / 2
        ear_fwd   = abs(ear_mid_x - sh_mid_x)

        # Ear height relative to shoulder height
        # In image coords y increases downward, so a LOWER ear (larger y)
        # means the head is drooping toward the chest.
        ear_mid_y = (L_EAR[1] + R_EAR[1]) / 2
        sh_mid_y  = (L_SH[1]  + R_SH[1])  / 2
        ear_y_rel = sh_mid_y - ear_mid_y   # positive = ear above shoulder (good)

        return {
            'neck_angle':     neck_angle,
            'shoulder_slope': shoulder_slope,
            'ear_fwd':        ear_fwd,
            'ear_y_rel':      ear_y_rel,
        }

    # ─────────────────────────────────────────────────────────────────
    # Calibration
    # ─────────────────────────────────────────────────────────────────
    def _calibrate(self, metrics):
        """
        Collect good-posture samples during the first N frames then
        lock in personalised thresholds.
        """
        self.calibration_samples.append(metrics)
        n = len(self.calibration_samples)

        if n < self.calibration_frames:
            return False   # still calibrating

        # Compute baseline from collected samples
        def avg(key): return np.mean([s[key] for s in self.calibration_samples])

        self.baseline = {
            'neck_angle':     avg('neck_angle'),
            'shoulder_slope': avg('shoulder_slope'),
            'ear_fwd':        avg('ear_fwd'),
            'ear_y_rel':      avg('ear_y_rel'),
        }

        # Thresholds = baseline shifted by a tolerance band
        # (personalised to this user's camera angle & proportions)
        self.thresh = {
            # neck straightens to ~170° when sitting well.
            # Allow 18° drop before flagging bad.
            'neck_angle_min':      self.baseline['neck_angle'] - 18,

            # shoulder slope should stay close to baseline
            'shoulder_slope_max':  self.baseline['shoulder_slope'] + 0.06,

            # if ears move forward more than 0.07 normalised units → head craning
            'ear_fwd_max':         self.baseline['ear_fwd'] + 0.07,

            # if ear drops significantly below baseline → head drooping
            'ear_y_rel_min':       self.baseline['ear_y_rel'] - 0.08,
        }

        print(f"[Posture] Calibrated baseline: {self.baseline}")
        print(f"[Posture] Thresholds:          {self.thresh}")
        return True

    # ─────────────────────────────────────────────────────────────────
    # Posture assessment
    # ─────────────────────────────────────────────────────────────────
    def assess_posture(self, landmarks):
        """
        Returns ('Good'|'Bad', reason_string, metrics_dict).
        Uses calibrated thresholds if available, otherwise falls back
        to conservative fixed thresholds.
        """
        metrics = self._extract_metrics(landmarks)

        # ── Not yet calibrated: collect samples ──
        if self.baseline is None:
            done = self._calibrate(metrics)
            if not done:
                # During calibration assume user is sitting well
                return 'Good', 'Calibrating...', metrics
            # Just finished calibrating — assess immediately
        
        # ── Assess against personalised thresholds ──
        bad_reasons = []

        if metrics['neck_angle'] < self.thresh['neck_angle_min']:
            bad_reasons.append(
                f"Neck bent ({metrics['neck_angle']:.0f}° < {self.thresh['neck_angle_min']:.0f}°)"
            )

        if metrics['shoulder_slope'] > self.thresh['shoulder_slope_max']:
            bad_reasons.append("Uneven shoulders")

        if metrics['ear_fwd'] > self.thresh['ear_fwd_max']:
            bad_reasons.append("Head forward")

        if metrics['ear_y_rel'] < self.thresh['ear_y_rel_min']:
            bad_reasons.append("Head drooping")

        if bad_reasons:
            return 'Bad', ', '.join(bad_reasons), metrics
        return 'Good', 'Good posture', metrics

    # ─────────────────────────────────────────────────────────────────
    # Main frame processor
    # ─────────────────────────────────────────────────────────────────
    def process_frame(self, frame):
        current_time = time.time()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results   = self.pose.process(rgb_frame)

        posture_data = {
            'status':    'Unknown',
            'head_angle': 0,
            'good_time':  self.total_good_time,
            'bad_time':   self.total_bad_time,
            'alert':      False,
        }

        if results.pose_landmarks:
            # Draw skeleton
            self.mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2),
            )

            landmarks = results.pose_landmarks.landmark

            # Head tilt angle
            head_angle = self.calculate_head_tilt(landmarks)

            # Posture assessment
            posture_status, reason, metrics = self.assess_posture(landmarks)
            self.current_status = posture_status

            # ── Timing ──
            if posture_status == 'Good':
                if self.good_posture_start is None:
                    self.good_posture_start = current_time
                if self.bad_posture_start is not None:
                    self.total_bad_time  += current_time - self.bad_posture_start
                    self.bad_posture_start = None
                    self.show_alert       = False
            else:
                if self.bad_posture_start is None:
                    self.bad_posture_start = current_time
                if self.good_posture_start is not None:
                    self.total_good_time  += current_time - self.good_posture_start
                    self.good_posture_start = None

                if (current_time - self.bad_posture_start) >= self.alert_threshold:
                    self.show_alert = True

            # ── Build data dict ──
            good_elapsed = (current_time - self.good_posture_start) if self.good_posture_start else 0
            bad_elapsed  = (current_time - self.bad_posture_start)  if self.bad_posture_start  else 0

            posture_data = {
                'status':    posture_status,
                'head_angle': round(head_angle, 1),
                'good_time':  round(self.total_good_time + good_elapsed, 1),
                'bad_time':   round(self.total_bad_time  + bad_elapsed,  1),
                'alert':      self.show_alert,
            }

            # ── Overlay text on frame ──
            # Calibration progress bar
            if self.baseline is None:
                n   = len(self.calibration_samples)
                pct = int(n / self.calibration_frames * 100)
                cv2.putText(frame, f'Calibrating: {pct}%  (sit straight!)',
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            else:
                status_color = (0, 200, 80) if posture_status == 'Good' else (0, 0, 255)
                cv2.putText(frame, f'Posture: {posture_status}',
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)

                # Show first reason if bad
                if posture_status == 'Bad':
                    cv2.putText(frame, reason.split(',')[0],
                                (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 255), 2)

            cv2.putText(frame, f'Head Angle: {head_angle:.1f}deg',
                        (10, 90 if self.baseline else 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

            if self.show_alert:
                cv2.putText(frame, 'BAD POSTURE ALERT!',
                            (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        return frame, posture_data

    # ─────────────────────────────────────────────────────────────────
    def __del__(self):
        self.pose.close()