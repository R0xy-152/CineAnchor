/**
 * AnchorVerse — 国际象棋规则引擎
 * 完整规则：合法走法、将军/将死/逼和、王车易位、吃过路兵、升变
 *
 * 用法:
 *   const game = new ChessGame();
 *   game.move({ from: [6,4], to: [4,4] });  // e2-e4
 *   game.getLegalMoves([1,0]);               // 获取某格合法走法
 *   console.log(game.fen());                 // FEN 导出
 */
const WHITE = 'white';
const BLACK = 'black';

const PIECES = {
    K: 'king', Q: 'queen', R: 'rook', B: 'bishop', N: 'knight', P: 'pawn',
};

class ChessGame {
    constructor(fen) {
        this.reset(fen);
    }

    // ── 初始化 ──────────────────────────────────────────────

    reset(fen) {
        if (fen) {
            this._loadFEN(fen);
        } else {
            this._loadFEN('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
        }
    }

    /** 获取某格的棋子 */
    at(row, col) {
        if (row < 0 || row > 7 || col < 0 || col > 7) return null;
        return this.board[row][col];
    }

    /** 当前回合颜色 */
    get turn() { return this._turn; }

    /** 游戏是否结束 */
    get isGameOver() { return this._gameOver; }

    /** 结果 */
    get result() { return this._result; } // 'white', 'black', 'draw', null

    // ── 走法 ────────────────────────────────────────────────

    /**
     * 尝试走棋
     * @returns {{ success: boolean, captured?: object, promotion?: boolean, check?: boolean, checkmate?: boolean }}
     */
    move(mv) {
        const from = Array.isArray(mv.from) ? mv.from : [mv.from.row, mv.from.col];
        const to = Array.isArray(mv.to) ? mv.to : [mv.to.row, mv.to.col];
        const promotion = mv.promotion || 'Q';

        // 验证
        const piece = this.at(from[0], from[1]);
        if (!piece) return { success: false, error: '没有棋子' };
        if (piece.color !== this._turn) return { success: false, error: '不是你的回合' };

        const legalMoves = this.getLegalMoves(from);
        const match = legalMoves.find(m =>
            m.to[0] === to[0] && m.to[1] === to[1]
            && (m.promotion || 'Q') === promotion
        );
        if (!match) return { success: false, error: '非法走法' };

        // 执行
        const captured = this._executeMove(from, to, promotion, match);
        this._turn = this._turn === WHITE ? BLACK : WHITE;
        this._halfMoveClock++;
        this._fullMoveNumber++;

        // 检查对方状态
        const inCheck = this._isInCheck(this._turn);
        const hasLegalMove = this._hasAnyLegalMove(this._turn);

        if (!hasLegalMove) {
            this._gameOver = true;
            if (inCheck) {
                this._result = this._turn === WHITE ? BLACK : WHITE;
                return { success: true, captured, checkmate: true, winner: this._result };
            } else {
                this._result = 'draw';
                return { success: true, captured, stalemate: true };
            }
        }

        if (inCheck) {
            return { success: true, captured, check: true };
        }

        return { success: true, captured };
    }

    /**
     * 获取某位置棋子的所有合法走法
     * @returns Array<{ to: [row,col], promotion?: string }>
     */
    getLegalMoves(pos) {
        const piece = this.at(pos[0], pos[1]);
        if (!piece) return [];

        const candidates = this._getCandidateMoves(pos, piece);
        // 过滤掉会让自己被将军的走法
        return candidates.filter(m => !this._wouldBeInCheck(pos, m.to, piece));
    }

    /** 获取所有合法走法 */
    getAllLegalMoves() {
        const moves = [];
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const piece = this.at(r, c);
                if (piece && piece.color === this._turn) {
                    const legals = this.getLegalMoves([r, c]);
                    for (const m of legals) {
                        moves.push({ from: [r, c], to: m.to, promotion: m.promotion });
                    }
                }
            }
        }
        return moves;
    }

    /** 检查某方是否被将军 */
    isInCheck(color) {
        return this._isInCheck(color);
    }

    // ── 序列化 ──────────────────────────────────────────────

    /** 导出 FEN */
    fen() {
        let fen = '';
        for (let r = 0; r < 8; r++) {
            let empty = 0;
            for (let c = 0; c < 8; c++) {
                const p = this.board[r][c];
                if (!p) {
                    empty++;
                } else {
                    if (empty > 0) { fen += empty; empty = 0; }
                    const ch = { king: 'K', queen: 'Q', rook: 'R', bishop: 'B', knight: 'N', pawn: 'P' }[p.type];
                    fen += p.color === WHITE ? ch : ch.toLowerCase();
                }
            }
            if (empty > 0) fen += empty;
            if (r < 7) fen += '/';
        }

        fen += ' ' + (this._turn === WHITE ? 'w' : 'b') + ' ';

        let castle = '';
        if (this._castling.wK) castle += 'K';
        if (this._castling.wQ) castle += 'Q';
        if (this._castling.bK) castle += 'k';
        if (this._castling.bQ) castle += 'q';
        fen += (castle || '-') + ' ';

        if (this._enPassant) {
            fen += String.fromCharCode(97 + this._enPassant[1]) + (8 - this._enPassant[0]);
        } else {
            fen += '-';
        }

        fen += ' ' + this._halfMoveClock + ' ' + this._fullMoveNumber;
        return fen;
    }

    /** 导出简洁棋盘字符串（调试用） */
    boardString() {
        const map = { king: 'K', queen: 'Q', rook: 'R', bishop: 'B', knight: 'N', pawn: 'P' };
        let s = '  a b c d e f g h\n';
        for (let r = 0; r < 8; r++) {
            s += (8 - r) + ' ';
            for (let c = 0; c < 8; c++) {
                const p = this.board[r][c];
                if (!p) s += '. ';
                else {
                    const ch = map[p.type];
                    s += (p.color === WHITE ? ch : ch.toLowerCase()) + ' ';
                }
            }
            s += (8 - r) + '\n';
        }
        s += '  a b c d e f g h';
        return s;
    }

    // ── 内部: FEN 解析 ──────────────────────────────────────

    _loadFEN(fen) {
        const parts = fen.split(' ');
        const boardStr = parts[0];
        this._turn = parts[1] === 'w' ? WHITE : BLACK;
        const castleStr = parts[2] || '-';
        const epStr = parts[3] || '-';
        this._halfMoveClock = parseInt(parts[4] || '0');
        this._fullMoveNumber = parseInt(parts[5] || '1');

        this.board = Array(8).fill(null).map(() => Array(8).fill(null));
        const rows = boardStr.split('/');
        for (let r = 0; r < 8; r++) {
            let c = 0;
            for (const ch of rows[r]) {
                if (ch >= '1' && ch <= '8') {
                    c += parseInt(ch);
                } else {
                    const color = ch === ch.toUpperCase() ? WHITE : BLACK;
                    const typeMap = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };
                    this.board[r][c] = { type: typeMap[ch.toLowerCase()], color };
                    c++;
                }
            }
        }

        this._castling = {
            wK: castleStr.includes('K'),
            wQ: castleStr.includes('Q'),
            bK: castleStr.includes('k'),
            bQ: castleStr.includes('q'),
        };

        if (epStr !== '-') {
            this._enPassant = [8 - parseInt(epStr[1]), epStr.charCodeAt(0) - 97];
        } else {
            this._enPassant = null;
        }

        this._gameOver = false;
        this._result = null;
        this._moveHistory = [];
    }

    // ── 内部: 候选走法 (不含将军检查) ─────────────────────────

    _getCandidateMoves(pos, piece) {
        switch (piece.type) {
            case 'king':   return this._kingMoves(pos, piece);
            case 'queen':  return this._slidingMoves(pos, piece, [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]]);
            case 'rook':   return this._slidingMoves(pos, piece, [[1,0],[-1,0],[0,1],[0,-1]]);
            case 'bishop': return this._slidingMoves(pos, piece, [[1,1],[-1,-1],[1,-1],[-1,1]]);
            case 'knight': return this._knightMoves(pos, piece);
            case 'pawn':   return this._pawnMoves(pos, piece);
            default:       return [];
        }
    }

    _kingMoves([r, c], piece) {
        const moves = [];
        const dirs = [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]];
        for (const [dr, dc] of dirs) {
            const nr = r + dr, nc = c + dc;
            if (nr < 0 || nr > 7 || nc < 0 || nc > 7) continue;
            const target = this.board[nr][nc];
            if (!target || target.color !== piece.color) {
                moves.push({ to: [nr, nc] });
            }
        }

        // 王车易位
        if (piece.color === WHITE && r === 7 && c === 4) {
            if (this._castling.wK && !this.board[7][5] && !this.board[7][6]
                && this.board[7][7]?.type === 'rook' && this.board[7][7]?.color === WHITE) {
                if (!this._isSquareAttacked([7,4], BLACK) && !this._isSquareAttacked([7,5], BLACK) && !this._isSquareAttacked([7,6], BLACK)) {
                    moves.push({ to: [7, 6] }); // O-O
                }
            }
            if (this._castling.wQ && !this.board[7][3] && !this.board[7][2] && !this.board[7][1]
                && this.board[7][0]?.type === 'rook' && this.board[7][0]?.color === WHITE) {
                if (!this._isSquareAttacked([7,4], BLACK) && !this._isSquareAttacked([7,3], BLACK) && !this._isSquareAttacked([7,2], BLACK)) {
                    moves.push({ to: [7, 2] }); // O-O-O
                }
            }
        }
        if (piece.color === BLACK && r === 0 && c === 4) {
            if (this._castling.bK && !this.board[0][5] && !this.board[0][6]
                && this.board[0][7]?.type === 'rook' && this.board[0][7]?.color === BLACK) {
                if (!this._isSquareAttacked([0,4], WHITE) && !this._isSquareAttacked([0,5], WHITE) && !this._isSquareAttacked([0,6], WHITE)) {
                    moves.push({ to: [0, 6] });
                }
            }
            if (this._castling.bQ && !this.board[0][3] && !this.board[0][2] && !this.board[0][1]
                && this.board[0][0]?.type === 'rook' && this.board[0][0]?.color === BLACK) {
                if (!this._isSquareAttacked([0,4], WHITE) && !this._isSquareAttacked([0,3], WHITE) && !this._isSquareAttacked([0,2], WHITE)) {
                    moves.push({ to: [0, 2] });
                }
            }
        }

        return moves;
    }

    _queenMoves(pos, piece) {
        return this._slidingMoves(pos, piece, [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]]);
    }

    _slidingMoves([r, c], piece, dirs) {
        const moves = [];
        for (const [dr, dc] of dirs) {
            for (let i = 1; i < 8; i++) {
                const nr = r + dr * i, nc = c + dc * i;
                if (nr < 0 || nr > 7 || nc < 0 || nc > 7) break;
                const target = this.board[nr][nc];
                if (!target) {
                    moves.push({ to: [nr, nc] });
                } else {
                    if (target.color !== piece.color) moves.push({ to: [nr, nc] });
                    break;
                }
            }
        }
        return moves;
    }

    _knightMoves([r, c], piece) {
        const moves = [];
        const jumps = [[2,1],[2,-1],[-2,1],[-2,-1],[1,2],[1,-2],[-1,2],[-1,-2]];
        for (const [dr, dc] of jumps) {
            const nr = r + dr, nc = c + dc;
            if (nr < 0 || nr > 7 || nc < 0 || nc > 7) continue;
            const target = this.board[nr][nc];
            if (!target || target.color !== piece.color) {
                moves.push({ to: [nr, nc] });
            }
        }
        return moves;
    }

    _pawnMoves([r, c], piece) {
        const moves = [];
        const dir = piece.color === WHITE ? -1 : 1;
        const startRow = piece.color === WHITE ? 6 : 1;
        const promoRow = piece.color === WHITE ? 0 : 7;

        // 前进一格
        const fwd = r + dir;
        if (fwd >= 0 && fwd <= 7 && !this.board[fwd][c]) {
            if (fwd === promoRow) {
                for (const p of ['Q', 'R', 'B', 'N']) moves.push({ to: [fwd, c], promotion: p });
            } else {
                moves.push({ to: [fwd, c] });
            }
            // 前进两格
            const fwd2 = r + dir * 2;
            if (r === startRow && !this.board[fwd2][c]) {
                moves.push({ to: [fwd2, c] });
            }
        }

        // 吃子
        for (const dc of [-1, 1]) {
            const nc = c + dc;
            if (nc < 0 || nc > 7) continue;
            const target = this.board[fwd][nc];
            if (target && target.color !== piece.color) {
                if (fwd === promoRow) {
                    for (const p of ['Q', 'R', 'B', 'N']) moves.push({ to: [fwd, nc], promotion: p });
                } else {
                    moves.push({ to: [fwd, nc] });
                }
            }
            // 吃过路兵
            if (this._enPassant && fwd === this._enPassant[0] && nc === this._enPassant[1]) {
                moves.push({ to: [fwd, nc] });
            }
        }

        return moves;
    }

    // ── 内部: 将军检测 ──────────────────────────────────────

    _isInCheck(color) {
        // 找到己方王
        let kingPos = null;
        for (let r = 0; r < 8 && !kingPos; r++) {
            for (let c = 0; c < 8; c++) {
                const p = this.board[r][c];
                if (p && p.type === 'king' && p.color === color) {
                    kingPos = [r, c];
                    break;
                }
            }
        }
        if (!kingPos) return true; // 王不见了 = 被吃掉 = 将军
        return this._isSquareAttacked(kingPos, color === WHITE ? BLACK : WHITE);
    }

    _isSquareAttacked(pos, byColor) {
        const [r, c] = pos;
        // 检查所有对方棋子的攻击
        const enemy = byColor;

        // 兵
        const pawnDir = enemy === WHITE ? 1 : -1;
        for (const dc of [-1, 1]) {
            const tr = r + pawnDir, tc = c + dc;
            if (tr >= 0 && tr <= 7 && tc >= 0 && tc <= 7) {
                const p = this.board[tr][tc];
                if (p && p.type === 'pawn' && p.color === enemy) return true;
            }
        }

        // 马
        const jumps = [[2,1],[2,-1],[-2,1],[-2,-1],[1,2],[1,-2],[-1,2],[-1,-2]];
        for (const [dr, dc] of jumps) {
            const tr = r + dr, tc = c + dc;
            if (tr >= 0 && tr <= 7 && tc >= 0 && tc <= 7) {
                const p = this.board[tr][tc];
                if (p && p.type === 'knight' && p.color === enemy) return true;
            }
        }

        // 王
        const kingDirs = [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]];
        for (const [dr, dc] of kingDirs) {
            const tr = r + dr, tc = c + dc;
            if (tr >= 0 && tr <= 7 && tc >= 0 && tc <= 7) {
                const p = this.board[tr][tc];
                if (p && p.type === 'king' && p.color === enemy) return true;
            }
        }

        // 车/后 (直线)
        for (const [dr, dc] of [[1,0],[-1,0],[0,1],[0,-1]]) {
            for (let i = 1; i < 8; i++) {
                const tr = r + dr * i, tc = c + dc * i;
                if (tr < 0 || tr > 7 || tc < 0 || tc > 7) break;
                const p = this.board[tr][tc];
                if (p) {
                    if ((p.type === 'rook' || p.type === 'queen') && p.color === enemy) return true;
                    break;
                }
            }
        }

        // 象/后 (斜线)
        for (const [dr, dc] of [[1,1],[-1,-1],[1,-1],[-1,1]]) {
            for (let i = 1; i < 8; i++) {
                const tr = r + dr * i, tc = c + dc * i;
                if (tr < 0 || tr > 7 || tc < 0 || tc > 7) break;
                const p = this.board[tr][tc];
                if (p) {
                    if ((p.type === 'bishop' || p.type === 'queen') && p.color === enemy) return true;
                    break;
                }
            }
        }

        return false;
    }

    _wouldBeInCheck(from, to, piece) {
        // 模拟走法
        const captured = this.board[to[0]][to[1]];
        const prevEnPassant = this._enPassant;
        const prevCastling = { ...this._castling };

        // 更新吃过的过路兵
        if (piece.type === 'pawn' && this._enPassant && to[0] === this._enPassant[0] && to[1] === this._enPassant[1]) {
            const epRow = piece.color === WHITE ? to[0] + 1 : to[0] - 1;
            this.board[epRow][to[1]] = null;
        }

        this.board[from[0]][from[1]] = null;
        this.board[to[0]][to[1]] = piece;
        this._enPassant = null;

        const inCheck = this._isInCheck(piece.color);

        // 还原
        this.board[from[0]][from[1]] = piece;
        this.board[to[0]][to[1]] = captured;
        this._enPassant = prevEnPassant;
        this._castling = prevCastling;

        return inCheck;
    }

    _hasAnyLegalMove(color) {
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const p = this.board[r][c];
                if (p && p.color === color) {
                    if (this.getLegalMoves([r, c]).length > 0) return true;
                }
            }
        }
        return false;
    }

    // ── 内部: 执行走法 ───────────────────────────────────────

    _executeMove(from, to, promotion, match) {
        const piece = this.board[from[0]][from[1]];
        const captured = this.board[to[0]][to[1]];

        this._moveHistory.push({
            piece, from, to, captured,
            enPassant: this._enPassant,
            castling: { ...this._castling },
            halfMoveClock: this._halfMoveClock,
        });

        // 移动棋子
        this.board[from[0]][from[1]] = null;
        this.board[to[0]][to[1]] = piece;

        // 升变
        if (match.promotion) {
            const typeMap = { Q: 'queen', R: 'rook', B: 'bishop', N: 'knight' };
            this.board[to[0]][to[1]] = { type: typeMap[match.promotion], color: piece.color };
        }

        // 吃过路兵
        if (piece.type === 'pawn' && this._enPassant && to[0] === this._enPassant[0] && to[1] === this._enPassant[1]) {
            const epRow = piece.color === WHITE ? to[0] + 1 : to[0] - 1;
            this.board[epRow][to[1]] = null;
        }

        // 更新过路兵
        this._enPassant = null;
        if (piece.type === 'pawn' && Math.abs(to[0] - from[0]) === 2) {
            this._enPassant = [(from[0] + to[0]) / 2, from[1]];
        }

        // 更新易位权
        if (piece.type === 'king') {
            if (piece.color === WHITE) { this._castling.wK = false; this._castling.wQ = false; }
            else { this._castling.bK = false; this._castling.bQ = false; }
        }
        if (piece.type === 'rook') {
            if (from[0] === 7 && from[1] === 0) this._castling.wQ = false;
            if (from[0] === 7 && from[1] === 7) this._castling.wK = false;
            if (from[0] === 0 && from[1] === 0) this._castling.bQ = false;
            if (from[0] === 0 && from[1] === 7) this._castling.bK = false;
        }

        // 王车易位 — 移动车
        if (piece.type === 'king' && Math.abs(to[1] - from[1]) === 2) {
            const rookFromCol = to[1] === 6 ? 7 : 0;
            const rookToCol = to[1] === 6 ? 5 : 3;
            const rook = this.board[to[0]][rookFromCol];
            this.board[to[0]][rookFromCol] = null;
            this.board[to[0]][rookToCol] = rook;
        }

        return captured;
    }

    /** 悔棋 */
    undo() {
        if (this._moveHistory.length === 0) return false;
        const last = this._moveHistory.pop();
        this.board[last.from[0]][last.from[1]] = last.piece;
        this.board[last.to[0]][last.to[1]] = last.captured;
        this._enPassant = last.enPassant;
        this._castling = last.castling;
        this._halfMoveClock = last.halfMoveClock;
        this._turn = this._turn === WHITE ? BLACK : WHITE;
        this._gameOver = false;
        this._result = null;
        return true;
    }
}

export { ChessGame, WHITE, BLACK };
