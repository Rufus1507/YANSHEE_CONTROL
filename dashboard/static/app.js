// ═══════════════════════════════════════════════════════════════
//  YANSHEE AI — Futuristic Dashboard & Control Center App JS
// ═══════════════════════════════════════════════════════════════

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
let ws;

const DOM = {
    // Mode Control Bar
    btnFace: document.getElementById('btn-face'),
    btnGesture: document.getElementById('btn-gesture'),
    btnAi: document.getElementById('btn-ai'),
    modeCurrentText: document.getElementById('mode-current-text'),
    modeSpinner: document.getElementById('mode-spinner'),
    btnShutdown: document.getElementById('btn-shutdown'),

    // Video & Camera
    videoFeed: document.getElementById('video-feed'),
    overlay: document.getElementById('vision-overlay'),
    fpsVal: document.getElementById('fps-val'),
    camFpsTop: document.getElementById('cam-fps-top'),
    sysCamFps: document.getElementById('sys-cam-fps'),
    sysUptimeTop: document.getElementById('sys-uptime-top'),
    sysLatency: document.getElementById('sys-latency'),
    sysRobotState: document.getElementById('sys-robot-state'),
    camLiveIndicator: document.getElementById('cam-live-indicator'),
    camModeBadge: document.getElementById('cam-mode-badge'),
    camSubBadge: document.getElementById('cam-sub-badge'),
    
    // Status Header
    lightCam: document.getElementById('light-cam'),
    camText: document.getElementById('cam-text'),
    lightApi: document.getElementById('light-api'),
    apiText: document.getElementById('api-text'),
    lightRobot: document.getElementById('light-robot'),
    robotText: document.getElementById('robot-text'),
    lightVoice: document.getElementById('light-voice'),
    voiceText: document.getElementById('voice-text'),
    robotDirectBadge: document.getElementById('robot-direct-badge'),
    
    // User Card
    userName: document.getElementById('user-name'),
    userRole: document.getElementById('user-role'),
    userConf: document.getElementById('user-conf'),
    confBar: document.getElementById('conf-bar'),
    avatarIcon: document.getElementById('avatar-icon'),
    avatarBox: document.getElementById('avatar-box'),
    userVerifiedBadge: document.getElementById('user-verified-badge'),
    userLivText: document.getElementById('user-liv-text'),
    
    // Liveness
    livTopBadge: document.getElementById('liv-top-badge'),
    livChallenge: document.getElementById('liv-challenge'),
    livConf: document.getElementById('liv-conf'),
    livDot: document.getElementById('liv-dot'),
    livStatus: document.getElementById('liv-status'),
    livSteps: document.getElementById('liveness-steps'),

    // Voice & TTS & Memory
    voiceIndicator: document.getElementById('voice-indicator'),
    voiceStatusText: document.getElementById('voice-status-text'),
    voiceLastCmd: document.getElementById('voice-last-cmd'),
    voiceLastText: document.getElementById('voice-last-text'),
    btnVoiceToggle: document.getElementById('btn-voice-toggle'),
    ttsInput: document.getElementById('tts-input'),
    ttsSendBtn: document.getElementById('tts-send-btn'),
    memoryMotionSelect: document.getElementById('memory-motion-select'),
    memoryKeywordInput: document.getElementById('memory-keyword-input'),

    // System Metrics
    circCpu: document.getElementById('circ-cpu'),
    circRam: document.getElementById('circ-ram'),
    circDisk: document.getElementById('circ-disk'),
    sysCpu: document.getElementById('sys-cpu'),
    sysRam: document.getElementById('sys-ram'),
    sysDisk: document.getElementById('sys-disk'),

    // Motion Progress
    motionCurrentName: document.getElementById('motion-current-name'),
    motionProgressFill: document.getElementById('motion-progress-fill'),
    motionPct: document.getElementById('motion-pct'),
    motionPrev: document.getElementById('motion-prev'),
    motionNext: document.getElementById('motion-next'),

    // Action Queue
    aqSizeTop: document.getElementById('aq-size-top'),
    aqList: document.getElementById('aq-list'),

    // Log Stream
    logStream: document.getElementById('log-stream')
};

const ctx = DOM.overlay ? DOM.overlay.getContext('2d') : null;

let currentSystemMode = 'face';
let currentBBox = null;
let isTrackingActive = false;
let currentLabel = 'Đang nhận diện...';
let currentStatus = 'RECOGNIZING';

let livenessChallenges = [];
let motionTimeout = null;
let lastMotion = 'None';
let queuedActions = [];
let isModeSwitching = false;

