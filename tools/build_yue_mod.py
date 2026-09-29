# -*- coding: utf-8 -*-
"""阶段 2：把重定向好的几何填进 vanilla 宿主的网格槽位，导出 `.xac`。

    blender -b --factory-startup --python tools/build_yue_mod.py -- --outfit a

一个套装导出两个资产：`head`（脸 + 头发）与 `body`（皮肤 + 衣服）。宿主是
vanilla 的 Argon 女性资产 —— **骨架留在宿主里不动**，只换网格。这就是
"换网格、留骨架"：`character_components.xml` 里的共享 component 持有骨架和
全部动画，macro 只挑 head/torso/props 三个网格槽位。

槽位表从 `yue_src.SLOTS` 派生，不在这里另写一份：两处各写一份必然会悄悄分歧，
而分歧的表现是"某个部件不见了"，不是报错。
"""

import os
import shutil
import sys

import addon_utils
import bpy
import pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths                                                      # noqa: E402
import yue_src                                                    # noqa: E402
import x4_materials                                               # noqa: E402

if paths.ADDON_DIR:
    sys.path.insert(0, paths.ADDON_DIR)


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

HOSTS = {
    'head': r'assets\characters\argon\heads\char_arg_f_dyn_blend_head.xac',
    'body': r'assets\characters\argon\bodies\char_arg_f_jacket_leggings_civ_01.xac',
}

#: 资产在扩展里的落点。两套装用不同的文件名，因为两者会同时装在一个 mod 里
#: （add 形态下两个 macro 都要能选到各自的网格）。
ASSET_PATH = {
    'head': r'assets\characters\argon\yueqingshu\heads\yue_%s_head.xac',
    'body': r'assets\characters\argon\yueqingshu\bodies\yue_%s_body.xac',
}


def slot_plan(key):
    """`yue_src.SLOTS` -> [(对象名, 宿主槽位, [(stem, region), ...])]。"""
    plan = {}
    for region, slots in yue_src.SLOTS.items():
        rows = []
        for slot_name, stems, mesh_id in slots:
            rows.append(('yue_%s_%s_%s' % (key, region, slot_name), mesh_id,
                         [(s, region) for s in stems]))
        plan[region] = rows
    return plan


def read_part_geometry():
    """{(stem, region): [ {material_name, verts, weights, uvs, faces} ]}。"""
    bpy.ops.wm.open_mainfile(filepath=paths.stage1_blend(OUTFIT))
    parts = {}
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        stem = ob.get('x4cc_part')
        region = ob.get('x4cc_region')
        if not stem:
            continue
        me = ob.data
        gname = {g.index: g.name for g in ob.vertex_groups}
        verts = [tuple(v.co) for v in me.vertices]
        weights = []
        for v in me.vertices:
            wd = {}
            for ge in v.groups:
                if ge.weight > 1e-6:
                    nm = gname.get(ge.group)
                    if nm:
                        wd[nm] = wd.get(nm, 0.0) + ge.weight
            weights.append(wd)
        uv_layer = me.uv_layers[0].data if len(me.uv_layers) else None
        uvs = []
        if uv_layer is not None:
            for loop in me.loops:
                uvs.append(tuple(uv_layer[loop.index].uv))
        mat = me.materials[0] if me.materials else None
        parts.setdefault((stem, region), []).append({
            'material_name': mat.name if mat else None,
            'verts': verts, 'weights': weights, 'uvs': uvs,
            'faces': [tuple(p.vertices) for p in me.polygons],
        })
    return parts


