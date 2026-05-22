/**
 * AnchorVerse — WebSocket 客户端
 * 连接管理 + 自动重连 + 消息路由 + 心跳
 */
class MultiplayerClient {
    constructor() {
        this.ws = null;
        this.roomId = null;
        this.sessionId = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnect = 8;
        this.poseTimer = null;
        this.pingTimer = null;
        this._handlers = {};
        this._joinPayload = {};
    }

    /** 连接到房间 */
    connect(roomId, displayName, avatarColor) {
        this.roomId = roomId;
        this._joinPayload = {
            type: 'join_room',
            display_name: displayName || 'Player',
            avatar_color: avatarColor || '#6366f1',
        };
        this._open();
    }

    /** 发送消息 */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    /** 注册消息处理器 */
    on(type, fn) {
        if (!this._handlers[type]) this._handlers[type] = [];
        this._handlers[type].push(fn);
    }

    /** 开始发送位置（每 50ms） */
    startPose(getPose) {
        this.stopPose();
        this.poseTimer = setInterval(() => {
            if (!this.connected) return;
            const pose = getPose();
            this.send({
                type: 'pose_update',
                p: pose.position,
                r: pose.rotation,
                a: pose.animation || 'idle',
            });
        }, 50);
    }

    stopPose() {
        if (this.poseTimer) { clearInterval(this.poseTimer); this.poseTimer = null; }
    }

    /** 断开 */
    disconnect() {
        this.stopPose();
        if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
        this.reconnectAttempts = this.maxReconnect; // 阻止重连
        if (this.ws) { this.ws.close(); this.ws = null; }
        this.connected = false;
    }

    // ── 内部 ──────────────────────────────────────────────

    _open() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws/room/${this.roomId}`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.send(this._joinPayload);
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this._route(msg);
            } catch (e) { /* ignore malformed */ }
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.stopPose();
            if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
            this._fire('disconnected', { reason: 'connection_closed' });
            this._tryReconnect();
        };

        this.ws.onerror = () => {
            // onclose will fire after this
        };
    }

    _route(msg) {
        const { type } = msg;

        if (type === 'room_state') {
            this.sessionId = msg.session_id;
            this.connected = true;
            this._startPing();
        }

        if (type === 'pong') return;

        this._fire(type, msg);
    }

    _fire(type, data) {
        const fns = this._handlers[type] || [];
        for (const fn of fns) fn(data);
    }

    _startPing() {
        if (this.pingTimer) clearInterval(this.pingTimer);
        this.pingTimer = setInterval(() => this.send({ type: 'ping' }), 10000);
    }

    _tryReconnect() {
        if (this.reconnectAttempts >= this.maxReconnect) return;
        const delay = Math.min(1000 * (this.reconnectAttempts + 1), 15000);
        this.reconnectAttempts++;
        setTimeout(() => { if (!this.connected) this._open(); }, delay);
    }
}

export { MultiplayerClient };
