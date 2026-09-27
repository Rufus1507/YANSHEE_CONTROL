// ═══════════════════════════════════════════════════════════════
//  YANSHEE FACE ID — Layout Fix App JS
// ═══════════════════════════════════════════════════════════════

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
let ws;

const DOM = {
    videoFeed: document.getElementById('video-feed'),
    overlay: document.getElementById('vision-overlay'),
    fpsVal: document.getElementById('fps-val'),
    
    lightCam: document.getElementById('light-cam'),
    camText: document.getElementById('cam-text'),
    lightApi: document.getElementById('light-api'),
    lightRobot: document.getElementById('light-robot'),
    robotText: document.getElementById('robot-text'),
    
    userName: document.getElementById('user-name'),
    userRole: document.getElementById('user-role'),
    userConf: document.getElementById('user-conf'),
    confBar: document.getElementById('conf-bar'),
    avatarIcon: document.getElementById('avatar-icon'),
    
    livTimer: document.getElementById('liveness-timer'),
    livSteps: document.getElementById('liveness-steps'),
    
    logStream: document.getElementById('log-stream')
};

const ctx = DOM.overlay.getContext('2d');

let currentBBox = null;
let currentTrackingId = null;
let isTrackingActive = false;
let currentLabel = 'Đang nhận diện...';
let currentStatus = 'RECOGNIZING';

let livenessInterval = null;
let livenessDeadline = 0;
let livenessChallenges = [];
let livenessCurrentIdx = 0;

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
            
            // Lật tọa độ X để khớp với video đã lật, do canvas đã bỏ lật CSS
            bx = w - bx - bw;

            // Màu theo trạng thái
            let color = '#00ff66';  // Xanh lá: đang nhận diện
            if (currentStatus === 'STRANGER' || currentStatus === 'Khách Lạ') {
                color = '#ff4444';  // Đỏ: khách lạ
            } else if (currentStatus === 'VERIFIED') {
                color = '#00d4ff';  // Xanh dương: đã xác minh
            } else if (currentStatus === 'LIVENESS_CHECK') {
                color = '#ffaa00';  // Cam: đang liveness
            } else if (currentStatus === 'FAILED') {
                color = '#ff6600';  // Cam đỏ: thất bại
            }
            
            drawCornerBox(bx, by, bw, bh, color);
            
            // Label text phía dưới bounding box
            const label = currentLabel || 'Đang nhận diện...';
            ctx.font = 'bold 13px "JetBrains Mono", monospace';
            const textW = ctx.measureText(label).width;
            // Background cho text
            ctx.fillStyle = color + 'cc';  // semi-transparent
            ctx.fillRect(bx, by + bh + 4, textW + 12, 22);
            ctx.fillStyle = '#000';
            ctx.fillText(label, bx + 6, by + bh + 20);
        }
    }
    requestAnimationFrame(renderCanvas);
}

// ─── Logging System ────────────────────────────────────────────
function addLog(category, text, textColor = '') {
    const entry = document.createElement('div');
    
    let typeClass = 'log-khac';
    if(category === 'Nhận diện') typeClass = 'log-nhandien';
    else if(category === 'Liveness') typeClass = 'log-liveness';
    else if(category === 'Cảnh báo') typeClass = 'log-canhbao';
    else if(category === 'Hệ thống') typeClass = 'log-hethong';

    entry.className = `log-item ${typeClass}`;
    const t = new Date().toLocaleTimeString('vi-VN', {hour12:false});
    
    let colorStyle = textColor ? `style="color: ${textColor}"` : '';
    
    entry.innerHTML = `
        <span class="log-time">[${t}]</span>
        <span class="log-cat">[${category}]</span>
        <span class="log-text" ${colorStyle}>${text}</span>
    `;
    
    DOM.logStream.appendChild(entry);
    DOM.logStream.scrollTop = DOM.logStream.scrollHeight;
    if(DOM.logStream.children.length > 100) DOM.logStream.removeChild(DOM.logStream.firstChild);
}

// ─── Liveness System ───────────────────────────────────────────
function renderLivenessSteps(challenges, currentIdx, status) {
    DOM.livSteps.innerHTML = '';
    
    if (challenges.length === 0) {
        DOM.livSteps.innerHTML = '<div class="liveness-placeholder">Đang chờ hệ thống...</div>';
        return;
    }
    
    challenges.forEach((ch, idx) => {
        const step = document.createElement('div');
        let iconHtml = '<div class="step-ico">○</div>';
        let stepClass = 'liveness-step pending';
        
        if (status === 'failed' && idx === currentIdx) {
            stepClass = 'liveness-step failed';
            iconHtml = '<div class="step-ico">✗</div>';
        } else if (idx < currentIdx || status === 'passed') {
            stepClass = 'liveness-step done';
            iconHtml = '<div class="step-ico">✓</div>';
        } else if (idx === currentIdx) {
            stepClass = 'liveness-step active';
            iconHtml = '<div class="step-ico"><div class="loader"></div></div>';
        }
        
        step.className = stepClass;
        step.innerHTML = `${iconHtml}<span>Bước ${idx+1}: ${ch}</span>`;
        DOM.livSteps.appendChild(step);
    });
}

