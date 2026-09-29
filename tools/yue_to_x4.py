# -*- coding: utf-8 -*-
"""月清疏的 3ds Max Biped 骨架 -> X4 的 91 骨 Biped。

这是所有来源里**最简单的一次映射**，而这正是重点：Pal7 的角色用的是
3ds Max Biped，与 X4 是同一个骨架家族，所以

    Bip001-L-UpperArm  ->  Bip01 L UpperArm

只是名字的拼写差异（`Bip001-` 对 `Bip01 `，连字符对空格）。手指、脚趾、
脊柱三节、锁骨全都有真正的对应物 —— 不像 MMD 来源要造上百根折叠骨。

仍然需要折叠的是**源比 X4 多出来的那些链**：马尾、飘带、面部表情骨、
扭转骨。它们没有对应物，只能继承它们所挂的那根骨的变换。

坐标：`(x, y, z) -> (x, z, y)`，`det = -1` —— 这是一次**反射**，
所以建网格时必须反转三角形绕序（见 `build_yue_x4.py`）。判据：

    x  月清疏 +X 是 "L" 侧        X4 +X 也是 "L" 侧      -> 同号
    y  月清疏 +Y 是上（脚底 y=0）  X4 +Z 是上             -> z
    z  月清疏 +Z 是前（Toe0 在 +Z）X4 +Y 是前（Toe0 在 +Y）-> y

三个方向都由解剖学定：`Bip001-L-Toe0 - Bip001-L-Foot = (+0.007, -0.090,
+0.113)` 主要落在 +Z，所以 +Z 是前；X4 的 `Bip01 L Toe0 - Bip01 L Foot`
主要落在 +Y，所以 +Y 是前。两边 `L` 骨的 x 同号，所以 x 原样传递。
"""

import numpy as np

#: 有真正对应物的骨。**一个源骨只能占一个目标**（`_assert_unique_targets`），
#: 重复的话谁赢取决于字典遍历顺序，实机表现为"飘带被抬到不该在的高度"。
CORE = {
    'Bip001-Pelvis': 'Bip01 Pelvis',
    'Bip001-Spine': 'Bip01 Spine',
    'Bip001-Spine1': 'Bip01 Spine1',
    'Bip001-Spine2': 'Bip01 Spine2',
    'Bip001-Neck': 'Bip01 Neck',
    'Bip001-Head': 'Bip01 Head',
}

#: 手指：两边都是 Max Biped 的编号 —— `Finger0` 是拇指（它的位置与手掌
#: 明显分离，其余四指沿一条线排开），`FingerN/1/2` 是三节指骨，中节把
#: 数字重复一次（`Finger11` = 食指中节）。实测两边的拇指都是 `Finger0`
#: （月清疏：`Finger0 - Hand` 的 X 分量 -0.006 对其余四指的 +0.038..+0.048；
#: X4：-3.08 对 +0.71..+2.78），所以编号可以直接照搬。
_FINGERS = ['Finger0', 'Finger01', 'Finger02',
            'Finger1', 'Finger11', 'Finger12',
            'Finger2', 'Finger21', 'Finger22',
            'Finger3', 'Finger31', 'Finger32',
            'Finger4', 'Finger41', 'Finger42']

for _side, _x4s in (('L', 'L'), ('R', 'R')):
    CORE['Bip001-%s-Clavicle' % _side] = 'Bip01 %s Clavicle' % _x4s
    CORE['Bip001-%s-UpperArm' % _side] = 'Bip01 %s UpperArm' % _x4s
    CORE['Bip001-%s-Forearm' % _side] = 'Bip01 %s Forearm' % _x4s
    CORE['Bip001-%s-Hand' % _side] = 'Bip01 %s Hand' % _x4s
    CORE['Bip001-%s-Thigh' % _side] = 'Bip01 %s Thigh' % _x4s
    CORE['Bip001-%s-Calf' % _side] = 'Bip01 %s Calf' % _x4s
    CORE['Bip001-%s-Foot' % _side] = 'Bip01 %s Foot' % _x4s
    CORE['Bip001-%s-Toe0' % _side] = 'Bip01 %s Toe0' % _x4s
    for _f in _FINGERS:
        CORE['Bip001-%s-%s' % (_side, _f)] = 'Bip01 %s %s' % (_x4s, _f)