def fill_slot(host_ob, obj_name, sources, materials):
    """用一个合并后的网格替换宿主槽位里原有的几何。"""
    verts, weights, faces, uvs, mat_order, mat_index = [], [], [], [], [], {}

    for src in sources:
        mn = src['material_name']
        mat = materials.get(mn) or materials.get(None)
        if mat is None:
            continue
        if mat.name not in mat_index:
            mat_index[mat.name] = len(mat_order)
            mat_order.append(mat)
        slot = mat_index[mat.name]

        base = len(verts)
        verts.extend(tuple(p) for p in src['verts'])
        weights.extend(src['weights'])
        for f in src['faces']:
            faces.append((f[0] + base, f[1] + base, f[2] + base, slot))
        uvs.extend(src.get('uvs') or [])

    if not faces:
        # `.xac` 表达不了"空槽位"：删掉对象会让导出器从模板重建它（带着
        # **vanilla 的几何**），而一个 3 顶点的桩会因为没有任何骨骼权重被拒。
        # 胸腔里一个 1 cm 的三角形两边都合法，而且看不见。
        verts = [(0.0, 0.0, 120.0), (1.0, 0.0, 120.0), (0.0, 1.0, 120.0)]
        weights = [{'Bip01 Spine1': 1.0} for _ in range(3)]
        faces = [(0, 1, 2, 0)]
        uvs = [(0.0, 0.0)] * 3
        mat_order = [next(iter(materials.values()))]

    me = bpy.data.meshes.new(obj_name)
    me.from_pydata(verts, [], [(f[0], f[1], f[2]) for f in faces])
    # 不用 mesh.validate()：它会把重合的反向面当"重复多边形"删掉。
    me.update()
    # 平滑着色必须在这里**再设一次**：这个网格是从零重建的，from_pydata
    # 默认平面着色，而导出器读的是 loop.normal —— 漏掉就是满脸面片，
    # 同时顶点数暴涨（每条 UV 缝+法线缝都算一个顶点）。
    for poly in me.polygons:
        poly.use_smooth = True
    for m in mat_order:
        me.materials.append(m)
    if len(me.polygons) != len(faces):
        print('   !! %s：from_pydata 产生 %d 个面，应为 %d —— 材质索引会错位'
              % (obj_name, len(me.polygons), len(faces)))
    else:
        for poly, f in zip(me.polygons, faces):
            poly.material_index = f[3]

    uv = me.uv_layers.new(name='UVMap')
    if len(uvs) == len(me.loops):
        for loop, v in zip(me.loops, uvs):
            uv.data[loop.index].uv = (v[0], v[1])
    else:
        print('   !! %s：UV 数 %d != loop 数 %d，用 (0,0)'
              % (obj_name, len(uvs), len(me.loops)))
        for loop in me.loops:
            uv.data[loop.index].uv = (0.0, 0.0)

    host_ob.data = me
    host_ob.name = obj_name
    for g in list(host_ob.vertex_groups):
        host_ob.vertex_groups.remove(g)
    groups = {}
    for vi, wd in enumerate(weights):
        for gname, gval in wd.items():
            g = groups.get(gname)
            if g is None:
                g = host_ob.vertex_groups.new(name=gname)
                groups[gname] = g
            g.add([vi], gval, 'REPLACE')
    return len(verts), len(faces), len(mat_order)


def build_asset(target, parts, plan):
    used = {s['material_name'] for e in parts.values() for s in e}
    print('[%s/%s] 零件=%d 材质=%d' % (OUTFIT_KEY, target, len(parts),
                                       len(used)))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('X4CharacterConverter', default_set=True)
    bpy.context.preferences.addons[
        'X4CharacterConverter'].preferences.data_root = paths.X4_ROOT + os.sep
    from X4CharacterConverter import addon as A2

    mats = x4_materials.create_materials(paths.DDS_DIR, only=used,
                                         collection='yue')
    print('[%s/%s] 材质：%d' % (OUTFIT_KEY, target, len(mats) - 1))

    A2.import_actor(bpy.context, pathlib.Path(
        os.path.join(paths.X4_ROOT, HOSTS[target])))
    slots = {}
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.get('x4cc_actor_id'):
            mid = ob.get('x4cc_mesh_id')
            if mid is not None:
                slots[int(mid)] = ob
    print('[%s/%s] 宿主槽位：%s' % (OUTFIT_KEY, target, sorted(slots)))

    kept = []
    for obj_name, mesh_id, wanted in plan[target]:
        host_ob = slots.get(mesh_id)
        if host_ob is None:
            print('   !! 槽位 %d 不存在' % mesh_id)
            continue
        sources = [s for key in wanted for s in parts.get(key, [])]
        if not sources:
            fill_slot(host_ob, obj_name, [], mats)
            print('   -- 槽位 %d (%s) 置空' % (mesh_id, obj_name))
            kept.append(host_ob)
            continue
        nv, nf, nm = fill_slot(host_ob, obj_name, sources, mats)
        print('   %-24s 槽位=%d 顶点=%-6d 面=%-6d 材质=%d'
              % (obj_name, mesh_id, nv, nf, nm))
        kept.append(host_ob)

    for mesh_id, ob in slots.items():
        if ob not in kept:
            fill_slot(ob, 'yue_unused_%d' % mesh_id, [], mats)
            print('   -- 槽位 %d 折叠（置空）' % mesh_id)

    export_name = os.path.basename(ASSET_PATH[target] % OUTFIT_KEY)
    pkg_target = os.path.join(paths.pkg_dir(OUTFIT), os.path.splitext(export_name)[0])
    if os.path.isdir(pkg_target):
        shutil.rmtree(pkg_target)
    pkg = A2.export_package(bpy.context, pathlib.Path(pkg_target))
    print('[%s/%s] 导出 -> %s' % (OUTFIT_KEY, target, pkg))
    return pkg


def main():
    paths.ensure(paths.PKG, paths.pkg_dir(OUTFIT))
    plan = slot_plan(OUTFIT_KEY)
    for target in ('head', 'body'):
        parts = read_part_geometry()
        build_asset(target, parts, plan)


if __name__ == '__main__':
    main()