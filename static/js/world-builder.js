/**
 * AnchorVerse — World Builder
 * 根据 world_config 程序化构建不同类型的 3D 场景
 * 返回场景数据：scene objects + 碰撞信息 + 玩家出生点
 */
import * as THREE from 'three';

/**
 * @param {THREE.Scene} scene
 * @param {object} config — 来自 room_state.world_config
 * @returns {{ islandCenter: THREE.Vector3, surfaceY: number, islandRadius: number }}
 */
function buildWorld(scene, config) {
    const terrainType = config.terrain_type || 'floating_island';
    const tcfg = config.terrain_config || {};

    switch (terrainType) {
        case 'castle_hall':       return _buildCastleHall(scene, config, tcfg);
        case 'space_station':     return _buildSpaceStation(scene, config, tcfg);
        case 'forest_clearing':   return _buildForestClearing(scene, config, tcfg);
        case 'desert_oasis':      return _buildDesertOasis(scene, config, tcfg);
        case 'void_platform':     return _buildVoidPlatform(scene, config, tcfg);
        case 'floating_island':
        default:                  return _buildFloatingIsland(scene, config, tcfg);
    }
}

// ── 场景光照 ──────────────────────────────────────────────

function _applyLighting(scene, config) {
    const ambColor = config.ambient_light || '#8899bb';
    const ambInt = config.ambient_intensity || 2.0;
    const sunColor = config.sun_color || '#ffeedd';
    const sunInt = config.sun_intensity || 4.0;

    scene.add(new THREE.AmbientLight(ambColor, ambInt));
    const sun = new THREE.DirectionalLight(sunColor, sunInt);
    sun.position.set(20, 25, 10);
    sun.castShadow = true;
    scene.add(sun);

    const sky = new THREE.DirectionalLight(config.ambient_light || '#aaccff', ambInt * 0.7);
    sky.position.set(-10, 15, -5);
    scene.add(sky);
}

function _applySky(scene, config) {
    scene.background = new THREE.Color(config.sky_color || '#87ceeb');
    scene.fog = new THREE.Fog(
        config.fog_color || '#c8dce8',
        config.fog_near || 30,
        config.fog_far || 80
    );
}

// ── 浮空岛 ────────────────────────────────────────────────

