# -*- coding: utf-8 -*-
"""组装扩展树：把导出的资产 + 三份 XML 拼成一个可打包的 X4 扩展。

    python tools/make_mod.py --mode add        # 新增一条外观（推荐）
    python tools/make_mod.py --mode replace    # 全量替换

产物形态：

    work/x4_yue_argon_<mode>/
      content.xml
      libraries/charactergroups.xml     add：把两根 macro 加进每个 Argon 女性外观池
      libraries/character_macros.xml    add：两根新 macro；replace：改 122 根的 <models>
      libraries/material_library.xml    我们自己的材质集合
      assets/characters/argon/yueqingshu/{heads,bodies}/*.xac + textures/*.gz

**两套装 = 两根 macro。** 月清疏在这个 mod 里有两种造型（流风回雪 /
雀吟逐霄），它们共用同一张脸和同一个身体，只有发型与衣服不同，所以是两个
独立的外观条目：

* add 形态把两根都放进外观池 —— 阿贡女性里会随机出现这两种造型；
* replace 形态把 122 根 macro **交替**分给 A 和 B，两种造型各约占一半。

两种形态共用同一个扩展 id 与同一套资产路径，**同时只能装一个**。
"""

import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                      # noqa: E402

MOD_ID = 'x4_yueqingshu_mod'
MOD_NAME = 'Yue Qingshu (Sword and Fairy 7)'
MOD_NAME_CN = '月清疏（仙剑奇侠传七）'
MOD_VERSION = '100'
MOD_DATE = '2026-09-29'

#: 这个 mod 的目标种族。阿贡女性共用 `character_argon_female_01`（持有骨架和
#: 全部动画的 component），所以 macro 的 `ref` 才让它被认成"这个种族的一个
#: 女人"，而 `pool_prefixes` 决定哪些外观池会选到它。
RACES = {
    'argon': {
        'race': 'argon',
        'base_macro': 'character_argon_female_cau_base_01_macro',
        'asset_dir': 'argon',
        #: 会刷这个种族女性的**势力**前缀。判据是"谁在用这个池"，而不是
        #: "池里的 macro 叫什么" —— 两者都会骗人：
        #:
        #: * `antigone.*` / `hatikvah.*` 是 Argon 的衍生势力，它们的
        #:   `factiondiplomat.female` 池**直接列** `character_arg_f_diplomat_0{2,3}_macro`
        #:   （有效 race = argon）。只写 `argon.` 会漏掉它们 —— 实测漏 2 个，
        #:   add 形态下这两个势力招的女性外交官仍然是原版；
        #: * 反过来 `terran.*.female` 里也有池选 argon 的 macro（泰伦的外交官），
        #:   但它们属于泰伦，收进来是错的。
        #:
        #: 另外 8 个 `argon.*.female`（`trader` / `passenger` / `prisoner` …）
        #: 是**纯路由池**，只含 `<select character="...">` 指向上面某个池，
        #: 不加它们：往路由器里塞是死重量，而它指向的那个池本来就在列表里。
        #: 这一条由 `female_pools_with_macros()` 的第二个筛子保证。
        'pool_prefixes': ('argon.', 'antigone.', 'hatikvah.'),
        'macro_list': os.path.join(paths.WORK, 'argon_female_macros.json'),
        'label': 'Argon',
        'label_cn': '阿贡（Argon）',
    },
}

#: 发布哪个套装。别名的拼写必须与 `build_yue_mod.ASSET_PATH` 生成的包名一致
#: （`yue_<key>_head` / `_body`），否则组装会在"包不存在"上停下 —— 这一条比
#: 它看起来重要：包名对不上时最容易做的是"顺手改名让脚本跑过去"，而那会把
#: 资产生成成 macro 指不到的路径，实机表现是**没有模型且不报错**。
#:
#: **目前只发布套装 A（流风回雪 / 默认套装 `MAJ02_01`）。**
#:
#: 套装 B（雀吟逐霄）的源定义、材质表、减面比例都还在 `yue_src.py` 里，构建
#: 也仍然支持（`build_all.py --outfits a,b`）—— 只是不进这个列表，所以不进
#: mod。它的长裙盖过大腿，而 X4 的骨架把腿按"没有长裙"的前提摆成外八字，
#: 两者冲突：收腿会把腿的形状改坏（膝盖折角），放阔裙子则会在腰封下缘出现
#: 水平折角。这些问题没有便宜的解法，先把 A 做扎实。
#:
#: 要恢复 B：把下面那行加回来，并跑 `build_all.py --outfits a,b`。
OUTFITS = [
    ('a', '流风回雪', 'yue_a'),
]

