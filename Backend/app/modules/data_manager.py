"""Data management module for session storage and PDF report generation"""

import sqlite3
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import io

class DataManager:
    """Manages session data storage and report generation"""
    
    def __init__(self, db_path='sessions.db'):
        self.db_path = db_path
        self.initialize_db()
    
    def initialize_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT DEFAULT 'Unknown',
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration REAL NOT NULL,
                good_posture_time REAL,
                bad_posture_time REAL,
                total_blinks INTEGER,
                blink_rate REAL,
                fatigue_level TEXT,
                head_angle REAL,
                posture_status TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_session(self, session_data):
        """Save session data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        posture_data = session_data.get('posture_data', {})
        blink_data = session_data.get('blink_data', {})
        
        cursor.execute('''
            INSERT INTO sessions (
                start_time, end_time, duration,
                good_posture_time, bad_posture_time,
                total_blinks, blink_rate, fatigue_level,
                head_angle, posture_status, user_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_data['start_time'].isoformat(),
            session_data['end_time'].isoformat(),
            session_data['duration'],
            posture_data.get('good_time', 0),
            posture_data.get('bad_time', 0),
            blink_data.get('total_blinks', 0),
            blink_data.get('blink_rate', 0),
            blink_data.get('fatigue_level', 'Normal'),
            posture_data.get('head_angle', 0),
            posture_data.get('status', 'Unknown'),
            session_data.get('user_name', 'Unknown')
        ))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_session(self, session_id):
        """Retrieve a specific session"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_latest_session(self):
        """Retrieve the most recent session"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_sessions(self, limit=10):
        """Retrieve all sessions with optional limit"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions ORDER BY id DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def generate_pdf_report(self, session_data):
        """Generate PDF report for a session"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30
        )
        story.append(Paragraph('Align & Blink Session Report', title_style))

        user_name = session_data.get('user_name', 'Unknown')   # ← add
        story.append(Paragraph(f'Report for: <b>{user_name}</b>', styles['Normal']))  # ← add
        story.append(Spacer(1, 0.2*inch))
        
        # Session Information
        session_info = [
            ['Session ID:', str(session_data.get('id', 'N/A'))],
            ['Start Time:', session_data.get('start_time', 'N/A')],
            ['End Time:', session_data.get('end_time', 'N/A')],
            ['Duration:', f"{session_data.get('duration', 0):.1f} seconds"]
        ]
        
        info_table = Table(session_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F4F6F8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Posture Summary
        story.append(Paragraph('Posture Summary', styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        posture_data = [
            ['Good Posture Time:', f"{session_data.get('good_posture_time', 0):.1f} seconds"],
            ['Bad Posture Time:', f"{session_data.get('bad_posture_time', 0):.1f} seconds"],
            ['Final Posture Status:', session_data.get('posture_status', 'Unknown')],
            ['Head Angle:', f"{session_data.get('head_angle', 0):.1f}°"]
        ]
        
        posture_table = Table(posture_data, colWidths=[2*inch, 4*inch])
        posture_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(posture_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Blink Statistics
        story.append(Paragraph('Blink Statistics', styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        blink_data = [
            ['Total Blinks:', str(session_data.get('total_blinks', 0))],
            ['Blink Rate:', f"{session_data.get('blink_rate', 0):.1f} blinks/minute"],
            ['Fatigue Level:', session_data.get('fatigue_level', 'Normal')]
        ]
        
        blink_table = Table(blink_data, colWidths=[2*inch, 4*inch])
        blink_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(blink_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Recommendations
        story.append(Paragraph('Recommendations', styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        recommendations = []
        
        # Posture recommendations
        good_time = session_data.get('good_posture_time', 0)
        bad_time = session_data.get('bad_posture_time', 0)
        if bad_time > good_time:
            recommendations.append('• Focus on maintaining good posture. Keep your back straight and shoulders relaxed.')
        
        # Blink recommendations
        blink_rate = session_data.get('blink_rate', 0)
        if blink_rate < 10:
            recommendations.append('• Increase your blink rate to prevent eye strain. Remember to blink regularly.')
        elif blink_rate > 30:
            recommendations.append('• High blink rate detected. Consider taking more frequent breaks to reduce eye fatigue.')
        
        # 20-20-20 rule reminder
        recommendations.append('• Follow the 20-20-20 rule: Every 20 minutes, look at something 20 feet away for 20 seconds.')
        
        for rec in recommendations:
            story.append(Paragraph(rec, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
