/**
 * Authoritative TherapySession Controller for NeuroBeat
 * Single source of truth for:
 * - Active session duration (accumulated active time using performance.now(), excluding paused time)
 * - True session start / pause / resume / completion lifecycle
 * - Event-to-beat synchronization accuracy (no Math.random(), 20% tolerance, phase alignment, coverage penalty)
 * - Server synchronization & clinical safety BPM adaptation
 */

class TherapySession {
    constructor(config) {
        this.sessionId = config.sessionId;
        this.sessionType = config.sessionType || 'gait_trainer';
        this.initialBPM = Number(config.initialBPM) || 60;
        this.targetBPM = Number(config.targetBPM) || 70;
        this.currentBPM = this.initialBPM;
        this.selectedBeatSound = config.selectedBeatSound || 'metronome';
        this.aiAdjustmentEnabled = config.aiAdjustmentEnabled !== false;

        // Active Duration Tracking (active time only, strictly excludes paused time)
        this.accumulatedDuration = 0; // milliseconds of active running time
        this.runStartedAt = null;     // performance.now() timestamp when current active interval began
        this.isActive = false;
        this.isStarted = false;

        // Timers & Intervals
        this.timerInterval = null;
        this.updateInterval = null;

        // Authoritative Rhythm & Accuracy Pipeline
        this.expectedBeats = [];      // Timestamps (seconds from active start) of played metronome beats
        this.performanceEvents = [];  // Timestamps (seconds from active start) of detected real events
        this.lastEvaluatedTime = 0;   // Active seconds evaluated up to
        this.lastBeatIndex = 0;

        // Running statistics across the entire session (never truncated)
        this.runningAccuracySum = 0;
        this.runningAccuracyCount = 0;
        this.currentAccuracy = null;   // null represents "insufficient data" / "waiting for input"
        this.currentStatusText = 'Ready to start';

        this.accuracyHistory = [];
        this.bpmHistory = [];

        // Audio and camera callback hooks
        this.onStartAudio = config.onStartAudio || null;
        this.onStopAudio = config.onStopAudio || null;
        this.onAdjustAudioTempo = config.onAdjustAudioTempo || null;
        this.onStartCamera = config.onStartCamera || null;
        this.onPauseCamera = config.onPauseCamera || null;
        this.onStopCamera = config.onStopCamera || null;
        this.onUpdateChart = config.onUpdateChart || null;

        this.updateUI();
    }

    // -------------------------------------------------------------
    // Active Duration Management
    // -------------------------------------------------------------

    /** Returns total accumulated active running time in milliseconds */
    getActiveDurationMs() {
        let total = this.accumulatedDuration;
        if (this.isActive && this.runStartedAt !== null) {
            total += (performance.now() - this.runStartedAt);
        }
        return Math.max(0, total);
    }

    /** Returns active duration in seconds (floating point for precision) */
    getActiveDurationSecondsPrecise() {
        return this.getActiveDurationMs() / 1000.0;
    }

    /** Returns active duration in whole seconds */
    getActiveDurationSeconds() {
        return Math.floor(this.getActiveDurationMs() / 1000.0);
    }

