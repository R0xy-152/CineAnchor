/**
 * AnchorVerse — 卡牌游戏 UI
 * Canvas 渲染手牌 + 桌面 + 多人同步
 */
import { Card, Deck, Hand, CardGameEngine, SUIT_SYMBOLS, SUIT_COLORS } from './card-deck.js';

class CardTableUI {
    constructor(onAction) {
        /** (action, data) => WS 回调 */
        this._onAction = onAction;
        this._panel = null;
        this._canvas = null;
        this._ctx = null;

        /** 游戏引擎 */
        this._engine = null;

        /** 本地玩家 ID / 座位 */
        this._selfId = null;
        this._selfSeat = -1;

        /** 选中卡片 */
        this._selectedCards = new Set();

        /** 可见性 */
        this.visible = false;

        /** 布局常量 */
        this._cardW = 70;
        this._cardH = 100;
        this._cardRadius = 8;
        this._fanSpread = 48;   // 手牌扇形间距
        this._fanArc = 0.04;    // 弧度偏移

        /** 其他玩家信息 */
        this._playerInfo = {}; // sessionId -> { name, color, seat }

        /** 他人手牌大小 */
        this._handSizes = {};

        /** 动画 */
        this._animations = [];
    }

    // ── 挂载 / 销毁 ──────────────────────────────────────────

    mount() {
        if (this._panel) return;

        const panel = document.createElement('div');
        panel.id = 'card-table-panel';
        panel.innerHTML = `
            <style>
                #card-table-panel {
                    position: fixed; inset: 0; z-index: 110; display: none;
                    background: rgba(10,10,20,0.92);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                }
                #card-table-panel.visible { display: block; }
                #card-table-canvas {
                    display: block; width: 100%; height: 100%;
                }
                #card-controls {
                    position: fixed; bottom: 24px; right: 24px; z-index: 111;
                    display: flex; flex-direction: column; gap: 8px;
                }
                #card-controls button {
                    width: 100px; padding: 8px 14px; border-radius: 8px; border: none;
                    background: #7c3aed; color: #fff; font-size: 13px; font-weight: 600;
                    cursor: pointer; transition: background 0.15s;
                }
                #card-controls button:hover { background: #6d28d9; }
                #card-controls button.secondary { background: rgba(255,255,255,0.1); }
                #card-controls button.secondary:hover { background: rgba(255,255,255,0.2); }
                #card-controls button:disabled { background: #333; color: #666; cursor: default; }
                #card-hint {
                    position: fixed; bottom: 140px; left: 50%; transform: translateX(-50%);
                    color: rgba(255,255,255,0.5); font-size: 12px; z-index: 111;
                    pointer-events: none;
                }
            </style>
            <canvas id="card-table-canvas"></canvas>
            <div id="card-controls">
                <button id="card-btn-deal">发牌</button>
                <button id="card-btn-shuffle">洗牌</button>
                <button id="card-btn-reset" class="secondary">重置</button>
                <button id="card-btn-close" class="secondary">关闭</button>
            </div>
            <div id="card-hint">点击手牌选中，再次点击打出</div>
        `;
        document.body.appendChild(panel);
        this._panel = panel;

        this._canvas = document.getElementById('card-table-canvas');
        this._ctx = this._canvas.getContext('2d');

        this._canvas.addEventListener('click', (e) => this._onClick(e));
        this._canvas.addEventListener('mousemove', (e) => this._onHover(e));

        document.getElementById('card-btn-deal').addEventListener('click', () => {
            this._onAction('card_deal', {});
        });
        document.getElementById('card-btn-shuffle').addEventListener('click', () => {
            this._onAction('card_shuffle', {});
        });
        document.getElementById('card-btn-reset').addEventListener('click', () => {
            this._onAction('card_reset', {});
        });
        document.getElementById('card-btn-close').addEventListener('click', () => {
            this.hide();
        });

        this._resize();
        window.addEventListener('resize', () => this._resize());
    }

    _resize() {
        if (!this._canvas) return;
        const dpr = window.devicePixelRatio || 1;
        const w = window.innerWidth;
        const h = window.innerHeight;
        this._canvas.width = w * dpr;
        this._canvas.height = h * dpr;
        this._canvas.style.width = w + 'px';
        this._canvas.style.height = h + 'px';
        this._ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this._cw = w;
        this._ch = h;
        if (this.visible) this._draw();
    }

    // ── 显示 / 隐藏 ──────────────────────────────────────────

    show() {
        if (!this._panel) this.mount();
        this.visible = true;
        this._panel.classList.add('visible');
        this._resize();
        this._draw();
        // 请求服务端初始化游戏状态
        this._onAction('card_init', {});
    }

