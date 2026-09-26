"""
Historical Analysis Service for NeuroBeat Neurorehabilitation Platform.
Provides deterministic, lightweight longitudinal data processing:
1. Historical session retrieval (last 5-10 sessions per patient)
2. Deterministic trend analysis (accuracy trend, BPM trend, averages)
3. Advisory historical BPM recommendation (purely optional/advisory, never overwrites authoritative logic)
4. Contextual accuracy comparison
5. Isolated Prototype / Demonstration dataset (strictly separated from database records)
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

def get_patient_history(
    patient_id: int,
    activity_type: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent completed therapy sessions and clinical reports for a specific patient.
    Lightweight and capped to `limit` records (default 5, max 10) to maintain high performance.
    """
    try:
        from models import TherapySession, ClinicalReport
        from app import db

        # Query completed sessions for this specific patient
        query = TherapySession.query.filter(
            TherapySession.patient_id == patient_id,
            TherapySession.completed == True
        )

        # Normalize activity_type if provided
        if activity_type:
            clean_activity = activity_type.strip().lower()
            # Handle potential underscore/space variations
            query = query.filter(
                (TherapySession.session_type == clean_activity) |
                (TherapySession.session_type == clean_activity.replace(' ', '_'))
            )

        # Order by newest first, capped to limit (max 10)
        safe_limit = max(1, min(10, limit))
        recent_sessions = query.order_by(TherapySession.end_time.desc()).limit(safe_limit).all()

        history = []
        for s in recent_sessions:
            # Check for linked clinical report
            report = ClinicalReport.query.filter_by(session_id=s.id).first()
            avg_bpm = round((s.initial_bpm + s.final_bpm) / 2.0, 1) if (s.initial_bpm and s.final_bpm) else (s.final_bpm or s.initial_bpm or 60.0)

            history.append({
                "session_id": s.id,
                "activity": s.session_type.replace('_', ' ').title() if s.session_type else "General Therapy",
                "session_type": s.session_type,
                "date": s.end_time.strftime("%Y-%m-%d %H:%M") if s.end_time else (s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else "Recent"),
                "duration_seconds": s.duration_seconds or 0,
                "accuracy": round(s.accuracy_score, 1) if s.accuracy_score is not None else None,
                "starting_bpm": round(s.initial_bpm, 1) if s.initial_bpm is not None else 60.0,
                "final_bpm": round(s.final_bpm, 1) if s.final_bpm is not None else (s.initial_bpm or 60.0),
                "average_bpm": avg_bpm,
                "target_bpm": round(s.target_bpm, 1) if s.target_bpm is not None else 70.0,
                "movement_count": report.movement_count if (report and report.movement_count) else 0,
                "report_summary": report.summary if report else None
            })

        return history

    except Exception as e:
        logging.error(f"[historical_analysis] Error fetching patient history for patient_id={patient_id}: {str(e)}", exc_info=True)
        return []

