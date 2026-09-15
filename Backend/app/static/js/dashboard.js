// ════════════════════════════════════════════════════════
// ErgoVision — dashboard.js
// ════════════════════════════════════════════════════════


// ── THEME TOGGLE ─────────────────────────────────────────
(function () {
    const root   = document.documentElement;
    const toggle = document.getElementById('themeToggle');
    const icon   = document.getElementById('toggleIcon');
    const label  = document.getElementById('toggleLabel');

    applyTheme(localStorage.getItem('ergovision-theme') || 'light');

    toggle.addEventListener('click', () => {
        applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        localStorage.setItem('ergovision-theme', theme);
        icon.textContent  = theme === 'dark' ? '🌙' : '☀️';
        label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    }
})();


// ── LOGIN ────────────────────────────────────────────────
(function () {
    const overlay  = document.getElementById('loginOverlay');
    const form     = document.getElementById('loginForm');
    const nameInp  = document.getElementById('loginName');
    const greeting = document.getElementById('userGreeting');
    const nameSpan = document.getElementById('userName');
    const logoutBtn= document.getElementById('logoutBtn');

    const saved = sessionStorage.getItem('ergovision-user');
    saved ? showApp(saved) : showLogin();

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const n = nameInp.value.trim();
        if (!n) return;
        sessionStorage.setItem('ergovision-user', n);
        showApp(n);
    });
    logoutBtn.addEventListener('click', () => {
    stopFrameLoop();
    stopWebcam();
    if (detectionActive) {
        fetch('/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_name: sessionStorage.getItem('ergovision-user') || 'Unknown' })
        });
        detectionActive = false;
    }   
        stopStatsPolling();
    videoFeed.style.display = 'none';
    videoFeed.src = '';
    noVideo.style.display = 'block';
    startBtn.disabled = false;
    stopBtn.disabled = true;
    downloadPdfBtn.disabled = false;
    exportBtn.disabled      = false;

    sessionStorage.removeItem('ergovision-user');
    showLogin();
    });

    function showApp(name) { overlay.style.display = 'none'; greeting.style.display = 'flex'; nameSpan.textContent = name; }
    function showLogin()   { overlay.style.display = 'flex'; greeting.style.display = 'none'; }
})();


const SoundManager = (function () {
    let enabled  = localStorage.getItem('ergovision-sound') !== 'false';
    let audioCtx = null;
    let unlocked = false;      // true once user has clicked something

    const toggleBtn  = document.getElementById('soundToggleBtn');
    const toggleIcon = document.getElementById('soundToggleIcon');
    const toggleText = document.getElementById('soundToggleText');
    const testBtn    = document.getElementById('soundTestBtn');

    // ── Unlock AudioContext on first any-click on page ──────
    // This one-time listener runs on the very first user interaction.
    document.addEventListener('click', function unlockOnce() {
        _getCtx().then(() => { unlocked = true; });
        document.removeEventListener('click', unlockOnce);
    }, { once: true });

    function updateUI() {
        toggleIcon.textContent = enabled ? '🔔' : '🔕';
        toggleText.textContent = enabled ? 'Sound On' : 'Sound Off';
        toggleBtn.classList.toggle('sound-off', !enabled);
    }
    updateUI();

    toggleBtn.addEventListener('click', () => {
        enabled = !enabled;
        localStorage.setItem('ergovision-sound', enabled);
        updateUI();
        if (enabled) _play(880, 0.2, 'sine', 0.2);   // confirmation chime
    });

    // Test button — explicit user gesture that unlocks AudioContext
    testBtn.addEventListener('click', () => {
        _getCtx().then(() => {
            unlocked = true;
            // Play the posture alert sound as the test
            _play(440, 0.4, 'square', 0.28);
            setTimeout(() => _play(330, 0.35, 'square', 0.22), 280);
            setTimeout(() => _play(440, 0.3, 'square', 0.18), 560);
            showToast('🔔 Audio unlocked! Alerts will now play.');
        });
    });

    // Create or return existing AudioContext, always resume it
    async function _getCtx() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }
        return audioCtx;
    }

    // Core tone generator
    async function _play(freq, dur, type = 'sine', vol = 0.25) {
        if (!enabled) return;
        try {
            const ctx  = await _getCtx();
            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = type;
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
            gain.gain.setValueAtTime(vol, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + dur);
        } catch (e) {
            console.warn('[Sound] Error:', e.message);
        }
    }

    // ── Public alert sounds ──────────────────────────────
    function postureAlert() {
        // Low-high buzz — unmistakeable "wrong" sound
        _play(300, 0.5, 'sawtooth', 0.3);
        setTimeout(() => _play(250, 0.4, 'sawtooth', 0.25), 350);
        setTimeout(() => _play(300, 0.5, 'sawtooth', 0.2),  700);
    }

    function eyeRuleAlert() {
        // Ascending chime — gentle reminder
        _play(523, 0.25, 'sine', 0.22);   // C5
        setTimeout(() => _play(659, 0.25, 'sine', 0.2),  200); // E5
        setTimeout(() => _play(784, 0.4,  'sine', 0.18), 400); // G5
    }

    function success() {
        // Short positive chime
        _play(880, 0.12, 'sine', 0.15);
        setTimeout(() => _play(1100, 0.22, 'sine', 0.12), 110);
    }

    return { postureAlert, eyeRuleAlert, success };
})();


