"""Build public/models/zombie.glb: three rigged, animated zombie variants.

    blender.exe -b --factory-startup --python tools/blender/characters/build_zombie.py -- [opts]

Options after `--`:
    --fast          skip texture baking (flat colours) - for animation iteration
    --force-bake    rebuild the cached baked textures
    --sheets[=a,b]  render animation contact sheets to renders/characters/ (all, or listed)
    --stills[=a,b]  render beauty stills (views: front,34,back,head,head34,game,crawler)
    --variants=A,B  build only these variants (a PARTIAL build never overwrites
                    public/models/zombie.glb - it writes a scratch glb instead)

Exports per variant:  body_X, legs_X (knee-down, hideable for crawlers), head_X, eyes_X.
"""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

import bpy
from mathutils import Vector, Matrix
from common import reset_scene, preview_render, MODELS_DIR, RENDERS_DIR, TEX_CACHE, setup_gpu
import lib_char as L
import zombie_mesh as ZM
import zombie_cloth as ZC
import zombie_mat as MAT
import zombie_rig as ZR
import zombie_anim as ZA

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in ARGS
FORCE_BAKE = '--force-bake' in ARGS
SHEETS = any(a == '--sheets' or a.startswith('--sheets=') for a in ARGS)
STILLS = any(a == '--stills' or a.startswith('--stills=') for a in ARGS)
VARIANTS = 'ABC'
SHEET_ONLY = None                # --sheets=rise,crawl  -> only those contact sheets
STILL_ONLY = None                # --stills=crawler,front
for a in ARGS:
    if a.startswith('--variants='):
        VARIANTS = a.split('=', 1)[1].replace(',', '')
    elif a.startswith('--sheets='):
        SHEET_ONLY = set(a.split('=', 1)[1].split(','))
    elif a.startswith('--stills='):
        STILL_ONLY = set(a.split('=', 1)[1].split(','))

BAKE_VERSION = 'v9'
KNEE_CUT = 0.470                 # crawler split height (just above the knee joint)
# Triangle budget.  docs/ASSET_CONTRACT.md says 25k/variant, but the integrator raised the
# ceiling for the characters to ~35k (they are the one thing the player looks at from 2 m);
# this is the hard backstop that guarantees nothing ships above 37k.
BUDGET = 35500
OUT = os.path.join(MODELS_DIR, 'zombie.glb')
# NEVER let a partial build overwrite the shipped asset: only --variants=ABC (the default)
# writes public/models/zombie.glb, anything else goes to a scratch file.
PARTIAL = sorted(VARIANTS) != ['A', 'B', 'C']
if PARTIAL:
    OUT = os.path.join(TEX_CACHE, '_scratch_zombie_%s.glb' % VARIANTS)
RDIR = os.path.join(RENDERS_DIR, 'characters')
os.makedirs(RDIR, exist_ok=True)
T0 = time.time()


def log(*a):
    print('[zombie %6.1fs]' % (time.time() - T0), *a)


# =======================================================================================
# 1. base meshes
# =======================================================================================
scn = reset_scene()
scn.render.fps = 30
scn.render.fps_base = 1.0
log('building body')
base_body = ZM.build_base_body()
log('body tris', L.triangle_count(base_body))
bb = [Vector(c) for c in base_body.bound_box]
log('body local bbox  x[%.3f %.3f] y[%.3f %.3f] z[%.3f %.3f]' % (
    min(p.x for p in bb), max(p.x for p in bb), min(p.y for p in bb),
    max(p.y for p in bb), min(p.z for p in bb), max(p.z for p in bb)))
base_head = ZM.build_head_mesh()
log('head tris', L.triangle_count(base_head))
for o in (base_body, base_head):
    L.clear_colors(o)

# =======================================================================================
# 2. UV + bake
# =======================================================================================
L.smart_uv(base_body, 68, 0.006)
L.smart_uv(base_head, 68, 0.008)

if FAST:
    skin_mat = MAT.simple('zombie_skin', (0.33, 0.31, 0.26), 0.75)
    head_mat = MAT.simple('zombie_head', (0.34, 0.31, 0.26), 0.75)
