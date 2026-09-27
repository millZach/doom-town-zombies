import * as THREE from 'three';
import { PLAYER } from '../config.js';

const _start = new THREE.Vector3();
const _end = new THREE.Vector3();
const _move = new THREE.Vector3();
const _fwd = new THREE.Vector3();
const _right = new THREE.Vector3();

export class Player {
  constructor(camera, collision) {
    this.camera = camera;
    this.col = collision;
    this.pos = new THREE.Vector3();          // feet
    this.vel = new THREE.Vector3();
    this.yaw = 0;
    this.pitch = 0;
    this.onGround = false;
    this.crouch = false;
    this.eye = PLAYER.eyeHeight;
    this.sprinting = false;
    this.stamina = PLAYER.sprintDuration;
    this.sprintLock = 0;
    this.maxHealth = PLAYER.health;
    this.health = PLAYER.health;
    this.lastHit = -99;
    this.points = PLAYER.startPoints;
    this.perks = new Set();
    this.downed = false;
    this.dead = false;
    this.revives = 0;
    this.moveAmount = 0;          // 0..1 for bob/spread
    this.bobTime = 0;
    // camera kick / shake
    this.recoilPitch = 0;
    this.recoilYaw = 0;
    this.kickVel = new THREE.Vector2();
    this.trauma = 0;
    this.landDip = 0;
    this.landEvent = 0;        // impact speed of the last landing, consumed by Weapons for foley
    this.jumpEvent = false;
    this.stepDip = 0;          // short dip impulse on each footfall
    this.hurtTilt = 0;
    this.adsFactor = 0;
    this.speedMul = 1;
    this.frozen = false;
    this.zone = null;
    this.time = 0;
  }

  spawn(pos, forward) {
    this.pos.copy(pos);
    this.vel.set(0, 0, 0);
    this.yaw = Math.atan2(-forward.x, -forward.z);
    this.pitch = 0;
  }