// ── POSTURE CHART ────────────────────────────────────────
const PostureChart = (function () {
    const canvas  = document.getElementById('postureChart');
    const ctx2d   = canvas ? canvas.getContext('2d') : null;
    const history = [];
    const MAX     = 60;

    function push(status) {
        history.push(status);
        if (history.length > MAX) history.shift();
        draw();
    }

    function draw() {
        if (!ctx2d) return;
        const W = canvas.width  = canvas.offsetWidth;
        const H = canvas.height = canvas.offsetHeight;
        ctx2d.clearRect(0, 0, W, H);

        const isDark    = document.documentElement.getAttribute('data-theme') === 'dark';
        const goodColor = isDark ? '#00c4a0' : '#0f6b5c';
        const badColor  = isDark ? '#ff6b7a' : '#b83a4a';

        if (history.length < 2) {
            ctx2d.fillStyle = isDark ? '#4a6a8a' : '#9aaabb';
            ctx2d.font = '11px Plus Jakarta Sans, sans-serif';
            ctx2d.textAlign = 'center';
            ctx2d.fillText('Waiting for data…', W / 2, H / 2 + 4);
            return;
        }

        const bw = W / MAX;
        history.forEach((s, i) => {
            ctx2d.fillStyle   = s === 'Good' ? goodColor : badColor;
            ctx2d.globalAlpha = 0.85;
            const bh = s === 'Good' ? H * 0.5 : H * 0.92;
            ctx2d.fillRect(i * bw, H - bh, Math.max(bw - 1, 1), bh);
        });
        ctx2d.globalAlpha = 1;
    }

    return { push, draw };
})();