RACE = None
MODE = 'add'
MOD = None
ASSET_BASE = None

#: 未打包的游戏库，按加载顺序 —— 与 `find_female_macros.py` 用同一批根目录，
#: 两个工具看到的是同一棵合并后的树。
MACRO_SOURCES = [
    os.path.join(paths.VANILLA, 'libraries', 'character_macros.xml'),
] + sorted(glob.glob(os.path.join(paths.DLC_ALL, '*', 'libraries',
                                  'character_macros.xml')))
POOL_SOURCES = [
    os.path.join(paths.VANILLA, 'libraries', 'charactergroups.xml'),
] + sorted(glob.glob(os.path.join(paths.DLC_ALL, '*', 'libraries',
                                  'charactergroups.xml')))

COMPONENT = 'character_argon_female_01'

#: 每个池名都以它结尾；种族前缀来自 RACES
POOL_SUFFIX = '.female'


def macro_name(key):
    return 'character_argon_female_%s_macro' % dict(
        (k, alias) for k, _n, alias in OUTFITS)[key]


def macro_head(key):
    return '%s/heads/yue_%s_head' % (ASSET_BASE, key)


def macro_body(key):
    return '%s/bodies/yue_%s_body' % (ASSET_BASE, key)


def pool_sources():
    """外观池库，按加载顺序 —— `verify_mod.py` 会重读它们来证明 add 形态的
    补丁恰好覆盖了被发现的那批池。"""
    return POOL_SOURCES


def configure(race, mode):
    global RACE, MODE, MOD, ASSET_BASE
    RACE = RACES[race]
    MODE = mode
    MOD = paths.mod_dir(race, mode)
    ASSET_BASE = ('extensions/%s/assets/characters/%s/yueqingshu'
                  % (MOD_ID, RACE['asset_dir']))
    return MOD


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path


# --------------------------------------------------------------------------
def merge_assets():
    """把四个导出包的内容搬进扩展树。

    导出器的 `write_package()` 把所有 `.xac` 硬编码进 `bodies/`（它没有
    head/torso 分工的概念），所以这里按文件名重新归位。
    """
    dst_root = os.path.join(MOD, 'assets', 'characters',
                            RACE['asset_dir'], 'yueqingshu')
    if os.path.exists(dst_root):
        shutil.rmtree(dst_root)
    os.makedirs(dst_root, exist_ok=True)

    xacs, textures = [], {}
    for key, _label, alias in OUTFITS:
        for half in ('head', 'body'):
            src = os.path.join(paths.pkg_dir({'key': key}),
                               '%s_%s' % (alias, half),
                               'assets', 'characters', 'mycharacters')
            if not os.path.isdir(src):
                raise RuntimeError(
                    '导出的包不存在：%s\n先跑 tools/build_yue_mod.py '
                    '--outfit %s' % (src, key))
            for root, _dirs, files in os.walk(src):
                for fn in files:
                    sp = os.path.join(root, fn)
                    if fn.endswith('.xac'):
                        sub = 'heads' if half == 'head' else 'bodies'
                        dp = os.path.join(dst_root, sub, fn)
                    else:
                        dp = os.path.join(dst_root, 'textures', fn)
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    shutil.copyfile(sp, dp)
                    if fn.endswith('.xac'):
                        xacs.append(dp)
                    else:
                        textures[fn] = dp
    return xacs, textures


