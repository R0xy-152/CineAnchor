/**
 * AnchorVerse — AI 物件生成器
 * 自然语言 → 程序化 3D 几何体 (客户端, 零 API 成本)
 *
 * 用法: generateFromPrompt("一个红木圆桌")
 * 返回: THREE.Group
 */
import * as THREE from 'three';

// ── 材质映射 ──────────────────────────────────────────────

const MATERIAL_MAP = {
    wood:       () => new THREE.MeshStandardMaterial({ color: 0x8b6914, roughness: 0.7 }),
    redwood:    () => new THREE.MeshStandardMaterial({ color: 0x8b3a3a, roughness: 0.6 }),
    stone:      () => new THREE.MeshStandardMaterial({ color: 0x999999, roughness: 0.9 }),
    metal:      () => new THREE.MeshStandardMaterial({ color: 0xcccccc, roughness: 0.3, metalness: 0.8 }),
    gold:       () => new THREE.MeshStandardMaterial({ color: 0xffcc00, roughness: 0.2, metalness: 0.9 }),
    glass:      () => new THREE.MeshStandardMaterial({ color: 0xddeeff, roughness: 0.1, transparent: true, opacity: 0.6 }),
    marble:     () => new THREE.MeshStandardMaterial({ color: 0xf5f5f0, roughness: 0.3 }),
    brick:      () => new THREE.MeshStandardMaterial({ color: 0xaa5533, roughness: 0.9 }),
    red:        () => new THREE.MeshStandardMaterial({ color: 0xcc3333, roughness: 0.5 }),
    blue:       () => new THREE.MeshStandardMaterial({ color: 0x3355cc, roughness: 0.5 }),
    green:      () => new THREE.MeshStandardMaterial({ color: 0x33aa55, roughness: 0.5 }),
    yellow:     () => new THREE.MeshStandardMaterial({ color: 0xffcc00, roughness: 0.5 }),
    purple:     () => new THREE.MeshStandardMaterial({ color: 0x8833cc, roughness: 0.5 }),
    black:      () => new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.5 }),
    white:      () => new THREE.MeshStandardMaterial({ color: 0xf0f0f0, roughness: 0.5 }),
    pink:       () => new THREE.MeshStandardMaterial({ color: 0xff88aa, roughness: 0.5 }),
    orange:     () => new THREE.MeshStandardMaterial({ color: 0xff8800, roughness: 0.5 }),
};

// ── 关键词 → 材质解析 ─────────────────────────────────────

function _parseMaterial(prompt) {
    const lower = prompt.toLowerCase();
    if (lower.includes('红木')) return MATERIAL_MAP.redwood();
    if (lower.includes('木')) return MATERIAL_MAP.wood();
    if (lower.includes('石') || lower.includes('石头')) return MATERIAL_MAP.stone();
    if (lower.includes('金属') || lower.includes('铁') || lower.includes('钢')) return MATERIAL_MAP.metal();
    if (lower.includes('金') || lower.includes('黄金')) return MATERIAL_MAP.gold();
    if (lower.includes('玻璃') || lower.includes('透明')) return MATERIAL_MAP.glass();
    if (lower.includes('大理石')) return MATERIAL_MAP.marble();
    if (lower.includes('砖')) return MATERIAL_MAP.brick();
    if (lower.includes('红色') || lower.includes('红')) return MATERIAL_MAP.red();
    if (lower.includes('蓝色') || lower.includes('蓝')) return MATERIAL_MAP.blue();
    if (lower.includes('绿色') || lower.includes('绿')) return MATERIAL_MAP.green();
    if (lower.includes('黄色') || lower.includes('黄')) return MATERIAL_MAP.yellow();
    if (lower.includes('紫色') || lower.includes('紫')) return MATERIAL_MAP.purple();
    if (lower.includes('黑色') || lower.includes('黑')) return MATERIAL_MAP.black();
    if (lower.includes('白色') || lower.includes('白')) return MATERIAL_MAP.white();
    if (lower.includes('粉色') || lower.includes('粉')) return MATERIAL_MAP.pink();
    if (lower.includes('橙色') || lower.includes('橙')) return MATERIAL_MAP.orange();
    return MATERIAL_MAP.wood(); // 默认木质
}