else:
    log('baking body skin')
    base_head.hide_render = True
    tex_b = L.bake_object_material(
        base_body, lambda m, o: MAT.skin_material(m, o, blood_head=False),
        'zskin_body_' + BAKE_VERSION, size=2048, samples=6, force=FORCE_BAKE)
    base_head.hide_render = False
    log('baking head skin')
    base_body.hide_render = True
    tex_h = L.bake_object_material(
        base_head, lambda m, o: MAT.skin_material(m, o, blood_head=True),
        'zskin_head_' + BAKE_VERSION, size=1024, samples=6, force=FORCE_BAKE)
    base_body.hide_render = False
    skin_mat = L.baked_material('zombie_skin', tex_b, roughness=0.8, normal_strength=1.0)
    head_mat = L.baked_material('zombie_head', tex_h, roughness=0.8, normal_strength=1.0)

# Gore: dark clotted meat.  The previous value was 6x more red than green, which under
# the game's warm key light turned every gore face (including the whole mouth interior)
# into saturated cherry - half of the 'clown mouth' the review filed.
gore_mat = MAT.simple('zombie_gore', (0.046, 0.015, 0.012), 0.34)
# teeth: dark, dry bone - the old (0.215,0.192,0.125) read as a cartoon grin
teeth_mat = MAT.simple('zombie_teeth', (0.094, 0.084, 0.058), 0.44)
gum_mat = MAT.simple('zombie_gum', (0.042, 0.017, 0.015), 0.52)
# modest ember, not a headlamp: the game drives the intensity (review #2)
eye_mat = MAT.simple('eye_glow', (0.24, 0.075, 0.010), 0.35, emission=(1.0, 0.34, 0.05),
                     strength=1.6)

base_body.data.materials.append(skin_mat)
base_body.data.materials.append(gore_mat)
GORE_SLOT = 1
# the whole neck stump (_neck_stump spans z 1.582-1.620) is gore, not skin: when the
# head pops this is the only thing the player sees
for i, p in enumerate(base_body.data.polygons):
    if p.center.z > 1.5775 and abs(p.center.x) < 0.080:
        p.material_index = GORE_SLOT

base_head.data.materials.append(head_mat)
base_head.data.materials.append(gore_mat)
for i in ZM.mouth_faces(base_head):
    base_head.data.polygons[i].material_index = 1

L.shade_smooth_ob(base_body, 55)
L.shade_smooth_ob(base_head, 55)

# =======================================================================================
# 3. armature + skinning of the base skin
# =======================================================================================
log('rigging')
rig = ZR.build(L)
arm = rig.ob

L.activate(base_body)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')


def head_bind(ob):
    """Rigid to `head`, blended into `neck` at the base so the join never tears."""
    gh = ob.vertex_groups.get('head') or ob.vertex_groups.new(name='head')
    gn = ob.vertex_groups.get('neck') or ob.vertex_groups.new(name='neck')
    for v in ob.data.vertices:
        t = max(0.0, min(1.0, (v.co.z - 1.555) / 0.058))
        gh.add([v.index], t, 'REPLACE')
        gn.add([v.index], 1.0 - t, 'REPLACE')
    L.activate(ob)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_NAME')
    return ob


def torso_weights(ob, only=None):
    """Bind a hanging panel (an apron, a coat tail) to hips/spine/chest purely by height.

    Nearest-surface weight transfer is wrong for anything that stands off the body: the
    outer edge of the apron was picking up the *hand* as its closest source vertex, so it
    swung out into a plank whenever the arm moved.
    """
    def c(x):
        return max(0.0, min(1.0, x))
    gh = ob.vertex_groups.get('hips') or ob.vertex_groups.new(name='hips')
    gs = ob.vertex_groups.get('spine') or ob.vertex_groups.new(name='spine')
    gc = ob.vertex_groups.get('chest') or ob.vertex_groups.new(name='chest')
    verts = ([ob.data.vertices[i] for i in only] if only is not None else ob.data.vertices)
    for v in verts:
        z = v.co.z
        wc = c((z - 1.230) / 0.150)
        ws = c((z - 1.010) / 0.150) * (1.0 - wc)
        wh = max(0.0, 1.0 - wc - ws)
        gh.add([v.index], wh, 'REPLACE')
        gs.add([v.index], ws, 'REPLACE')
        gc.add([v.index], wc, 'REPLACE')
    return ob