function _buildFloatingIsland(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const center = new THREE.Vector3(0, 6, 0);
    const topRadius = tcfg.island_radius || 4.5;
    const height = tcfg.island_height || 10;
    const bottomRadius = 0.3;
    const grassColor = tcfg.grass_color || '#4a7c3f';

    const group = new THREE.Group();
    scene.add(group);

    // 锥体
    const coneGeom = new THREE.CylinderGeometry(bottomRadius, topRadius, height, 32);
    const coneMat = new THREE.MeshStandardMaterial({ color: 0x6b5e4a, roughness: 0.8, metalness: 0.05 });
    const cone = new THREE.Mesh(coneGeom, coneMat);
    cone.position.copy(center);
    cone.position.y -= height / 2;
    cone.castShadow = true;
    cone.receiveShadow = true;
    group.add(cone);

    // 顶部草皮
    const topGeom = new THREE.CylinderGeometry(topRadius, topRadius, 0.3, 32);
    const topMat = new THREE.MeshStandardMaterial({ color: grassColor, roughness: 0.7 });
    const topDisk = new THREE.Mesh(topGeom, topMat);
    topDisk.position.copy(center);
    topDisk.position.y += 0.15;
    topDisk.castShadow = true;
    topDisk.receiveShadow = true;
    group.add(topDisk);

    // 草地环
    const rimGeom = new THREE.TorusGeometry(topRadius - 0.15, 0.25, 8, 32);
    const rimMat = new THREE.MeshStandardMaterial({ color: 0x5a9645, roughness: 0.6 });
    const rim = new THREE.Mesh(rimGeom, rimMat);
    rim.rotation.x = Math.PI / 2;
    rim.position.copy(center);
    rim.position.y += 0.3;
    rim.castShadow = true;
    group.add(rim);

    // 岩层环
    for (let i = 1; i <= 3; i++) {
        const t = i / 4;
        const rockY = center.y - height * t;
        const rockR = bottomRadius + (topRadius - bottomRadius) * (1 - t);
        const rockGeom = new THREE.TorusGeometry(rockR, 0.15 + Math.random() * 0.2, 8, 32);
        const rockMat = new THREE.MeshStandardMaterial({ color: 0x8a7a6a, roughness: 0.9 });
        const rockRing = new THREE.Mesh(rockGeom, rockMat);
        rockRing.rotation.x = Math.PI / 2;
        rockRing.position.y = rockY;
        rockRing.castShadow = true;
        group.add(rockRing);
    }

    // 底部水晶
    const crystalGeom = new THREE.OctahedronGeometry(0.5, 0);
    const crystalMat = new THREE.MeshStandardMaterial({
        color: 0x7c3aed, roughness: 0.2, metalness: 0.3,
        emissive: 0x2a1050, emissiveIntensity: 0.8,
    });
    const crystal = new THREE.Mesh(crystalGeom, crystalMat);
    crystal.position.copy(center);
    crystal.position.y -= height + 0.3;
    crystal.scale.set(1, 1.8, 1);
    group.add(crystal);

    // 浮空碎石
    for (let i = 0; i < 12; i++) {
        const angle = (i / 12) * Math.PI * 2;
        const dist = topRadius + 1.5 + Math.random() * 2.5;
        const heightOff = (Math.random() - 0.5) * 3;
        const rockGeom = new THREE.IcosahedronGeometry(0.2 + Math.random() * 0.5, 1);
        const rockMat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.9 });
        const smallRock = new THREE.Mesh(rockGeom, rockMat);
        smallRock.position.set(
            center.x + Math.cos(angle) * dist,
            center.y + heightOff,
            center.z + Math.sin(angle) * dist
        );
        smallRock.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
        smallRock.castShadow = true;
        group.add(smallRock);
    }

    // 云朵
    for (let i = 0; i < 8; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = topRadius + 2 + Math.random() * 6;
        const cloudY = center.y + 2 + Math.random() * 4;
        group.add(_makeCloud(
            center.x + Math.cos(angle) * dist, cloudY,
            center.z + Math.sin(angle) * dist, 0.8 + Math.random() * 1.5
        ));
    }

    // 粒子
    scene.add(_makeParticleRing(center, topRadius, 200));

    return {
        islandCenter: center,
        surfaceY: center.y + 0.3,
        islandRadius: topRadius,
    };
}

// ── 城堡大厅 ──────────────────────────────────────────────

