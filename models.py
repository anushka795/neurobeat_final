from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import json

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'patient' or 'clinician'
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient_profile = db.relationship('PatientProfile', foreign_keys='PatientProfile.user_id', backref='user', uselist=False)
    clinician_profile = db.relationship('ClinicianProfile', backref='user', uselist=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PatientProfile(db.Model):
    __tablename__ = 'patient_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    condition = db.Column(db.String(50), nullable=False)  # 'parkinsons' or 'stroke'
    baseline_cadence = db.Column(db.Float)  # steps per minute
    baseline_tapping_speed = db.Column(db.Float)  # taps per minute
    baseline_speech_rate = db.Column(db.Float)  # syllables per minute
    target_cadence = db.Column(db.Float)
    target_speech_rate = db.Column(db.Float)
    assigned_clinician_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Stroke-specific fields
    stroke_affected_side = db.Column(db.String(20))  # 'left', 'right', 'bilateral'
    stroke_severity = db.Column(db.String(20))  # 'mild', 'moderate', 'severe'
    aphasia_type = db.Column(db.String(30))  # 'broca', 'wernicke', 'global', 'none'
    dysarthria_severity = db.Column(db.String(20))  # 'mild', 'moderate', 'severe', 'none'
    motor_impairment_level = db.Column(db.String(20))  # 'mild', 'moderate', 'severe'
    cognitive_status = db.Column(db.String(20))  # 'normal', 'mild_impairment', 'moderate_impairment'
    emotional_status = db.Column(db.String(30))  # 'stable', 'mild_depression', 'anxiety', 'mixed'
    preferred_music_genre = db.Column(db.String(50))
    preferred_beat_sound = db.Column(db.String(20), default='metronome')  # metronome, drum, soft_bell, wooden_block, piano  # Patient's preferred music style
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = db.relationship('TherapySession', backref='patient', lazy=True)

class ClinicianProfile(db.Model):
    __tablename__ = 'clinician_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profession = db.Column(db.String(100))
    license_number = db.Column(db.String(50))
    specialization = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # No direct relationship - will query manually for assigned patients

class TherapySession(db.Model):
    __tablename__ = 'therapy_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id'), nullable=False)
    session_type = db.Column(db.String(50), nullable=False)  # 'gait_trainer', 'speech_rhythm', 'upper_limb_motor', 'melodic_intonation', 'cognitive_rhythm'
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    initial_bpm = db.Column(db.Float, nullable=False)
    final_bpm = db.Column(db.Float)
    target_bpm = db.Column(db.Float, nullable=False)
    duration_seconds = db.Column(db.Integer)
    accuracy_score = db.Column(db.Float)  # 0-100 percentage
    completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    
    # Stroke-specific fields
    affected_limb = db.Column(db.String(20))  # For motor sessions
    speech_clarity_score = db.Column(db.Float)  # For speech sessions
    cognitive_load_level = db.Column(db.Integer)  # 1-5 scale for cognitive sessions
    emotional_response = db.Column(db.String(20))  # 'positive', 'neutral', 'negative'
    generated_beat_url = db.Column(db.String(500))  # URL to generated beat audio
    
    # JSON field to store session metrics
    metrics_data = db.Column(db.Text)  # JSON string
    
    def set_metrics(self, metrics_dict):
        self.metrics_data = json.dumps(metrics_dict)
    
    def get_metrics(self):
        if self.metrics_data:
            return json.loads(self.metrics_data)
        return {}

class SessionMetrics(db.Model):
    __tablename__ = 'session_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('therapy_sessions.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    current_bpm = db.Column(db.Float, nullable=False)
    sync_accuracy = db.Column(db.Float)  # 0-100 percentage
    adjustment_made = db.Column(db.Boolean, default=False)
    
    # Relationships
    session = db.relationship('TherapySession', backref='metrics')

class BaselineAssessment(db.Model):
    __tablename__ = 'baseline_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id'), nullable=False)
    assessment_type = db.Column(db.String(50), nullable=False)  # 'gait', 'tapping', 'speech'
    measured_value = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    assessed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref='assessments')
    assessor = db.relationship('User', foreign_keys=[assessed_by])

class ClinicalReport(db.Model):
    __tablename__ = 'clinical_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id'), nullable=False)
    clinician_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('therapy_sessions.id'), nullable=True)
    
    activity_type = db.Column(db.String(50))
    duration_seconds = db.Column(db.Integer)
    initial_bpm = db.Column(db.Float)
    avg_bpm = db.Column(db.Float)
    final_bpm = db.Column(db.Float)
    target_bpm = db.Column(db.Float)
    accuracy_score = db.Column(db.Float)
    movement_count = db.Column(db.Integer, default=0)
    
    # Structured AI interpretation fields
    summary = db.Column(db.Text)
    what_you_did = db.Column(db.Text)               # JSON encoded list of strings
    performance_observations = db.Column(db.Text)  # JSON encoded list of strings
    what_to_improve = db.Column(db.Text)           # JSON encoded list of strings
    recommendations = db.Column(db.Text)           # JSON encoded list of strings
    
    # Structured SOAP notes
    soap_subjective = db.Column(db.Text)
    soap_objective = db.Column(db.Text)
    soap_assessment = db.Column(db.Text)
    soap_plan = db.Column(db.Text)
    
    # Audit & model tracking
    ai_model = db.Column(db.String(50), default='gemini-3.5-flash-lite')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('clinical_reports', lazy=True, order_by='ClinicalReport.created_at.desc()'))
    clinician = db.relationship('User', foreign_keys=[clinician_id])
    therapy_session = db.relationship('TherapySession', backref=db.backref('clinical_report', uselist=False))

    def to_dict(self):
        def parse_json_list(val):
            if not val:
                return []
            try:
                data = json.loads(val)
                return data if isinstance(data, list) else [str(data)]
            except Exception:
                return [str(val)]

        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'clinician_id': self.clinician_id,
            'session_id': self.session_id,
            'activity_type': self.activity_type or 'General Therapy',
            'duration_seconds': self.duration_seconds or 0,
            'initial_bpm': round(self.initial_bpm, 1) if self.initial_bpm is not None else None,
            'avg_bpm': round(self.avg_bpm, 1) if self.avg_bpm is not None else None,
            'final_bpm': round(self.final_bpm, 1) if self.final_bpm is not None else None,
            'target_bpm': round(self.target_bpm, 1) if self.target_bpm is not None else None,
            'accuracy_score': round(self.accuracy_score, 1) if self.accuracy_score is not None else None,
            'movement_count': self.movement_count or 0,
            'summary': self.summary or '',
            'what_you_did': parse_json_list(self.what_you_did),
            'performance_observations': parse_json_list(self.performance_observations),
            'what_to_improve': parse_json_list(self.what_to_improve),
            'recommendations': parse_json_list(self.recommendations),
            'soap': {
                'subjective': self.soap_subjective or 'Patient completed therapy protocol without adverse events.',
                'objective': self.soap_objective or 'Objective data recorded.',
                'assessment': self.soap_assessment or 'Patient demonstrates stable motor response.',
                'plan': self.soap_plan or 'Continue prescribed rehabilitation protocol.'
            },
            'ai_model': self.ai_model,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else ''
        }
