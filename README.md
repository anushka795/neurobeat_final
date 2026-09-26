# 🎶 NeuroBeat – AI-Powered Adaptive Music Therapy Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![AI-Powered](https://img.shields.io/badge/AI-Google%20Gemini%202.5-orange.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**NeuroBeat** is an AI-powered neurorehabilitation platform leveraging **Rhythmic Auditory Stimulation (RAS)** and computer vision to assist patients recovering from stroke and managing Parkinson’s disease. By dynamically syncing acoustic tempo (BPM) with real-time patient kinematics and motor accuracy, NeuroBeat bridges clinical physical therapy and gamified home rehabilitation.

---

## 🌟 Key Upgrades & Recent Enhancements

### 1. 🤖 Gemini AI Integration & Structured Clinical Reporting
- **Model**: Powered by Google Gemini (`gemini-2.5-flash`) via the modern `google-genai` SDK.
- **Actionable Structured Reports**: Automatically analyzes session telemetry to generate:
  - **Clinical Summary**: High-level synopsis of patient cadence entrainment and fatigue indicators.
  - **What You Did**: Clear, bulleted action items summarizing motor performance.
  - **What to Improve**: Targeted physiological feedback and synchronization areas for improvement.
  - **Recommendations**: Clinically grounded next steps for future sessions.
  - **SOAP Notes**: Professional **S**ubjective, **O**bjective, **A**ssessment, and **P**lan documentation tailored for clinicians.
- **Resilient Fallback Engine**: If the Gemini API is offline, experiencing rate limits, or credentials are unavailable, an automated deterministic clinical engine seamlessly generates accurate reports without crashing or showing blank screens.

### 2. 📈 Elimination of "N/A" Values & Accurate Progress Tracking
- Resolved telemetry tracking bugs where session metrics, duration, step counts, and accuracy formerly defaulted to `N/A`.
- Implemented real-time mathematical calculation of cadence consistency, movement synchrony, and BPM transitions, displaying immediate, accurate progress in the session modal and clinician dashboard.

### 3. 🗄️ Structured Database Storage & Schema Configuration
- **`ClinicalReport` Table**: Dedicated relational model in SQLite storing structured clinical metrics, full SOAP notes, and JSON-encoded bullet point arrays (`what_you_did`, `what_to_improve`, `recommendations`).
- **Idempotent Session Handling**: Prevents redundant or duplicate report generation across repeated completion calls.

### 4. 🧠 Longitudinal Intelligence & Historical Analysis Layer
A lightweight, non-invasive analytical engine (`services/historical_analysis.py`) that tracks patient progression over time across 9 core features:
- **Session History Retrieval**: Fetches past completed sessions filtered by activity type.
- **Deterministic Trend Analysis**: Mathematically identifies whether motor accuracy is **`improving`**, **`declining`**, or **`stable`** without bloated external dependencies.
- **Advisory Recommended BPM**: Suggests safe, gradual pacing adjustments ($+2$ to $+3$ BPM when performance improves; consolidates pace when fatigue is detected).
- **Contextual Accuracy Comparison**: Quantifies performance relative to past baselines (e.g., *"+4.5% above historical average"*).
- **Prototype Demo Mode**: In-memory synthetic demonstration dataset (`?demo=true`) for showcasing patient trajectories with zero database writes.

### 5. 🎯 Therapy Routing & Activity Separation
- Fixed routing collisions so each activity runs in its own dedicated, isolated flow:
  - 🚶 **Gait Training**: Full-body pose kinematics, step cadences, and foot strike entrainment.
  - 🗣️ **Speech Therapy**: Auditory syllable timing, rhythm synchronization, and vocal exercise.
  - ⚖️ **Balance Training**: Postural sway tracking, center-of-gravity stabilization, and stance timers.
  - 👆 **Upper Limb / Finger Tapping**: Fine motor finger tapping frequency and dysdiadochokinesia assessment.

### 6. 🎨 Frontend & UI/UX Enhancements
- **Refined Color Palette**: Cohesive medical-grade dark theme (`#01aac5` primary cyan, `#042046` deep navy background, sleek glassmorphism cards).
- **Theme Icon Standardization**: Integrated dark-mode moon icon styling matching the application interface.
- **Interactive Post-Session Modal**: Replaced unstructured raw text with cleanly formatted bullet point cards.

---

## 🏗️ System Architecture

```
├── app.py                      # Flask application initialization & DB config
├── main.py                     # Server entrypoint
├── models.py                   # SQLAlchemy schema (User, PatientProfile, TherapySession, ClinicalReport)
├── routes.py                   # REST API & template routing
├── beat_generator.py           # Core adaptive metronome & tempo pacing algorithms
├── services/
│   ├── gemini_service.py       # Google Gemini AI clinical reporting & deterministic fallback
│   └── historical_analysis.py  # Trend analysis, advisory BPM, historical comparisons & demo mode
├── static/ / frontend/
│   ├── css/custom.css          # Styling tokens, responsive layout, glassmorphic UI
│   ├── js/session.js           # MediaPipe camera integration, kinematic tracking & session state
│   └── js/audio.js             # WebAudio API synthesizer, rhythmic beat generator
└── templates/
    ├── index.html              # Landing page / authentication
    ├── clinician_dashboard.html# Clinician patient overview & session histories
    ├── patient_dashboard.html  # Patient session hub & activity selection
    ├── session.html            # Live camera therapy session & real-time metronome
    └── progress.html           # Historical progress charts & analytics
```

---

## ⚙️ Tech Stack

- **Backend**: Python 3.11+, Flask 3.1, Flask-SQLAlchemy, SQLite
- **AI & Analytics**: Google GenAI SDK (`gemini-2.5-flash`), NumPy, SciPy
- **Computer Vision**: MediaPipe Pose / Hands via JavaScript
- **Audio Synthesis**: WebAudio API (low-latency procedural metronome synthesis)
- **Frontend**: Semantic HTML5, Vanilla JavaScript, Custom CSS Design System

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.11 or higher
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com/))

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/anushka795/neurobeat_final.git
cd neurobeat_final

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_secure_flask_secret_key_here
FLASK_ENV=development
```

### 4. Run the Application
```bash
python main.py
```
Open your browser and navigate to `http://localhost:5000`.

---

## 🧪 Testing the Historical Data Layer
An automated test suite is included to verify all 9 historical data features:
```bash
python scratch/test_historical_layer.py
```

---

## 📚 Research & Scientific Foundations
- **Rhythmic Auditory Stimulation (RAS)** in Neurological Rehabilitation:
  - [PLOS ONE: Music-assisted therapy for motor function in Parkinson's](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0264587)
  - [Frontiers in Neurology: Auditory-motor entrainment in stroke rehabilitation](https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2015.00185/full)
- WHO Guidelines for Neurorehabilitation and Motor Recovery.

---

## 👥 Original Team & Contributors
- **Anushka**
- **Aditya Jha**
- **Harsh Tiwari**
- **Pulkit Tiwari**
- **Yash Kumar**