def calculate_historical_trends(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate simple, deterministic trends across historical sessions without external AI dependencies.
    Transparent, verifiable, and fast (<1ms).
    """
    if not sessions:
        return {
            "number_of_previous_sessions": 0,
            "average_previous_accuracy": None,
            "recent_average_accuracy": None,
            "recent_best_accuracy": None,
            "accuracy_trend": "insufficient_data",
            "average_previous_bpm": None,
            "recent_best_bpm": None,
            "bpm_trend": "insufficient_data",
            "previous_successful_bpm_range": None
        }

    total_sessions = len(sessions)
    
    # 1. Accuracy calculations
    valid_accuracies = [s["accuracy"] for s in sessions if s["accuracy"] is not None]
    if valid_accuracies:
        avg_acc = round(sum(valid_accuracies) / len(valid_accuracies), 1)
        best_acc = round(max(valid_accuracies), 1)
        # Recent average: up to the last 3 sessions (sessions are ordered newest-first)
        recent_3 = valid_accuracies[:3]
        recent_avg_acc = round(sum(recent_3) / len(recent_3), 1)
    else:
        avg_acc = None
        best_acc = None
        recent_avg_acc = None

    # Trend detection (chronological: compare older vs newer)
    if len(valid_accuracies) >= 2:
        # Note: sessions are newest first. Reverse to get chronological order
        chronological_accs = list(reversed(valid_accuracies))
        first_half = chronological_accs[:len(chronological_accs)//2 or 1]
        second_half = chronological_accs[len(chronological_accs)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if (avg_second - avg_first) >= 3.0:
            accuracy_trend = "improving"
        elif (avg_first - avg_second) >= 3.0:
            accuracy_trend = "declining"
        else:
            accuracy_trend = "stable"
    elif len(valid_accuracies) == 1:
        accuracy_trend = "stable"
    else:
        accuracy_trend = "insufficient_data"

    # 2. BPM calculations
    valid_bpms = [s["final_bpm"] for s in sessions if s["final_bpm"] is not None]
    if valid_bpms:
        avg_bpm = round(sum(valid_bpms) / len(valid_bpms), 1)
        best_bpm = round(max(valid_bpms), 1)
        min_bpm = round(min(valid_bpms), 1)
        bpm_range_str = f"{int(min_bpm)}–{int(best_bpm)}" if min_bpm != best_bpm else f"{int(min_bpm)}"
    else:
        avg_bpm = None
        best_bpm = None
        bpm_range_str = None

    if len(valid_bpms) >= 2:
        chronological_bpms = list(reversed(valid_bpms))
        if chronological_bpms[-1] > chronological_bpms[0] + 2:
            bpm_trend = "progressing"
        elif chronological_bpms[0] > chronological_bpms[-1] + 2:
            bpm_trend = "decreasing"
        else:
            bpm_trend = "stable"
    elif len(valid_bpms) == 1:
        bpm_trend = "stable"
    else:
        bpm_trend = "insufficient_data"

    return {
        "number_of_previous_sessions": total_sessions,
        "average_previous_accuracy": avg_acc,
        "recent_average_accuracy": recent_avg_acc,
        "recent_best_accuracy": best_acc,
        "accuracy_trend": accuracy_trend,
        "average_previous_bpm": avg_bpm,
        "recent_best_bpm": best_bpm,
        "bpm_trend": bpm_trend,
        "previous_successful_bpm_range": bpm_range_str
    }

def calculate_recommended_bpm(
    patient_profile: Any,
    activity_type: str,
    trends: Dict[str, Any],
    current_target_bpm: float = 70.0,
    current_initial_bpm: float = 60.0
) -> Dict[str, Any]:
    """
    Produce an OPTIONAL advisory BPM recommendation based on previous performance.
    IMPORTANT: This recommendation is purely advisory and NEVER automatically overwrites
    authoritative baseline calculations unless explicitly activated.
    """
    count = trends.get("number_of_previous_sessions", 0)
    recent_acc = trends.get("recent_average_accuracy")
    avg_bpm = trends.get("average_previous_bpm") or current_initial_bpm
    trend = trends.get("accuracy_trend", "stable")

    # If insufficient history, recommend starting at existing authoritative baseline
    if count == 0 or recent_acc is None:
        return {
            "historical_recommended_bpm": round(current_initial_bpm, 1),
            "rationale": "Initial baseline recommendation based on clinical intake profile.",
            "is_advisory": True
        }

    # Clinical pacing logic:
    # 1. High accuracy (>80%) and improving -> gradual +2 BPM increase towards target
    if recent_acc >= 80.0 and trend in ["improving", "stable"]:
        recommended = min(float(current_target_bpm), avg_bpm + 2.0)
        rationale = f"Patient demonstrated strong rhythm synchronization ({recent_acc}%). Gradual +2 BPM progression recommended."
    # 2. Low accuracy (<60%) -> maintain safe baseline or gentle -2 BPM to rebuild regularity
    elif recent_acc < 60.0:
        recommended = max(current_initial_bpm * 0.85, avg_bpm - 2.0)
        rationale = f"Recent accuracy ({recent_acc}%) suggests fatigue or difficulty matching tempo. Consolidating cadence at safe tempo."
    # 3. Stable performance (60-80%) -> hold steady at historical average
    else:
        recommended = avg_bpm
        rationale = f"Stable performance ({recent_acc}%). Consolidating motor rhythm entrainment at current cadence."

    # Safety clamps
    is_speech = activity_type in ["speech_rhythm", "speech_therapy"]
    if is_speech:
        clamped_recommended = max(60.0, min(180.0, recommended))
    else:
        clamped_recommended = max(40.0, min(200.0, recommended))

    return {
        "historical_recommended_bpm": round(clamped_recommended, 1),
        "historical_average_bpm": avg_bpm,
        "historical_average_accuracy": recent_acc,
        "rationale": rationale,
        "is_advisory": True
    }

def build_accuracy_comparison(
    current_accuracy: Optional[float],
    trends: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build a safe, objective comparison between current session accuracy and historical performance.
    Never alters the raw current_accuracy recorded by the sensors.
    """
    if current_accuracy is None:
        return {
            "current_accuracy": None,
            "historical_average_accuracy": trends.get("average_previous_accuracy"),
            "historical_trend": trends.get("accuracy_trend", "insufficient_data"),
            "accuracy_delta": None,
            "status": "No real-time accuracy captured for current session."
        }

    hist_avg = trends.get("average_previous_accuracy")
    if hist_avg is not None:
        delta = round(current_accuracy - hist_avg, 1)
        delta_str = f"+{delta}%" if delta > 0 else f"{delta}%"
    else:
        delta = None
        delta_str = "Baseline session"

    return {
        "current_accuracy": round(current_accuracy, 1),
        "historical_average_accuracy": hist_avg,
        "accuracy_delta": delta_str,
        "historical_trend": trends.get("accuracy_trend", "stable")
    }

def get_demo_historical_context(activity_type: str = "Gait Trainer") -> Dict[str, Any]:
    """
    Feature 7: DEMONSTRATION / PROTOTYPE MODE.
    Provides a small, clean synthetic dataset to demonstrate longitudinal learning
    without fabricating real clinical records or inserting anything into the real database.
    """
    synthetic_sessions = [
        {
            "session_id": "DEMO-004",
            "activity": activity_type,
            "session_type": activity_type.lower().replace(' ', '_'),
            "date": "Demo Progression 3",
            "duration_seconds": 200,
            "accuracy": 80.0,
            "starting_bpm": 59.0,
            "final_bpm": 61.0,
            "average_bpm": 60.0,
            "target_bpm": 65.0,
            "movement_count": 202,
            "report_summary": "Strong synchronization achieved across target cadence."
        },
        {
            "session_id": "DEMO-003",
            "activity": activity_type,
            "session_type": activity_type.lower().replace(' ', '_'),
            "date": "Demo Progression 2",
            "duration_seconds": 180,
            "accuracy": 76.0,
            "starting_bpm": 57.0,
            "final_bpm": 59.0,
            "average_bpm": 58.0,
            "target_bpm": 65.0,
            "movement_count": 174,
            "report_summary": "Auditory following stabilized with higher rhythm alignment."
        },
        {
            "session_id": "DEMO-002",
            "activity": activity_type,
            "session_type": activity_type.lower().replace(' ', '_'),
            "date": "Demo Progression 1",
            "duration_seconds": 150,
            "accuracy": 72.0,
            "starting_bpm": 55.0,
            "final_bpm": 57.0,
            "average_bpm": 56.0,
            "target_bpm": 65.0,
            "movement_count": 142,
            "report_summary": "Improved step consistency noted during middle interval."
        },
        {
            "session_id": "DEMO-001",
            "activity": activity_type,
            "session_type": activity_type.lower().replace(' ', '_'),
            "date": "Demo Baseline",
            "duration_seconds": 120,
            "accuracy": 68.0,
            "starting_bpm": 55.0,
            "final_bpm": 55.0,
            "average_bpm": 55.0,
            "target_bpm": 65.0,
            "movement_count": 110,
            "report_summary": "Initial baseline entrainment established."
        }
    ]

    trends = calculate_historical_trends(synthetic_sessions)
    recommended = {
        "historical_recommended_bpm": 63.0,
        "historical_average_bpm": 57.2,
        "historical_average_accuracy": 74.0,
        "rationale": "Prototype demo shows an improving trajectory from 68% to 80% accuracy. Progression to 63 BPM recommended.",
        "is_advisory": True
    }

    return {
        "is_demo": True,
        "mode": "PROTOTYPE_DEMONSTRATION",
        "patient_id": "DEMO_PATIENT",
        "activity": activity_type,
        "previous_sessions": synthetic_sessions,
        "trends": trends,
        "recommended_bpm": recommended,
        "note": "Demonstration mode only. This synthetic data is never saved to the medical database."
    }

def build_historical_context(
    patient_id: int,
    activity_type: Optional[str] = None,
    limit: int = 5,
    allow_demo_fallback: bool = False,
    current_target_bpm: float = 70.0,
    current_initial_bpm: float = 60.0
) -> Dict[str, Any]:
    """
    Unified entry point to construct a compact historical context object for a patient.
    Safely fallbacks to empty/demo context if patient is brand new.
    """
    # 1. Fetch real sessions
    real_sessions = get_patient_history(patient_id=patient_id, activity_type=activity_type, limit=limit)

    # 2. Check if we should use demo fallback (strictly when real history is empty AND explicitly requested)
    if not real_sessions and allow_demo_fallback:
        return get_demo_historical_context(activity_type=activity_type or "Gait Trainer")

    # 3. Calculate deterministic trends
    trends = calculate_historical_trends(real_sessions)

    # 4. Calculate advisory recommended BPM
    recommendation = calculate_recommended_bpm(
        patient_profile=None,
        activity_type=activity_type or "gait_trainer",
        trends=trends,
        current_target_bpm=current_target_bpm,
        current_initial_bpm=current_initial_bpm
    )

    # 5. Assemble compact historical context
    activity_name = activity_type.replace('_', ' ').title() if activity_type else "General Therapy"
    return {
        "is_demo": False,
        "patient_id": patient_id,
        "activity": activity_name,
        "previous_sessions_count": len(real_sessions),
        "previous_sessions": real_sessions,
        "trends": trends,
        "recommended_bpm": recommendation
    }
