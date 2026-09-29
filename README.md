# 月清疏（仙剑奇侠传七）→ X4: Foundations **Argon 女性** NPC

把《仙剑奇侠传七》的**月清疏**（UE4.25 / 3ds Max Biped，两套装共 191 / 239 骨）
移植成《X4：基石》里的 **Argon 女性** NPC 外观，替换头部与躯干网格。

```bash
python tools/build_all.py --mode add        # 一条命令：重定向 → 贴图 → 导出 → 组装 → 打包
python tools/verify_mod.py  --mode add      # 发版前自检
```

> 源码与文档在本仓库；成品 mod 见 `work/dist/`（`tools/build_release.py` 生成）。

## 两种形态（装之前二选一）

| 形态 | 你会得到什么 | 什么时候用 |
|---|---|---|
| **仅增加** `--mode add` | 新增两条 macro（`…_yue_a_macro` / `…_yue_b_macro`），并往 **6 个 Argon 女性外观池**各加两条 `<select>`。**原版 macro 一条不动**，她只是随机出现的其中一种；其余女性保持自己的脸/名字/语音。**剧情/任务 NPC 不走外观池，保持原版。** | 正式游玩、发布 |
| **全量替换** `--mode replace` | 把 **122 个** Argon 女性 macro 的 `<models>` 逐个改写成月清疏，含不走池的剧情 NPC —— 所有 Argon 女性都是她。**两套服装交替分配**（A=61 / B=61） | 想看模型出现在所有地方 / 调试 |

两种形态共用同一个扩展 id（`x4_yueqingshu_mod`）与同一套资产路径，**同时只能装一个**。
发布包已分开：

```
x4_yueqingshu_argon_add_v1.0.zip       ← 仅增加（推荐）
x4_yueqingshu_argon_replace_v1.0.zip   ← 全量替换
```

解压到 `X4 Foundations/extensions/` 下即可（压缩包里已经是 `x4_yueqingshu_mod/` 一层），
然后在游戏的 `扩展 / Extensions` 菜单里启用。

**存档安全**：`content.xml` 带 `save="0"`，mod 不往存档里写任何东西；两种形态都只改
`<models>` 与外观池的 `<select>`，**不新增、不删除、不改名**任何 macro 或 component，
也不碰 NPC 的 `identification`（名字/背景/职称/语音）。卸掉 mod 后存档照常加载，
NPC 恢复原版外观。

## 两套服装怎么共存

月清疏在这个 mod 里有两个造型 —— **流风回雪**（默认套装 `MAJ02_01`）与
**雀吟逐霄**（第二套装 `MAJ02_02`）。它们**共用同一张脸和同一个身体**（head / eye /
mouth / 眉 / 泪线这两次导出的顶点数逐位相同），只有**发型与衣服**不同，所以是两条
独立的外观条目、两套独立资产：

* `add` 形态把两条都放进外观池 —— 阿贡女性里两种造型随机出现；
* `replace` 形态把 122 条 macro 交替分给 A 和 B，各约占一半（不按名字或阵营分组，
  否则某些岗位会清一色只出现一套衣服）。

## 管线做了什么

```
YueQingShu_MAJ02_0{1,2}.glb（含骨骼蒙皮）
      →  逐骨绑定姿态转移（191/239 骨 → 91 骨）  →  yue_<key>_stage1.blend
      →  X4CharacterConverter 导出               →  .xac + DDS + xml（每套装 2 个资产）
      →  XRCatTool 打包                          →  ext_01.cat / ext_01.dat
```

核心是第一步：**X4 的 NPC 替换是「换网格、留骨架」**。
`character_components.xml` 里的共享 component `character_argon_female_01`
拥有骨骼与 1100+ 条动画，macro 只挑 head/torso/props 三个**网格**槽位 ——
所以替换物必须带上**逐字节相同的 91 骨骼 Biped 骨架**。本 mod 的 4 个 `.xac`
都是 91/91 骨记录与**各自的宿主**逐字节相同（`verify_mod.py` 会逐个验证）。

> 注意"各自的宿主"：vanilla 的 head 资产与 body 资产**骨架序列化并不相同**
> （`jacket` 与 `sweater` 两个 body 资产之间只有 21/91 相同）。替换哪个资产，
> 就要和**那个**资产比 —— 拿一个统一基准去比会误报。

