/**
 * AnchorVerse — WebRTC 语音聊天
 * Mesh 拓扑：每个 peer 直接连接所有其他用户
 * 信令通过已有 WebSocket 通道传输
 */
class VoiceChat {
    constructor() {
        /** Map: sessionId -> RTCPeerConnection */
        this._peers = new Map();
        /** Map: sessionId -> MediaStream (remote) */
        this._streams = new Map();
        /** 本地音频流 */
        this._localStream = null;
        /** 是否静音 */
        this._muted = false;
        /** 是否激活 */
        this._active = false;
        /** WS 发送回调 */
        this._sendSignal = null;
        /** 自己的 sessionId */
        this._selfId = null;
        /** STUN 服务器 */
        this._iceServers = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
            ],
        };
        /** 状态指示器 */
        this._indicator = null;
    }

    /**
     * 启动语音
     * @param {function} sendSignal — (type, toSessionId, data) => WS
     */
    async start(sendSignal) {
        if (this._active) return;
        this._sendSignal = sendSignal;

        try {
            this._localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
                video: false,
            });
        } catch (e) {
            console.warn('麦克风访问失败:', e);
            return false;
        }

        this._active = true;
        this._showIndicator();
        return true;
    }

    /** 停止语音 */
    stop() {
        this._active = false;
        this._muted = false;

        // 关闭所有 peer 连接
        for (const [sid, pc] of this._peers) {
            pc.close();
        }
        this._peers.clear();
        this._streams.clear();

        // 停止本地流
        if (this._localStream) {
            this._localStream.getTracks().forEach(t => t.stop());
            this._localStream = null;
        }

        this._hideIndicator();
    }

    /** 切换静音 */
    toggleMute() {
        if (!this._localStream) return false;
        this._muted = !this._muted;
        this._localStream.getAudioTracks().forEach(t => {
            t.enabled = !this._muted;
        });
        this._updateIndicator();
        return this._muted;
    }

    get isMuted() { return this._muted; }
    get isActive() { return this._active; }

    /** 设置自己的 sessionId */
    setSelfId(sid) {
        this._selfId = sid;
    }

    // ── 远程事件 ──────────────────────────────────────────

    /** 新用户加入 → 创建 offer */
    async onUserJoined(sessionId) {
        if (!this._active || sessionId === this._selfId) return;
        if (this._peers.has(sessionId)) return;

        await this._createPeerConnection(sessionId);

        // 创建 offer
        const offer = await this._peers.get(sessionId).createOffer();
        await this._peers.get(sessionId).setLocalDescription(offer);

        this._sendSignal('voice_offer', sessionId, {
            sdp: offer,
        });
    }

    /** 用户离开 → 关闭连接 */
    onUserLeft(sessionId) {
        const pc = this._peers.get(sessionId);
        if (pc) {
            pc.close();
            this._peers.delete(sessionId);
        }
        this._streams.delete(sessionId);
    }

    /** 收到 offer → 创建 answer */
    async onOffer(fromSessionId, sdp) {
        if (!this._active) return;

        await this._ensurePeer(fromSessionId);

        const pc = this._peers.get(fromSessionId);
        await pc.setRemoteDescription(new RTCSessionDescription(sdp));

        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        this._sendSignal('voice_answer', fromSessionId, {
            sdp: answer,
        });
    }

    /** 收到 answer */
    async onAnswer(fromSessionId, sdp) {
        const pc = this._peers.get(fromSessionId);
        if (!pc) return;

        await pc.setRemoteDescription(new RTCSessionDescription(sdp));
    }

    /** 收到 ICE candidate */
    async onIceCandidate(fromSessionId, candidate) {
        const pc = this._peers.get(fromSessionId);
        if (!pc) return;

        try {
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (e) {
            console.warn('ICE candidate 添加失败:', e);
        }
    }

    /** 获取远程音频流（用于 3D 空间音频，预留） */
    getStream(sessionId) {
        return this._streams.get(sessionId) || null;
    }

    // ── 内部 ──────────────────────────────────────────────

    async _ensurePeer(sessionId) {
        if (!this._peers.has(sessionId)) {
            await this._createPeerConnection(sessionId);
        }
    }

    async _createPeerConnection(sessionId) {
        const pc = new RTCPeerConnection(this._iceServers);

        // 添加本地音频轨
        if (this._localStream) {
            this._localStream.getTracks().forEach(track => {
                pc.addTrack(track, this._localStream);
            });
        }

        // 接收远程音频
        pc.ontrack = (event) => {
            if (event.streams[0]) {
                this._streams.set(sessionId, event.streams[0]);
                // 创建 audio 元素播放
                this._playRemoteStream(sessionId, event.streams[0]);
            }
        };

        // ICE candidate
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                this._sendSignal('voice_ice', sessionId, {
                    candidate: event.candidate,
                });
            }
        };

        // 连接状态
        pc.onconnectionstatechange = () => {
            if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                this._peers.delete(sessionId);
                this._streams.delete(sessionId);
            }
        };

        this._peers.set(sessionId, pc);
    }

    _playRemoteStream(sessionId, stream) {
        // 检查是否已有 audio 元素
        const existingId = `voice-remote-${sessionId}`;
        if (document.getElementById(existingId)) return;

        const audio = document.createElement('audio');
        audio.id = existingId;
        audio.srcObject = stream;
        audio.autoplay = true;
        audio.volume = 0.8;
        document.body.appendChild(audio);
    }

    // ── UI 指示器 ────────────────────────────────────────

    _showIndicator() {
        if (this._indicator) return;
        const el = document.createElement('div');
        el.id = 'voice-indicator';
        el.innerHTML = `
            <style>
                #voice-indicator {
                    position: fixed; top: 16px; left: 16px;
                    background: rgba(0,0,0,0.7); border-radius: 20px;
                    padding: 6px 14px; z-index: 105; cursor: pointer;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    font-size: 13px; color: #4ade80; font-weight: 600;
                    border: 1px solid rgba(74,222,128,0.3);
                    display: flex; align-items: center; gap: 8px;
                    user-select: none;
                }
                #voice-indicator.muted { color: #f87171; border-color: rgba(248,113,113,0.3); }
                #voice-dot {
                    width: 8px; height: 8px; border-radius: 50%;
                    background: #4ade80;
                    animation: voice-pulse 1.5s ease infinite;
                }
                #voice-indicator.muted #voice-dot {
                    background: #f87171; animation: none;
                }
                @keyframes voice-pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.3; }
                }
            </style>
            <span id="voice-dot"></span>
            <span id="voice-label">语音</span>
        `;
        document.body.appendChild(el);

        el.addEventListener('click', () => this.toggleMute());
        this._indicator = el;
        this._updateIndicator();
    }

    _hideIndicator() {
        if (this._indicator) {
            this._indicator.remove();
            this._indicator = null;
        }
    }

    _updateIndicator() {
        if (!this._indicator) return;
        const label = this._indicator.querySelector('#voice-label');
        if (this._muted) {
            this._indicator.classList.add('muted');
            if (label) label.textContent = '已静音';
        } else {
            this._indicator.classList.remove('muted');
            if (label) label.textContent = '语音';
        }
    }
}

export { VoiceChat };
