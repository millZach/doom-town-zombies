"""Material + hand testbed.  Renders a material ball chart and a bare gloved hand/arm."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_weapons import *                                  # noqa

MODE = 'all'
for a in sys.argv:
    if a.startswith('--mode='):
        MODE = a.split('=', 1)[1]

reset_scene()
prebake(force=('--force' in sys.argv))

if MODE in ('all', 'mats'):
    names = ['metal_blued', 'metal_parker', 'metal_steel', 'metal_brass',
             'polymer_black', 'polymer_rubber', 'wood_walnut', 'wood_birch',
             'sleeve_olive', 'glove_leather', 'metal_red_enamel', 'polymer_cream']
    for i, n in enumerate(names):
        col, row = i % 4, i // 4
        x, z = -0.225 + col * 0.15, 0.125 - row * 0.125
        b = rbox('m_' + n, (0.082, 0.082, 0.082), (x - 0.030, 0.62, z), rot=(0, 0, D2R(20)))
        finish(b, M(n), bev=0.004, segs=4, texel=0.10)
        sp = sphere('m_s_' + n, 0.036, (x + 0.036, 0.615, z + 0.004), segs=40)
        finish(sp, M(n), bev=0.0, texel=0.10)
    render_eye(os.path.join(WRENDERS, 'test_materials.png'), samples=64, res=(1100, 620))
    for ob in list(bpy.context.scene.objects):
        if ob.name.startswith('m_'):
            bpy.data.objects.remove(ob, do_unlink=True)

if MODE in ('all', 'hand'):
    arm = build_arm('arm_R', 'R', wrist=(0.052, 0.255, -0.115), fingers=(0.13, 0.95, 0.28),
                    back=(0.96, -0.06, 0.26), elbow=(0.20, 0.00, -0.30),
                    curl=(0.86, 0.90, 0.92, 0.93), thumb_curl=0.45)
    print('arm tris', tri_count())
    render_eye(os.path.join(WRENDERS, 'test_hand_eye.png'), samples=48, res=(1280, 720))
    render_detail(os.path.join(WRENDERS, 'test_hand_back.png'), target=(0.055, 0.29, -0.09),
                  distance=0.26, yaw=-118, pitch=22, samples=56, lens=45)
    render_detail(os.path.join(WRENDERS, 'test_hand_side.png'), target=(0.055, 0.29, -0.09),
                  distance=0.26, yaw=8, pitch=8, samples=56, lens=45)
print('DONE')
