# -*- coding: utf-8 -*-
"""一条命令端到端重建。

    python tools/build_all.py --mode add        # 只构建
    python tools/build_all.py --mode add --deploy   # 构建并安装进游戏

    stage1    Blender  重定向 + 减面 + 分 head/body   -> work/yue_<k>_stage1.blend
    textures  python   DDS + manifest                -> work/tex_out/mats/
    stage2    Blender  填宿主槽位、导出 .xac          -> work/x4cc_pkg/<k>/
    mod       python   XML + 材质库                  -> work/x4_yue_argon_<mode>/
    pack      XRCatTool                              -> ext_01.cat / ext_01.dat
    deploy    python   拷进游戏                       -> extensions/x4_yueqingshu_mod/

每一步都是**全量重建**：stage1 的 blend、整套 DDS、两个包、mod 目录和已安装的
扩展全部从零写。没有任何东西是就地修补的，所以陈旧产物不可能在一次运行后
存活 —— 这一点很重要，因为"mod 没生效"和"mod 是上一轮的"在游戏里长得一样。

`deploy` **刻意不在默认步骤里**：它往游戏安装目录写东西，而一个顺手把自己
装进去的构建就是一个会让人意外的构建。只有 `--deploy` 才会做。
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                      # noqa: E402

STEPS = ['stage1', 'textures', 'stage2', 'mod', 'pack']

#: 候选 Blender 位置，按顺序试；`BLENDER` 环境变量覆盖全部
BLENDER_CANDIDATES = [
    os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'),
                 'Blender Foundation'),
    os.path.join(os.environ.get('ProgramW6432', r'C:\Program Files'),
                 'Blender Foundation'),
    r'D:\Blender Foundation',
    r'C:\Blender Foundation',
    '/usr/share/blender',
    '/Applications/Blender.app/Contents/MacOS',
]


def find_blender():
    env = os.environ.get('BLENDER')
    if env and os.path.isfile(env):
        return env
    found = shutil.which('blender')
    if found:
        return found
    hits = []
    for root in BLENDER_CANDIDATES:
        hits += glob.glob(os.path.join(root, 'Blender*', 'blender.exe'))
        hits += glob.glob(os.path.join(root, 'blender'))
    if not hits:
        raise SystemExit('找不到 Blender；设 BLENDER=/path/to/blender')
    hits.sort(reverse=True)          # 新版本优先
    return hits[0]


def run(cmd, label, dry=False):
    print('\n=== %s\n    %s' % (label, ' '.join(cmd)))
    if dry:
        return 0
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit('%s 失败，退出码 %d' % (label, r.returncode))
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--mode', choices=('add', 'replace'), default='add',
                    help='mod 形态（默认 add：正式的形态）')
    ap.add_argument('--race', choices=('argon',), default='argon')
    ap.add_argument('--outfits', default='a',
                    help='要构建的套装（默认只构建 A；B 的源定义还在，'
                         "需要时用 --outfits a,b 恢复）")
    ap.add_argument('--skip', default='', metavar='STEP[,STEP]',
                    help='跳过的步骤：%s[,deploy]' % ','.join(STEPS))
    ap.add_argument('--only', default='', metavar='STEP[,STEP]',
                    help='只跑这些步骤')
    ap.add_argument('--weight', type=int, default=1,
                    help='add 形态：每根 macro 在每个池里列几次')
    ap.add_argument('--deploy', action='store_true',
                    help='完成后安装进游戏')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    only = {s for s in args.only.split(',') if s}
    skip = {s for s in args.skip.split(',') if s}
    todo = [s for s in STEPS if (not only or s in only) and s not in skip]
    if args.deploy:
        todo.append('deploy')
    outfits = [k for k in args.outfits.split(',') if k]
    print('steps: %s   outfits: %s' % (todo, outfits))

    missing = paths.check(verbose=False)
    if missing:
        print('!! 有路径没解析出来：%s' % missing)
        paths.check()
        if 'XRCatTool' in missing and 'pack' in todo:
            raise SystemExit('打包需要 XRCatTool')

    blender = find_blender() if ({'stage1', 'stage2'} & set(todo)) else None
    if blender:
        print('blender: %s' % blender)

    py = [sys.executable]
    mod_dir = paths.mod_dir(args.race, args.mode)
    paths.ensure(paths.WORK)

    for key in outfits:
        if 'stage1' in todo:
            run([blender, '-b', '--factory-startup', '--python',
                 os.path.join(HERE, 'build_yue_x4.py'), '--',
                 '--outfit', key], 'stage1 套装 %s（重定向）' % key,
                args.dry_run)
        if 'stage2' in todo:
            run([blender, '-b', '--factory-startup', '--python',
                 os.path.join(HERE, 'build_yue_mod.py'), '--',
                 '--outfit', key], 'stage2 套装 %s（导出 .xac）' % key,
                args.dry_run)
    if 'textures' in todo:
        paths.ensure(paths.DDS_DIR)
        run(py + [os.path.join(HERE, 'prepare_textures_yue.py')],
            '贴图 -> DDS', args.dry_run)
    if 'mod' in todo:
        run(py + [os.path.join(HERE, 'make_mod.py'), '--race', args.race,
                  '--mode', args.mode, '--weight', str(args.weight)],
            '组装 mod 树', args.dry_run)
    if 'pack' in todo:
        if not paths.XRCAT_TOOL:
            raise SystemExit('找不到 XRCatTool；设 XRCAT_TOOL')
        run([paths.XRCAT_TOOL, '-in', mod_dir.replace('\\', '/'),
             '-out', (mod_dir + '/ext_01.cat').replace('\\', '/')],
            '打包 ext_01.cat', args.dry_run)
    if 'deploy' in todo:
        run(py + [os.path.join(HERE, 'deploy.py'), '--mode', args.mode],
            '安装进游戏', args.dry_run)

    print('\ndone: %s' % mod_dir)


if __name__ == '__main__':
    sys.exit(main())