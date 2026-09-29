# -*- coding: utf-8 -*-
"""Every path this pipeline needs, resolved once and overridable by env vars.

Nothing here is a hard-coded absolute path: each location is either derived
from this file's own position (so the project keeps working when the workspace
is moved, renamed or copied to another machine) or probed from a list of
candidates.  An environment variable exists for every case probing cannot
cover -- a game installed somewhere unusual, the source extraction kept
elsewhere.

    YUE_SRC        the Pal7 extraction directory (holds `月清疏_YueQingShu/`)
    X4_GAME        X4: Foundations install (holds `0N.cat`, `extensions/`)
    X4_WORKSPACE   the shared workspace root (default: this project's parent)
    XRCAT_TOOL     XRCatTool.exe, when it is not next to the game

`shared/` follows the workspace layout: the unpacked game root, the Blender
converter addon and the reference mods are shared by every mod project, while
`work/` belongs to this one.
"""

import glob
import os

# --------------------------------------------------------------------------
# this project
# --------------------------------------------------------------------------
TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(TOOLS)
DOCS = os.path.join(PROJ, 'docs')
WORK = os.path.join(PROJ, 'work')

WORKSPACE = os.environ.get('X4_WORKSPACE') or os.path.dirname(PROJ)
SHARED = os.path.join(WORKSPACE, 'shared')

#: unpacked vanilla assets the converter reads through `data_root`
X4_ROOT = os.path.join(SHARED, 'x4root')

#: the Blender addon (X4 Character Converter), version-agnostic
_addons = sorted(glob.glob(os.path.join(SHARED, 'X4CharacterConverter*')))
ADDON_DIR = next((p for p in _addons if os.path.isdir(p)), None)


def _first_dir(*candidates):
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def _first_file(*candidates):
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


#: unpacked game libraries (character_macros.xml, charactergroups.xml, ...).
#: The older projects kept them under their own `work/`; both layouts are
#: accepted so this project does not force a move on anyone.
VANILLA = _first_dir(
    os.path.join(SHARED, 'vanilla'),
    os.path.join(WORKSPACE, 'x4-character-retarget', 'work', 'vanilla'),
)
DLC_ALL = _first_dir(
    os.path.join(SHARED, 'dlc_all'),
    os.path.join(WORKSPACE, 'x4-character-retarget', 'work', 'dlc_all'),
)

# --------------------------------------------------------------------------
# the game
# --------------------------------------------------------------------------
_GAME_CANDIDATES = [
    os.environ.get('X4_GAME'),
    r'D:\SteamLibrary\steamapps\common\X4 Foundations',
    r'C:\Program Files (x86)\Steam\steamapps\common\X4 Foundations',
    r'C:\SteamLibrary\steamapps\common\X4 Foundations',
    r'E:\SteamLibrary\steamapps\common\X4 Foundations',
]
GAME = _first_dir(*_GAME_CANDIDATES)

#: where the game loads extensions from (both the install and the user dir)
EXTENSIONS = os.path.join(GAME, 'extensions') if GAME else None
USER_X4 = os.path.join(os.path.expanduser('~'), 'Documents', 'Egosoft', 'X4')
USER_EXTENSIONS = os.path.join(USER_X4, 'extensions')

#: XRCatTool ships with "X Tools"; it is either beside the game or in its own
#: Steam entry.  `-out` must end in `.cat`.
XRCAT_TOOL = _first_file(
    os.environ.get('XRCAT_TOOL'),
    os.path.join(GAME, 'XRCatTool.exe') if GAME else None,
    os.path.join(GAME, 'tools', 'XRCatTool.exe') if GAME else None,
    os.path.join(os.path.dirname(GAME), 'X Tools', 'XRCatTool.exe')
    if GAME else None,
    os.path.join(os.path.expanduser('~'), 'Downloads', 'XRCatTool.exe'),
)

# --------------------------------------------------------------------------
# the source model
# --------------------------------------------------------------------------
#: the Pal7 extraction lives beside the workspace, not inside it -- it is a
#: separate research repo, and copying ~1.6 GB of assets into every mod
#: project would be absurd.  The sibling layout is a default, not a rule.
_SRC_CANDIDATES = [
    os.environ.get('YUE_SRC'),
    os.path.join(os.path.dirname(WORKSPACE), 'dsh-xianjian7', 'output'),
    os.path.join(WORKSPACE, 'xianjian7', 'output'),
]
SRC = _first_dir(*_SRC_CANDIDATES)

