"""Zombie animation: procedural keyframing with analytic foot placement (no foot sliding),
asymmetric limping gaits and looping secondary motion.

All clips are authored at 30 fps.  Locomotion clips are in place: the stance foot moves
backward at exactly the reported speed, so the game can drive them at that speed and the
feet will be planted.
"""
import math, random
from mathutils import Vector, Matrix, Euler

import lib_char as L
from zombie_rig import (J, SKELETON, THIGH_LEN, SHIN_LEN, LEG_LEN, ARM_LEN)

FPS = 30
DEG = math.radians

HEEL = Vector((0.0, 0.050, -0.090))     # ankle -> heel contact (foot rest frame)
BALL = Vector((0.0, -0.115, -0.090))    # ankle -> ball contact


# ---------------------------------------------------------------------------------------
# looping noise: sum of harmonics, exactly periodic over u in [0,1)
# ---------------------------------------------------------------------------------------

_NOISE_CACHE = {}


def noise_curve(seed, harmonics=(1, 2, 3, 5)):
    key = (seed, harmonics)
    if key not in _NOISE_CACHE:
        rnd = random.Random(seed)
        terms = [(1.0 / h, rnd.random() * math.tau, h) for h in harmonics]
        norm = sum(a for a, _, _ in terms)
        _NOISE_CACHE[key] = ([(a / norm, p, h) for a, p, h in terms])
    return _NOISE_CACHE[key]


def lnoise(u, seed, harmonics=(1, 2, 3, 5)):
    """Smooth pseudo-random signal in [-1,1] that loops over u."""
    return sum(a * math.sin(math.tau * h * u + p) for a, p, h in noise_curve(seed, harmonics))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_io(t, p=2.0):
    t = max(0.0, min(1.0, t))
    return t ** p / (t ** p + (1 - t) ** p)


def seg(t, a, b):
    """Normalised position of t inside [a,b]."""
    if b <= a:
        return 0.0
    return max(0.0, min(1.0, (t - a) / (b - a)))


# ---------------------------------------------------------------------------------------
# posing helpers
# ---------------------------------------------------------------------------------------

class Poser:
    def __init__(self, rig):
        self.rig = rig
        self.rest_rot = {n: rig.rest[n].to_3x3().to_4x4() for n in rig.spec}

    def begin(self):
        self.rig.reset()

    # --- root / hips -------------------------------------------------------------
    def root(self, loc=(0, 0, 0), pitch=0.0, roll=0.0, yaw=0.0):
        m = (Matrix.Translation(Vector(loc)) @
             Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4() @
             self.rest_rot['root'])
        self.rig.set_world('root', m)

    def hips(self, pos, pitch=0.0, roll=0.0, yaw=0.0):
        m = (Matrix.Translation(Vector(pos)) @
             Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4() @
             self.rest_rot['hips'])
        self.rig.set_world('hips', m)

    def spine_chain(self, spine=(0, 0, 0), chest=(0, 0, 0), neck=(0, 0, 0), head=(0, 0, 0)):
        for name, v in (('spine', spine), ('chest', chest), ('neck', neck), ('head', head)):
            self.rig.set_euler(name, v[0], v[1], v[2])

    # --- arms (FK) ---------------------------------------------------------------
    def arm(self, side, shoulder=(0, 0, 0), upper=(0, 0, 0), elbow=0.0, hand=(0, 0, 0)):
        s = 1.0 if side == 'L' else -1.0
        self.rig.set_euler('shoulder_' + side, shoulder[0], shoulder[1], shoulder[2] * s)
        self.rig.set_euler('upperarm_' + side, upper[0], upper[1] * s, upper[2] * s)
        self.rig.set_euler('forearm_' + side, elbow, 0.0, 0.0)
        self.rig.set_euler('hand_' + side, hand[0], hand[1] * s, hand[2] * s)

    # --- arms (IK to a wrist target) ---------------------------------------------
    def arm_ik(self, side, target, pole=None, shoulder=(0, 0, 0), hand=(0, 0, 0),
               hand_dir=None):
        s = 1.0 if side == 'L' else -1.0
        self.rig.set_euler('shoulder_' + side, shoulder[0], shoulder[1], shoulder[2] * s)
        if pole is None:
            pole = Vector((0.55 * s, 0.9, -0.3))
        self.rig.two_bone_ik('upperarm_' + side, 'forearm_' + side, Vector(target), pole)
        if hand_dir is not None:
            self.rig.aim('hand_' + side, Vector(hand_dir))
        else:
            self.rig.set_euler('hand_' + side, hand[0], hand[1] * s, hand[2] * s)

    # --- legs --------------------------------------------------------------------
    def leg(self, side, ankle, pitch=0.0, yaw=0.0, toe=0.0, knee_out=0.35):
        s = 1.0 if side == 'L' else -1.0
        pole = Vector((knee_out * s, -1.0, 0.0))
        self.rig.two_bone_ik('thigh_' + side, 'shin_' + side, Vector(ankle), pole)
        m = (Matrix.Translation(Vector(ankle)) @
             Matrix.Rotation(yaw, 4, 'Z') @
             Matrix.Rotation(-pitch, 4, 'X') @
             self.rest_rot['foot_' + side])
        self.rig.set_world('foot_' + side, m)
        self.rig.set_euler('toe_' + side, toe, 0, 0)


def foot_pose_from_pivot(pivot_world, pitch, yaw, pivot_local):
    """Ankle position that puts `pivot_local` (foot-rest-frame) at `pivot_world`."""
    r = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'X')
    return Vector(pivot_world) - (r @ Vector(pivot_local))


# ---------------------------------------------------------------------------------------
# gait
# ---------------------------------------------------------------------------------------

class Leg:
    def __init__(self, side, phase, duty, front, lift, x, yaw=0.0,
                 heel_pitch=DEG(11), toe_off=DEG(-38), swing_tuck=0.0, knee_out=0.35,
                 drag=0.0):
        self.side = side
        self.phase = phase
        self.duty = duty
        self.front = front            # fraction of the excursion ahead of the body
        self.lift = lift
        self.x = x
        self.yaw = yaw
        self.heel_pitch = heel_pitch
        self.toe_off = toe_off
        self.swing_tuck = swing_tuck
        self.knee_out = knee_out
        self.drag = drag              # 0 = normal, 1 = foot scuffs along the ground


class Gait:
    """Analytic foot placement for a looping locomotion cycle."""

    def __init__(self, v, T, legs):
        self.v = v
        self.T = T
        self.legs = {l.side: l for l in legs}

    def stance_geometry(self, leg):
        E = self.v * leg.duty * self.T
        tau0 = leg.phase * self.T
        # heel contact point in ground space so that mid-stance sits under the body
        yg_heel = HEEL.y - self.v * (tau0 + leg.duty * self.T * leg.front)
        return E, tau0, yg_heel

    def ankle_at(self, leg, s):
        """s = leg-local cycle phase in [0,1). Returns (ankle Vector, pitch, toe)."""
        E, tau0, yg_heel = self.stance_geometry(leg)
        yg_ball = yg_heel - HEEL.y + BALL.y
        if s < leg.duty:
            t = s / leg.duty
            tau = tau0 + t * leg.duty * self.T
            if t < 0.20:
                k = smooth(t / 0.20)
                pitch = leg.heel_pitch * (1 - k)
                pivot, pw = HEEL, yg_heel
            elif t < 0.62:
                pitch = 0.0
                pivot, pw = BALL, yg_ball
            else:
                k = ease_io(seg(t, 0.62, 1.0), 1.7)
                pitch = leg.toe_off * k
                pivot, pw = BALL, yg_ball
            a = foot_pose_from_pivot(Vector((leg.x, pw, 0.0)), pitch, leg.yaw, pivot)
            a.y += self.v * tau            # ground -> body frame
            toe = max(0.0, -pitch * 0.85)
            return a, pitch, toe
        # ---- swing
        t = (s - leg.duty) / (1.0 - leg.duty)
        a0, p0, _ = self.ankle_at(leg, leg.duty - 1e-4)
        a1, p1, _ = self.ankle_at(leg, 0.0)
        k = ease_io(t, 1.6)
        y = a0.y + (a1.y - a0.y) * k + leg.swing_tuck * math.sin(math.pi * t) * (1 - t)
        lift = leg.lift * math.sin(math.pi * (t ** 0.75))
        z = a0.z + (a1.z - a0.z) * k + lift
        x = a0.x + (a1.x - a0.x) * k
        # foot: toe-off angle recovers, toe lifts mid-swing, heel-strike angle at landing
        if t < 0.45:
            pitch = p0 + (DEG(8) - p0) * smooth(t / 0.45)
        else:
            pitch = DEG(8) + (p1 - DEG(8)) * smooth(seg(t, 0.45, 1.0))
        if leg.drag > 0:
            z = min(z, 0.006 + 0.05 * leg.drag * math.sin(math.pi * t) + 0.002)
            pitch = min(pitch, DEG(2))
        return Vector((x, y, z)), pitch, max(0.0, -pitch * 0.7)

    def max_reach(self, hip_z_fn, hip_xy_fn, samples=120):
        worst = 0.0
        for i in range(samples):
            u = i / samples
            for leg in self.legs.values():
                s = (u - leg.phase) % 1.0
                a, _, _ = self.ankle_at(leg, s)
                hx, hy = hip_xy_fn(u, leg.side)
                hz = hip_z_fn(u)
                d = (Vector((hx, hy, hz)) - a).length
                worst = max(worst, d)
        return worst