function _buildCastleHall(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const floorSize = tcfg.floor_size || 12;
    const pillarCount = tcfg.pillar_count || 8;
    const wallColor = tcfg.wall_color || '#4a4a5a';
    const center = new THREE.Vector3(0, 0, 0);

    // 地板
    const floorGeom = new THREE.PlaneGeometry(floorSize, floorSize);
    const floorMat = new THREE.MeshStandardMaterial({ color: 0x3a3a44, roughness: 0.5 });
    const floor = new THREE.Mesh(floorGeom, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    scene.add(floor);

    // 棋盘格地板装饰
    const tileSize = floorSize / 8;
    for (let x = -4; x < 4; x++) {
        for (let z = -4; z < 4; z++) {
            if ((x + z) % 2 !== 0) continue;
            const tileGeom = new THREE.PlaneGeometry(tileSize * 0.9, tileSize * 0.9);
            const tileMat = new THREE.MeshStandardMaterial({ color: 0x4a4a50, roughness: 0.6 });
            const tile = new THREE.Mesh(tileGeom, tileMat);
            tile.rotation.x = -Math.PI / 2;
            tile.position.set(x * tileSize, 0.005, z * tileSize);
            tile.receiveShadow = true;
            scene.add(tile);
        }
    }

    // 石柱
    for (let i = 0; i < pillarCount; i++) {
        const angle = (i / pillarCount) * Math.PI * 2;
        const dist = floorSize / 2 - 1.2;
        const px = Math.cos(angle) * dist;
        const pz = Math.sin(angle) * dist;

        const pillarGeom = new THREE.CylinderGeometry(0.25, 0.3, 5, 16);
        const pillarMat = new THREE.MeshStandardMaterial({ color: wallColor, roughness: 0.8 });
        const pillar = new THREE.Mesh(pillarGeom, pillarMat);
        pillar.position.set(px, 2.5, pz);
        pillar.castShadow = true;
        pillar.receiveShadow = true;
        scene.add(pillar);

        // 柱头
        const capitalGeom = new THREE.CylinderGeometry(0.35, 0.25, 0.4, 16);
        const capital = new THREE.Mesh(capitalGeom, pillarMat);
        capital.position.set(px, 5.1, pz);
        scene.add(capital);
    }

    // 蜡烛光源 — 暖色调点光
    for (let i = 0; i < 4; i++) {
        const angle = (i / 4) * Math.PI * 2 + Math.PI / 4;
        const dist = floorSize / 2 - 2;
        const candleLight = new THREE.PointLight(0xffaa55, 8, 8);
        candleLight.position.set(Math.cos(angle) * dist, 2, Math.sin(angle) * dist);
        scene.add(candleLight);
    }

    return {
        islandCenter: center,
        surfaceY: 0.05,
        islandRadius: floorSize / 2 - 1,
    };
}

// ── 太空站 ────────────────────────────────────────────────

function _buildSpaceStation(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const platformRadius = tcfg.platform_radius || 6;
    const ringSegments = tcfg.ring_segments || 4;
    const center = new THREE.Vector3(0, 4, 0);

    // 主平台
    const platGeom = new THREE.CylinderGeometry(platformRadius, platformRadius, 0.3, 48);
    const platMat = new THREE.MeshStandardMaterial({ color: 0x889999, roughness: 0.3, metalness: 0.8 });
    const platform = new THREE.Mesh(platGeom, platMat);
    platform.position.copy(center);
    platform.receiveShadow = true;
    scene.add(platform);

    // 环形结构
    for (let i = 0; i < ringSegments; i++) {
        const angle = (i / ringSegments) * Math.PI * 2;
        const ringGeom = new THREE.TorusGeometry(platformRadius + 1.5, 0.2, 8, 48);
        const ringMat = new THREE.MeshStandardMaterial({
            color: 0x7c3aed, roughness: 0.2, metalness: 0.9,
            emissive: 0x1a0850, emissiveIntensity: 0.5,
        });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.position.copy(center);
        ring.rotation.x = Math.PI / 2;
        scene.add(ring);
    }

    // 中央核心柱
    const coreGeom = new THREE.CylinderGeometry(0.5, 0.6, 3, 16);
    const coreMat = new THREE.MeshStandardMaterial({ color: 0xcccccc, roughness: 0.2, metalness: 0.9 });
    const core = new THREE.Mesh(coreGeom, coreMat);
    core.position.set(center.x, center.y + 1.5, center.z);
    core.castShadow = true;
    scene.add(core);

    // 核心光环
    const glowGeom = new THREE.TorusGeometry(0.7, 0.08, 8, 24);
    const glowMat = new THREE.MeshBasicMaterial({ color: 0x44ccff });
    const glow = new THREE.Mesh(glowGeom, glowMat);
    glow.position.set(center.x, center.y + 2.5, center.z);
    scene.add(glow);

    // 星星背景
    const starsGeom = new THREE.BufferGeometry();
    const starsCount = 500;
    const starsPositions = new Float32Array(starsCount * 3);
    for (let i = 0; i < starsCount; i++) {
        starsPositions[i * 3] = (Math.random() - 0.5) * 80;
        starsPositions[i * 3 + 1] = (Math.random() - 0.5) * 80;
        starsPositions[i * 3 + 2] = (Math.random() - 0.5) * 80;
    }
    starsGeom.setAttribute('position', new THREE.BufferAttribute(starsPositions, 3));
    const starsMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.1, transparent: true, opacity: 0.8 });
    const stars = new THREE.Points(starsGeom, starsMat);
    scene.add(stars);

    return {
        islandCenter: center,
        surfaceY: center.y + 0.15,
        islandRadius: platformRadius,
    };
}

// ── 森林空地 ──────────────────────────────────────────────