| 脚本 | 作用 |
|---|---|
| `tools/paths.py` | 所有路径解析（项目相对 + 环境变量覆盖，无硬编码盘符） |
| `tools/glb.py` | 最小 glTF-binary 读取器（够量源模型，不实现用不到的部分） |
| `tools/yue_src.py` | 源材质定义、head/body 分区、减面比例、不可见面判据 |
| `tools/yue_to_x4.py` | 骨骼映射表（CORE / 折叠规则 / 横向阻尼 / 坐标与 UV 约定） |
| `tools/build_yue_x4.py` | 阶段 1：Blender 里重定向网格、减面、分 head/torso |
| `tools/prepare_textures_yue.py` | 源 `_D`/`_N`/`_ORM` → DDS（BC1/BC5/BC4）+ 材质 manifest |
| `tools/build_yue_mod.py` | 阶段 2：填进 vanilla 宿主的网格槽、导出 `.xac` |
| `tools/make_mod.py` | 组装 mod 树（`--mode add` / `--mode replace`，两条 macro） |
| `tools/find_female_macros.py` | 枚举「有效 race=argon 且 female」的 macro → `work/argon_female_macros.json` |
| `tools/verify_mod.py` | 发版自检：树 / 材质 / **骨架逐字节** / XML 语义 |
| `tools/check_xpath.py` | 把 diff 真套到 vanilla 库上，验证**每条 sel 都命中**（"改了没变化"的头号原因） |
| `tools/render_check.py` | 离线出图（正/侧/背/头，**开背面剔除**，绕序错了会一眼看穿） |
| `tools/measure_x4.py` | 量 vanilla 骨架的坐标约定、绑定姿态、眼位 |
| `tools/diag_leg_clip.py` | 按高度分层量"腿穿出裙子"多少厘米（判据是腿外缘 vs 裙侧壁外缘） |
| `tools/build_release.py` | 打成发布 zip |
| `tools/deploy.py` | 装进 / 卸出游戏（**不在构建的默认步骤里**） |

## 复现

```bash
python   tools/find_female_macros.py --race argon          # 生成 122 个 macro 清单（replace 用）
python   tools/build_all.py --mode add                     # 全量重建（add 形态）
python   tools/build_all.py --mode replace                 # 全量重建（replace 形态）
python   tools/verify_mod.py --mode add                    # 自检，参数必须与产物一致
python   tools/check_xpath.py --mode add                   # 验证 XML 的 sel 真能命中
python   tools/build_release.py --version 1.0              # 发布 zip
python   tools/build_all.py --mode add --deploy            # 可选：构建并安装进游戏
python   tools/deploy.py --mode none                       # 卸载
```

`build_all.py` **默认只构建、不安装**：它会往游戏的 `extensions/` 写目录，这种事
不该由"构建"顺手做掉。两个形态共用一个扩展 id，装另一个就等于替换掉当前这个。