ARM_SEGS = [(ZR.J['shoulder_L'], ZR.J['elbow_L']), (ZR.J['elbow_L'], ZR.J['wrist_L']),
            (ZR.J['wrist_L'], ZR.J['hand_L']),
            (ZR.J['shoulder_R'], ZR.J['elbow_R']), (ZR.J['elbow_R'], ZR.J['wrist_R']),
            (ZR.J['wrist_R'], ZR.J['hand_R'])]
ARM_GROUPS = {'shoulder_L', 'shoulder_R', 'upperarm_L', 'upperarm_R',
              'forearm_L', 'forearm_R', 'hand_L', 'hand_R'}


def _seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


DISTAL_GROUPS = {'forearm_L', 'forearm_R', 'hand_L', 'hand_R'}


def clean_arm_weights(ob, maxdist=0.165, distal_all=False):
    """Drop arm/hand weights from garment vertices that are nowhere near an arm.

    Nearest-surface transfer binds by proximity to the *skin*, and a flared skirt or a
    hanging panel passes within a few centimetres of the hand.  Variant B's dress was
    picking up `hand_R` at full weight down at knee height, so the whole skirt swung out
    into a plank every time the arm moved.  Stripped vertices fall back to a hips/spine
    height blend.
    """
    gidx = {g.index: g.name for g in ob.vertex_groups}
    byname = {g.name: g for g in ob.vertex_groups}
    orphans = []
    fixed = 0
    for v in ob.data.vertices:
        far = min(_seg_dist(v.co, a, b) for a, b in ARM_SEGS) > maxdist
        # `distal_all`: a garment panel is NEVER driven by a forearm or a hand, however
        # close it happens to sit in the rest pose.  The rest hand hangs beside the hip,
        # so the dress waist and the apron band were picking up hand_R at full weight
        # inside the 90 mm radius and swinging out into a flat sail across the front of
        # the dress whenever the arm moved.  Proximal bones (shoulder/upperarm) still win
        # near the shoulder, so a sleeve head and a yoke still follow the deltoid.
        if not far and not distal_all:
            continue
        removed = False
        for g in list(v.groups):
            nm = gidx.get(g.group)
            if nm in ARM_GROUPS and g.weight > 1e-5 and (far or nm in DISTAL_GROUPS):
                byname[nm].remove([v.index])
                removed = True
        if not removed:
            continue
        fixed += 1
        if not any(g.weight > 1e-5 for g in ob.data.vertices[v.index].groups
                   if gidx.get(g.group) not in ARM_GROUPS):
            orphans.append(v.index)
    if orphans:
        torso_weights(ob, only=orphans)
    return fixed


def orphan_guard(ob, maxdist=0.100):
    """Height-weight any vertex that has no weights at all, before `fix_weights` runs.

    `L.fix_weights` resolves an unweighted vertex from its NEAREST weighted neighbour, and
    in the rest pose the hand hangs right beside the hip: a waistband or skirt vertex that
    came out of the join unweighted therefore adopted `hand_R`, and was dragged into a
    flat sail across the front of the dress whenever the arm moved (variant B, visible in
    every shipped render as a "blade" from the waist to the chest).  Anything that is not
    within `maxdist` of an arm gets a hips/spine/chest height blend instead, which is what
    a garment vertex should have had in the first place.
    """
    orph = [v.index for v in ob.data.vertices
            if not any(g.weight > 1e-5 for g in v.groups)]
    if not orph:
        return 0, 0
    far = [i for i in orph
           if min(_seg_dist(ob.data.vertices[i].co, a, b) for a, b in ARM_SEGS) > maxdist]
    if far:
        torso_weights(ob, only=far)
    return len(orph), len(far)


def transfer_weights(src, dst):
    L.activate(dst)
    m = dst.modifiers.new('DT', 'DATA_TRANSFER')
    m.object = src
    m.use_vert_data = True
    m.data_types_verts = {'VGROUP_WEIGHTS'}
    m.vert_mapping = 'POLYINTERP_NEAREST'
    m.layers_vgroup_select_src = 'ALL'
    m.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.datalayout_transfer(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name)
    return dst