// ── 尺寸解析 ──────────────────────────────────────────────

function _parseScale(prompt) {
    const s = { w: 0.5, h: 0.5, d: 0.5 };
    if (prompt.includes('大') || prompt.includes('巨大')) { s.w = 1.5; s.h = 1.5; s.d = 1.5; }
    if (prompt.includes('小') || prompt.includes('迷你')) { s.w = 0.2; s.h = 0.2; s.d = 0.2; }
    if (prompt.includes('高') || prompt.includes('长')) { s.h = 1.0; s.w = 0.3; s.d = 0.3; }
    if (prompt.includes('宽')) { s.w = 1.0; s.d = 1.0; s.h = 0.3; }
    if (prompt.includes('扁') || prompt.includes('薄')) { s.h = 0.1; }
    if (prompt.includes('细')) { s.w = 0.1; s.d = 0.1; }
    return s;
}

// ── 腿数解析 ──────────────────────────────────────────────

function _parseLegCount(prompt) {
    if (prompt.includes('三腿') || prompt.includes('三条腿')) return 3;
    if (prompt.includes('四腿') || prompt.includes('四条腿')) return 4;
    if (prompt.includes('独腿') || prompt.includes('一条腿')) return 1;
    return 4; // 默认 4
}

// ── 基础图元 ──────────────────────────────────────────────

function _box(w, h, d, mat) {
    return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
}

function _cylinder(rTop, rBot, h, mat, seg = 16) {
    return new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg), mat);
}

function _sphere(r, mat, seg = 16) {
    return new THREE.Mesh(new THREE.SphereGeometry(r, seg, seg), mat);
}

function _cone(r, h, mat, seg = 16) {
    return new THREE.Mesh(new THREE.ConeGeometry(r, h, seg), mat);
}

// ── 物件生成器 ────────────────────────────────────────────

function _makeTable(mat, prompt) {
    const group = new THREE.Group();
    const legCount = _parseLegCount(prompt);
    const isRound = prompt.includes('圆');
    const isBig = prompt.includes('大');

    const topSize = isBig ? 0.8 : 0.5;
    const topH = 0.06;
    const legH = isBig ? 0.7 : 0.5;
    const legR = 0.03;

    // 桌面
    let top;
    if (isRound) {
        top = _cylinder(topSize, topSize, topH, mat, 24);
    } else {
        top = _box(topSize * 2, topH, topSize * 2, mat);
    }
    top.position.y = legH;
    top.castShadow = true;
    top.receiveShadow = true;
    group.add(top);

    // 桌腿
    const radius = isRound ? topSize * 0.75 : topSize * 0.7;
    for (let i = 0; i < legCount; i++) {
        const angle = (i / legCount) * Math.PI * 2 + (legCount === 3 ? Math.PI / 6 : Math.PI / 4);
        const leg = _cylinder(legR, legR, legH, mat);
        leg.position.set(Math.cos(angle) * radius, legH / 2, Math.sin(angle) * radius);
        leg.castShadow = true;
        group.add(leg);
    }

    return group;
}

function _makeChair(mat, prompt) {
    const group = new THREE.Group();
    const seatH = 0.45;
    const seatSize = 0.25;

    // 座面
    const seat = _box(seatSize * 2, 0.04, seatSize * 2, mat);
    seat.position.y = seatH;
    seat.castShadow = true;
    group.add(seat);

    // 四腿
    const legR = 0.03;
    const offset = seatSize - 0.03;
    for (const [x, z] of [[-offset, -offset], [offset, -offset], [-offset, offset], [offset, offset]]) {
        const leg = _cylinder(legR, legR, seatH, mat);
        leg.position.set(x, seatH / 2, z);
        leg.castShadow = true;
        group.add(leg);
    }

    // 靠背
    const back = _box(seatSize * 2, 0.35, 0.04, mat);
    back.position.set(0, seatH + 0.2, -seatSize);
    back.castShadow = true;
    group.add(back);

    return group;
}

