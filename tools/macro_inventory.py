# -*- coding: utf-8 -*-
"""人物 macro 清单：**查一次、落盘、按游戏版本复用**。

    python tools/macro_inventory.py --check        # 开工第一步：版本对得上就直接复用
    python tools/macro_inventory.py --rebuild      # 强制重查并落盘

## 为什么要有这个

"哪些 macro 算 Argon 女性""哪些外观池会刷她们"这两份清单，是每次替换工程都要
用、又每次都要重查的东西。重查一次要合并 8 个库、递归展开 429 个池 —— 不难，
但**每次换 X4 版本答案都会变**（新增/删除 macro、改池的指向、DLC 加池）。

于是有两种错法，都很安静：

* **拿旧清单去 replace**：mod 装上了、加载了，一部分 NPC 变了、另一部分没变，
  任何日志里都没有一行报错；
* **每次都重查**：慢，而且如果没有和版本绑定，"这次查的和上次查的"是不是同一个
  版本，谁也说不清。

所以清单落盘时**带上游戏指纹**，复用前先比指纹。

## 指纹是什么

`0N.cat` / `0N.dat` 的**文件名 + 字节数**列表，加上 `ego_dlc_*` 目录名。
不用 `extensions/` 的完整列表：玩家自己装的 mod 也住在那里，会让指纹每次开机都变。
基础包的字节数变化就足以捕捉版本更新（Egosoft 每次改内容都会重建这些包）。

## 落盘位置

    work/macro_inventory_<指纹前 12 位>.json

同一台机器上装过几个版本就留几份，互不覆盖 —— 这也正是"有对应版本数据就复用"
的前提。
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paths                                                      # noqa: E402
import make_mod                                                   # noqa: E402
import find_female_macros as ffm                                  # noqa: E402
from x4lib import (load_tree, index, expand_pool,          # noqa: E402
                   effective_race, audit_race)


# --------------------------------------------------------------------------
# 指纹
# --------------------------------------------------------------------------
def fingerprint(game=None):
    """(短哈希, 明细)。读不到游戏目录时返回 (None, {'error': ...})。"""
    game = game or paths.GAME
    if not game or not os.path.isdir(game):
        return None, {'error': 'game dir not found: %s' % game}
    cats = []
    for p in sorted(glob.glob(os.path.join(game, '*.cat'))):
        dat = p[:-4] + '.dat'
        if not os.path.isfile(dat):
            continue
        cats.append('%s:%d' % (os.path.basename(p),
                               os.path.getsize(dat)))
    dlcs = sorted(os.path.basename(d)
                  for d in glob.glob(os.path.join(game, 'extensions',
                                                  'ego_dlc_*')))
    detail = {'base_paks': cats, 'dlcs': dlcs}
    raw = json.dumps(detail, sort_keys=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:12], detail


def inventory_path(fp):
    return os.path.join(paths.WORK, 'macro_inventory_%s.json' % fp)


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
# 查询函数在 x4lib 里（load_tree / index / expand_pool / effective_race /
# audit_race），这里不再各写一份。


def build(verbose=True):
    pools = index(load_tree(make_mod.POOL_SOURCES), 'characters')
    macros = index(load_tree(make_mod.MACRO_SOURCES), 'macros')
    female = sorted(n for n in pools if n and n.endswith('.female'))
    if verbose:
        print('库：%d 个 macro 定义，%d 个池（其中 .female %d 个）'
              % (len(macros), len(pools), len(female)))

    races = {}
    # 池前缀表来自 make_mod，不在两处各写一份
    for r in sorted(make_mod.RACES):
        make_mod.configure(r, 'add')
        prefixes = make_mod.RACES[r]['pool_prefixes']
        direct, routers, names = audit_race(r, pools, macros, prefixes)
        races[r] = {
            'pool_prefixes': list(prefixes),
            'pools_direct': direct,
            'pools_router': routers,
            'pools_total_that_spawn_race': len(direct) + len(routers),
            'macros_in_those_pools': names,
        }
        if verbose:
            print('  %-8s 会刷该种族女性的池 %d 个（直接 %d + 路由 %d），'
                  '涉及 macro %d 个'
                  % (r, len(direct) + len(routers), len(direct),
                     len(routers), len(names)))

    fp, detail = fingerprint()
    return {
        'fingerprint': fp,
        'fingerprint_detail': detail,
        'built': time.strftime('%Y-%m-%d %H:%M:%S'),
        'game_dir': paths.GAME,
        'totals': {'macros': len(macros), 'pools': len(pools),
                   'female_pools': len(female)},
        'races': races,
    }


# --------------------------------------------------------------------------
def summarize(data):
    t = data.get('totals', {})
    print('清单版本指纹 %s（建于 %s）' % (data.get('fingerprint'),
                                         data.get('built')))
    print('  %d 个 macro 定义，%d 个池，其中 %d 个 .female 池'
          % (t.get('macros', 0), t.get('pools', 0), t.get('female_pools', 0)))
    for r, rec in sorted((data.get('races') or {}).items()):
        print('  [%s] 该覆盖的池 %d 个（直接） + %d 个纯路由；'
              '前缀 %s'
              % (r, len(rec.get('pools_direct', [])),
                 len(rec.get('pools_router', [])),
                 ','.join(rec.get('pool_prefixes', []))))
        for n in rec.get('pools_direct', []):
            print('       %s' % n)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true',
                    help='比对指纹；命中就复用，未命中提示 --rebuild')
    ap.add_argument('--rebuild', action='store_true', help='强制重查并落盘')
    ap.add_argument('--print', dest='show', action='store_true',
                    help='打印已落盘清单的摘要')
    args = ap.parse_args()

    if args.check or not (args.rebuild or args.show):
        fp, detail = fingerprint()
        if fp is None:
            print('读不到游戏目录，无法做版本检验：%s' % detail.get('error'))
            print('（设 X4_GAME 指向 X4 安装目录）')
            return 2
        p = inventory_path(fp)
        if os.path.exists(p) and not args.rebuild:
            data = json.load(open(p, encoding='utf-8'))
            print('版本命中，复用清单 %s' % p)
            summarize(data)
            return 0
        print('版本未命中（指纹 %s）：这个版本还没有清单。' % fp)
        print('  已知的其它版本清单：')
        for q in sorted(glob.glob(os.path.join(paths.WORK,
                                               'macro_inventory_*.json'))):
            print('    %s' % os.path.basename(q))
        if not args.check:
            print('\n跑 --rebuild 全量重查。')
        return 3

    data = build()
    paths.ensure(paths.WORK)
    p = inventory_path(data['fingerprint'])
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print('\n落盘：%s' % p)
    summarize(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())