# =======================================================================================
# 4. variants
# =======================================================================================
# base albedos roughly doubled (review #10): the old values were darker than the tarmac,
# so the zombies vanished into the fog.
CLOTH = {
    'A': (ZC.variant_A, dict(
        top=('cloth_A_shirt', dict(base=(0.430, 0.408, 0.352), dirt=(0.090, 0.072, 0.048),
                                   blood=0.9, uv_scale=132)),
        bottom=('cloth_A_slacks', dict(base=(0.090, 0.090, 0.102), dirt=(0.034, 0.029, 0.023),
                                       blood=0.5, uv_scale=98)),
        acc=('cloth_A_leather', None))),
    'B': (ZC.variant_B, dict(
        # a faded blue print, so the cream blossoms actually read as flowers against it
        top=('cloth_B_dress', dict(base=(0.146, 0.168, 0.202), dirt=(0.062, 0.049, 0.034),
                                   pattern='floral', blood=0.7, uv_scale=118)),
        acc=('cloth_B_acc', None),
        panel=('cloth_B_apron', dict(base=(0.300, 0.288, 0.254), dirt=(0.074, 0.055, 0.036),
                                     blood=1.0, uv_scale=142)))),
    'C': (ZC.variant_C, dict(
        top=('cloth_C_fatigue', dict(base=(0.118, 0.120, 0.074), dirt=(0.046, 0.039, 0.024),
                                     pattern='twill', blood=0.65, uv_scale=86)),
        bottom=('cloth_C_fatigue2', dict(base=(0.108, 0.110, 0.068), dirt=(0.042, 0.035, 0.022),
                                         pattern='twill', blood=0.35, uv_scale=86)),
        acc=('cloth_C_webbing', None))),
}
HEAD_EXTRA = {'A': (ZC.hair_A, 'hair_A', 'hair'), 'B': (ZC.hair_B, 'hair_B', 'hair'),
              'C': (ZC.helmet_C, 'helmet_C', 'metal')}

exported = [arm]
stats = {}


def bake_cloth(ob, name, kw):
    L.smart_uv(ob, 72, 0.01)
    if FAST:
        return MAT.simple(name, kw['base'], 0.82)
    tex = L.bake_object_material(ob, lambda m, o: MAT.cloth_material(m, o, **kw),
                                 name + '_' + BAKE_VERSION, size=1024, samples=6,
                                 force=FORCE_BAKE)
    return L.baked_material(name, tex, roughness=0.85)


