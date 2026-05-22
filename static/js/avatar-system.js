/**
 * AnchorVerse — Avatar 系统
 * 胶囊几何体 Avatar + 名字牌 + lerp 插值同步
 */
import * as THREE from 'three';

class AvatarSystem {
    constructor(scene) {
        this.scene = scene;
        /** Map: session_id -> { group, nameplate, targetPos, targetRot, color } */
        this.avatars = new Map();
        this.selfSessionId = null;
    }

    /** 创建本地玩家 Avatar（不渲染自己，或者渲染可选） */
    createSelf(sessionId, color) {
        this.selfSessionId = sessionId;
        // 本地玩家不渲染自己的 avatar
    }

    /** 添加远程玩家 */
    addRemote(sessionId, displayName, color, position, rotation) {
        const group = new THREE.Group();

        // 身体 — 拉伸的球体
        const bodyGeom = new THREE.CapsuleGeometry(0.2, 0.5, 4, 8);
        const bodyMat = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
        const body = new THREE.Mesh(bodyGeom, bodyMat);
        body.position.y = 0.5;
        body.castShadow = true;
        group.add(body);

        // 头部
        const headGeom = new THREE.SphereGeometry(0.13, 12, 12);
        const headMat = new THREE.MeshStandardMaterial({ color: 0xffccaa, roughness: 0.5 });
        const head = new THREE.Mesh(headGeom, headMat);
        head.position.y = 0.95;
        head.castShadow = true;
        group.add(head);

        // 方向指示（鼻子）
        const noseGeom = new THREE.ConeGeometry(0.04, 0.08, 4);
        const noseMat = new THREE.MeshBasicMaterial({ color: 0xff6b6b });
        const nose = new THREE.Mesh(noseGeom, noseMat);
        nose.position.set(0, 0.97, -0.13);
        nose.rotation.x = Math.PI / 2;
        group.add(nose);

        // 名字牌 (Canvas Sprite)
        const nameplate = this._makeNameplate(displayName);
        nameplate.position.y = 1.25;
        group.add(nameplate);

        // 初始位置
        if (position) {
            group.position.set(position[0], position[1], position[2]);
        }
        if (rotation) {
            group.quaternion.set(rotation[0], rotation[1], rotation[2], rotation[3]);
        }

        this.scene.add(group);

        this.avatars.set(sessionId, {
            group,
            nameplate,
            targetPos: new THREE.Vector3(
                position ? position[0] : 0,
                position ? position[1] : 0,
                position ? position[2] : 0
            ),
            targetRot: new THREE.Quaternion(
                rotation ? rotation[0] : 0,
                rotation ? rotation[1] : 0,
                rotation ? rotation[2] : 0,
                rotation ? rotation[3] : 1
            ),
            displayName,
            color,
        });
    }

    /** 移除远程玩家 */
    removeRemote(sessionId) {
        const data = this.avatars.get(sessionId);
        if (!data) return;
        this.scene.remove(data.group);
        data.group.traverse(c => {
            if (c.geometry) c.geometry.dispose();
            if (c.material) c.material.dispose();
        });
        this.avatars.delete(sessionId);
    }

    /** 接收位置更新 */
    updatePose(sessionId, position, rotation, animation) {
        if (sessionId === this.selfSessionId) return;
        const data = this.avatars.get(sessionId);
        if (!data) return;
        data.targetPos.set(position[0], position[1], position[2]);
        data.targetRot.set(rotation[0], rotation[1], rotation[2], rotation[3]);
        data.animation = animation;
    }

    /** 批量接收位置广播 */
    updateBatch(users) {
        for (const u of users) {
            this.updatePose(u.session_id, u.p, u.r, u.a);
        }
    }

    /** 每帧调用：lerp 插值 + 名字牌朝向相机 */
    tick(camera, delta) {
        const lerpFactor = 1 - Math.exp(-12 * delta); // 平滑跟随
        for (const [sid, data] of this.avatars) {
            // 位置插值
            data.group.position.lerp(data.targetPos, lerpFactor);
            // 旋转插值
            data.group.quaternion.slerp(data.targetRot, lerpFactor);
            // 名字牌朝向相机
            if (data.nameplate) {
                data.nameplate.lookAt(camera.position);
            }
            // 走动动画 — 身体微幅上下
            if (data.animation === 'walk') {
                const bob = Math.sin(performance.now() * 0.008) * 0.04;
                data.group.children[0].position.y = 0.5 + bob;
            }
        }
    }

    /** 获取远程玩家数量 */
    get remoteCount() {
        return this.avatars.size;
    }

    // ── 内部 ──────────────────────────────────────────────

    _makeNameplate(name) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.beginPath();
        ctx.roundRect(30, 8, 196, 48, 12);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 22px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(name, 128, 32);

        const tex = new THREE.CanvasTexture(canvas);
        tex.minFilter = THREE.LinearFilter;
        const spriteMat = new THREE.SpriteMaterial({ map: tex, transparent: true });
        const sprite = new THREE.Sprite(spriteMat);
        sprite.scale.set(1.0, 0.25, 1);
        return sprite;
    }
}

export { AvatarSystem };