# ---------------------------------------------------------------------------------------
# locomotion clips
# ---------------------------------------------------------------------------------------

class Loco:
    """Tuning for one locomotion cycle."""

    def __init__(self, name, v, frames, legs, hip_z, bob=0.022, bob_phase=0.0,
                 sway=0.022, sway_phase=0.0, pelvis_yaw=DEG(6), pelvis_roll=DEG(3),
                 lean=DEG(12), side_lean=DEG(4), spine_twist=DEG(5),
                 head=(DEG(6), DEG(-10), DEG(7)), head_wobble=DEG(5),
                 arms=None, shoulder_drop=DEG(4), jitter=0.0, head_lag=DEG(0)):
        self.name = name
        self.v = v
        self.frames = frames
        self.legs = legs
        self.hip_z = hip_z
        self.bob = bob
        self.bob_phase = bob_phase
        self.sway = sway
        self.sway_phase = sway_phase
        self.pelvis_yaw = pelvis_yaw
        self.pelvis_roll = pelvis_roll
        self.lean = lean
        self.side_lean = side_lean
        self.spine_twist = spine_twist
        self.head = head
        self.head_wobble = head_wobble
        self.arms = arms or (lambda u, side: (DEG(10), DEG(8), 0.0, DEG(30), 0.0))
        self.shoulder_drop = shoulder_drop
        self.jitter = jitter
        self.head_lag = head_lag

    @property
    def T(self):
        return self.frames / float(FPS)


def build_loco(rig, st):
    """Keyframe a looping locomotion clip; returns (action, achieved speed)."""
    gait = Gait(st.v, st.T, st.legs)

    HIP_DROP = J['hips'].z - J['hip_L'].z          # hips bone -> femur head

    def hip_z_fn(u):
        return st.hip_z - HIP_DROP + st.bob * math.cos(math.tau * 2 * u + st.bob_phase)

    def hip_xy_fn(u, side):
        s = 1 if side == 'L' else -1
        sway = st.sway * math.sin(math.tau * u + st.sway_phase)
        yaw = st.pelvis_yaw * math.sin(math.tau * u + st.sway_phase)
        hx = J['hip_' + side].x + sway
        hy = J['hip_' + side].y - s * math.sin(yaw) * abs(J['hip_' + side].x)
        return hx, hy

    reach = gait.max_reach(hip_z_fn, hip_xy_fn)
    limit = LEG_LEN * 0.975
    if reach > limit:
        st.hip_z -= (reach - limit) * 1.02
        reach = gait.max_reach(hip_z_fn, hip_xy_fn)

    act = L.new_action(rig, st.name)
    p = Poser(rig)
    N = st.frames
    for f in range(N + 1):
        u = (f % N) / float(N)
        p.begin()
        p.root((0, 0, 0))
        sway = st.sway * math.sin(math.tau * u + st.sway_phase)
        bob = st.bob * math.cos(math.tau * 2 * u + st.bob_phase)
        jn = st.jitter * lnoise(u, 11, (2, 3, 5, 7))
        p.hips((sway + jn * 0.01, 0.010 + 0.010 * math.cos(math.tau * 2 * u), st.hip_z + bob),
               pitch=st.lean * 0.35 + DEG(2) * lnoise(u, 3, (2, 4)),
               roll=st.pelvis_roll * math.sin(math.tau * u + st.sway_phase + 0.4),
               yaw=st.pelvis_yaw * math.sin(math.tau * u + st.sway_phase))
        tw = -st.spine_twist * math.sin(math.tau * u + st.sway_phase)
        wob = lnoise(u, 5, (1, 2, 3))
        wob2 = lnoise(u + 0.27, 9, (1, 2, 3, 5))
        # the head lags behind the chest by ~1/12 cycle: dead weight on a slack neck
        lag = math.sin(math.tau * (u - 0.085) + st.sway_phase)
        lagz = st.head_lag * lag
        p.spine_chain(
            spine=(st.lean * 0.30, tw * 0.45, st.side_lean * 0.45 + DEG(2) * wob),
            chest=(st.lean * 0.35, tw * 0.55, st.side_lean * 0.55 + DEG(2.5) * wob2),
            neck=(st.head[0] * 0.5 - st.lean * 0.45, -tw * 0.4 + lagz * 0.4,
                  st.head[2] * 0.5 + st.head_wobble * 0.6 * wob2 - lagz * 0.5),
            head=(st.head[0] * 0.5 + st.head[1] * 0.0 + DEG(3) * wob + lagz * 0.35,
                  -tw * 0.5 + st.head_wobble * 0.5 * wob + lagz * 0.6,
                  st.head[2] * 0.5 + st.head_wobble * wob2 - lagz * 0.8))
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            ua_p, ua_b, ua_t, el, hp = st.arms(u, side)
            p.arm(side,
                  shoulder=(st.shoulder_drop * (0.6 if side == 'R' else 1.0) * (
                      0.5 + 0.5 * math.sin(math.tau * u + (0 if side == 'L' else math.pi))),
                      0, 0),
                  upper=(ua_p, ua_t, ua_b), elbow=el, hand=(hp, 0, 0))
        for side in ('L', 'R'):
            leg = gait.legs[side]
            sph = (u - leg.phase) % 1.0
            ankle, pitch, toe = gait.ankle_at(leg, sph)
            p.leg(side, ankle, pitch=pitch, yaw=leg.yaw, toe=toe, knee_out=leg.knee_out)
        rig.key(f)
    L.finish_action(act, N)
    return act, st.v, reach


def walk_style():
    legs = [
        Leg('R', 0.00, 0.62, 0.44, 0.085, -J['hip_L'].x - 0.012, yaw=DEG(-7),
            heel_pitch=DEG(12), toe_off=DEG(-40), swing_tuck=0.045, knee_out=0.30),
        # left leg is the bad one: short stance, dragged, stiff knee
        Leg('L', 0.54, 0.54, 0.50, 0.030, J['hip_L'].x + 0.020, yaw=DEG(12),
            heel_pitch=DEG(2), toe_off=DEG(-16), swing_tuck=0.010, knee_out=0.55,
            drag=0.55),
    ]

    def arms(u, side):
        # The walker's signature: the right arm is completely dead - it hangs from a
        # limp shoulder and swings passively at HALF the leg frequency, a beat behind.
        # The left is half raised and clawed and barely moves at all.
        if side == 'R':
            sw = math.sin(math.pi * (u - 0.22) * 2.0 * 0.5)        # half frequency
            return (DEG(8) + DEG(13) * sw + DEG(3) * lnoise(u, 21),
                    DEG(-6) + DEG(4) * lnoise(u, 22),
                    DEG(-10),
                    DEG(20) + DEG(14) * max(0.0, sw) + DEG(4) * lnoise(u, 23),
                    DEG(-14) + DEG(10) * lnoise(u, 24))
        sw = math.sin(math.tau * (u - 0.32))
        return (DEG(54) + DEG(5) * sw + DEG(5) * lnoise(u, 31),
                DEG(10) + DEG(4) * lnoise(u, 32),
                DEG(16),
                DEG(80) + DEG(6) * sw + DEG(6) * lnoise(u, 33),
                DEG(-28) + DEG(9) * lnoise(u, 34))

    return Loco('walk', 0.90, 36, legs, hip_z=0.866, bob=0.020, bob_phase=DEG(35),
                sway=0.034, sway_phase=0.0, pelvis_yaw=DEG(8), pelvis_roll=DEG(6),
                lean=DEG(14), side_lean=DEG(11), spine_twist=DEG(6),
                head=(DEG(10), 0, DEG(9)), head_wobble=DEG(7), arms=arms,
                shoulder_drop=DEG(7), jitter=0.6, head_lag=DEG(6))


def run_style():
    legs = [
        Leg('R', 0.00, 0.44, 0.40, 0.145, -J['hip_L'].x - 0.010, yaw=DEG(-5),
            heel_pitch=DEG(6), toe_off=DEG(-44), swing_tuck=0.085, knee_out=0.35),
        Leg('L', 0.52, 0.40, 0.44, 0.105, J['hip_L'].x + 0.016, yaw=DEG(9),
            heel_pitch=DEG(2), toe_off=DEG(-30), swing_tuck=0.055, knee_out=0.50),
    ]

    def arms(u, side):
        # runner: a real 25 degree counter-swing driven off the same signal as the legs
        ph = 0.0 if side == 'R' else 0.5
        sw = math.sin(math.tau * (u - 0.12 + ph))
        if side == 'R':
            return (DEG(24) + DEG(25) * sw + DEG(6) * lnoise(u, 41),
                    DEG(26) + DEG(8) * lnoise(u, 42),
                    DEG(-14),
                    DEG(62) + DEG(30) * max(0.0, sw) + DEG(8) * lnoise(u, 43),
                    DEG(-16) + DEG(10) * lnoise(u, 44))
        return (DEG(44) + DEG(25) * sw + DEG(7) * lnoise(u, 51),
                DEG(38) + DEG(9) * lnoise(u, 52),
                DEG(12),
                DEG(84) + DEG(24) * sw + DEG(8) * lnoise(u, 53),
                DEG(-26) + DEG(11) * lnoise(u, 54))

    return Loco('run', 2.60, 22, legs, hip_z=0.874, bob=0.036, bob_phase=DEG(160),
                sway=0.020, sway_phase=0.0, pelvis_yaw=DEG(10), pelvis_roll=DEG(5),
                lean=DEG(24), side_lean=DEG(6), spine_twist=DEG(11),
                head=(DEG(4), 0, DEG(7)), head_wobble=DEG(7), arms=arms,
                shoulder_drop=DEG(7), jitter=1.0, head_lag=DEG(5))


