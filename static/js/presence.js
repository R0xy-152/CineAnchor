/**
 * AnchorVerse — 临场感模块
 * 用户列表面板 + 在线人数 + 加入/离开提示 + 房主徽章 + 踢人
 */
class Presence {
    constructor() {
        this._panel = null;
        this._userList = null;
        this._countEl = null;
        this._users = new Map(); // sessionId -> { displayName, color, isHost }
        this._isHost = false;
        this._hostSession = null;
        this._selfSession = null;
        this._onKick = null;
    }

    mount(onKick) {
        this._onKick = onKick || null;

        const el = document.createElement('div');
        el.id = 'presence-panel';
        el.innerHTML = `
            <style>
                #presence-panel {
                    position: fixed; top: 16px; right: 16px;
                    width: 200px; background: rgba(0,0,0,0.7);
                    border-radius: 12px; padding: 12px; z-index: 100;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    border: 1px solid rgba(255,255,255,0.08);
                }
                #presence-header {
                    display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 8px;
                }
                #presence-count { color: #7c3aed; font-weight: 700; font-size: 14px; }
                #presence-hint { color: #666; font-size: 11px; }
                #presence-list { display: flex; flex-direction: column; gap: 4px; }
                .presence-user {
                    display: flex; align-items: center; gap: 8px;
                    color: #ccc; font-size: 13px;
                }
                .presence-dot {
                    width: 8px; height: 8px; border-radius: 50%;
                    flex-shrink: 0;
                }
                .presence-host-badge {
                    font-size: 10px; color: #f59e0b; margin-left: 2px;
                }
                .presence-kick-btn {
                    margin-left: auto; background: none; border: 1px solid rgba(255,255,255,0.15);
                    color: #999; font-size: 10px; padding: 1px 6px; border-radius: 4px;
                    cursor: pointer; display: none;
                }
                .presence-kick-btn:hover { color: #f87171; border-color: #f87171; }
                .presence-kick-btn.visible { display: inline-block; }
            </style>
            <div id="presence-header">
                <span id="presence-count">👤 0 在线</span>
                <span id="presence-hint">Tab 切换</span>
            </div>
            <div id="presence-list"></div>
        `;
        document.body.appendChild(el);

        this._panel = el;
        this._countEl = el.querySelector('#presence-count');
        this._userList = el.querySelector('#presence-list');
    }

    /** 设置房主身份 */
    setHost(isHost) {
        this._isHost = isHost;
        this._render();
    }

    /** 设置完整用户列表 */
    setUsers(users, hostSession) {
        this._hostSession = hostSession || null;
        this._users.clear();
        for (const u of users) {
            this._users.set(u.session_id, {
                displayName: u.display_name,
                color: u.avatar_color,
                isHost: u.is_host || u.session_id === hostSession,
            });
        }
        this._render();
    }

    /** 设置自己的 session */
    setSelfSession(sid) {
        this._selfSession = sid;
    }

    /** 添加用户 */
    addUser(sessionId, displayName, color) {
        this._users.set(sessionId, {
            displayName,
            color,
            isHost: sessionId === this._hostSession,
        });
        this._render();
    }

    /** 移除用户 */
    removeUser(sessionId) {
        this._users.delete(sessionId);
        this._render();
    }

    get count() {
        return this._users.size;
    }

    // ── 内部 ──────────────────────────────────────────────

    _render() {
        if (!this._countEl) return;
        const hostMark = this._isHost ? ' 👑' : '';
        this._countEl.textContent = `👤 ${this._users.size} 在线${hostMark}`;

        this._userList.innerHTML = '';
        for (const [sid, u] of this._users) {
            const row = document.createElement('div');
            row.className = 'presence-user';

            const isSelf = sid === this._selfSession;
            const hostIcon = u.isHost ? ' 👑' : '';

            row.innerHTML = `
                <span class="presence-dot" style="background:${u.color}"></span>
                <span>${this._esc(u.displayName)}${hostIcon}</span>
            `;

            // 房主踢人按钮（不踢自己）
            if (this._isHost && !isSelf && this._onKick) {
                const kickBtn = document.createElement('button');
                kickBtn.className = 'presence-kick-btn visible';
                kickBtn.textContent = '✕';
                kickBtn.title = '踢出房间';
                kickBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this._onKick(sid);
                });
                row.appendChild(kickBtn);
            }

            this._userList.appendChild(row);
        }
    }

    _esc(s) {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }
}

export { Presence };