#: 全局刚体拟合用的骨对：明确、左右对称、分布在全身，使拟合在三个轴上
#: 都良态。脚趾不参与（它与脚踝的距离太短，噪声大）。
ALIGN_PAIRS = [
    ('Bip001-Pelvis', 'Bip01 Pelvis'),
    ('Bip001-Spine', 'Bip01 Spine'),
    ('Bip001-Spine1', 'Bip01 Spine1'),
    ('Bip001-Spine2', 'Bip01 Spine2'),
    ('Bip001-Neck', 'Bip01 Neck'),
    ('Bip001-Head', 'Bip01 Head'),
    ('Bip001-L-Clavicle', 'Bip01 L Clavicle'),
    ('Bip001-R-Clavicle', 'Bip01 R Clavicle'),
    ('Bip001-L-UpperArm', 'Bip01 L UpperArm'),
    ('Bip001-R-UpperArm', 'Bip01 R UpperArm'),
    ('Bip001-L-Forearm', 'Bip01 L Forearm'),
    ('Bip001-R-Forearm', 'Bip01 R Forearm'),
    ('Bip001-L-Hand', 'Bip01 L Hand'),
    ('Bip001-R-Hand', 'Bip01 R Hand'),
    ('Bip001-L-Thigh', 'Bip01 L Thigh'),
    ('Bip001-R-Thigh', 'Bip01 R Thigh'),
    ('Bip001-L-Calf', 'Bip01 L Calf'),
    ('Bip001-R-Calf', 'Bip01 R Calf'),
    ('Bip001-L-Foot', 'Bip01 L Foot'),
    ('Bip001-R-Foot', 'Bip01 R Foot'),
]

#: X4 用 look-at 控制器驱动这两根；靠近它们的源几何会被改绑到头，
#: 这样一次注视变化不能把眼球甩出眼窝。
#:
#: 月清疏的 `Eyejoint_L/R` **故意不映射到它们**：那两根是眼球的旋转中心，
#: 一旦交给 look-at，大角度注视会把整个眼球转出眼眶（前一版项目的实测
#: 症状是"眼球偶尔乱跑不跟头"）。让它们随面部链折叠到 `Bip01 Head`，
#: 眼球就永远待在眼窝里 —— 代价是不再有独立的注视，对 NPC 来说不可见。
EYE_CONTROLLERS = {'left_eye_dummy', 'right_eye_dummy'}
HEAD_BONE = 'Bip01 Head'

#: 只平移、不旋转：X4 的脚链比源的陡，按方向对齐会把脚翘起来、脚跟悬空。
NO_ROTATE_BONES = {'Bip01 L Foot', 'Bip01 R Foot',
                   'Bip01 L Toe0', 'Bip01 R Toe0'}

#: 侧面判据用的前缀。源骨名是 `Bip001-L-*` / `Bip001-R-*`。
SIDE_TOKENS = (('-L-', 'L'), ('-R-', 'R'))


def yue_to_blender(p):
    """月清疏 (x, up, forward) 米 -> Blender/X4 轴序，同样单位。

    这是一次交换两轴的**反射**（det = -1），所以三角形绕序必须反转。
    见模块开头的推导。
    """
    return np.array([p[0], p[2], p[1]], float)


def side_of(name):
    """'L' / 'R' / None。

    先看名字里的 `-L-` / `-R-`；名字里没有的（`Bone001`、`LingDang`、
    `LeftArm_Refine`）**沿父链上溯**，因为 Max Biped 的附属骨常常不带侧向前缀
    却挂在某一侧的手臂下 —— 实测 `Bone001` 挂在 `Bip001-R-UpperArm` 下、
    `Bone001(mirrored)` 挂在 `Bip001-L-UpperArm` 下。判错过一次就会让袖带
    去继承对面手臂的变换。

    注意挂在躯干下的飘带（`Bip001-Xtra10` 与其镜像 `Bip001-Xtra10Opp`）
    上溯到 `Bip001-Spine` 就停了，正确地返回 None：它们本来就该跟着躯干。
    """
    for tok, side in SIDE_TOKENS:
        if tok in name:
            return side
    # `Bone185` 这类名字毫无线索，但父链会说明它挂在哪
    return _SIDE_CACHE.get(name)