function _buildForestClearing(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const clearingRadius = tcfg.clearing_radius || 5;
    const treeCount = tcfg.tree_count || 20;
    const treeRange = tcfg.tree_height_range || [3, 8];
    const center = new THREE.Vector3(0, 0, 0);

    // 地面 — 大片草地
    const groundGeom = new THREE.PlaneGeometry(40, 40, 32, 32);
    // 微起伏
    const posAttr = groundGeom.attributes.position;
    for (let i = 0; i < posAttr.count; i++) {
        const x = posAttr.getX(i);
        const y = posAttr.getY(i);
        const dist = Math.sqrt(x * x + y * y);
        if (dist > clearingRadius) {
            posAttr.setZ(i, Math.sin(x * 0.7) * Math.cos(y * 0.7) * 0.8
                + Math.sin(x * 1.3 + y * 0.9) * 0.3);
        }
    }
    groundGeom.computeVertexNormals();
    const groundMat = new THREE.MeshStandardMaterial({ color: 0x4a7c3f, roughness: 0.8 });
    const ground = new THREE.Mesh(groundGeom, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.05;
    ground.receiveShadow = true;
    scene.add(ground);

    // 空地 — 浅色表面
    const clearingGeom = new THREE.CylinderGeometry(clearingRadius, clearingRadius, 0.05, 32);
    const clearingMat = new THREE.MeshStandardMaterial({ color: 0x8a9a5a, roughness: 0.9 });
    const clearing = new THREE.Mesh(clearingGeom, clearingMat);
    clearing.position.y = 0.02;
    clearing.receiveShadow = true;
    scene.add(clearing);

    // 树木
    for (let i = 0; i < treeCount; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = clearingRadius + 1.5 + Math.random() * 10;
        const x = Math.cos(angle) * dist;
        const z = Math.sin(angle) * dist;
        const h = treeRange[0] + Math.random() * (treeRange[1] - treeRange[0]);
        scene.add(_makeTree(x, 0, z, h));
    }

    // 随机野花
    for (let i = 0; i < 30; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = Math.random() * (clearingRadius - 0.5);
        const x = Math.cos(angle) * dist;
        const z = Math.sin(angle) * dist;
        const flower = _makeFlower(
            ['#ff3366', '#ffcc00', '#ff8800', '#ff66aa', '#ffffff'][Math.floor(Math.random() * 5)]
        );
        flower.position.set(x, 0.04, z);
        scene.add(flower);
    }

    // 阳光束 (丁达尔效果模拟)
    for (let i = 0; i < 3; i++) {
        const beamGeom = new THREE.CylinderGeometry(0.1, 0.6, 15, 8, 1, true);
        const beamMat = new THREE.MeshBasicMaterial({
            color: 0xffeedd, transparent: true, opacity: 0.06,
            side: THREE.DoubleSide, depthWrite: false,
        });
        const beam = new THREE.Mesh(beamGeom, beamMat);
        beam.position.set((Math.random() - 0.5) * 6, 7, (Math.random() - 0.5) * 6);
        beam.rotation.x = Math.PI * 0.15;
        scene.add(beam);
    }

    return {
        islandCenter: center,
        surfaceY: 0.05,
        islandRadius: clearingRadius,
    };
}

// ── 沙漠绿洲 ──────────────────────────────────────────────

function _buildDesertOasis(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const oasisRadius = tcfg.oasis_radius || 4;
    const duneCount = tcfg.dune_count || 6;
    const palmCount = tcfg.palm_count || 5;
    const center = new THREE.Vector3(0, 0, 0);

    // 沙地
    const sandGeom = new THREE.PlaneGeometry(50, 50, 40, 40);
    const posAttr = sandGeom.attributes.position;
    for (let i = 0; i < posAttr.count; i++) {
        const x = posAttr.getX(i);
        const y = posAttr.getY(i);
        const dist = Math.sqrt(x * x + y * y);
        if (dist > oasisRadius) {
            posAttr.setZ(i, Math.sin(x * 0.3) * Math.cos(y * 0.5) * 2
                + Math.cos(x * 0.2 + y * 0.3) * 3);
        }
    }
    sandGeom.computeVertexNormals();
    const sandMat = new THREE.MeshStandardMaterial({ color: 0xddbb77, roughness: 0.9 });
    const sand = new THREE.Mesh(sandGeom, sandMat);
    sand.rotation.x = -Math.PI / 2;
    sand.receiveShadow = true;
    scene.add(sand);

    // 水面
    const waterGeom = new THREE.CircleGeometry(oasisRadius, 32);
    const waterMat = new THREE.MeshStandardMaterial({
        color: 0x4499cc, roughness: 0.1, metalness: 0.5,
        transparent: true, opacity: 0.85,
    });
    const water = new THREE.Mesh(waterGeom, waterMat);
    water.rotation.x = -Math.PI / 2;
    water.position.y = 0.03;
    scene.add(water);

    // 棕榈树
    for (let i = 0; i < palmCount; i++) {
        const angle = (i / palmCount) * Math.PI * 2 + Math.random() * 0.3;
        const dist = oasisRadius * 0.6 + Math.random() * oasisRadius * 0.3;
        const x = Math.cos(angle) * dist;
        const z = Math.sin(angle) * dist;
        scene.add(_makePalmTree(x, 0, z));
    }

    // 沙丘
    for (let i = 0; i < duneCount; i++) {
        const angle = (i / duneCount) * Math.PI * 2;
        const dist = oasisRadius + 3 + Math.random() * 8;
        const duneGeom = new THREE.SphereGeometry(2 + Math.random() * 3, 16, 8, 0, Math.PI * 2, 0, Math.PI / 3);
        const dune = new THREE.Mesh(duneGeom, sandMat);
        dune.position.set(Math.cos(angle) * dist, -0.5, Math.sin(angle) * dist);
        dune.scale.y = 0.3;
        dune.castShadow = true;
        dune.receiveShadow = true;
        scene.add(dune);
    }

    return {
        islandCenter: center,
        surfaceY: 0.05,
        islandRadius: oasisRadius,
    };
}

// ── 虚空平台 ──────────────────────────────────────────────

function _buildVoidPlatform(scene, config, tcfg) {
    _applySky(scene, config);
    _applyLighting(scene, config);

    const platformSize = tcfg.platform_size || 8;
    const neonColor = tcfg.neon_color || '#7c3aed';
    const center = new THREE.Vector3(0, 0, 0);

    // 主平台
    const platGeom = new THREE.BoxGeometry(platformSize, 0.2, platformSize);
    const platMat = new THREE.MeshStandardMaterial({ color: 0x1a1a2e, roughness: 0.3, metalness: 0.8 });
    const platform = new THREE.Mesh(platGeom, platMat);
    platform.position.y = -0.1;
    platform.receiveShadow = true;
    scene.add(platform);

    // 网格线
    if (tcfg.grid_lines !== false) {
        const gridSize = platformSize / 2 - 0.5;
        const mat = new THREE.LineBasicMaterial({ color: neonColor, transparent: true, opacity: 0.3 });
        for (let i = -gridSize; i <= gridSize; i += 1) {
            const ptsX = [new THREE.Vector3(i, 0.01, -gridSize), new THREE.Vector3(i, 0.01, gridSize)];
            scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ptsX), mat));
            const ptsZ = [new THREE.Vector3(-gridSize, 0.01, i), new THREE.Vector3(gridSize, 0.01, i)];
            scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ptsZ), mat));
        }
    }

    // 边缘霓虹光带
    const edgeGeom = new THREE.TorusGeometry(platformSize / 2 - 0.1, 0.05, 8, 4);
    const edgeMat = new THREE.MeshBasicMaterial({ color: neonColor });
    const edge = new THREE.Mesh(edgeGeom, edgeMat);
    edge.rotation.x = Math.PI / 2;
    edge.position.y = 0.01;
    scene.add(edge);

    // 下方粒子
    const particlesGeom = new THREE.BufferGeometry();
    const pCount = 300;
    const pPos = new Float32Array(pCount * 3);
    for (let i = 0; i < pCount; i++) {
        pPos[i * 3] = (Math.random() - 0.5) * 30;
        pPos[i * 3 + 1] = -Math.random() * 20;
        pPos[i * 3 + 2] = (Math.random() - 0.5) * 30;
    }
    particlesGeom.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({
        color: neonColor, size: 0.06, transparent: true,
        opacity: 0.6, depthWrite: false, blending: THREE.AdditiveBlending,
    });
    scene.add(new THREE.Points(particlesGeom, pMat));

    return {
        islandCenter: center,
        surfaceY: 0.01,
        islandRadius: platformSize / 2 - 0.5,
    };
}