function _makeLamp(mat, prompt) {
    const group = new THREE.Group();
    // 底座
    const base = _cylinder(0.12, 0.15, 0.05, mat, 16);
    base.position.y = 0.02;
    base.castShadow = true;
    group.add(base);
    // 杆
    const pole = _cylinder(0.025, 0.025, 0.8, mat);
    pole.position.y = 0.4;
    pole.castShadow = true;
    group.add(pole);
    // 灯罩
    const shadeMat = new THREE.MeshStandardMaterial({
        color: 0xffeedd, roughness: 0.3,
        emissive: 0xffddaa, emissiveIntensity: 0.3,
    });
    const shade = _cone(0.15, 0.2, shadeMat, 16);
    shade.position.y = 0.85;
    group.add(shade);

    return group;
}

function _makeTree(mat, prompt) {
    const group = new THREE.Group();
    const trunkMat = MATERIAL_MAP.wood();
    const leafMat = new THREE.MeshStandardMaterial({ color: 0x2d6b2a, roughness: 0.8 });

    const trunk = _cylinder(0.08, 0.12, 1.5, trunkMat);
    trunk.position.y = 0.75;
    trunk.castShadow = true;
    group.add(trunk);

    for (let i = 0; i < 3; i++) {
        const crown = _cone(0.35 + i * 0.15, 0.6, leafMat, 8);
        crown.position.y = 1.2 + i * 0.4;
        crown.castShadow = true;
        group.add(crown);
    }

    return group;
}

function _makeHouse(mat, prompt) {
    const group = new THREE.Group();
    const wallMat = mat;
    const roofMat = new THREE.MeshStandardMaterial({ color: 0x993333, roughness: 0.7 });

    // 主体
    const body = _box(1.0, 0.8, 0.8, wallMat);
    body.position.y = 0.4;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    // 屋顶
    const roofGeom = new THREE.ConeGeometry(0.7, 0.5, 4);
    const roof = new THREE.Mesh(roofGeom, roofMat);
    roof.position.y = 1.0;
    roof.rotation.y = Math.PI / 4;
    roof.castShadow = true;
    group.add(roof);

    // 门
    const door = _box(0.16, 0.35, 0.02, new THREE.MeshStandardMaterial({ color: 0x5c3a1e, roughness: 0.6 }));
    door.position.set(0, 0.18, 0.4);
    group.add(door);

    return group;
}

function _makeTower(mat, prompt) {
    const group = new THREE.Group();
    const body = _cylinder(0.25, 0.35, 2.0, mat);
    body.position.y = 1.0;
    body.castShadow = true;
    group.add(body);

    const top = _cone(0.35, 0.4, mat, 8);
    top.position.y = 2.1;
    top.castShadow = true;
    group.add(top);

    // 窗户环
    for (let i = 0; i < 4; i++) {
        const angle = (i / 4) * Math.PI * 2;
        const win = _box(0.08, 0.12, 0.02, new THREE.MeshStandardMaterial({ color: 0xffff88, emissive: 0x444400, emissiveIntensity: 0.5 }));
        win.position.set(Math.cos(angle) * 0.3, 1.5, Math.sin(angle) * 0.3);
        win.rotation.y = -angle;
        group.add(win);
    }

    return group;
}

function _makeWall(mat, prompt) {
    const group = new THREE.Group();
    const len = prompt.includes('长') ? 3.0 : 1.5;
    const wall = _box(len, 1.2, 0.15, mat);
    wall.position.y = 0.6;
    wall.castShadow = true;
    wall.receiveShadow = true;
    group.add(wall);
    return group;
}