// ─── Dọn dẹp sạch sẽ toàn bộ trạng thái khuôn mặt (không để sót tàn dư) ─
function clearFaceVisionUI() {
    currentBBox = null;
    isTrackingActive = false;
    currentLabel = '';
    currentStatus = 'WAITING';
    livenessChallenges = [];

    // Xóa sạch canvas overlay
    if (DOM.overlay && ctx) {
        ctx.clearRect(0, 0, DOM.overlay.width, DOM.overlay.height);
    }

    // Đưa User Card về trạng thái sạch sẽ
    if (DOM.userName) DOM.userName.textContent = '--';
    if (DOM.userRole) DOM.userRole.textContent = 'ID: --';
    if (DOM.userConf) DOM.userConf.textContent = '--';
    if (DOM.confBar) DOM.confBar.style.width = '0%';
    if (DOM.avatarIcon) DOM.avatarIcon.textContent = '?';
    if (DOM.avatarBox) {
        DOM.avatarBox.style.borderColor = 'var(--panel-border)';
        DOM.avatarBox.style.color = 'var(--text-muted)';
    }
    if (DOM.userVerifiedBadge) {
        DOM.userVerifiedBadge.className = 'badge badge-outline';
        DOM.userVerifiedBadge.textContent = 'WAITING';
        DOM.userVerifiedBadge.style.color = 'var(--text-muted)';
        DOM.userVerifiedBadge.style.borderColor = 'var(--panel-border)';
    }
    if (DOM.userLivText) {
        DOM.userLivText.textContent = '--';
        DOM.userLivText.style.color = 'var(--text-muted)';
    }
    updateLivenessUI('--', '--', 'WAITING', '', '#8f9baf');
}

// ─── Canvas Overlay ────────────────────────────────────────────
function drawCornerBox(x, y, w, h, color) {
    if (!ctx) return;
    const cl = Math.min(w, h) * 0.15;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.moveTo(x, y+cl); ctx.lineTo(x, y); ctx.lineTo(x+cl, y);
    ctx.moveTo(x+w-cl, y); ctx.lineTo(x+w, y); ctx.lineTo(x+w, y+cl);
    ctx.moveTo(x+w, y+h-cl); ctx.lineTo(x+w, y+h); ctx.lineTo(x+w-cl, y+h);
    ctx.moveTo(x+cl, y+h); ctx.lineTo(x, y+h); ctx.lineTo(x, y+h-cl);
    ctx.stroke();
    ctx.shadowBlur = 0;
}

function renderCanvas() {
    if (!DOM.overlay || !DOM.videoFeed || !ctx) return;
    const w = DOM.videoFeed.naturalWidth || DOM.videoFeed.clientWidth;
    const h = DOM.videoFeed.naturalHeight || DOM.videoFeed.clientHeight;
    
    if (w > 0) {
        DOM.overlay.width = w;
        DOM.overlay.height = h;
        ctx.clearRect(0, 0, w, h);
        
        // CHỈ VẼ KHUNG NHẬN DIỆN NẾU ĐANG Ở CHẾ ĐỘ FACE!
        // Nếu ở Gesture hay AI mode, canvas luôn trong suốt 100%, không bị sót khung cũ!
        if (currentSystemMode === 'face' && currentBBox && isTrackingActive) {
            let [bx, by, bw, bh] = currentBBox;
            bx = w - bx - bw; // Mirror horizontally

            let color = '#00e676';
            if (currentStatus === 'STRANGER' || currentStatus === 'Khách Lạ') color = '#ff3333';
            else if (currentStatus === 'VERIFIED') color = '#00b0ff';
            else if (currentStatus === 'LIVENESS_CHECK') color = '#ff9100';
            else if (currentStatus === 'FAILED') color = '#ff3333';
            
            drawCornerBox(bx, by, bw, bh, color);
            
            const label = currentLabel || 'Đang nhận diện...';
            ctx.font = 'bold 12px "JetBrains Mono", monospace';
            const textW = ctx.measureText(label).width;
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.fillRect(bx + (bw - textW)/2 - 10, by - 25, textW + 20, 22);
            ctx.fillStyle = color;
            ctx.fillText(label, bx + (bw - textW)/2, by - 10);
        }
    }
    requestAnimationFrame(renderCanvas);
}

// ─── Logging System ────────────────────────────────────────────
function addLog(category, text, catIcon = 'ℹ️') {
    if (!DOM.logStream) return;
    const entry = document.createElement('div');
    entry.className = 'log-row';
    
    let dotClass = 'log-dot';
    if (category === 'Face') dotClass += ' face';
    else if (category === 'User') dotClass += ' user';
    else if (category === 'Voice' || category === 'Intent' || category === 'Motion' || category === 'AI') dotClass += ' voice';
    else if (category === 'Error' || category === 'Cảnh báo') dotClass += ' error';

    const t = new Date().toLocaleTimeString('vi-VN', {hour12:false});
    
    entry.innerHTML = `
        <div class="${dotClass}"></div>
        <div class="log-time">${t}</div>
        <div class="log-cat"><span class="icon">${catIcon}</span> ${category}</div>
        <div class="log-msg">${text}</div>
    `;
    
    DOM.logStream.appendChild(entry);
    DOM.logStream.scrollTop = DOM.logStream.scrollHeight;
    if (DOM.logStream.children.length > 60) DOM.logStream.removeChild(DOM.logStream.firstChild);
}

