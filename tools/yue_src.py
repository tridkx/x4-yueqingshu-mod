# -*- coding: utf-8 -*-
"""What the Pal7 source is: materials, parts, textures, and what to throw away.

Pal7 is a UE4 title, so the export is a glTF binary with **separate maps per
material** (`_D` / `_N` / `_ORM`) rather than the single shared atlases an MMD
model ships.  That changes three things against the Genshin projects:

* the normal map is the author's, not a generated flat one -- X4 accepts BC5
  directly, so it goes through unchanged;
* `_ORM` packs occlusion/roughness/metallic into R/G/B, so roughness is read
  from the **green** channel instead of being a per-material constant;
* nothing is atlased, so a UV shift from decimation damages far less -- but
  the parts are still decimated conservatively, see `DECIMATE`.

Two outfits share one face.  Measured: `MI_MAJ02_01_head`, `_eye`,
`mouth_Skeleton`, `Eyelash_eyebrow`, `TearLine` and `Eye_Occlusion` carry
identical vertex counts in both exports, and `MI_MAJ02_01_body` /
`MI_MAJ02_01_hair` keep the same material *names* -- only the garment
materials (`cloth*`, `tassel`) and the hair *geometry* differ.  The two
outfits therefore share their face textures and differ in the rest.
"""

import os
import re

import numpy as np

import paths

# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
#: Per outfit: source material name -> (stem, diffuse, normal, orm).
#:
#: The stem is what the X4 material is called (`yue.a_head`); it must be ascii
#: and unique *within an outfit*.  The three texture names are the basenames
#: (without `.png`) of the maps in `textures/`; `None` means the material has
#: no such map and a placeholder is used instead.
#:
#: **Two of these are not the asset's own names on purpose.**  Pal7 paints its
#: head albedo as an *overlay*: only the features are drawn and the rest of the
#: sheet is pure black, because the game's skin shader supplies the rest --
#: used as-is, the forehead, chin and neck render as black patches.  The
#: extraction repo's `fix_head_texture.py` flood-fills that unused black with
#: skin tone and writes `*_skin.png`, and composites the iris disc onto the
#: sclera as `*_eye.png` (the shader multiplies the two, and the iris map's
#: surround is black, so the raw pair renders a black eyeball).  Both fixed
#: sheets are what the extraction's own `.blend` uses -- verified by reading
#: its material nodes, not by guessing from the filenames.
MATS = {
    'a': {
        'MI_MAJ02_01_head': ('head', 'T_MAJ02_01_head_D_skin',
                             'T_MAJ02_01_head_N', 'T_MAJ02_01_head_ORM'),
        'MI_MAJ02_01_body': ('body', 'T_MAJ02_01_body_D',
                             'T_MAJ02_01_body_N', 'T_MAJ02_01_body_ORM'),
        'MI_MAJ02_01_hair': ('hair', 'T_MAJ02_01_Hair_D', None, None),
        'MI_MAJ02_01_cloth1': ('cloth1', 'T_MAJ02_01_cloth1_D',
                               'T_MAJ02_01_cloth1_N', 'T_MAJ02_01_cloth1_ORM'),
        'MI_MAJ02_01_cloth2': ('cloth2', 'T_MAJ02_01_cloth2_D',
                               'T_MAJ02_01_cloth2_N', 'T_MAJ02_01_cloth2_ORM'),
        'MI_MAJ02_01_tassel': ('tassel', 'T_MAJ02_01_tassel_D',
                               'T_MAJ02_01_tassel_N', 'T_MAJ02_01_tassel_ORM'),
        'MI_MAJ02_01_eye': ('eye', 'S_EyeScleraBaseColor_eye', None, None),
        'MI_MAJ02_01_mouth_Skeleton': ('mouth', 'T_Mouth_D',
                                       'T_Mouth_N', 'T_Mouth_ORM'),
        'MAJ02_01_Eyelash_eyebrow': ('brow', 'MAJ03_01_Eyelash_Master',
                                     None, None),
        'eyelash_new_Inst': ('eyelash', 'MAJ03_01_Eyelash_Master', None, None),
    },
    'b': {
        'MI_MAJ02_01_head': ('head', 'T_MAJ02_01_head_D_skin',
                             'T_MAJ02_01_head_N', 'T_MAJ02_01_head_ORM'),
        'MI_MAJ02_01_body': ('body', 'T_MAJ02_01_body_D',
                             'T_MAJ02_01_body_N', 'T_MAJ02_01_body_ORM'),
        'MI_MAJ02_01_hair': ('hair', 'T_MAJ02_01_Hair_D', None, None),
        'MI_MAJ02_02_cloth1': ('cloth1', 'MAJ02_02_cloth1_BaseColor',
                               'MAJ02_02_cloth1_Normal',
                               'MAJ02_02_cloth1_OcclusionRoughnessMetallic'),
        'MI_MAJ02_02_cloth2': ('cloth2', 'MAJ02_02_cloth2_BaseColor',
                               'MAJ02_02_cloth2_Normal',
                               'MAJ02_02_cloth2_OcclusionRoughnessMetallic'),
        'MI_MAJ02_02_cloth3': ('cloth3', 'MAJ02_02_cloth3_BaseColor',
                               'MAJ02_02_cloth3_Normal',
                               'MAJ02_02_cloth3_OcclusionRoughnessMetallic'),
        'MI_MAJ02_02_tassel': ('tassel', 'T_MAJ02_02_tassel_D',
                               'T_MAJ02_01_tassel_N', 'T_MAJ02_01_tassel_ORM'),
        'MI_MAJ02_01_eye': ('eye', 'S_EyeScleraBaseColor_eye', None, None),
        'MI_MAJ02_01_mouth_Skeleton': ('mouth', 'T_Mouth_D',
                                       'T_Mouth_N', 'T_Mouth_ORM'),
        'MAJ02_01_Eyelash_eyebrow': ('brow', 'MAJ03_01_Eyelash_Master',
                                     None, None),
        'MI_MAJ02_01_eyelash': ('eyelash', 'T_MAJ02_01_eyelash', None, None),
    },
}

