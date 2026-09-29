# -*- coding: utf-8 -*-
"""把源 PNG 编成 X4 要的 DDS，并写一份材质 manifest。

    python tools/prepare_textures_yue.py [--outfit a|b|all]

在 Blender **之外**跑，因为 Blender 自带的 Python 没有 PIL。

三种贴图槽，格式由转换器校验：

    Diffuse     BC1   （有 alpha 遮罩的才用 BC3）
    Normal      BC5   源就带法线图，直接用，不生成假的平面法线
    Smoothness  BC4   **从源 `_ORM` 的绿通道取**：smoothness = 1 - roughness
                      （X4 的 Smoothness 槽接进 Roughness 之前会过一次
                      Invert，见 `x4_materials.create_materials`）

这是这个来源相对 MMD 来源最大的优势：法线和粗糙度都是作者画的，不用猜。

贴图按**源文件**去重：两套装共用同一张脸、同一个身体，只有衣服和流苏不同，
所以脸和身体的 DDS 只编码一次，两套材质指向同一个文件。
"""

import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bc_encode                                                  # noqa: E402
import paths                                                      # noqa: E402
import yue_src                                                    # noqa: E402

#: X4 wants at most 1024 on a body texture; these sources are 2048 and 4096.
MAX_SIZE = 1024
#: the source normal maps carry fine weave detail that dies at 1024; they are
#: the one slot worth the extra memory.
MAX_SIZE_NORMAL = 1024

COLLECTION = 'yue'


def arg(name, default=None):
    argv = sys.argv
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def find_png(tex_dir, basename):
    """Locate `<basename>.png` in the source texture directory (or None)."""
    if not basename:
        return None
    for ext in ('.png', '.PNG', '.tga'):
        p = os.path.join(tex_dir, basename + ext)
        if os.path.isfile(p):
            return p
    return None


def load_tex(path, size):
    img = Image.open(path)
    if img.mode not in ('RGB', 'RGBA', 'L'):
        img = img.convert('RGB')
    if size and max(img.size) > size:
        w, h = img.size
        s = size / float(max(w, h))
        img = img.resize((max(1, int(w * s)), max(1, int(h * s))),
                         Image.LANCZOS)
    return img


