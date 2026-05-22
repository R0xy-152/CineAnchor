/**
 * AnchorVerse — 聊天浮层 UI
 * 消息列表 + 输入框 + 系统消息
 */
class ChatUI {
    constructor() {
        this._container = null;
        this._list = null;
        this._input = null;
        this._onSend = null;
        this._maxMessages = 100;
    }

    /** 挂载到页面 */
    mount(onSend) {
        this._onSend = onSend;

        const el = document.createElement('div');
        el.id = 'chat-ui';
        el.innerHTML = `
            <style>
                #chat-ui {
                    position: fixed; bottom: 16px; left: 16px;
                    width: 320px; max-height: 360px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    z-index: 100; pointer-events: none;
                    display: flex; flex-direction: column;
                }
                #chat-messages {
                    flex: 1; overflow-y: auto;
                    margin-bottom: 6px; min-height: 0;
                    pointer-events: auto;
                    scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent;
                }
                .chat-msg {
                    padding: 4px 8px; margin-bottom: 2px;
                    font-size: 13px; color: #ccc;
                    background: rgba(0,0,0,0.5); border-radius: 6px;
                    word-break: break-word;
                }
                .chat-msg .name { color: #7c3aed; font-weight: 600; }
                .chat-msg.system { color: #666; font-style: italic; font-size: 12px; }
                #chat-input-row {
                    display: flex; gap: 8px; pointer-events: auto;
                }
                #chat-input {
                    flex: 1; padding: 8px 12px; border-radius: 8px;
                    border: 1px solid rgba(255,255,255,0.1);
                    background: rgba(0,0,0,0.6); color: #fff; outline: none;
                    font-size: 13px;
                }
                #chat-input:focus { border-color: #7c3aed; }
            </style>
            <div id="chat-messages"></div>
            <div id="chat-input-row">
                <input id="chat-input" placeholder="按 T 输入消息..." maxlength="500">
            </div>
        `;
        document.body.appendChild(el);

        this._container = el;
        this._list = el.querySelector('#chat-messages');
        this._input = el.querySelector('#chat-input');

        this._input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this._send();
            e.stopPropagation();
        });

        // 默认隐藏
        el.style.display = 'none';
    }

    /** 添加消息 */
    addMessage(displayName, text, isSystem = false) {
        if (!this._list) return;
        const div = document.createElement('div');
        div.className = isSystem ? 'chat-msg system' : 'chat-msg';
        if (isSystem) {
            div.textContent = text;
        } else {
            div.innerHTML = `<span class="name">${this._esc(displayName)}:</span> ${this._esc(text)}`;
        }
        this._list.appendChild(div);
        this._list.scrollTop = this._list.scrollHeight;

        // 限制消息数
        while (this._list.children.length > this._maxMessages) {
            this._list.firstChild.remove();
        }
    }

    /** 显示/隐藏 */
    show() {
        if (this._container) this._container.style.display = 'flex';
    }

    hide() {
        if (this._container) this._container.style.display = 'none';
        if (this._input) this._input.blur();
    }

    toggle() {
        if (!this._container) return;
        if (this._container.style.display === 'none') {
            this.show();
            setTimeout(() => this._input?.focus(), 50);
        } else {
            this.hide();
        }
    }

    // ── 内部 ──────────────────────────────────────────────

    _send() {
        const text = (this._input?.value || '').trim();
        if (!text) return;
        if (this._onSend) this._onSend(text);
        this._input.value = '';
    }

    _esc(s) {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }
}

export { ChatUI };