def sprint_style():
    legs = [
        Leg('R', 0.00, 0.34, 0.36, 0.185, -J['hip_L'].x - 0.006, yaw=DEG(-3),
            heel_pitch=DEG(0), toe_off=DEG(-48), swing_tuck=0.110, knee_out=0.30),
        Leg('L', 0.50, 0.33, 0.38, 0.165, J['hip_L'].x + 0.010, yaw=DEG(6),
            heel_pitch=DEG(0), toe_off=DEG(-44), swing_tuck=0.100, knee_out=0.40),
    ]

    def arms(u, side):
        # sprinter: a hard 60 degree pump, head leading, elbows snapping through
        ph = 0.0 if side == 'R' else 0.5
        sw = math.sin(math.tau * (u - 0.08 + ph))
        return (DEG(18) + DEG(60) * sw + DEG(6) * lnoise(u, 61 + (0 if side == 'R' else 10)),
                DEG(16) + DEG(7) * lnoise(u, 62),
                DEG(-10) if side == 'R' else DEG(8),
                DEG(78) + DEG(52) * max(0.0, sw) + DEG(8) * lnoise(u, 63),
                DEG(-18) + DEG(10) * lnoise(u, 64))

    return Loco('sprint', 4.20, 16, legs, hip_z=0.884, bob=0.040, bob_phase=DEG(170),
                sway=0.014, sway_phase=0.0, pelvis_yaw=DEG(12), pelvis_roll=DEG(4),
                lean=DEG(36), side_lean=DEG(3), spine_twist=DEG(14),
                head=(DEG(-8), 0, DEG(4)), head_wobble=DEG(5), arms=arms,
                shoulder_drop=DEG(9), jitter=1.2, head_lag=DEG(4))


# ---------------------------------------------------------------------------------------
# standing base pose used by idle / attack / tear / hit
# ---------------------------------------------------------------------------------------

STAND_HIP = 0.905


def stand(p, u=0.0, lean=DEG(11), sway=1.0, hip_dz=0.0, hip_dy=0.0, hip_dx=0.0,
          twist=0.0, head=(DEG(8), 0.0, DEG(10)), breathe=1.0, seed=0):
    """Weight on the right leg, left leg slack: the resting zombie stance."""
    s1 = lnoise(u, 101 + seed, (1, 2, 3))
    s2 = lnoise(u + 0.4, 107 + seed, (1, 2, 3, 5))
    s3 = lnoise(u + 0.7, 113 + seed, (1, 2, 4))
    hz = STAND_HIP + hip_dz + sway * 0.012 * s1 + breathe * 0.006 * math.sin(math.tau * u)
    p.hips((hip_dx + 0.030 + sway * 0.016 * s2, hip_dy + 0.012, hz),
           pitch=lean * 0.30 + DEG(2) * s1,
           roll=DEG(-5) + DEG(3) * s2,
           yaw=twist * 0.3 + DEG(3) * s3)
    p.spine_chain(
        spine=(lean * 0.30, twist * 0.25 + DEG(3) * s2, DEG(5) + DEG(3) * s1),
        chest=(lean * 0.40, twist * 0.35 + DEG(4) * s3, DEG(7) + DEG(3) * s2),
        neck=(head[0] * 0.45 - lean * 0.40, head[1] * 0.4 + DEG(3) * s1,
              head[2] * 0.45 + DEG(4) * s3),
        head=(head[0] * 0.55 + DEG(3) * s2, head[1] * 0.6 + DEG(5) * s2,
              head[2] * 0.55 + DEG(5) * s1))
    return s1, s2, s3


def stand_legs(p, hz_extra=0.0):
    aL = Vector((J['ankle_L'].x + 0.018, -0.070, 0.092))
    aR = Vector((J['ankle_R'].x - 0.004, 0.035, 0.092))
    p.leg('L', aL, pitch=DEG(-4), yaw=DEG(14), toe=DEG(4), knee_out=0.55)
    p.leg('R', aR, pitch=DEG(2), yaw=DEG(-7), toe=0.0, knee_out=0.30)


def hang_arms(p, u=0.0, amount=1.0):
    p.arm('R', shoulder=(DEG(3), 0, 0),
          upper=(DEG(16) + DEG(5) * lnoise(u, 201), DEG(-8), DEG(-5) + DEG(3) * lnoise(u, 202)),
          elbow=DEG(36) + DEG(9) * lnoise(u, 203),
          hand=(DEG(-16) + DEG(10) * lnoise(u, 204), 0, 0))
    p.arm('L', shoulder=(DEG(6), 0, 0),
          upper=(DEG(52) + DEG(7) * lnoise(u, 211), DEG(10), DEG(4) + DEG(4) * lnoise(u, 212)),
          elbow=DEG(88) + DEG(8) * lnoise(u, 213),
          hand=(DEG(-30) + DEG(12) * lnoise(u, 214), 0, 0))


# ---------------------------------------------------------------------------------------
# keyed interpolation for the one-shot clips
# ---------------------------------------------------------------------------------------

def kf(t, keys, ease=1.6):
    """Interpolate a list of (time, value) with smooth easing. Values may be float/Vector."""
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            k = ease_io((t - t0) / (t1 - t0), ease)
            if isinstance(v0, Vector):
                return v0.lerp(v1, k)
            return v0 + (v1 - v0) * k
    return keys[-1][1]


def V(*a):
    return Vector(a)


def twitch(u, at, width, sharp=3.0):
    """A short loop-safe impulse centred on `at`."""
    d = (u - at + 0.5) % 1.0 - 0.5
    x = abs(d) / width
    if x >= 1.0:
        return 0.0
    return (1 - x) ** sharp * math.cos(d / width * math.pi * 1.5)


# ---------------------------------------------------------------------------------------
# idle
# ---------------------------------------------------------------------------------------

def build_idle(rig, frames=120):
    """Swaying and twitchy: three sharp 2-frame head/shoulder snaps per cycle on top of
    the sway, at roughly 3x the old jerk amplitude (review #23)."""
    act = L.new_action(rig, 'idle')
    p = Poser(rig)
    for f in range(frames + 1):
        u = (f % frames) / float(frames)
        p.begin()
        p.root((0, 0, 0))
        # sharp, short snaps - width 0.017 of a 4 s cycle is ~2 frames
        snap = (twitch(u, 0.185, 0.018, 4.0) + 0.85 * twitch(u, 0.52, 0.016, 4.0) +
                0.70 * twitch(u, 0.815, 0.017, 4.0))
        jerk = twitch(u, 0.31, 0.055) + 0.7 * twitch(u, 0.74, 0.04) + 1.4 * snap
        shudder = twitch(u, 0.58, 0.09, 2.0) + 0.9 * twitch(u, 0.06, 0.07, 2.0)
        s1, s2, s3 = stand(p, u, lean=DEG(11) + DEG(9) * shudder,
                           twist=DEG(10) * snap,
                           head=(DEG(9) + DEG(44) * jerk, DEG(52) * jerk,
                                 DEG(12) + DEG(40) * jerk))
        stand_legs(p)
        hang_arms(p, u)
        # twitches ride on top of the hanging arms
        rig.set_euler('upperarm_R', DEG(12) + DEG(5) * lnoise(u, 201) + DEG(40) * jerk,
                      DEG(-6), DEG(8) + DEG(3) * lnoise(u, 202) + DEG(16) * snap)
        rig.set_euler('forearm_R', DEG(30) + DEG(9) * lnoise(u, 203) + DEG(52) * jerk)
        rig.set_euler('forearm_L', DEG(78) + DEG(8) * lnoise(u, 213) + DEG(34) * shudder)
        rig.set_euler('shoulder_L', DEG(14) * snap, 0, 0)
        rig.set_euler('shoulder_R', DEG(-10) * snap, 0, 0)
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# attack: two handed overhead rake, contact at 45%
# ---------------------------------------------------------------------------------------