    hide() {
        this.visible = false;
        if (this._panel) this._panel.classList.remove('visible');
    }

    toggle() {
        if (this.visible) this.hide();
        else this.show();
    }

    // ── 游戏状态同步 ──────────────────────────────────────────

    /** 从服务端状态初始化/更新游戏 */
    initGame(players, selfId, config = {}) {
        this._selfId = selfId;
        // 记录玩家信息
        for (const p of players) {
            const sid = typeof p === 'string' ? p : p.session_id;
            if (!this._playerInfo[sid]) {
                this._playerInfo[sid] = {
                    name: p.display_name || sid.slice(0, 8),
                    color: p.avatar_color || '#6366f1',
                };
            } else {
                this._playerInfo[sid].name = p.display_name || this._playerInfo[sid].name;
                this._playerInfo[sid].color = p.avatar_color || this._playerInfo[sid].color;
            }
        }
        const playerIds = players.map(p => typeof p === 'string' ? p : p.session_id);
        if (!this._engine) {
            this._engine = new CardGameEngine(playerIds, config);
        } else {
            this._engine.players = playerIds;
        }
        this._selfSeat = playerIds.indexOf(selfId);
    }

    /** 服务器发牌结果 (个人手牌) */
    onDeal(data) {
        if (!this._engine) return;
        this._engine.phase = 'playing';
        // data.hand: 当前玩家的手牌
        const hand = this._engine.getHand(this._selfId);
        if (hand && data.hand) {
            hand.clear();
            for (const c of data.hand) {
                hand.add(new Card(c.suit, c.rank));
            }
        }
        if (data.table) {
            this._engine.tableCards = data.table.map(c => {
                const card = new Card(c.suit, c.rank);
                card.faceUp = c.faceUp !== false;
                return card;
            });
        }
        this._selectedCards.clear();
        if (this.visible) this._draw();
    }

    /** 加载游戏状态 */
    loadState(state) {
        if (!this._engine) return;
        this._engine.phase = state.phase;
        this._engine.turnIndex = state.turnIndex;
        this._engine.dealerIndex = state.dealerIndex;
        if (state.tableCards) {
            this._engine.tableCards = state.tableCards.map(c => {
                const card = new Card(c.suit, c.rank);
                card.faceUp = c.faceUp !== false;
                return card;
            });
        }
        if (state.discard_top) {
            const c = state.discard_top;
            const card = new Card(c.suit, c.rank);
            card.faceUp = true;
            if (this._engine.discardPile.length > 0) {
                this._engine.discardPile[this._engine.discardPile.length - 1] = card;
            } else {
                this._engine.discardPile.push(card);
            }
        }
        // hands: 对于他人是数量(number)，对于自己是数组
        if (state.hands) {
            for (const [pid, cards] of Object.entries(state.hands)) {
                if (pid === this._selfId) continue;
                if (typeof cards === 'number') {
                    this._handSizes[pid] = cards;
                } else if (Array.isArray(cards)) {
                    this._handSizes[pid] = cards.length;
                    const hand = this._engine.getHand(pid);
                    if (hand) {
                        hand.clear();
                        for (const c of cards) {
                            const card = new Card(c.suit, c.rank);
                            card.faceUp = false;
                            hand.add(card);
                        }
                    }
                }
            }
        }
        this._selectedCards.clear();
        if (this.visible) this._draw();
    }

    /** 服务器广播: 玩家出牌 */
    onCardPlayed(data) {
        if (!this._engine) return;
        const hand = this._engine.getHand(data.player_id);
        if (hand) {
            hand.remove(data.card_id);
        }
        if (data.player_id !== this._selfId && this._handSizes[data.player_id] > 0) {
            this._handSizes[data.player_id]--;
        }
        if (data.card) {
            const c = data.card;
            const card = new Card(c.suit, c.rank);
            card.faceUp = true;
            this._engine.discardPile.push(card);
        }
        if (data.turn_index !== undefined) {
            this._engine.turnIndex = data.turn_index;
        }
        if (this._engine.currentPlayer !== data.current_player && data.current_player) {
            this._engine.turnIndex = this._engine.players.indexOf(data.current_player);
        }
        if (this.visible) this._draw();
    }

    /** 服务器广播: 玩家抽牌 */
    onCardDrawn(data) {
        if (!this._engine) return;
        if (data.player_id === this._selfId && data.card) {
            const hand = this._engine.getHand(data.player_id);
            if (hand) {
                const card = new Card(data.card.suit, data.card.rank);
                card.faceUp = data.card.faceUp !== false;
                hand.add(card);
            }
        } else {
            // 其他玩家: 只更新计数
            this._handSizes[data.player_id] = (this._handSizes[data.player_id] || 0) + 1;
        }
        if (this.visible) this._draw();
    }

