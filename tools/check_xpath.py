# -*- coding: utf-8 -*-
"""把 mod 的 XML diff 真的**套到 vanilla 库上**，看每条 sel 命中没有。

    python tools/check_xpath.py --mode add
    python tools/check_xpath.py --mode replace

`verify_mod.py` 数的是"diff 里有多少个 `<replace>`"，那是**我们写了什么**；
这个脚本回答的是另一个问题：**游戏会不会认**。

X4 的 XML diff 用的是 XPath。写得像模像样但一条都命不中的 `sel` 不会报任何
错 —— mod 正常加载、正常启用、什么都没变。这是"改了 XML 但游戏里没变化"最
常见的那条路（技能 §11.11），而它只有把 diff 真套上去才看得见。

命中判据：
  replace  该 XPath 在合并后的 vanilla 树里必须**恰好**选中一个节点
  add      该 XPath 指向的父节点必须存在（池 / macros 根）

vanilla 树按**加载顺序**合并：基础库在前，DLC 在后，后者覆盖前者 —— 与游戏一致。
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

# Windows 控制台默认 GBK，输出里的 ✓ / 中文注释混排会抛 UnicodeEncodeError，
# 让一个**已经通过**的检查看起来像崩了。显式把 stdout 钉成 UTF-8。
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                      # noqa: E402
import make_mod                                                   # noqa: E402
# 库解析统一放在 x4lib（这里和 make_mod 都要用，直接互相 import 会成环）
from x4lib import load_tree, to_relative                         # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--mode', choices=('add', 'replace'), default='add')
    ap.add_argument('--race', choices=('argon',), default='argon')
    ap.add_argument('--mod', default=None)
    args = ap.parse_args()

    mod = args.mod or paths.mod_dir(args.race, args.mode)
    if not os.path.isdir(mod):
        raise SystemExit('%s 不存在 —— 先构建' % mod)
    make_mod.configure(args.race, args.mode)

    print('== 合并 vanilla 库（%d 个 macro 源）' % len(make_mod.MACRO_SOURCES))
    macros_root = load_tree(make_mod.MACRO_SOURCES)
    pools_root = load_tree(make_mod.POOL_SOURCES)
    n_macros = len(macros_root.find('macros') or [])
    n_pools = len(pools_root.find('characters') or [])
    print('   %d 个 macro，%d 个 character 池' % (n_macros, n_pools))

    macros_xml = os.path.join(mod, 'libraries', 'character_macros.xml')
    text = open(macros_xml, encoding='utf-8').read()
    root = ET.fromstring(text)

    bad = []
    n_hit = 0

    print('\n== character_macros.xml')
    for el in root:
        if el.tag == 'replace':
            sel = to_relative(el.get('sel') or '')
            if not sel:
                bad.append('<replace> 没有 sel')
                continue
            try:
                hits = macros_root.findall(sel)
            except SyntaxError as e:
                bad.append('sel 语法错误 %r：%s' % (sel, e))
                continue
            if len(hits) == 1:
                n_hit += 1
            else:
                bad.append('sel 命中 %d 个（应为 1）：%s' % (len(hits), sel))
        elif el.tag == 'add':
            sel = to_relative(el.get('sel') or '')
            # `<add sel="/macros">` 是往根里加，根一定在
            if sel in ('macros', 'characters'):
                n_hit += 1
                continue
            try:
                hits = macros_root.findall(sel)
            except SyntaxError as e:
                bad.append('sel 语法错误 %r：%s' % (sel, e))
                continue
            if len(hits) == 1:
                n_hit += 1
            else:
                bad.append('add sel 命中 %d 个（应为 1）：%s' % (len(hits), sel))
    print('   %d 条 sel 命中' % n_hit)

    pools_xml = os.path.join(mod, 'libraries', 'charactergroups.xml')
    if os.path.exists(pools_xml):
        print('\n== charactergroups.xml（套在池库上）')
        proot = ET.fromstring(open(pools_xml, encoding='utf-8').read())
        n_pool = 0
        for el in proot:
            if el.tag != 'add':
                continue
            sel = to_relative(el.get('sel') or '')
            try:
                hits = pools_root.findall(sel)
            except SyntaxError as e:
                bad.append('池 sel 语法错误 %r：%s' % (sel, e))
                continue
            if len(hits) == 1:
                n_pool += 1
            else:
                bad.append('池 sel 命中 %d 个（应为 1）：%s' % (len(hits), sel))
        print('   %d 个池 sel 命中' % n_pool)

    print('\n%s' % ('-' * 62))
    if bad:
        print('FAILED：%d 条 sel 不会生效' % len(bad))
        for b in bad[:25]:
            print('   - %s' % b)
        return 1
    print('所有 sel 都能在真实 vanilla 数据上命中 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())