"""Main Flask application for Align and Blink - AI-powered posture and eye health monitoring system"""

import base64
import os
import secrets
import numpy as np
from flask import Flask, render_template, jsonify, request, send_file, session
from app.modules.posture_detection import PostureDetector
from app.modules.blink_detection import BlinkDetector
from app.modules.eye_rule_timer import EyeRuleTimer
from app.modules.data_manager import DataManager
import cv2
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Secret key — needed so Flask can safely give each visitor their own
# signed cookie (this is what lets us tell visitors apart).
# In production, set SECRET_KEY as an environment variable so it stays
# the same across restarts. If it's not set, we generate one automatically
# (fine for now — it just means everyone's session resets on server restart).
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Reject any request body bigger than 5 MB. A single webcam frame as
# base64 JPEG is usually well under 1 MB, so 5 MB gives plenty of room
# without letting a bad/huge payload eat server memory.
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Initialize modules
data_manager = DataManager()

# ── PER-VISITOR STATE ────────────────────────────────────────────
# Instead of one global set of detectors shared by everyone, each visitor
# (identified by their browser's session cookie) gets their own entry here.
#
#   user_sessions = {
#       "abc123...": { 'detection_active': False, 'posture_detector': ..., ... },
#       "def456...": { 'detection_active': False, 'posture_detector': ..., ... },
#   }
#
# sessions_lock guards the DICTIONARY ITSELF (adding/removing visitors).
# Each visitor's own 'lock' guards THEIR data (so two visitors never block
# each other, but one visitor's own requests still stay safe/consistent).
user_sessions = {}
sessions_lock = threading.Lock()


def get_user_session():
    """Return this visitor's own state dictionary, creating it if needed."""
    if 'user_id' not in session:
        session['user_id'] = secrets.token_hex(16)
    user_id = session['user_id']

    with sessions_lock:
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'detection_active': False,
                'posture_detector': PostureDetector(),
                'blink_detector': BlinkDetector(),
                'eye_rule_timer': EyeRuleTimer(),
                'current_session': None,
                'lock': threading.Lock(),
                'settings': {'bad_posture_threshold': 45},
            }
        return user_sessions[user_id]


@app.route('/')
def index():
    """Main dashboard page"""
    us = get_user_session()
    return render_template('index.html', settings=us['settings'])