function _makeFence(mat, prompt) {
    const group = new THREE.Group();
    const count = 6;
    const spacing = 0.25;
    const totalLen = count * spacing;

    for (let i = 0; i < count; i++) {
        const post = _cylinder(0.03, 0.03, 0.7, mat);
        post.position.set(-totalLen / 2 + i * spacing, 0.35, 0);
        post.castShadow = true;
        group.add(post);
    }
    // 横杆
    for (let yOff of [0.2, 0.55]) {
        const rail = _box(totalLen, 0.04, 0.04, mat);
        rail.position.y = yOff;
        rail.castShadow = true;
        group.add(rail);
    }

    return group;
}

function _makeBridge(mat, prompt) {
    const group = new THREE.Group();
    const len = prompt.includes('长') ? 2.5 : 1.5;

    // 桥面
    const deck = _box(len, 0.06, 0.5, mat);
    deck.position.y = 0.3;
    deck.receiveShadow = true;
    group.add(deck);

    // 栏杆
    for (const z of [-0.23, 0.23]) {
        for (let x = -len / 2; x <= len / 2; x += 0.3) {
            const post = _cylinder(0.02, 0.02, 0.2, mat);
            post.position.set(x, 0.4, z);
            group.add(post);
        }
        const rail = _box(len, 0.03, 0.03, mat);
        rail.position.set(0, 0.5, z);
        group.add(rail);
    }

    return group;
}

function _makeVase(mat, prompt) {
    const group = new THREE.Group();
    // 瓶身
    const body = new THREE.Mesh(new THREE.LatheGeometry([
        new THREE.Vector2(0, 0),
        new THREE.Vector2(0.05, 0.05),
        new THREE.Vector2(0.15, 0.2),
        new THREE.Vector2(0.12, 0.4),
        new THREE.Vector2(0.14, 0.55),
        new THREE.Vector2(0.1, 0.7),
        new THREE.Vector2(0.06, 0.85),
        new THREE.Vector2(0.04, 0.9),
    ], 24), mat);
    body.castShadow = true;
    group.add(body);

    return group;
}

function _makeSculpture(mat, prompt) {
    const group = new THREE.Group();
    // 抽象雕塑：多个旋转的环
    for (let i = 0; i < 3; i++) {
        const ringGeom = new THREE.TorusGeometry(0.15 + i * 0.06, 0.03, 8, 16);
        const ring = new THREE.Mesh(ringGeom, mat);
        ring.position.y = 0.3 + i * 0.15;
        ring.rotation.x = Math.random() * Math.PI;
        ring.rotation.y = Math.random() * Math.PI;
        group.add(ring);
    }
    return group;
}

function _makeBookshelf(mat, prompt) {
    const group = new THREE.Group();
    const h = 1.2, w = 0.8, d = 0.25;

    // 外框
    const sides = [
        _box(0.04, h, d, mat),  // 左
        _box(0.04, h, d, mat),  // 右
        _box(w, 0.04, d, mat),  // 顶
        _box(w, 0.04, d, mat),  // 底
    ];
    sides[0].position.set(-w / 2, h / 2, 0);
    sides[1].position.set(w / 2, h / 2, 0);
    sides[2].position.set(0, h, 0);
    sides[3].position.set(0, 0.02, 0);
    for (const s of sides) { s.castShadow = true; group.add(s); }

    // 隔板
    for (let i = 1; i <= 3; i++) {
        const shelf = _box(w - 0.08, 0.02, d, mat);
        shelf.position.y = i * 0.28;
        shelf.castShadow = true;
        group.add(shelf);
    }

    return group;
}

function _makeChest(mat, prompt) {
    const group = new THREE.Group();
    const body = _box(0.6, 0.4, 0.35, mat);
    body.position.y = 0.2;
    body.castShadow = true;
    group.add(body);

    // 盖子 (微弧形 → 用半个圆柱)
    const lidGeom = new THREE.CylinderGeometry(0.18, 0.18, 0.6, 16, 1, false, 0, Math.PI);
    const lid = new THREE.Mesh(lidGeom, mat);
    lid.position.y = 0.4;
    lid.rotation.z = Math.PI / 2;
    group.add(lid);

    // 锁扣
    const lock = _box(0.06, 0.08, 0.04, new THREE.MeshStandardMaterial({ color: 0xffcc00, roughness: 0.3, metalness: 0.8 }));
    lock.position.set(0, 0.42, 0.18);
    group.add(lock);

    return group;
}