// ── HELP CAROUSEL ───────────────────────────────────────
(function () {
    const tips = [
        { icon: '📸', title: 'Camera Position',  text: 'Place camera at eye level, 50–70 cm away for best accuracy.' },
        { icon: '🪑', title: 'Calibrate First',  text: 'Sit up straight for the first 3 seconds after clicking Start. That becomes your baseline.' },
        { icon: '👁️', title: '20-20-20 Rule',    text: 'Every 20 min, look 20 feet away for 20 sec. The timer tracks this automatically.' },
        { icon: '🔔', title: 'Enable Sound',     text: 'Click the orange "▶ Test" button once to unlock audio. Then alerts will play automatically.' },
        { icon: '📊', title: 'Posture Chart',    text: 'Green bars = good posture, red = bad. Updated every second for the last 60 seconds.' },
        { icon: '📥', title: 'PDF Report',       text: 'Click the green "Download PDF Report" button after your session ends.' },
    ];

    let current = 0;
    const helpBtn   = document.getElementById('helpBtn');
    const helpPanel = document.getElementById('helpPanel');
    const helpClose = document.getElementById('helpClose');
    const tipIcon   = document.getElementById('helpTipIcon');
    const tipTitle  = document.getElementById('helpTipTitle');
    const tipText   = document.getElementById('helpTipText');
    const helpPrev  = document.getElementById('helpPrev');
    const helpNext  = document.getElementById('helpNext');
    const helpDots  = document.getElementById('helpDots');

    function render() {
        const t = tips[current];
        tipIcon.textContent  = t.icon;
        tipTitle.textContent = t.title;
        tipText.textContent  = t.text;
        helpDots.innerHTML   = tips.map((_, i) =>
            `<span class="help-dot ${i === current ? 'active' : ''}" data-i="${i}"></span>`
        ).join('');
        helpDots.querySelectorAll('.help-dot').forEach(d =>
            d.addEventListener('click', () => { current = +d.dataset.i; render(); })
        );
    }

    helpBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        helpPanel.classList.toggle('visible');
        render();
    });
    helpClose.addEventListener('click', () => helpPanel.classList.remove('visible'));
    helpPrev.addEventListener('click',  () => { current = (current - 1 + tips.length) % tips.length; render(); });
    helpNext.addEventListener('click',  () => { current = (current + 1) % tips.length; render(); });
    document.addEventListener('click',  (e) => {
        if (!helpPanel.contains(e.target) && e.target !== helpBtn)
            helpPanel.classList.remove('visible');
    });
})();


// ════════════════════════════════════════════════════════
// CORE DETECTION
// ════════════════════════════════════════════════════════
let detectionActive  = false;
let statsInterval    = null;
let currentSessionId = null;
let lastPostureAlert = 0;
let lastEyeAlert     = 0;
const ALERT_COOLDOWN = 30000;   // 30s minimum between repeated sounds

const startBtn          = document.getElementById('startBtn');
const stopBtn           = document.getElementById('stopBtn');
const saveSettingsBtn   = document.getElementById('saveSettings');
const exportBtn         = document.getElementById('exportBtn');
const downloadPdfBtn    = document.getElementById('downloadPdfBtn');
const videoFeed         = document.getElementById('videoFeed');
const noVideo           = document.getElementById('noVideo');
const modal             = document.getElementById('summaryModal');
const closeModal        = document.querySelector('.close');
const downloadReportBtn = document.getElementById('downloadReportBtn');

// ── WEBCAM CAPTURE (browser-side) ─────────────────────────
const webcamVideo = document.getElementById('webcamVideo');
const captureCanvas = document.getElementById('captureCanvas');
let webcamStream = null;

async function startWebcam() {
    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });
        webcamVideo.srcObject = webcamStream;
        console.log('Webcam started successfully');
        return true;
    } catch (err) {
        console.error('Webcam access failed:', err);
        alert('Could not access webcam: ' + err.message);
        return false;
    }
}

function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
    }
}

window.addEventListener('beforeunload', () => {
    stopWebcam();
    // Tell the server too, so it doesn't stay stuck thinking detection
    // is still running. sendBeacon works reliably even as the page is
    // closing (a normal fetch() might get cancelled mid-flight).
    if (detectionActive) {
        navigator.sendBeacon('/stop', new Blob(
            [JSON.stringify({ user_name: sessionStorage.getItem('ergovision-user') || 'Unknown' })],
            { type: 'application/json' }
        ));
    }
});

