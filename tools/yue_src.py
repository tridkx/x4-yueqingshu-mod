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
        'MI_MAJ02_01_Eye_Occlusion': ('eyeocc', None, None, None),
        'MI_MAJ02_01_TearLine': ('tear', None, None, None),
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
        'MI_MAJ02_01_Eye_Occlusion': ('eyeocc', None, None, None),
        'MI_MAJ02_01_TearLine': ('tear', None, None, None),
    },
}

#: Materials that never reach the mod.
#:
#: `M_ProxyHide` is Pal7's own "do not draw this" flag: 2405 vertices of body
#: shell the artists keep around so the character does not turn into a hole
#: when a garment clip plays.  The `.blend` exports already drop it; shipping
#: it would put an opaque second skin *over* the real one.
DROP_MATERIALS = {'M_ProxyHide'}

# --------------------------------------------------------------------------
# which X4 asset each material belongs to
# --------------------------------------------------------------------------
#: region -> [(slot name, [stems], host mesh id)].  The host mesh ids are the
#: slots the vanilla Argon-female assets declare; see `build_yue_mod.SLOT_PLAN`.
SLOTS = {
    'head': [
        ('face', ['head', 'eye', 'mouth', 'brow', 'eyelash', 'eyeocc',
                  'tear'], 0),
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
    'eyelash': 'TWOSIDED',
    'brow': 'TWOSIDED',
    'eyeocc': 'TWOSIDED',
    'tear': 'TWOSIDED',
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

#: stem -> placeholder base colour, for the four materials Pal7 drives purely
#: from shader parameters (no `PM_Diffuse` at all).  Read off the rendered
#: preview rather than invented: `eyelash_new_Inst` is the dark lash mass, the
#: tear line is a wet highlight, the occlusion layer is a soft shadow.
PLACEHOLDER_RGB = {
    'eyelash': (38, 30, 28),
    'eyeocc': (168, 150, 142),
    'tear': (232, 236, 240),
}
DEFAULT_PLACEHOLDER = (200, 200, 200)

#: stem -> smoothness (0 = matte, 1 = mirror), used only where the source has
#: no `_ORM` map to read roughness from.
SMOOTHNESS = {
    'head': 0.28, 'body': 0.28, 'mouth': 0.30,
    'eye': 0.72, 'eyelash': 0.35, 'brow': 0.25,
    'eyeocc': 0.30, 'tear': 0.85,
    'hair': 0.42, 'cloth1': 0.20, 'cloth2': 0.20, 'cloth3': 0.20,
    'tassel': 0.30,
}

#: Materials whose albedo genuinely needs an alpha channel (BC3 rather than
#: BC1).  Only the hair: its `_alpha` map is the strand cut-out.  Everything
#: else measured fully opaque through its own UVs, and giving them an alpha
#: channel would cost 2x the texture memory for a mask nobody reads.
ALPHA_STEMS = {'hair'}

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
        'eye': 1.0, 'mouth': 0.60, 'brow': 1.0, 'eyeocc': 1.0, 'tear': 1.0,
    },
    'b': {
        'hair': 0.45, 'eyelash': 0.15, 'head': 0.70, 'body': 0.45,
        'cloth1': 0.30, 'cloth2': 0.30, 'cloth3': 0.60, 'tassel': 0.40,
        'eye': 1.0, 'mouth': 0.60, 'brow': 1.0, 'eyeocc': 1.0, 'tear': 1.0,
    },
}
DEFAULT_DECIMATE = 0.35
#: never decimate a part below this many vertices -- a collapsed eye or lash
#: strip stops being recognisable long before it stops being cheap.
DECIMATE_FLOOR = 120

# --------------------------------------------------------------------------
# geometry fixes
# --------------------------------------------------------------------------
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