    // ── 交互 ──────────────────────────────────────────────────

    _onClick(e) {
        if (!this._engine || !this.visible) return;

        const mx = e.clientX;
        const my = e.clientY;

        // 检查手牌点击
        const hand = this._engine.getHand(this._selfId);
        if (hand && hand.size > 0) {
            const layouts = this._layoutHand(hand, true);
            for (let i = layouts.length - 1; i >= 0; i--) {
                const l = layouts[i];
                if (mx >= l.x && mx <= l.x + l.w && my >= l.y && my <= l.y + l.h) {
                    this._onCardClick(hand.cards[i], i);
                    return;
                }
            }
        }

        // 点击空白取消选中
        this._selectedCards.clear();
        this._draw();
    }

    _onCardClick(card, index) {
        const cardId = card.id;
        if (this._selectedCards.has(cardId)) {
            // 再次点击 → 打出
            this._selectedCards.delete(cardId);
            this._onAction('card_play', { card_id: cardId });
        } else {
            // 选中 (同时最多选 3 张)
            if (this._selectedCards.size >= 3) {
                this._selectedCards.clear();
            }
            this._selectedCards.add(cardId);
        }
        this._draw();
    }

    _onHover(e) {
        const prev = this._hoveredIndex;
        this._hoveredIndex = -1;

        if (!this._engine || !this.visible) return;
        const hand = this._engine.getHand(this._selfId);
        if (!hand || hand.size === 0) return;

        const layouts = this._layoutHand(hand, true);
        const mx = e.clientX, my = e.clientY;

        for (let i = layouts.length - 1; i >= 0; i--) {
            const l = layouts[i];
            if (mx >= l.x && mx <= l.x + l.w && my >= l.y && my <= l.y + l.h) {
                this._hoveredIndex = i;
                break;
            }
        }

        if (prev !== this._hoveredIndex) {
            this._draw();
            if (this._hoveredIndex >= 0) {
                this._canvas.style.cursor = 'pointer';
            } else {
                this._canvas.style.cursor = 'default';
            }
        }
    }

    // ── 布局计算 ─────────────────────────────────────────────

    /**
     * 计算手牌扇形布局
     * @returns {Array<{x, y, w, h, rotation, lift}>}
     */
    _layoutHand(hand, isSelf) {
        const count = hand.size;
        const layouts = [];

        if (count === 0) return layouts;

        if (isSelf) {
            // 自己手牌: 底部扇形
            const totalW = (count - 1) * this._fanSpread + this._cardW;
            const startX = (this._cw - totalW) / 2;
            const baseY = this._ch - 20;
            const centerX = this._cw / 2;

            for (let i = 0; i < count; i++) {
                const x = startX + i * this._fanSpread;
                const t = (i - (count - 1) / 2) / Math.max(count - 1, 1);
                const rotation = t * 0.3; // 弧度
                const lift = -Math.abs(t) * 30; // 两端抬起
                layouts.push({
                    x, y: baseY + lift,
                    w: this._cardW, h: this._cardH,
                    rotation: rotation * (180 / Math.PI),
                    lift,
                });
            }
        } else {
            // 其他玩家手牌: 顶部紧凑排列
            const totalW = (count - 1) * 18 + this._cardW * 0.7;
            const startX = (this._cw - totalW) / 2;
            for (let i = 0; i < count; i++) {
                layouts.push({
                    x: startX + i * 18,
                    y: 60,
                    w: this._cardW * 0.7, h: this._cardH * 0.7,
                    rotation: 0, lift: 0,
                });
            }
        }

        return layouts;
    }

    // ── 渲染 ─────────────────────────────────────────────────