function _makeFountain(mat, prompt) {
    const group = new THREE.Group();
    const poolGeom = new THREE.CylinderGeometry(0.4, 0.5, 0.2, 24);
    const poolMat = new THREE.MeshStandardMaterial({ color: 0x999999, roughness: 0.5 });
    const pool = new THREE.Mesh(poolGeom, poolMat);
    pool.position.y = 0.1;
    pool.receiveShadow = true;
    group.add(pool);

    // 中心柱
    const pillar = _cylinder(0.06, 0.08, 0.5, poolMat);
    pillar.position.y = 0.35;
    group.add(pillar);

    // 顶部碗
    const bowl = new THREE.Mesh(
        new THREE.SphereGeometry(0.15, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2),
        poolMat
    );
    bowl.position.y = 0.6;
    group.add(bowl);

    return group;
}

function _makeThrone(mat, prompt) {
    const group = new THREE.Group();
    // 底座
    const base = _box(0.6, 0.1, 0.5, mat);
    base.position.y = 0.05;
    group.add(base);
    // 座面
    const seat = _box(0.5, 0.08, 0.4, mat);
    seat.position.y = 0.4;
    group.add(seat);
    // 靠背
    const back = _box(0.5, 0.8, 0.06, mat);
    back.position.set(0, 0.8, -0.18);
    back.castShadow = true;
    group.add(back);
    // 扶手
    for (const z of [-0.2, 0.2]) {
        const arm = _box(0.5, 0.06, 0.06, mat);
        arm.position.set(0, 0.7, z);
        group.add(arm);
    }

    return group;
}

function _makeCandle(mat, prompt) {
    const group = new THREE.Group();
    const waxMat = new THREE.MeshStandardMaterial({ color: 0xffeedd, roughness: 0.5 });
    const body = _cylinder(0.04, 0.05, 0.2, waxMat);
    body.position.y = 0.1;
    group.add(body);

    const flameGeom = new THREE.SphereGeometry(0.03, 8, 8);
    const flameMat = new THREE.MeshBasicMaterial({ color: 0xffaa33 });
    const flame = new THREE.Mesh(flameGeom, flameMat);
    flame.position.y = 0.22;
    group.add(flame);

    return group;
}

function _makePillar(mat, prompt) {
    const group = new THREE.Group();
    const body = _cylinder(0.12, 0.15, 2.0, mat, 16);
    body.position.y = 1.0;
    body.castShadow = true;
    group.add(body);

    // 柱头
    const cap = _box(0.3, 0.1, 0.3, mat);
    cap.position.y = 2.05;
    group.add(cap);

    return group;
}

function _makeArch(mat, prompt) {
    const group = new THREE.Group();
    // 左柱
    const left = _box(0.12, 1.5, 0.12, mat);
    left.position.set(-0.4, 0.75, 0);
    left.castShadow = true;
    group.add(left);
    // 右柱
    const right = _box(0.12, 1.5, 0.12, mat);
    right.position.set(0.4, 0.75, 0);
    right.castShadow = true;
    group.add(right);
    // 拱顶
    const archGeom = new THREE.TorusGeometry(0.4, 0.06, 8, 16, Math.PI);
    const arch = new THREE.Mesh(archGeom, mat);
    arch.position.set(0, 1.5, 0);
    arch.rotation.y = Math.PI / 2;
    arch.rotation.z = Math.PI;
    group.add(arch);

    return group;
}