环境依赖：Blender 5.2、系统 Python（Pillow / numpy）、
[X Tools](https://www.egosoft.com/download/x4/bonus_en.php)（`XRCatTool.exe`）、
以及工作区里的 `x4-anim-preview`（离线动作预览器）。
`tools/paths.py` 会自己探测它们，找不到时用环境变量覆盖
（`YUE_SRC` / `X4_GAME` / `XRCAT_TOOL` / `X4_WORKSPACE`）。

## 已验证

| 项 | 结果 |
|---|---|
| 骨架 | 4 个 `.xac` 各 **91/91** bind 记录与各自宿主逐字节相同 |
| 骨骼映射 | A：178 带权骨 → 52 直接 + 折叠 + 1 未映射（根骨 `Bip001`，无权重）；B：158 → 52 + 105 |
| 坐标手性 | `(x,y,z) → (x,z,y)`，`det(R) = +1.0000`（Kabsch），映射本身 det = −1 → **反转绕序** |
| 全局拟合 | scale = **108.35 cm/unit**（把 1.676 m 的源模型放大到 X4 女性体型，成品高 180.5 cm） |
| UV | 存 `1 − v_src`；与提取仓库自己的 `.blend` 逐值核对（`v[−0.0098, 1.0000]` 对 `[−0.0098, 0.9988]`） |
| 顶点预算 | A：head 19166 vs 5002（**3.83×**）；torso 15781 vs 4600（**3.43×**）<br>B：head 16034 vs 5002（**3.21×**）；torso 16977 vs 4600（**3.69×**），上限 6× |
| 贴图 | 25 个材质 / 37 个 DDS（15.6 MB 发布包），全部在 `ext_01.cat` 内可解析 |
| 自检 | `verify_mod.py` 两种形态全过（**0 警告**） |
| XML 生效性 | `check_xpath.py`：把 diff 套到合并后的 vanilla 库（726 macro / 134 池）上，add 形态 7 条 sel、replace 形态 123 条 sel **全部命中** |

### 动画预览（`x4-anim-preview/tools/ai_check.py`）

| 指标 | 套装 A | 套装 B | 甘雨（已发布） | vanilla |
|---|---|---|---|---|
| 关节撕裂 | 1.40× | **1.27×** | 1.87× | 1.00× |
| 两脚间距 | 0.89–0.91× | **0.93×** | 0.87–0.90× | 1.00× |
| 骨架 / 绕序 / 顶点爆炸 | 无 | 无 | 无 | — |
| 结论 | WARN（撕裂一项） | **OK（0 告警）** | — | — |

指标是**比值**；逐张对比图（`report_outfit_a/shots/`、`report_outfit_b/shots/`）已确认
无破面、无错位、贴图正确。**两项都不差于已发布的前作。**

## 已知问题

1. **关节处的残余撕裂**（肩、肘、脚踝），套装 A 为 vanilla 的 1.40×，略高于预览器
   1.35× 的保守阈值。根因是源骨架与 X4 骨架的脊柱/腿长比例不同（源 191 骨对
   X4 91 骨），"给骨链共享位移"的修法会引入更明显的弯折，已在更早的项目里试过并
   回退。绝对量 9.6 cm 对 vanilla 的 6.8 cm，**远好于前作的 187% / 203%**。
2. **套装 B 的腿部几何被横向收窄到 55%**（`yue_src.LEG_SHRINK`）。B 的长裙
   盖过大腿，而修"猫步"的横向阻尼把腿推到了 vanilla 的站姿宽度上，大腿于是
   从裙子两侧顶出来（`tools/diag_leg_clip.py` 实测 z=53–77 段最多 **5.19 cm**）。
   收窄的是**几何**、绕它自己的骨轴，**骨骼一动不动**，所以动画照旧、只有剪影
   变瘦；残余穿模降到 1.6 cm（单层，邻层 ≤0.5 cm）。**套装 A 保持 1.00 不动** ——
   它的短裙到大腿中部，腿在裙外本来就是裸露的，没有这个问题。
3. **马尾与飘带是刚体**：它们跟头/躯干一起动，不会自己摆。X4 的 Biped 骨架里
   没有发丝链或布料链（只有 91 根），源的 `Ponytail1–14`、`Xtra01–12`、
   `Bone001–187` 只能折叠到链的根所对应的骨上。
4. **头发没有 alpha 测试**（睫毛走的是 `ALPHA8`，见下）：X4 的 `blendmode` 是**单值**，"双面"与
   "alpha 测试"不能兼得。这里选了 `TWOSIDED`（否则发片从背面看会整片消失），
   所以贴图 alpha 不参与剔除，剪影完全由几何承载 —— 这也是头发减面到 0.20 之后
   仍然站得住的原因。
5. **三件"不该被看见"的层被丢弃**：`M_ProxyHide`（2405 顶点，Pal7 自己的
   "别画这个"标记，留着会在真皮肤外面再套一层不透明的壳）、`Eye_Occlusion`
   （252 顶点）与 `TearLine`（312 顶点）。后两件是同一件事的 alpha 版本 ——
   提取仓库的 `.blend` 把它们的 Blender alpha 设成 **0.0** 和 **0.15**，X4 的
   `blendmode` 是单值，"淡"对一件同时必须双面的几何不可表达，丢弃等价。
   第一版没丢，渲染出来是两个眼睛上方各一块米色斑 —— 见
   `docs/成品预览_两套装.png` 的第一版。
6. **睫毛走 `ALPHA8`**（唯一一件不做双面的）：`eyelash_new_Inst` 是 9751 顶点、
   12074 面的睫毛卡片，源的 `.blend` 给它 alpha=0.35。不淡化的实机效果是眼睛上
   一大块深色（第一版渲染出来的"浓重眼线"）。追求双面而放弃这个淡化，代价比
   收益大 —— 睫毛贴在眼球上，极少被从背面看到。

## 版权

模型、贴图等游戏资产版权归 **软星科技（北京）有限公司 / 大宇资讯**所有。
本仓库**只包含工具与文档**，不含模型、贴图或游戏资产。仅供个人学习研究使用，
请勿再分发或商用。