def _build_side_cache(parent):
    """父链推断，一次算完。依赖 `build_bone_map` 拿到的父子表。"""
    global _SIDE_CACHE
    _SIDE_CACHE = {}
    resolving = set()

    def resolve(n):
        if n in _SIDE_CACHE:
            return _SIDE_CACHE[n]
        if n in resolving:                       # 环，不该出现
            return None
        resolving.add(n)
        out = None
        for tok, side in SIDE_TOKENS:
            if tok in n:
                out = side
                break
        if out is None:
            p = parent.get(n)
            if p:
                out = resolve(p)
        resolving.discard(n)
        _SIDE_CACHE[n] = out
        return out

    for n in parent:
        resolve(n)
    return _SIDE_CACHE


_SIDE_CACHE = {}


def is_direct_bone(name):
    return name in CORE


def check_core(bones):
    """每个 CORE 源名都必须在骨架里，且不能有两个共用一个目标。"""
    have = {b['name'] for b in bones}
    missing = sorted(set(CORE) - have)
    if missing:
        raise SystemExit('!! 骨架里缺这些 CORE 骨：%s' % missing)
    _assert_unique_targets()
    return True


def _assert_unique_targets():
    seen = {}
    for src, dst in CORE.items():
        if dst in seen:
            raise SystemExit(
                '!! 两个源骨都映射到 %s：%s 与 %s。只有一条 (src, dst, R) '
                '记录能活下来，而活下来的是哪条由字典顺序决定 —— 让优先级 '
                '低的那个折叠到父骨上去。' % (dst, seen[dst], src))
        seen[dst] = src


def build_bone_map(bones):
    """{源骨 -> x4 骨}，**每一根**骨都有，包括飘带链。

    直接骨按名字映射。其余都是**折叠骨**：它们在 X4 里没有对应物，于是
    折叠到**它们所在链的根**所映射的目标上，而不是按自己位置找最近的骨。

    为什么按链根：月清疏的马尾 5 节挂在 `Bip001-Head` 下、面部几十根表情骨
    挂在 `Face` 下、袖带 4 节挂在 `Bip001-L/R-UpperArm` 下、裙摆/飘带挂在
    `Bip001-Spine*` 下。按位置找最近骨的话，一条长链的末节会落到离它最近的
    随便哪根核心骨上 —— 马尾梢在 y=1.10 会落到大腿上，每走一步都跟着甩。
    链挂在谁身上，就由谁决定。
    """
    parent = {b['name']: (bones[b['parent']]['name'] if b['parent'] >= 0
                          else None) for b in bones}
    _build_side_cache(parent)

    out = {}
    for b in bones:
        if b['name'] in CORE:
            out[b['name']] = CORE[b['name']]

    root_cache = {}

    def chain_root(n):
        if n in root_cache:
            return root_cache[n]
        seen, cur = [], n
        while cur is not None and cur not in CORE:
            seen.append(cur)
            cur = parent.get(cur)
        root = cur if cur is not None else n
        for s in seen:
            root_cache[s] = root
        root_cache.setdefault(n, root)
        return root

    for b in bones:
        n = b['name']
        if n in out:
            continue
        out[n] = CORE.get(chain_root(n))
    return out


def report_map(bones, bone_map, x4_names, weighted):
    direct = [b for b in weighted if b in CORE]
    folded = [b for b in weighted if b not in CORE and bone_map.get(b)]
    lost = [b for b in weighted
            if not bone_map.get(b) or bone_map[b] not in x4_names]
    print('  骨映射：%d 根带权骨 -> %d 直接 + %d 折叠 + %d 未映射'
          % (len(weighted), len(direct), len(folded), len(lost)))
    if lost:
        print('   !! 未映射：%s' % sorted(lost)[:20])
    return lost


