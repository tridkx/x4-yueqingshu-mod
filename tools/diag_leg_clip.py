# -*- coding: utf-8 -*-
"""量"腿穿出裙子"：按高度分层，比较腿的外缘与裙子的内缘。

    blender -b --factory-startup --python tools/diag_leg_clip.py -- --blend <b>

对每一层高度输出：

    leg_out   腿几何在这一层的最大 |x|（外缘）
    skirt_in  裙子几何在这一层的最大 |x|（**最内侧**的那圈，也就是它的内缘）
    clip      leg_out − skirt_in > 0 就是穿模，单位 cm

"裙子的内缘"取的是该层所有裙子顶点里**最靠内**的那一圈的半径 —— 裙子不是
一个圆筒，褶皱会让半径在一个区间内摆动，穿模发生在腿顶到最里面那圈的时候。

腿的判据用**权重**（`Bip01 L/R Thigh` / `Calf` / `Foot` / `Toe0` 主导），
不用材质：皮肤和靴子是两个材质，但都在同一条腿上。
"""

import os
import sys

import bpy

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
if not BLEND:
    raise SystemExit('need --blend')
bpy.ops.wm.open_mainfile(filepath=BLEND)

LEG_BONES = {'Bip01 L Thigh', 'Bip01 R Thigh', 'Bip01 L Calf', 'Bip01 R Calf',
             'Bip01 L Foot', 'Bip01 R Foot', 'Bip01 L Toe0', 'Bip01 R Toe0'}
SKIRT_PARTS = {'cloth1', 'cloth2', 'cloth3'}

leg, skirt = [], []
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    part = ob.get('x4cc_part') or ''
    gname = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        w = {gname[ge.group]: ge.weight for ge in v.groups if ge.weight > 1e-6}
        if not w:
            continue
        top = max(w, key=w.get)
        # **必须按侧分开比**：第一版把所有裙子顶点混在一起取 min()，
        # 拿到的是对侧裙子的外缘（负值），于是"穿模"算出 44-66 cm 这种
        # 荒谬数字。左右两条腿各自只和对侧的裙片比。
        side = 'L' if v.co.x > 0 else 'R'
        if part in SKIRT_PARTS:
            skirt.append((abs(v.co.x), v.co.z, side))
        elif top in LEG_BONES and abs(v.co.x) > 1.0:
            leg.append((abs(v.co.x), v.co.z, top, side))

print('腿顶点 %d，裙子顶点 %d' % (len(leg), len(skirt)))
if not leg or not skirt:
    raise SystemExit('没找到腿或裙子')

zmax = max(z for _x, z, _s in skirt)
zmin = min(z for _x, z, _b, _s in leg)
print('裙子下沿 z=%.1f  腿顶 z=%.1f\n' % (zmax, max(z for _x, z, _b, _s in leg)))

print('%6s %8s %9s %8s  %-6s %s'
      % ('z 层', 'leg_out', 'skirt_in', 'clip', '侧', '腿主导骨'))
step = 4.0
z = zmin
worst = (0.0, 0.0, '')
while z < zmax:
    for side in ('L', 'R'):
        lg = [(x, b) for x, zz, b, s in leg
              if s == side and z <= zz < z + step]
        sk = [x for x, zz, s in skirt if s == side and z <= zz < z + step]
        if not lg or not sk:
            continue
        lo = max(x for x, _b in lg)
        # 穿模的判据是**腿的外缘 vs 裙子侧壁的外缘**：腿从裙子外面露出来，
        # 意味着腿比裙子还靠外。之前拿 `min(sk)` 当"裙子内缘"是错的 ——
        # 那取到的是垂在两腿之间的前襟（x≈0），算出来的"穿模"是几十厘米。
        hi = max(sk)
        clip = lo - hi
        bone = ''
        if clip > 0:
            bs = [b for x, b in lg if x > hi]
            bone = max(set(bs), key=bs.count) if bs else ''
            if clip > worst[1]:
                worst = (z, clip, side)
        print('%6.0f %8.2f %9.2f %8.2f  %-6s %s'
              % (z, lo, hi, clip, side, bone if clip > 0 else ''))
    z += step

print('\n最大穿模 %.2f cm（z=%.0f 层，%s 侧）' % (worst[1], worst[0], worst[2]))
print('腿最外缘 %.2f cm' % max(x for x, _z, _b, _s in leg))