#: Materials that never reach the mod.
#:
#: `M_ProxyHide` is Pal7's own "do not draw this" flag: 2405 vertices of body
#: shell the artists keep around so the character does not turn into a hole
#: when a garment clip plays.  The `.blend` exports already drop it; shipping
#: it would put an opaque second skin *over* the real one.
#:
#: `Eye_Occlusion` and `TearLine` are the same idea expressed through alpha,
#: and the extraction's own `.blend` is the evidence: it sets their Blender
#: alpha to **0.0** and **0.15**.  They are 408 and 492 faces of eye-socket
#: shading that the game composites; carried into X4 as opaque surfaces they
#: become a beige patch over each eye and a dark ring under it -- visible in
#: `docs/成品预览_两套装.png`'s first render, which is how this was caught.
#: X4's blendmode is a single value, so "faint" is not expressible for
#: geometry that also has to be TWOSIDED; dropping them is equivalent.
DROP_MATERIALS = {
    'M_ProxyHide',
    'MI_MAJ02_01_Eye_Occlusion',
    'MI_MAJ02_01_TearLine',
}

# --------------------------------------------------------------------------
# which X4 asset each material belongs to
# --------------------------------------------------------------------------
#: region -> [(slot name, [stems], host mesh id)].  The host mesh ids are the
#: slots the vanilla Argon-female assets declare; see `build_yue_mod.SLOT_PLAN`.
SLOTS = {
    'head': [
        ('face', ['head', 'eye', 'mouth', 'brow', 'eyelash'], 0),
        ('hair', ['hair'], 1),
    ],
    'body': [
        ('skin', ['body'], 0),
        ('cloth', ['cloth1', 'cloth2', 'cloth3', 'tassel'], 1),
    ],
}

REGION_OF = {}
for _region, _slots in SLOTS.items():
    for _n, _stems, _mid in _slots:
        for _s in _stems:
            REGION_OF[_s] = _region

# --------------------------------------------------------------------------
# shading
# --------------------------------------------------------------------------
#: stem -> X4 shader.  `p1_hair` brings the anisotropic hair shading and the
#: alpha-tested pipeline; everything else is the standard character shader.
SHADER = {
    'hair': 'p1_hair',
    'eyelash': 'p1_hair',
    'brow': 'p1_hair',
}