    _draw() {
        const ctx = this._ctx;
        const w = this._cw;
        const h = this._ch;

        ctx.clearRect(0, 0, w, h);

        // 背景渐变
        const bg = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.7);
        bg.addColorStop(0, '#1a1a2e');
        bg.addColorStop(1, '#0a0a14');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, w, h);

        if (!this._engine) {
            ctx.fillStyle = '#888';
            ctx.font = '18px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('等待游戏开始...', w / 2, h / 2);
            return;
        }

        // 标题
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 22px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('🃏 卡牌桌', w / 2, 36);

        // 回合指示
        if (this._engine.phase === 'playing') {
            const cp = this._engine.currentPlayer;
            const info = this._playerInfo[cp] || { name: cp?.slice(0, 8) || '?' };
            const isMe = cp === this._selfId;
            ctx.fillStyle = isMe ? '#7c3aed' : '#888';
            ctx.font = '14px sans-serif';
            ctx.fillText(`${isMe ? '你的' : (info.name + ' 的')}回合`, w / 2, 58);
        }

        // 绘制其他玩家手牌
        this._drawOtherPlayers(ctx);

        // 绘制桌面中央区域
        this._drawTable(ctx);

        // 绘制自己的手牌
        this._drawSelfHand(ctx);

        // 牌堆计数
        if (this._engine.deck) {
            ctx.fillStyle = '#666';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(`牌堆: ${this._engine.deck.remaining} 张 | 弃牌: ${this._engine.discardPile.length} 张`, w - 20, h - 20);
        }
    }

    _drawSelfHand(ctx) {
        const hand = this._engine.getHand(this._selfId);
        if (!hand || hand.size === 0) return;

        const layouts = this._layoutHand(hand, true);

        for (let i = 0; i < hand.cards.length; i++) {
            const card = hand.cards[i];
            const l = layouts[i];
            const isHovered = i === this._hoveredIndex;
            const isSelected = this._selectedCards.has(card.id);

            ctx.save();
            // 选中/悬停时弹出
            const liftY = isSelected ? -20 : (isHovered ? -10 : 0);
            const cx = l.x + l.w / 2;
            const cy = l.y + l.h / 2 + liftY;
            ctx.translate(cx, cy);
            ctx.rotate(l.rotation * Math.PI / 180);

            this._drawCard(ctx, -l.w / 2, -l.h / 2, l.w, l.h, card, isSelected);

            ctx.restore();
        }
    }

    _drawOtherPlayers(ctx) {
        if (!this._engine) return;
        const playerIds = this._engine.players.filter(pid => pid !== this._selfId);

        const totalW = playerIds.length * 180;
        const startX = (this._cw - totalW) / 2;

        for (let i = 0; i < playerIds.length; i++) {
            const pid = playerIds[i];
            const info = this._playerInfo[pid] || { name: pid?.slice(0, 8), color: '#666' };
            const hand = this._engine.getHand(pid);
            const cx = startX + i * 180 + 90;
            const cy = 110;
            const isTurn = pid === this._engine.currentPlayer;

            // 玩家标签
            ctx.save();
            ctx.fillStyle = info.color;
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText((isTurn ? '▶ ' : '') + info.name, cx, cy - 15);

            // 手牌数
            const count = hand ? hand.size : (this._handSizes[pid] || 0);
            ctx.fillStyle = '#888';
            ctx.font = '11px sans-serif';
            ctx.fillText(count + ' 张', cx, cy + 10);

            // 手牌示意 (紧凑重叠)
            if (hand && hand.size > 0) {
                const startX2 = cx - Math.min(hand.size * 12, 40);
                for (let j = 0; j < Math.min(hand.size, 5); j++) {
                    this._drawCard(ctx, startX2 + j * 12, cy + 18, 28, 40,
                        { faceUp: false, id: 'back' }, false);
                }
            }

            ctx.restore();
        }
    }

    _drawTable(ctx) {
        const cx = this._cw / 2;
        const cy = this._ch / 2 + 20;

        // 桌面牌
        if (this._engine.tableCards && this._engine.tableCards.length > 0) {
            const count = this._engine.tableCards.length;
            const totalW = (count - 1) * 30 + this._cardW;
            const startX = cx - totalW / 2;

            for (let i = 0; i < count; i++) {
                this._drawCard(ctx, startX + i * 30, cy - this._cardH / 2,
                    this._cardW, this._cardH, this._engine.tableCards[i], false);
            }
        }

        // 弃牌堆顶部
        if (this._engine.discardPile.length > 0) {
            const topCard = this._engine.discardPile[this._engine.discardPile.length - 1];
            const pileX = cx + 160;
            const pileY = cy - this._cardH / 2;
            // 画几张重叠的牌背
            for (let i = 0; i < Math.min(3, this._engine.discardPile.length); i++) {
                this._drawCard(ctx, pileX - i * 2, pileY - i * 2, this._cardW * 0.8, this._cardH * 0.8,
                    { faceUp: false, id: 'discard_back' }, false);
            }
            // 顶牌正面
            this._drawCard(ctx, pileX + 4, pileY + 4, this._cardW * 0.8, this._cardH * 0.8, topCard, false);
            ctx.fillStyle = '#888';
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('弃牌堆', pileX, pileY + this._cardH * 0.8 + 20);
        }

        // 牌堆
        if (this._engine.deck && this._engine.deck.remaining > 0) {
            const deckX = cx - 200;
            const deckY = cy - this._cardH / 2;
            for (let i = 0; i < Math.min(3, this._engine.deck.remaining); i++) {
                this._drawCard(ctx, deckX - i * 2, deckY - i * 2, this._cardW * 0.8, this._cardH * 0.8,
                    { faceUp: false, id: 'deck_back' }, false);
            }
            ctx.fillStyle = '#888';
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('牌堆', deckX, deckY + this._cardH * 0.8 + 20);
        }
    }

    /**
     * 绘制单张卡牌
     */
    _drawCard(ctx, x, y, w, h, card, selected) {
        const r = this._cardRadius;

        ctx.save();

        // 阴影
        ctx.shadowColor = selected ? 'rgba(124,58,237,0.8)' : 'rgba(0,0,0,0.4)';
        ctx.shadowBlur = selected ? 16 : 6;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = selected ? 0 : 2;

        // 圆角矩形
        this._roundRect(ctx, x, y, w, h, r);

        if (card.faceUp === false) {
            // 牌背
            const grad = ctx.createLinearGradient(x, y, x + w, y + h);
            grad.addColorStop(0, '#2d1f5e');
            grad.addColorStop(0.5, '#4c2d8f');
            grad.addColorStop(1, '#2d1f5e');
            ctx.fillStyle = grad;
            ctx.fill();

            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();

            // 背面花纹
            ctx.save();
            ctx.beginPath();
            ctx.rect(x + 4, y + 4, w - 8, h - 8);
            ctx.clip();
            ctx.fillStyle = 'rgba(255,255,255,0.06)';
            const cx = x + w / 2, cy2 = y + h / 2;
            for (let a = 0; a < 8; a++) {
                const angle = (a / 8) * Math.PI * 2;
                ctx.beginPath();
                ctx.moveTo(cx, cy2);
                ctx.arc(cx, cy2, Math.min(w, h) * 0.35, angle, angle + 0.3);
                ctx.closePath();
                ctx.fill();
            }
            ctx.restore();

            // 中央菱形
            ctx.save();
            ctx.fillStyle = 'rgba(255,255,255,0.08)';
            const dCX = x + w / 2, dCY = y + h / 2, dS = Math.min(w, h) * 0.2;
            ctx.beginPath();
            ctx.moveTo(dCX, dCY - dS);
            ctx.lineTo(dCX + dS, dCY);
            ctx.lineTo(dCX, dCY + dS);
            ctx.lineTo(dCX - dS, dCY);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        } else {
            // 牌面
            ctx.fillStyle = '#fafafa';
            ctx.fill();
            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = 'rgba(0,0,0,0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();

            const color = card.color || SUIT_COLORS[card.suit] || '#111';
            const symbol = card.symbol || SUIT_SYMBOLS[card.suit] || '';
            const rank = card.rank || '?';
            const fs = Math.max(10, w * 0.2);

            // 左上角 rank + suit
            ctx.fillStyle = color;
            ctx.font = `bold ${fs}px sans-serif`;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            ctx.fillText(rank, x + 6, y + 4);
            ctx.font = `${fs * 0.7}px sans-serif`;
            ctx.fillText(symbol, x + 6, y + 4 + fs);

            // 中央大 suit
            ctx.fillStyle = color;
            ctx.font = `${w * 0.5}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(symbol, x + w / 2, y + h / 2);

            // 右下角 (倒置)
            ctx.save();
            ctx.translate(x + w - 6, y + h - 4);
            ctx.rotate(Math.PI);
            ctx.fillStyle = color;
            ctx.font = `bold ${fs}px sans-serif`;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            ctx.fillText(rank, 0, 0);
            ctx.font = `${fs * 0.7}px sans-serif`;
            ctx.fillText(symbol, 0, fs);
            ctx.restore();
        }

        ctx.restore();
    }

    _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    // ── 动画循环 ─────────────────────────────────────────────

    tick() {
        // 动画更新 (预留)
        for (let i = this._animations.length - 1; i >= 0; i--) {
            const anim = this._animations[i];
            anim.progress += 0.016;
            if (anim.progress >= 1) {
                this._animations.splice(i, 1);
            }
        }
        if (this.visible && this._animations.length > 0) {
            this._draw();
        }
    }

    // ── 辅助 ─────────────────────────────────────────────────

    /** 设置本地玩家 */
    setSelfId(sid) {
        this._selfId = sid;
    }

    /** 更新玩家信息 */
    setPlayerInfo(sessionId, info) {
        this._playerInfo[sessionId] = info;
    }
}

export { CardTableUI };
