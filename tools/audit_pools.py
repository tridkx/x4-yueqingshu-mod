# -*- coding: utf-8 -*-
"""审计：哪些外观池会刷出目标种族的女性，add 形态是否覆盖全了。

    python tools/audit_pools.py --race argon

**判据不是池名的前缀，而是"这个池选到的 macro 是不是目标种族的女性"。**
两者会不一致，而且两个方向都会错：

* `antigone.factiondiplomat.female` —— 安提戈涅是 Argon 的衍生势力，池里选的是
  `character_arg_f_diplomat_02_macro`（有效 race = argon）。按前缀筛会漏掉它，
  add 形态下这批女性就还是原版；
* `terran.*.female` 里有两个外交官池选的是 **argon** 的 macro。按"池里 macro 的
  种族"筛会把它们错收进来 —— 而它们属于泰伦，不该被 Argon 的替换影响。

所以判据是**池名所属势力**（谁在用这个池）**加**池里 macro 的有效种族，
两者都要看，缺一个就会错。

`<select character="...">` 会**递归展开**：池可以指向池
（`argon.trader.female` → `argon.civilian.female`），漏掉这一层会少算池。
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paths                                                      # noqa: E402
import make_mod                                                   # noqa: E402
from x4lib import (load_tree, index, expand_pool,            # noqa: E402
                   effective_race, audit_race)


# 查询函数（index / expand_pool / effective_race）在 x4lib 里，这里是同一个实现，
# 不再各写一份 —— 两份必然悄悄分歧。


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--race', default='argon')
    args = ap.parse_args()

    make_mod.configure(args.race, 'add')
    pools = index(load_tree(make_mod.POOL_SOURCES), 'characters')
    macros = index(load_tree(make_mod.MACRO_SOURCES), 'macros')
    print('库：%d 个 macro 定义，%d 个池' % (len(macros), len(pools)))

    female_pools = sorted(n for n in pools if n and n.endswith('.female'))
    print('其中 .female 池：%d 个\n' % len(female_pools))

    # 每个池：它选到的 macro 里，有效 (race, female) 的分布
    rows = []
    for name in female_pools:
        got = expand_pool(pools.get(name), pools)
        kinds = {}
        for m in got:
            r, f = effective_race(macros.get(m), macros)
            kinds[(r, f)] = kinds.get((r, f), 0) + 1
        rows.append((name, got, kinds))

    target = [(n, g, k) for n, g, k in rows if (args.race, 'true') in k]
    # 纯路由池（只含 <select character=...>）不算"该覆盖"：它指向的池已经在
    # 列表里，往它里面塞是死重量。审计必须与 `female_pools_with_macros` 用
    # 同一个判据，否则会把 8 个路由器报成"漏掉"。
    def is_router(name):
        el = pools.get(name)
        if el is None:
            return False
        return not any(c.get('macro') for c in el.findall('select'))
    print('=== 会刷出 %s 女性的池：%d 个 ===' % (args.race, len(target)))
    by_prefix = {}
    for n, g, k in target:
        pre = n.split('.')[0]
        by_prefix.setdefault(pre, []).append((n, len(g), k))
    for pre in sorted(by_prefix):
        print('\n  [%s]  %d 个池' % (pre, len(by_prefix[pre])))
        for n, ng, k in by_prefix[pre]:
            mix = ', '.join('%s/%s x%d' % (r, f, c)
                            for (r, f), c in sorted(k.items(), key=lambda z: -z[1]))
            print('     %-38s %2d macro  (%s)' % (n, ng, mix))

    # 与 make_mod 实际会改的池对比
    configured = make_mod.female_pools_with_macros()
    print('\n=== 与 make_mod.pool_prefixes = %s 的覆盖对比 ==='
          % (make_mod.RACE['pool_prefixes'],))
    want = {n for n, _g, _k in target if not is_router(n)}
    routers = sorted(n for n, _g, _k in target if is_router(n))
    have = set(configured)
    missing = sorted(want - have)
    extra = sorted(have - want)
    print('  审计认为该覆盖：%d 个（另有 %d 个纯路由池，不需单独加）'
          % (len(want), len(routers)))
    print('  实际会覆盖：    %d 个' % len(have))
    if missing:
        print('\n  !! 漏掉的池（%d 个）——add 形态下这些女性仍是原版：' % len(missing))
        for n in missing:
            print('     %s' % n)
    if extra:
        print('\n  ?? 多收的池（%d 个）：' % len(extra))
        for n in extra:
            print('     %s' % n)
    if not missing and not extra:
        print('\n  覆盖完整，与审计一致 ✓')
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())