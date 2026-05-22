/**
 * AnchorVerse — 国际象棋游戏 UI
 * Canvas 渲染棋盘 + 规则引擎 + 双人对战
 */
import { ChessGame } from './chess-engine.js';

class ChessUI {
    constructor(onMoveSent) {
        this._game = new ChessGame();
        this._panel = null;
        this._canvas = null;
        this._ctx = null;
        this._selected = null;       // [row, col] | null
        this._legalMoves = [];       // 选中格子的合法目标
        this._localColor = 'white';  // 本地玩家的颜色（观战者不操作）
        this._playerColor = 'white'; // 当前操作方
        this._onMoveSent = onMoveSent; // (from, to, promotion) => WS
        this._visible = false;
        this._pieceImages = {};
        this._sqSize = 52;
        this._padding = 24;
        this._lastClickSq = null;
        this._isMyTurn = false;
        this._moveCallback = null;
    }

    /** 挂载 UI */
    mount(moveCallback) {
        this._moveCallback = moveCallback || null;

        const el = document.createElement('div');
        el.id = 'chess-panel';
        el.innerHTML = `
            <style>
                #chess-panel {
                    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    background: rgba(0,0,0,0.9); border-radius: 12px; padding: 16px;
                    z-index: 150; display: none;
                    border: 1px solid rgba(255,255,255,0.1);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    user-select: none;
                }
                #chess-canvas { display: block; border-radius: 4px; cursor: pointer; }
                #chess-info {
                    display: flex; justify-content: space-between; align-items: center;
                    margin-top: 10px; color: #ccc; font-size: 13px;
                }
                #chess-status { color: #7c3aed; font-weight: 600; }
                #chess-close {
                    background: none; border: 1px solid rgba(255,255,255,0.2);
                    color: #999; padding: 4px 12px; border-radius: 4px;
                    cursor: pointer; font-size: 12px;
                }
                #chess-close:hover { color: #fff; border-color: #f87171; }
            </style>
            <canvas id="chess-canvas" width="464" height="464"></canvas>
            <div id="chess-info">
                <span id="chess-status">白方回合</span>
                <button id="chess-close">关闭棋盘</button>
            </div>
        `;
        document.body.appendChild(el);

        this._panel = el;
        this._canvas = el.querySelector('#chess-canvas');
        this._ctx = this._canvas.getContext('2d');

        this._canvas.addEventListener('click', (e) => this._onClick(e));
        el.querySelector('#chess-close').addEventListener('click', () => this.hide());

        this._preRenderPieces();
    }

    /** 开始对局 */
    startGame(playerColor) {
        this._game.reset();
        this._localColor = playerColor || 'white';
        this._playerColor = 'white';
        this._selected = null;
        this._legalMoves = [];
        this._isMyTurn = (this._localColor === 'white');
        this._render();
        this.show();
    }

    /** 显示/隐藏 */
    show() {
        if (this._panel) this._panel.style.display = 'block';
        this._visible = true;
    }

    hide() {
        if (this._panel) this._panel.style.display = 'none';
        this._visible = false;
    }

    toggle() {
        if (this._visible) this.hide();
        else this.show();
    }

    get visible() { return this._visible; }

    /** 远程收到走法 */
    receiveMove(from, to, promotion) {
        const result = this._game.move({ from, to, promotion: promotion || 'Q' });
        if (result.success) {
            this._playerColor = this._game.turn;
            this._isMyTurn = (this._playerColor === this._localColor);
            this._selected = null;
            this._legalMoves = [];
            this._updateStatus();
            this._render();
        }
        return result;
    }

    // ── 内部 ──────────────────────────────────────────────

    _onClick(e) {
        const rect = this._canvas.getBoundingClientRect();
        const scaleX = this._canvas.width / rect.width;
        const scaleY = this._canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        const col = Math.floor((x - this._padding) / this._sqSize);
        const row = Math.floor((y - this._padding) / this._sqSize);

        if (col < 0 || col > 7 || row < 0 || row > 7) return;

        // 翻转棋盘（黑方视角）
        const rc = this._localColor === 'black' ? [7 - row, 7 - col] : [row, col];

        if (!this._isMyTurn) return;

        this._handleSquareClick(rc);
    }

    _handleSquareClick([row, col]) {
        // 如果已有选中，尝试走棋
        if (this._selected) {
            const match = this._legalMoves.find(m => m.to[0] === row && m.to[1] === col);
            if (match) {
                const promotion = match.promotion || 'Q';
                const from = this._selected;
                this._executeLocalMove(from, [row, col], promotion);
                return;
            }
        }

        // 选择新棋子
        const piece = this._game.at(row, col);
        if (piece && piece.color === this._localColor) {
            this._selected = [row, col];
            this._legalMoves = this._game.getLegalMoves([row, col]);
        } else {
            this._selected = null;
            this._legalMoves = [];
        }
        this._render();
    }