def merge_material_library(textures):
    """合并四份生成的材质库，然后修好它们。

    两处修补，都因为转换器的 `build_material_library()` 写的是固定模板、
    并不读 Blender 材质：

    * 每个贴图路径都是字面量 `PUT_YOUR_TEXTURE_PATH_HERE`；
    * **每个材质都拿到 `shader="p1_character" blendmode="NONE"`**，无论材质
      身上带着什么 `x4cc_shader` / `x4cc_blendmode`。前一版项目给丝袜设了
      `ALPHA1` 却装进了 `NONE` —— 黑色丝袜在游戏里从来没有透明过。所以
      shader 和 blend 模式在这里从 manifest 取，那是它们唯一可能的来源。
    """
    manifest = json.load(open(os.path.join(paths.DDS_DIR, 'manifest.json'),
                              encoding='utf-8'))
    collections = {}
    for key, _label, alias in OUTFITS:
        for half in ('head', 'body'):
            p = os.path.join(paths.pkg_dir({'key': key}),
                             '%s_%s' % (alias, half),
                             'libraries', 'material_library.xml')
            if not os.path.exists(p):
                continue
            for m in re.finditer(
                    r'<collection name="([^"]+)">(.*?)</collection>',
                    read(p), re.S):
                name, inner = m.group(1), m.group(2)
                block = collections.setdefault(name, {})
                for mm in re.finditer(
                        r'<material name="([^"]+)".*?</material>', inner, re.S):
                    block[mm.group(1)] = mm.group(0)

    if not collections:
        raise RuntimeError('导出的包里没有材质集合 —— build_yue_mod.py 跑过吗？')

    def fix_path(match):
        return ('value="%s\\textures\\%s"'
                % (ASSET_BASE.replace('/', '\\'), match.group(1)))

    out = ["<?xml version='1.0' encoding='utf-8'?>", '<diff>',
           '  <add sel="/materiallibrary" pos="prepend">']
    total = 0
    unknown = []
    for coll, mats in sorted(collections.items()):
        out.append('    <collection name="%s">' % coll)
        for mname in sorted(mats):
            block = mats[mname]
            entry = manifest.get('%s.%s' % (coll, mname))
            if entry is None:
                unknown.append('%s.%s' % (coll, mname))
            else:
                block = re.sub(r'shader="[^"]*"',
                               'shader="%s"' % entry['shader'], block)
                block = re.sub(r'blendmode="[^"]*"',
                               'blendmode="%s"' % entry['blendmode'], block)
            block = re.sub(r'value="PUT_YOUR_TEXTURE_PATH_HERE\\([^"]+)"',
                           fix_path, block)
            out.append('      ' + block.strip())
            total += 1
        out.append('    </collection>')
    out += ['  </add>', '</diff>', '']
    if unknown:
        raise RuntimeError('这些材质在 manifest 里没有条目：%s —— shader 与 '
                           'blend 模式会静默退回转换器默认值' % unknown)
    write(os.path.join(MOD, 'libraries', 'material_library.xml'),
          '\n'.join(out))
    return total


def merge_library(sources):
    """按加载顺序合并 {名字: 块文本}，用于 `<macro>` / `<character>`。

    **底层是 ElementTree，不是正则。** 原来那版正则有三个毛病，实测同一批库
    它给出 681 个 macro / 429 个池，而 ET 给出 **726 / 134** —— 少算 45 个
    macro，多算 295 个池（把嵌套标签也当成了独立的池）；而且开标签的属性
    （**包括 `ref`**）被 `[^>]*>` 吞掉，任何"沿 ref 链解析有效 race"都失效。
    池的数目多算三倍，则"我覆盖了多少个池"这类结论全是错的。

    返回的仍是文本（调用方在用正则找 `<select ...>`），但这次是从解析过的
    元素序列化出来的，属性齐全。
    """
    import xml.etree.ElementTree as _ET
    from x4lib import load_tree, index
    root = load_tree(sources)
    out = {}
    for group in ('macros', 'characters'):
        for name, el in index(root, group).items():
            out[name] = _ET.tostring(el, encoding='unicode')
    return out


def female_pools_with_macros():
    """每一个可能刷出目标种族女性的外观池。

    两道筛子，都是刻意的：

    * 池名是 `<race>.*` + `.female` —— 势力自己的池。判据是池**名字**，
      不是池里 macro 的种族：阿贡的外交官池选的是 `race="argon"` 的 macro，
      而名字里带 `yaki` 的两根 macro 其实也是 argon；
    * 池必须**直接列出 macro**。只含 `<select character="...">` 链接的池是
      路由器（`argon.trader.female` → `argon.civilian.female`），往它里面加
      是死重量，而它路由到的那个池本来就在这份名单里。

    靠发现而不是写死，这样 DLC 新增的池能自动被覆盖。
    """
    pools = merge_library(POOL_SOURCES)
    out = []
    for name in sorted(pools):
        if not (name.startswith(RACE['pool_prefixes'])
                and name.endswith(POOL_SUFFIX)):
            continue
        if re.search(r'<select\s+macro="', pools[name]):
            out.append(name)
    return out


