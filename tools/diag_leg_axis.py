# -*- coding: utf-8 -*-
"""量腿**骨链**与**几何**的横向位置随高度的变化 —— 用来判断腿是不是一条直边。

    blender -b --factory-startup --python tools/diag_leg_axis.py -- --blend <b>

判据是**相邻两段的斜率**：腿看上去应该是一条从胯到脚笔直外张的斜边（倒 V
的一条边）。只要斜率在膝盖处跳变，实机上就是"腿在 V 中间折了一下"。

    斜率 = (下一根骨的 X − 这根骨的 X) / (下一根骨的 Z − 这根骨的 Z)

斜率沿链**连续**才是直边；某一段突然变大，折角就出现在那个关节。
"""

import os
import sys

import bpy

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

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm is None:
    raise SystemExit('没有骨架')
mw = arm.matrix_world
chain = ['Bip01 L Thigh', 'Bip01 L Calf', 'Bip01 L Foot', 'Bip01 L Toe0']
pts = []
for b in chain:
    if b in arm.data.bones:
        h = mw @ arm.data.bones[b].head_local
        pts.append((b, float(h[0]), float(h[2])))

print('=== 骨链（左侧）===')
print('%6s %9s %9s' % ('骨', 'X (cm)', 'Z (cm)'))
for b, x, z in pts:
    print('%6s %9.2f %9.2f' % (b.split()[-1], x, z))
print('\n=== 段斜率 dX/dZ ===')
for (b0, x0, z0), (b1, x1, z1) in zip(pts, pts[1:]):
    dz = z0 - z1
    if abs(dz) < 1e-6:
        continue
    print('%-10s -> %-10s  %+.4f' % (b0.split()[-1], b1.split()[-1],
                                     (x1 - x0) / dz))

LEG = {'Bip01 L Thigh', 'Bip01 R Thigh', 'Bip01 L Calf', 'Bip01 R Calf',
       'Bip01 L Foot', 'Bip01 R Foot'}
buckets = {}
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    gname = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        w = {gname[ge.group]: ge.weight for ge in v.groups if ge.weight > 1e-6}
        if not w:
            continue
        if max(w, key=w.get) in LEG and v.co.x > 1.0:
            b = int(v.co.z // 5) * 5
            buckets.setdefault(b, []).append(float(v.co.x))
print('\n=== 几何重心（左腿，按 5 cm 分层）===')
prev = None
for b in sorted(buckets):
    m = sum(buckets[b]) / len(buckets[b])
    sl = ''
    if prev is not None and b > prev[0]:
        sl = '段斜率 %+.4f' % ((m - prev[1]) / (b - prev[0]))
    print('  z=%3d  n=%-5d 重心 X=%6.2f   %s' % (b, len(buckets[b]), m, sl))
    prev = (b, m)
