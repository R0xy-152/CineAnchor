/**
 * AnchorVerse — 第一人称编辑器
 * 物件拾取 / 放置 / 删除 + 物品栏 UI
 */
import * as THREE from 'three';

// ── 预置物件库 ────────────────────────────────────────────
const OBJECT_LIBRARY = [
    // 基础形状
    { key: 'cube_default', name: '方块', geom: () => new THREE.BoxGeometry(0.5, 0.5, 0.5), color: '#aaaaaa', cat: '基础' },
    { key: 'sphere_default', name: '球体', geom: () => new THREE.SphereGeometry(0.25, 16, 16), color: '#cccccc', cat: '基础' },
    { key: 'cylinder_default', name: '圆柱', geom: () => new THREE.CylinderGeometry(0.2, 0.2, 0.5, 16), color: '#bbbbbb', cat: '基础' },
    { key: 'cone_default', name: '圆锥', geom: () => new THREE.ConeGeometry(0.2, 0.5, 16), color: '#999999', cat: '基础' },

    // 家具
    { key: 'table_square', name: '方桌', geom: () => _table(), color: '#8b6914', cat: '家具' },
    { key: 'chair_wood', name: '椅子', geom: () => _chair(), color: '#8b6914', cat: '家具' },
    { key: 'bar_counter', name: '吧台', geom: () => new THREE.BoxGeometry(2, 0.6, 0.6), color: '#5c3a1e', cat: '家具' },
    { key: 'sofa', name: '沙发', geom: () => new THREE.BoxGeometry(1.5, 0.6, 0.7), color: '#4a4a6a', cat: '家具' },
    { key: 'shelf', name: '书架', geom: () => _shelf(), color: '#8b6914', cat: '家具' },

    // 容器/餐具
    { key: 'cup_tea', name: '茶杯', geom: () => new THREE.CylinderGeometry(0.08, 0.06, 0.12, 16), color: '#ffffff', cat: '餐具' },
    { key: 'wine_glass', name: '酒杯', geom: () => _wineGlass(), color: '#ddeeff', cat: '餐具' },
    { key: 'bottle', name: '酒瓶', geom: () => _bottle(), color: '#2d5a27', cat: '餐具' },
    { key: 'plate', name: '盘子', geom: () => new THREE.CylinderGeometry(0.18, 0.16, 0.03, 24), color: '#f5f5f5', cat: '餐具' },

    // 自然
    { key: 'tree_pine', name: '松树', geom: () => _tree(), color: '#2d5a27', cat: '自然' },
    { key: 'rock_large', name: '大石头', geom: () => new THREE.IcosahedronGeometry(0.3, 1), color: '#888888', cat: '自然' },
    { key: 'flower_red', name: '红花', geom: () => _flower(), color: '#ff3366', cat: '自然' },
    { key: 'bush', name: '灌木', geom: () => new THREE.SphereGeometry(0.25, 8, 6), color: '#3a6b2a', cat: '自然' },

    // 桌游
    { key: 'chess_pawn_white', name: '白兵', geom: () => _chessPawn(), color: '#f0f0e0', cat: '桌游' },
    { key: 'chess_pawn_black', name: '黑兵', geom: () => _chessPawn(), color: '#2a2a2a', cat: '桌游' },
    { key: 'dice', name: '骰子', geom: () => new THREE.BoxGeometry(0.15, 0.15, 0.15), color: '#ffffff', cat: '桌游' },
    { key: 'card', name: '卡牌', geom: () => new THREE.BoxGeometry(0.2, 0.005, 0.28), color: '#ffffff', cat: '桌游' },
    { key: 'poker_chip_red', name: '筹码', geom: () => new THREE.CylinderGeometry(0.1, 0.1, 0.03, 24), color: '#cc2222', cat: '桌游' },

    // 照明
    { key: 'lamp_ceiling', name: '吊灯', geom: () => _ceilingLamp(), color: '#ffdd88', cat: '照明' },
    { key: 'candle', name: '蜡烛', geom: () => new THREE.CylinderGeometry(0.03, 0.04, 0.15, 12), color: '#ffeedd', cat: '照明' },
    { key: 'floor_lamp', name: '落地灯', geom: () => _floorLamp(), color: '#dddddd', cat: '照明' },
];