// ── 共享几何体 ────────────────────────────────────────────

function _makeCloud(x, y, z, scale) {
    const group = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, transparent: true, opacity: 0.6 });
    for (let j = 0; j < 5; j++) {
        const blobGeom = new THREE.SphereGeometry((0.4 + Math.random() * 0.6) * scale, 8, 6);
        const blob = new THREE.Mesh(blobGeom, mat);
        blob.position.set(Math.random() * 1.5 * scale, Math.random() * 0.4 * scale, Math.random() * 1.5 * scale);
        group.add(blob);
    }
    group.position.set(x, y, z);
    return group;
}

function _makeParticleRing(center, topRadius, count) {
    const geom = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = topRadius + 3 + Math.random() * 15;
        positions[i * 3] = center.x + Math.cos(angle) * dist;
        positions[i * 3 + 1] = center.y + (Math.random() - 0.3) * 20;
        positions[i * 3 + 2] = center.z + Math.sin(angle) * dist;
    }
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
        color: 0xaaaacc, size: 0.08, transparent: true,
        opacity: 0.5, depthWrite: false,
    });
    return new THREE.Points(geom, mat);
}

function _makeTree(x, y, z, height) {
    const group = new THREE.Group();
    // 树干
    const trunkGeom = new THREE.CylinderGeometry(0.15, 0.22, height * 0.6, 8);
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x8b5a3c, roughness: 0.9 });
    const trunk = new THREE.Mesh(trunkGeom, trunkMat);
    trunk.position.y = height * 0.3;
    trunk.castShadow = true;
    group.add(trunk);

    // 树冠 (多层球)
    const foliageColor = 0x3a6b2a;
    for (let j = 0; j < 3; j++) {
        const crownGeom = new THREE.ConeGeometry(0.6 + j * 0.3, height * 0.5, 8);
        const crownMat = new THREE.MeshStandardMaterial({ color: foliageColor, roughness: 0.8 });
        const crown = new THREE.Mesh(crownGeom, crownMat);
        crown.position.y = height * 0.5 + j * 0.5;
        crown.castShadow = true;
        crown.receiveShadow = true;
        group.add(crown);
    }

    group.position.set(x, y, z);
    return group;
}

