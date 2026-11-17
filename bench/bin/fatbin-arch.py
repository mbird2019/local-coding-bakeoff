#!/usr/bin/env python3
"""List the CUDA arch (sm_XX) of each .nv_fatbin entry in an ELF. Usage: fatbin-arch.py FILE"""
import struct, subprocess, sys, collections
f = sys.argv[1]
out = subprocess.run(["readelf", "-S", "-W", f], capture_output=True, text=True).stdout
off = size = None
for line in out.splitlines():
    if ".nv_fatbin" in line:
        p = line.split(".nv_fatbin")[1].split()
        off, size = int(p[2], 16), int(p[3], 16)
if off is None: sys.exit("no .nv_fatbin section")
data = open(f, "rb"); data.seek(off); b = data.read(size)
c = collections.Counter(); i = 0
while i + 16 <= len(b):
    magic, ver, hsize, fsize = struct.unpack_from("<IHHQ", b, i)
    if magic != 0xBA55ED50: i += 8; continue
    j = i + hsize; end = j + fsize
    while j + 64 <= end:
        kind, _, eh, esz, csz, _, minor, major, arch = struct.unpack_from("<HHIQIIHHI", b, j)
        c[("PTX" if kind == 1 else "ELF" if kind == 2 else str(kind), arch)] += 1
        j += eh + esz
    i = end
for (k, a), n in sorted(c.items()): print(f"{k} sm_{a}: {n} entries")
