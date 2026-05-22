/**
 * AnchorVerse — 卡牌游戏框架
 * 牌组管理、发牌、手牌、回合
 */

const SUITS = ['spades', 'hearts', 'diamonds', 'clubs'];
const SUIT_SYMBOLS = { spades: '♠', hearts: '♥', diamonds: '♦', clubs: '♣' };
const SUIT_COLORS = { spades: '#111', hearts: '#d32f2f', diamonds: '#d32f2f', clubs: '#111' };
const RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];

class Card {
    constructor(suit, rank) {
        this.suit = suit;
        this.rank = rank;
        this.faceUp = true;
    }

    get symbol() { return SUIT_SYMBOLS[this.suit]; }
    get color() { return SUIT_COLORS[this.suit]; }
    get rankIndex() { return RANKS.indexOf(this.rank); }
    get suitIndex() { return SUITS.indexOf(this.suit); }

    /** 唯一标识 */
    get id() { return `${this.rank}_of_${this.suit}`; }

    /** 排序权重 (0-51) */
    get sortKey() { return this.suitIndex * 13 + this.rankIndex; }
}

class Deck {
    constructor() {
        this.cards = [];
        this._reset();
    }

    _reset() {
        this.cards = [];
        for (const suit of SUITS) {
            for (const rank of RANKS) {
                this.cards.push(new Card(suit, rank));
            }
        }
    }

    /** Fisher-Yates 洗牌 */
    shuffle() {
        for (let i = this.cards.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [this.cards[i], this.cards[j]] = [this.cards[j], this.cards[i]];
        }
    }

    /** 从顶部抽一张 */
    draw() {
        return this.cards.pop() || null;
    }

    /** 发牌 (每人 N 张) */
    deal(numPlayers, cardsPerPlayer) {
        const hands = Array.from({ length: numPlayers }, () => []);
        for (let r = 0; r < cardsPerPlayer; r++) {
            for (let p = 0; p < numPlayers; p++) {
                const card = this.draw();
                if (card) hands[p].push(card);
            }
        }
        return hands;
    }

    /** 重置并洗牌 */
    reset() {
        this._reset();
        this.shuffle();
    }

    get remaining() { return this.cards.length; }
}

class Hand {
    constructor(playerId) {
        this.playerId = playerId;
        this.cards = [];
    }

    add(card) {
        this.cards.push(card);
    }

    remove(cardId) {
        const idx = this.cards.findIndex(c => c.id === cardId);
        if (idx >= 0) return this.cards.splice(idx, 1)[0];
        return null;
    }

    sort(by = 'rank') {
        if (by === 'rank') {
            this.cards.sort((a, b) => a.sortKey - b.sortKey);
        } else if (by === 'suit') {
            this.cards.sort((a, b) => {
                if (a.suitIndex !== b.suitIndex) return a.suitIndex - b.suitIndex;
                return a.rankIndex - b.rankIndex;
            });
        }
    }

    get size() { return this.cards.length; }
    clear() { this.cards = []; }
}

class CardGameEngine {
    /**
     * @param {string[]} players - session IDs in seat order
     * @param {object} config - game-specific config
     */
    constructor(players, config = {}) {
        this.deck = new Deck();
        this.players = players;
        this.config = config;
        this.hands = {};       // playerId -> Hand
        this.tableCards = [];  // community/table cards
        this.discardPile = [];
        this.turnIndex = 0;
        this.phase = 'setup';  // setup | dealing | playing | finished
        this.dealerIndex = 0;
        this.startTime = null;

        for (const pid of players) {
            this.hands[pid] = new Hand(pid);
        }
    }

    get currentPlayer() { return this.players[this.turnIndex]; }
    get playerCount() { return this.players.length; }

    startGame() {
        this.phase = 'dealing';
        this.deck.reset();
        this.startTime = Date.now();
        // 默认发牌: 每人 2 张
        const count = this.config.cardsPerPlayer || 2;
        const dealtHands = this.deck.deal(this.playerCount, count);
        for (let i = 0; i < this.playerCount; i++) {
            this.hands[this.players[i]].cards = dealtHands[i];
        }
        // 桌面牌
        const tableCount = this.config.tableCards || 0;
        for (let i = 0; i < tableCount; i++) {
            const card = this.deck.draw();
            if (card) this.tableCards.push(card);
        }
        this.turnIndex = (this.dealerIndex + 1) % this.playerCount;
        this.phase = 'playing';
        return { hands: dealtHands, table: [...this.tableCards] };
    }

    nextTurn() {
        this.turnIndex = (this.turnIndex + 1) % this.playerCount;
    }

    /** 玩家弃牌 */
    playCard(playerId, cardId) {
        const hand = this.hands[playerId];
        if (!hand) return null;
        const card = hand.remove(cardId);
        if (card) {
            this.discardPile.push(card);
        }
        return card;
    }

    /** 玩家抽牌 */
    drawCard(playerId) {
        const hand = this.hands[playerId];
        if (!hand) return null;
        const card = this.deck.draw();
        if (card) hand.add(card);
        return card;
    }

    /** 设置玩家手牌可见性 */
    setHandVisibility(playerId, faceUp) {
        const hand = this.hands[playerId];
        if (hand) {
            for (const card of hand.cards) {
                card.faceUp = faceUp;
            }
        }
    }

    /** 获取当前玩家手牌 */
    getHand(playerId) {
        return this.hands[playerId] || null;
    }

    toState() {
        return {
            phase: this.phase,
            turnIndex: this.turnIndex,
            currentPlayer: this.currentPlayer,
            dealerIndex: this.dealerIndex,
            deckRemaining: this.deck.remaining,
            tableCards: this.tableCards.map(c => ({
                id: c.id, suit: c.suit, rank: c.rank, faceUp: c.faceUp,
            })),
            discardSize: this.discardPile.length,
            hands: Object.fromEntries(
                Object.entries(this.hands).map(([pid, hand]) => [
                    pid, hand.cards.map(c => ({
                        id: c.id, suit: c.suit, rank: c.rank, faceUp: c.faceUp,
                    })),
                ])
            ),
        };
    }
}

export { Card, Deck, Hand, CardGameEngine, SUITS, RANKS, SUIT_SYMBOLS, SUIT_COLORS };
