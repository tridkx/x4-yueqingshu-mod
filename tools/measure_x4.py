# -*- coding: utf-8 -*-
"""Measure the X4 Argon-female skeleton: axes, handedness, bind pose.

Every number the retarget depends on is printed here rather than assumed.
The three questions this answers, in order of how expensive it is to get
them wrong:

1. **Which axis is up / forward / which side is +X?**  Read off anatomy
   (toes point forward, the two eyes straddle the midline), never off a fit.
2. **Is the vanilla bind pose A or T?**  The arm chain angle decides how much
   of the source's own arm pose has to be undone.
3. **Where does the chain actually sit?**  Bone heads in centimetres, plus
   the eye dummies the look-at system drives.

    python tools/measure_x4.py [--host head|body]
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                      # noqa: E402
import xac_skeleton as xs                                         # noqa: E402

np.set_printoptions(precision=2, suppress=True, linewidth=200)

#: the chains worth printing in full; everything else is summarised
CHAINS = [
    'Bip01', 'Bip01 Pelvis', 'Bip01 Spine', 'Bip01 Spine1', 'Bip01 Spine2',
    'Bip01 Neck', 'Bip01 Head', 'Bip01 HeadNub',
    'left_eye_dummy', 'right_eye_dummy',
    'Bip01 L Clavicle', 'Bip01 L UpperArm', 'Bip01 L Forearm', 'Bip01 L Hand',
    'Bip01 L Finger0', 'Bip01 L Finger01', 'Bip01 L Finger02',
    'Bip01 R Clavicle', 'Bip01 R UpperArm', 'Bip01 R Forearm', 'Bip01 R Hand',
    'Bip01 L Thigh', 'Bip01 L Calf', 'Bip01 L Foot', 'Bip01 L Toe0',
    'Bip01 R Thigh', 'Bip01 R Calf', 'Bip01 R Foot', 'Bip01 R Toe0',
    'Attachment_Helper', 'L_Pec_LookAt', 'R_Pec_LookAt',
    'L_Knee_front_Helper', 'R_Knee_front_Helper',
]


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n else v


def ray(name, child, sk):
    """Bone direction, as the normalised head->child vector."""
    return unit(sk.head(child) - sk.head(name))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--host', choices=('head', 'body'), default='head')
    args = ap.parse_args()
    host = paths.HOST_HEAD if args.host == 'head' else paths.HOST_BODY

    sk = xs.Skeleton(host)
    print('== %s' % os.path.basename(host))
    print('   %d nodes' % len(sk.nodes))

    # ------------------------------------------------------------------
    print('\n--- 1. anatomy: which way is which -------------------------')
    for a, b, why in [
            ('Bip01 L Toe0', 'Bip01 L Foot', 'toe sits forward of the ankle'),
            ('right_eye_dummy', 'left_eye_dummy', 'the eyes straddle the midline'),
            ('Bip01 L Thigh', 'Bip01 R Thigh', 'left hip is on one side of it'),
    ]:
        if a in sk.by_name and b in sk.by_name:
            v = sk.head(a) - sk.head(b)
            print('   %-42s %s' % ('%s - %s' % (a, b), v.round(2)))
    print('   (up = the axis the head is highest on; forward = toes;')
    print('    +X = the side "Bip01 L" lives on, per X4 naming)')

    # ------------------------------------------------------------------
    print('\n--- 2. bone heads (X4 world) --------------------------------')
    for b in CHAINS:
        if b in sk.by_name:
            h = sk.head(b)
            print('   %-22s (%8.2f, %8.2f, %8.2f)' % (b, h[0], h[1], h[2]))
        else:
            print('   %-22s *** absent ***' % b)

    # ------------------------------------------------------------------
    print('\n--- 3. bind pose: chain directions --------------------------')
    pairs = [
        ('clavicle', 'Bip01 L Clavicle', 'Bip01 L UpperArm'),
        ('upperarm', 'Bip01 L UpperArm', 'Bip01 L Forearm'),
        ('forearm', 'Bip01 L Forearm', 'Bip01 L Hand'),
        ('hand', 'Bip01 L Hand', 'Bip01 L Finger0'),
        ('thigh', 'Bip01 L Thigh', 'Bip01 L Calf'),
        ('calf', 'Bip01 L Calf', 'Bip01 L Foot'),
        ('foot', 'Bip01 L Foot', 'Bip01 L Toe0'),
    ]
    for label, a, b in pairs:
        if a in sk.by_name and b in sk.by_name:
            d = ray(a, b, sk)
            # angle from the up axis and from the forward axis
            up_ax = int(np.argmax(np.abs(_up(sk))))
            print('   %-10s dir %s   |angle to up| %6.1f deg'
                  % (label, d.round(3), np.degrees(np.arccos(
                      np.clip(abs(d[up_ax]), -1, 1)))))
    u, f, r = _axes(sk)
    print('   up      %s' % u.round(3))
    print('   forward %s' % f.round(3))
    print('   right   %s' % r.round(3))

    # ------------------------------------------------------------------
    print('\n--- 4. eye dummies vs the head bone -------------------------')
    if 'Bip01 Head' in sk.by_name:
        h = sk.head('Bip01 Head')
        for e in ('left_eye_dummy', 'right_eye_dummy'):
            if e in sk.by_name:
                print('   %-16s %s   (rel. head %s)'
                      % (e, sk.head(e).round(2), (sk.head(e) - h).round(2)))

    # ------------------------------------------------------------------
    print('\n--- 5. all bones ---------------------------------------------')
    for n in sk.names():
        print('   %s' % n)
    return 0


def _axes(sk):
    """(up, forward, right) as world unit vectors, read off anatomy."""
    up = unit(sk.head('Bip01 Head') - sk.head('Bip01 Pelvis'))
    fwd = unit(sk.head('Bip01 L Toe0') - sk.head('Bip01 L Foot'))
    # orthogonalise forward against up, then right = forward x up
    fwd = unit(fwd - up * float(fwd @ up))
    right = unit(np.cross(fwd, up))
    return up, fwd, right


def _up(sk):
    return _axes(sk)[0]


if __name__ == '__main__':
    sys.exit(main())