// ── 物件生成器 ────────────────────────────────────────────

function _table() {
    const g = new THREE.Group();
    const top = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.05, 0.8));
    g.add(top);
    for (let x = -1; x <= 1; x += 2) {
        for (let z = -1; z <= 1; z += 2) {
            const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.6, 8));
            leg.position.set(x * 0.3, -0.32, z * 0.3);
            g.add(leg);
        }
    }
    return g;
}

function _chair() {
    const g = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.04, 0.35));
    seat.position.y = 0.3;
    g.add(seat);
    for (let x = -1; x <= 1; x += 2) {
        for (let z = -1; z <= 1; z += 2) {
            const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.32, 6));
            leg.position.set(x * 0.14, 0.14, z * 0.14);
            g.add(leg);
        }
    }
    const back = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.25, 0.03));
    back.position.set(0, 0.5, -0.16);
    g.add(back);
    return g;
}

function _shelf() {
    const g = new THREE.Group();
    for (let i = 0; i < 4; i++) {
        const shelf = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.03, 0.25));
        shelf.position.y = i * 0.3;
        g.add(shelf);
    }
    return g;
}

function _wineGlass() {
    const g = new THREE.Group();
    const bowl = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8));
    bowl.position.y = 0.14;
    bowl.scale.set(1, 0.7, 1);
    g.add(bowl);
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.1, 6));
    stem.position.y = 0.07;
    g.add(stem);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.05, 0.02, 12));
    base.position.y = 0.01;
    g.add(base);
    return g;
}

function _bottle() {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.2, 16));
    body.position.y = 0.1;
    g.add(body);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.03, 0.08, 12));
    neck.position.y = 0.24;
    g.add(neck);
    const lip = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.015, 12));
    lip.position.y = 0.29;
    g.add(lip);
    return g;
}

function _tree() {
    const g = new THREE.Group();
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.06, 0.6, 8));
    trunk.position.y = 0.3;
    g.add(trunk);
    for (let i = 0; i < 3; i++) {
        const foliage = new THREE.Mesh(new THREE.ConeGeometry(0.2 - i * 0.04, 0.3, 8));
        foliage.position.y = 0.55 + i * 0.18;
        g.add(foliage);
    }
    return g;
}

function _flower() {
    const g = new THREE.Group();
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.2, 6));
    stem.position.y = 0.1;
    g.add(stem);
    const petals = new THREE.Mesh(new THREE.SphereGeometry(0.05, 6, 3));
    petals.position.y = 0.22;
    g.add(petals);
    return g;
}

function _chessPawn() {
    const g = new THREE.Group();
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.03, 12));
    base.position.y = 0.015;
    g.add(base);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 0.08, 12));
    body.position.y = 0.07;
    g.add(body);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6));
    head.position.y = 0.12;
    g.add(head);
    return g;
}

function _ceilingLamp() {
    const g = new THREE.Group();
    const shade = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.25, 12, 1, true));
    shade.position.y = -0.05;
    shade.rotation.x = Math.PI;
    g.add(shade);
    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.3, 4));
    cord.position.y = 0.15;
    g.add(cord);
    return g;
}

function _floorLamp() {
    const g = new THREE.Group();
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.2, 8));
    pole.position.y = 0.6;
    g.add(pole);
    const shade = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.3, 12, 1, true));
    shade.position.y = 1.3;
    shade.rotation.x = Math.PI;
    g.add(shade);
    return g;
}

// ── 编辑器 ────────────────────────────────────────────────

class EditorMode {
    constructor(scene, camera, renderer, onPlace, onRemove) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        this._onPlace = onPlace;     // (assetKey, position, rotation) => WS
        this._onRemove = onRemove;   // (objId) => WS

        this.active = false;
        this.selectedAsset = 'cube_default';

        /** 场景中的物件 Map: objId -> THREE.Group */
        this.placedObjects = new Map();

