# -*- coding: utf-8 -*-
"""X4 库（`character_macros.xml` / `charactergroups.xml`）的读取与查询。

抽成独立模块的原因有两个，都是踩出来的：

1. **正则解析会骗人。** 原来的 `merge_library` 用
   `<tag\\s+name="([^"]+)"[^>]*>(.*?)</tag>` 抓标签，两个毛病：
   开标签的其余属性（**包括 `ref`**）被 `[^>]*>` 吞掉，于是"沿 ref 链解析有效
   race"永远解析不出东西；而 `[^>]*` 在属性跨行时还会错位。实测同一批库，
   正则给 681 个 macro / 429 个池，ElementTree 给 **726 / 134** —— 前者漏 45 个
   macro、多算 295 个池（把嵌套标签也算成了独立的池）。**池的数目多算三倍**，
   任何"我覆盖了多少个池"的结论就都是错的。
2. **不能互相 import。** `check_xpath` 要读 `make_mod` 的库列表，`make_mod` 又要
   读库 —— 两边直接 import 就是环。库解析放在这里，两边都向下依赖它。

查询函数一律吃 **ElementTree 元素**，不吃字符串：属性是判据的一部分
（`ref` / `macro` / `character` / `race` / `female`），丢掉就没法做对。
"""

import os
import re
import xml.etree.ElementTree as ET

#: 顶层容器的标签名；库文件的根可能是它们，也可能直接就是条目
GROUPS = ('macros', 'characters', 'materiallibrary')


def _upsert(root, group_tag, item):
    """按 name 覆盖式插入：后加载的库赢，与游戏的加载顺序一致。"""
    name = item.get('name')
    if name is None:
        root.append(item)
        return
    group = root.find(group_tag)
    if group is None:
        group = ET.SubElement(root, group_tag)
    for old in group.findall("*[@name='%s']" % name):
        group.remove(old)
    group.append(item)


def load_tree(sources):
    """把若干库文件按加载顺序合并成一棵 `<root>` 树。

    根下只会有 `macros` / `characters` 两个容器，其子节点是合并去重后的条目。

    **必须用 `iter()` 递归找，不能只看顶层。** 两种文件格式同时在用：

        vanilla/libraries/charactergroups.xml   <characters> 直接列池
        <dlc>/libraries/charactergroups.xml     <diff><add sel="/characters">…
                                                （T 文件是 XPath 补丁格式）

    DLC 的池套在 `<add sel="...">` 里。第一版只遍历 `for child in top`，于是
    **DLC 的 99 个 `.female` 池一个都没进来**（134 个池里只剩 vanilla 的 32 个
    `.female`）。这个错误听起来像"池很少"，而不是像"解析失败" —— 而
    "我覆盖了几个池"正是靠这个数。
    """
    root = ET.Element('root')
    for path in sources:
        if not path or not os.path.exists(path):
            continue
        try:
            top = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for tag, group in (('macro', 'macros'), ('character', 'characters')):
            for el in top.iter(tag):
                if el.get('name'):
                    _upsert(root, group, el)
    return root


def index(root, group):
    """`{name: element}`；属性都在元素上，不会被任何正则吃掉。"""
    g = root.find(group)
    return {e.get('name'): e for e in (g if g is not None else [])}


def to_relative(xpath):
    """X4 的 `sel` 从文档根写起（`/macros/...`），而 ElementTree 的 `findall`
    **拒绝在元素上用绝对路径**（报 `cannot use absolute path on element`）。
    我们的合成树根是 `<root>`，其下正好是 `<macros>` / `<characters>`，
    所以去掉开头的 `/` 即可，语义不变。"""
    return (xpath or '').lstrip('/')


def expand_pool(el, pools, seen=None):
    """一个池递归展开后选到的全部 macro。

    `<select character="...">` 是**池指向池**（`argon.trader.female` ->
    `argon.civilian.female`）。不展开就会少算池，而"要不要往路由器里也加一条"
    正取决于展开结果。
    """
    if seen is None:
        seen = set()
    if el is None:
        return set()
    name = el.get('name')
    if name in seen:
        return set()
    seen.add(name)
    out = set()
    for c in el.findall('select'):
        if c.get('macro'):
            out.add(c.get('macro'))
        elif c.get('character'):
            out |= expand_pool(pools.get(c.get('character')), pools, seen)
    return out


def effective_race(el, macros, seen=None):
    """沿 `ref` 链解析出**有效**的 `(race, female)`。

    macro 的 `race` 常常不在自己身上，而只在它 ref 的那个 base macro 的
    `<identification>` 里 —— `character_arg_f_diplomat_02_macro` 就是这样，
    它自己的 body 里一个 `race=` 都没有。
    """
    if seen is None:
        seen = set()
    if el is None:
        return None, None
    name = el.get('name')
    if name in seen:
        return None, None
    seen.add(name)
    ident = el.find('.//identification')
    race = ident.get('race') if ident is not None else None
    fem = ident.get('female') if ident is not None else None
    if race is None:
        ref = el.get('ref')
        if ref:
            r2, f2 = effective_race(macros.get(ref), macros, seen)
            race = race or r2
            fem = fem if fem is not None else f2
    return race, ('true' if fem in (True, 'true') else fem)


def audit_race(race, pools, macros, prefixes):
    """会刷这个种族女性的池，以及其中哪些**真的该加**。

    判据是两条**都要**看，缺一个就错：

    * **池名的势力前缀**（谁在用这个池）—— `antigone.*` / `hatikvah.*` 是
      Argon 的衍生势力，它们的 `factiondiplomat.female` 直接列 argon 的 macro，
      只看 `argon.` 会漏掉；
    * **池里 macro 的有效 race** —— 反过来 `terran.*.female` 里也有池选 argon
      的 macro（泰伦的外交官），按"池里 macro 的种族"筛会把它们错收进来。

    返回 `(direct, routers, macro_names)`：

        direct   直接列 macro 且前缀匹配 -> **必须逐个加**
        routers  只含 `<select character=...>` -> 不加（它指向的池已在 direct 里）
        macro    这些池展开后选到的、有效 (race, female) 的 macro 名
    """
    direct, routers, names = [], [], set()
    for name in sorted(pools):
        el = pools[name]
        if not name or not name.endswith('.female'):
            continue
        got = expand_pool(el, pools)
        if not got:
            continue
        if not any(effective_race(macros.get(m), macros) == (race, 'true')
                   for m in got):
            continue
        names |= set(got)
        if not name.startswith(tuple(prefixes)):
            continue
        if any(c.get('macro') for c in el.findall('select')):
            direct.append(name)
        else:
            routers.append(name)
    return sorted(direct), sorted(routers), sorted(names)