def write_content():
    race = RACE['label']
    if MODE == 'replace':
        desc = ('Replaces every %s female NPC body with Yue Qingshu from '
                'Sword and Fairy 7, in her two outfits.' % race)
        cdesc = ('把《仙剑奇侠传七》的月清疏%s女性 NPC 的外观：'
                 '全部替换，两套服装交替出现。' % RACE['label_cn'])
    else:
        desc = ('Adds Yue Qingshu from Sword and Fairy 7 to the %s female '
                'NPC appearance pools as two more bodies among the existing '
                'ones, in her two outfits.' % race)
        cdesc = ('把《仙剑奇侠传七》的月清疏加入%s女性 NPC 的外观池：'
                 '两套服装都是随机出现的候选，其余女性保持原样。'
                 % RACE['label_cn'])
    text = '''<?xml version="1.0" encoding="utf-8"?>
<content id="{id}" name="{name}" version="{ver}" date="{date}" save="0"
         description="{desc}">
  <text language="7"  name="{name}" description="{desc}"/>
  <text language="44" name="{name}" description="{desc}"/>
  <text language="86" name="{cn}" description="{cdesc}"/>
</content>
'''.format(id=MOD_ID, name=MOD_NAME, ver=MOD_VERSION, date=MOD_DATE,
           desc=desc, cn=MOD_NAME_CN, cdesc=cdesc)
    return write(os.path.join(MOD, 'content.xml'), text)


def _macro_block(name, key, indent='    '):
    """一根 macro 的 XML；两套装只在 head/torso 的 ref 上不同。"""
    return [
        '%s<macro name="%s" class="npc"' % (indent, name),
        '%s       ref="%s">' % (indent, RACE['base_macro']),
        '%s  <component ref="%s" />' % (indent, COMPONENT),
        '%s  <properties>' % indent,
        '%s    <models>' % indent,
        '%s      <model type="head"  ref="%s" />' % (indent, macro_head(key)),
        '%s      <model type="torso" ref="%s" />' % (indent, macro_body(key)),
        '%s      <model type="props"  ref="none" />' % indent,
        '%s      <model type="props2" ref="none" />' % indent,
        '%s    </models>' % indent,
        '%s  </properties>' % indent,
        '%s</macro>' % indent,
    ]


def _models_block(key, indent='      '):
    return [
        '%s<models>' % indent,
        '%s  <model type="head"  ref="%s" />' % (indent, macro_head(key)),
        '%s  <model type="torso" ref="%s" />' % (indent, macro_body(key)),
        '%s  <model type="props"  ref="none" />' % indent,
        '%s  <model type="props2" ref="none" />' % indent,
        '%s</models>' % indent,
    ]


def write_character_macros():
    """`--mode add`：两根新 macro，一条 `<replace>` 都没有。

    macro 在这里现写而不是继承 base 的 `<models>`，因为它**必须**恰好在那
    一块上不同；其余（`identification` / `eyepositions` / `facemods` /
    `bonemods`）都由 `ref` 继承。

    `props`（随机发型）设成 `none`：月清疏的头发烘在 head 资产里，继承来的
    vanilla 发型会画在它上面。
    """
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<diff>',
        '',
        '  <!-- 月清疏作为两套额外的 %s 女性外观。' % RACE['label'],
        '',
        '       这是 <add>，不是 <replace>：每一根 vanilla macro 都原样保留，',
        '       所以她只是下面那些池里的候选之一。剧情/任务 NPC（不走外观池）',
        '       保持原版外观。',
        '',
        '       ref 到 cau base 是"能被选到"的关键：沿它继承来的 identification',
        '       说 race="%s" female="true"，于是要这个种族女性的池会接受它。 -->'
        % RACE['race'],
        '  <add sel="/macros">',
    ]
    for key, label, alias in OUTFITS:
        lines.append('    <!-- 套装 %s：%s -->' % (key.upper(), label))
        lines += _macro_block(macro_name(key), key)
    lines += [
        '  </add>',
        '',
        '</diff>',
        '',
    ]
    path = write(os.path.join(MOD, 'libraries', 'character_macros.xml'),
                 '\n'.join(lines))
    print('character_macros: +%d macro（%s）, 0 根 vanilla macro 被改动'
          % (len(OUTFITS), ', '.join(macro_name(k) for k, _l, _a in OUTFITS)))
    return path