        /** 半透明预览体 */
        this._ghost = null;
        this._ghostVisible = false;

        /** Raycaster */
        this._raycaster = new THREE.Raycaster();
        this._raycaster.far = 15;

        /** 鼠标 */
        this._mouse = new THREE.Vector2(0, 0);

        /** 物品栏 */
        this._inventoryEl = null;
        this._inventoryVisible = false;

        this._initGhost();
        this._initMouse();
    }

    // ── 公共 API ──────────────────────────────────────────

    /** 切换编辑模式 */
    toggle() {
        this.active = !this.active;
        if (this.active) {
            this._inventoryVisible = true;
            this._renderInventory();
        } else {
            this._inventoryVisible = false;
            if (this._inventoryEl) this._inventoryEl.style.display = 'none';
            if (this._ghost) this._ghost.visible = false;
        }
        return this.active;
    }

    /** 远程收到物件放置 */
    addRemoteObject(objId, assetKey, position, rotation) {
        const mesh = this._createObjectMesh(assetKey);
        mesh.position.set(position[0], position[1], position[2]);
        if (rotation) mesh.quaternion.set(rotation[0], rotation[1], rotation[2], rotation[3]);
        this.scene.add(mesh);
        this.placedObjects.set(objId, mesh);
    }

    /** 远程收到物件删除 */
    removeRemoteObject(objId) {
        const obj = this.placedObjects.get(objId);
        if (obj) {
            this.scene.remove(obj);
            obj.traverse(c => {
                if (c.geometry && c.geometry !== this._sharedGeom(c.geometry)) c.geometry.dispose();
                if (c.material) c.material.dispose();
            });
            this.placedObjects.delete(objId);
        }
    }

    /** 获取当前选中物件信息 */
    get selectedAssetInfo() {
        return OBJECT_LIBRARY.find(o => o.key === this.selectedAsset);
    }

    /** 每帧调用 */
    tick() {
        if (!this.active || !this._ghost) return;

        this._raycaster.setFromCamera(this._mouse, this.camera);
        const allTargets = [];
        for (const [, obj] of this.placedObjects) {
            allTargets.push(obj);
        }

        const hits = this._raycaster.intersectObjects(allTargets, true);
        if (hits.length > 0 && hits[0].distance < 10) {
            const point = hits[0].point;
            const normal = hits[0].face.normal.clone();
            normal.transformDirection(hits[0].object.matrixWorld);

            // 表面吸附
            this._ghost.position.copy(point).addScaledVector(normal, 0.1);
            this._ghost.visible = true;
            this._ghostVisible = true;
        } else {
            // 悬浮在远处
            const dir = new THREE.Vector3();
            this.camera.getWorldDirection(dir);
            this._ghost.position.copy(this.camera.position).addScaledVector(dir, 2.5);
            this._ghost.visible = true;
            this._ghostVisible = true;
        }
    }

    /** 点击放置物件 */
    placeSelected() {
        if (!this.active || !this._ghost || !this._ghostVisible) return;

        const objId = 'obj_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6);
        const position = this._ghost.position.clone();
        const rotation = this._ghost.quaternion.clone();

        const mesh = this._createObjectMesh(this.selectedAsset);
        mesh.position.copy(position);
        mesh.quaternion.copy(rotation);
        this.scene.add(mesh);
        this.placedObjects.set(objId, mesh);

        if (this._onPlace) {
            this._onPlace(this.selectedAsset, position.toArray(), rotation.toArray());
        }
        return objId;
    }

    /** 删除被指向的物件 */
    removePointed() {
        if (!this.active) return;
        this._raycaster.setFromCamera(this._mouse, this.camera);
        const allTargets = [];
        for (const [id, obj] of this.placedObjects) {
            allTargets.push(obj);
        }
        const hits = this._raycaster.intersectObjects(allTargets, true);
        if (hits.length > 0 && hits[0].distance < 10) {
            // 找到根节点
            let root = hits[0].object;
            while (root.parent && root.parent !== this.scene) {
                root = root.parent;
            }
            // 找到对应的 objId
            for (const [id, obj] of this.placedObjects) {
                if (obj === root) {
                    this.scene.remove(obj);
                    obj.traverse(c => {
                        if (c.geometry && c.geometry !== this._sharedGeom(c.geometry)) c.geometry.dispose();
                        if (c.material) c.material.dispose();
                    });
                    this.placedObjects.delete(id);
                    if (this._onRemove) this._onRemove(id);
                    return id;
                }
            }
        }
        return null;
    }

    // ── 内部 ──────────────────────────────────────────────

    _initGhost() {
        const geom = new THREE.BoxGeometry(0.3, 0.3, 0.3);
        const mat = new THREE.MeshBasicMaterial({
            color: 0x7c3aed,
            transparent: true,
            opacity: 0.4,
            depthTest: true,
            depthWrite: false,
        });
        this._ghost = new THREE.Mesh(geom, mat);
        this._ghost.visible = false;
        this.scene.add(this._ghost);
    }

    _updateGhostShape() {
        const info = OBJECT_LIBRARY.find(o => o.key === this.selectedAsset);
        if (!info || !this._ghost) return;
        // 简化：用包围盒更新 ghost
        this._ghost.geometry.dispose();
        this._ghost.geometry = info.geom();
    }

    _initMouse() {
        window.addEventListener('mousemove', (e) => {
            this._mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            this._mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
        });
    }

    _createObjectMesh(assetKey) {
        const info = OBJECT_LIBRARY.find(o => o.key === assetKey);
        if (!info) {
            return new THREE.Mesh(
                new THREE.BoxGeometry(0.3, 0.3, 0.3),
                new THREE.MeshStandardMaterial({ color: 0xcccccc })
            );
        }
        const geom = info.geom();
        const color = new THREE.Color(info.color);
        const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0.1 });
        return new THREE.Mesh(geom, mat);
    }

    _renderInventory() {
        if (!this._inventoryEl) {
            const el = document.createElement('div');
            el.id = 'inventory-panel';
            document.body.appendChild(el);
            this._inventoryEl = el;
        }

        const categories = [...new Set(OBJECT_LIBRARY.map(o => o.cat))];
        let html = `
            <style>
                #inventory-panel {
                    position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
                    background: rgba(0,0,0,0.85); border-radius: 12px; padding: 12px;
                    z-index: 101; max-width: 90vw; display: none;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    border: 1px solid rgba(255,255,255,0.1);
                }
                #inventory-panel .inv-cat { color: #666; font-size: 11px; text-transform: uppercase; margin: 4px 0 2px; }
                #inventory-panel .inv-grid { display: flex; flex-wrap: wrap; gap: 4px; }
                #inventory-btn {
                    padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);
                    cursor: pointer; font-size: 12px; color: #ccc; background: rgba(255,255,255,0.05);
                    white-space: nowrap; transition: all 0.1s;
                }
                #inventory-btn:hover { background: rgba(124,58,237,0.3); border-color: #7c3aed; }
                #inventory-btn.selected { background: #7c3aed; color: #fff; border-color: #7c3aed; }
            </style>
        `;

        for (const cat of categories) {
            const items = OBJECT_LIBRARY.filter(o => o.cat === cat);
            html += `<div class="inv-cat">${cat}</div><div class="inv-grid">`;
            for (const item of items) {
                const sel = item.key === this.selectedAsset ? ' selected' : '';
                html += `<button class="inv-btn${sel}" data-key="${item.key}" title="${item.name}">${item.name}</button>`;
            }
            html += '</div>';
        }

        this._inventoryEl.innerHTML = html;

        // 绑定点击
        this._inventoryEl.querySelectorAll('.inv-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.selectedAsset = btn.dataset.key;
                this._updateGhostShape();
                this._renderInventory();
            });
        });

        this._inventoryEl.style.display = this._inventoryVisible ? 'block' : 'none';
    }

    _sharedGeom(geom) {
        // 判断是否与其他物件共享的几何体（预置库共享）
        return false; // 简化处理
    }
}

export { EditorMode, OBJECT_LIBRARY };