function clearLogs() {
    if (DOM.logStream) {
        DOM.logStream.innerHTML = '';
        addLog('Hệ thống', 'Đã xóa nhật ký sự kiện', '🧹');
    }
}

// ─── Helpers ───────────────────────────────────────────
function updateLivenessUI(challenge, conf, status, colorClass, dotColor) {
    if(DOM.livChallenge) DOM.livChallenge.textContent = challenge;
    if(DOM.livConf) DOM.livConf.textContent = conf;
    if(DOM.livStatus) DOM.livStatus.textContent = status;
    if(DOM.livDot) DOM.livDot.style.backgroundColor = dotColor;
    if(DOM.livTopBadge) {
        DOM.livTopBadge.className = 'badge badge-solid';
        DOM.livTopBadge.style.background = `rgba(${dotColor==='#00e676'?'0,230,118':(dotColor==='#ff3333'?'255,51,51':'255,145,0')}, 0.15)`;
        DOM.livTopBadge.style.color = dotColor;
        DOM.livTopBadge.textContent = status.toUpperCase();
    }
}

function renderActionQueue(current, size) {
    if (!DOM.aqSizeTop || !DOM.aqList) return;
    DOM.aqSizeTop.textContent = size;
    DOM.aqList.innerHTML = '';
    
    if (!current && size === 0) {
        DOM.aqList.innerHTML = '<div class="aq-placeholder">Hàng đợi trống</div>';
        return;
    }

    if (current) {
        DOM.aqList.innerHTML += `
            <div class="aq-item">
                <div class="aq-item-icon">🏃</div>
                <div class="aq-item-info">
                    <span class="aq-item-name">${current}</span>
                    <span class="aq-item-status">Đang thực thi</span>
                </div>
                <div class="aq-item-right text-blue">
                    <div class="loader"></div>
                </div>
            </div>
        `;
    }

    for (let i = 0; i < size; i++) {
        let name = queuedActions[i] || `Action #${i+1}`;
        DOM.aqList.innerHTML += `
            <div class="aq-item">
                <div class="aq-item-icon" style="background: rgba(255,255,255,0.05); color: #8f9baf;">⏳</div>
                <div class="aq-item-info">
                    <span class="aq-item-name" style="color: #8f9baf;">${name}</span>
                    <span class="aq-item-status queued">Chờ trong hàng đợi</span>
                </div>
            </div>
        `;
    }
}

function startMotionProgress(motionName) {
    if (!DOM.motionCurrentName || !DOM.motionProgressFill) return;
    DOM.motionPrev.textContent = lastMotion;
    lastMotion = DOM.motionCurrentName.textContent !== 'IDLE' ? DOM.motionCurrentName.textContent : motionName;
    DOM.motionCurrentName.textContent = motionName;
    
    let pct = 0;
    DOM.motionProgressFill.style.width = '0%';
    DOM.motionPct.textContent = '0%';
    DOM.motionProgressFill.style.background = 'var(--accent-blue)';
    
    if(motionTimeout) clearInterval(motionTimeout);
    motionTimeout = setInterval(() => {
        pct += 5;
        if(pct >= 100) {
            pct = 100;
            clearInterval(motionTimeout);
            DOM.motionProgressFill.style.background = 'var(--accent-green)';
            setTimeout(() => {
                DOM.motionCurrentName.textContent = 'IDLE';
                DOM.motionProgressFill.style.width = '0%';
                DOM.motionPct.textContent = '0%';
                DOM.motionProgressFill.style.background = 'var(--accent-blue)';
            }, 1000);
        }
        DOM.motionProgressFill.style.width = pct + '%';
        DOM.motionPct.textContent = pct + '%';
    }, 100);
}