for V in VARIANTS:
    log('variant', V)
    build_fn, matspec = CLOTH[V]
    wounds = ZM.wounds_for(V)
    top, bottom, acc, panel = build_fn()
    groups = []
    for parts, key in ((top, 'top'), (bottom, 'bottom'), (acc, 'acc'), (panel, 'panel')):
        if not parts:
            continue
        # Weight each piece BEFORE joining: only a sleeve should ever be arm-driven.
        # Nearest-surface transfer on the joined garment bound the flared skirt of the
        # dress to `hand_R`, and the whole thing swung out into a plank when the arm
        # moved.  Doing it per part lets the rule depend on what the part is.
        if key != 'panel':
            nfix = 0
            for pt in parts:
                transfer_weights(base_body, pt)
                if 'sleeve' not in pt.name:
                    nfix += clean_arm_weights(pt, 0.090, distal_all=True)
            if nfix:
                log('  %s: stripped stray arm weights from %d verts' % (key, nfix))
        # diagnostic: a garment part that keeps a hand weight swings out into a plank
        for pt in parts:
            gi = {g.index: g.name for g in pt.vertex_groups}
            bad = sum(1 for v in pt.data.vertices for g in v.groups
                      if gi.get(g.group) in ('hand_L', 'hand_R', 'forearm_L', 'forearm_R')
                      and g.weight > 0.25)
            if bad and 'sleeve' not in pt.name:
                log('  WARNING %s still arm-weighted on %d verts' % (pt.name, bad))
        ob = L.join(parts, '_cloth_%s_%s' % (V, key))
        if key == 'panel':
            torso_weights(ob)
        if key in ('top', 'bottom'):
            n = ZC.tear_open(ob, wounds, seed=hash(V + key) & 0xffff)
            if n:
                log('  %s torn open: %d faces removed' % (key, n))
        if key in ('top', 'bottom'):
            ZC.folds(ob, key, seed=hash(V + key) & 0xffff)
        ZC.rumple(ob, seed=hash(V + key) & 0xffff)
        L.clear_colors(ob)
        L.shade_smooth_ob(ob, 62)
        groups.append((ob, key))

    body = L.duplicate(base_body, 'body_' + V)
    ZM.variant_body(body, V)
    for w in wounds:
        if w.get('ribs'):
            ZM.exposed_ribs(body, w)
    for i in ZM.wound_faces(body, V):
        body.data.polygons[i].material_index = GORE_SLOT

    covers = [g[0] for g in groups if g[1] in ('top', 'bottom')]
    # Protect the skin under every garment tear.  A plain sphere of w['r']*1.55 was
    # SMALLER than the hole the cloth builder cut, so the player looked through the tear
    # into the black inside of the garment - the "black rectangle" the verifier saw.  The
    # protected volume is now the same swept tube the hole is cut with, 1.9x wider.
    keep = [(Vector(w['c']), w['r'] * 1.55) for w in wounds]
    tubes = []
    for w in wounds:
        if not w.get('hole'):
            continue
        tubes.append((Vector(w['c']), Vector(ZM.hole_axis(w)).normalized(),
                      w['hole'] * 1.90))

    def _protect(c):
        if any((c - p).length < r for p, r in keep):
            return True
        for wc, ax, r in tubes:
            rel = c - wc
            al = rel.dot(ax)
            if abs(al) < 0.16 and (rel - ax * al).length < r:
                return True
        return False

    nrem = L.remove_covered(body, covers, 0.012, protect=_protect)
    log('  hidden faces removed:', nrem)

    for ob, key in groups:
        name, kw = matspec[key]
        if kw is None:
            L.smart_uv(ob, 72, 0.01)
            m = (MAT.simple(name, (0.048, 0.038, 0.030), 0.55) if FAST else
                 L.baked_material(name, L.bake_object_material(
                     ob, lambda mm, o: MAT.leather_material(
                         mm, o, base=(0.048, 0.038, 0.030)), name + '_' + BAKE_VERSION,
                     size=512, samples=6, force=FORCE_BAKE), roughness=0.6))
        else:
            m = bake_cloth(ob, name, kw)
        ob.data.materials.clear()
        ob.data.materials.append(m)
    body = L.join([body] + [g[0] for g in groups], 'body_' + V)
    log('  orphan verts %d (height-weighted %d)' % orphan_guard(body))
    L.fix_weights(body, arm)
    # crawler split: knee-down becomes its own hideable object, both halves capped
    body, legs = L.split_at_z(body, KNEE_CUT, 'legs_' + V, mat_index=GORE_SLOT,
                              jag=0.013, seed=hash(V) & 0xff)
    # Belt and braces on the gore material: `_cap_open_edges` sets it on the faces it
    # creates, but the cut also passes through the trouser shell, and anything the fill
    # missed used to ship as plain grey cloth - the "smooth closed trouser cap" the
    # verifier saw on the crawler.  Everything within 12 mm of the cut plane is gore.
    # Only the CAP faces, which face up or down.  Painting every face within 12 mm of the
    # cut plane also painted the outside wall of the trouser leg, so an intact zombie wore
    # a bright red ring round each knee in every render.
    for ob_ in (body, legs):
        n_ = 0
        for poly in ob_.data.polygons:
            if abs(poly.center.z - KNEE_CUT) < 0.013 and abs(poly.normal.z) > 0.45:
                poly.material_index = GORE_SLOT
                n_ += 1
        log('  %s: %d faces forced to gore at the cut' % (ob_.name, n_))
    # splintered femur ends sticking out of the stumps (dry-bone material)
    bone = ZM.stump_bones(KNEE_CUT)
    L.clear_colors(bone)
    L.shade_smooth_ob(bone, 30)
    bone.data.materials.append(teeth_mat)
    body = L.join([body, bone], 'body_' + V)
    L.fix_weights(body, arm)
    L.fix_weights(legs, arm)

    head = L.duplicate(base_head, 'head_' + V)
    ZM.variant_face(head, V)
    for i in ZM.face_wound_faces(head, V):
        head.data.polygons[i].material_index = 1
    fn, hname, hkind = HEAD_EXTRA[V]
    extra = fn()
    L.clear_colors(extra)
    L.shade_smooth_ob(extra, 40)
    L.smart_uv(extra, 72, 0.01)
    if FAST or hkind == 'metal':
        hm = MAT.simple(hname, (0.058, 0.062, 0.050) if hkind == 'metal' else (0.030, 0.024, 0.019),
                        0.55, metallic=0.85 if hkind == 'metal' else 0.0)
    else:
        hm = L.baked_material(hname, L.bake_object_material(
            extra, lambda mm, o: MAT.hair_material(mm, o), hname + '_' + BAKE_VERSION,
            size=512, samples=6, force=FORCE_BAKE), roughness=0.62)
    extra.data.materials.clear()
    extra.data.materials.append(hm)
    teeth = ZM.build_teeth(V)
    L.clear_colors(teeth)
    teeth.data.materials.append(teeth_mat)
    L.shade_smooth_ob(teeth, 24)
    gums, tongue = ZM.build_gums(V)
    gums = L.join([gums, tongue], '_gums_' + V)
    L.clear_colors(gums)
    gums.data.materials.append(gum_mat)
    L.shade_smooth_ob(gums, 50)
    head = L.join([head, teeth, gums, extra], 'head_' + V)
    head_bind(head)

    eyes = ZM.build_eyes('eyes_' + V)
    L.clear_colors(eyes)
    eyes.data.materials.append(eye_mat)
    L.shade_smooth_ob(eyes, 60)
    head_bind(eyes)

    # --- contract triangle budget -------------------------------------------------
    # docs/ASSET_CONTRACT.md: "character <= 25k tris per variant".  Everything above is
    # sized to land under it; this is the backstop that guarantees it rather than hoping.
    tri = [L.triangle_count(o) for o in (body, legs, head, eyes)]
    if sum(tri) > BUDGET:
        k = float(BUDGET - tri[3]) / float(sum(tri) - tri[3])
        log('  over budget (%d): trimming by %.3f' % (sum(tri), k))
        for o in (body, legs, head):
            L.decimate(o, k)
        L.fix_weights(body, arm)
        L.fix_weights(legs, arm)
        L.fix_weights(head, arm)

    stats[V] = (L.triangle_count(body), L.triangle_count(legs), L.triangle_count(head),
                L.triangle_count(eyes))
    log('  tris body %d legs %d head %d eyes %d  total %d  (budget %d)'
        % (stats[V] + (sum(stats[V]), BUDGET)))
    exported += [body, legs, head, eyes]