// ── Start ────────────────────────────────────────────────
startBtn.addEventListener('click', async () => {
    try {
        const camOk = await startWebcam();
        if (!camOk) return;

        const res  = await fetch('/start', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await res.json();
        if (data.status === 'success') {
            detectionActive         = true;
            startBtn.disabled       = true;
            stopBtn.disabled        = false;
            downloadPdfBtn.disabled = true;
            exportBtn.disabled      = true;
            videoFeed.style.display = 'block';
            noVideo.style.display   = 'none';
            SoundManager.success();
            startStatsPolling();
            startFrameLoop();   // start sending frames
        } else { alert('Error: ' + data.message); }
    } catch (e) {
    stopWebcam();   // don't leave the camera running if /start failed
    alert('Failed to start detection. Please check your connection and try again.');
}
});

let frameLoopActive = false;
``
function startFrameLoop() {
    captureCanvas.width = 640;
    captureCanvas.height = 480;
    frameLoopActive = true;
    sendNextFrame();
}

// Stops the frame-sending loop immediately. Called the instant Stop is
// clicked (not after /stop resolves), so no stray frames get sent once
// the user has asked detection to stop.
function stopFrameLoop() {
    frameLoopActive = false;
}

async function sendNextFrame() {
    if (!frameLoopActive || !detectionActive) return;

    if (webcamVideo.readyState >= 2) {
        const ctx = captureCanvas.getContext('2d');
        ctx.drawImage(webcamVideo, 0, 0, 640, 480);
        const imageData = captureCanvas.toDataURL('image/jpeg', 0.7);

        try {
            const res = await fetch('/process_frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
            const data = await res.json();
            if (data.status === 'success') {
                videoFeed.src = data.image;
            }
        } catch (e) {
            console.error('Frame processing error:', e);
        }
    }

    // Only schedule the NEXT frame after this one is fully done
    if (frameLoopActive) {
        setTimeout(sendNextFrame, 150);
    }
}

// ── Stop ─────────────────────────────────────────────────
stopBtn.addEventListener('click', async () => {
    try {
        stopBtn.disabled = true;
        stopFrameLoop();   // stop sending frames immediately, before the /stop request even goes out
        stopWebcam();
        const userName = sessionStorage.getItem('ergovision-user') || 'Unknown';
        const res = await fetch('/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_name: userName }) });
        const data = await res.json();
        if (data.status === 'success') {
            detectionActive         = false;
            setTimeout(() => { startBtn.disabled = false; }, 500);
            downloadPdfBtn.disabled = false;
            exportBtn.disabled      = false;
            videoFeed.style.display = 'none';
            videoFeed.src           = '';
            noVideo.style.display   = 'block';
            stopStatsPolling();
            if (data.summary) { currentSessionId = data.summary.session_id; showSummary(data.summary); }
        } else { stopBtn.disabled = false; alert('Error: ' + data.message); }
    } catch (e) { stopBtn.disabled = false; alert('Failed to stop detection'); }
});

// ── Save settings ────────────────────────────────────────
saveSettingsBtn.addEventListener('click', async () => {
    const threshold = document.getElementById('postureThreshold').value;
    try {
        const res  = await fetch('/update_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bad_posture_threshold: parseInt(threshold) })
        });
        const data = await res.json();
        if (data.status === 'success') { SoundManager.success(); showToast('Settings saved ✓'); }
        else { alert('Error: ' + data.message); }
    } catch (e) { alert('Failed to save settings'); }
});

// ── PDF Download (prominent one-click button) ────────────
function triggerDownload(btn, originalText) {
    btn.disabled    = true;
    btn.textContent = '⏳ Generating PDF…';
    const url = currentSessionId ? `/export?session_id=${currentSessionId}` : '/export';
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => { btn.disabled = false; btn.textContent = originalText; }, 2500);
}

downloadPdfBtn.addEventListener('click',    () => triggerDownload(downloadPdfBtn,    '📥 Download PDF Report'));
downloadReportBtn.addEventListener('click', () => triggerDownload(downloadReportBtn, '📥 Download PDF Report'));

exportBtn.addEventListener('click', async () => {
    exportBtn.disabled    = true;
    exportBtn.textContent = '⏳ Generating…';
    await new Promise(r => setTimeout(r, 300));
    const url = currentSessionId ? `/export?session_id=${currentSessionId}` : '/export';
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => { exportBtn.disabled = false; exportBtn.textContent = '📄 Export Last Report'; }, 2500);
});

// ── Stats polling ────────────────────────────────────────
function startStatsPolling() { statsInterval = setInterval(updateStats, 1000); }
function stopStatsPolling()  { if (statsInterval) { clearInterval(statsInterval); statsInterval = null; } }