class YueAdapter:
    """`retarget_core` 需要知道的关于 Pal7 骨架的一切。"""

    name = 'pal7'
    align_pairs = ALIGN_PAIRS
    eye_controllers = EYE_CONTROLLERS
    head_bone = HEAD_BONE
    no_rotate_bones = NO_ROTATE_BONES

    #: 手指**独立驱动**，不绑手掌：这个来源的手指标号与 X4 完全对应，
    #: 而且绑定姿态都是 A-pose 的自然张开手。MMD 来源要靠"绑手掌"回避
    #: 虎口撕裂，是因为它的手指骨位置与 X4 差得远；这里实测差不到 1 cm。
    fingers_bind_to_palm = False

    #: 源骨链里有**同位骨**（`Bip001-L-ForeTwist` 与 `Bip001-L-Forearm`
    #: 位置完全相同，`Bip001-LCalfTwist` 与 `Bip001-L-Calf` 同）。它们映射到
    #: 同一个 X4 骨，所以要沿主链继续往下找第一个有独立目标的子骨来定轴向，
    #: 否则轴向会退回父方向，把整条手臂转 90 度。
    walk_axis_chain = True

    eye_pairs = ()

    #: 每根 X4 腿骨保留多少**横向**位移（纵向不动，所以腿长与触地不变）。
    #:
    #: 两套骨架对"腿朝哪边"的看法不同，不只是站姿宽窄：
    #:
    #:            源（拟合后）    X4 绑定
    #:     髋      +8.5 cm   ->   +11.61
    #:     膝      +8.7       ->   +14.81
    #:     踝      +8.8       ->   +17.70
    #:
    #: 也就是说源腿**几乎是垂直的**（踝间距 17.6 cm），而 X4 的绑定姿态向
    #: 外撇（踝间距 35.4 cm）。原样对齐会把整条腿甩到裙子外面。
    #:
    #: 但折扣**不能沿链递减**：那是"猫步"的根因（前一版项目实测 0.60/0.30/0.20
    #: 把踝间距压到 16.4 cm，走路时两只脚落在一条线上）。逐级递减不只是把腿
    #: 平移，它把骨链**折弯**，关节落进它驱动的几何内侧，绑定姿态看不出来，
    #: 动画一播就现形。
    #:
    #: 判据有两条：**骨链横向单调外撇**（大腿 < 小腿 < 踝）且**两脚间距
    #: 接近 vanilla 的 35.4 cm**。按下面的取值，踝落在 8.8 + (17.70-8.8)*0.95
    #: = 17.26 cm，即两脚间距 34.5 cm。用 `tools/measure_legs.py` 复核。
    LATERAL_DAMP = {
        'Bip01 L Thigh': 0.60, 'Bip01 R Thigh': 0.60,
        'Bip01 L Calf': 0.85, 'Bip01 R Calf': 0.85,
        'Bip01 L Foot': 0.95, 'Bip01 R Foot': 0.95,
        'Bip01 L Toe0': 0.95, 'Bip01 R Toe0': 0.95,
    }

    def adjust_target(self, x4_bone, src_pos, dst_pos):
        k = self.LATERAL_DAMP.get(x4_bone)
        if k is None:
            return dst_pos
        out = np.array(dst_pos, float)
        out[0] = src_pos[0] + (dst_pos[0] - src_pos[0]) * k
        return out

    def __init__(self, bone_map):
        self.bone_map = bone_map

    def to_blender(self, p):
        return yue_to_blender(p)

    def map_bone(self, name):
        return self.bone_map.get(name)

    def is_direct_bone(self, name):
        return name in CORE

    def side_of(self, name):
        return side_of(name)


#: 头部链在 X4 里的长度与源不同：X4 的 `Bip01 Head` 在 `Bip01 Neck` 上方
#: 7.8 cm，源是 5.2 cm（1.477 - 1.425）。`retarget_core._harmonise_head_neck`
#: 会给两根骨一个共享位移，把差异从视觉上抹平。
#: 颈部权重修正的区间与阈值：源的颈部中下段被画成混合权重，重定向后
#: `Bip01 Spine2` 与 `Bip01 Neck` 各自带着不同的拟合旋转，混合会在脖子中段
#: 扫出一道可见的折角。**必须在 `transform()` 之前**改源权重 —— 顶点位置是
#: `transform()` 内部用权重算出来的，事后改成品权重对几何零影响。
NECK_FIX_Z = (128.0, 145.0)
NECK_FIX_X = 6.0