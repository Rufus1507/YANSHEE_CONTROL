// ═══════════════════════════════════════════════════════════════
//  YANSHEE AI — Futuristic Dashboard App JS
// ═══════════════════════════════════════════════════════════════

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
let ws;

const DOM = {
    videoFeed: document.getElementById('video-feed'),
    overlay: document.getElementById('vision-overlay'),
    fpsVal: document.getElementById('fps-val'),
    camFpsTop: document.getElementById('cam-fps-top'),
    sysCamFps: document.getElementById('sys-cam-fps'),
    sysUptimeTop: document.getElementById('sys-uptime-top'),
    
    lightCam: document.getElementById('light-cam'),
    camText: document.getElementById('cam-text'),
    lightApi: document.getElementById('light-api'),
    lightRobot: document.getElementById('light-robot'),
    robotText: document.getElementById('robot-text'),
    lightVoice: document.getElementById('light-voice'),
    voiceText: document.getElementById('voice-text'),
    
    userName: document.getElementById('user-name'),
    userRole: document.getElementById('user-role'),
    userConf: document.getElementById('user-conf'),
    confBar: document.getElementById('conf-bar'),
    avatarIcon: document.getElementById('avatar-icon'),
    avatarBox: document.getElementById('avatar-box'),
    userVerifiedBadge: document.getElementById('user-verified-badge'),
    userLivText: document.getElementById('user-liv-text'),
    
    livTopBadge: document.getElementById('liv-top-badge'),
    livChallenge: document.getElementById('liv-challenge'),
    livConf: document.getElementById('liv-conf'),
    livDot: document.getElementById('liv-dot'),
    livStatus: document.getElementById('liv-status'),
    livSteps: document.getElementById('liveness-steps'),

    // Voice & TTS
    voiceIndicator: document.getElementById('voice-indicator'),
    voiceStatusText: document.getElementById('voice-status-text'),
    voiceLastCmd: document.getElementById('voice-last-cmd'),
    voiceLastText: document.getElementById('voice-last-text'),
    voiceTopBadge: document.getElementById('voice-top-badge'),
    ttsInput: document.getElementById('tts-input'),
    ttsSendBtn: document.getElementById('tts-send-btn'),

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

    logStream: document.getElementById('log-stream')
};

const ctx = DOM.overlay.getContext('2d');

let currentBBox = null;
let isTrackingActive = false;
let currentLabel = 'Đang nhận diện...';
let currentStatus = 'RECOGNIZING';

let livenessInterval = null;
let livenessDeadline = 0;
let livenessChallenges = [];
let livenessCurrentIdx = 0;

let motionTimeout = null;
let lastMotion = 'None';
let queuedActions = [];