#: the two outfits, in the order the mod presents them (A then B)
OUTFITS = [
    {
        'key': 'a',
        'name': '默认套装',
        'code': 'MAJ02_01',
        'dir': '01_默认套装_MAJ02_01',
        'glb': 'YueQingShu_MAJ02_01.glb',
        'blend': '01_默认套装_MAJ02_01.blend',
    },
    {
        'key': 'b',
        'name': '第二套装',
        'code': 'MAJ02_02',
        'dir': '02_第二套装_MAJ02_02',
        'glb': 'YueQingShu_MAJ02_02.glb',
        'blend': '02_第二套装_MAJ02_02.blend',
    },
]
SRC_CHAR_DIR = os.path.join(SRC, '月清疏_YueQingShu') if SRC else None


def outfit_dir(outfit):
    return os.path.join(SRC_CHAR_DIR, outfit['dir'])


def outfit_glb(outfit):
    return os.path.join(outfit_dir(outfit), outfit['glb'])


def outfit_tex(outfit):
    return os.path.join(outfit_dir(outfit), 'textures')


# --------------------------------------------------------------------------
# vanilla hosts (the two Argon female assets the converter fills)
# --------------------------------------------------------------------------
#: heads and bodies of the Argon female; the mod rewrites the mesh slots of
#: one of these and keeps its skeleton untouched.
HOST_HEAD = os.path.join(X4_ROOT, 'assets', 'characters', 'argon', 'heads',
                         'char_arg_f_dyn_blend_head.xac')
HOST_BODY = os.path.join(X4_ROOT, 'assets', 'characters', 'argon', 'bodies',
                         'char_arg_f_jacket_leggings_civ_01.xac')

#: the byte-exact skeleton reference: the body with all 91 bones deduplicated
SKELETON_REF = os.path.join(WORKSPACE, 'ganyu', 'work', 'vanilla',
                            'char_arg_f_jacket_leggings_civ_01.xac')

# --------------------------------------------------------------------------
# this project's work tree
# --------------------------------------------------------------------------
NPZ = os.path.join(WORK, 'npz')
PREVIEW = os.path.join(WORK, 'preview')
X4_BONES_JSON = os.path.join(WORK, 'x4_bones.json')
PKG = os.path.join(WORK, 'x4cc_pkg')
DDS_DIR = os.path.join(WORK, 'tex_out', 'mats')
VERIFY_TMP = os.path.join(WORK, 'verify_tmp')
DIST = os.path.join(WORK, 'dist')


def stage1_blend(outfit):
    return os.path.join(WORK, 'yue_%s_stage1.blend' % outfit['key'])


def bones_json(outfit):
    return os.path.join(WORK, 'yue_%s_bones.json' % outfit['key'])


def mod_dir(race, mode):
    return os.path.join(WORK, 'x4_yue_%s_%s' % (race, mode))


def pkg_dir(outfit):
    return os.path.join(PKG, outfit['key'])


# --------------------------------------------------------------------------
def ensure(*dirs):
    for d in dirs:
        if d:
            os.makedirs(d, exist_ok=True)


def check(verbose=True):
    """Report what resolved and what did not; returns the missing list."""
    items = [
        ('source extraction', SRC),
        ('source character dir', SRC_CHAR_DIR),
        ('x4 root (unpacked assets)', X4_ROOT),
        ('converter addon', ADDON_DIR),
        ('vanilla libraries', VANILLA),
        ('dlc libraries', DLC_ALL),
        ('game install', GAME),
        ('XRCatTool', XRCAT_TOOL),
    ]
    for o in OUTFITS:
        items.append(('source glb (%s)' % o['key'], outfit_glb(o)))
    missing = [name for name, path in items if not path or
               (name.startswith('source glb') and not os.path.isfile(path))]
    if verbose:
        for name, path in items:
            print('  %-28s %s' % (name, path or '*** MISSING ***'))
    return missing


if __name__ == '__main__':
    missing = check()
    print('missing: %s' % (missing or 'none'))