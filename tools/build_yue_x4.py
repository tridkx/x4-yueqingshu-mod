# -*- coding: utf-8 -*-
"""阶段 1：把一个月清疏套装重定向到 X4 的 91 骨 Biped，切成 head/body 两半。

    blender -b --factory-startup --python tools/build_yue_x4.py -- --outfit a

在 Blender 里做的事：导入 vanilla 的 Argon 女性宿主（拿到逐字节的骨架）、
对源网格做**逐骨绑定姿态转移**、抬脚到地面、按材质分组、减面、平滑权重，
存成 `work/yue_<key>_stage1.blend`。阶段 2 再把结果填进宿主的网格槽位。

三个只在**这个**来源上才成立的前提，都实测过：

1. **绕序必须反转。** 坐标映射 `(x,y,z) -> (x,z,y)` 交换了两个轴，`det = -1`，
   是一次反射。反射会把每个三角形的朝向翻过来，而 **glb 自带的逐顶点法线
   证明源绕序是对的**（逐面 `dot(面法线, 顶点法线)` 均值 +0.99，正的占 100%）。
   所以问题不在源，在映射 —— 反射一定伴随一次绕序反转。
   不反转的实机症状：整件衣服、整张脸从正面看不见（引擎剔掉正面），能透过
   它们看到内壳，光照像揉皱的破布。

2. **UV 的 v 要翻一次。** glTF 与 DX 一样把 v=0 放在图像顶端，Blender 放在
   底端；导出器自己还会做一次 `1 - v`。所以 Blender 里必须存 `1 - v_src`，
   两边的翻转才会抵消。不翻的实机症状：整张贴图上下颠倒 —— 而离线预览
   用的是源图形的 UV，**预览会一直是"对"的**。

3. **同位骨的轴向要沿主链继续找。** `Bip001-L-ForeTwist` 与 `Bip001-L-Forearm`
   位置完全相同（Max Biped 的扭转骨就长这样），两者映射到同一个 X4 骨。
   若轴向退回父方向，整条上臂会转 90 度。
"""

import importlib
import os
import sys

import addon_utils
import bpy
import numpy as np
import pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths                                                      # noqa: E402
import glb as glblib                                              # noqa: E402
import yue_src                                                    # noqa: E402
from yue_to_x4 import (YueAdapter, build_bone_map, check_core,     # noqa: E402
                       report_map, yue_to_blender)
sys.path.insert(0, os.path.join(paths.WORKSPACE, 'x4-character-retarget',
                                'tools'))
from retarget_core import BindPoseRetarget                        # noqa: E402


def arg(name, default=None):
    argv = sys.argv
    if '--' in argv:
        rest = argv[argv.index('--') + 1:]
        if name in rest:
            i = rest.index(name)
            if i + 1 < len(rest):
                return rest[i + 1]
    return default


OUTFIT_KEY = arg('--outfit', 'a')
OUTFIT = yue_src.outfit(OUTFIT_KEY)

if paths.ADDON_DIR:
    sys.path.insert(0, paths.ADDON_DIR)