async function updateStats() {
    try {
        const res   = await fetch('/stats');
        const stats = await res.json();
        if (!res.ok) return;

        // Posture badge
        const postureEl       = document.getElementById('postureStatus');
        postureEl.textContent = stats.posture_status;
        postureEl.className   = 'status-value';
        if      (stats.posture_status === 'Good') postureEl.classList.add('status-good');
        else if (stats.posture_status === 'Bad')  postureEl.classList.add('status-bad');

        // Chart update
        if (stats.posture_status === 'Good' || stats.posture_status === 'Bad')
            PostureChart.push(stats.posture_status);

        // Numbers
        document.getElementById('headAngle').textContent       = stats.head_angle.toFixed(1) + '°';
        document.getElementById('goodPostureTime').textContent = stats.good_posture_time.toFixed(1) + 's';
        document.getElementById('badPostureTime').textContent  = stats.bad_posture_time.toFixed(1) + 's';
        document.getElementById('totalBlinks').textContent     = stats.total_blinks;
        document.getElementById('blinkRate').textContent       = stats.blink_rate.toFixed(1) + '/min';

        // Fatigue
        const fatigueEl       = document.getElementById('fatigueLevel');
        fatigueEl.textContent = stats.fatigue_level;
        fatigueEl.style.color = getFatigueColor(stats.fatigue_level);

        // Eye rule timer
        document.getElementById('eyeRuleMessage').textContent =
            !detectionActive ? 'Start a session to begin tracking' :
            stats.eye_rule_next > 0
                ? `Next break in ${Math.floor(stats.eye_rule_next / 60)}m ${Math.floor(stats.eye_rule_next % 60)}s`
                : 'Take a break now!';

        // Alerts + sounds
        const alertBox = document.getElementById('alertBox');
        const now      = Date.now();
        if (stats.bad_posture_alert) {
            alertBox.textContent   = '⚠️ BAD POSTURE ALERT! Adjust your position.';
            alertBox.className     = 'alert-box alert-posture';
            alertBox.style.display = 'block';
            if (now - lastPostureAlert > ALERT_COOLDOWN) {
                SoundManager.postureAlert();
                lastPostureAlert = now;
            }
        } else if (stats.eye_rule_alert) {
            alertBox.textContent   = '👁️ 20-20-20 Rule: Look at something 20 feet away!';
            alertBox.className     = 'alert-box alert-eye-rule';
            alertBox.style.display = 'block';
            if (now - lastEyeAlert > ALERT_COOLDOWN) {
                SoundManager.eyeRuleAlert();
                lastEyeAlert = now;
            }
        } else {
            alertBox.style.display = 'none';
        }
    } catch (e) { console.error('Stats error:', e); }
}

function getFatigueColor(level) {
    if (level === 'Eye Strain') return 'var(--warning)';
    if (level === 'Fatigued')   return 'var(--danger)';
    return 'var(--accent)';
}

// ── Session Summary Modal ────────────────────────────────
function showSummary(summary) {
    const posture  = summary.posture_data || {};
    const blink    = summary.blink_data   || {};
    const duration = summary.duration     || 0;
    const goodPct  = duration > 0 ? Math.round((posture.good_time || 0) / duration * 100) : 0;
    document.getElementById('summaryContent').innerHTML = `
        <p><strong>Session Duration</strong>  <span>${duration.toFixed(1)}s</span></p>
        <p><strong>Good Posture Time</strong> <span>${(posture.good_time||0).toFixed(1)}s (${goodPct}%)</span></p>
        <p><strong>Bad Posture Time</strong>  <span>${(posture.bad_time||0).toFixed(1)}s</span></p>
        <p><strong>Total Blinks</strong>      <span>${blink.total_blinks||0}</span></p>
        <p><strong>Blink Rate</strong>        <span>${(blink.blink_rate||0).toFixed(1)} /min</span></p>
        <p><strong>Fatigue Level</strong>     <span>${blink.fatigue_level||'Normal'}</span></p>`;
    modal.style.display = 'block';
}

closeModal.addEventListener('click', () => { modal.style.display = 'none'; });
window.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

// ── Toast ─────────────────────────────────────────────────
function showToast(message) {
    let t = document.getElementById('ergoToast');
    if (!t) { t = document.createElement('div'); t.id = 'ergoToast'; document.body.appendChild(t); }
    t.textContent = message;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2800);
}

window.addEventListener('resize', () => PostureChart.draw());