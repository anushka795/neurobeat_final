"""
Gemini AI Service for NeuroBeat Neurorehabilitation Platform
Implements Few-Shot Prompt Engineering for:
1. Clinician SOAP Progress Notes & Motor Assessment
2. Patient Post-Session Empathetic Recovery Coaching
"""

import os
import json
import logging
from typing import Dict, List, Optional

def get_gemini_client():
    """Initialize and return the Google GenAI client if API key is present."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(env_path, override=True)
    except Exception:
        pass

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logging.error(f"Failed to initialize GenAI client: {str(e)}")
        return None

def generate_clinical_soap_note_few_shot(
    patient_name: str,
    condition: str,
    baseline_data: Dict,
    recent_sessions: List[Dict]
) -> Dict:
    """
    Generate a clinical SOAP progress note using Few-Shot Prompting.
    Provides structured exemplar to ensure clinical terminology and exact formatting.
    """
    client = get_gemini_client()
    
    # Fallback if no API key configured yet
    if not client:
        return {
            "success": True,
            "status": "key_required",
            "message": "GEMINI_API_KEY is not configured in .env.",
            "report": _generate_deterministic_clinical_fallback(patient_name, condition, baseline_data, recent_sessions)
        }

    from google.genai import types

    few_shot_prompt = f"""You are an expert clinical neurorehabilitation documentation specialist.
Convert raw rehabilitation session metrics into concise, professional SOAP progress notes.
Match the exact style, headings, and clinical brevity shown in the example below.

--- CLINICAL EXEMPLAR ---
[INPUT]
Patient: John Doe (Condition: Stroke - Right Hemiparesis)
Baseline: {{"cadence": 48.0, "tapping_speed": 32.0}}
Sessions: [
  {{"date": "2026-09-10", "type": "gait_trainer", "duration_min": 6.0, "accuracy": 74, "bpm": 50}},
  {{"date": "2026-09-12", "type": "gait_trainer", "duration_min": 8.0, "accuracy": 78, "bpm": 52}},
  {{"date": "2026-09-15", "type": "gait_trainer", "duration_min": 10.0, "accuracy": 83, "bpm": 55}}
]

[OUTPUT]
### Clinical Progress Note (SOAP)
- **S (Subjective):** Patient completed auditory-motor entrainment sessions. Tolerated cadence progressions well without reported falls or severe dizziness.
- **O (Objective):** Gait cadence progressed from 48 BPM baseline to 55 BPM. Average synchronization accuracy improved from 74% to 83% over 3 sessions. Total active gait duration reached 10 minutes.
- **A (Assessment):** Positive motor response to Rhythmic Auditory Stimulation (RAS). Right lower limb stepping shows improved temporal regularity. Mild cadence instability observed after minute 8, indicating motor fatigue threshold.
- **P (Plan):** Maintain target cadence at 55 BPM for 2 more sessions to consolidate motor stability. If sync accuracy remains >80%, advance to 58 BPM. Introduce 60-second seated rest interval at minute 5.

==================================================
--- NOW GENERATE FOR THIS PATIENT ---
[INPUT]
Patient: {patient_name} (Condition: {condition})
Baseline: {json.dumps(baseline_data)}
Sessions: {json.dumps(recent_sessions)}

[OUTPUT]
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=few_shot_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2, # Low temperature ensures strict fidelity to the example format
                max_output_tokens=2000,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return {
            "success": True,
            "status": "success",
            "report": response.text.strip()
        }
    except Exception as e:
        logging.error(f"Gemini API error during clinical report: {str(e)}")
        return {
            "success": True,
            "status": "error",
            "message": str(e),
            "report": _generate_deterministic_clinical_fallback(patient_name, condition, baseline_data, recent_sessions)
        }