function _makeStatue(mat, prompt) {
    const group = new THREE.Group();
    // 底座
    const base = _box(0.3, 0.2, 0.3, mat);
    base.position.y = 0.1;
    group.add(base);
    // 身体
    const body = _box(0.12, 0.4, 0.1, mat);
    body.position.y = 0.4;
    group.add(body);
    // 头
    const head = _sphere(0.07, mat);
    head.position.y = 0.65;
    group.add(head);
    // 手臂
    for (const z of [-0.12, 0.12]) {
        const arm = _box(0.05, 0.25, 0.05, mat);
        arm.position.set(0, 0.42, z);
        group.add(arm);
    }

    return group;
}

function _makeWell(mat, prompt) {
    const group = new THREE.Group();
    const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.25, 0.06, 8, 24),
        mat
    );
    ring.position.y = 0.35;
    ring.rotation.x = Math.PI / 2;
    ring.castShadow = true;
    group.add(ring);

    const base = _cylinder(0.25, 0.25, 0.3, mat);
    base.position.y = 0.15;
    base.castShadow = true;
    group.add(base);

    return group;
}

// ── 默认生成：方块堆叠 ────────────────────────────────────

function _makeDefault(mat, prompt) {
    const group = new THREE.Group();
    const scale = _parseScale(prompt);

    const body = _box(scale.w, scale.h, scale.d, mat);
    body.position.y = scale.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    return group;
}

// ── 关键词 → 生成器路由 ───────────────────────────────────

const GENERATOR_MAP = [
    { keys: ['桌', 'table', '台'],              fn: _makeTable },
    { keys: ['椅', 'chair', '凳', '座'],         fn: _makeChair },
    { keys: ['灯', 'lamp', '光'],                fn: _makeLamp },
    { keys: ['树', 'tree'],                      fn: _makeTree },
    { keys: ['房', 'house', '屋'],               fn: _makeHouse },
    { keys: ['塔', 'tower', '楼'],               fn: _makeTower },
    { keys: ['墙', 'wall'],                      fn: _makeWall },
    { keys: ['栅栏', 'fence', '围栏', '篱笆'],    fn: _makeFence },
    { keys: ['桥', 'bridge'],                    fn: _makeBridge },
    { keys: ['花瓶', 'vase', '瓶'],              fn: _makeVase },
    { keys: ['雕塑', 'sculpture', '雕像'],        fn: _makeSculpture },
    { keys: ['书架', 'bookshelf', '书柜'],        fn: _makeBookshelf },
    { keys: ['宝箱', 'chest', '箱子', '柜'],      fn: _makeChest },
    { keys: ['喷泉', 'fountain', '泉'],           fn: _makeFountain },
    { keys: ['王座', 'throne', '宝座'],           fn: _makeThrone },
    { keys: ['蜡烛', 'candle'],                   fn: _makeCandle },
    { keys: ['柱子', 'pillar', '柱'],             fn: _makePillar },
    { keys: ['拱门', 'arch', '拱'],               fn: _makeArch },
    { keys: ['雕像', 'statue', '人像'],           fn: _makeStatue },
    { keys: ['井', 'well'],                      fn: _makeWell },
];

// ── 主入口 ────────────────────────────────────────────────

/**
 * 从 prompt 生成 3D 物件
 * @param {string} prompt — 中文描述, e.g. "一张红木圆桌"
 * @returns {{ group: THREE.Group, name: string, color: string }}
 */
function generateFromPrompt(prompt) {
    if (!prompt || !prompt.trim()) {
        return { group: _makeDefault(MATERIAL_MAP.wood(), '方块'), name: '默认方块', color: '#8b6914' };
    }

    const mat = _parseMaterial(prompt);

    // 匹配生成器
    for (const { keys, fn } of GENERATOR_MAP) {
        for (const k of keys) {
            if (prompt.includes(k)) {
                const group = fn(mat, prompt);
                const name = prompt.slice(0, 20);
                return { group, name, color: '#' + mat.color.getHexString() };
            }
        }
    }

    // 默认：几何体堆叠
    return {
        group: _makeDefault(mat, prompt),
        name: prompt.slice(0, 20),
        color: '#' + mat.color.getHexString(),
    };
}

export { generateFromPrompt };