// ─── Mode Switching Logic ──────────────────────────────────────
function updateModeUI(mode, isTransitioning, targetMode = null) {
    isModeSwitching = isTransitioning;
    
    // Enable/disable buttons during transition
    const buttons = [DOM.btnFace, DOM.btnGesture, DOM.btnAi];
    buttons.forEach(btn => {
        if (btn) btn.disabled = isTransitioning;
    });

    if (DOM.modeSpinner) {
        DOM.modeSpinner.style.display = isTransitioning ? 'inline' : 'none';
        if (isTransitioning && targetMode) {
            DOM.modeSpinner.textContent = `⏳ Đang chuyển sang ${targetMode.toUpperCase()}...`;
        }
    }

    if (mode) {
        currentSystemMode = mode;
        clearFaceVisionUI(); // Dọn sạch tàn dư khung nhận diện và user card cũ

        const modeLabels = {
            'face': 'FACE RECOGNITION (1)',
            'gesture': 'GESTURE CONTROL (2)',
            'ai': 'GEMINI AI (3)',
            'idle': 'CHỜ (IDLE)'
        };
        if (DOM.modeCurrentText) {
            DOM.modeCurrentText.textContent = modeLabels[mode] || mode.toUpperCase();
        }

        // Active classes trên thanh nút
        if (DOM.btnFace) DOM.btnFace.classList.toggle('active', mode === 'face');
        if (DOM.btnGesture) DOM.btnGesture.classList.toggle('active', mode === 'gesture');
        if (DOM.btnAi) DOM.btnAi.classList.toggle('active', mode === 'ai');

        // Video feed & Badges handling
        if (mode === 'face') {
            // Chế độ Face: Dùng scaleX(-1) cho webcam thô, chữ vẽ bằng overlay bình thường
            if (DOM.videoFeed) DOM.videoFeed.classList.add('mirror');
            if (DOM.camLiveIndicator) {
                DOM.camLiveIndicator.textContent = 'LIVE (FACE)';
                DOM.camLiveIndicator.className = 'text-green';
            }
            if (DOM.camModeBadge) DOM.camModeBadge.innerHTML = '<span class="icon">👤</span> Face: ON';
            if (DOM.camSubBadge) DOM.camSubBadge.innerHTML = '<span class="icon">🧬</span> Liveness: ON';

        } else if (mode === 'gesture') {
            // Chế độ Gesture: KHÔNG dùng scaleX(-1) vì cam_control đã lật frame và ghi chữ tiếng Việt!
            // Giúp toàn bộ chữ hiển thị đúng chiều đọc, không bị đảo ngược gương!
            if (DOM.videoFeed) DOM.videoFeed.classList.remove('mirror');
            if (DOM.camLiveIndicator) {
                DOM.camLiveIndicator.textContent = 'GESTURE MODE';
                DOM.camLiveIndicator.className = 'text-blue';
            }
            if (DOM.camModeBadge) DOM.camModeBadge.innerHTML = '<span class="icon">🖐️</span> Gesture: ON';
            if (DOM.camSubBadge) DOM.camSubBadge.innerHTML = '<span class="icon">👤</span> Face: OFF';

            // Cập nhật thông tin sang Gesture
            if (DOM.userName) DOM.userName.textContent = 'CHẾ ĐỘ CỬ CHỈ';
            if (DOM.userRole) DOM.userRole.textContent = 'MediaPipe Tracking';
            if (DOM.avatarIcon) DOM.avatarIcon.textContent = '🖐️';
            if (DOM.avatarBox) {
                DOM.avatarBox.style.borderColor = 'var(--accent-blue)';
                DOM.avatarBox.style.color = 'var(--accent-blue)';
            }
            if (DOM.userVerifiedBadge) {
                DOM.userVerifiedBadge.className = 'badge badge-outline';
                DOM.userVerifiedBadge.textContent = 'GESTURE ACTIVE';
                DOM.userVerifiedBadge.style.color = 'var(--accent-blue)';
                DOM.userVerifiedBadge.style.borderColor = 'var(--accent-blue)';
            }
            updateLivenessUI('Theo dõi bàn tay & cử chỉ', 'ON', 'GESTURE', '', '#00b0ff');

        } else if (mode === 'ai') {
            if (DOM.videoFeed) DOM.videoFeed.classList.remove('mirror');
            if (DOM.camLiveIndicator) {
                DOM.camLiveIndicator.textContent = 'AI MODE';
                DOM.camLiveIndicator.className = 'text-muted';
            }
            if (DOM.camModeBadge) DOM.camModeBadge.innerHTML = '<span class="icon">🧠</span> Gemini AI: ON';
            if (DOM.camSubBadge) DOM.camSubBadge.innerHTML = '<span class="icon">📷</span> Cam: OFF';

            // Cập nhật thông tin sang AI
            if (DOM.userName) DOM.userName.textContent = 'GEMINI AI';
            if (DOM.userRole) DOM.userRole.textContent = 'Trợ lý giọng nói thông minh';
            if (DOM.avatarIcon) DOM.avatarIcon.textContent = '🧠';
            if (DOM.avatarBox) {
                DOM.avatarBox.style.borderColor = 'var(--accent-blue)';
                DOM.avatarBox.style.color = 'var(--accent-blue)';
            }
            if (DOM.userVerifiedBadge) {
                DOM.userVerifiedBadge.className = 'badge badge-outline';
                DOM.userVerifiedBadge.textContent = 'GEMINI ACTIVE';
                DOM.userVerifiedBadge.style.color = 'var(--accent-blue)';
                DOM.userVerifiedBadge.style.borderColor = 'var(--accent-blue)';
            }
            updateLivenessUI('Đàm thoại AI tự nhiên', 'ON', 'AI MODE', '', '#ab47bc');
        }
    }
}