# --------------------------------------------------------------------------
# the vanilla skeleton
# --------------------------------------------------------------------------
def load_x4_armature():
    """导入宿主，取走它的骨架，丢掉它的网格。

    这是"换网格、留骨架"那一步：骨架必须与 vanilla **逐字节相同**，
    因为动画、注视、挂点全挂在共享 component 上。
    """
    importlib.import_module('X4CharacterConverter')
    addon_utils.enable('X4CharacterConverter', default_set=True)
    bpy.context.preferences.addons[
        'X4CharacterConverter'].preferences.data_root = paths.X4_ROOT + os.sep
    from X4CharacterConverter import addon as A

    A.import_actor(bpy.context, pathlib.Path(paths.HOST_HEAD))
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    for ob in list(bpy.data.objects):
        if ob.type == 'MESH':
            bpy.data.objects.remove(ob, do_unlink=True)

    mw = arm.matrix_world
    bones = {}
    for b in arm.data.bones:
        bones[b.name] = {
            'head': tuple(mw @ b.head_local),
            'tail': tuple(mw @ b.tail_local),
            'parent': b.parent.name if b.parent else None,
        }
    return arm, bones


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def decimate(ob, ratio, floor=yue_src.DECIMATE_FLOOR):
    """就地坍缩减面；返回 (顶点数, 无权重数, 是否失效)。"""
    if ratio >= 0.999 or len(ob.data.polygons) < 4:
        return len(ob.data.vertices), 0, False
    before = len(ob.data.vertices)
    mod = ob.modifiers.new(name='Decimate', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    new_me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = new_me
    bpy.data.meshes.remove(old)
    if len(ob.data.vertices) < floor:
        return before, 0, True
    unweighted = sum(1 for v in ob.data.vertices
                     if not any(ge.weight > 1e-6 for ge in v.groups))
    return len(ob.data.vertices), unweighted, False


#: 权重平滑的轮数。跨骨混合时，两根骨的拟合旋转不同，接缝处会起折痕。
#: 轮数越多，每个顶点的邻域越宽，过渡就摊在更多三角形上而不是挤在一条带里。
WEIGHT_SMOOTH_ROUNDS = 4


def smooth_vertex_weights(ob, rounds=WEIGHT_SMOOTH_ROUNDS, alpha=0.5):
    me = ob.data
    n = len(me.vertices)
    adj = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    gname = {g.index: g.name for g in ob.vertex_groups}
    W = [{gname[ge.group]: ge.weight for ge in v.groups
          if ge.weight > 1e-6 and ge.group in gname} for v in me.vertices]
    for _ in range(rounds):
        NW = []
        for i, w in enumerate(W):
            acc = {k: v * (1.0 - alpha) for k, v in w.items()}
            nb = adj[i]
            if nb:
                share = alpha / len(nb)
                for j in nb:
                    for k, val in W[j].items():
                        acc[k] = acc.get(k, 0.0) + val * share
            tot = sum(acc.values())
            NW.append({k: v / tot for k, v in acc.items()} if tot > 1e-9 else w)
        W = NW
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    groups = {}
    for i, w in enumerate(W):
        for k, val in w.items():
            g = groups.get(k)
            if g is None:
                g = ob.vertex_groups.new(name=k)
                groups[k] = g
            g.add([i], val, 'REPLACE')


def foot_vertex_mask(weights, sides=('L', 'R')):
    out = set()
    names = {'Bip01 %s Foot' % s for s in sides} | \
            {'Bip01 %s Toe0' % s for s in sides}
    for i, w in enumerate(weights):
        if any(k in names and v > 0.3 for k, v in w.items()):
            out.add(i)
    return out


def lift_feet(verts, weights, ground=yue_src.GROUND_Z):
    """把脚底对齐到地面；返回 (新顶点, 抬升量)。"""
    mask = sorted(foot_vertex_mask(weights))
    if not mask:
        return verts, 0.0
    dz = ground - float(verts[mask][:, 2].min())
    if abs(dz) < 0.05:
        return verts, 0.0
    out = verts.copy()
    out[mask, 2] += dz
    return out, dz


def make_material(name, texture):
    """占位材质；阶段 2 会用真正的 X4 材质替换掉它。

    一个完全没有材质槽的子网格会被静默丢掉，所以几何引用到的每个材质
    都必须在这里存在，哪怕真正的 DDS 绑定发生在后面。
    """
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (400, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    if texture and os.path.exists(texture):
        img = bpy.data.images.load(texture, check_existing=True)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.label = 'Diffuse'
        tex.location = (-350, 200)
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.55
    return mat


# --------------------------------------------------------------------------
def main():
    paths.ensure(paths.WORK)
    arm, x4_bones = load_x4_armature()
    print('X4 骨架：%d 骨' % len(x4_bones))

    src_path = paths.outfit_glb(OUTFIT)
    g = glblib.Glb(src_path)
    joint_names, joint_mats = g.joints()
    src_pos = {n: joint_mats[i][:3, 3] for i, n in enumerate(joint_names)}
    nodes = g.g['nodes']
    parent_idx = {}
    for i, nd in enumerate(nodes):
        for c in nd.get('children', []):
            parent_idx[c] = i
    joints = g.g['skins'][0]['joints']
    src_par = {}
    for k, j in enumerate(joints):
        p = parent_idx.get(j)
        src_par[joint_names[k]] = (nodes[p].get('name') if p is not None
                                   else None)

    bones = [{'name': n, 'parent': -1, 'position': src_pos[n]}
             for n in joint_names]
    # `check_core` / `build_bone_map` 期望的是一份带索引父表
    idx_of = {n: i for i, n in enumerate(joint_names)}
    for b in bones:
        p = src_par.get(b['name'])
        b['parent'] = idx_of[p] if p in idx_of else -1

    check_core(bones)
    bmap = build_bone_map(bones)
    adapter = YueAdapter(bmap)

    # 带权骨：从 glb 的 JOINTS_0 统计
    weighted = set()
    total_v = total_t = 0
    for mat_name, a in g.prims():
        total_v += len(a['pos'])
        total_t += len(a['idx']) // 3
        J = a.get('joints')
        if J is None:
            continue
        W = a['weights']
        used = np.unique(J[W > 1e-6])
        for bi in used:
            weighted.add(joint_names[int(bi)])
    print('%s：%d 顶点，%d 三角面，%d 带权骨'
          % (OUTFIT['name'], total_v, total_t, len(weighted)))
    report_map(bones, bmap, set(x4_bones), sorted(weighted))

    transfer = BindPoseRetarget(src_pos, src_par, x4_bones, adapter=adapter)

    # ------------------------------------------------------------------
    # 逐 primitive 变换：每个 primitive 的权重是 (n,4) 的 JOINTS/WEIGHTS
    parts = []
    dropped = {}
    for mat_name, a in g.prims():
        # 先判丢弃再查 stem：`M_ProxyHide` 本来就故意没有 stem，顺序反了会
        # 对每个 primitive 报一次"材质无 stem"，把真正的映射错误淹掉。
        if mat_name in yue_src.DROP_MATERIALS:
            dropped[mat_name] = dropped.get(mat_name, 0) + len(a['pos'])
            continue
        stem = yue_src.stem_of(OUTFIT_KEY, mat_name)
        if stem is None:
            print('   !! 材质无 stem：%s' % mat_name)
            continue
        J = a.get('joints')
        W = a.get('weights')
        if J is None or W is None:
            print('   !! %s 没有蒙皮，跳过' % mat_name)
            continue
        weights = []
        for v in range(len(J)):
            wl = []
            for s in range(4):
                w = float(W[v][s])
                if w > 1e-6:
                    wl.append((int(J[v][s]), w))
            weights.append(wl)

        Vx, n_unw, n_targets = transfer.transform(a['pos'], weights,
                                                  joint_names)
        Wx = transfer.merge_weights(weights, joint_names)
        Nx = (transfer.R @ a['nrm'].T).T if 'nrm' in a else None
        parts.append({
            'stem': stem, 'material': mat_name, 'verts': Vx, 'weights': Wx,
            'normals': Nx, 'uvs': a['uv'], 'idx': a['idx'],
            'region': yue_src.REGION_OF.get(stem),
        })

    # 脚：整只脚共用一个位移（否则脚跟会翘起来离地）
    for _m, _n in sorted(dropped.items()):
        print('  -- 丢弃 %s：%d 顶点（Pal7 自己的"别画这个"标记）' % (_m, _n))
    all_v = np.vstack([p['verts'] for p in parts])
    base_W = [{} for _ in range(len(all_v))]
    off = 0
    for p in parts:
        for i, w in enumerate(p['weights']):
            base_W[off + i] = w
        off += len(p['verts'])
    _lifted, dz = lift_feet(all_v, base_W)
    if dz:
        print('  脚：整体抬升 %.2f cm 对齐地面' % dz)
        for p in parts:
            p['verts'] = p['verts'] + np.array([0.0, 0.0, dz])

    # ------------------------------------------------ 重合层外推
    # 衣服是**贴在身体上**建模的，两层同深就会 z-fighting（实机是一块
    # 闪烁的斑）。沿自身法线把衣服推出去 2 mm：远低于 NPC 距离上看得见的
    # 尺度，又远高于那里深度缓冲的分辨率。
    def push(part_list, distance):
        n = 0
        for p in part_list:
            if p['normals'] is None or not len(p['verts']):
                continue
            nn = p['normals'].copy()
            ln = np.linalg.norm(nn, axis=1, keepdims=True)
            ln[ln < 1e-9] = 1.0
            p['verts'] = p['verts'] + (nn / ln) * distance
            n += len(p['verts'])
        return n

    cloth = [p for p in parts if p['stem'] in
             ('cloth1', 'cloth2', 'cloth3', 'tassel')]
    if cloth:
        n = push(cloth, yue_src.CLOTH_OFFSET)
        print('  衣服：%d 顶点外推 %.1f mm（消除与皮肤的 z-fighting）'
              % (n, yue_src.CLOTH_OFFSET * 10))
    occ = [p for p in parts if p['stem'] == 'eyeocc']
    if occ:
        push(occ, yue_src.OCCLUSION_OFFSET)

    # ------------------------------------------------------------------ 网格
    tex_dir = paths.outfit_tex(OUTFIT)
    ratios = yue_src.DECIMATE[OUTFIT_KEY]
    blender_mats = {}
    built = []
    for p in parts:
        stem = p['stem']
        region = p['region']
        if region is None:
            print('   !! %s 没有归属资产，跳过' % stem)
            continue
        nv_src = len(p['verts'])
        # 反射：映射 det = -1，每个三角形要反过来写，否则整片朝内。
        faces = [(int(p['idx'][i + 2]), int(p['idx'][i + 1]), int(p['idx'][i]))
                 for i in range(0, len(p['idx']), 3)]
        # 去重顶点（UE4 的 primitive 里顶点已按 UV/法线接缝裂开，但
        # 同一索引仍可能出现多次；合并能省下不少预算）
        used = sorted({i for f in faces for i in f})
        remap = {o: n for n, o in enumerate(used)}
        sverts = [tuple(float(x) for x in p['verts'][i]) for i in used]
        sfaces = [tuple(remap[i] for i in f) for f in faces]

        mat_name = 'yue.%s_%s' % (OUTFIT_KEY, stem)
        if mat_name not in blender_mats:
            tstem = yue_src.texture_stem_of(OUTFIT_KEY, p['material'])
            cand = None
            if tstem:
                for ext in ('.png', '.PNG'):
                    q = os.path.join(tex_dir, tstem + ext)
                    if os.path.exists(q):
                        cand = q
                        break
            blender_mats[mat_name] = make_material(mat_name, cand)

        obj_name = 'yue_%s_%s_%s' % (OUTFIT_KEY, stem, region[0])
        me = bpy.data.meshes.new(obj_name)
        me.from_pydata(sverts, [], sfaces)
        # 不用 mesh.validate()：它会把重合的反向面当成"重复多边形"删掉。
        me.update()
        for poly in me.polygons:
            poly.use_smooth = True
        # UV：glTF 的 v 向下（与 PMX 同），Blender 的向上；导出器还会再翻
        # 一次，所以这里存 1 - v，两边的翻转互相抵消。
        uvl = [(float(p['uvs'][i][0]), 1.0 - float(p['uvs'][i][1]))
               for i in used]
        uv_layer = me.uv_layers.new(name='UVMap')
        for loop in me.loops:
            uv_layer.data[loop.index].uv = uvl[loop.vertex_index]

        ob = bpy.data.objects.new(obj_name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(blender_mats[mat_name])

        groups_vg = {}
        for newi, oldi in enumerate(used):
            for gname, gval in p['weights'][oldi].items():
                vg = groups_vg.get(gname)
                if vg is None:
                    vg = ob.vertex_groups.new(name=gname)
                    groups_vg[gname] = vg
                vg.add([newi], gval, 'REPLACE')

        ratio = ratios.get(stem, yue_src.DEFAULT_DECIMATE)
        nv_before = len(me.vertices)
        nv_after, unw, failed = decimate(ob, ratio)
        if failed:
            print('      %s：减面会只剩 %d 顶点，保留 %d'
                  % (obj_name, nv_after, nv_before))
        smooth_vertex_weights(ob)

        ob['x4cc_part'] = stem
        ob['x4cc_region'] = region
        ob['x4cc_material'] = mat_name
        ob.parent = arm
        mod = ob.modifiers.new(name='Armature', type='ARMATURE')
        mod.object = arm
        built.append(ob)
        print('  %-26s %-4s 面 %-6d 顶点 %d -> %d  材质槽=%d 顶点组=%d'
              % (obj_name, region, len(sfaces), nv_before, nv_after,
                 len(ob.data.materials), len(ob.vertex_groups)))

    out = paths.stage1_blend(OUTFIT)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('SAVED %s' % out)
    print('对象：%d' % len(built))


main()