  forward(out = new THREE.Vector3()) {
    return out.set(0, 0, -1).applyEuler(new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ'));
  }

  /**
   * Weapon recoil on the camera.
   *
   * Two components, as in BO2: a *view kick* that springs back to where you were pointing, and a
   * small *permanent* shift of the aim itself. Without the second part every weapon returns to the
   * exact original aim point and there is no recoil to control; with it, a long burst walks off
   * target and the player has to pull back down.
   */
  addRecoil(pitchDeg, yawDeg) {
    this.kickVel.x += pitchDeg * 0.0174 * 18;
    this.kickVel.y += yawDeg * 0.0174 * 18;
    this.pitch = Math.max(-1.52, Math.min(1.52, this.pitch + pitchDeg * 0.0174 * 0.22));
    this.yaw += yawDeg * 0.0174 * 0.22;
  }

  shake(amount) { this.trauma = Math.min(1, this.trauma + amount); }

  damage(amount, time) {
    if (this.downed || this.dead) return false;
    this.health -= amount;
    this.lastHit = time;
    this.hurtTilt = (Math.random() < 0.5 ? -1 : 1) * 0.05;
    this.shake(0.35);
    if (this.health <= 0) { this.health = 0; return true; }
    return false;
  }

  /**
   * Right-stick look with BO2-style aim assist:
   *   - slowdown: look speed drops while the crosshair is over a zombie
   *   - rotational: while strafing, the view gently follows the target under the crosshair
   *   - ADS snap: pulling LT near a zombie eases the aim onto its chest
   * `opts.aimTargets()` returns candidate world points ({ pos, dist }) and `opts.aimAssist`
   * is 'on' | 'off'.
   */
  _padLook(dt, input, opts) {
    const pad = input.pad;
    if (!pad?.active) { this._snap = null; return; }
    const rate = 3.4 * (input.stickSensitivity || 1) * (1 - this.adsFactor * 0.5);   // rad/s at full tilt
    let rx = pad.rx, ry = pad.ry * (input.invertY ? -1 : 1);
    let slow = 1;
    const assist = opts.aimAssist !== 'off' && opts.aimTargets;
    let target = null;
    if (assist) {
      target = this._assistTarget(opts.aimTargets(), this.adsFactor > 0.5 ? 14 : 9);
      if (target && target.err < target.cone) slow = this.adsFactor > 0.5 ? 0.42 : 0.55;
    }
    this.yaw -= rx * rate * slow * dt;
    this.pitch -= ry * rate * 0.72 * slow * dt;

    if (!target) { this._snap = null; return; }
    // rotational assist: only while the player is moving the left stick sideways
    if (Math.abs(pad.lx) > 0.25 && target.err < target.cone * 1.6) {
      this.yaw += target.dYaw * Math.min(1, dt * 3.2) * 0.45;
    }
    // ADS snap on the LT press
    if (input.mouse.rightPressed && target.err < 0.22 && target.dist < 40) this._snap = { t: 0, target };
    if (this._snap) {
      // re-measure every frame so the ease converges on the target instead of overshooting
      const s = this._snap, cam = this.camera.position, tp = s.target.pos;
      s.t += dt;
      const dx = tp.x - cam.x, dy = tp.y - cam.y, dz = tp.z - cam.z;
      let dYaw = Math.atan2(-dx, -dz) - this.yaw; dYaw = Math.atan2(Math.sin(dYaw), Math.cos(dYaw));
      const dPitch = Math.atan2(dy, Math.hypot(dx, dz)) - this.pitch;
      const k = Math.min(1, dt * 14);
      this.yaw += dYaw * k;
      this.pitch += dPitch * k;
      if (s.t > 0.18 || !input.mouse.right) this._snap = null;
    }
  }

  _assistTarget(points, degCone) {
    if (!points || !points.length) return null;
    const cam = this.camera.position;
    let best = null;
    for (const p of points) {
      const dx = p.pos.x - cam.x, dy = p.pos.y - cam.y, dz = p.pos.z - cam.z;
      const d = Math.hypot(dx, dy, dz);
      if (d < 0.8 || d > 45) continue;
      const tYaw = Math.atan2(-dx, -dz), tPitch = Math.atan2(dy, Math.hypot(dx, dz));
      let dYaw = tYaw - this.yaw; dYaw = Math.atan2(Math.sin(dYaw), Math.cos(dYaw));
      const dPitch = tPitch - this.pitch;
      const err = Math.hypot(dYaw, dPitch);
      // the magnet is a roughly fixed-size disc around the target, plus a small angular floor
      const cone = Math.max(degCone * 0.0174 * 0.35, Math.atan(0.55 / d));
      if (err > cone * 2.5) continue;
      if (!best || err < best.err) best = { err, cone, dYaw, dPitch, dist: d, pos: p.pos };
    }
    if (best && this.col.raycast(cam, _move.set(best.pos.x - cam.x, best.pos.y - cam.y, best.pos.z - cam.z).normalize(), best.dist - 0.3)) return null;
    return best;
  }

  update(dt, input, time, opts = {}) {
    this.time = time;
    const sens = 0.0021 * input.sensitivity * (1 - this.adsFactor * 0.45);
    if (!this.frozen) {
      this.yaw -= input.mouse.dx * sens;
      this.pitch -= input.mouse.dy * sens;
      this._padLook(dt, input, opts);
      this.pitch = Math.max(-1.52, Math.min(1.52, this.pitch));
    }

    // regen
    if (!this.downed && time - this.lastHit > PLAYER.regenDelay && this.health < this.maxHealth) {
      this.health = Math.min(this.maxHealth, this.health + PLAYER.regenRate * dt);
    }

    // movement input
    let mx = 0, mz = 0;
    if (!this.frozen) {
      if (input.down('KeyW')) mz -= 1;
      if (input.down('KeyS')) mz += 1;
      if (input.down('KeyA')) mx -= 1;
      if (input.down('KeyD')) mx += 1;
      const pad = input.pad;
      if (pad?.active) { mx += pad.lx; mz += pad.ly; }
    }
    // analog sticks walk slower at partial deflection; keys are always full speed
    const moveMag = Math.min(1, Math.hypot(mx, mz));
    const wantsSprint = !this.frozen && !this.downed && input.down('ShiftLeft') && mz < 0 && !opts.blockSprint;
    if (input.hit('KeyC') || input.hit('ControlLeft')) this.crouch = !this.crouch;
    if (wantsSprint) this.crouch = false;

    // sprint stamina
    if (wantsSprint && this.stamina > 0 && this.sprintLock <= 0) {
      this.sprinting = true;
      this.stamina -= dt;
      if (this.stamina <= 0) { this.stamina = 0; this.sprintLock = 1.2; }
    } else {
      this.sprinting = false;
      this.sprintLock -= dt;
      this.stamina = Math.min(PLAYER.sprintDuration, this.stamina + dt * (PLAYER.sprintDuration / PLAYER.sprintRecover));
    }

    let speed = this.downed ? 0 : this.sprinting ? PLAYER.sprintSpeed : this.crouch ? PLAYER.crouchSpeed : PLAYER.walkSpeed;
    speed *= 1 - this.adsFactor * (1 - PLAYER.adsSpeedMul);
    if (mz > 0) speed *= PLAYER.backpedalMul;
    speed *= this.speedMul;

    _fwd.set(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    _right.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    _move.set(0, 0, 0).addScaledVector(_fwd, -mz).addScaledVector(_right, mx);
    if (_move.lengthSq() > 0) _move.normalize().multiplyScalar(speed * Math.max(0.35, moveMag));

    const accel = this.onGround ? 14 : 3;
    this.vel.x += (_move.x - this.vel.x) * Math.min(1, accel * dt);
    this.vel.z += (_move.z - this.vel.z) * Math.min(1, accel * dt);
    this.vel.y -= PLAYER.gravity * dt;

    if (!this.frozen && !this.downed && this.onGround && input.hit('Space')) {
      this.vel.y = PLAYER.jumpVelocity;
      this.onGround = false;
      this.crouch = false;
      this.jumpEvent = true;
    }

    // integrate + collide (substeps for fast motion)
    const wasGround = this.onGround;
    const prevVy = this.vel.y;
    const steps = 2;
    this.onGround = false;
    const r = PLAYER.radius;
    const height = this.downed ? 0.9 : this.crouch ? 1.2 : PLAYER.height;
    for (let s = 0; s < steps; s++) {
      const px = this.pos.x, py = this.pos.y, pz = this.pos.z;
      const wx = this.vel.x * dt / steps, wz = this.vel.z * dt / steps;
      this.pos.addScaledVector(this.vel, dt / steps);
      _start.set(this.pos.x, this.pos.y + r, this.pos.z);
      _end.set(this.pos.x, this.pos.y + height - r, this.pos.z);
      let up = this.col.capsule(_start, _end, r, undefined, 0.55);
      let dx = _start.x - this.pos.x, dy = _start.y - r - this.pos.y, dz = _start.z - this.pos.z;
      this.pos.set(_start.x, _start.y - r, _start.z);
      // step-up: blocked by a ledge (door sill, ramp lip, kerb, stair nosing) while grounded →
      // retry the move from up to STEP higher and settle onto what's there, like any FPS
      const want = Math.hypot(wx, wz);
      const got = Math.hypot(this.pos.x - px, this.pos.z - pz);
      if ((wasGround || this.onGround) && this.vel.y <= 0.5 && want > 1e-4 && got < want * 0.6) {
        const STEP = 0.42;
        _start.set(px + wx, py + STEP + r, pz + wz);
        _end.set(px + wx, py + STEP + height - r, pz + wz);
        this.col.capsule(_start, _end, r, undefined, 0.55);
        const sx = _start.x, sz = _start.z;
        const stepGot = Math.hypot(sx - px, sz - pz);
        if (stepGot > got + want * 0.3) {
          const g = this.col.ground(sx, sz, py + STEP + 0.05, STEP + 0.15);
          if (g !== null && g > py + 0.02 && g <= py + STEP) {
            this.pos.set(sx, g, sz);
            up = 1; dx = 0; dy = 0; dz = 0;
            this.vel.y = 0;
          }
        }
      }
      if (up > 0.55 && this.vel.y <= 0) { this.onGround = true; this.vel.y = 0; }
      else if (dy < -1e-4 && this.vel.y > 0) this.vel.y = 0;   // head bump
      if (Math.abs(dx) + Math.abs(dz) > 1e-4) {
        // remove velocity into the wall
        const n = new THREE.Vector3(dx, 0, dz).normalize();
        const vn = this.vel.x * n.x + this.vel.z * n.z;
        if (vn < 0) { this.vel.x -= n.x * vn; this.vel.z -= n.z * vn; }
      }
    }
    // ground snap (walking down ramps/steps)
    if (!this.onGround && wasGround && this.vel.y <= 0) {
      const g = this.col.ground(this.pos.x, this.pos.z, this.pos.y + 0.3, 0.75);
      if (g !== null && this.pos.y - g < 0.4) { this.pos.y = g; this.onGround = true; this.vel.y = 0; }
    }
    if (this.onGround && !wasGround && prevVy < -2.5) {
      this.landDip = Math.min(0.12, -prevVy * 0.012);
      this.landEvent = -prevVy;      // consumed (and zeroed) by Weapons for the landing foley
    }
    if (this.pos.y < -60) this.pos.y = 5; // safety

    // eye height
    const targetEye = this.downed ? PLAYER.proneEyeHeight : this.crouch ? PLAYER.crouchEyeHeight : PLAYER.eyeHeight;
    this.eye += (targetEye - this.eye) * Math.min(1, dt * 10);

    const hs = Math.hypot(this.vel.x, this.vel.z);
    this.moveAmount = this.onGround ? Math.min(1, hs / PLAYER.walkSpeed) : 0.4;
    const prevBob = this.bobTime;
    this.bobTime += dt * hs * 1.55;
    // footfall impulse (a step should land, not hum)
    if (Math.floor(this.bobTime / Math.PI) !== Math.floor(prevBob / Math.PI) && this.onGround && this.moveAmount > 0.2) this.stepDip = 1;
    this.stepDip = Math.max(0, this.stepDip - dt * 8);

    // camera kick springs. The view kick recovers slowly enough that a burst accumulates and the
    // player has to fight it; addRecoil() already moved the aim itself by a smaller amount.
    this.recoilPitch += this.kickVel.x * dt;
    this.recoilYaw += this.kickVel.y * dt;
    this.kickVel.multiplyScalar(Math.max(0, 1 - 16 * dt));
    this.recoilPitch -= this.recoilPitch * Math.min(1, 5 * dt) * 0.65;
    this.recoilYaw -= this.recoilYaw * Math.min(1, 5 * dt) * 0.8;
    this.trauma = Math.max(0, this.trauma - dt * 1.4);
    this.landDip *= Math.max(0, 1 - dt * 7);
    this.hurtTilt *= Math.max(0, 1 - dt * 4);

    this._updateCamera(time);
  }

  _updateCamera(t) {
    const cam = this.camera;
    const bobAmt = this.moveAmount * (1 - this.adsFactor * 0.85) * (this.sprinting ? 1.6 : 1);
    // Lissajous walk cycle: x = sin(t), y = sin(2t) — a figure of eight, not a single-axis hum.
    const bobY = (Math.sin(this.bobTime * 2) * 0.5 + 0.5) * 0.032 * bobAmt + this.stepDip * this.stepDip * 0.012 * bobAmt;
    const bobX = Math.sin(this.bobTime) * 0.022 * bobAmt;
    const bobRoll = Math.sin(this.bobTime) * 0.012 * bobAmt;
    // positional shake is linear in trauma (squaring it made a 12-gauge move the camera by 0.01°)
    const shPos = this.trauma;
    const shRot = this.trauma * this.trauma;
    const n = (k) => Math.sin(t * 37 + k) * Math.sin(t * 23.3 + k * 1.7);
    cam.position.set(this.pos.x, this.pos.y + this.eye - bobY - this.landDip, this.pos.z);
    cam.position.x += _right.x * bobX + n(4) * shPos * 0.045;
    cam.position.y += n(5) * shPos * 0.035;
    cam.position.z += _right.z * bobX + n(6) * shPos * 0.045;
    const downRoll = this.downed ? 0.18 : 0;
    cam.rotation.set(
      this.pitch + this.recoilPitch + n(1) * shRot * 0.05,
      this.yaw + this.recoilYaw + n(2) * shRot * 0.05,
      n(3) * shRot * 0.04 + this.hurtTilt + downRoll + bobRoll,
      'YXZ');
    cam.updateMatrixWorld();
  }
}