    /** Returns timer formatted as MM:SS */
    getFormattedTimer() {
        const totalSec = this.getActiveDurationSeconds();
        const minutes = Math.floor(totalSec / 60);
        const seconds = totalSec % 60;
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    /** Returns friendly duration string (e.g. '1m 05s' or '35s') */
    getFriendlyDuration() {
        const totalSec = this.getActiveDurationSeconds();
        const minutes = Math.floor(totalSec / 60);
        const seconds = totalSec % 60;
        if (minutes > 0) {
            return `${minutes}m ${String(seconds).padStart(2, '0')}s`;
        }
        return `${seconds}s`;
    }

    // -------------------------------------------------------------
    // Event & Beat Recording
    // -------------------------------------------------------------

    /** Record an expected beat timestamp on the active session timeline */
    recordExpectedBeat(activeTimestampSec = null) {
        if (!this.isActive) return;
        const ts = activeTimestampSec !== null ? activeTimestampSec : this.getActiveDurationSecondsPrecise();
        this.expectedBeats.push(ts);
    }

    /**
     * Record a genuine detected physical performance event
     * @param {string} type - 'step', 'arm_movement', 'voice', or 'cognitive_tap'
     * @param {number} confidence - event detection confidence (0.0 to 1.0)
     */
    recordPerformanceEvent(type, confidence = 1.0) {
        if (!this.isActive) return;
        const ts = this.getActiveDurationSecondsPrecise();
        const ev = {
            timestamp: ts,
            type: type,
            confidence: Math.max(0.0, Math.min(1.0, confidence))
        };
        this.performanceEvents.push(ev);

        // Keep last 150 events to avoid unbounded memory while maintaining sufficient history
        if (this.performanceEvents.length > 150) {
            this.performanceEvents.shift();
        }

        console.debug(`[NeuroBeat Event] ${type} at ${ts.toFixed(3)}s (confidence: ${confidence.toFixed(2)})`);
        this.updateStatusDisplay(true, 'Active');
    }

    // -------------------------------------------------------------
    // Authoritative Event-to-Beat Rhythm Synchronization Formula
    // -------------------------------------------------------------

    /**
     * Evaluates rhythm synchronization accuracy over the recent performance window.
     * Compares each expected beat against nearest real performance event within a 20% tolerance.
     * Incorporates coverage and timing score. Never uses Math.random().
     */
    evaluateCurrentAccuracy() {
        if (!this.isActive) return null;

        const currentActiveSec = this.getActiveDurationSecondsPrecise();
        // Evaluate window of recent beats (last 5 seconds)
        const windowDuration = 5.0;
        const windowStart = Math.max(0, currentActiveSec - windowDuration);

        // Find expected beats in this window
        const beatsInWindow = this.expectedBeats.filter(b => b >= windowStart && b <= currentActiveSec);

        // Find detected performance events in this window
        const eventsInWindow = this.performanceEvents.filter(e => e.timestamp >= (windowStart - 0.5) && e.timestamp <= (currentActiveSec + 0.5));

        // GUARD: If no events detected, report insufficient data rather than fabricating an accuracy
        if (eventsInWindow.length === 0) {
            this.currentAccuracy = null;
            if (this.sessionType === 'speech_rhythm' || this.sessionType === 'speech_therapy' || this.sessionType === 'melodic_intonation') {
                this.currentStatusText = 'Waiting for voice';
            } else if (this.sessionType === 'cognitive_rhythm') {
                this.currentStatusText = 'Waiting for response';
            } else if (this.sessionType === 'finger_tapping') {
                this.currentStatusText = 'Waiting for tap';
            } else if (this.sessionType === 'balance_training') {
                this.currentStatusText = 'Waiting for stance movement';
            } else {
                this.currentStatusText = 'Waiting for movement';
            }
            this.updateAccuracyDisplay(null, this.currentStatusText);
            return null;
        }

        if (beatsInWindow.length === 0) {
            this.updateAccuracyDisplay(null, 'Listening for beats');
            return null;
        }

        const beatInterval = 60.0 / this.currentBPM;
        const tolerance = 0.20 * beatInterval; // 20% timing tolerance

        const matchedTimingAccuracies = [];
        const claimedEventIndices = new Set();

        for (const beatTime of beatsInWindow) {
            let bestError = Infinity;
            let bestIdx = null;

            for (let i = 0; i < eventsInWindow.length; i++) {
                if (claimedEventIndices.has(i)) continue;
                const err = Math.abs(eventsInWindow[i].timestamp - beatTime);
                if (err <= (beatInterval * 0.5) && err < bestError) {
                    bestError = err;
                    bestIdx = i;
                }
            }

            if (bestIdx !== null && bestError <= tolerance) {
                claimedEventIndices.add(bestIdx);
                // Linear timing accuracy from 100% (0 error) down to 0% (at tolerance limit)
                const timingAcc = Math.max(0.0, Math.min(100.0, 100.0 * (1.0 - (bestError / tolerance))));
                matchedTimingAccuracies.push(timingAcc);
            }
        }

        const totalExpected = beatsInWindow.length;
        const matchedCount = matchedTimingAccuracies.length;
        const coverage = totalExpected > 0 ? (matchedCount / totalExpected) : 0;
        const timingScore = matchedCount > 0 ? (matchedTimingAccuracies.reduce((a, b) => a + b, 0) / matchedCount) : 0;

        // Authoritative Prototype Formula: 70% Timing Accuracy + 30% Beat Coverage
        const windowOverall = Math.max(0.0, Math.min(100.0, (0.70 * timingScore) + (0.30 * (coverage * 100.0))));
        const roundedAcc = Math.round(windowOverall);

        this.currentAccuracy = roundedAcc;
        this.currentStatusText = roundedAcc >= 80 ? 'In Sync' : (roundedAcc >= 60 ? 'Adapting' : 'Off-beat');

        // Add to running session statistics
        this.runningAccuracySum += windowOverall;
        this.runningAccuracyCount += 1;

        this.accuracyHistory.push({
            timestamp: new Date(),
            bpm: this.currentBPM,
            timingScore: Math.round(timingScore),
            coverage: Math.round(coverage * 100),
            overallAccuracy: roundedAcc,
            eventCount: eventsInWindow.length
        });

        this.updateAccuracyDisplay(roundedAcc, this.currentStatusText);
        return roundedAcc;
    }

    /** Calculates overall session average accuracy across all valid windows */
    calculateOverallAccuracy() {
        if (this.runningAccuracyCount === 0) {
            return null; // Insufficient data throughout session
        }
        return Math.round(this.runningAccuracySum / this.runningAccuracyCount);
    }

    // -------------------------------------------------------------
    // Session Lifecycle Management
    // -------------------------------------------------------------

    /** Start the therapy session */
    async start() {
        if (this.isActive) return;

        console.log(`[NeuroBeat] Starting active therapy session ${this.sessionId}`);

        // Notify server of true active start
        try {
            const resp = await fetch(`/session/${this.sessionId}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (resp.ok) {
                console.log(`[NeuroBeat] Server recorded active start for session ${this.sessionId}`);
            }
        } catch (e) {
            console.warn('[NeuroBeat] Server start notification warning:', e);
        }

        this.runStartedAt = performance.now();
        this.isActive = true;
        this.isStarted = true;

        // UI Controls state
        const startBtn = document.getElementById('startBtn');
        const pauseBtn = document.getElementById('pauseBtn');
        const stopBtn = document.getElementById('stopBtn');
        if (startBtn) startBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = 'inline-block';
        if (stopBtn) stopBtn.style.display = 'inline-block';

        // Start Audio Engine
        if (this.onStartAudio) {
            this.onStartAudio(this.currentBPM);
        }

        // Start Camera
        if (this.onStartCamera) {
            this.onStartCamera();
        }

        // Start Timers
        this.timerInterval = setInterval(() => {
            this.updateTimerDisplay();
        }, 1000);

        // Start Periodic Accuracy & BPM Synchronization (every 4 seconds)
        this.updateInterval = setInterval(() => {
            this.sendSessionUpdate();
        }, 4000);

        this.updateTimerDisplay();
        this.updateUI();
    }

    /** Pause the therapy session (freezes active duration accumulator) */
    pause() {
        if (!this.isActive) return;

        // Accumulate active duration up to this exact millisecond
        if (this.runStartedAt !== null) {
            this.accumulatedDuration += (performance.now() - this.runStartedAt);
            this.runStartedAt = null;
        }
        this.isActive = false;

        console.log(`[NeuroBeat] Session paused. Active duration: ${this.getActiveDurationSeconds()}s`);

        // UI Controls state
        const startBtn = document.getElementById('startBtn');
        const pauseBtn = document.getElementById('pauseBtn');
        if (startBtn) {
            startBtn.style.display = 'inline-block';
            startBtn.innerHTML = '<i data-feather="play" class="me-2"></i>Resume';
        }
        if (pauseBtn) pauseBtn.style.display = 'none';

        // Pause audio & camera
        if (this.onStopAudio) {
            this.onStopAudio();
        }
        if (this.onPauseCamera) {
            this.onPauseCamera();
        }

        // Clear running intervals
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }

        this.updateTimerDisplay();
        this.updateStatusDisplay(false, 'Paused');
        if (typeof feather !== 'undefined') feather.replace();
    }

    /** Resume the therapy session */
    resume() {
        if (this.isActive) return;

        this.runStartedAt = performance.now();
        this.isActive = true;

        console.log(`[NeuroBeat] Session resumed at ${this.getActiveDurationSeconds()}s`);

        const startBtn = document.getElementById('startBtn');
        const pauseBtn = document.getElementById('pauseBtn');
        if (startBtn) startBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = 'inline-block';

        if (this.onStartAudio) {
            this.onStartAudio(this.currentBPM);
        }
        if (this.onStartCamera) {
            this.onStartCamera();
        }

        this.timerInterval = setInterval(() => {
            this.updateTimerDisplay();
        }, 1000);

        this.updateInterval = setInterval(() => {
            this.sendSessionUpdate();
        }, 4000);

        this.updateTimerDisplay();
        this.updateStatusDisplay(true, 'Active');
        if (typeof feather !== 'undefined') feather.replace();
    }

    /** Complete the therapy session and commit exact active duration and accuracy to backend */
    async complete() {
        // Freeze duration accumulator
        if (this.isActive && this.runStartedAt !== null) {
            this.accumulatedDuration += (performance.now() - this.runStartedAt);
            this.runStartedAt = null;
        }
        this.isActive = false;

        // Clear intervals
        if (this.timerInterval) clearInterval(this.timerInterval);
        if (this.updateInterval) clearInterval(this.updateInterval);

        // Stop audio and camera completely
        if (this.onStopAudio) this.onStopAudio();
        if (this.onStopCamera) this.onStopCamera();

        const exactActiveSeconds = this.getActiveDurationSeconds();
        const finalAccuracy = this.calculateOverallAccuracy();

        console.log(`[NeuroBeat] Completing session ${this.sessionId}: Active Duration = ${exactActiveSeconds}s, Final Accuracy = ${finalAccuracy}%`);

        const submitBtn = document.getElementById('stopBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Completing...';
        }

        try {
            const response = await fetch(`/session/${this.sessionId}/complete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duration: exactActiveSeconds,
                    final_bpm: this.currentBPM,
                    accuracy_score: finalAccuracy,
                    notes: `Completed ${this.sessionType.replace('_', ' ')} therapy. Active Duration: ${this.getFriendlyDuration()}. BPM range: ${this.initialBPM} -> ${Math.round(this.currentBPM)}. Average Accuracy: ${finalAccuracy !== null ? finalAccuracy + '%' : 'Insufficient data'}.`
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Populate completion modal
                const accEl = document.getElementById('modalAccuracyScore');
                const durEl = document.getElementById('modalDuration');
                const bpmEl = document.getElementById('modalFinalBpm');
                const feedbackEl = document.getElementById('modalAiFeedback');
                const whatYouDidEl = document.getElementById('modalWhatYouDid');
                const keyImprovementsEl = document.getElementById('modalKeyImprovements');

                if (accEl) accEl.textContent = finalAccuracy !== null ? `${finalAccuracy}%` : 'N/A';
                if (durEl) durEl.textContent = this.getFriendlyDuration();
                if (bpmEl) bpmEl.textContent = Math.round(this.currentBPM);

                const summaryText = data.summary || data.feedback || "Terrific commitment to today's rehabilitation session! Regular rhythmic entrainment supports motor neuroplasticity.";
                if (feedbackEl) feedbackEl.textContent = summaryText;

                // Render "What You Did" bullet points
                if (whatYouDidEl) {
                    const didItems = Array.isArray(data.what_you_did) && data.what_you_did.length > 0
                        ? data.what_you_did
                        : [
                            `Completed ${this.getFriendlyDuration()} of structured ${this.sessionType.replace('_', ' ')} rhythmic entrainment.`,
                            `Maintained cadence between ${Math.round(this.initialBPM)} BPM and ${Math.round(this.currentBPM)} BPM.`
                        ];
                    whatYouDidEl.innerHTML = didItems.map(item => `
                        <li class="d-flex align-items-start gap-2 mb-1">
                            <span class="text-success mt-1" style="font-size: 0.65rem;">●</span>
                            <span>${item}</span>
                        </li>
                    `).join('');
                }

                // Render "Key Improvements" bullet points
                if (keyImprovementsEl) {
                    const improveItems = Array.isArray(data.what_to_improve) && data.what_to_improve.length > 0
                        ? data.what_to_improve
                        : [
                            "Focus on consistent rhythmic synchronization during tempo transitions.",
                            "Maintain steady posture and symmetrical motor movement throughout the session."
                        ];
                    keyImprovementsEl.innerHTML = improveItems.map(item => `
                        <li class="d-flex align-items-start gap-2 mb-1">
                            <span class="text-info mt-1" style="font-size: 0.65rem;">●</span>
                            <span>${item}</span>
                        </li>
                    `).join('');
                }

                const modalEl = document.getElementById('sessionCompleteModal');
                if (modalEl && typeof bootstrap !== 'undefined') {
                    const completeModal = new bootstrap.Modal(modalEl);
                    if (typeof feather !== 'undefined') feather.replace();
                    completeModal.show();
                } else {
                    alert(`Session Completed!\nActive Duration: ${this.getFriendlyDuration()}\nAccuracy: ${finalAccuracy !== null ? finalAccuracy + '%' : 'N/A'}`);
                    window.location.href = '/patient/dashboard';
                }
            } else {
                alert(`Error completing session: ${data.error || 'Server sync error'}`);
                window.location.href = '/patient/dashboard';
            }
        } catch (error) {
            console.error('Session complete error:', error);
            alert('Session completed locally. Returning to dashboard.');
            window.location.href = '/patient/dashboard';
        }
    }

    // -------------------------------------------------------------
    // Periodic Server Synchronization & BPM Adaptation
    // -------------------------------------------------------------

    async sendSessionUpdate() {
        if (!this.isActive) return;

        // 1. Evaluate accuracy on actual events in recent window
        const currentAcc = this.evaluateCurrentAccuracy();

        // 2. Transmit to server
        try {
            const response = await fetch('/session/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    current_bpm: this.currentBPM,
                    sync_accuracy: currentAcc
                })
            });

