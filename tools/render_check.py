# -*- coding: utf-8 -*-
"""出图：把一个 stage1 的 .blend 渲染成正/侧/头三张，用来**看图**判断对错。

    blender -b --factory-startup --python tools/render_check.py -- \
        --blend work/yue_a_stage1.blend --out work/preview/a

它刻意把**背面剔除打开**：绕序对不对在别处只能靠数值推断，在这里是一眼
就能看出来的事 —— 反射没反转绕序时，正面看到的是一片空洞，能直接看穿到
内壳。普通渲染（双面）会把这个错误完全掩盖掉。

第二步给每张图**单独再渲一次带法线着色的版本**（材质替换成
`dot(法线, 视线)`），面片感的真凶是法线而不是几何，这一张能直接分辨
"几何塌了"和"法线是平的"。
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def arg(name, default=None):
    argv = sys.argv
    if '--' in argv:
        rest = argv[argv.index('--') + 1:]
        if name in rest:
            i = rest.index(name)
            if i + 1 < len(rest):
                return rest[i + 1]
    return default


BLEND = arg('--blend')
OUT = arg('--out')
RES = int(arg('--res', '900'))
ONLY = arg('--only')
#: 逗号分隔的 stem 列表，从渲染里隐藏 —— 分材质出图是定位"这块黑的是谁"
#: 最快的手段：把可疑件逐个摘掉，看症状跟着谁走。
HIDE = [s for s in (arg('--hide') or '').split(',') if s]
#: 关掉背面剔除，用来区分"绕序错"和"贴图/光照错"。
NO_CULL = arg('--no-cull') is not None
GAIN = float(arg('--gain', '3.0'))
#: `--zoom z0,z1` 渲染指定高度区间（cm，X4 的 Z 就是身高方向）。查"腿穿出
#: 裙子"这类问题时全身图看不出名堂，必须贴到那一段去看。
ZOOM = arg('--zoom')
#: `--elev` 抬高相机并俯视若干度。查"内八/外八"必须俯视 —— 正面图里
#: 脚尖的朝向只体现为左右各偏几个像素，看不出来。
ELEV = float(arg('--elev', '0'))

if not BLEND or not OUT:
    raise SystemExit('need --blend and --out')
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene

hidden = []
for ob in list(bpy.data.objects):
    if ob.type != 'MESH':
        continue
    if (ob.get('x4cc_part') or '') in HIDE:
        hidden.append('%s(%s)' % (ob.name, ob.get('x4cc_part')))
        bpy.data.objects.remove(ob, do_unlink=True)
if HIDE:
    print('hidden: %s' % (', '.join(hidden) or 'nothing matched'))

# ---------------------------------------------------------------- bounds
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        lo = Vector((min(lo[i], w[i]) for i in range(3)))
        hi = Vector((max(hi[i], w[i]) for i in range(3)))
size = hi - lo
print('bounds: lo=%s hi=%s size=%s' % (tuple(round(v, 1) for v in lo),
                                       tuple(round(v, 1) for v in hi),
                                       tuple(round(v, 1) for v in size)))

# ---------------------------------------------------------------- lights
for spec in [((0, 300, 260), 4.0), ((-260, 160, 120), 2.4),
             ((240, -200, 160), 2.0)]:
    lamp = bpy.data.lights.new('L', type='AREA')
    lamp.energy = spec[1] * 24000 * GAIN
    lamp.size = 400
    ob = bpy.data.objects.new('L', lamp)
    ob.location = spec[0]
    d = Vector((0, 0, size.z * 0.55)) - Vector(spec[0])
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(ob)

world = bpy.data.worlds.new('W') if not scene.world else scene.world
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.05, 0.055, 0.07, 1.0)
    bg.inputs[1].default_value = 0.6 * GAIN

cam_data = bpy.data.cameras.new('C')
cam_data.type = 'ORTHO'
cam = bpy.data.objects.new('C', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.engine = 'BLENDER_EEVEE'
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 32
except Exception:
    pass

# 背面剔除：绕序错误的唯一"一眼可辨"判据
for mat in bpy.data.materials:
    mat.use_backface_culling = not NO_CULL


def shoot(name, loc, target, ortho, res_x, res_y):
    if ELEV:
        # 把相机沿"从目标出发的视线方向"抬起来：水平距离乘 cos、高度加
        # h*sin。第一版只加了高度、没缩水平距离，等于把相机挪到了目标
        # **上方**而不是**斜上方**，对焦就偏了（渲染出来只有裙子没有脚）。
        import math as _m
        dx, dy = loc[0] - target[0], loc[1] - target[1]
        hh = _m.hypot(dx, dy) or 1.0
        e = _m.radians(ELEV)
        loc = (target[0] + dx * _m.cos(e), target[1] + dy * _m.cos(e),
               target[2] + hh * _m.sin(e))
    cam.location = loc
    cam_data.ortho_scale = ortho
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('  ->', scene.render.filepath)


mid = (lo + hi) / 2.0
h = size.z
R = max(size.x, size.y)
views = [
    # 角色面朝 +Y，所以正面相机站在 +Y 看向 -Y
    ('front', (mid.x, mid.y + 600, mid.z), (mid.x, mid.y, mid.z),
     R * 1.25 + 20, RES, int(RES * 1.5)),
    ('side', (mid.x + 600, mid.y, mid.z), (mid.x, mid.y, mid.z),
     R * 1.25 + 20, RES, int(RES * 1.5)),
    ('back', (mid.x, mid.y - 600, mid.z), (mid.x, mid.y, mid.z),
     R * 1.25 + 20, RES, int(RES * 1.5)),
]
# 头部：取头顶往下一段
head_lo = hi.z - h * 0.24
views.append(('head', (mid.x, mid.y + 600, head_lo + h * 0.10),
              (mid.x, mid.y, head_lo + h * 0.10), h * 0.30 + 10,
              RES, RES))

if ZOOM:
    z0, z1 = [float(v) for v in ZOOM.split(',')]
    tgt_z = (z0 + z1) / 2.0
    span = max(z1 - z0, 1.0)
    views = [
        ('zoom_front', (mid.x, mid.y + 600, tgt_z), (mid.x, mid.y, tgt_z),
         span * 1.15, RES, int(RES * 1.6)),
        ('zoom_back', (mid.x, mid.y - 600, tgt_z), (mid.x, mid.y, tgt_z),
         span * 1.15, RES, int(RES * 1.6)),
        ('zoom_side', (mid.x + 600, mid.y, tgt_z), (mid.x, mid.y, tgt_z),
         span * 1.15, RES, int(RES * 1.6)),
    ]

for name, loc, tgt, ortho, rx, ry in views:
    if ONLY and name != ONLY:
        continue
    shoot(name, loc, tgt, ortho, rx, ry)

print('DONE %s' % OUT)