async function switchMode(targetMode) {
    if (isModeSwitching) {
        addLog('Cảnh báo', 'Hệ thống đang chuyển chế độ. Vui lòng chờ...', '⏳');
        return;
    }

    addLog('Hệ thống', `Yêu cầu chuyển sang chế độ: ${targetMode.toUpperCase()}`, '🔄');
    updateModeUI(null, true, targetMode);

    try {
        const resp = await fetch('/api/mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode: targetMode})
        });
        const data = await resp.json();
        if (data.success) {
            updateModeUI(data.mode, false);
            addLog('Hệ thống', `Chuyển thành công sang ${data.mode.toUpperCase()}`, '✅');
        } else {
            updateModeUI(null, false);
            addLog('Error', `Lỗi chuyển chế độ: ${data.error}`, '❌');
            alert(`Lỗi chuyển chế độ: ${data.error}`);
        }
    } catch (err) {
        updateModeUI(null, false);
        addLog('Error', `Không thể kết nối API chuyển chế độ: ${err.message}`, '❌');
    }
}

function confirmShutdown() {
    if (confirm("⚠️ BẠN CÓ CHẮC CHẮN MUỐN DỪNG TOÀN BỘ HỆ THỐNG YANSHEE AI?\n\nTất cả luồng Camera, Voice, Robot và Server sẽ được tắt an toàn.")) {
        shutdownSystem();
    }
}

async function shutdownSystem() {
    addLog('Hệ thống', 'Đang gửi yêu cầu dừng toàn bộ hệ thống...', '🛑');
    if (DOM.btnShutdown) DOM.btnShutdown.disabled = true;

    try {
        const resp = await fetch('/api/shutdown', {method: 'POST'});
        const data = await resp.json();
        addLog('Hệ thống', 'Lệnh Shutdown đã được xác nhận. Hệ thống đang tắt...', '🛑');
        alert("Hệ thống đã nhận lệnh Shutdown và đang dừng toàn bộ dịch vụ an toàn.");
    } catch (err) {
        addLog('Error', `Lỗi khi gọi shutdown: ${err.message}`, '❌');
    }
}

// ─── Robot Direct Motion Controls ──────────────────────────────
async function sendRobotMotion(motion) {
    addLog('Motion', `Gửi lệnh cử động: ${motion}`, '🎮');
    try {
        const resp = await fetch('/api/robot/motion', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({motion: motion})
        });
        const data = await resp.json();
        if (data.success) {
            addLog('Motion', `✅ ${data.message}`, '🏃');
            startMotionProgress(motion);
        } else {
            addLog('Error', `❌ Không thể thực thi cử động: ${data.error}`, '⚠️');
        }
    } catch (err) {
        addLog('Error', `Lỗi gửi lệnh robot: ${err.message}`, '❌');
    }
}

// ─── Voice & TTS Controls ──────────────────────────────────────
async function toggleVoice() {
    try {
        const resp = await fetch('/api/voice/toggle', {method: 'POST'});
        const data = await resp.json();
        if (data.success) {
            const stateStr = data.running ? 'BẬT' : 'TẮT';
            addLog('Voice', `Đã ${stateStr} lắng nghe giọng nói`, '🎙️');
        } else {
            addLog('Error', `Lỗi: ${data.error}`, '❌');
        }
    } catch (err) {
        addLog('Error', `Lỗi toggle voice: ${err.message}`, '❌');
    }
}

async function sendTTS() {
    if (!DOM.ttsInput) return;
    const text = DOM.ttsInput.value.trim();
    if (!text) return;

    addLog('Voice', `Yêu cầu phát TTS: "${text}"`, '🔊');
    try {
        const resp = await fetch('/api/tts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text})
        });
        const data = await resp.json();
        if (data.success) {
            DOM.ttsInput.value = '';
            addLog('Voice', `Đang phát âm: "${text}"`, '✅');
        } else {
            addLog('Error', `Lỗi TTS: ${data.error}`, '❌');
        }
    } catch (err) {
        addLog('Error', `Lỗi gửi TTS: ${err.message}`, '❌');
    }
}

// ─── Smart Memory Controls ─────────────────────────────────────
async function learnKeyword() {
    if (!DOM.memoryMotionSelect || !DOM.memoryKeywordInput) return;
    const motion = DOM.memoryMotionSelect.value;
    const keyword = DOM.memoryKeywordInput.value.trim();

    if (!keyword) {
        alert("Vui lòng nhập từ khóa mới!");
        return;
    }

    addLog('Hệ thống', `Đang dạy từ khóa mới: "${keyword}" → ${motion}`, '🧠');
    try {
        const resp = await fetch('/api/memory/learn', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({motion: motion, keyword: keyword})
        });
        const data = await resp.json();
        if (data.success) {
            addLog('Hệ thống', `✅ Robot đã học thành công: "${keyword}" → ${motion}`, '🎉');
            DOM.memoryKeywordInput.value = '';
        } else {
            addLog('Error', `Lỗi học từ khóa: ${data.error}`, '❌');
        }
    } catch (err) {
        addLog('Error', `Lỗi API memory: ${err.message}`, '❌');
    }
}