def load_macro_list(path):
    """读 `find_female_macros.py` 写的两种形状之一的 macro 名单。

    它产出过两种：一串裸名字，以及一个带证据的字典
    （`{'targets': [{'name': ..., 'why': ...}, ...], ...}`）。只认第一种形状
    的话会静默替换**零根** macro：mod 装上了、加载了、什么都没变，而任何地方
    都不报错。两种都接受，且空结果直接硬失败而不是写一个空的 `<diff>`。
    """
    data = json.load(open(path, encoding='utf-8'))
    if isinstance(data, dict):
        entries = data.get('targets')
        if entries is None:
            raise RuntimeError('%s 是个字典但没有 "targets" 键 —— 键是 %s'
                               % (path, sorted(data)))
        names = [e['name'] if isinstance(e, dict) else e for e in entries]
    elif isinstance(data, list):
        names = [e['name'] if isinstance(e, dict) else e for e in data]
    else:
        raise RuntimeError('%s 既不是列表也不是字典' % path)
    if not names:
        raise RuntimeError('%s 里一根 macro 都没有 —— 拒绝写一个空的替换'
                           % path)
    return names


def write_character_macros_replace():
    """`--mode replace`：改掉每一根女性 macro 的 `<models>`。

    读 `find_female_macros.py` 产出的名单，那份名单同时也是"它完整"的证据
    （有效 `race` + `female`，外加从该种族自己的女性池可达的每一根）。
    只动 `<models>`，所以 `identification` / `facemods` / `bonemods` 照旧。

    **两套装交替分配**：第 i 根用 A 还是 B 由 i 的奇偶决定，两种造型各占约
    一半。不按名字或阵营分组，因为那会让某些岗位清一色只出现一套衣服。
    """
    path_in = RACE['macro_list']
    if not os.path.exists(path_in):
        raise RuntimeError('%s 不存在 —— --mode replace 需要这份名单；'
                           '先跑 tools/find_female_macros.py --race %s'
                           % (path_in, RACE['race']))
    macros = load_macro_list(path_in)

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<diff>',
        '',
        '  <!-- 全量替换：每一根 %s 女性 NPC macro 的 <models> 都换成' % RACE['label'],
        '       月清疏，所以这个种族的每个女人都是她 —— 包括外观池够不到的',
        '       剧情/任务 NPC。vanilla macro 没有被删除，只是被重新指向，',
        '       所以 identification/facemods/bonemods 照常工作。',
        '',
        '       逐根改而不是改 base，是因为派生的 macro 会**重写** <models>，',
        '       把它 ref 的 base 遮掉。',
        '',
        '       两套服装交替分配（奇偶），各约占一半。 -->',
        '',
    ]
    counts = {'a': 0, 'b': 0}
    for i, name in enumerate(macros):
        key = OUTFITS[i % len(OUTFITS)][0]
        counts[key] += 1
        lines.append("  <replace sel=\"/macros/macro[@name='%s']"
                     "/properties/models\">" % name)
        lines += _models_block(key)
        lines.append('  </replace>')
        lines.append('')
    # 一根方便用的 macro，让模型也能用 `add_npc` / 调试角色测试按名字刷出来。
    # 池不选它，它纯粹是个把手。
    lines += [
        '  <!-- 没有池会选它：直接刷出她用的把手（两套装各一根）。 -->',
        '  <add sel="/macros">',
    ]
    for key, label, alias in OUTFITS:
        lines.append('    <!-- 套装 %s：%s -->' % (key.upper(), label))
        lines += _macro_block(macro_name(key), key)
    lines += [
        '  </add>',
        '',
        '</diff>',
        '',
    ]
    path = write(os.path.join(MOD, 'libraries', 'character_macros.xml'),
                 '\n'.join(lines))
    print('character_macros: %d 根 macro 被替换（A=%d, B=%d）+ %d 根把手 macro'
          % (len(macros), counts['a'], counts['b'], len(OUTFITS)))
    return path