def build_attack(rig, frames=27, lead='R', name='attack'):
    """A fast diagonal one-arm claw swipe across the body, contact at 45%.

    The old clip raised both arms straight over the head in a symmetric 'hooray' -
    the cartoon-zombie cliche.  This is a BO2 swipe: wind up across and behind the
    shoulder 0-35%, rip down-and-across through the target at 45% with the hips
    rotating ~20 degrees into it, follow through past the far hip, recover (#12).
    """
    act = L.new_action(rig, name)
    p = Poser(rig)
    s = 1.0 if lead == 'L' else -1.0        # +X is the character's left
    off = 'R' if lead == 'L' else 'L'
    so = -s
    # leading wrist: out and back over the shoulder -> across the chest -> past the hip
    wr_lead = [(0.00, V(s * 0.27, -0.22, 1.05)),
               (0.18, V(s * 0.40, 0.12, 1.34)),
               (0.34, V(s * 0.48, 0.22, 1.44)),      # wound up BEHIND the shoulder, not
                                                     # over the head - that was the tell
               (0.45, V(so * 0.06, -0.58, 1.28)),    # contact, across the body
               (0.56, V(so * 0.30, -0.44, 0.98)),    # follow through past the far hip
               (0.72, V(so * 0.22, -0.26, 0.88)),
               (0.88, V(s * 0.16, -0.24, 0.94)),
               (1.00, V(s * 0.27, -0.22, 1.04))]
    # trailing arm: hangs back and counterweights, never mirrors the swipe
    wr_off = [(0.00, V(so * 0.27, -0.20, 1.06)),
              (0.20, V(so * 0.30, -0.34, 1.16)),
              (0.36, V(so * 0.28, -0.44, 1.22)),
              (0.50, V(so * 0.34, -0.10, 1.06)),
              (0.68, V(so * 0.32, 0.06, 0.96)),
              (0.86, V(so * 0.28, -0.12, 1.00)),
              (1.00, V(so * 0.27, -0.20, 1.05))]
    lean_k = [(0.0, DEG(10)), (0.30, DEG(-6)), (0.45, DEG(24)), (0.60, DEG(32)),
              (0.80, DEG(20)), (1.0, DEG(12))]
    # the hips rotate ~20 degrees into the swing and unwind through contact
    twist_k = [(0.0, 0.0), (0.34, DEG(22) * s), (0.45, DEG(-14) * s),
               (0.62, DEG(-20) * s), (1.0, DEG(-2) * s)]
    hipz_k = [(0.0, 0.0), (0.30, 0.018), (0.45, -0.038), (0.62, -0.056), (1.0, -0.006)]
    hipy_k = [(0.0, 0.0), (0.24, 0.042), (0.45, -0.078), (0.62, -0.104), (0.82, -0.058),
              (1.0, -0.010)]
    for f in range(frames + 1):
        t = f / float(frames)
        p.begin()
        p.root((0, 0, 0))
        lean = kf(t, lean_k, 1.9)
        tw = kf(t, twist_k, 1.9)
        stand(p, t * 0.5, lean=lean, sway=0.3, hip_dz=kf(t, hipz_k, 1.9),
              hip_dy=kf(t, hipy_k, 1.9), twist=tw,
              head=(DEG(4) + lean * 0.3, tw * 0.7, DEG(6)), breathe=0.0, seed=1)
        step = kf(t, [(0.0, 0.0), (0.22, -0.02), (0.45, -0.10), (0.62, -0.13),
                      (0.85, -0.10), (1.0, -0.03)], 1.8)
        aL = V(J['ankle_L'].x + 0.030, -0.115 + step * (1.0 if lead == 'R' else 0.4), 0.092)
        aR = V(J['ankle_R'].x - 0.012, 0.075 + step * (1.0 if lead == 'L' else 0.0), 0.092)
        p.leg('L', aL, pitch=DEG(-2), yaw=DEG(14), knee_out=0.6)
        p.leg('R', aR, pitch=DEG(4), yaw=DEG(-8), knee_out=0.3)
        # the leading shoulder drives all the way through the swing
        shl = kf(t, [(0.0, DEG(4)), (0.34, DEG(24)), (0.45, DEG(-4)), (0.60, DEG(-16)),
                     (1.0, DEG(4))], 1.6)
        sho = kf(t, [(0.0, DEG(4)), (0.34, DEG(-8)), (0.60, DEG(12)), (1.0, DEG(4))], 1.6)
        pole_l = V(s * 0.9, 0.55, -0.35)
        pole_o = V(so * 0.9, 0.7, -0.3)
        p.arm_ik(lead, kf(t, wr_lead, 1.7), pole=pole_l,
                 shoulder=(shl, 0, DEG(7)), hand=(DEG(-34), 0, 0))
        p.arm_ik(off, kf(t, wr_off, 1.6), pole=pole_o,
                 shoulder=(sho, 0, DEG(3)), hand=(DEG(-20), 0, 0))
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# tear: grab a board and rip it toward itself
# ---------------------------------------------------------------------------------------

def build_tear(rig, frames=36):
    """Left hand braces on the window frame, right hand yanks a board free, and the
    whole body recoils for three frames when it gives at ~55% (review #15)."""
    act = L.new_action(rig, 'tear')
    p = Poser(rig)
    BREAK = 0.55
    # right arm: grip, load, then rip back and away past the hip
    wr_R = [(0.00, V(-0.26, -0.24, 1.10)), (0.22, V(-0.18, -0.60, 1.24)),
            (0.40, V(-0.17, -0.64, 1.23)), (0.52, V(-0.19, -0.66, 1.21)),
            (BREAK, V(-0.22, -0.50, 1.18)), (0.66, V(-0.34, -0.10, 1.02)),
            (0.80, V(-0.40, 0.14, 0.92)), (1.00, V(-0.27, -0.20, 1.08))]
    # left arm: plants on the frame at 20% and stays put - it is the brace
    wr_L = [(0.00, V(0.27, -0.26, 1.14)), (0.18, V(0.22, -0.62, 1.34)),
            (0.34, V(0.21, -0.65, 1.33)), (BREAK, V(0.21, -0.65, 1.33)),
            (0.68, V(0.22, -0.62, 1.30)), (0.84, V(0.25, -0.40, 1.18)),
            (1.00, V(0.26, -0.22, 1.12))]
    lean_k = [(0.0, DEG(12)), (0.34, DEG(26)), (0.50, DEG(30)), (BREAK, DEG(28)),
              (0.64, DEG(-14)), (0.78, DEG(-16)), (1.0, DEG(10))]
    hipy_k = [(0.0, 0.0), (0.34, -0.052), (0.50, -0.062), (BREAK, -0.060),
              (0.66, 0.062), (0.80, 0.070), (1.0, 0.0)]
    hipz_k = [(0.0, 0.0), (0.34, -0.022), (0.50, -0.030), (0.68, -0.058), (0.82, -0.042),
              (1.0, -0.004)]
    twist_k = [(0.0, 0.0), (0.34, DEG(-12)), (0.50, DEG(-16)), (BREAK, DEG(-14)),
               (0.66, DEG(16)), (0.82, DEG(10)), (1.0, 0.0)]
    for f in range(frames + 1):
        t = f / float(frames)
        p.begin()
        p.root((0, 0, 0))
        lean = kf(t, lean_k, 1.8)
        # straining shudder while it is loaded, then a hard 3-frame snap-back
        strain = math.sin(t * 74.0) * max(0.0, 1.0 - abs(t - 0.46) / 0.14) * DEG(2.6)
        snap = math.exp(-26.0 * max(0.0, t - BREAK)) * (1.0 if t >= BREAK else 0.0)
        stand(p, t * 0.5, lean=lean - DEG(22) * snap, sway=0.4,
              hip_dz=kf(t, hipz_k, 1.8), hip_dy=kf(t, hipy_k, 1.8),
              twist=kf(t, twist_k, 1.7) + DEG(10) * snap,
              head=(DEG(2) + lean * 0.35 + strain - DEG(30) * snap,
                    strain * 2 + DEG(14) * snap, DEG(8)), breathe=0.0, seed=2)
        # weight shifts onto the back foot as it pulls
        aL = V(J['ankle_L'].x + 0.030, -0.100 - 0.020 * snap, 0.092)
        aR = V(J['ankle_R'].x - 0.012, 0.055 + 0.055 * smooth(seg(t, BREAK, 0.72)), 0.092)
        p.leg('L', aL, pitch=DEG(-3), yaw=DEG(13), knee_out=0.6)
        p.leg('R', aR, pitch=DEG(3), yaw=DEG(-7), knee_out=0.3)
        curl_R = DEG(-10) - DEG(34) * smooth(seg(t, 0.14, 0.34))
        curl_L = DEG(-10) - DEG(30) * smooth(seg(t, 0.10, 0.26))
        p.arm_ik('R', kf(t, wr_R, 1.7) + V(0, strain * 0.4, strain * 0.2),
                 pole=V(-0.9, 0.7, -0.35),
                 shoulder=(DEG(14) * smooth(seg(t, 0.1, 0.4)) - DEG(10) * snap, 0, DEG(-6)),
                 hand=(curl_R, 0, 0))
        p.arm_ik('L', kf(t, wr_L, 1.6), pole=V(0.9, 0.8, -0.25),
                 shoulder=(DEG(6) * smooth(seg(t, 0.05, 0.3)), 0, DEG(-4)),
                 hand=(curl_L, 0, 0))
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# hit: short upper-body flinch
# ---------------------------------------------------------------------------------------