def bleed_colors(img, rounds=12):
    """把不透明像素的颜色扩散进透明区。

    透明像素的颜色通常是纯黑，而 mip 生成会**盲目平均**颜色：贴着遮罩边界
    的一个二级纹素是本体色与黑的混合，于是任何采样到边缘附近的 UV 都会读到
    灰黑色 —— 实机表现是遮罩边缘一圈深色斑点。先用最近的可用颜色填满透明区，
    平均值才有意义，alpha 仍然照常携带遮罩。必须在建 mip 链**之前**做。
    """
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    rgb, alpha = a[..., :3].copy(), a[..., 3]
    filled = alpha > 127
    if filled.all() or not filled.any():
        return img
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1),
              (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for _ in range(rounds):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(rgb.shape[:2], np.float32)
        for dy, dx in shifts:
            acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * \
                np.roll(np.roll(filled, dy, 0), dx, 1)[..., None]
            cnt += np.roll(np.roll(filled, dy, 0), dx, 1)
        todo = (~filled) & (cnt > 0)
        if not todo.any():
            break
        rgb[todo] = acc[todo] / cnt[todo][..., None]
        filled |= todo
    out = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def normal_from(img):
    """源法线图 -> BC5 要的 (R, G) 双通道图。

    Pal7 存的是标准切线空间法线（RGB，+Y up）。BC5 只存 XY，Z 由引擎重建，
    质量比 BC1 高一截；转换器要的也正是 BC5。
    """
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255.0
    n = a * 2.0 - 1.0
    ln = np.linalg.norm(n, axis=2, keepdims=True)
    ln[ln < 1e-6] = 1.0
    n = n / ln
    # BC5 的 G 通道在 DirectX 约定下存 -Y；X4 用 OpenGL 约定（+Y up），
    # 源图也是 +Y up，所以原样取 XY。
    # `encode_bc5` 走 `im.convert('RGB')` 再取前两个通道，所以这里必须是
    # 三通道：只给两通道的话 PIL 的 fromarray 会按 RGB 解析而数据不够，
    # 报 "not enough image data"。
    xy = np.stack([(n[..., 0] * 0.5 + 0.5) * 255.0,
                   (n[..., 1] * 0.5 + 0.5) * 255.0,
                   np.full(n.shape[:2], 255.0)], axis=-1)
    return Image.fromarray(np.clip(xy, 0, 255).astype(np.uint8))


def flat_normal(size):
    a = np.zeros((size[1], size[0], 3), np.uint8)
    a[..., 0] = 128
    a[..., 1] = 128
    a[..., 2] = 255
    return Image.fromarray(a)


def smoothness_from(orm, size, fallback):
    """源 ORM 绿通道 -> smoothness 灰度图（1 - roughness）。"""
    if orm is None:
        return Image.fromarray(
            np.full((size[1], size[0]), int(round(fallback * 255)), np.uint8))
    img = load_tex(orm, MAX_SIZE).convert('RGB')
    if img.size != size:
        img = img.resize(size, Image.LANCZOS)
    g = np.asarray(img).astype(np.float32)[..., 1] / 255.0
    return Image.fromarray(
        np.clip((1.0 - g) * 255.0, 0, 255).astype(np.uint8))


def dds_stem(basename):
    """源贴图 basename -> DDS 文件名用的 ascii 词干。"""
    s = yue_src.ascii_stem(basename)
    for pre in ('t_maj02_01_', 't_maj02_02_', 'maj02_02_', 'maj02_01_', 't_'):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s


# --------------------------------------------------------------------------
def encode_outfit(key, out_dir, cache, verbose=True):
    """给一个套装编码它需要的全部 DDS；返回 manifest 片段。"""
    outfit = yue_src.outfit(key)
    tex_dir = paths.outfit_tex(outfit)
    mats = yue_src.materials(key)
    manifest = {}
    if verbose:
        print('== 套装 %s（%s） 贴图目录 %s' % (key, outfit['name'], tex_dir))

    for mat_name, rec in sorted(mats.items()):
        stem, d, n, o = rec
        name = '%s.%s_%s' % (COLLECTION, key, stem)
        diff_png = find_png(tex_dir, d)
        nrm_png = find_png(tex_dir, n)
        orm_png = find_png(tex_dir, o)
        if diff_png is None and d is not None:
            print('   !! %-26s 缺少漫反射贴图 %s.png' % (mat_name, d))

        shader = yue_src.SHADER.get(stem, 'p1_character')
        blend = yue_src.BLEND.get(stem, yue_src.DEFAULT_BLEND)
        smooth0 = yue_src.SMOOTHNESS.get(stem, 0.25)

        entry = {
            'x4_name': name, 'stem': stem, 'outfit': key,
            'source_material': mat_name,
            'alpha': stem in yue_src.ALPHA_STEMS,
            'shader': shader, 'blendmode': blend,
            'smoothness': smooth0, 'depth': 0.5,
            'textures': {},
        }

        # ---------------------------------------------------- diffuse
        if diff_png:
            ck = ('diff', os.path.normcase(diff_png), MAX_SIZE)
            if ck not in cache:
                img = load_tex(diff_png, MAX_SIZE)
                rgba = img.convert('RGBA')
                needs_alpha = any(
                    m in yue_src.ALPHA_STEMS
                    for k2 in yue_src.MATS.values()
                    for m, r2 in k2.items() if r2[1] == d)
                base = os.path.join(out_dir, '%s_%s_diff.dds'
                                    % (COLLECTION, dds_stem(d)))
                if rgba.getchannel('A').getextrema()[0] < 128:
                    rgba = bleed_colors(rgba)
                if needs_alpha:
                    bc_encode.encode_bc3(rgba, base)
                    fmt = 'BC3'
                else:
                    bc_encode.encode_bc1(rgba.convert('RGB'), base)
                    fmt = 'BC1'
                cache[ck] = (base, fmt, img.size)
                if verbose:
                    print('   %-22s %-34s %sx%s -> %s'
                          % (stem, os.path.basename(diff_png),
                             img.size[0], img.size[1], fmt))
            base, fmt, size = cache[ck]
            entry['textures']['Diffuse'] = base
        else:
            # 导出器要求**每个**材质都有 Diffuse 节点（缺一个就
            # `XacError: missing required texture node`），而 Pal7 有几个
            # 材质根本没有基础色贴图 —— 颜色全在 shader 参数里。
            # 给它们一张纯色图；颜色从渲染预览里读出来，不是随手编的。
            size = (MAX_SIZE, MAX_SIZE)
            rgb = yue_src.PLACEHOLDER_RGB.get(stem,
                                              yue_src.DEFAULT_PLACEHOLDER)
            ck = ('flat', stem, rgb)
            if ck not in cache:
                base = os.path.join(out_dir, '%s_%s_%s_diff.dds'
                                    % (COLLECTION, key, stem))
                bc_encode.encode_bc1(Image.new('RGB', size, tuple(rgb)), base)
                cache[ck] = (base, 'BC1', size)
                if verbose:
                    print('   %-22s 无基础色贴图 -> 占位纯色 #%02X%02X%02X'
                          % (stem, rgb[0], rgb[1], rgb[2]))
            base, fmt, size = cache[ck]
            entry['textures']['Diffuse'] = base

        # ----------------------------------------------------- normal
        ck = ('nrm', os.path.normcase(nrm_png) if nrm_png else None, size)
        if ck not in cache:
            base = os.path.join(out_dir, '%s_%s_nrm.dds' % (COLLECTION, stem))
            if nrm_png:
                img = load_tex(nrm_png, MAX_SIZE_NORMAL)
                bc_encode.encode_bc5(normal_from(img), base)
                src = os.path.basename(nrm_png)
            else:
                bc_encode.encode_bc5(flat_normal(size), base)
                src = '(平坦法线)'
            cache[ck] = (base, src)
            if verbose:
                print('   %-22s 法线 %-30s -> BC5' % (stem, src))
        entry['textures']['Normal'] = cache[ck][0]

        # ------------------------------------------------- smoothness
        ck = ('smooth', os.path.normcase(orm_png) if orm_png else None,
              size, smooth0)
        if ck not in cache:
            base = os.path.join(out_dir, '%s_%s_smooth.dds' % (COLLECTION, stem))
            bc_encode.encode_bc4(smoothness_from(orm_png, size, smooth0), base)
            cache[ck] = base
        entry['textures']['Smoothness'] = cache[ck]

        manifest[name] = entry

    return manifest


def main():
    which = arg('--outfit', 'all')
    keys = ['a', 'b'] if which == 'all' else [which]
    out_dir = paths.DDS_DIR
    paths.ensure(out_dir)

    cache = {}
    manifest = {}
    for k in keys:
        manifest.update(encode_outfit(k, out_dir, cache))

    # 阶段 2 会按 x4_name 去查 manifest；两套装的材质名不同，所以合并成
    # 一份即可，`outfit` 字段保留来源信息。
    out = os.path.join(out_dir, 'manifest.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    files = {p for e in manifest.values() for p in e['textures'].values()}
    total = sum(os.path.getsize(p) for p in files if os.path.exists(p))
    print('manifest: %s（%d 个材质，%d 个 DDS，%.1f MB）'
          % (out, len(manifest), len(files), total / 1e6))


if __name__ == '__main__':
    main()