// ─── Canvas Overlay ────────────────────────────────────────────
function drawCornerBox(x, y, w, h, color) {
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
    const w = DOM.videoFeed.naturalWidth || DOM.videoFeed.clientWidth;
    const h = DOM.videoFeed.naturalHeight || DOM.videoFeed.clientHeight;
    
    if (w > 0) {
        DOM.overlay.width = w;
        DOM.overlay.height = h;
        ctx.clearRect(0, 0, w, h);
        
        if (currentBBox && isTrackingActive) {
            let [bx, by, bw, bh] = currentBBox;
            bx = w - bx - bw;

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
    const entry = document.createElement('div');
    entry.className = 'log-row';
    
    let dotClass = 'log-dot';
    if(category === 'Face') dotClass += ' face';
    else if(category === 'User') dotClass += ' user';
    else if(category === 'Voice' || category === 'Intent' || category === 'Motion') dotClass += ' voice';
    else if(category === 'Error' || category === 'Cảnh báo') dotClass += ' error';

    const t = new Date().toLocaleTimeString('vi-VN', {hour12:false});
    
    entry.innerHTML = `
        <div class="${dotClass}"></div>
        <div class="log-time">${t}</div>
        <div class="log-cat"><span class="icon">${catIcon}</span> ${category}</div>
        <div class="log-msg">${text}</div>
    `;
    
    DOM.logStream.appendChild(entry);
    DOM.logStream.scrollTop = DOM.logStream.scrollHeight;
    if(DOM.logStream.children.length > 50) DOM.logStream.removeChild(DOM.logStream.firstChild);
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
    DOM.motionPrev.textContent = lastMotion;
    lastMotion = DOM.motionCurrentName.textContent !== 'IDLE' ? DOM.motionCurrentName.textContent : motionName;
    DOM.motionCurrentName.textContent = motionName;
    
    // Simulate progress
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

// ─── Event Handling ────────────────────────────────────────────
function handleEvent(type, payload) {
    switch (type) {
        case 'FRAME_READY':
            const fps = Math.round(payload.fps);
            DOM.fpsVal.textContent = fps;
            DOM.camFpsTop.textContent = fps;
            DOM.sysCamFps.textContent = fps;
            break;

        case 'FACE_DETECTED':
            currentBBox = payload.bbox;
            currentStatus = payload.status || 'RECOGNIZING';
            currentLabel = payload.label || 'Đang nhận diện...';
            isTrackingActive = true;
            if(!DOM.userName.textContent || DOM.userName.textContent === '--') {
                updateLivenessUI('Đang chờ hệ thống', '--', 'WAITING', '', '#8f9baf');
            }
            break;

        case 'FACE_LOST':
            currentBBox = null;
            isTrackingActive = false;
            currentLabel = 'Đang nhận diện...';
            currentStatus = 'RECOGNIZING';
            
            DOM.userName.textContent = '--';
            DOM.userRole.textContent = 'ID: --';
            DOM.userConf.textContent = '--';
            DOM.confBar.style.width = '0%';
            DOM.avatarIcon.textContent = '?';
            DOM.avatarBox.style.borderColor = 'var(--panel-border)';
            DOM.avatarBox.style.color = 'var(--text-muted)';
            
            DOM.userVerifiedBadge.className = 'badge badge-outline';
            DOM.userVerifiedBadge.textContent = 'WAITING';
            DOM.userVerifiedBadge.style.color = 'var(--text-muted)';
            DOM.userVerifiedBadge.style.borderColor = 'var(--panel-border)';
            DOM.userLivText.textContent = '--';

            updateLivenessUI('--', '--', 'WAITING', '', '#8f9baf');
            break;

        case 'USER_RECOGNIZED':
        case 'USER_VERIFIED': {
            const conf = payload.confidence || 0;
            DOM.userName.textContent = payload.full_name;
            DOM.userRole.textContent = payload.role;
            DOM.userConf.textContent = conf.toFixed(1) + '%';
            DOM.confBar.style.width = conf + '%';
            
            DOM.avatarIcon.textContent = '👤'; // Could use image if available
            DOM.avatarBox.style.borderColor = 'var(--accent-blue)';
            DOM.avatarBox.style.color = 'var(--accent-blue)';
            
            DOM.userVerifiedBadge.className = 'badge badge-outline badge-green';
            DOM.userVerifiedBadge.textContent = '✔ VERIFIED';
            DOM.userVerifiedBadge.style.color = 'var(--accent-blue)';
            DOM.userVerifiedBadge.style.borderColor = 'var(--accent-blue)';

            currentLabel = payload.full_name;
            currentStatus = 'VERIFIED';
            addLog('Face', `Face detected → ${payload.full_name} (${conf.toFixed(1)}%)`, '👤');
            break;
        }

        case 'UNKNOWN_USER': {
            const strangerLabel = payload.label || 'Khách Lạ';
            DOM.userName.textContent = strangerLabel;
            DOM.userRole.textContent = 'CHƯA ĐĂNG KÝ';
            DOM.userConf.textContent = (payload.best_score ? (payload.best_score * 100).toFixed(1) : '0') + '%';
            DOM.confBar.style.width = (payload.best_score ? payload.best_score * 100 : 0) + '%';
            
            DOM.avatarIcon.textContent = '⚠️';
            DOM.avatarBox.style.borderColor = 'var(--accent-red)';
            DOM.avatarBox.style.color = 'var(--accent-red)';

            DOM.userVerifiedBadge.className = 'badge badge-outline';
            DOM.userVerifiedBadge.textContent = 'UNKNOWN';
            DOM.userVerifiedBadge.style.color = 'var(--accent-red)';
            DOM.userVerifiedBadge.style.borderColor = 'var(--accent-red)';

            currentLabel = strangerLabel;
            currentStatus = 'STRANGER';
            addLog('Cảnh báo', `Phát hiện ${strangerLabel}`, '⚠️');
            break;
        }

        case 'LIVENESS_STARTED':
            livenessChallenges = payload.challenges || [];
            updateLivenessUI('Bắt đầu kiểm tra', '--', 'PROCESSING', '', '#ff9100');
            break;

        case 'LIVENESS_PROGRESS':
            updateLivenessUI(payload.current_challenge, '--', 'PROCESSING', '', '#ff9100');
            break;

        case 'LIVENESS_PASSED':
            updateLivenessUI('Hoàn thành', '98.5%', 'PASS', '', '#00e676');
            DOM.userLivText.textContent = '✔ PASS';
            DOM.userLivText.style.color = 'var(--accent-green)';
            addLog('User', `User liveness verified`, '✅');
            break;

        case 'LIVENESS_FAILED':
            updateLivenessUI(payload.reason || 'Thất bại', '--', 'FAIL', '', '#ff3333');
            DOM.userLivText.textContent = '✖ FAIL';
            DOM.userLivText.style.color = 'var(--accent-red)';
            addLog('Cảnh báo', `Liveness failed: ${payload.reason}`, '❌');
            break;

        case 'CAMERA_STATUS':
        case 'CAMERA_CONNECTED':
        case 'CAMERA_RECONNECTING':
        case 'CAMERA_ERROR':
        case 'CAMERA_DISCONNECTED':
            const camStat = type.split('_')[1] || payload.status;
            if (camStat === 'CONNECTED' || camStat === 'ONLINE') {
                DOM.lightCam.className = 'status-dot on';
                DOM.camText.textContent = 'Live';
                if(type === 'CAMERA_CONNECTED') addLog('Camera', 'Camera ổn định', '📷');
            } else if (camStat === 'RECONNECTING') {
                DOM.lightCam.className = 'status-dot warn';
                DOM.camText.textContent = 'Reconnecting';
            } else {
                DOM.lightCam.className = 'status-dot';
                DOM.camText.textContent = 'Offline';
            }
            break;

        case 'ROBOT_STATUS':
            const botStat = (payload.status || 'offline').toUpperCase();
            if (['READY', 'ONLINE', 'CONNECTED'].includes(botStat)) {
                DOM.lightRobot.className = 'status-dot on';
            } else if (botStat !== 'OFFLINE') {
                DOM.lightRobot.className = 'status-dot blue'; // Processing
            } else {
                DOM.lightRobot.className = 'status-dot';
            }
            DOM.robotText.textContent = botStat.split('_').map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');
            break;

        // Voice Control 
        case 'VOICE_STATUS':
            const vStat = (payload.status || 'stopped').toLowerCase();
            if (vStat === 'ready') {
                DOM.lightVoice.className = 'status-dot on';
                DOM.voiceText.textContent = 'Sẵn sàng';
                DOM.voiceIndicator.textContent = '🎤';
                DOM.voiceStatusText.textContent = 'Đang chờ nghe lệnh...';
                DOM.voiceTopBadge.textContent = 'Sẵn sàng';
                DOM.voiceTopBadge.className = 'badge badge-outline badge-green';
            } else if (vStat === 'listening') {
                DOM.lightVoice.className = 'status-dot warn';
                DOM.voiceText.textContent = 'Listening';
                DOM.voiceIndicator.textContent = '👂';
                DOM.voiceStatusText.textContent = 'Đang nghe...';
                DOM.voiceTopBadge.textContent = 'Listening';
                DOM.voiceTopBadge.className = 'badge badge-solid';
                DOM.voiceTopBadge.style.background = 'rgba(255,145,0,0.15)';
                DOM.voiceTopBadge.style.color = '#ff9100';
            } else {
                DOM.lightVoice.className = 'status-dot';
                DOM.voiceText.textContent = 'Đã dừng';
                DOM.voiceIndicator.textContent = '⏸️';
                DOM.voiceStatusText.textContent = 'Dừng';
                DOM.voiceTopBadge.textContent = 'OFF';
                DOM.voiceTopBadge.className = 'badge badge-outline';
            }
            break;
        case 'VOICE_RECOGNIZED':
            DOM.voiceLastText.textContent = `"${payload.text}"`;
            break;
        case 'VOICE_COMMAND':
            DOM.voiceLastCmd.textContent = payload.motion;
            DOM.voiceStatusText.textContent = 'Đang thực thi...';
            addLog('Voice', `Đã nhận lệnh: "${payload.raw_text}"`, '🎤');
            addLog('Intent', `Intent recognized → ${payload.motion}`, '🧠');
            startMotionProgress(payload.motion);
            break;

        case 'TTS_STARTED':
            addLog('Voice', `Phát TTS: "${payload.text}"`, '🔊');
            break;

        case 'ACTION_QUEUE_UPDATE':
            renderActionQueue(payload.current, payload.queue_size || 0);
            break;
        case 'ACTION_EXECUTING':
            renderActionQueue(payload.name, DOM.aqSizeTop.textContent);
            addLog('Motion', `Motion started → ${payload.name}`, '🏃');
            startMotionProgress(payload.name);
            break;
        case 'ACTION_COMPLETED':
            renderActionQueue(null, DOM.aqSizeTop.textContent);
            addLog('Motion', `Motion completed`, '✅');
            break;

        case 'SYSTEM_METRICS':
            if(payload.cpu) {
                DOM.sysCpu.textContent = payload.cpu.percent + '%';
                DOM.circCpu.style.setProperty('--val', (payload.cpu.percent * 3.6) + 'deg');
            }
            if(payload.memory) {
                DOM.sysRam.textContent = payload.memory.percent + '%';
                DOM.circRam.style.setProperty('--val', (payload.memory.percent * 3.6) + 'deg');
            }
            if(payload.disk && payload.disk.percent !== undefined) {
                DOM.sysDisk.textContent = payload.disk.percent + '%';
                DOM.circDisk.style.setProperty('--val', (payload.disk.percent * 3.6) + 'deg');
            }
            if(payload.uptime_seconds !== undefined) {
                const s = Math.floor(payload.uptime_seconds);
                const up = s > 3600 ? `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m` : (s > 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`);
                DOM.sysUptimeTop.textContent = up;
            }
            break;
    }
}

// ─── WebSocket ─────────────────────────────────────────────────
function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
        DOM.lightApi.classList.add('on');
        addLog('Hệ thống', 'Kết nối Data Stream thành công', '🔌');
    };
    ws.onclose = () => {
        DOM.lightApi.classList.remove('on');
        addLog('Cảnh báo', 'Mất kết nối Stream. Đang thử lại...', '❌');
        setTimeout(connect, 2000);
    };
    ws.onmessage = (e) => {
        try {
            const { type, payload } = JSON.parse(e.data);
            if(type !== 'ping') handleEvent(type, payload);
        } catch(err){}
    };
}

// ─── Boot ──────────────────────────────────────────────────────
connect();
renderCanvas();
addLog('Hệ thống', 'YANSHEE AI SYSTEM STARTED', '🚀');