// ─── Initial Status Fetch ──────────────────────────────────────
async function fetchInitialStatus() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        if (data.mode) {
            updateModeUI(data.mode, data.transitioning);
        }
        if (DOM.lightCam && DOM.camText) {
            if (data.camera_running || data.mode === 'face' || data.mode === 'gesture') {
                DOM.lightCam.className = 'status-dot on';
                DOM.camText.textContent = 'Live';
            } else {
                DOM.lightCam.className = 'status-dot';
                DOM.camText.textContent = 'Offline';
            }
        }
        if (DOM.lightApi && DOM.apiText) {
            DOM.lightApi.className = 'status-dot on';
            DOM.apiText.textContent = 'Live';
        }
        if (DOM.lightVoice && DOM.voiceText) {
            if (data.voice_running) {
                DOM.lightVoice.className = 'status-dot on';
                DOM.voiceText.textContent = 'Đang nghe';
            } else {
                DOM.lightVoice.className = 'status-dot';
                DOM.voiceText.textContent = 'Tắt';
            }
        }
        if (DOM.robotText && DOM.sysRobotState) {
            const rStat = data.robot_connected ? 'Connected' : 'Offline';
            DOM.robotText.textContent = rStat;
            DOM.sysRobotState.textContent = rStat;
            if (DOM.lightRobot) DOM.lightRobot.className = data.robot_connected ? 'status-dot on' : 'status-dot';
        }
    } catch (err) {
        console.warn('Initial status fetch failed:', err);
    }
}