function clearLiveness() {
    if(livenessInterval) clearInterval(livenessInterval);
    DOM.livTimer.textContent = '';
    renderLivenessSteps([], 0, '');
}

// ─── Event Handling ────────────────────────────────────────────
function handleEvent(type, payload) {
    switch (type) {
        case 'FRAME_READY':
            DOM.fpsVal.textContent = Math.round(payload.fps);
            break;

        case 'FACE_DETECTED':
            currentBBox = payload.bbox;
            currentTrackingId = payload.tracking_id;
            currentStatus = payload.status || 'RECOGNIZING';
            currentLabel = payload.label || 'Đang nhận diện...';
            isTrackingActive = true;
            break;

        case 'FACE_LOST':
            currentBBox = null;
            isTrackingActive = false;
            currentLabel = 'Đang nhận diện...';
            currentStatus = 'RECOGNIZING';
            DOM.userName.textContent = '--';
            DOM.userRole.textContent = '--';
            DOM.userConf.textContent = '0%';
            DOM.confBar.style.width = '0%';
            DOM.avatarIcon.textContent = '👤';
            DOM.avatarIcon.style.color = '#fff';
            clearLiveness();
            break;

        case 'USER_RECOGNIZED':
        case 'USER_VERIFIED': {
            const conf = payload.confidence || 0;
            DOM.userName.textContent = payload.full_name;
            DOM.userRole.textContent = payload.role;
            DOM.userConf.textContent = conf.toFixed(1) + '%';
            DOM.confBar.style.width = conf + '%';
            DOM.avatarIcon.textContent = '✓';
            DOM.avatarIcon.style.color = 'var(--accent-green)';
            // Cập nhật canvas label
            currentLabel = payload.full_name || 'Nhận diện';
            currentStatus = 'VERIFIED';
            addLog('Nhận diện', `✓ Đã phát hiện: ${payload.full_name}`, 'var(--accent-blue)');
            break;
        }

        case 'UNKNOWN_USER': {
            const strangerLabel = payload.label || 'Khách Lạ';
            DOM.userName.textContent = strangerLabel;
            DOM.userRole.textContent = 'CHƯA ĐĂNG KÝ';
            DOM.userConf.textContent = (payload.best_score ? (payload.best_score * 100).toFixed(1) : '0') + '%';
            DOM.confBar.style.width = (payload.best_score ? payload.best_score * 100 : 0) + '%';
            DOM.avatarIcon.textContent = '⚠️';
            DOM.avatarIcon.style.color = 'var(--accent-red)';
            // Cập nhật label trên canvas
            currentLabel = strangerLabel;
            currentStatus = 'STRANGER';
            addLog('Cảnh báo', `⚠ Phát hiện ${strangerLabel} — Score: ${payload.best_score ? payload.best_score.toFixed(3) : 'N/A'}`, 'var(--accent-red)');
            break;
        }

        case 'LIVENESS_STARTED':
            livenessChallenges = payload.challenges || [];
            livenessCurrentIdx = 0;
            livenessDeadline = Date.now() + (payload.timeout || 10)*1000;
            
            renderLivenessSteps(livenessChallenges, 0, 'active');
            
            const tick = () => {
                const rem = Math.max(0, Math.ceil((livenessDeadline - Date.now())/1000));
                DOM.livTimer.textContent = rem + 's';
                if(rem <= 0 && livenessInterval) clearInterval(livenessInterval);
            }
            tick();
            if(livenessInterval) clearInterval(livenessInterval);
            livenessInterval = setInterval(tick, 1000);
            
            addLog('Liveness', `Bắt đầu yêu cầu xác minh`, 'var(--accent-orange)');
            break;

        case 'LIVENESS_PROGRESS':
            livenessCurrentIdx = payload.current_index;
            renderLivenessSteps(livenessChallenges, livenessCurrentIdx, 'active');
            addLog('Liveness', `Đang thực hiện thử thách: ${payload.current_challenge}`);
            break;

        case 'LIVENESS_PASSED':
            if(livenessInterval) clearInterval(livenessInterval);
            DOM.livTimer.textContent = '';
            renderLivenessSteps(livenessChallenges, livenessChallenges.length, 'passed');
            addLog('Liveness', 'Đã vượt qua kiểm tra sinh trắc', 'var(--accent-green)');
            break;

        case 'LIVENESS_FAILED':
            if(livenessInterval) clearInterval(livenessInterval);
            DOM.livTimer.textContent = '';
            renderLivenessSteps(livenessChallenges, livenessCurrentIdx, 'failed');
            addLog('Cảnh báo', `Thử thách thất bại (${payload.reason})`, 'var(--accent-red)');
            break;

        case 'CAMERA_STATUS':
            const camStat = (payload.status || 'offline').toUpperCase();
            if (camStat === 'ONLINE') {
                DOM.lightCam.className = 'status-dot on';
                if (DOM.camText.textContent !== 'Online') {
                    setTimeout(()=> DOM.videoFeed.src = '/video_feed?t='+Date.now(), 500);
                }
            } else if (camStat === 'CONNECTING') {
                DOM.lightCam.className = 'status-dot warn';
            } else {
                DOM.lightCam.className = 'status-dot';
            }
            DOM.camText.textContent = camStat.charAt(0).toUpperCase() + camStat.slice(1).toLowerCase();
            break;

        case 'CAMERA_CONNECTED':
            DOM.lightCam.className = 'status-dot on';
            DOM.camText.textContent = 'Online';
            addLog('Hệ thống', 'Camera Yanshee Connected', 'var(--accent-green)');
            break;

        case 'CAMERA_RECONNECTING':
            DOM.lightCam.className = 'status-dot warn';
            DOM.camText.textContent = 'Reconnecting';
            addLog('Cảnh báo', 'Camera đang reconnect...', 'var(--accent-orange)');
            break;

        case 'CAMERA_ERROR':
            DOM.lightCam.className = 'status-dot';
            DOM.camText.textContent = 'Error';
            addLog('Cảnh báo', `Camera lỗi: ${payload.error || 'Unknown'}`, 'var(--accent-red)');
            break;

        case 'CAMERA_DISCONNECTED':
            DOM.lightCam.className = 'status-dot';
            DOM.camText.textContent = 'Offline';
            addLog('Cảnh báo', 'Camera Yanshee Disconnected', 'var(--accent-red)');
            break;

        case 'ROBOT_STATUS':
            const botStat = (payload.status || 'offline').toUpperCase();
            if (['READY', 'ONLINE', 'CONNECTED'].includes(botStat)) {
                DOM.lightRobot.className = 'status-dot on';
            } else if (['SPEAKING', 'GREETING', 'RESETTING', 'WAITING_RESET', 'BUSY', 'CONNECTING'].includes(botStat)) {
                DOM.lightRobot.className = 'status-dot warn';
            } else {
                DOM.lightRobot.className = 'status-dot';
            }
            // Pretty formatting e.g. "Waiting Reset"
            const prettyStat = botStat.split('_').map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');
            DOM.robotText.textContent = prettyStat;
            break;

        case 'ROBOT_SPEAKING_STARTED':
            addLog('Hệ thống', `Robot → Nói: ${payload.speech}`);
            break;
        case 'ROBOT_GREETING_STARTED':
            addLog('Hệ thống', `Robot → Greeting started: ${payload.motion}`);
            break;
        case 'ROBOT_GREETING_FINISHED':
            addLog('Hệ thống', `Robot → Greeting finished`);
            break;
        case 'ROBOT_RESET_WAITING':
            addLog('Hệ thống', `Robot → Waiting ${payload.delay}s before reset`);
            break;
        case 'ROBOT_RESET_STARTED':
            addLog('Hệ thống', `Robot → Reset started: ${payload.motion}`);
            break;
        case 'ROBOT_RESET_FINISHED':
            addLog('Hệ thống', `Robot → Reset finished`);
            break;
        case 'ROBOT_READY':
            addLog('Hệ thống', `Robot → Ready`, 'var(--accent-green)');
            break;
    }
}

// ─── WebSocket ─────────────────────────────────────────────────
function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
        DOM.lightApi.classList.add('on');
        addLog('Hệ thống', 'Kết nối Data Stream thành công');
    };
    ws.onclose = () => {
        DOM.lightApi.classList.remove('on');
        addLog('Cảnh báo', 'Mất kết nối Stream. Đang thử lại...', 'var(--accent-red)');
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
addLog('Hệ thống', 'YANSHEE FACE ID Khởi động hoàn tất');
