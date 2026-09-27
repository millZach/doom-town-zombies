"""Real signage lettering.

Replaces the old 3x5 bitmap `text_boxes()` (environment.md #6): letters were one extruded box per
pixel, which (a) read as Lego at any distance, and (b) got corrupted by the random `skip` wear pass
(A -> H, R -> K: "FHLLOUT SHELTEK").

Here a Blender FONT object is converted to a mesh, squashed to the plate's width and stamped into
the caller's geometry bank as ~2 mm of proud paint. Wear is applied to the *material*, never by
deleting parts of a glyph, so a sign can never spell the wrong word.
"""
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

# stencil = the 1950s civil-defence / military look; black = bold grotesque for vehicle signage
FONT_FILES = {
    'stencil': ('C:/Windows/Fonts/STENCIL.TTF',),
    'black':   ('C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
    'bold':    ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/ariblk.ttf'),
    'cond':    ('C:/Windows/Fonts/AGENCYB.TTF', 'C:/Windows/Fonts/arialbd.ttf'),
}
_FONTS = {}


def font(kind='stencil'):
    """Load (once) one of the named faces; falls back to Blender's built-in font."""
    if kind in _FONTS:
        return _FONTS[kind]
    f = None
    for path in FONT_FILES.get(kind, ()):
        if os.path.exists(path):
            try:
                f = bpy.data.fonts.load(path, check_existing=True)
                break
            except Exception:
                f = None
    if f is None:                                   # Bfont: still real letterforms
        f = bpy.data.fonts.get('Bfont Regular') or bpy.data.fonts.get('Bfont')
        if f is None:
            try:
                f = bpy.data.fonts.load('<builtin>')
            except Exception:
                f = None
    _FONTS[kind] = f
    return f


def _text_mesh(text, kind, tracking, weight, res):
    cu = bpy.data.curves.new('_signtxt', 'FONT')
    cu.body = text
    fo = font(kind)
    if fo is not None:
        cu.font = fo
    cu.size = 1.0
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.space_character = 1.0 + tracking
    cu.offset = weight                       # fattens the strokes a touch so thin faces still read
    cu.resolution_u = res
    cu.extrude = 0.0
    ob = bpy.data.objects.new('_signtxt', cu)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    return me


def sign_text(target, mat, text, origin, run, up, face, h=0.26, width=None, depth=0.0022,
              kind='stencil', tracking=0.06, weight=0.012, res=None, bg=False, squash=None):
    """Stamp `text` onto a flat sign face.

    origin  centre of the text block;  run/up/face  orthogonal axes of the plate
    h       cap height in metres;  width  optional total width the text is squashed into
    depth   how far the paint stands proud of the plate (keep it tiny: this is paint, not tiles)
    Returns the (width, height) actually used.
    """
    # curve resolution by how big the lettering actually is on screen: a 5 cm crate stencil at
    # res 3 costs as many triangles as the hero sign over the blast door and reads the same
    if res is None:
        res = 1 if h < 0.10 else (2 if h < 0.24 else 3)
    me = _text_mesh(text, kind, tracking, weight, res)
    if not len(me.polygons):
        bpy.data.meshes.remove(me)
        return (0.0, 0.0)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    w0, h0 = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    # cap height for an all-caps string == the mesh height; normalise on that so `h` is exact
    sy = h / max(h0, 1e-6)
    sx = sy if width is None else min(sy, (width / max(w0, 1e-6)))
    if width is not None and squash is not None:
        sx = max(sx, sy * squash)                     # allow a little condensing, never a lot
    bmesh.ops.translate(bm, vec=(-cx, -cy, 0.0), verts=bm.verts)
    bmesh.ops.scale(bm, vec=(sx, sy, 1.0), verts=bm.verts)
    # give the paint a hair of thickness so it catches the light and never z-fights
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    top = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, depth), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    r, u, f = Vector(run).normalized(), Vector(up).normalized(), Vector(face).normalized()
    o = Vector(origin)
    m = Matrix(((r.x, u.x, f.x, o.x), (r.y, u.y, f.y, o.y), (r.z, u.z, f.z, o.z), (0, 0, 0, 1)))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)

    me2 = bpy.data.meshes.new('_signstamp')
    bm.to_mesh(me2)
    bm.free()
    dst = target.bm(mat, bg)
    dst.faces.ensure_lookup_table()
    n0 = len(dst.faces)
    dst.from_mesh(me2)
    dst.faces.ensure_lookup_table()
    for fc in dst.faces[n0:]:
        fc.select = True                 # letters stay faceted, never get auto-smoothed
    bpy.data.meshes.remove(me2)
    return (w0 * sx, h)


def sign_plate(target, mat_plate, mat_text, text, centre, run, up, face, h=0.26,
               pad=(0.16, 0.13), plate_t=0.02, kind='stencil', bg=False, width=None):
    """A stencilled board: plate + lettering, sized to the text."""
    w, _ = sign_text(target, mat_text, text, tuple(Vector(centre) + Vector(face).normalized() * (plate_t * 0.5 + 0.001)),
                     run, up, face, h=h, width=width, kind=kind, bg=bg)
    r, u, f = Vector(run).normalized(), Vector(up).normalized(), Vector(face).normalized()
    hw, hh, ht = (w + pad[0] * 2) / 2, (h + pad[1] * 2) / 2, plate_t / 2
    c = Vector(centre)
    m = Matrix(((r.x, u.x, f.x, c.x), (r.y, u.y, f.y, c.y), (r.z, u.z, f.z, c.z), (0, 0, 0, 1)))
    bm = target.bm(mat_plate, bg)
    verts = bmesh.ops.create_cube(bm, size=1.0)['verts']
    bmesh.ops.transform(bm, matrix=m @ Matrix.Diagonal(Vector((hw * 2, hh * 2, ht * 2)).to_4d()),
                        verts=verts)
    return w + pad[0] * 2