def build_hit(rig, frames=11):
    act = L.new_action(rig, 'hit')
    p = Poser(rig)
    k = [(0.0, 0.0), (0.22, 1.0), (0.45, 0.45), (0.7, 0.18), (1.0, 0.0)]
    for f in range(frames + 1):
        t = f / float(frames)
        a = kf(t, k, 1.4)
        p.begin()
        p.root((0, 0, 0))
        stand(p, 0.15, lean=DEG(11) - DEG(20) * a, sway=0.2,
              hip_dz=-0.020 * a, hip_dy=0.045 * a, twist=DEG(14) * a,
              head=(DEG(8) - DEG(30) * a, DEG(16) * a, DEG(10) + DEG(10) * a),
              breathe=0.0, seed=3)
        stand_legs(p)
        p.arm('R', shoulder=(DEG(3) + DEG(10) * a, 0, 0),
              upper=(DEG(12) - DEG(26) * a, DEG(-6), DEG(8) + DEG(18) * a),
              elbow=DEG(30) + DEG(34) * a, hand=(DEG(-14) - DEG(18) * a, 0, 0))
        p.arm('L', shoulder=(DEG(6) + DEG(12) * a, 0, 0),
              upper=(DEG(46) - DEG(30) * a, DEG(12), DEG(18) + DEG(22) * a),
              elbow=DEG(78) + DEG(26) * a, hand=(DEG(-26) - DEG(16) * a, 0, 0))
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# climb: through a window, sill 0.9 m, +1.4 m of root motion along -Y
# ---------------------------------------------------------------------------------------

def build_climb(rig, frames=54):
    act = L.new_action(rig, 'climb')
    p = Poser(rig)
    SILL = 0.90
    root_k = [(0.00, 0.00), (0.16, -0.08), (0.45, -0.58), (0.72, -1.10),
              (0.88, -1.34), (1.00, -1.40)]
    hipz_k = [(0.00, 0.905), (0.18, 0.840), (0.38, 1.020), (0.52, 1.060),
              (0.70, 0.930), (0.84, 0.865), (1.00, 0.905)]
    lean_k = [(0.00, DEG(14)), (0.20, DEG(34)), (0.45, DEG(48)), (0.62, DEG(40)),
              (0.80, DEG(22)), (1.00, DEG(12))]
    # hands grab the sill, then push off it
    wrR_k = [(0.00, V(-0.26, -0.20, 1.05)), (0.16, V(-0.30, -0.60, SILL + 0.04)),
             (0.40, V(-0.32, -0.62, SILL + 0.02)), (0.58, V(-0.32, -0.62, SILL + 0.02)),
             (0.70, V(-0.30, -0.95, 1.00)), (0.86, V(-0.30, -1.22, 0.98)),
             (1.00, V(-0.28, -1.58, 1.02))]
    wrL_k = [(0.00, V(0.27, -0.22, 1.08)), (0.16, V(0.30, -0.60, SILL + 0.04)),
             (0.40, V(0.32, -0.62, SILL + 0.02)), (0.62, V(0.32, -0.62, SILL + 0.02)),
             (0.74, V(0.30, -1.05, 0.96)), (0.88, V(0.30, -1.30, 0.94)),
             (1.00, V(0.28, -1.62, 1.06))]
    # right leg swings over first, then the left
    ankR_k = [(0.00, V(-0.11, 0.02, 0.092)), (0.20, V(-0.13, -0.18, 0.40)),
              (0.32, V(-0.14, -0.55, 1.02)), (0.44, V(-0.14, -0.78, 0.86)),
              (0.56, V(-0.13, -0.95, 0.092)), (1.00, V(-0.12, -0.95, 0.092))]
    ankL_k = [(0.00, V(0.11, 0.02, 0.092)), (0.30, V(0.12, -0.05, 0.10)),
              (0.46, V(0.13, -0.25, 0.44)), (0.60, V(0.14, -0.58, 1.04)),
              (0.74, V(0.13, -0.95, 0.80)), (0.86, V(0.12, -1.32, 0.092)),
              (1.00, V(0.12, -1.34, 0.092))]
    for f in range(frames + 1):
        t = f / float(frames)
        ry = kf(t, root_k, 1.5)
        p.begin()
        p.root((0, ry, 0))
        lean = kf(t, lean_k, 1.6)
        hz = kf(t, hipz_k, 1.6)
        p.hips((0.012 * math.sin(t * 7), ry + 0.02, hz), pitch=lean * 0.42,
               roll=DEG(7) * math.sin(t * 5.5), yaw=DEG(9) * math.sin(t * 4.0))
        p.spine_chain(spine=(lean * 0.30, DEG(5) * math.sin(t * 4), DEG(4)),
                      chest=(lean * 0.34, DEG(7) * math.sin(t * 4), DEG(5)),
                      neck=(DEG(6) - lean * 0.45, DEG(5), DEG(6)),
                      head=(DEG(10) - lean * 0.30, DEG(8) * math.sin(t * 3), DEG(8)))
        p.arm_ik('R', kf(t, wrR_k, 1.6), pole=V(-0.9, 0.9, -0.2),
                 shoulder=(DEG(10), 0, DEG(6)), hand=(DEG(-18), 0, 0))
        p.arm_ik('L', kf(t, wrL_k, 1.6), pole=V(0.9, 0.9, -0.2),
                 shoulder=(DEG(10), 0, DEG(6)), hand=(DEG(-18), 0, 0))
        p.leg('R', kf(t, ankR_k, 1.5), pitch=DEG(-14) * smooth(seg(t, 0.15, 0.4)),
              yaw=DEG(-8), knee_out=0.55)
        p.leg('L', kf(t, ankL_k, 1.5), pitch=DEG(-14) * smooth(seg(t, 0.45, 0.68)),
              yaw=DEG(10), knee_out=0.65)
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# rise: claws up out of the ground
# ---------------------------------------------------------------------------------------

def build_rise(rig, frames=66):
    act = L.new_action(rig, 'rise')
    p = Poser(rig)
    # Re-timed for review #14: one hand breaks the surface on its own and claws at the
    # ground for the first ~0.5 s; the second hand and then the head follow.
    #
    # The previous attempt set the wrist targets above ground from t = 0.02 but started
    # the hips at -1.40 m.  The shoulder was then 0.97 m below the target while the arm is
    # only 0.569 m long, so `two_bone_ik` clamped every one of those targets to max reach
    # and the hand never actually left the soil until t = 0.90 - exactly the "empty ground
    # then everything at once" the review filed.  The grave is now 0.92 m deep, which is
    # still deep enough to hide the head (top of skull at -0.13 m at t = 0) but inside the
    # arm's reach, and the reach is checked against ARM_LEN below.
    hip0 = -0.92
    hipz_k = [(0.00, hip0), (0.16, hip0 + 0.02), (0.30, -0.84), (0.44, -0.62),
              (0.58, -0.28), (0.70, 0.16), (0.82, 0.58), (0.92, 0.84), (1.00, 0.905)]
    lean_k = [(0.00, DEG(-6)), (0.22, DEG(4)), (0.40, DEG(30)), (0.58, DEG(46)),
              (0.76, DEG(34)), (0.90, DEG(18)), (1.00, DEG(12))]
    # right hand alone for the first third, scrabbling at the surface: four alternating
    # grabs that break ground at t = 0.04 and claw backwards
    wrR_k = [(0.00, V(-0.19, -0.04, -0.055)), (0.04, V(-0.21, -0.09, 0.062)),
             (0.09, V(-0.25, -0.17, 0.012)), (0.14, V(-0.29, -0.13, 0.072)),
             (0.19, V(-0.33, -0.21, 0.010)), (0.24, V(-0.37, -0.17, 0.066)),
             (0.30, V(-0.41, -0.25, 0.008)), (0.44, V(-0.43, -0.33, 0.030)),
             (0.58, V(-0.41, -0.43, 0.052)), (0.72, V(-0.36, -0.40, 0.34)),
             (0.85, V(-0.31, -0.30, 0.74)), (1.00, V(-0.27, -0.20, 1.02))]
    # left hand stays under the soil until 0.30 of the clip
    wrL_k = [(0.00, V(0.15, 0.02, -0.46)), (0.18, V(0.17, -0.02, -0.34)),
             (0.28, V(0.23, -0.08, -0.10)), (0.34, V(0.31, -0.16, 0.052)),
             (0.40, V(0.38, -0.20, 0.010)), (0.52, V(0.44, -0.30, 0.058)),
             (0.64, V(0.42, -0.42, 0.072)), (0.76, V(0.36, -0.34, 0.44)),
             (0.88, V(0.32, -0.26, 0.84)), (1.00, V(0.28, -0.22, 1.10))]
    for f in range(frames + 1):
        t = f / float(frames)
        hz = kf(t, hipz_k, 1.7)
        lean = kf(t, lean_k, 1.6)
        shudder = (twitch(t, 0.20, 0.05, 2.0) + twitch(t, 0.47, 0.05, 2.0) +
                   twitch(t, 0.68, 0.045, 2.0))
        p.begin()
        p.root((0, 0, 0))
        p.hips((0.03 * math.sin(t * 8) + 0.02 * shudder, 0.02, hz),
               pitch=lean * 0.40 + DEG(6) * shudder,
               roll=DEG(10) * math.sin(t * 6.5), yaw=DEG(12) * math.sin(t * 4.5))
        p.spine_chain(spine=(lean * 0.28, DEG(8) * math.sin(t * 5), DEG(6) * math.sin(t * 3)),
                      chest=(lean * 0.32, DEG(10) * math.sin(t * 5), DEG(7) * math.sin(t * 3)),
                      neck=(DEG(-14) + lean * 0.10, DEG(6), DEG(8)),
                      head=(DEG(-18) + lean * 0.25 + DEG(10) * shudder,
                            DEG(12) * math.sin(t * 4), DEG(10)))
        p.arm_ik('R', kf(t, wrR_k, 1.5), pole=V(-1.0, 0.6, -0.2),
                 shoulder=(DEG(12), 0, DEG(8)), hand=(DEG(-30), 0, 0))
        p.arm_ik('L', kf(t, wrL_k, 1.5), pole=V(1.0, 0.6, -0.2),
                 shoulder=(DEG(12), 0, DEG(8)), hand=(DEG(-30), 0, 0))
        # legs trail underground, then plant
        plantR = smooth(seg(t, 0.46, 0.60))
        plantL = smooth(seg(t, 0.66, 0.80))
        # tucked: knees folded, feet gathered under the hips
        tuckR = V(-0.13, 0.20, hz - 0.30)
        tuckL = V(0.14, 0.26, hz - 0.26)
        aR = tuckR.lerp(V(-0.12, -0.18, 0.092), plantR)
        aL = tuckL.lerp(V(0.14, 0.12, 0.092), plantL)
        p.leg('R', aR, pitch=DEG(-16) * (1 - plantR), yaw=DEG(-8), knee_out=0.5)
        p.leg('L', aL, pitch=DEG(-16) * (1 - plantL), yaw=DEG(12), knee_out=0.6)
        if f == 0:
            surf = {'R': None, 'L': None, 'head': None}
        for key, bone in (('R', 'hand_R'), ('L', 'hand_L'), ('head', 'head')):
            if surf[key] is None and rig.bone_head(bone).z > 0.0:
                surf[key] = t
        rig.key(f)
    # printed at build time so the "one hand first" timing is checked, not asserted
    print('[rise] surface crossings (fraction of clip): hand_R %s  hand_L %s  head %s'
          % tuple('%.2f' % v if v is not None else '-' for v in
                  (surf['R'], surf['L'], surf['head'])))
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------
# deaths
# ---------------------------------------------------------------------------------------

