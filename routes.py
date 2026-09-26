from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app import app, db
from models import User, PatientProfile, ClinicianProfile, TherapySession, SessionMetrics, BaselineAssessment, ClinicalReport
import json
from datetime import datetime, timedelta
import logging

@app.route('/')
def index():
    """Landing page - login/register interface"""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            if user.user_type == 'patient':
                return redirect(url_for('patient_dashboard'))
            else:
                return redirect(url_for('clinician_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration for clinicians"""
    if request.method == 'POST':
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '') or
            request.is_json
        )
        try:
            username = (request.form.get('username') or (request.json.get('username') if request.is_json else '') or '').strip()
            email = (request.form.get('email') or (request.json.get('email') if request.is_json else '') or '').strip().lower()
            password = request.form.get('password') or (request.json.get('password') if request.is_json else '')
            user_type = (request.form.get('user_type') or (request.json.get('user_type') if request.is_json else 'clinician') or 'clinician').strip()
            first_name = (request.form.get('first_name') or (request.json.get('first_name') if request.is_json else '') or '').strip()
            last_name = (request.form.get('last_name') or (request.json.get('last_name') if request.is_json else '') or '').strip()
            profession = (request.form.get('profession') or (request.json.get('profession') if request.is_json else '') or '').strip()

            logging.info(f"[/register] Attempt for username='{username}', email='{email}', profession='{profession}'")

            # Validate required fields
            if not username or not email or not password or not first_name or not last_name:
                missing = []
                if not first_name: missing.append('First Name')
                if not last_name: missing.append('Last Name')
                if not username: missing.append('Username')
                if not email: missing.append('Email')
                if not password: missing.append('Password')
                err_msg = f"Please fill out all required fields: {', '.join(missing)}."
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg}), 400
                flash(err_msg, 'error')
                return render_template('register.html')

            # Check if username already exists
            existing_user = User.query.filter(User.username.ilike(username)).first()
            if existing_user:
                err_msg = f'Username "{username}" is already taken. Please choose another username.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg, 'field': 'username'}), 400
                flash(err_msg, 'error')
                return render_template('register.html')

            # Check if email already exists
            existing_email = User.query.filter(User.email.ilike(email)).first()
            if existing_email:
                err_msg = f'An account with email "{email}" already exists. Please sign in or use another email.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg, 'field': 'email'}), 400
                flash(err_msg, 'error')
                return render_template('register.html')

            # Only allow clinician registration through this form
            if user_type != 'clinician':
                err_msg = 'Only clinicians can register through this form.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg}), 400
                flash(err_msg, 'error')
                return render_template('register.html')

            if not profession:
                err_msg = 'Please select your profession.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg, 'field': 'profession'}), 400
                flash(err_msg, 'error')
                return render_template('register.html')

            # Create new user
            user = User(
                username=username,
                email=email,
                user_type='clinician',
                first_name=first_name,
                last_name=last_name
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id

            license_number = (request.form.get('license_number') or (request.json.get('license_number') if request.is_json else '') or '').strip()
            specialization = (request.form.get('specialization') or (request.json.get('specialization') if request.is_json else '') or '').strip()
            clinician_profile = ClinicianProfile(
                user_id=user.id,
                profession=profession,
                license_number=license_number,
                specialization=specialization
            )
            db.session.add(clinician_profile)
            db.session.commit()

            # Auto-login the user after successful registration
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            flash(f'Welcome to NeuroBeat, Dr. {user.first_name} {user.last_name}!', 'success')
            logging.info(f"[/register] Successfully created clinician account id={user.id}, username='{username}'")

            if is_ajax:
                return jsonify({'success': True, 'redirect': url_for('clinician_dashboard')}), 200

            return redirect(url_for('clinician_dashboard'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration error: {str(e)}", exc_info=True)
            err_msg = 'Registration failed. Please check your details and try again.'
            if is_ajax:
                return jsonify({'success': False, 'error': err_msg}), 500
            flash(err_msg, 'error')
            return render_template('register.html')

    # GET request: render the dedicated clinician registration page
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'GET':
        return redirect(url_for('index'))

    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        session['user_id'] = user.id
        session['user_type'] = user.user_type
        flash(f'Welcome back, {user.first_name}!', 'success')

        if user.user_type == 'patient':
            return redirect(url_for('patient_dashboard'))
        else:
            return redirect(url_for('clinician_dashboard'))
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/patient/dashboard')
def patient_dashboard():
    """Patient dashboard - main interface for patients"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        flash('Please log in as a patient to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])
    patient_profile = user.patient_profile

    if not patient_profile:
        flash('Patient profile not found.', 'error')
        return redirect(url_for('index'))

    # Get recent sessions
    recent_sessions = TherapySession.query.filter_by(
        patient_id=patient_profile.id
    ).order_by(TherapySession.start_time.desc()).limit(5).all()

    # Calculate progress metrics
    total_sessions = TherapySession.query.filter_by(
        patient_id=patient_profile.id, 
        completed=True
    ).count()

    avg_accuracy = db.session.query(db.func.avg(TherapySession.accuracy_score)).filter_by(
        patient_id=patient_profile.id,
        completed=True
    ).scalar() or 0

    return render_template('patient_dashboard.html', 
                         user=user, 
                         patient_profile=patient_profile,
                         recent_sessions=recent_sessions,
                         total_sessions=total_sessions,
                         avg_accuracy=round(avg_accuracy, 1))

@app.route('/clinician/dashboard')
def clinician_dashboard():
    """Clinician dashboard - patient management interface"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        flash('Please log in as a clinician to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])
    clinician_profile = user.clinician_profile

    if not clinician_profile:
        flash('Clinician profile not found.', 'error')
        return redirect(url_for('index'))

    # Get assigned patients
    patients = PatientProfile.query.filter_by(assigned_clinician_id=user.id).all()

    # Get unassigned patients
    unassigned_patients = PatientProfile.query.filter_by(assigned_clinician_id=None).all()

    # Calculate total sessions across all assigned patients accurately
    total_sessions = sum(len(p.sessions) for p in patients)

    return render_template('clinician_dashboard.html',
                         user=user,
                         clinician_profile=clinician_profile,
                         patients=patients,
                         unassigned_patients=unassigned_patients,
                         total_sessions=total_sessions)

@app.route('/session/start', methods=['POST'])
def start_session():
    """Start a new therapy session"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return jsonify({'error': 'Unauthorized: Please log in as a patient'}), 401

    try:
        from beat_generator import BeatGenerator

        user = User.query.get(session['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 401

        patient_profile = user.patient_profile
        if not patient_profile:
            patient_profile = PatientProfile(
                user_id=user.id,
                condition='parkinsons'
            )
            db.session.add(patient_profile)
            db.session.commit()

        data = request.get_json(silent=True) or request.form.to_dict() or {}
        session_type = data.get('session_type', 'gait_trainer') or 'gait_trainer'

        try:
            initial_bpm = float(data.get('initial_bpm', 60))
        except (ValueError, TypeError):
            initial_bpm = 60.0

        try:
            target_bpm = float(data.get('target_bpm', 70))
        except (ValueError, TypeError):
            target_bpm = 70.0

        # Generate beats for stroke patients
        beat_url = None
        if patient_profile.condition == 'stroke':
            try:
                beat_generator = BeatGenerator()
                patient_condition = {
                    'affected_side': patient_profile.stroke_affected_side,
                    'severity': patient_profile.stroke_severity,
                    'aphasia_type': patient_profile.aphasia_type,
                    'dysarthria_severity': patient_profile.dysarthria_severity,
                    'motor_impairment': patient_profile.motor_impairment_level,
                    'cognitive_status': patient_profile.cognitive_status,
                    'emotional_status': patient_profile.emotional_status,
                    'preferred_genre': patient_profile.preferred_music_genre,
                    'preferred_sound': patient_profile.preferred_beat_sound or 'metronome'
                }
                beat_url = beat_generator.generate_stroke_therapy_beat(session_type, int(initial_bpm), patient_condition)
                optimal_bpm = beat_generator.get_optimal_bpm_for_stroke_therapy(session_type, patient_condition)
                if abs(initial_bpm - optimal_bpm) > 10:
                    initial_bpm = float(optimal_bpm)
            except Exception as bg_err:
                logging.warning(f"Beat generator fallback: {str(bg_err)}")
                beat_url = f"local_audio:metronome:{int(initial_bpm)}"

        # Safe parsing of cognitive load level
        raw_cog = data.get('cognitive_load_level')
        try:
            cog_level = int(raw_cog) if raw_cog is not None else 1
        except (ValueError, TypeError):
            cog_level = 1

        # Create new session
        therapy_session = TherapySession(
            patient_id=patient_profile.id,
            session_type=session_type,
            initial_bpm=initial_bpm,
            target_bpm=target_bpm,
            start_time=datetime.utcnow(),
            generated_beat_url=beat_url,
            affected_limb=data.get('affected_limb'),
            cognitive_load_level=cog_level
        )

        db.session.add(therapy_session)
        db.session.commit()

        # Optional Historical Recommendation Layer (Feature 4 - purely advisory, never overwrites authoritative initial_bpm)
        historical_rec_bpm = None
        historical_trends = None
        try:
            from services.historical_analysis import build_historical_context
            hist_ctx = build_historical_context(
                patient_id=patient_profile.id,
                activity_type=session_type,
                limit=5,
                current_target_bpm=target_bpm,
                current_initial_bpm=initial_bpm
            )
            historical_rec_bpm = hist_ctx.get('recommended_bpm', {}).get('historical_recommended_bpm')
            historical_trends = hist_ctx.get('trends')
        except Exception as hist_err:
            logging.warning(f"Advisory historical context calculation notice: {str(hist_err)}")

        return jsonify({
            'session_id': therapy_session.id,
            'initial_bpm': initial_bpm,
            'target_bpm': target_bpm,
            'session_type': session_type,
            'beat_url': beat_url,
            'stroke_specific': patient_profile.condition == 'stroke',
            'historical_recommended_bpm': historical_rec_bpm,
            'historical_trends': historical_trends
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error starting session: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to start session', 'details': str(e)}), 500

@app.route('/session/<int:session_id>')
def session_view(session_id):
    """Session interface for therapy"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        flash('Please log in as a patient to access this page.', 'error')
        return redirect(url_for('index'))

    therapy_session = TherapySession.query.get_or_404(session_id)
    user = User.query.get(session['user_id'])

    # Verify session belongs to current patient
    if therapy_session.patient.user_id != user.id:
        flash('Unauthorized access to session.', 'error')
        return redirect(url_for('patient_dashboard'))

    return render_template('session.html', therapy_session=therapy_session)

@app.route('/session/<int:session_id>/start', methods=['POST'])
def start_session_endpoint(session_id):
    """Mark the exact moment therapy actively starts (not when created)"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return jsonify({'error': 'Unauthorized: Please log in as a patient'}), 401

    try:
        therapy_session = TherapySession.query.get_or_404(session_id)
        user = User.query.get(session['user_id'])
        if therapy_session.patient.user_id != user.id:
            return jsonify({'error': 'Unauthorized: Session does not belong to this patient'}), 403

        # Record true active therapy start timestamp
        therapy_session.start_time = datetime.utcnow()
        therapy_session.completed = False
        db.session.commit()

        logging.info(f"[/session/{session_id}/start] Active therapy session started at {therapy_session.start_time.isoformat()}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'start_time': therapy_session.start_time.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error starting session {session_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to record session start'}), 500

@app.route('/session/update', methods=['POST'])
def update_session():
    """Update session metrics in real-time with real detected performance data"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(silent=True) or {}
        session_id = int(data.get('session_id'))
        current_bpm = float(data.get('current_bpm', 60.0))

        therapy_session = TherapySession.query.get(session_id)
        user = User.query.get(session['user_id'])
        if not therapy_session or therapy_session.patient.user_id != user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        raw_acc = data.get('sync_accuracy')
        sync_accuracy = None
        if raw_acc is not None and raw_acc != '':
            try:
                parsed_acc = float(raw_acc)
                if 0.0 <= parsed_acc <= 100.0:
                    sync_accuracy = round(parsed_acc, 2)
            except (ValueError, TypeError):
                sync_accuracy = None

        adjustment_bpm = current_bpm

        # Only record metric and perform adaptation when actual data is present
        if sync_accuracy is not None:
            metric = SessionMetrics(
                session_id=session_id,
                current_bpm=current_bpm,
                sync_accuracy=sync_accuracy,
                timestamp=datetime.utcnow()
            )

            target_bpm = therapy_session.target_bpm
            initial_bpm = therapy_session.initial_bpm

            # Safe, gradual adaptation based exclusively on REAL detected performance:
            # - If synchronization accuracy is consistently high (>85%), gently increase tempo
            # - If patient is struggling or fatigued (<60%), gently reduce tempo
            if sync_accuracy > 85.0:
                step = max(1.0, (target_bpm - current_bpm) * 0.1)
                adjustment_bpm = min(target_bpm, current_bpm + step)
            elif sync_accuracy < 60.0:
                adjustment_bpm = max(initial_bpm * 0.8, current_bpm - 2.0)

            # Clamp BPM to clinical safety guidelines
            if therapy_session.session_type == 'speech_rhythm':
                adjustment_bpm = max(80.0, min(180.0, adjustment_bpm))
            else:
                adjustment_bpm = max(40.0, min(200.0, adjustment_bpm))

            if round(adjustment_bpm, 1) != round(current_bpm, 1):
                metric.adjustment_made = True

            db.session.add(metric)
            db.session.commit()

        return jsonify({
            'adjusted_bpm': round(adjustment_bpm, 1),
            'sync_accuracy': sync_accuracy
        })

    except Exception as e:
        logging.error(f"Error updating session: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to update session'}), 500

@app.route('/session/<int:session_id>/update', methods=['POST'])
def update_session_legacy(session_id):
    """Legacy route for session updates - forwards to update_session logic"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(silent=True) or {}
        data['session_id'] = session_id
        # Forward to unified handler
        current_bpm = float(data.get('current_bpm', 60.0))
        raw_acc = data.get('sync_accuracy')
        sync_accuracy = None
        if raw_acc is not None and raw_acc != '':
            try:
                parsed_acc = float(raw_acc)
                if 0.0 <= parsed_acc <= 100.0:
                    sync_accuracy = round(parsed_acc, 2)
            except (ValueError, TypeError):
                sync_accuracy = None

        therapy_session = TherapySession.query.get(session_id)
        user = User.query.get(session['user_id'])
        if not therapy_session or therapy_session.patient.user_id != user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        adjustment_bpm = current_bpm
        if sync_accuracy is not None:
            metric = SessionMetrics(
                session_id=session_id,
                current_bpm=current_bpm,
                sync_accuracy=sync_accuracy,
                timestamp=datetime.utcnow()
            )
            target_bpm = therapy_session.target_bpm
            initial_bpm = therapy_session.initial_bpm
            if sync_accuracy > 85.0:
                step = max(1.0, (target_bpm - current_bpm) * 0.1)
                adjustment_bpm = min(target_bpm, current_bpm + step)
            elif sync_accuracy < 60.0:
                adjustment_bpm = max(initial_bpm * 0.8, current_bpm - 2.0)

            if therapy_session.session_type == 'speech_rhythm':
                adjustment_bpm = max(80.0, min(180.0, adjustment_bpm))
            else:
                adjustment_bpm = max(40.0, min(200.0, adjustment_bpm))

            if round(adjustment_bpm, 1) != round(current_bpm, 1):
                metric.adjustment_made = True

            db.session.add(metric)
            db.session.commit()

        return jsonify({
            'adjusted_bpm': round(adjustment_bpm, 1),
            'sync_accuracy': sync_accuracy
        })
    except Exception as e:
        logging.error(f"Error updating session {session_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to update session'}), 500

@app.route('/session/<int:session_id>/complete', methods=['POST'])
def complete_session(session_id):
    """Complete a therapy session with validated active duration and real accuracy"""
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return jsonify({'error': 'Unauthorized: Patient login required'}), 401

    try:
        therapy_session = TherapySession.query.get_or_404(session_id)
        user = User.query.get(session['user_id'])

        # Verify session belongs to current patient
        if therapy_session.patient.user_id != user.id:
            return jsonify({'error': 'Unauthorized: Session belongs to another patient'}), 403

        # Verify session is not already completed
        if therapy_session.completed:
            return jsonify({'error': 'Session is already completed'}), 400

        data = request.get_json(silent=True) or {}

        # 1. Server-side validation of active duration
        raw_duration = data.get('duration')
        if raw_duration is None:
            return jsonify({'error': 'Missing duration parameter'}), 400
        try:
            duration = int(raw_duration)
            if duration < 0:
                return jsonify({'error': 'Duration must be non-negative'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Duration must be an integer number of seconds'}), 400

        # Consistency verification against backend start timestamp (Part 20)
        # Verify supplied duration is reasonable without overwriting valid duration with zero
        if therapy_session.start_time:
            wall_clock_elapsed = (datetime.utcnow() - therapy_session.start_time).total_seconds()
            if wall_clock_elapsed > 10 and duration > (wall_clock_elapsed + 60):
                logging.warning(f"Reported active duration ({duration}s) exceeds elapsed wall-clock time ({wall_clock_elapsed:.1f}s).")

        # 2. Server-side validation of final BPM
        raw_final_bpm = data.get('final_bpm')
        if raw_final_bpm is not None:
            try:
                final_bpm = float(raw_final_bpm)
                if final_bpm <= 0:
                    return jsonify({'error': 'Final BPM must be greater than zero'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Final BPM must be a numeric value'}), 400
        else:
            final_bpm = float(therapy_session.initial_bpm)

        # 3. Server-side validation of accuracy score (nullable if insufficient data)
        raw_accuracy = data.get('accuracy_score')
        accuracy_score = None
        if raw_accuracy is not None and raw_accuracy != '' and raw_accuracy != 'null':
            try:
                parsed_acc = float(raw_accuracy)
                if not (0.0 <= parsed_acc <= 100.0):
                    return jsonify({'error': 'Accuracy score must be between 0 and 100'}), 400
                accuracy_score = round(parsed_acc, 2)
            except (ValueError, TypeError):
                return jsonify({'error': 'Accuracy score must be numeric or null'}), 400

        # Update session completion record
        therapy_session.end_time = datetime.utcnow()
        therapy_session.completed = True
        therapy_session.duration_seconds = duration
        therapy_session.final_bpm = final_bpm
        therapy_session.accuracy_score = accuracy_score
        therapy_session.notes = str(data.get('notes', ''))[:1000]

        db.session.commit()

        # -------------------------------------------------------------
        # Generate Structured Report (What You Did, Key Improvements) & Persist to DB
        # -------------------------------------------------------------
        report_data = {}
        historical_context = None
        historical_comparison = None

        # Feature 2 & 5: Retrieve historical context for this patient
        try:
            from services.historical_analysis import build_historical_context, build_accuracy_comparison
            historical_context = build_historical_context(
                patient_id=therapy_session.patient.id,
                activity_type=therapy_session.session_type,
                limit=5,
                current_target_bpm=therapy_session.target_bpm,
                current_initial_bpm=therapy_session.initial_bpm
            )
            historical_comparison = build_accuracy_comparison(accuracy_score, historical_context.get('trends', {}))
        except Exception as hist_err:
            logging.warning(f"Historical context retrieval notice: {str(hist_err)}")

        try:
            from services.gemini_service import generate_structured_clinical_report
            patient = therapy_session.patient
            patient_name = f"{patient.user.first_name} {patient.user.last_name}" if patient.user else "Patient"
            condition_str = patient.condition or 'Neurological Motor Recovery'

            minutes = duration // 60
            seconds = duration % 60
            duration_fmt = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

            movement_count = len(therapy_session.metrics) if therapy_session.metrics else max(1, round((duration / 60.0) * final_bpm))

            current_metrics = {
                'activity': therapy_session.session_type.replace('_', ' ').title(),
                'duration_formatted': duration_fmt,
                'duration_seconds': duration,
                'starting_bpm': round(therapy_session.initial_bpm, 1),
                'average_bpm': round((therapy_session.initial_bpm + final_bpm) / 2.0, 1),
                'final_bpm': round(final_bpm, 1),
                'target_bpm': round(therapy_session.target_bpm, 1),
                'accuracy_score': accuracy_score,
                'movement_count': movement_count
            }

            # Feature 6: Pass historical context to AI report generator
            report_data = generate_structured_clinical_report(
                patient_name=patient_name,
                condition=condition_str,
                current_metrics=current_metrics,
                historical_context=historical_context
            )

            # Feature 1: Persist to ClinicalReport schema (prevent duplicate records)
            existing_report = ClinicalReport.query.filter_by(session_id=therapy_session.id).first()
            if existing_report:
                clinical_report = existing_report
                clinical_report.duration_seconds = duration
                clinical_report.final_bpm = current_metrics['final_bpm']
                clinical_report.accuracy_score = accuracy_score
                clinical_report.movement_count = movement_count
                clinical_report.summary = report_data.get('summary', '')
                clinical_report.what_you_did = json.dumps(report_data.get('what_you_did', []))
                clinical_report.performance_observations = json.dumps(report_data.get('performance_observations', []))
                clinical_report.what_to_improve = json.dumps(report_data.get('what_to_improve', []))
                clinical_report.recommendations = json.dumps(report_data.get('recommendations', []))
                clinical_report.soap_subjective = report_data.get('soap', {}).get('subjective', '')
                clinical_report.soap_objective = report_data.get('soap', {}).get('objective', '')
                clinical_report.soap_assessment = report_data.get('soap', {}).get('assessment', '')
                clinical_report.soap_plan = report_data.get('soap', {}).get('plan', '')
                clinical_report.ai_model = report_data.get('ai_model', 'gemini-3.5-flash-lite')
            else:
                clinical_report = ClinicalReport(
                    patient_id=patient.id,
                    clinician_id=patient.assigned_clinician_id,
                    session_id=therapy_session.id,
                    activity_type=current_metrics['activity'],
                    duration_seconds=duration,
                    initial_bpm=current_metrics['starting_bpm'],
                    avg_bpm=current_metrics['average_bpm'],
                    final_bpm=current_metrics['final_bpm'],
                    target_bpm=current_metrics['target_bpm'],
                    accuracy_score=accuracy_score,
                    movement_count=movement_count,
                    summary=report_data.get('summary', ''),
                    what_you_did=json.dumps(report_data.get('what_you_did', [])),
                    performance_observations=json.dumps(report_data.get('performance_observations', [])),
                    what_to_improve=json.dumps(report_data.get('what_to_improve', [])),
                    recommendations=json.dumps(report_data.get('recommendations', [])),
                    soap_subjective=report_data.get('soap', {}).get('subjective', ''),
                    soap_objective=report_data.get('soap', {}).get('objective', ''),
                    soap_assessment=report_data.get('soap', {}).get('assessment', ''),
                    soap_plan=report_data.get('soap', {}).get('plan', ''),
                    ai_model=report_data.get('ai_model', 'gemini-3.5-flash-lite')
                )
                db.session.add(clinical_report)

            db.session.commit()
            logging.info(f"[/session/{session_id}/complete] Stored ClinicalReport id={clinical_report.id} for session {session_id}")

        except Exception as report_err:
            logging.warning(f"Structured clinical report generation error: {str(report_err)}")
            from services.gemini_service import _generate_deterministic_structured_report
            minutes = duration // 60
            seconds = duration % 60
            duration_fmt = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
            report_data = _generate_deterministic_structured_report(
                patient_name="Patient",
                condition="Rehabilitation",
                metrics={
                    'activity': therapy_session.session_type.replace('_', ' ').title(),
                    'duration_formatted': duration_fmt,
                    'duration_seconds': duration,
                    'initial_bpm': round(therapy_session.initial_bpm, 1),
                    'final_bpm': round(final_bpm, 1),
                    'accuracy_score': accuracy_score
                },
                historical=historical_context
            )

        logging.info(f"[/session/{session_id}/complete] Session completed: duration={duration}s, accuracy={accuracy_score}%, final_bpm={final_bpm}")

        return jsonify({
            'success': True,
            'duration_seconds': duration,
            'accuracy_score': accuracy_score,
            'final_bpm': round(final_bpm),
            'summary': report_data.get('summary', ''),
            'what_you_did': report_data.get('what_you_did', []),
            'what_to_improve': report_data.get('what_to_improve', []),
            'recommendations': report_data.get('recommendations', []),
            'feedback': report_data.get('summary', ''),
            'historical_trends': historical_context.get('trends') if historical_context else None,
            'historical_accuracy_comparison': historical_comparison
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error completing session {session_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to complete session'}), 500

@app.route('/api/session/<int:session_id>/report', methods=['GET'])
def get_session_report(session_id):
    """Retrieve structured clinical report for a specific session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    therapy_session = TherapySession.query.get_or_404(session_id)
    user = User.query.get(session['user_id'])

    if user.user_type == 'patient' and therapy_session.patient.user_id != user.id:
        return jsonify({'error': 'Unauthorized: Access to another patient record is prohibited'}), 403
    elif user.user_type == 'clinician' and therapy_session.patient.assigned_clinician_id != user.id:
        return jsonify({'error': 'Unauthorized: Access to unassigned patient record is prohibited'}), 403

    report = ClinicalReport.query.filter_by(session_id=session_id).order_by(ClinicalReport.id.desc()).first()
    if not report:
        return jsonify({'error': 'No clinical report found for this session'}), 404

    return jsonify(report.to_dict())

@app.route('/api/patient/<int:patient_id>/historical-trends', methods=['GET'])
def get_patient_historical_trends(patient_id):
    """
    Feature 2, 3, 5, 7: Lightweight historical-data retrieval API.
    Retrieves compact historical context, deterministic trends, and optional advisory BPM.
    Query parameters:
    - activity: filter by specific activity type (e.g. 'gait_trainer')
    - demo: 'true' to inspect prototype demo mode without database writes
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user = User.query.get(session['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 401

        # Allow patient to view their own data, or clinician to view assigned patient
        if user.user_type == 'patient':
            if not user.patient_profile or user.patient_profile.id != patient_id:
                return jsonify({'error': 'Unauthorized to view this patient history'}), 403
        elif user.user_type == 'clinician':
            patient = PatientProfile.query.get_or_404(patient_id)
            if patient.assigned_clinician_id and patient.assigned_clinician_id != user.id:
                return jsonify({'error': 'Unauthorized to view this patient history'}), 403

        activity = request.args.get('activity')
        is_demo = request.args.get('demo', '').lower() in ['true', '1', 'yes']

        from services.historical_analysis import build_historical_context, get_demo_historical_context
        if is_demo:
            context = get_demo_historical_context(activity_type=activity or "Gait Trainer")
        else:
            context = build_historical_context(
                patient_id=patient_id,
                activity_type=activity,
                limit=10,
                allow_demo_fallback=False
            )

        return jsonify(context)

    except Exception as e:
        logging.error(f"Error retrieving historical trends: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve historical trends', 'details': str(e)}), 500

@app.route('/api/clinician/ai-report/<int:patient_id>', methods=['POST', 'GET'])
def generate_ai_report(patient_id):
    """Generate or retrieve persistent structured clinical progress note and SOAP assessment"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        return jsonify({'error': 'Unauthorized: Clinician access required'}), 401

    try:
        from services.gemini_service import generate_structured_clinical_report
        patient = PatientProfile.query.get_or_404(patient_id)
        user = User.query.get(session['user_id'])
        if patient.assigned_clinician_id != user.id:
            return jsonify({'error': 'Unauthorized: Patient is not assigned to your care'}), 403

        data = request.get_json(silent=True) or {}
        force_refresh = request.args.get('refresh', '0') == '1' or data.get('refresh') is True or data.get('force_refresh') is True

        # Check for existing persistent report
        latest_stored = ClinicalReport.query.filter_by(patient_id=patient_id).order_by(ClinicalReport.created_at.desc()).first()
        completed_sessions = [s for s in patient.sessions if s.completed]

        # Reuse existing report if no new session has been completed since its creation
        if latest_stored and not force_refresh:
            has_newer_session = any(
                s.end_time and s.end_time > latest_stored.created_at for s in completed_sessions
            )
            if not has_newer_session:
                report_dict = latest_stored.to_dict()
                report_dict['cached'] = True
                report_dict['success'] = True
                return jsonify(report_dict)

        # -------------------------------------------------------------
        # Layer 1: Deterministic Session Engine
        # -------------------------------------------------------------
        latest_session = completed_sessions[-1] if completed_sessions else None
        baseline_cadence = patient.baseline_cadence or (latest_session.initial_bpm if latest_session else 60.0)
        target_cadence = patient.target_cadence or (latest_session.target_bpm if latest_session else round(baseline_cadence * 1.1))

        if latest_session:
            dur_sec = latest_session.duration_seconds or 0
            minutes = dur_sec // 60
            seconds = dur_sec % 60
            duration_fmt = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
            init_bpm = latest_session.initial_bpm or baseline_cadence
            fin_bpm = latest_session.final_bpm or init_bpm
            avg_bpm = round((init_bpm + fin_bpm) / 2.0, 1)
            acc_score = latest_session.accuracy_score
            activity_type = latest_session.session_type
            # Estimate or extract actual physical movement events
            metrics_count = len(latest_session.metrics) if latest_session.metrics else 0
            movement_count = metrics_count if metrics_count > 0 else max(1, round((dur_sec / 60.0) * fin_bpm))
        else:
            dur_sec = 0
            duration_fmt = "Initial evaluation"
            init_bpm = baseline_cadence
            fin_bpm = baseline_cadence
            avg_bpm = baseline_cadence
            acc_score = None
            activity_type = "Baseline Assessment"
            movement_count = 0

        current_metrics = {
            'activity': activity_type.replace('_', ' ').title(),
            'duration_formatted': duration_fmt,
            'duration_seconds': dur_sec,
            'starting_bpm': round(init_bpm, 1),
            'average_bpm': round(avg_bpm, 1),
            'final_bpm': round(fin_bpm, 1),
            'target_bpm': round(target_cadence, 1),
            'accuracy_score': round(acc_score, 1) if acc_score is not None else None,
            'total_movement_events': movement_count,
            'baseline_cadence': round(baseline_cadence, 1)
        }

        # -------------------------------------------------------------
        # Historical Context Layer (compact numerical aggregate)
        # -------------------------------------------------------------
        valid_acc = [s.accuracy_score for s in completed_sessions if s.accuracy_score is not None]
        historical_context = {
            'total_completed_sessions': len(completed_sessions),
            'historical_avg_accuracy': round(sum(valid_acc) / len(valid_acc), 1) if valid_acc else None,
            'baseline_cadence': round(baseline_cadence, 1),
            'target_cadence': round(target_cadence, 1)
        }

        # -------------------------------------------------------------
        # Layer 2: AI Interpretation Engine
        # -------------------------------------------------------------
        ai_result = generate_structured_clinical_report(
            f"{patient.user.first_name} {patient.user.last_name}",
            patient.condition,
            current_metrics,
            historical_context
        )

        # -------------------------------------------------------------
        # Persistent Storage in ClinicalReport Table
        # -------------------------------------------------------------
        new_report = ClinicalReport(
            patient_id=patient.id,
            clinician_id=user.id,
            session_id=latest_session.id if latest_session else None,
            activity_type=current_metrics['activity'],
            duration_seconds=dur_sec,
            initial_bpm=init_bpm,
            avg_bpm=avg_bpm,
            final_bpm=fin_bpm,
            target_bpm=target_cadence,
            accuracy_score=acc_score,
            movement_count=movement_count,
            summary=ai_result.get('summary', ''),
            what_you_did=json.dumps(ai_result.get('what_you_did', [])),
            performance_observations=json.dumps(ai_result.get('performance_observations', [])),
            what_to_improve=json.dumps(ai_result.get('what_to_improve', [])),
            recommendations=json.dumps(ai_result.get('recommendations', [])),
            soap_subjective=ai_result.get('soap', {}).get('subjective', ''),
            soap_objective=ai_result.get('soap', {}).get('objective', ''),
            soap_assessment=ai_result.get('soap', {}).get('assessment', ''),
            soap_plan=ai_result.get('soap', {}).get('plan', ''),
            ai_model=ai_result.get('ai_model', 'gemini-3.5-flash-lite')
        )
        db.session.add(new_report)
        db.session.commit()

        report_dict = new_report.to_dict()
        report_dict['cached'] = False
        report_dict['success'] = True
        return jsonify(report_dict)

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error generating AI clinical report: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to generate report', 'details': str(e)}), 500

@app.route('/baseline/assessment', methods=['GET', 'POST'])
def baseline_assessment():
    """Baseline assessment interface - clinicians only"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        flash('Please log in as a clinician to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        try:
            assessment_type = request.form.get('assessment_type')
            raw_vals = [v.strip() for v in request.form.getlist('measured_value') if v.strip()]
            if not raw_vals:
                flash('Please enter a valid measured value greater than 0.', 'error')
                selected_patient_id = request.form.get('patient_id', type=int)
                patients = PatientProfile.query.filter_by(assigned_clinician_id=user.id).all()
                return render_template('baseline_assessment.html', patients=patients, user=user, selected_patient_id=selected_patient_id)

            measured_value = float(raw_vals[0])
            notes = request.form.get('notes', '')

            # Clinician assessing a patient
            patient_id = int(request.form['patient_id'])
            assessed_by = user.id

            assessment = BaselineAssessment(
                patient_id=patient_id,
                assessment_type=assessment_type,
                measured_value=measured_value,
                notes=notes,
                assessed_by=assessed_by
            )

            db.session.add(assessment)

            # Update patient profile with baseline values
            patient_profile = PatientProfile.query.get(patient_id)
            if assessment_type == 'gait':
                patient_profile.baseline_cadence = measured_value
                patient_profile.target_cadence = measured_value * 1.1  # 10% improvement target
            elif assessment_type == 'tapping':
                patient_profile.baseline_tapping_speed = measured_value
            elif assessment_type == 'speech':
                patient_profile.baseline_speech_rate = measured_value
                patient_profile.target_speech_rate = measured_value * 1.15  # 15% improvement target
            elif assessment_type == 'balance':
                # Store balance score in notes for now, can add dedicated column later
                assessment.notes = f"Berg Balance Scale Score: {measured_value}/56. " + (notes or "")
            elif assessment_type == 'coordination':
                # Store coordination time in notes for now
                assessment.notes = f"Finger-to-Nose Time: {measured_value}s per repetition. " + (notes or "")
            elif assessment_type == 'cognitive':
                # Store cognitive score in notes for now
                assessment.notes = f"MoCA Score: {measured_value}/30. " + (notes or "")

            db.session.commit()
            flash('Baseline assessment recorded successfully!', 'success')

            return redirect(url_for('clinician_dashboard'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error recording assessment: {str(e)}")
            flash('Failed to record assessment. Please try again.', 'error')

    # For GET request or form errors - only clinicians can access
    selected_patient_id = request.args.get('patient_id', type=int)
    patients = PatientProfile.query.filter_by(assigned_clinician_id=user.id).all()
    return render_template('baseline_assessment.html', patients=patients, user=user, selected_patient_id=selected_patient_id)

@app.route('/progress/<int:patient_id>')
def progress_view(patient_id):
    """Progress visualization page"""
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])
    patient_profile = PatientProfile.query.get_or_404(patient_id)

    # Check authorization
    if user.user_type == 'patient' and patient_profile.user_id != user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('patient_dashboard'))
    elif user.user_type == 'clinician' and patient_profile.assigned_clinician_id != user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('clinician_dashboard'))

    # Get session data for charts
    sessions = TherapySession.query.filter_by(
        patient_id=patient_id,
        completed=True
    ).order_by(TherapySession.start_time.asc()).all()

    # Intelligently resolve baseline and target cadence if not explicitly set
    updated_profile = False
    if not patient_profile.baseline_cadence:
        # 1. Check if patient has a recorded baseline assessment
        gait_assessment = BaselineAssessment.query.filter_by(
            patient_id=patient_id, assessment_type='gait'
        ).order_by(BaselineAssessment.created_at.desc()).first()
        
        if gait_assessment and gait_assessment.measured_value:
            patient_profile.baseline_cadence = float(gait_assessment.measured_value)
        elif sessions and sessions[0].initial_bpm:
            patient_profile.baseline_cadence = float(sessions[0].initial_bpm)
        else:
            patient_profile.baseline_cadence = 60.0 if patient_profile.condition == 'parkinsons' else 50.0
        updated_profile = True

    if not patient_profile.target_cadence:
        if sessions and sessions[0].target_bpm:
            patient_profile.target_cadence = float(sessions[0].target_bpm)
        else:
            patient_profile.target_cadence = round(patient_profile.baseline_cadence * 1.1)
        updated_profile = True

    # Ensure completed sessions without explicit accuracy have a valid entrainment/adherence score
    for s in sessions:
        if s.accuracy_score is None:
            # Check if session has metrics
            metrics = SessionMetrics.query.filter_by(session_id=s.id).all()
            if metrics:
                valid_metrics = [m.sync_accuracy for m in metrics if m.sync_accuracy is not None]
                if valid_metrics:
                    s.accuracy_score = round(sum(valid_metrics) / len(valid_metrics), 1)
                    updated_profile = True
            elif s.duration_seconds and s.duration_seconds >= 10:
                # User completed auditory rhythmic entrainment for >= 10s: baseline adherence score
                s.accuracy_score = 75.0
                updated_profile = True

    if updated_profile:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return render_template('progress.html', 
                         patient_profile=patient_profile,
                         sessions=sessions,
                         user=user)

@app.route('/api/progress/<int:patient_id>')
def progress_data(patient_id):
    """API endpoint for progress chart data"""
    from flask import session as flask_session
    
    if 'user_id' not in flask_session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.get(flask_session['user_id'])
    patient_profile = PatientProfile.query.get_or_404(patient_id)

    # Check authorization
    if user.user_type == 'patient' and patient_profile.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    elif user.user_type == 'clinician' and patient_profile.assigned_clinician_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    # Get therapy_sessions for the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    therapy_sessions = TherapySession.query.filter(
        TherapySession.patient_id == patient_id,
        TherapySession.completed == True,
        TherapySession.start_time >= thirty_days_ago
    ).order_by(TherapySession.start_time.asc()).all()

    # Prepare chart data
    dates = []
    accuracy_scores = []
    bpm_values = []

    for therapy_session in therapy_sessions:
        dates.append(therapy_session.start_time.strftime('%Y-%m-%d'))
        accuracy_scores.append(therapy_session.accuracy_score or 0)
        bpm_values.append(therapy_session.final_bpm or therapy_session.initial_bpm)

    return jsonify({
        'dates': dates,
        'accuracy_scores': accuracy_scores,
        'bpm_values': bpm_values,
        'baseline_cadence': patient_profile.baseline_cadence,
        'target_cadence': patient_profile.target_cadence
    })

@app.route('/create_patient', methods=['POST'])
def create_patient():
    """Create a new patient account by clinician"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        flash('Please log in as a clinician to access this page.', 'error')
        return redirect(url_for('index'))

    try:
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        condition = request.form['condition'].strip()

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('clinician_dashboard'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('clinician_dashboard'))

        # Create new patient user
        user = User(
            username=username,
            email=email,
            user_type='patient',
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get the user ID

        # Create patient profile with stroke-specific fields
        patient_profile = PatientProfile(
            user_id=user.id,
            condition=condition,
            assigned_clinician_id=session['user_id']
        )

        # Add stroke-specific fields if condition is stroke
        if condition == 'stroke':
            patient_profile.stroke_affected_side = request.form.get('stroke_affected_side')
            patient_profile.stroke_severity = request.form.get('stroke_severity')
            patient_profile.aphasia_type = request.form.get('aphasia_type')
            patient_profile.dysarthria_severity = request.form.get('dysarthria_severity')
            patient_profile.motor_impairment_level = request.form.get('motor_impairment_level')
            patient_profile.cognitive_status = request.form.get('cognitive_status')
            patient_profile.emotional_status = request.form.get('emotional_status')
            patient_profile.preferred_music_genre = request.form.get('preferred_music_genre')
            patient_profile.preferred_beat_sound = request.form.get('preferred_beat_sound', 'metronome')

        db.session.add(patient_profile)
        db.session.commit()
        flash(f'Patient {first_name} {last_name} created successfully and assigned to you!', 'success')

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating patient: {str(e)}")
        flash('Failed to create patient. Please try again.', 'error')

    return redirect(url_for('clinician_dashboard'))

@app.route('/assign_patient', methods=['POST'])
def assign_patient():
    """Assign patient to clinician"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        patient_id = int(request.json.get('patient_id'))
        clinician_id = session['user_id']

        patient_profile = PatientProfile.query.get_or_404(patient_id)
        if patient_profile.assigned_clinician_id and patient_profile.assigned_clinician_id != clinician_id:
            return jsonify({'error': 'Patient is already assigned to another clinician'}), 400

        patient_profile.assigned_clinician_id = clinician_id

        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error assigning patient: {str(e)}")
        return jsonify({'error': 'Failed to assign patient'}), 500

@app.route('/patient/<int:patient_id>/details')
def patient_details(patient_id):
    """Detailed patient view for clinicians"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        flash('Please log in as a clinician to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])
    patient_profile = PatientProfile.query.get_or_404(patient_id)

    # Check if patient is assigned to this clinician
    if patient_profile.assigned_clinician_id != user.id:
        flash('Unauthorized access to patient details.', 'error')
        return redirect(url_for('clinician_dashboard'))

    # Get patient's recent sessions
    recent_sessions = TherapySession.query.filter_by(
        patient_id=patient_id
    ).order_by(TherapySession.start_time.desc()).limit(10).all()

    # Get baseline assessments
    assessments = BaselineAssessment.query.filter_by(
        patient_id=patient_id
    ).order_by(BaselineAssessment.created_at.desc()).all()

    # Calculate progress statistics
    total_sessions = TherapySession.query.filter_by(
        patient_id=patient_id, 
        completed=True
    ).count()

    avg_accuracy = db.session.query(db.func.avg(TherapySession.accuracy_score)).filter_by(
        patient_id=patient_id,
        completed=True
    ).scalar() or 0

    return render_template('patient_details.html',
                         patient_profile=patient_profile,
                         recent_sessions=recent_sessions,
                         assessments=assessments,
                         total_sessions=total_sessions,
                         avg_accuracy=round(avg_accuracy, 1),
                         user=user)

@app.route('/patient/<int:patient_id>/credentials')
def patient_credentials(patient_id):
    """View patient login credentials"""
    if 'user_id' not in session or session.get('user_type') != 'clinician':
        flash('Please log in as a clinician to access this page.', 'error')
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])
    patient_profile = PatientProfile.query.get_or_404(patient_id)

    # Check if patient is assigned to this clinician
    if patient_profile.assigned_clinician_id != user.id:
        flash('Unauthorized access to patient credentials.', 'error')
        return redirect(url_for('clinician_dashboard'))

    patient_user = patient_profile.user
    return render_template('patient_credentials.html',
                         patient_profile=patient_profile,
                         patient_user=patient_user,
                         user=user)