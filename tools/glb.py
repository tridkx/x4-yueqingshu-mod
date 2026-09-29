# -*- coding: utf-8 -*-
"""Minimal glTF-binary reader, enough to measure a source model.

The Pal7 exports are single-mesh glTF binaries with one skin, N material
primitives and no animations -- a full glTF implementation would be mostly
dead code here, so this parses exactly what the pipeline needs and refuses
anything it does not understand instead of guessing.

Everything is returned as plain numpy arrays in the glTF's own space
(right-handed, Y up, metres or whatever unit the exporter used).
"""

import json
import struct

import numpy as np

#: glTF component types -> numpy dtypes
_CT = {
    5120: np.int8, 5121: np.uint8, 5122: np.int16,
    5123: np.uint16, 5125: np.uint32, 5126: np.float32,
}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class Glb(object):
    def __init__(self, path):
        self.path = str(path)
        with open(path, 'rb') as fh:
            data = fh.read()
        magic, ver, total = struct.unpack('<III', data[:12])
        if magic != 0x46546C67:
            raise ValueError('%s is not a glb (bad magic)' % path)
        if ver != 2:
            raise ValueError('%s: glTF version %d is not supported' % (path, ver))
        self.json = None
        self.bin = b''
        off = 12
        while off < total:
            clen, ctype = struct.unpack('<II', data[off:off + 8])
            body = data[off + 8:off + 8 + clen]
            if ctype == 0x4E4F534A:
                self.json = json.loads(body.decode('utf-8'))
            elif ctype == 0x004E4942:
                self.bin = body
            off += 8 + clen
        if self.json is None:
            raise ValueError('%s: no JSON chunk' % path)
        self.g = self.json

    # ------------------------------------------------------------------
    def accessor(self, idx):
        """An accessor as an (n, k) array; sparse accessors are not used here."""
        acc = self.g['accessors'][idx]
        if 'sparse' in acc:
            raise NotImplementedError('sparse accessors are not supported')
        n, k = acc['count'], _NCOMP[acc['type']]
        dt = np.dtype(_CT[acc['componentType']]).newbyteorder('<')
        if 'bufferView' not in acc:
            return np.zeros((n, k), dt)
        bv = self.g['bufferViews'][acc['bufferView']]
        start = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        stride = bv.get('byteStride') or k * dt.itemsize
        if stride == k * dt.itemsize:
            flat = np.frombuffer(self.bin, dt, n * k, start)
            return flat.reshape(n, k)
        # interleaved: walk the stride explicitly
        out = np.empty((n, k), dt)
        for i in range(n):
            out[i] = np.frombuffer(self.bin, dt, k, start + i * stride)
        return out

    # ------------------------------------------------------------------
    def prims(self):
        """Yield ``(material_name, arrays)`` for every primitive of mesh 0."""
        mesh = self.g['meshes'][0]
        for p in mesh['primitives']:
            a = p['attributes']
            mat = self.g['materials'][p['material']]['name']
            arrays = {
                'pos': self.accessor(a['POSITION']).astype(np.float64),
                'idx': self.accessor(p['indices']).reshape(-1).astype(np.int64),
            }
            for key, name in (('NORMAL', 'nrm'), ('TEXCOORD_0', 'uv'),
                              ('JOINTS_0', 'joints'), ('WEIGHTS_0', 'weights'),
                              ('TANGENT', 'tan')):
                if key in a:
                    arrays[name] = self.accessor(a[key])
            yield mat, arrays

    # ------------------------------------------------------------------
    def joints(self):
        """Joint names and their rest-pose world positions.

        glTF stores joints as nodes; the world transform is the product of
        the node chain, and a joint's own translation lives in its matrix.
        """
        nodes = self.g['nodes']
        skin = self.g['skins'][0]
        parent = {}
        for i, nd in enumerate(nodes):
            for c in nd.get('children', []):
                parent[c] = i

        def local(i):
            nd = nodes[i]
            if 'matrix' in nd:
                return np.array(nd['matrix'], float).reshape(4, 4).T
            m = np.eye(4)
            t = nd.get('translation', [0, 0, 0])
            r = nd.get('rotation', [0, 0, 0, 1])
            s = nd.get('scale', [1, 1, 1])
            x, y, z, w = r
            rot = np.array([
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ])
            m[:3, :3] = rot * np.array(s)[None, :]
            m[:3, 3] = t
            return m

        names, mats = [], []
        for j in skin['joints']:
            names.append(nodes[j].get('name', 'joint_%d' % j))
            chain, cur = [], j
            while cur is not None:
                chain.append(cur)
                cur = parent.get(cur)
            m = np.eye(4)
            for cur in reversed(chain):
                m = m @ local(cur)
            mats.append(m)
        return names, np.array(mats)

    # ------------------------------------------------------------------
    def summary(self):
        tot_v = tot_t = 0
        per = []
        for mat, a in self.prims():
            nv, nt = len(a['pos']), len(a['idx']) // 3
            tot_v += nv
            tot_t += nt
            per.append((mat, nv, nt))
        names, mats = self.joints()
        return {
            'materials': per, 'verts': tot_v, 'tris': tot_t,
            'joints': names, 'joint_mats': mats,
        }


def face_normals(pos, idx):
    """Geometric normals of every triangle (unnormalised winding normal)."""
    tri = pos[idx.reshape(-1, 3)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(ln == 0, 1.0, ln)


def winding_report(pos, idx, nrm=None):
    """Mean dot(face normal, vertex normal) -- the winding sanity check.

    A source file that carries its own vertex normals can be asked directly
    whether its triangles agree with them; > 0 means the winding follows the
    right-hand rule for the stored normals, < 0 means every triangle faces
    inwards (the classic "reflected axis mapping" bug).
    """
    fn = face_normals(pos, idx)
    if nrm is None:
        c = pos.mean(axis=0, keepdims=True)
        vn = pos - c
        vn /= np.where(np.linalg.norm(vn, axis=1, keepdims=True) == 0, 1.0,
                       np.linalg.norm(vn, axis=1, keepdims=True))
        vn = vn[idx.reshape(-1, 3)].mean(axis=1)
    else:
        vn = nrm[idx.reshape(-1, 3)].astype(np.float64).mean(axis=1)
    d = (fn * vn).sum(axis=1)
    return float(d.mean()), float((d > 0).mean())


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        g = Glb(p)
        s = g.summary()
        print('=== %s' % p)
        print('  verts %d  tris %d  joints %d' % (s['verts'], s['tris'],
                                                  len(s['joints'])))
        for mat, nv, nt in s['materials']:
            print('    %-32s v=%-7d t=%d' % (mat, nv, nt))