def write_character_groups(weight=1):
    """把两套装都加进每一个列 macro 的女性池。

    `weight` = 每根 macro 在每个池里出现几次。X4 在池的条目里**均匀**抽取，
    所以一个原本有 3 个候选的池，每根加 1 条 → 每个套装各占 1/5。

    与"改 macro"那条路（`write_character_macros_replace()`，
    `--mode replace` 选中）相对。
    """
    pools = female_pools_with_macros()
    if not pools:
        raise RuntimeError('找不到 %s 女性外观池 —— 库解包到 %s 了吗？'
                           % (RACE['label'], paths.VANILLA))

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<diff>',
        '',
        '  <!-- 月清疏加入外观池。只动**直接列出 macro** 的池：纯粹做',
        '       select-character 路由的池最终会走到这些池之一。',
        '',
        '       一条 = 一份份额。这些池原本有 3 个 vanilla 候选，所以每根加',
        '       一条之后，两套装合计占 2/5；vanilla macro 原封不动，另外',
        '       3/5 保持她们自己的脸、名字与语音。 -->',
        '',
    ]
    for name in pools:
        lines.append("  <add sel=\"/characters/character[@name='%s']\">" % name)
        for key, _label, _alias in OUTFITS:
            for _ in range(weight):
                lines.append('    <select macro="%s" />' % macro_name(key))
        lines.append('  </add>')
        lines.append('')
    lines += ['</diff>', '']
    path = write(os.path.join(MOD, 'libraries', 'charactergroups.xml'),
                 '\n'.join(lines))
    print('charactergroups: %d 个池各加入 %d 根 macro（每根 x%d）'
          % (len(pools), len(OUTFITS), weight))
    for name in pools:
        print('   %s' % name)
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--race', choices=sorted(RACES), default='argon',
                    help='她加入哪个种族的女性（默认 argon；本项目只为它构建）')
    ap.add_argument('--mode', choices=('add', 'replace'), default='add',
                    help='add = 多两个池内候选（默认）；'
                         'replace = 这个种族的每个女人')
    ap.add_argument('--weight', type=int, default=1, metavar='N',
                    help='仅 add 形态：每根 macro 在每个池里列几次；'
                         'vanilla 池原本有 3 个候选，所以 1 = 每套装 20%%'
                         '（默认 1）')
    ap.add_argument('--out', default=None,
                    help='覆盖输出目录（默认 work/x4_yue_<race>_<mode>）')
    args = ap.parse_args()

    configure(args.race, args.mode)
    if args.out:
        globals()['MOD'] = os.path.abspath(args.out)

    # 在碰输出目录**之前**检查 macro 名单：名单缺失曾经让脚本跑到一半失败，
    # 留下一个半成品树，看起来像真产物（有 content.xml 和 assets，但没有
    # macro、没有 .cat）。
    if MODE == 'replace' and not os.path.exists(RACE['macro_list']):
        print('%s 不存在：--mode replace 要重写它点名的名单。\n'
              '用这条命令生成：\n'
              '  python tools/find_female_macros.py --race %s --out %s'
              % (RACE['macro_list'], RACE['race'], RACE['macro_list']),
              file=sys.stderr)
        return 2

    if os.path.exists(MOD):
        shutil.rmtree(MOD)

    xacs, textures = merge_assets()
    print('assets copied : %d xac, %d textures' % (len(xacs), len(textures)))
    for x in sorted(xacs):
        print('   %s (%d KB)' % (os.path.relpath(x, MOD),
                                 os.path.getsize(x) // 1024))

    n = merge_material_library(textures)
    print('materials     : %d merged into one collection' % n)
    write_content()
    if MODE == 'replace':
        write_character_macros_replace()
    else:
        write_character_macros()
        write_character_groups(args.weight)
    print('xml written   : content.xml + macros%s'
          % ('' if MODE == 'replace' else ' + pools'))

    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _d, fs in os.walk(MOD) for f in fs)
    print('mod size      : %.1f MB -> %s' % (total / 1e6, MOD))


if __name__ == '__main__':
    sys.exit(main())