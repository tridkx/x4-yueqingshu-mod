# 月清疏（仙剑奇侠传七）→ X4: Foundations **Argon 女性** NPC

> 源码：<https://github.com/tridkx/x4-yueqingshu-mod> · 成品 mod 见 [Releases](https://github.com/tridkx/x4-yueqingshu-mod/releases)
> —— 与作者另外几个 X4 项目同源：[x4-character-retarget](https://github.com/tridkx/x4-character-retarget)（管线与文档）、
> [x4-ganyu-mod](https://github.com/tridkx/x4-ganyu-mod)、[x4-lumine-mod](https://github.com/tridkx/x4-lumine-mod)、
> [x4-boru-mod](https://github.com/tridkx/x4-boru-mod)。

把《仙剑奇侠传七》的**月清疏**（UE4.25 / 3ds Max Biped，191 骨）移植成
《X4：基石》里的 **Argon 女性** NPC 外观，替换头部与躯干网格。

**服装：默认套装（流风回雪 `MAJ02_01`）。** 第二套装（雀吟逐霄）的源定义与
构建支持都还在仓库里（`yue_src.MATS['b']`、`build_all.py --outfits a,b`），
只是不进 mod —— 原因见第 4 节。

```bash
python tools/build_all.py --mode add        # 一条命令：重定向 → 贴图 → 导出 → 组装 → 打包
python tools/verify_mod.py  --mode add      # 发版前自检
python tools/check_xpath.py --mode add      # 验证 XML 的 sel 真能命中 vanilla 数据
```

## 1. 两种形态（装之前二选一）

| 形态 | 你会得到什么 | 什么时候用 |
|---|---|---|
| **仅增加** `--mode add` | 新增一条 macro `character_argon_female_yue_a_macro`，并往 **6 个 Argon 女性外观池**各加一条 `<select>`。**原版 macro 一条不动**，她只是随机出现的其中一种；其余女性保持自己的脸/名字/语音。**剧情/任务 NPC 不走外观池，保持原版。** | 正式游玩、发布 |
| **全量替换** `--mode replace` | 把 **122 个** Argon 女性 macro 的 `<models>` 逐个改写成月清疏，含不走池的剧情 NPC —— 所有 Argon 女性都是她 | 想看模型出现在所有地方 / 调试 |

两种形态共用同一个扩展 id（`x4_yueqingshu_mod`）与同一套资产路径，**同时只能装一个**。
发布包已分开：

```
x4_yueqingshu_argon_add_v1.1.zip       ← 仅增加（推荐）
x4_yueqingshu_argon_replace_v1.1.zip   ← 全量替换
```

解压到 `X4 Foundations/extensions/` 下即可（压缩包里已经是 `x4_yueqingshu_mod/` 一层），
然后在游戏的 `扩展 / Extensions` 菜单里启用。

**存档安全**：`content.xml` 带 `save="0"`，mod 不往存档里写任何东西；两种形态都只改
`<models>` 与外观池的 `<select>`，**不新增、不删除、不改名**任何 macro 或 component，
也不碰 NPC 的 `identification`（名字/背景/职称/语音）。卸掉 mod 后存档照常加载，
NPC 恢复原版外观。

## 2. 管线做了什么

```
YueQingShu_MAJ02_01.glb（含骨骼蒙皮）
      →  逐骨绑定姿态转移（191 骨 → 91 骨）      →  yue_a_stage1.blend
      →  X4CharacterConverter 导出               →  .xac + DDS + xml（head / body 两个资产）
      →  XRCatTool 打包                          →  ext_01.cat / ext_01.dat
```

核心是第一步：**X4 的 NPC 替换是「换网格、留骨架」**。
`character_components.xml` 里的共享 component `character_argon_female_01`
拥有骨骼与 1100+ 条动画，macro 只挑 head/torso/props 三个**网格**槽位 ——
所以替换物必须带上**逐字节相同的 91 骨骼 Biped 骨架**。本 mod 的两个 `.xac`
都是 91/91 骨记录与**各自的宿主**逐字节相同（`verify_mod.py` 会逐个验证）。

> 注意“各自的宿主”：vanilla 的 head 资产、`jacket` body 资产与 `sweater` body
> 资产**三者的骨架序列化并不相同**（jacket 与 sweater 之间只有 21/91 相同）。
> 替换哪个资产，就要和**那个**资产比 —— 拿一个统一基准去比会误报。

| 脚本 | 作用 |
|---|---|
| `tools/paths.py` | 所有路径解析（项目相对 + 环境变量覆盖，无硬编码盘符） |
| `tools/glb.py` | 最小 glTF-binary 读取器（够量源模型，不实现用不到的部分） |
| `tools/yue_src.py` | 源材质定义、head/body 分区、减面比例、腿部/裙子几何修正 |
| `tools/yue_to_x4.py` | 骨骼映射表（CORE / 折叠规则 / 横向阻尼 / 坐标与 UV 约定） |
| `tools/build_yue_x4.py` | 阶段 1：Blender 里重定向网格、减面、分 head/torso |
| `tools/prepare_textures_yue.py` | 源 `_D`/`_N`/`_ORM` → DDS（BC1/BC5/BC4）+ 材质 manifest |
| `tools/build_yue_mod.py` | 阶段 2：填进 vanilla 宿主的网格槽、导出 `.xac` |
| `tools/make_mod.py` | 组装 mod 树（`--mode add` / `--mode replace`） |
| `tools/find_female_macros.py` | 枚举「有效 race=argon 且 female」的 macro → `work/argon_female_macros.json` |
| `tools/verify_mod.py` | 发版自检：树 / 材质 / **骨架逐字节** / XML 语义 |
| `tools/check_xpath.py` | 把 diff 真套到 vanilla 库上，验证**每条 sel 都命中**（“改了没变化”的头号原因） |
| `tools/render_check.py` | 离线出图（正/侧/背/头，**开背面剔除**；`--zoom`/`--elev` 查局部） |
| `tools/measure_x4.py` | 量 vanilla 骨架的坐标约定、绑定姿态、眼位 |
| `tools/diag_leg_axis.py` | 量腿的**骨链倾角**，判断腿是不是一条直边（折角 = 相邻两段倾角之差） |
| `tools/diag_leg_clip.py` | 按高度分层量“腿穿出裙子”多少厘米 |
| `tools/build_release.py` | 打成发布 zip |
| `tools/deploy.py` | 装进 / 卸出游戏（**不在构建的默认步骤里**） |

## 3. 复现

```bash
python   tools/find_female_macros.py --race argon          # 生成 122 个 macro 清单（replace 用）
python   tools/build_all.py --mode add                     # 全量重建（add 形态）
python   tools/build_all.py --mode replace                 # 全量重建（replace 形态）
python   tools/verify_mod.py --mode add                    # 自检，参数必须与产物一致
python   tools/check_xpath.py --mode add                   # 验证 XML 的 sel 真能命中
python   tools/build_release.py --version 1.1              # 发布 zip
python   tools/build_all.py --mode add --deploy            # 可选：构建并安装进游戏
python   tools/deploy.py --mode none                       # 卸载
```

`build_all.py` **默认只构建、不安装**：它会往游戏的 `extensions/` 写目录，这种事
不该由“构建”顺手做掉。两个形态共用一个扩展 id，装另一个就等于替换掉当前这个。

环境依赖：Blender 5.2、系统 Python（Pillow / numpy）、
[X Tools](https://www.egosoft.com/download/x4/bonus_en.php)（`XRCatTool.exe`）、
以及工作区里的 `x4-anim-preview`（离线动作预览器）。
`tools/paths.py` 会自己探测它们，找不到时用环境变量覆盖
（`YUE_SRC` / `X4_GAME` / `XRCAT_TOOL` / `X4_WORKSPACE`）。

## 4. 为什么只有默认套装

第二套装（雀吟逐霄）早已完整跑通（239 骨、减面、贴图、导出、macro 全部能做），
但它有一个**没有便宜解法**的冲突：

* X4 的 Argon 女性骨架把腿摆成**外八字**（Thigh 11.61 → Calf 14.81 → Foot 17.70 cm，
  踝间距 35.4 cm），因为她们的布料是长裤和短夹克，**游戏里没有长裙**；
* 月清疏的源模型双腿**几乎垂直**（踝间距 17.6 cm），第二套装的**紫蓝长裙盖过大腿**。

重定向必须把源腿映射到 X4 的宽站姿上（否则动画一播就是“猫步”），腿于是顶出
长裙。两条修法都试过，都不成立：

| 修法 | 结果 |
|---|---|
| 收窄腿的几何 | 穿模数字修好了（5.19 → 1.62 cm），但**腿的形状读起来不对**（用户实测）——而且方向反了：不合身的是衣服 |
| 按高度放阔裙子 | 除一层采样异常外全部不穿模，但**腰封下缘出现水平折角**：`cloth1/2/3` 是整套服装的材质（顶点从 z=190 的披肩铺到 z=−1 的靴底），带内真正的裙子只有 1526 个顶点，而腰封（`cloth3`，z 83–109）被一起拉宽了 |

而在同一轮里还查清了另一件事——**横向阻尼改的不是腿的位置，是每一段的倾角**：
骨架永远是 vanilla 的（stage1 里导入的宿主骨架），量骨链永远量不出问题，真正
变的是每段的目标位置。折角 = 相邻两段倾角之差：

```
初版 0.60/0.85/0.95   大腿 4.30°  小腿 4.75°   折角 0.45°   看不出
二版 0.80/1.00/1.20   大腿 4.80°  小腿 6.45°   折角 1.65°   3.7 倍，一眼可见
```

第二版是照着“两脚间距要接近 vanilla”（89–91%，指标达标）调出来的。
**指标对不等于形状对**：比值只约束两个端点，形状约束的是整条链。
所以阻尼回退到初版，代价是两脚间距只有 vanilla 的 76–81%（见“已知问题”）。

默认套装没有这个问题：它的短裙只到大腿中部，**腿在裙外本来就是裸露的**
（原作预览可证），所以腿怎么外撇都不穿模。先把这一套装做扎实。

第二套装的完整源定义、材质表与减面比例都留在 `yue_src.py` 里，
`python tools/build_all.py --outfits a,b` 仍能把它构建出来 —— 缺的只是一个
既不改腿形、也不在腰封上折角的放阔方案。

## 5. 已验证

| 项 | 结果 |
|---|---|
| 骨架 | head / body 两个 `.xac` 各 **91/91** bind 记录与各自宿主逐字节相同 |
| 骨骼映射 | 178 根带权骨 → 52 直接 + 折叠 + 1 未映射（根骨 `Bip001`，无权重） |
| 坐标手性 | `(x,y,z) → (x,z,y)`，Kabsch 拟合 `det(R) = +1.0000`，映射本身 det = −1 → **反转绕序** |
| 全局拟合 | scale = **108.35 cm/unit**（把 1.676 m 的源模型放大到 X4 女性体型，成品高 180.5 cm） |
| UV | 存 `1 − v_src`；与提取仓库自己的 `.blend` 逐值核对（`v[−0.0098, 1.0000]` 对 `[−0.0098, 0.9988]`） |
| 顶点预算 | head 19166 vs 5002（**3.83×**）；torso 15781 vs 4600（**3.43×**），上限 6× |
| 贴图 | 12 个材质，全部在 `ext_01.cat` 内可解析 |
| 自检 | `verify_mod.py` 两种形态全过（**0 警告**） |
| XML 生效性 | `check_xpath.py`：把 diff 套到合并后的 vanilla 库（726 macro / 134 池）上，add 形态 7 条 sel、replace 形态 123 条 sel **全部命中** |

### 动画预览（`x4-anim-preview/tools/ai_check.py`）

| 指标 | 月清疏（默认套装） | 甘雨（已发布） | vanilla |
|---|---|---|---|
| 关节撕裂 | 1.41–1.42× | 1.87× | 1.00× |
| 两脚间距 | 0.76–0.81× | 0.87–0.90× | 1.00× |
| 骨架 89/89 · 位置偏差 | 0.0 cm | — | — |

指标是**比值**；逐张对比图（`report_outfit_a/shots/`）已确认无破面、无错位、
贴图正确，腿是一条从胯到脚笔直外张的斜边（倒 V），膝盖处**无折角**。

## 6. 已知问题

1. **两脚间距只有 vanilla 的 76–81%**（预览器下限 85%）。这是为“腿是直的”付的
   代价：把间距推到 89–91% 的那组阻尼值会让腿在膝盖处折出 1.65° 的角，实机一眼
   可见（见第 4 节）。**形状优先。** 若将来要同时满足两者，正确做法是让**整条
   链一起**线性平移（保持各段倾角不变），而不是给某一段单独加码。
2. **关节处的残余撕裂**（肩、肘、脚踝）为 vanilla 的 1.41–1.42×，略高于预览器
   1.35× 的保守阈值。根因是源骨架（191 骨）与 X4 骨架（91 骨）的脊柱/腿长比例
   不同，“给骨链共享位移”的修法会引入更明显的弯折，已在更早的项目里试过并回退。
   绝对量 9.6 cm 对 vanilla 的 6.8 cm，仍优于已发布的前作（1.87× / 2.03×）。
3. **马尾与飘带是刚体**：X4 的 Biped 骨架里没有发丝链或布料链（只有 91 根），
   源的 `Ponytail1–14`、`Xtra01–12`、`Bone001–187` 只能折叠到链的根所对应的骨上，
   跟着头/躯干一起动，不会自己摆。
4. **头发不做 alpha 测试**：X4 的 `blendmode` 是**单值**，“双面”与“alpha 测试”
   不能兼得，这里选了 `TWOSIDED`（否则发片从背面看会整片消失），剪影完全由几何
   承载。睫毛是唯一例外，走 `ALPHA8`（源的 `.blend` 给了它 alpha=0.35）。
5. **三件“不该被看见”的层被丢弃**：`M_ProxyHide`（2405 顶点，Pal7 自己的
   “别画这个”标记，留着会在真皮肤外再套一层不透明壳）、`Eye_Occlusion`（252 顶点）
   与 `TearLine`（312 顶点）—— 后两件是同一件事的 alpha 版本，提取仓库的 `.blend`
   把它们的 alpha 设成 **0.0** 和 **0.15**；X4 的单值 `blendmode` 表达不了“淡”。

## 7. 版权

模型、贴图等游戏资产版权归 **软星科技（北京）有限公司 / 大宇资讯**所有。
本仓库**只包含工具与文档**，不含模型、贴图或游戏资产。仅供个人学习研究使用，
请勿再分发或商用。
