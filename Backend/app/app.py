"""Main Flask application for ErgoVision - AI-powered posture and eye health monitoring system"""

from flask import Flask, render_template, Response, jsonify, request, send_file
from app.modules.posture_detection import PostureDetector
from app.modules.blink_detection import BlinkDetector
from app.modules.eye_rule_timer import EyeRuleTimer
from app.modules.data_manager import DataManager
import cv2
import threading
import time
from datetime import datetime
import io

app = Flask(__name__)

# Global state
detection_active = False
detection_lock = threading.Lock()
video_capture = None         
camera_lock = threading.Lock()

# Initialize modules
posture_detector = PostureDetector()
blink_detector = BlinkDetector()
eye_rule_timer = EyeRuleTimer()
data_manager = DataManager()

# Session tracking
current_session = None
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
video_capture.set(cv2.CAP_PROP_FPS, 20)

# Settings
settings = {
    'bad_posture_threshold': 45  # seconds, configurable
}

def get_camera():
    """Get or create video capture"""
    global video_capture
    with camera_lock:
        if video_capture is None or not video_capture.isOpened():
            video_capture = cv2.VideoCapture(0)
            video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            video_capture.set(cv2.CAP_PROP_FPS, 20)
        return video_capture

def release_camera():
    """Safely release camera"""
    global video_capture
    with camera_lock:
        if video_capture is not None and video_capture.isOpened():
            video_capture.release()
        video_capture = None

def generate_frames():
    """Generator function to stream video frames with pose landmarks"""
    global detection_active
    cam = get_camera()

    while detection_active:
                
            success, frame = video_capture.read()
            if not success:
                break
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Process frame for posture detection
            frame, posture_data = posture_detector.process_frame(frame)
            
            # Process frame for blink detection
            frame, blink_data = blink_detector.process_frame(frame)
            
            # Update current session data
            if current_session:
                with detection_lock:
                    current_session['posture_data'] = posture_data
                    current_session['blink_data'] = blink_data
                    current_session['eye_rule_status'] = eye_rule_timer.get_status()
            
            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    release_camera()
    
    
        


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html', settings=settings)

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start', methods=['POST'])
def start_detection():
    """Start detection session"""
    global detection_active, current_session
    
    with detection_lock:
        if detection_active:
            return jsonify({'status': 'error', 'message': 'Detection already running'}), 400\
            
        release_camera()
        detection_active = True
        
        # Initialize new session
        current_session = {
            'start_time': datetime.now(),
            'posture_data': {},
            'blink_data': {},
            'eye_rule_status': {}
        }
        
        # Reset detectors
        posture_detector.reset()
        blink_detector.reset()
        eye_rule_timer.reset()
        
        return jsonify({'status': 'success', 'message': 'Detection started'})

@app.route('/stop', methods=['POST'])
def stop_detection():
    """Stop detection session and save data"""
    global detection_active, current_session

    with detection_lock:
        if not detection_active:
            return jsonify({'status': 'error', 'message': 'No active detection'}), 400
        
        detection_active = False
        time.sleep(0.3)
        
        # Calculate session duration
        if current_session:
            current_session['end_time'] = datetime.now()
            duration = (current_session['end_time'] - current_session['start_time']).total_seconds()
            current_session['duration'] = duration
            
            # Save session to database
            session_id = data_manager.save_session(current_session)
            
            # Prepare summary
            summary = {
                'session_id': session_id,
                'duration': duration,
                'posture_data': current_session['posture_data'],
                'blink_data': current_session['blink_data']
            }
            
            return jsonify({'status': 'success', 'message': 'Detection stopped', 'summary': summary})
        
        return jsonify({'status': 'success', 'message': 'Detection stopped'})

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get current session statistics"""
    if not detection_active or not current_session:
        # return jsonify({'status': 'error', 'message': 'No active session'}), 400
        return jsonify({
        'posture_status': 'Stopped',
        'head_angle': 0,
        'good_posture_time': 0,
        'bad_posture_time': 0,
        'total_blinks': 0,
        'blink_rate': 0,
        'fatigue_level': 'Normal',
        'eye_rule_alert': False,
        'eye_rule_next': 0,
        'bad_posture_alert': False
    })
    
    with detection_lock:
        stats = {
            'posture_status': current_session['posture_data'].get('status', 'Unknown'),
            'head_angle': current_session['posture_data'].get('head_angle', 0),
            'good_posture_time': current_session['posture_data'].get('good_time', 0),
            'bad_posture_time': current_session['posture_data'].get('bad_time', 0),
            'total_blinks': current_session['blink_data'].get('total_blinks', 0),
            'blink_rate': current_session['blink_data'].get('blink_rate', 0),
            'fatigue_level': current_session['blink_data'].get('fatigue_level', 'Normal'),
            'eye_rule_alert': current_session['eye_rule_status'].get('alert', False),
            'eye_rule_next': current_session['eye_rule_status'].get('next_break', 0),
            'bad_posture_alert': current_session['posture_data'].get('alert', False)
        }
        
        return jsonify(stats)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    """Update application settings"""
    global settings
    
    data = request.json
    if 'bad_posture_threshold' in data:
        threshold = int(data['bad_posture_threshold'])
        if 10 <= threshold <= 300:  # Validate range
            settings['bad_posture_threshold'] = threshold
            posture_detector.set_alert_threshold(threshold)
            return jsonify({'status': 'success', 'message': 'Settings updated'})
    
    return jsonify({'status': 'error', 'message': 'Invalid settings'}), 400

@app.route('/export', methods=['GET'])
def export_report():
    """Generate and download PDF report of the last session"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        # Get the most recent session
        session_data = data_manager.get_latest_session()
    else:
        session_data = data_manager.get_session(int(session_id))
    
    if not session_data:
        return jsonify({'status': 'error', 'message': 'No session data found'}), 404
    
    # Generate PDF
    pdf_buffer = data_manager.generate_pdf_report(session_data)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'ergovision_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@app.route('/history', methods=['GET'])
def get_history():
    """Get session history"""
    sessions = data_manager.get_all_sessions(limit=10)
    return jsonify({'sessions': sessions})

if __name__ == '__main__':
    # Initialize database
    data_manager.initialize_db()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