@app.route('/process_frame', methods=['POST'])
def process_frame():
    """Receive a single frame from the browser, run detection, return processed frame"""
    us = get_user_session()

    if not us['detection_active']:
        return jsonify({'status': 'error', 'message': 'Detection not active'}), 400

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'status': 'error', 'message': 'No image provided'}), 400

    try:
        # Decode base64 image sent from browser (format: "data:image/jpeg;base64,....")
        image_data = data['image'].split(',')[1] if ',' in data['image'] else data['image']
        img_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'status': 'error', 'message': 'Could not decode image'}), 400

        # Flip horizontally for a natural mirror effect (raise right hand -> appears on your left)
        frame = cv2.flip(frame, 1)

        # Run existing detection logic — unchanged, just using THIS visitor's detectors
        frame, posture_data = us['posture_detector'].process_frame(frame)
        frame, blink_data = us['blink_detector'].process_frame(frame)

        # Update this visitor's current session data
        if us['current_session']:
            with us['lock']:
                us['current_session']['posture_data'] = posture_data
                us['current_session']['blink_data'] = blink_data
                us['current_session']['eye_rule_status'] = us['eye_rule_timer'].get_status()

        # Encode processed frame back to base64 to send to browser
        ret, buffer = cv2.imencode('.jpg', frame)
        processed_b64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({
            'status': 'success',
            'image': 'data:image/jpeg;base64,' + processed_b64
        })

    except Exception as e:
        print(f"ERROR in process_frame: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/start', methods=['POST'])
def start_detection():
    """Start detection session"""
    us = get_user_session()

    with us['lock']:
        if us['detection_active']:
            return jsonify({'status': 'error', 'message': 'Detection already running'}), 400

        us['detection_active'] = True

        # Initialize new session for THIS visitor
        us['current_session'] = {
            'start_time': datetime.now(),
            'posture_data': {},
            'blink_data': {},
            'eye_rule_status': {}
        }

        # Reset this visitor's detectors
        us['posture_detector'].reset()
        us['blink_detector'].reset()
        us['eye_rule_timer'].reset()

        return jsonify({'status': 'success', 'message': 'Detection started'})


@app.route('/stop', methods=['POST'])
def stop_detection():
    """Stop detection session and save data"""
    us = get_user_session()

    request_data = request.get_json(silent=True) or {}
    user_name = request_data.get('user_name', 'Unknown')

    with us['lock']:
        if not us['detection_active']:
            return jsonify({'status': 'error', 'message': 'No active detection'}), 400
        us['detection_active'] = False

    time.sleep(0.8)

    with us['lock']:
        if us['current_session']:
            us['current_session']['end_time'] = datetime.now()
            us['current_session']['user_name'] = user_name
            duration = (us['current_session']['end_time'] - us['current_session']['start_time']).total_seconds()
            us['current_session']['duration'] = duration

            # Save session to database
            session_id = data_manager.save_session(us['current_session'])

            # Prepare summary
            summary = {
                'session_id': session_id,
                'duration': duration,
                'posture_data': us['current_session']['posture_data'],
                'blink_data': us['current_session']['blink_data']
            }

            return jsonify({'status': 'success', 'message': 'Detection stopped', 'summary': summary})

        return jsonify({'status': 'success', 'message': 'Detection stopped'})


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get current session statistics"""
    us = get_user_session()

    if not us['detection_active'] or not us['current_session']:
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

    with us['lock']:
        stats = {
            'posture_status': us['current_session']['posture_data'].get('status', 'Unknown'),
            'head_angle': us['current_session']['posture_data'].get('head_angle', 0),
            'good_posture_time': us['current_session']['posture_data'].get('good_time', 0),
            'bad_posture_time': us['current_session']['posture_data'].get('bad_time', 0),
            'total_blinks': us['current_session']['blink_data'].get('total_blinks', 0),
            'blink_rate': us['current_session']['blink_data'].get('blink_rate', 0),
            'fatigue_level': us['current_session']['blink_data'].get('fatigue_level', 'Normal'),
            'eye_rule_alert': us['current_session']['eye_rule_status'].get('alert', False),
            'eye_rule_next': us['current_session']['eye_rule_status'].get('next_break', 0),
            'bad_posture_alert': us['current_session']['posture_data'].get('alert', False)
        }

        return jsonify(stats)


@app.route('/update_settings', methods=['POST'])
def update_settings():
    """Update application settings"""
    us = get_user_session()

    data = request.get_json(silent=True)
    if not data or 'bad_posture_threshold' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid settings'}), 400

    try:
        threshold = int(data['bad_posture_threshold'])
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid settings'}), 400

    if 10 <= threshold <= 300:  # Validate range
        us['settings']['bad_posture_threshold'] = threshold
        us['posture_detector'].set_alert_threshold(threshold)
        return jsonify({'status': 'success', 'message': 'Settings updated'})

    return jsonify({'status': 'error', 'message': 'Invalid settings'}), 400


@app.route('/export', methods=['GET'])
def export_report():
    """Generate and download PDF report of the last session"""
    session_id = request.args.get('session_id')

    if not session_id:
        session_data = data_manager.get_latest_session()
    else:
        try:
            session_id_int = int(session_id)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid session_id'}), 400
        session_data = data_manager.get_session(session_id_int)

    if not session_data:
        return jsonify({'status': 'error', 'message': 'No session data found'}), 404

    pdf_buffer = data_manager.generate_pdf_report(session_data)

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'alignandblink_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@app.route('/history', methods=['GET'])
def get_history():
    """Get session history"""
    sessions = data_manager.get_all_sessions(limit=10)
    return jsonify({'sessions': sessions})


if __name__ == '__main__':
    # Initialize database
    data_manager.initialize_db()

    # Render (and most cloud hosts) assign the port to listen on via the
    # PORT environment variable — they don't let you pick 5000 yourself.
    # Locally, PORT won't be set, so we fall back to 5000 as before.
    port = int(os.environ.get('PORT', 5000))

    # Debug mode should be OFF by default (it can leak source code and
    # allow arbitrary code execution if it's ever left on in production).
    # To turn it on for local development, set the environment variable
    # FLASK_DEBUG=1 before running, e.g.:
    #   Windows (PowerShell):  $env:FLASK_DEBUG=1; python -m app.app
    #   Mac/Linux:             FLASK_DEBUG=1 python -m app.app
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'

    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)