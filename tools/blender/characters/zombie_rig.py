"""Zombie skeleton: exact contract bone names, rest pose, and the joint table the mesh
builder also reads so geometry and bones always agree.

Character faces -Y, +X is the character's LEFT, Z up, origin between the feet.
"""
import math
from mathutils import Vector

FWD = Vector((0, -1, 0))      # facing
UPV = Vector((0, 0, 1))

# ---- joint positions (armature space, metres) -----------------------------------------
J = {
    'root':       Vector((0.000, 0.000, 0.000)),
    'hips':       Vector((0.000, 0.010, 1.010)),   # pelvis centre
    'spine':      Vector((0.000, -0.004, 1.140)),
    'chest':      Vector((0.000, -0.004, 1.300)),
    'neck':       Vector((0.000, 0.014, 1.462)),
    'head':       Vector((0.000, 0.016, 1.572)),
    'head_top':   Vector((0.000, -0.004, 1.800)),

    # shoulders sit ~12 mm wider than before so the silhouette reads as a person, not a
    # coat hanger; the arm is the same length, just hung further out (review #7)
    'clav_L':     Vector((0.026, 0.008, 1.458)),
    'shoulder_L': Vector((0.202, 0.004, 1.440)),
    'elbow_L':    Vector((0.266, -0.017, 1.148)),
    'wrist_L':    Vector((0.310, -0.055, 0.885)),
    'hand_L':     Vector((0.326, -0.068, 0.788)),

    'hip_L':      Vector((0.095, 0.006, 0.928)),
    'knee_L':     Vector((0.100, -0.008, 0.487)),
    'ankle_L':    Vector((0.098, 0.010, 0.092)),
    'toe_L':      Vector((0.098, -0.128, 0.034)),
    'toetip_L':   Vector((0.098, -0.208, 0.026)),
}
for k in list(J):
    if k.endswith('_L'):
        v = J[k]
        J[k[:-2] + '_R'] = Vector((-v.x, v.y, v.z))

# roll reference vectors: the bone's local +Z is aligned to this
_FWD = (0, -1, 0)
_UP = (0, 0, 1)

SKELETON = {
    # name:        (parent,       head,          tail,             roll ref)
    'root':        (None,         J['root'],     J['root'] + Vector((0, 0, 0.14)), _FWD),
    'hips':        ('root',       J['hips'],     J['spine'],       _FWD),
    'spine':       ('hips',       J['spine'],    J['chest'],       _FWD),
    'chest':       ('spine',      J['chest'],    J['neck'],        _FWD),
    'neck':        ('chest',      J['neck'],     J['head'],        _FWD),
    'head':        ('neck',       J['head'],     J['head_top'],    _FWD),

    'shoulder_L':  ('chest',      J['clav_L'],     J['shoulder_L'], _UP),
    'upperarm_L':  ('shoulder_L', J['shoulder_L'], J['elbow_L'],    _FWD),
    'forearm_L':   ('upperarm_L', J['elbow_L'],    J['wrist_L'],    _FWD),
    'hand_L':      ('forearm_L',  J['wrist_L'],    J['hand_L'],     _FWD),
    'shoulder_R':  ('chest',      J['clav_R'],     J['shoulder_R'], _UP),
    'upperarm_R':  ('shoulder_R', J['shoulder_R'], J['elbow_R'],    _FWD),
    'forearm_R':   ('upperarm_R', J['elbow_R'],    J['wrist_R'],    _FWD),
    'hand_R':      ('forearm_R',  J['wrist_R'],    J['hand_R'],     _FWD),

    'thigh_L':     ('hips',       J['hip_L'],   J['knee_L'],   _FWD),
    'shin_L':      ('thigh_L',    J['knee_L'],  J['ankle_L'],  _FWD),
    'foot_L':      ('shin_L',     J['ankle_L'], J['toe_L'],    _UP),
    'toe_L':       ('foot_L',     J['toe_L'],   J['toetip_L'], _UP),
    'thigh_R':     ('hips',       J['hip_R'],   J['knee_R'],   _FWD),
    'shin_R':      ('thigh_R',    J['knee_R'],  J['ankle_R'],  _FWD),
    'foot_R':      ('shin_R',     J['ankle_R'], J['toe_R'],    _UP),
    'toe_R':       ('foot_R',     J['toe_R'],   J['toetip_R'], _UP),
}

CONTRACT_BONES = [
    'root', 'hips', 'spine', 'chest', 'neck', 'head',
    'shoulder_L', 'upperarm_L', 'forearm_L', 'hand_L',
    'shoulder_R', 'upperarm_R', 'forearm_R', 'hand_R',
    'thigh_L', 'shin_L', 'foot_L', 'toe_L',
    'thigh_R', 'shin_R', 'foot_R', 'toe_R',
]

THIGH_LEN = (J['knee_L'] - J['hip_L']).length
SHIN_LEN = (J['ankle_L'] - J['knee_L']).length
LEG_LEN = THIGH_LEN + SHIN_LEN
UPPERARM_LEN = (J['elbow_L'] - J['shoulder_L']).length
FOREARM_LEN = (J['wrist_L'] - J['elbow_L']).length
ARM_LEN = UPPERARM_LEN + FOREARM_LEN

# ankle -> ball-of-foot offset in foot rest space (used by the footstep solver)
BALL_OFFSET = Vector((0.0, -0.105, -0.092))   # ankle to sole-under-the-ball
HEEL_OFFSET = Vector((0.0, 0.055, -0.092))
ANKLE_HEIGHT = 0.092


def build(lib, name='Armature'):
    rig = lib.Rig(name, SKELETON)
    return rig