function _makeFlower(color) {
    const group = new THREE.Group();
    const stemGeom = new THREE.CylinderGeometry(0.015, 0.02, 0.3, 6);
    const stemMat = new THREE.MeshStandardMaterial({ color: 0x3a6b2a });
    const stem = new THREE.Mesh(stemGeom, stemMat);
    stem.position.y = 0.15;
    group.add(stem);

    const petalGeom = new THREE.SphereGeometry(0.06, 6, 4);
    const petalMat = new THREE.MeshStandardMaterial({ color, roughness: 0.5 });
    const petal = new THREE.Mesh(petalGeom, petalMat);
    petal.position.y = 0.32;
    group.add(petal);

    return group;
}

function _makePalmTree(x, y, z) {
    const group = new THREE.Group();
    // 弯曲树干
    const trunkGeom = new THREE.CylinderGeometry(0.12, 0.18, 3, 8);
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0xaa8855, roughness: 0.8 });
    const trunk = new THREE.Mesh(trunkGeom, trunkMat);
    trunk.position.y = 1.5;
    trunk.rotation.z = (Math.random() - 0.5) * 0.3;
    trunk.rotation.x = (Math.random() - 0.5) * 0.3;
    trunk.castShadow = true;
    group.add(trunk);

    // 棕榈叶
    for (let j = 0; j < 7; j++) {
        const angle = (j / 7) * Math.PI * 2;
        const leafGeom = new THREE.BoxGeometry(0.08, 0.02, 1.5);
        const leafMat = new THREE.MeshStandardMaterial({ color: 0x5a9645, roughness: 0.7, side: THREE.DoubleSide });
        const leaf = new THREE.Mesh(leafGeom, leafMat);
        leaf.position.y = 3;
        leaf.rotation.y = angle;
        leaf.rotation.z = 0.6 + Math.random() * 0.4;
        leaf.castShadow = true;
        group.add(leaf);
    }

    group.position.set(x, y, z);
    return group;
}

export { buildWorld };
