"""Dev harness: build the raw zombie geometry and render silhouette checks (no materials)."""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

import bpy
from mathutils import Vector
from common import reset_scene, preview_render, pbr_material, RENDERS_DIR
import lib_char as L
import zombie_mesh as ZM

t0 = time.time()
reset_scene()
body = ZM.build_base_body()
head = ZM.build_head_mesh()
teeth = ZM.build_teeth()
eyes = ZM.build_eyes()
for o in (body, head, teeth, eyes):
    L.shade_smooth_ob(o)
print('BODY tris', L.triangle_count(body), 'HEAD tris', L.triangle_count(head),
      'TEETH', L.triangle_count(teeth))

clay = pbr_material('clay', (0.52, 0.5, 0.48), 0.55)
for o in (body, head):
    o.data.materials.append(clay)
teeth.data.materials.append(pbr_material('tooth', (0.75, 0.72, 0.6), 0.35))
eyes.data.materials.append(pbr_material('eye', (0.9, 0.5, 0.1), 0.3, emission=(1, 0.6, 0.15), emission_strength=4))

out = os.path.join(RENDERS_DIR, 'characters')
os.makedirs(out, exist_ok=True)
preview_render(os.path.join(out, 'dev_body_front.png'), target=(0, 0, 0.92), distance=4.2,
               yaw_deg=0, pitch_deg=2, lens=42, samples=36)
preview_render(os.path.join(out, 'dev_body_34.png'), target=(0, 0, 0.92), distance=4.2,
               yaw_deg=40, pitch_deg=6, lens=42, samples=36)
preview_render(os.path.join(out, 'dev_body_side.png'), target=(0, 0, 0.92), distance=4.2,
               yaw_deg=90, pitch_deg=2, lens=42, samples=36)
preview_render(os.path.join(out, 'dev_body_back.png'), target=(0, 0, 0.92), distance=4.2,
               yaw_deg=180, pitch_deg=2, lens=42, samples=36)
preview_render(os.path.join(out, 'dev_head_front.png'), target=(0, -0.01, 1.70), distance=0.75,
               yaw_deg=0, pitch_deg=2, lens=45, samples=36, ground=False)
preview_render(os.path.join(out, 'dev_head_34.png'), target=(0, -0.01, 1.70), distance=0.75,
               yaw_deg=40, pitch_deg=8, lens=45, samples=36, ground=False)
preview_render(os.path.join(out, 'dev_head_side.png'), target=(0, 0.0, 1.70), distance=0.75,
               yaw_deg=90, pitch_deg=2, lens=45, samples=36, ground=False)
preview_render(os.path.join(out, 'dev_hand.png'), target=(0.31, -0.07, 0.83), distance=0.45,
               yaw_deg=35, pitch_deg=12, lens=45, samples=36, ground=False)
print('TOTAL', round(time.time() - t0, 1), 's')