#: stem -> X4 blend mode.  X4's `blendmode` is a **single value**, so
#: "draw both sides" and "alpha test" are mutually exclusive (see the skill's
#: §1.8).  Thin sheets -- anything the camera can see the back of -- have to be
#: TWOSIDED; only surfaces that are genuinely alpha-cut go the other way.
#:
#: Pal7's hair, lashes and brows are geometry-plus-alpha atlases, but the
#: geometry here is dense enough that the silhouette is carried by triangles
#: rather than by the mask, and `TWOSIDED` is what stops a hair card from
#: vanishing when seen from behind.
BLEND = {
    'hair': 'TWOSIDED',
    # 睫毛是**唯一**走 alpha 混合的一件，因为源就是这么做的：提取仓库自己的
    # `.blend` 给它设了 alpha=0.35 —— 9751 个顶点、12074 个面的睫毛卡片，
    # 不淡化就是眼睛上一大块深色（第一版渲染出来的"浓重眼线"就是它）。
    # 代价是失去 TWOSIDED；睫毛贴在眼球上，本来就极少被从背面看到。
    'eyelash': 'ALPHA8',
    'brow': 'TWOSIDED',
    'cloth1': 'TWOSIDED',
    'cloth2': 'TWOSIDED',
    'cloth3': 'TWOSIDED',
    'tassel': 'TWOSIDED',
    'eye': 'NONE',
    'head': 'NONE',
    'body': 'NONE',
    'mouth': 'NONE',
}
DEFAULT_BLEND = 'TWOSIDED'

#: stem -> placeholder base colour, for the materials Pal7 drives purely from
#: shader parameters (no `PM_Diffuse` at all).  The values are the `.blend`'s
#: own Principled base colours converted to 8-bit, not invented.
PLACEHOLDER_RGB = {
    'eyelash': (20, 14, 6),
}
DEFAULT_PLACEHOLDER = (200, 200, 200)

#: stem -> placeholder alpha, again read off the `.blend`.  Only a material
#: whose blend mode actually uses alpha needs one.
PLACEHOLDER_ALPHA = {
    'eyelash': 0.35,
}

#: stem -> smoothness (0 = matte, 1 = mirror), used only where the source has
#: no `_ORM` map to read roughness from.
SMOOTHNESS = {
    'head': 0.28, 'body': 0.28, 'mouth': 0.30,
    'eye': 0.72, 'eyelash': 0.35, 'brow': 0.25,
    'hair': 0.42, 'cloth1': 0.20, 'cloth2': 0.20, 'cloth3': 0.20,
    'tassel': 0.30,
}

#: Materials whose albedo genuinely needs an alpha channel (BC3 rather than
#: BC1).  The hair's `_alpha` map is the strand cut-out; the lashes have no
#: map at all, so their alpha lives in the generated placeholder.
ALPHA_STEMS = {'hair', 'eyelash'}

# --------------------------------------------------------------------------
# decimation
# --------------------------------------------------------------------------
#: stem -> Blender collapse ratio.  **This is the whole budget argument.**
#:
#: The source is 115k / 75k vertices against a vanilla budget of roughly 9.6k
#: for the two assets together -- 12x over, well past the ~15x point where the
#: map screen starts to flicker.  The user asked for "stability first", so the
#: targets are vanilla x3-6 per asset:
#:
#:     head asset  vanilla ~5.0k  ->  budget <= 30k
#:     body asset  vanilla ~4.6k  ->  budget <= 27k
#:
#: `hair` and `eyelash` dominate (48.8k + 9.8k in outfit A) and are exactly the
#: parts where a collapse is least visible -- hair cards are dense strips that
#: read the same at half the triangles, and lashes are 2 cm of geometry.
#: `head` (the face) keeps most of its density: it is 4.0k vertices, and the
#: face is what the player actually looks at.
#:
#: The garments are large but smooth; 0.35 keeps the silhouette and the fold
#: shading.  `body` is mostly hidden under them.
DECIMATE = {
    'a': {
        'hair': 0.20, 'eyelash': 0.15, 'head': 0.70, 'body': 0.40,
        'cloth1': 0.35, 'cloth2': 0.22, 'tassel': 0.35,
        'eye': 1.0, 'mouth': 0.60, 'brow': 1.0,
    },
    'b': {
        'hair': 0.45, 'eyelash': 0.15, 'head': 0.70, 'body': 0.45,
        'cloth1': 0.30, 'cloth2': 0.30, 'cloth3': 0.60, 'tassel': 0.40,
        'eye': 1.0, 'mouth': 0.60, 'brow': 1.0,
    },
}
DEFAULT_DECIMATE = 0.35
#: never decimate a part below this many vertices -- a collapsed eye or lash
#: strip stops being recognisable long before it stops being cheap.
DECIMATE_FLOOR = 120