def build_death_back(rig, frames=45, name='death_back'):
    act = L.new_action(rig, name)
    p = Poser(rig)
    hip_k = [(0.00, V(0.03, 0.012, 0.905)), (0.12, V(0.03, 0.045, 0.880)),
             (0.30, V(0.02, 0.140, 0.720)), (0.50, V(0.01, 0.270, 0.420)),
             (0.68, V(0.00, 0.350, 0.210)), (0.80, V(0.00, 0.365, 0.160)),
             (1.00, V(0.00, 0.360, 0.155))]
    pitch_k = [(0.00, DEG(9)), (0.12, DEG(-16)), (0.30, DEG(-34)), (0.50, DEG(-62)),
               (0.68, DEG(-82)), (0.80, DEG(-88)), (1.00, DEG(-89))]
    spine_k = [(0.00, DEG(4)), (0.12, DEG(-14)), (0.34, DEG(-10)), (0.60, DEG(6)),
               (0.80, DEG(14)), (1.00, DEG(9))]
    head_k = [(0.00, DEG(6)), (0.10, DEG(-30)), (0.30, DEG(-24)), (0.60, DEG(4)),
              (0.78, DEG(26)), (0.90, DEG(16)), (1.00, DEG(18))]
    ankR_k = [(0.00, V(-0.10, 0.030, 0.092)), (0.22, V(-0.11, 0.010, 0.120)),
              (0.45, V(-0.12, -0.140, 0.280)), (0.66, V(-0.13, -0.330, 0.190)),
              (0.82, V(-0.13, -0.430, 0.085)), (1.00, V(-0.13, -0.445, 0.080))]
    ankL_k = [(0.00, V(0.12, -0.050, 0.092)), (0.24, V(0.13, -0.060, 0.150)),
              (0.48, V(0.14, -0.200, 0.330)), (0.70, V(0.15, -0.380, 0.230)),
              (0.86, V(0.15, -0.470, 0.088)), (1.00, V(0.15, -0.480, 0.082))]
    wrR_k = [(0.00, V(-0.26, -0.16, 1.02)), (0.16, V(-0.34, 0.02, 1.34)),
             (0.36, V(-0.40, 0.12, 1.16)), (0.58, V(-0.44, 0.26, 0.70)),
             (0.78, V(-0.42, 0.34, 0.24)), (1.00, V(-0.40, 0.30, 0.10))]
    wrL_k = [(0.00, V(0.27, -0.20, 1.06)), (0.16, V(0.36, -0.02, 1.38)),
             (0.36, V(0.42, 0.10, 1.20)), (0.58, V(0.46, 0.22, 0.74)),
             (0.78, V(0.44, 0.32, 0.26)), (1.00, V(0.42, 0.28, 0.12))]
    _death_body(rig, p, frames, hip_k, pitch_k, spine_k, head_k,
                ankR_k, ankL_k, wrR_k, wrL_k, roll_amp=DEG(7), knee_out=0.5, land=0.76)
    L.finish_action(act, frames)
    return act


def build_death_fwd(rig, frames=48, name='death_front'):
    act = L.new_action(rig, name)
    p = Poser(rig)
    hip_k = [(0.00, V(0.03, 0.012, 0.905)), (0.16, V(0.02, 0.020, 0.700)),
             (0.34, V(0.01, 0.010, 0.430)), (0.52, V(0.00, -0.020, 0.330)),
             (0.72, V(0.00, 0.030, 0.230)), (0.88, V(0.00, 0.060, 0.170)),
             (1.00, V(0.00, 0.062, 0.165))]
    pitch_k = [(0.00, DEG(9)), (0.16, DEG(26)), (0.34, DEG(44)), (0.52, DEG(58)),
               (0.72, DEG(76)), (0.88, DEG(86)), (1.00, DEG(87))]
    spine_k = [(0.00, DEG(4)), (0.20, DEG(16)), (0.45, DEG(22)), (0.70, DEG(10)),
               (0.90, DEG(-4)), (1.00, DEG(-2))]
    head_k = [(0.00, DEG(6)), (0.18, DEG(-16)), (0.42, DEG(10)), (0.66, DEG(28)),
              (0.86, DEG(6)), (1.00, DEG(10))]
    ankR_k = [(0.00, V(-0.10, 0.030, 0.092)), (0.26, V(-0.11, 0.150, 0.100)),
              (0.50, V(-0.12, 0.400, 0.150)), (0.72, V(-0.13, 0.640, 0.130)),
              (0.90, V(-0.13, 0.790, 0.090)), (1.00, V(-0.13, 0.800, 0.085))]
    ankL_k = [(0.00, V(0.12, -0.050, 0.092)), (0.28, V(0.13, 0.120, 0.110)),
              (0.52, V(0.15, 0.380, 0.200)), (0.74, V(0.16, 0.620, 0.160)),
              (0.92, V(0.16, 0.770, 0.092)), (1.00, V(0.16, 0.785, 0.086))]
    wrR_k = [(0.00, V(-0.26, -0.16, 1.02)), (0.20, V(-0.30, -0.36, 0.78)),
             (0.44, V(-0.34, -0.52, 0.42)), (0.66, V(-0.38, -0.58, 0.20)),
             (0.86, V(-0.42, -0.60, 0.08)), (1.00, V(-0.43, -0.60, 0.06))]
    wrL_k = [(0.00, V(0.27, -0.20, 1.06)), (0.20, V(0.32, -0.40, 0.82)),
             (0.44, V(0.36, -0.56, 0.46)), (0.66, V(0.40, -0.62, 0.22)),
             (0.86, V(0.44, -0.64, 0.09)), (1.00, V(0.45, -0.64, 0.07))]
    _death_body(rig, p, frames, hip_k, pitch_k, spine_k, head_k,
                ankR_k, ankL_k, wrR_k, wrL_k, roll_amp=DEG(-9), knee_out=0.7, land=0.80)
    L.finish_action(act, frames)
    return act