bpy.data.objects.remove(base_body, do_unlink=True)
bpy.data.objects.remove(base_head, do_unlink=True)

# =======================================================================================
# 5. animation
# =======================================================================================
log('animating')
clips = ZA.build_all(rig)
for c in clips:
    log('  clip %-12s %3d frames  %.2fs  %s' % c)

# =======================================================================================
# 6. export
# =======================================================================================
bpy.context.scene.frame_set(0)
bpy.ops.object.select_all(action='DESELECT')
for ob in exported:
    ob.select_set(True)
bpy.context.view_layer.objects.active = arm
L.export_character(OUT)
log('EXPORTED', OUT, os.path.getsize(OUT) // 1024, 'KB')

# =======================================================================================
# 7. check renders
# =======================================================================================
PARTS = ('body_', 'legs_', 'head_', 'eyes_')
# check renders are capped (shared laptop, thermal budget): 896x504 / 32 samples
RES = (896, 504)
SAMP = 32

if STILLS or SHEETS:
    scn = setup_gpu(SAMP)
    scn.view_settings.view_transform = 'AgX'


def show_only(V, crawler=False):
    for ob in bpy.data.objects:
        if ob.name.startswith(PARTS):
            ob.hide_render = not ob.name.endswith('_' + V)
            if crawler and ob.name.startswith('legs_'):
                ob.hide_render = True


def want(tag):
    """--stills=head,crawler renders only those views (cheap iteration on one problem)."""
    return STILL_ONLY is None or tag in STILL_ONLY


if STILLS:
    for V in VARIANTS:
        show_only(V)
        act = bpy.data.actions['idle']
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
        bpy.context.scene.frame_set(18)
        if want('front'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_front.png' % V), target=(0, 0, 0.92),
                      distance=3.9, yaw_deg=10, pitch_deg=2, lens=42, samples=SAMP, res=RES)
        if want('34'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_34.png' % V), target=(0, 0, 0.92),
                      distance=3.9, yaw_deg=46, pitch_deg=6, lens=42, samples=SAMP, res=RES)
        if want('back'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_back.png' % V), target=(0, 0, 0.92),
                      distance=3.9, yaw_deg=160, pitch_deg=6, lens=42, samples=SAMP, res=RES)
        hb = arm.pose.bones['head']
        hp = (arm.matrix_world @ hb.matrix).translation + Vector((0, -0.01, 0.10))
        if want('head'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_head.png' % V), target=tuple(hp),
                      distance=0.70, yaw_deg=20, pitch_deg=4, lens=45, samples=SAMP, res=RES,
                      ground=False, key=60.0, rim=40.0, sky=0.25)
        if want('head34'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_head34.png' % V), target=tuple(hp),
                      distance=0.62, yaw_deg=52, pitch_deg=-4, lens=45, samples=SAMP, res=RES,
                      ground=False, key=60.0, rim=40.0, sky=0.25)
        # what the player actually sees: 1.9 m away, eye height
        bpy.context.scene.frame_set(40)
        if want('game'):
          L.dusk_render(os.path.join(RDIR, 'zombie_%s_game.png' % V), target=(0, 0, 1.35),
                      distance=1.9, yaw_deg=22, pitch_deg=3, lens=30, samples=SAMP, res=RES)
    # crawler check: legs hidden, gore stump showing
    show_only(VARIANTS[0], crawler=True)
    if 'crawl' in bpy.data.actions:
        act = bpy.data.actions['crawl']
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
        bpy.context.scene.frame_set(10)
    if want('crawler'):
        L.dusk_render(os.path.join(RDIR, 'zombie_crawler.png'), target=(0, 0, 0.42),
                      distance=2.6, yaw_deg=48, pitch_deg=14, lens=42, samples=SAMP, res=RES)
        # tight on the severed knee.  Shot on the REST pose, not the crawl: in the crawl
        # the body is prone and a world-space camera aimed at knee height frames the head.
        act0 = bpy.data.actions['idle']
        arm.animation_data.action = act0
        try:
            arm.animation_data.action_slot = act0.slots[0]
        except Exception:
            pass
        bpy.context.scene.frame_set(0)
        # from BELOW: the cut cap is a horizontal disc facing down, so a camera above the
        # knee only ever sees the outside of the trouser leg
        L.dusk_render(os.path.join(RDIR, 'zombie_stump.png'), target=(0.10, 0.0, 0.455),
                      distance=0.80, yaw_deg=28, pitch_deg=-38, lens=45, samples=SAMP,
                      res=RES, ground=False, key=180.0, rim=90.0, sky=0.35)
    show_only(VARIANTS[0])

if SHEETS:
    tmp = os.path.join(RDIR, '_tmp')
    os.makedirs(tmp, exist_ok=True)
    show_only('A')
    for name, nframes, dur, note in clips:
        if SHEET_ONLY is not None and name not in SHEET_ONLY:
            continue
        act = bpy.data.actions[name]
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
        show_only('A', crawler=name.startswith('crawl') or name == 'to_crawl')
        cols = 6
        paths = []
        # the rise is judged on its first half second, so sample it front-loaded
        fracs = ([0.0, 0.05, 0.13, 0.24, 0.45, 0.72] if name == 'rise' else
                 [i / float(cols) for i in range(cols)])
        for i in range(cols):
            f = int(round(fracs[i] * nframes))
            bpy.context.scene.frame_set(f)
            pth = os.path.join(tmp, '%s_%02d.png' % (name, i))
            # the rise is judged on hands breaking the soil, so frame the ground, close
            tgt = (0, -0.2 if name == 'climb' else 0,
                   0.45 if name.startswith(('crawl', 'to_crawl')) else 0.90)
            dist = 4.4
            if name == 'rise':
                tgt, dist = (0, -0.1, 0.35), 2.5
            preview_render(pth, target=tgt, distance=dist, yaw_deg=58, pitch_deg=6,
                           lens=40, samples=24, res=(320, 460))
            paths.append(pth)
        L.contact_sheet(paths, os.path.join(RDIR, 'anim_%s.png' % name), cols, (320, 460))
log('done')