# --------------------------------------------------------------------------
# geometry fixes
# --------------------------------------------------------------------------
#: Per outfit: how much of the leg's **horizontal width** to keep.
#:
#: The long skirt of outfit B reaches past mid-thigh, and the lateral damping
#: that fixes the "catwalk" (see `yue_to_x4.LATERAL_DAMP`) pushes the legs out
#: to vanilla's stance width.  For outfit A that is harmless -- its skirt stops
#: at mid-thigh and the legs below it are bare by design.  For B the legs then
#: stick out through the sides of the skirt: measured with `diag_leg_clip.py`,
#: up to **5.19 cm** at z=77 (and 2-5 cm across z=53..77).
#:
#: The fix is to narrow the leg *geometry* around its own bone axis -- the
#: bones stay exactly where vanilla has them, so the animation is untouched and
#: only the silhouette gets thinner.  Outfit A keeps 1.0: it is not broken and
#: the user said so.
LEG_SHRINK = {
    'a': 1.00,
    'b': 0.55,
}

#: The bones a vertex must be mostly bound to before it counts as "leg".  The
#: threshold is on the summed weight of these bones, so a vertex blended across
#: thigh and calf is still handled smoothly.
LEG_BONES = ('Bip01 L Thigh', 'Bip01 R Thigh',
             'Bip01 L Calf', 'Bip01 R Calf',
             'Bip01 L Foot', 'Bip01 R Foot')
LEG_BONE_MIN_WEIGHT = 0.5

#: Pal7 models the garment on the body, so the two surfaces tie in depth and
#: flicker.  Push the garment out along its own normals.  2 mm is far below
#: anything visible at NPC range and far above the depth buffer's resolution
#: there; the whole garment moves together so no seam opens.
CLOTH_OFFSET = 0.2
#: the eye-occlusion layer floats a fraction of a mm off the eyelid.
OCCLUSION_OFFSET = 0.12

#: vanilla's own boot soles bottom out at -0.32 cm
GROUND_Z = -0.5


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def outfit(key):
    return next(o for o in paths.OUTFITS if o['key'] == key)


def materials(key):
    return MATS[key]


def stem_of(key, material_name):
    rec = MATS[key].get(material_name)
    return rec[0] if rec else None


def maps_of(key, material_name):
    """(stem, diffuse, normal, orm) 或 None。"""
    return MATS[key].get(material_name)


def texture_stem_of(key, material_name):
    """Diffuse 贴图的 basename（无扩展名），给 stage1 的占位材质用。"""
    rec = MATS[key].get(material_name)
    return rec[1] if rec else None


def ascii_stem(name):
    """Any string -> a name X4 can open: ascii, lowercase, `[a-z0-9_]` only.

    X4 resolves asset paths as byte strings and a CJK character *is*
    alphanumeric to Python, so `isalnum()` alone would happily produce a name
    the game cannot open -- with a magenta missing-texture as the only clue.
    """
    out = ''.join(c if (c.isascii() and (c.isalnum() or c == '_')) else '_'
                  for c in str(name))
    return re.sub(r'_+', '_', out).strip('_').lower()


#: DDS stem aliases: source texture stem -> the name its `.dds` files get.
#: Both outfits name their face/hair textures identically, so those encode
#: once and the two material sets point at the same file.
def dds_stem(tex_stem):
    return ascii_stem(tex_stem)


def sample_face_alpha(alpha, uvf, samples=4):
    """Mean alpha of a triangle's UVs, as `(n,)` in 0..255.

    Shared by the builder (which deletes faces the author painted out) and by
    `diag_alpha_faces.py` (which reports them) -- one implementation, so the
    two can never disagree about what "invisible" means.

    `alpha` is `(H, W)` with row 0 at the **top** of the image, and `uvf` is
    `(n, 3, 2)` with v measured downwards from the top, i.e. the source's own
    convention.
    """
    h, w = alpha.shape
    bary = [(1 / 3., 1 / 3., 1 / 3.),
            (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6)][:samples]
    acc = np.zeros(len(uvf))
    for bw in bary:
        u = sum(bw[i] * uvf[:, i, 0] for i in range(3))
        v = sum(bw[i] * uvf[:, i, 1] for i in range(3))
        x = np.clip((u % 1.0) * (w - 1), 0, w - 1).astype(int)
        y = np.clip((v % 1.0) * (h - 1), 0, h - 1).astype(int)
        acc += alpha[y, x]
    return acc / len(bary)


#: A face is "invisible" when every sample of its own albedo reads below this.
ALPHA_KEEP = 8.0