def build_death_side(rig, frames=48, side='L', name='death_left'):
    """Spun off its feet and dumped on one shoulder, then a heavy settle.

    s = +1 puts the body down on the character's left (+X)."""
    s = 1.0 if side == 'L' else -1.0
    act = L.new_action(rig, name)
    p = Poser(rig)
    hip_k = [(0.00, V(0.03, 0.012, 0.905)), (0.14, V(0.03 + 0.06 * s, 0.040, 0.860)),
             (0.32, V(0.16 * s, 0.120, 0.660)), (0.52, V(0.30 * s, 0.190, 0.380)),
             (0.70, V(0.40 * s, 0.230, 0.185)), (0.84, V(0.44 * s, 0.245, 0.136)),
             (1.00, V(0.45 * s, 0.248, 0.132))]
    pitch_k = [(0.00, DEG(9)), (0.16, DEG(-6)), (0.36, DEG(-22)), (0.56, DEG(-44)),
               (0.74, DEG(-58)), (0.88, DEG(-62)), (1.00, DEG(-63))]
    roll_k = [(0.00, 0.0), (0.16, DEG(-14) * s), (0.36, DEG(-38) * s),
              (0.58, DEG(-64) * s), (0.78, DEG(-82) * s), (1.00, DEG(-86) * s)]
    yaw_k = [(0.00, 0.0), (0.30, DEG(24) * s), (0.60, DEG(52) * s), (1.00, DEG(60) * s)]
    spine_k = [(0.00, DEG(4)), (0.20, DEG(-10)), (0.45, DEG(-4)), (0.72, DEG(8)),
               (1.00, DEG(6))]
    head_k = [(0.00, DEG(6)), (0.14, DEG(-24)), (0.40, DEG(-10)), (0.70, DEG(18)),
              (0.88, DEG(8)), (1.00, DEG(12))]
    ankR_k = [(0.00, V(-0.10, 0.030, 0.092)), (0.24, V(-0.12 + 0.10 * s, -0.020, 0.230)),
              (0.48, V(0.02 + 0.22 * s, -0.140, 0.320)), (0.70, V(0.14 + 0.28 * s, -0.240, 0.180)),
              (0.88, V(0.16 + 0.30 * s, -0.280, 0.086)), (1.00, V(0.16 + 0.30 * s, -0.290, 0.082))]
    ankL_k = [(0.00, V(0.12, -0.050, 0.092)), (0.26, V(0.10 + 0.12 * s, -0.080, 0.190)),
              (0.50, V(0.06 + 0.26 * s, -0.200, 0.300)), (0.72, V(0.10 + 0.32 * s, -0.320, 0.170)),
              (0.90, V(0.12 + 0.34 * s, -0.360, 0.090)), (1.00, V(0.12 + 0.34 * s, -0.370, 0.084))]
    wrR_k = [(0.00, V(-0.26, -0.16, 1.02)), (0.18, V(-0.30 + 0.10 * s, -0.04, 1.22)),
             (0.40, V(-0.20 + 0.26 * s, 0.10, 0.92)), (0.62, V(-0.06 + 0.40 * s, 0.22, 0.46)),
             (0.82, V(0.02 + 0.46 * s, 0.28, 0.16)), (1.00, V(0.02 + 0.48 * s, 0.26, 0.10))]
    wrL_k = [(0.00, V(0.27, -0.20, 1.06)), (0.18, V(0.30 + 0.08 * s, -0.06, 1.28)),
             (0.40, V(0.34 + 0.20 * s, 0.06, 1.00)), (0.62, V(0.40 + 0.32 * s, 0.18, 0.52)),
             (0.82, V(0.46 + 0.38 * s, 0.26, 0.18)), (1.00, V(0.46 + 0.40 * s, 0.24, 0.12))]
    _death_body(rig, p, frames, hip_k, pitch_k, spine_k, head_k,
                ankR_k, ankL_k, wrR_k, wrL_k, roll_k=roll_k, yaw_k=yaw_k,
                knee_out=0.6, land=0.78)
    L.finish_action(act, frames)
    return act


def _death_body(rig, p, frames, hip_k, pitch_k, spine_k, head_k, ankR_k, ankL_k,
                wrR_k, wrL_k, roll_amp=DEG(6), knee_out=0.5, roll_k=None, yaw_k=None,
                land=0.78):
    """Shared death driver.  After `land` the torso is down but the limbs keep moving
    for ~0.4 s - the settle tail that makes a fall read as weight instead of a plank."""
    for f in range(frames + 1):
        t = f / float(frames)
        after = max(0.0, t - land)
        # decaying impact ring, strongest right at contact
        settle = math.exp(-9.0 * after) * math.sin(after * 58.0) if t > land else 0.0
        # slower, larger limb flop riding on top of it
        flop = math.exp(-3.4 * after) * math.sin(after * 19.0) if t > land else 0.0
        p.begin()
        p.root((0, 0, 0))
        hp = kf(t, hip_k, 1.5)
        roll = (kf(t, roll_k, 1.5) if roll_k is not None
                else roll_amp * math.sin(t * 3.2))
        yaw = (kf(t, yaw_k, 1.5) if yaw_k is not None else DEG(8) * math.sin(t * 2.6))
        p.hips(hp + V(0, 0, 0.012 * settle), pitch=kf(t, pitch_k, 1.5) + DEG(4) * settle,
               roll=roll + DEG(5) * settle, yaw=yaw + DEG(3) * flop)
        sp = kf(t, spine_k, 1.5)
        hd = kf(t, head_k, 1.5)
        p.spine_chain(spine=(sp * 0.55 + DEG(5) * settle, DEG(6) * math.sin(t * 3),
                             DEG(5) * math.sin(t * 2.4) + DEG(4) * flop),
                      chest=(sp * 0.65 + DEG(7) * settle, DEG(8) * math.sin(t * 3),
                             DEG(6) * math.sin(t * 2.4) + DEG(5) * flop),
                      neck=(hd * 0.45 + DEG(9) * settle, DEG(6) * math.sin(t * 2),
                            DEG(6) + DEG(6) * flop),
                      head=(hd * 0.55 + DEG(16) * settle, DEG(10) * math.sin(t * 2),
                            DEG(8) + DEG(10) * flop))
        # the arms and legs carry on past the torso - dead weight, not braced
        fl = V(0.030 * flop, 0.040 * flop, 0.026 * abs(flop))
        p.arm_ik('R', kf(t, wrR_k, 1.5) - fl, pole=V(-1.0, 0.7, -0.2),
                 shoulder=(DEG(8) + DEG(10) * flop, 0, DEG(6)), hand=(DEG(-20), 0, 0))
        p.arm_ik('L', kf(t, wrL_k, 1.5) + fl, pole=V(1.0, 0.7, -0.2),
                 shoulder=(DEG(8) - DEG(10) * flop, 0, DEG(6)), hand=(DEG(-20), 0, 0))
        lf = V(0.012 * flop, 0.030 * flop, 0.020 * max(0.0, flop))
        p.leg('R', kf(t, ankR_k, 1.5) + lf, pitch=DEG(-6) + DEG(12) * flop,
              yaw=DEG(-10), knee_out=knee_out)
        p.leg('L', kf(t, ankL_k, 1.5) - lf, pitch=DEG(-4) - DEG(12) * flop,
              yaw=DEG(14), knee_out=knee_out + 0.2)
        rig.key(f)


# ---------------------------------------------------------------------------------------
# crawler: everything below the knee has been blown off (legs_X is hidden by the game)
# ---------------------------------------------------------------------------------------

# Authored to match src/ai/zombies.js CLIP_SPEED.crawl, which ships at 0.8.  The asset was
# previously built at 0.55 and the fix log asked the code stream to change its constant;
# that left a live ~45% foot-slide in the built game, so the asset moves instead.
# Ground speed the crawl cycle is authored for.  This MUST match src/ai/zombies.js
# CLIP_SPEED.crawl (0.55) or the hands and stumps slide: the code stream set 0.55, and the
# cycle was still authored at 0.80, which is a 45 % slide.  Verified by the build log line
# "clip crawl ... v=0.55 m/s".
CRAWL_V = 0.55
CRAWL_HIP_Z = 0.150
CRAWL_PITCH = DEG(84)


def _crawl_torso(p, u, rig, lift=1.0, roll_extra=0.0, drag=0.0):
    """Prone torso propped on the forearms, dragging.  `u` is the cycle phase."""
    pull = math.sin(math.tau * u)               # +1 while the left arm pulls
    heave = math.cos(math.tau * u)
    p.hips((0.012 * pull, 0.100 + 0.030 * drag + 0.018 * heave,
            CRAWL_HIP_Z + 0.022 * max(0.0, heave)),
           pitch=CRAWL_PITCH - DEG(5) * heave,
           roll=DEG(11) * pull + roll_extra,
           yaw=DEG(7) * pull)
    # the chest levers up off the ground; the head swings low and lags behind it
    arch = lift * (1.0 + 0.12 * heave)
    p.spine_chain(
        spine=(-DEG(20) * arch, DEG(6) * pull, DEG(5) * pull),
        chest=(-DEG(26) * arch, DEG(9) * pull, DEG(7) * pull),
        neck=(-DEG(26) * arch + DEG(8) * heave, DEG(7) * pull, DEG(8) * pull),
        head=(-DEG(14) * arch + DEG(16) * heave + DEG(4) * lnoise(u, 301),
              DEG(12) * pull, DEG(14) * pull + DEG(5) * lnoise(u, 302)))


def _crawl_legs(p, u, kick=1.0):
    """Dead legs trailing behind, scuffing alternately."""
    for side in ('L', 'R'):
        s = 1 if side == 'L' else -1
        ph = 0.0 if side == 'L' else 0.5
        sw = math.sin(math.tau * (u + ph))
        p.leg(side, V(s * (0.115 + 0.020 * max(0.0, sw)),
                      0.795 + 0.055 * kick * sw,
                      0.055 + 0.030 * kick * max(0.0, sw)),
              pitch=DEG(-10), yaw=DEG(8) * s, knee_out=0.55 + 0.2 * s)