// ─── Event Handling ────────────────────────────────────────────
function handleEvent(type, payload) {
    switch (type) {
        // Mode switching events
        case 'MODE_CHANGING':
            updateModeUI(null, true, payload.to);
            addLog('Hệ thống', `Đang chuyển chế độ: ${payload.from} → ${payload.to}`, '⏳');
            break;
        case 'MODE_CHANGED':
            updateModeUI(payload.mode, false);
            addLog('Hệ thống', `Chế độ hiện tại: ${payload.mode.toUpperCase()}`, '✅');
            break;
        case 'MODE_ERROR':
            updateModeUI(null, false);
            addLog('Cảnh báo', `Lỗi chuyển chế độ: ${payload.error}`, '❌');
            break;

        // Camera & Frame
        case 'FRAME_READY':
            if (DOM.lightCam) DOM.lightCam.className = 'status-dot on';
            if (DOM.camText) DOM.camText.textContent = 'Live';
            const fps = Math.round(payload.fps || 0);
            if (DOM.fpsVal) DOM.fpsVal.textContent = fps;
            if (DOM.camFpsTop) DOM.camFpsTop.textContent = fps;
            if (DOM.sysCamFps) DOM.sysCamFps.textContent = fps;
            if (DOM.sysLatency && payload.latency_ms !== undefined) {
                DOM.sysLatency.textContent = `${Math.round(payload.latency_ms)} ms`;
            }
            break;

        case 'FACE_DETECTED':
            if (currentSystemMode !== 'face') return; // Không hiển thị nếu không ở chế độ Face
            currentBBox = payload.bbox;
            currentStatus = payload.status || 'RECOGNIZING';
            currentLabel = payload.label || 'Đang nhận diện...';
            isTrackingActive = true;
            if (!DOM.userName.textContent || DOM.userName.textContent === '--') {
                updateLivenessUI('Đang nhận diện...', '--', 'PROCESSING', '', '#8f9baf');
            }
            break;

        case 'FACE_LOST':
            if (currentSystemMode === 'face') {
                clearFaceVisionUI();
            }
            break;

        case 'USER_RECOGNIZED':
        case 'USER_VERIFIED': {
            if (currentSystemMode !== 'face') return;
            const conf = payload.confidence || 0;
            if (DOM.userName) DOM.userName.textContent = payload.full_name;
            if (DOM.userRole) DOM.userRole.textContent = payload.role;
            if (DOM.userConf) DOM.userConf.textContent = conf.toFixed(1) + '%';
            if (DOM.confBar) DOM.confBar.style.width = conf + '%';
            if (DOM.avatarIcon) DOM.avatarIcon.textContent = '👤';
            if (DOM.avatarBox) {
                DOM.avatarBox.style.borderColor = 'var(--accent-blue)';
                DOM.avatarBox.style.color = 'var(--accent-blue)';
            }
            if (DOM.userVerifiedBadge) {
                DOM.userVerifiedBadge.className = 'badge badge-outline badge-green';
                DOM.userVerifiedBadge.textContent = '✔ VERIFIED';
                DOM.userVerifiedBadge.style.color = 'var(--accent-blue)';
                DOM.userVerifiedBadge.style.borderColor = 'var(--accent-blue)';
            }
            currentLabel = payload.full_name;
            currentStatus = 'VERIFIED';
            addLog('Face', `Xác thực thành công: ${payload.full_name} (${conf.toFixed(1)}%)`, '👤');
            break;
        }

        case 'UNKNOWN_USER': {
            if (currentSystemMode !== 'face') return;
            const strangerLabel = payload.label || 'Khách Lạ';
            if (DOM.userName) DOM.userName.textContent = strangerLabel;
            if (DOM.userRole) DOM.userRole.textContent = 'CHƯA ĐĂNG KÝ';
            if (DOM.userConf) DOM.userConf.textContent = (payload.best_score ? (payload.best_score * 100).toFixed(1) : '0') + '%';
            if (DOM.confBar) DOM.confBar.style.width = (payload.best_score ? payload.best_score * 100 : 0) + '%';
            if (DOM.avatarIcon) DOM.avatarIcon.textContent = '⚠️';
            if (DOM.avatarBox) {
                DOM.avatarBox.style.borderColor = 'var(--accent-red)';
                DOM.avatarBox.style.color = 'var(--accent-red)';
            }
            if (DOM.userVerifiedBadge) {
                DOM.userVerifiedBadge.className = 'badge badge-outline';
                DOM.userVerifiedBadge.textContent = 'UNKNOWN';
                DOM.userVerifiedBadge.style.color = 'var(--accent-red)';
                DOM.userVerifiedBadge.style.borderColor = 'var(--accent-red)';
            }
            currentLabel = strangerLabel;
            currentStatus = 'STRANGER';
            addLog('Cảnh báo', `Phát hiện: ${strangerLabel}`, '⚠️');
            break;
        }

        case 'LIVENESS_STARTED':
            if (currentSystemMode !== 'face') return;
            livenessChallenges = payload.challenges || [];
            updateLivenessUI('Bắt đầu thử thách', '--', 'PROCESSING', '', '#ff9100');
            break;

        case 'LIVENESS_PROGRESS':
            if (currentSystemMode !== 'face') return;
            updateLivenessUI(payload.current_challenge, '--', 'PROCESSING', '', '#ff9100');
            break;

        case 'LIVENESS_PASSED':
            if (currentSystemMode !== 'face') return;
            updateLivenessUI('Vượt qua thử thách', 'PASS', 'PASS', '', '#00e676');
            if (DOM.userLivText) {
                DOM.userLivText.textContent = '✔ PASS';
                DOM.userLivText.style.color = 'var(--accent-green)';
            }
            addLog('User', `Đã vượt qua kiểm tra chống giả mạo`, '✅');
            break;

        case 'LIVENESS_FAILED':
            if (currentSystemMode !== 'face') return;
            updateLivenessUI(payload.reason || 'Thất bại', '--', 'FAIL', '', '#ff3333');
            if (DOM.userLivText) {
                DOM.userLivText.textContent = '✖ FAIL';
                DOM.userLivText.style.color = 'var(--accent-red)';
            }
            addLog('Cảnh báo', `Chống giả mạo thất bại: ${payload.reason}`, '❌');
            break;

        case 'CAMERA_STATUS':
        case 'CAMERA_CONNECTED':
        case 'CAMERA_RECONNECTING':
        case 'CAMERA_ERROR':
        case 'CAMERA_DISCONNECTED':
        case 'CAMERA_STOPPED': {
            const rawStat = (payload && payload.status) ? payload.status.toUpperCase() : type.replace('CAMERA_', '');
            if (rawStat === 'CONNECTED' || rawStat === 'ONLINE' || rawStat === 'READY') {
                if (DOM.lightCam) DOM.lightCam.className = 'status-dot on';
                if (DOM.camText) DOM.camText.textContent = 'Live';
                if (type === 'CAMERA_CONNECTED') addLog('Camera', 'Nguồn camera ổn định', '📷');
            } else if (rawStat === 'RECONNECTING') {
                if (DOM.lightCam) DOM.lightCam.className = 'status-dot warn';
                if (DOM.camText) DOM.camText.textContent = 'Reconnecting';
            } else {
                if (DOM.lightCam) DOM.lightCam.className = 'status-dot';
                if (DOM.camText) DOM.camText.textContent = 'Offline';
            }
            break;
        }

        case 'ROBOT_STATUS': {
            const botStat = (payload.status || 'offline').toUpperCase();
            if (['READY', 'ONLINE', 'CONNECTED'].includes(botStat)) {
                if (DOM.lightRobot) DOM.lightRobot.className = 'status-dot on';
            } else if (botStat !== 'OFFLINE') {
                if (DOM.lightRobot) DOM.lightRobot.className = 'status-dot blue';
            } else {
                if (DOM.lightRobot) DOM.lightRobot.className = 'status-dot';
            }
            const formatted = botStat.split('_').map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');
            if (DOM.robotText) DOM.robotText.textContent = formatted;
            if (DOM.sysRobotState) DOM.sysRobotState.textContent = formatted;
            if (DOM.robotDirectBadge) DOM.robotDirectBadge.textContent = formatted;
            break;
        }

        // Voice Control 
        case 'VOICE_STATUS': {
            const vStat = (payload.status || 'stopped').toLowerCase();
            if (vStat === 'ready' || vStat === 'started' || vStat === 'listening') {
                if (DOM.lightVoice) DOM.lightVoice.className = 'status-dot on';
                if (DOM.voiceText) DOM.voiceText.textContent = vStat === 'listening' ? 'Đang nghe' : 'Sẵn sàng';
                if (DOM.voiceIndicator) DOM.voiceIndicator.textContent = '🎤';
                if (DOM.voiceStatusText) DOM.voiceStatusText.textContent = 'Đang lắng nghe...';
            } else {
                if (DOM.lightVoice) DOM.lightVoice.className = 'status-dot';
                if (DOM.voiceText) DOM.voiceText.textContent = 'Tắt';
                if (DOM.voiceIndicator) DOM.voiceIndicator.textContent = '⏸️';
                if (DOM.voiceStatusText) DOM.voiceStatusText.textContent = 'Tắt';
            }
            break;
        }
        case 'VOICE_RECOGNIZED':
            if (DOM.voiceLastText) DOM.voiceLastText.textContent = `"${payload.text}"`;
            break;
        case 'VOICE_COMMAND':
            if (DOM.voiceLastCmd) DOM.voiceLastCmd.textContent = payload.motion;
            if (DOM.voiceStatusText) DOM.voiceStatusText.textContent = 'Đang thực thi...';
            addLog('Voice', `Đã nhận lệnh: "${payload.raw_text}"`, '🎤');
            addLog('Intent', `Ánh xạ cử động: ${payload.motion}`, '🧠');
            startMotionProgress(payload.motion);
            break;

        case 'TTS_STARTED':
            addLog('Voice', `Phát TTS: "${payload.text}"`, '🔊');
            break;
        case 'TTS_FINISHED':
            addLog('Voice', `Hoàn tất phát TTS`, '✅');
            break;

        // Action Queue
        case 'ACTION_QUEUE_UPDATE':
            renderActionQueue(payload.current, payload.queue_size || 0);
            break;
        case 'ACTION_EXECUTING':
            renderActionQueue(payload.name, DOM.aqSizeTop ? DOM.aqSizeTop.textContent : 0);
            addLog('Motion', `Thực thi: ${payload.name}`, '🏃');
            startMotionProgress(payload.name);
            break;
        case 'ACTION_COMPLETED':
            renderActionQueue(null, DOM.aqSizeTop ? DOM.aqSizeTop.textContent : 0);
            addLog('Motion', `Hoàn thành cử động`, '✅');
            break;

        // Gesture
        case 'GESTURE_STATUS':
            addLog('Gesture', `Trạng thái Gesture: ${payload.status}`, '🖐️');
            break;
        case 'GESTURE_COMMAND':
            addLog('Gesture', `Nhận cử chỉ: ${payload.action}`, '🖐️');
            break;

        // Gemini AI
        case 'GEMINI_AI_STATUS':
            addLog('AI', `Gemini AI: ${payload.status}`, '🧠');
            break;
        case 'GEMINI_AI_REPLY':
            addLog('AI', `Phản hồi: "${payload.text}"`, '💬');
            break;

        // System Metrics
        case 'SYSTEM_METRICS':
            if(payload.cpu && DOM.sysCpu && DOM.circCpu) {
                DOM.sysCpu.textContent = payload.cpu.percent + '%';
                DOM.circCpu.style.setProperty('--val', (payload.cpu.percent * 3.6) + 'deg');
            }
            if(payload.memory && DOM.sysRam && DOM.circRam) {
                DOM.sysRam.textContent = payload.memory.percent + '%';
                DOM.circRam.style.setProperty('--val', (payload.memory.percent * 3.6) + 'deg');
            }
            if(payload.disk && DOM.sysDisk && DOM.circDisk && payload.disk.percent !== undefined) {
                DOM.sysDisk.textContent = payload.disk.percent + '%';
                DOM.circDisk.style.setProperty('--val', (payload.disk.percent * 3.6) + 'deg');
            }
            if(payload.uptime_seconds !== undefined && DOM.sysUptimeTop) {
                const s = Math.floor(payload.uptime_seconds);
                const up = s > 3600 ? `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m` : (s > 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`);
                DOM.sysUptimeTop.textContent = up;
            }
            break;
    }
}

// ─── WebSocket Connection ──────────────────────────────────────
function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
        if (DOM.lightApi) DOM.lightApi.className = 'status-dot on';
        if (DOM.apiText) DOM.apiText.textContent = 'Live';
        addLog('Hệ thống', 'Kết nối Data Stream thành công', '🔌');
        fetchInitialStatus();
    };
    ws.onclose = () => {
        if (DOM.lightApi) DOM.lightApi.className = 'status-dot';
        if (DOM.apiText) DOM.apiText.textContent = 'Offline';
        addLog('Cảnh báo', 'Mất kết nối Stream. Đang kết nối lại...', '❌');
        setTimeout(connect, 2000);
    };
    ws.onmessage = (e) => {
        try {
            const { type, payload } = JSON.parse(e.data);
            if (type !== 'ping') handleEvent(type, payload);
        } catch(err){}
    };
}

// ─── Boot System ───────────────────────────────────────────────
connect();
renderCanvas();
addLog('Hệ thống', 'YANSHEE AI CONTROL CENTER STARTED', '🚀');
