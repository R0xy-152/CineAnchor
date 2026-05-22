/**
 * AnchorVerse — 临场感模块
 * 用户列表面板 + 在线人数 + 加入/离开提示
 */
class Presence {
    constructor() {
        this._panel = null;
        this._userList = null;
        this._countEl = null;
        this._users = new Map(); // sessionId -> { displayName, color }
    }

    mount() {
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

    /** 设置完整用户列表 */
    setUsers(users) {
        this._users.clear();
        for (const u of users) {
            this._users.set(u.session_id, {
                displayName: u.display_name,
                color: u.avatar_color,
            });
        }
        this._render();
    }

    /** 添加用户 */
    addUser(sessionId, displayName, color) {
        this._users.set(sessionId, { displayName, color });
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
        this._countEl.textContent = `👤 ${this._users.size} 在线`;

        this._userList.innerHTML = '';
        for (const [, u] of this._users) {
            const row = document.createElement('div');
            row.className = 'presence-user';
            row.innerHTML = `
                <span class="presence-dot" style="background:${u.color}"></span>
                <span>${this._esc(u.displayName)}</span>
            `;
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