def build_crawl(rig, frames=30):
    """Alternating forearm pulls, the torso dragging behind, head swinging low."""
    act = L.new_action(rig, 'crawl')
    p = Poser(rig)
    E = CRAWL_V * (frames / float(FPS))          # ground covered per cycle
    for f in range(frames + 1):
        u = (f % frames) / float(frames)
        p.begin()
        p.root((0, 0, 0))
        _crawl_torso(p, u, rig)
        _crawl_legs(p, u)
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            ph = 0.0 if side == 'L' else 0.5
            a = (u + ph) % 1.0
            if a < 0.55:                          # planted: the hand drags backward
                k = a / 0.55
                y = -0.66 + E * k
                z = 0.085 + 0.010 * math.sin(math.pi * k)
                x = s * (0.285 - 0.035 * k)
            else:                                 # reaching forward again
                k = ease_io((a - 0.55) / 0.45, 1.7)
                y = (-0.66 + E) + (-0.66 - (-0.66 + E)) * k
                z = 0.085 + 0.155 * math.sin(math.pi * (k ** 0.8))
                x = s * (0.250 + 0.035 * k)
            p.arm_ik(side, V(x, y, z), pole=V(s * 1.0, 0.35, 0.85),
                     shoulder=(DEG(14) if a < 0.55 else DEG(-6), 0, DEG(6)),
                     hand=(DEG(-26) - DEG(16) * (1.0 - min(1.0, a / 0.55)), 0, 0))
        rig.key(f)
    L.finish_action(act, frames)
    return act


def build_crawl_attack(rig, frames=21):
    """One-arm forward swipe from prone, contact at 45%."""
    act = L.new_action(rig, 'crawl_attack')
    p = Poser(rig)
    wr_R = [(0.00, V(-0.27, -0.24, 0.10)), (0.22, V(-0.34, 0.06, 0.30)),
            (0.34, V(-0.36, 0.12, 0.38)), (0.45, V(0.02, -0.66, 0.34)),
            (0.58, V(0.14, -0.62, 0.14)), (0.78, V(-0.18, -0.34, 0.09)),
            (1.00, V(-0.27, -0.24, 0.10))]
    wr_L = [(0.00, V(0.28, -0.60, 0.09)), (0.30, V(0.30, -0.58, 0.09)),
            (0.55, V(0.31, -0.56, 0.09)), (0.80, V(0.29, -0.58, 0.09)),
            (1.00, V(0.28, -0.60, 0.09))]
    lift_k = [(0.0, 1.0), (0.30, 1.45), (0.45, 1.20), (0.62, 0.85), (1.0, 1.0)]
    for f in range(frames + 1):
        t = f / float(frames)
        p.begin()
        p.root((0, 0, 0))
        _crawl_torso(p, 0.25 + 0.2 * math.sin(t * math.pi), rig,
                     lift=kf(t, lift_k, 1.7), roll_extra=DEG(-16) * smooth(seg(t, 0.2, 0.5)))
        _crawl_legs(p, 0.25, kick=0.4)
        p.arm_ik('R', kf(t, wr_R, 1.7), pole=V(-1.0, 0.35, 0.85),
                 shoulder=(DEG(16) * smooth(seg(t, 0.1, 0.34)), 0, DEG(8)),
                 hand=(DEG(-38), 0, 0))
        p.arm_ik('L', kf(t, wr_L, 1.5), pole=V(1.0, 0.35, 0.85),
                 shoulder=(DEG(6), 0, DEG(6)), hand=(DEG(-24), 0, 0))
        rig.key(f)
    L.finish_action(act, frames)
    return act


def build_to_crawl(rig, frames=18):
    """0.6 s collapse from standing to prone, for the moment the legs are blown off."""
    act = L.new_action(rig, 'to_crawl')
    p = Poser(rig)
    hipz_k = [(0.00, 0.905), (0.18, 0.760), (0.40, 0.470), (0.64, 0.235),
              (0.84, 0.150), (1.00, CRAWL_HIP_Z)]
    hipy_k = [(0.00, 0.012), (0.22, 0.030), (0.50, 0.062), (0.78, 0.090), (1.00, 0.100)]
    pitch_k = [(0.00, DEG(10)), (0.16, DEG(26)), (0.42, DEG(52)), (0.68, DEG(74)),
               (0.88, DEG(84)), (1.00, CRAWL_PITCH)]
    arch_k = [(0.00, 0.0), (0.30, -0.25), (0.60, 0.35), (0.84, 0.90), (1.00, 1.0)]
    wrR_k = [(0.00, V(-0.26, -0.20, 1.02)), (0.24, V(-0.30, -0.46, 0.72)),
             (0.48, V(-0.30, -0.62, 0.32)), (0.70, V(-0.29, -0.66, 0.10)),
             (1.00, V(-0.285, -0.66, 0.085))]
    wrL_k = [(0.00, V(0.27, -0.22, 1.06)), (0.26, V(0.31, -0.48, 0.76)),
             (0.52, V(0.31, -0.60, 0.34)), (0.74, V(0.29, -0.52, 0.10)),
             (1.00, V(0.265, -0.385, 0.085))]
    for f in range(frames + 1):
        t = f / float(frames)
        drop = kf(t, arch_k, 1.6)
        p.begin()
        p.root((0, 0, 0))
        p.hips((0.024 * (1 - t), kf(t, hipy_k, 1.5), kf(t, hipz_k, 1.6)),
               pitch=kf(t, pitch_k, 1.6), roll=DEG(-9) * math.sin(t * 5.0),
               yaw=DEG(8) * math.sin(t * 3.4))
        p.spine_chain(spine=(-DEG(20) * drop, DEG(5) * math.sin(t * 4), DEG(5) * drop),
                      chest=(-DEG(26) * drop, DEG(7) * math.sin(t * 4), DEG(7) * drop),
                      neck=(-DEG(26) * drop + DEG(14) * (1 - drop), DEG(6), DEG(8) * drop),
                      head=(-DEG(14) * drop + DEG(22) * (1 - drop),
                            DEG(10) * math.sin(t * 3), DEG(12) * drop))
        p.arm_ik('R', kf(t, wrR_k, 1.5), pole=V(-1.0, 0.5, 0.6),
                 shoulder=(DEG(12), 0, DEG(6)), hand=(DEG(-28), 0, 0))
        p.arm_ik('L', kf(t, wrL_k, 1.5), pole=V(1.0, 0.5, 0.6),
                 shoulder=(DEG(12), 0, DEG(6)), hand=(DEG(-28), 0, 0))
        # the stumps kick and then trail
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            tgt = V(s * 0.11, 0.030, 0.092).lerp(
                V(s * 0.115, 0.795, 0.055), smooth(seg(t, 0.20, 0.95)))
            tgt.z += 0.22 * math.sin(math.pi * seg(t, 0.15, 0.75)) * (1.0 if s > 0 else 0.7)
            p.leg(side, tgt, pitch=DEG(-10), yaw=DEG(8) * s, knee_out=0.55 + 0.2 * s)
        rig.key(f)
    L.finish_action(act, frames)
    return act


# ---------------------------------------------------------------------------------------

def build_all(rig):
    """Every contract clip. Returns [(name, frames, duration, note), ...]."""
    info = []
    for style in (walk_style(), run_style(), sprint_style()):
        act, v, reach = build_loco(rig, style)
        info.append((style.name, style.frames, style.frames / float(FPS),
                     'v=%.2f m/s hip_z=%.3f reach=%.3f/%.3f' % (v, style.hip_z, reach, LEG_LEN)))
    simple = [(build_idle, 'idle'), (build_tear, 'tear'), (build_hit, 'hit'),
              (build_climb, 'climb'), (build_rise, 'rise'),
              (build_crawl, 'crawl'), (build_crawl_attack, 'crawl_attack'),
              (build_to_crawl, 'to_crawl')]
    for fn, nm in simple:
        a = fn(rig)
        n = int(a.frame_end)
        note = 'v=%.2f m/s' % CRAWL_V if nm == 'crawl' else ''
        info.append((nm, n, n / float(FPS), note))
    # attacks: a left and a right diagonal swipe; `attack` stays as the right-hand one
    # so every existing caller keeps working.
    for lead, nm in (('R', 'attack'), ('R', 'attack_R'), ('L', 'attack_L')):
        a = build_attack(rig, lead=lead, name=nm)
        n = int(a.frame_end)
        info.append((nm, n, n / float(FPS), 'lead ' + lead))
    # deaths: four directional falls, plus death_1/death_2 kept as aliases of
    # death_back/death_front so nothing that already references them breaks.
    deaths = [(build_death_back, dict(name='death_back')),
              (build_death_back, dict(name='death_1')),
              (build_death_fwd, dict(name='death_front')),
              (build_death_fwd, dict(name='death_2')),
              (lambda r, **kw: build_death_side(r, side='L', **kw), dict(name='death_left')),
              (lambda r, **kw: build_death_side(r, side='R', **kw), dict(name='death_right'))]
    for fn, kw in deaths:
        a = fn(rig, **kw)
        n = int(a.frame_end)
        info.append((kw['name'], n, n / float(FPS), ''))
    return info
