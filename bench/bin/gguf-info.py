#!/usr/bin/env python3
"""gguf-info.py FILE [PATTERN]: print KV keys matching PATTERN and tensor-name groups (no weights read)."""
import struct, sys, re, collections
f = open(sys.argv[1], "rb"); pat = re.compile(sys.argv[2] if len(sys.argv) > 2 else "mtp|nextn|spec", re.I)
def rd(fmt): return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))
def s(): (n,) = rd("Q"); return f.read(n).decode("utf-8", "replace")
T = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
def val(t):
    if t == 8: return s()
    if t == 9:
        (et, n) = rd("IQ")
        if et in T:
            sz = struct.calcsize(T[et]); 
            if n > 64: f.seek(sz * n, 1); return f"[{n} x {T[et]}]"
            return [rd(T[et])[0] for _ in range(n)]
        v = [val(et) for _ in range(n)]; return v if n <= 8 else f"[{n} items]"
    return rd(T[t])[0]
magic, ver, nt, nkv = rd("4sIQQ")
print("gguf v%d tensors=%d kv=%d" % (ver, nt, nkv))
for _ in range(nkv):
    k = s(); (t,) = rd("I"); v = val(t)
    if pat.search(k) or k in ("general.name", "general.architecture", "general.file_type"): print("KV", k, "=", str(v)[:200])
groups = collections.Counter(); hits = []
for _ in range(nt):
    name = s(); (nd,) = rd("I"); dims = rd("Q" * nd); rd("IQ")
    groups[re.sub(r"\.\d+\.", ".N.", name).split(".")[0] + ("." + name.split(".")[1] if name.startswith("blk") else "")] += 1
    if pat.search(name): hits.append((name, dims))
print("blocks:", len([g for g in groups if g.startswith("blk.")]), "non-blk groups:", {g: n for g, n in groups.items() if not g.startswith("blk.")})
print("tensors matching:", len(hits)); [print("  ", n, d) for n, d in hits[:25]]