    _executeLocalMove(from, to, promotion) {
        const result = this._game.move({ from, to, promotion });
        if (result.success) {
            this._selected = null;
            this._legalMoves = [];
            this._playerColor = this._game.turn;
            this._isMyTurn = false; // 等待对方走棋
            this._updateStatus();
            this._render();

            if (this._moveCallback) {
                this._moveCallback(from, to, promotion);
            }
            if (this._onMoveSent) {
                this._onMoveSent(from, to, promotion);
            }
        }
    }

    _updateStatus() {
        const el = this._panel?.querySelector('#chess-status');
        if (!el) return;
        if (this._game.isGameOver) {
            if (this._game.result === 'draw') el.textContent = '和棋！';
            else el.textContent = `${this._game.result === 'white' ? '白方' : '黑方'} 获胜！`;
        } else if (this._game.isInCheck(this._game.turn)) {
            el.textContent = `${this._playerColor === 'white' ? '白方' : '黑方'} 被将军！`;
        } else {
            el.textContent = `${this._playerColor === 'white' ? '白方' : '黑方'} 回合`;
        }
    }

    _render() {
        const ctx = this._ctx;
        const p = this._padding;
        const s = this._sqSize;
        const w = this._canvas.width;
        const h = this._canvas.height;

        ctx.clearRect(0, 0, w, h);

        // 坐标标注
        ctx.fillStyle = '#888';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const files = 'abcdefgh';
        const reverse = this._localColor === 'black';

        for (let i = 0; i < 8; i++) {
            const fileIdx = reverse ? 7 - i : i;
            ctx.fillText(files[fileIdx], p + i * s + s / 2, p + 8 * s + 12);
            ctx.fillText((reverse ? i + 1 : 8 - i).toString(), p - 12, p + i * s + s / 2);
        }

        // 棋盘格
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const dr = reverse ? 7 - r : r;
                const dc = reverse ? 7 - c : c;
                const x = p + c * s, y = p + r * s;
                ctx.fillStyle = (dr + dc) % 2 === 0 ? '#f0d9b5' : '#b58863';
                ctx.fillRect(x, y, s, s);

                // 高亮选中格
                if (this._selected && this._selected[0] === dr && this._selected[1] === dc) {
                    ctx.fillStyle = 'rgba(124,58,237,0.5)';
                    ctx.fillRect(x, y, s, s);
                }

                // 高亮合法走法
                for (const m of this._legalMoves) {
                    if (m.to[0] === dr && m.to[1] === dc) {
                        const cx = x + s / 2, cy = y + s / 2;
                        const target = this._game.at(dr, dc);
                        if (target) {
                            ctx.strokeStyle = 'rgba(255,80,80,0.8)';
                            ctx.lineWidth = 3;
                            ctx.beginPath();
                            ctx.arc(cx, cy, s * 0.35, 0, Math.PI * 2);
                            ctx.stroke();
                        } else {
                            ctx.fillStyle = 'rgba(0,0,0,0.2)';
                            ctx.beginPath();
                            ctx.arc(cx, cy, s * 0.15, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }
                }
            }
        }

        // 棋子
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const dr = reverse ? 7 - r : r;
                const dc = reverse ? 7 - c : c;
                const piece = this._game.at(dr, dc);
                if (!piece) continue;
                const x = p + c * s + s / 2;
                const y = p + r * s + s / 2;
                const key = piece.color + '_' + piece.type;
                const img = this._pieceImages[key];
                if (img) {
                    ctx.drawImage(img, x - s * 0.4, y - s * 0.4, s * 0.8, s * 0.8);
                }
            }
        }

        // 将军高亮
        if (this._game.isInCheck(this._game.turn)) {
            // 找到被将军的王
            for (let r = 0; r < 8; r++) {
                for (let c = 0; c < 8; c++) {
                    const dr = reverse ? 7 - r : r;
                    const dc = reverse ? 7 - c : c;
                    const piece = this._game.at(dr, dc);
                    if (piece && piece.type === 'king' && piece.color === this._game.turn) {
                        const x = p + c * s, y = p + r * s;
                        ctx.fillStyle = 'rgba(255,50,50,0.35)';
                        ctx.fillRect(x, y, s, s);
                    }
                }
            }
        }
    }

    _preRenderPieces() {
        const types = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn'];
        const unicode = {
            king: { white: '♔', black: '♚' },
            queen: { white: '♕', black: '♛' },
            rook: { white: '♖', black: '♜' },
            bishop: { white: '♗', black: '♝' },
            knight: { white: '♘', black: '♞' },
            pawn: { white: '♙', black: '♟' },
        };

        for (const type of types) {
            for (const color of ['white', 'black']) {
                const c = document.createElement('canvas');
                c.width = 64; c.height = 64;
                const ctx = c.getContext('2d');
                ctx.font = '48px serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = color === 'white' ? '#ffffff' : '#111111';
                ctx.strokeStyle = color === 'white' ? '#333333' : '#cccccc';
                ctx.lineWidth = 1;
                ctx.fillText(unicode[type][color], 32, 34);
                ctx.strokeText(unicode[type][color], 32, 34);
                this._pieceImages[color + '_' + type] = c;
            }
        }
    }
}

export { ChessUI };