            if (response.ok) {
                const data = await response.json();

                // Adaptive BPM update if suggested by server and adjustment is enabled
                if (this.aiAdjustmentEnabled && data.adjusted_bpm && data.adjusted_bpm !== this.currentBPM) {
                    const oldBpm = this.currentBPM;
                    this.currentBPM = data.adjusted_bpm;
                    console.log(`[NeuroBeat Adaptation] BPM adjusted from ${oldBpm} to ${this.currentBPM}`);

                    // Adjust Tone.js audio metronome tempo
                    if (this.onAdjustAudioTempo) {
                        this.onAdjustAudioTempo(this.currentBPM);
                    }

                    this.bpmHistory.push({
                        time: this.getActiveDurationSeconds(),
                        bpm: this.currentBPM
                    });

                    if (this.onUpdateChart) {
                        this.onUpdateChart();
                    }
                }
            }
        } catch (error) {
            console.warn('[NeuroBeat] Periodic update warning:', error);
        }

        if (this.onUpdateChart) {
            this.onUpdateChart();
        }

        this.updateUI();
    }

    // -------------------------------------------------------------
    // UI Rendering
    // -------------------------------------------------------------

    updateTimerDisplay() {
        const timerEl = document.getElementById('sessionTimer');
        if (timerEl) {
            timerEl.textContent = this.getFormattedTimer();
        }
    }

    updateAccuracyDisplay(accuracy, statusText) {
        const accuracyEl = document.getElementById('accuracy');
        const progressBar = document.getElementById('accuracyProgress');

        if (accuracy === null || isNaN(accuracy)) {
            if (accuracyEl) accuracyEl.textContent = '--%';
            if (progressBar) {
                progressBar.style.width = '0%';
                progressBar.textContent = statusText || 'Waiting for movement';
                progressBar.className = 'progress-bar bg-secondary';
            }
        } else {
            const rounded = Math.round(accuracy);
            if (accuracyEl) accuracyEl.textContent = `${rounded}%`;
            if (progressBar) {
                progressBar.style.width = `${rounded}%`;
                progressBar.textContent = `${rounded}% Rhythm Synchronization`;
                progressBar.className = 'progress-bar';
                if (rounded >= 80) {
                    progressBar.classList.add('bg-success');
                } else if (rounded >= 60) {
                    progressBar.classList.add('bg-warning');
                } else {
                    progressBar.classList.add('bg-danger');
                }
            }
        }
    }

    updateStatusDisplay(isActive, text) {
        const voiceIndicator = document.getElementById('voiceIndicator');
        const micIcon = document.getElementById('micIcon');
        if (voiceIndicator) {
            voiceIndicator.textContent = text;
            voiceIndicator.style.color = isActive ? '#10b981' : '#64748b';
        }
        if (micIcon && typeof feather !== 'undefined') {
            micIcon.setAttribute('data-feather', isActive ? 'activity' : 'activity');
            feather.replace();
        }
    }

    updateUI() {
        // Update BPM display
        const currentBpmEl = document.getElementById('currentBPM');
        if (currentBpmEl) {
            currentBpmEl.textContent = Math.round(this.currentBPM);
        }

        const targetBpmEl = document.getElementById('targetBPM');
        if (targetBpmEl) {
            targetBpmEl.textContent = Math.round(this.targetBPM);
        }

        this.updateTimerDisplay();
        this.updateAccuracyDisplay(this.currentAccuracy, this.currentStatusText);
    }
}

// Attach to window for global access
window.TherapySession = TherapySession;
