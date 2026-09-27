"""Doom Town — vehicles, mannequins and the heavier street props."""
import math, random, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Euler  # noqa: E402
import layout as L  # noqa: E402


import lib_vehicles as V  # noqa: E402


def local(x, y, yaw, dx, dy):
    c, s = math.cos(yaw), math.sin(yaw)
    return (x + dx * c - dy * s, y + dx * s + dy * c)


def sedan(scn, x, y, yaw, paint='paint_red', seed=0, burnt=False, bg=False,
          roll=0.0, pitch=0.0, dz=0.0, flat=(1, 0, 0, 1)):
    V.place(scn, V.build_sedan, x, y, yaw, roll, pitch, dz, bg=bg,
            paint=paint, burnt=burnt, seed=seed, flat=flat)
    if not bg:
        h = 1.55 if abs(roll) < 0.8 else 1.35
        scn.col_obj('COL_CAR', (x, y, h / 2), (5.25, 2.15, h), (0, 0, yaw))


def pickup(scn, x, y, yaw, paint='paint_teal', seed=0, bg=False, burnt=False):
    V.place(scn, V.build_pickup, x, y, yaw, bg=bg, paint=paint, seed=seed, burnt=burnt)
    if not bg:
        scn.col_obj('COL_CAR', (x, y, 0.88), (5.45, 2.15, 1.76), (0, 0, yaw))


def school_bus(scn, x, y, yaw, seed=0):
    V.place(scn, V.build_bus, x, y, yaw, seed=seed)
    scn.col_obj('COL_BUS', (x, y, 1.6), (9.6, 2.7, 3.2), (0, 0, yaw))


# --------------------------------------------------------------------------- mannequins
import lib_mannequin as MQ  # noqa: E402


def mannequins(scn):
    MQ.place(scn, -6.2, -8.6, math.radians(40), clothes='dress', seed=1,
             arms=((0.30, 0.14, 0.55), (-0.10, 0.20, 0.35)))
    MQ.place(scn, -5.4, -8.2, math.radians(-120), clothes='suit', seed=2,
             arms=((-0.25, 0.26, 1.10), (0.35, 0.12, 0.30)))
    MQ.place(scn, 7.2, 4.6, math.radians(200), burnt=True, missing=('arm_l',), seed=3,
             arms=((0.0, 0.2, 0.4), (0.9, 0.35, 1.5)))
    # toppled in the road, one arm gone
    MQ.place(scn, 3.4, -17.6, math.radians(15), roll=math.radians(96), dz=0.22,
             clothes='suit', missing=('arm_r',), seed=4, collide=False,
             arms=((1.4, 0.4, 0.9), (0, 0, 0)))
    MQ.place(scn, -10.3, 6.6, math.radians(-60), seed=5, missing=('head',),
             arms=((0.15, 0.18, 0.25), (0.15, 0.18, 0.25)))
    # burnt figure slumped against the sandbags by the bunker
    MQ.place(scn, 1.6, 10.2, math.radians(150), pitch=math.radians(-58), dz=0.52,
             burnt=True, seed=6, collide=False, missing=('leg_r',),
             arms=((1.9, 0.45, 0.7), (1.6, 0.3, 1.2)))
    MQ.place(scn, -9.1, -3.2, math.radians(70), clothes='dress', burnt=True, seed=7,
             missing=('arm_r', 'head'), arms=((0.7, 0.3, 0.9), (0, 0, 0)))


def build(scn):
    school_bus(scn, -2.3, -12.6, math.radians(114))
    # the burnt-out wreck by the bunker is flipped onto its roof
    sedan(scn, 5.4, 8.2, math.radians(-22), 'paint_red', seed=1, burnt=True,
          roll=math.radians(168), pitch=math.radians(-6), dz=1.52, flat=(1, 1, 1, 1))
    sedan(scn, -8.4, 5.6, math.radians(98), 'paint_teal', seed=2, flat=(0, 1, 0, 0))
    pickup(scn, 8.6, -15.4, math.radians(-68), 'paint_cream', seed=3)
    sedan(scn, 8.8, -1.2, math.radians(86), 'paint_cream', seed=4, burnt=True,
          flat=(1, 1, 0, 1))
    mannequins(scn)