def generate_patient_feedback_few_shot(
    session_type: str,
    duration_sec: int,
    accuracy: float,
    bpm_info: str
) -> str:
    """
    Generate warm, empathetic post-session recovery coaching for patients.
    Uses Few-Shot Prompting to balance praise, fatigue acknowledgment, and rest.
    """
    client = get_gemini_client()
    if not client:
        return _generate_deterministic_patient_feedback(session_type, accuracy)

    from google.genai import types

    few_shot_prompt = f"""You are a warm, compassionate physical therapy coach for neurological recovery patients.
Write exactly a 2-sentence encouraging post-session message based on the patient's performance.

--- EXAMPLE 1 (High Accuracy Session) ---
Input: Session: gait_trainer, Duration: 480s, Accuracy: 88%, BPM: 60 -> 68
Output: Fantastic stepping consistency today—you stayed locked into the beat for 88% of your walk! You reached 68 BPM with great form, so take 10 minutes to sit back, hydrate, and rest your legs.

--- EXAMPLE 2 (Fatigue / Lower Accuracy Session) ---
Input: Session: upper_limb_motor, Duration: 300s, Accuracy: 61%, BPM: 55 -> 52
Output: Good effort pushing through your arm movements today; every repetition helps rebuild neural pathways. Your muscles worked hard today, so let your arms rest and relax before your next session.

--- EXAMPLE 3 (Short / Interrupted Session) ---
Input: Session: gait_trainer, Duration: 3s, Accuracy: 0%, BPM: 40
Output: It is completely fine to start small and pause whenever you need to. Rest up and try again when you are feeling ready for another rhythm session!

==================================================
--- NOW GENERATE FOR THIS SESSION ---
Input: Session: {session_type}, Duration: {duration_sec}s, Accuracy: {round(accuracy)}%, BPM: {bpm_info}
Output:
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=few_shot_prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=1000,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini API error during patient feedback: {str(e)}")
        return _generate_deterministic_patient_feedback(session_type, accuracy)

def _generate_deterministic_clinical_fallback(patient_name: str, condition: str, baseline: Dict, sessions: List[Dict]) -> str:
    """Deterministic fallback summary when API key is missing or offline."""
    total_sessions = len(sessions)
    if total_sessions == 0:
        return f"### Clinical Progress Note (SOAP)\n- **S:** Patient registered for {condition.replace('_', ' ').title()} rehabilitation.\n- **O:** Baseline assessment recorded. No completed therapy sessions to date.\n- **A:** Initial evaluation phase.\n- **P:** Begin prescribed therapy modules."

    avg_acc = sum(s.get('accuracy', 0) for s in sessions) / total_sessions
    last_bpm = sessions[-1].get('final_bpm') or sessions[-1].get('bpm', 60)
    
    return f"""### Clinical Progress Note (SOAP)
*(Generated using clinical rule engine. Add GEMINI_API_KEY to enable AI Few-Shot generation)*

- **S (Subjective):** Patient completed {total_sessions} therapy session(s). Adherence to scheduled rhythmic entrainment protocol is stable.
- **O (Objective):** Average rhythm synchronization accuracy is {round(avg_acc, 1)}%. Final active tempo recorded at {round(last_bpm)} BPM.
- **A (Assessment):** Motor adaptation is progressing according to prescribed auditory cueing. Rhythm entrainment stability is established at current tempo band.
- **P (Plan):** Continue current exercise regimen. Advance target cadence by +3 to +5 BPM if average accuracy exceeds 80% over next 3 sessions."""

def _generate_deterministic_patient_feedback(session_type: str, accuracy: float) -> str:
    """Deterministic patient recovery feedback when API key is missing or offline."""
    if accuracy >= 80:
        return f"Wonderful work maintaining rhythm today with an accuracy of {round(accuracy)}%! Take a few minutes to sit down, hydrate, and give your muscles a well-deserved rest."
    else:
        return f"Great effort completing your therapy session today—every minute of practice strengthens neural recovery! Rest comfortably and hydrate before your next activity."
