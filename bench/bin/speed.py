#!/usr/bin/env python3
"""local coding bake-off speed check: speed.py PORT MODEL...  One fixed ~3k-token code prompt,
256 output tokens, prints load seconds, prompt tok/s, generation tok/s and per-card VRAM after load."""
import json, subprocess, sys, tarfile, time, urllib.request
port, models = sys.argv[1], sys.argv[2:]
src = tarfile.open("/opt/bakeoff/src/camera-app.tar").extractfile("src/camera-app/mjpeg.py").read().decode()
src += tarfile.open("/opt/bakeoff/src/camera-app.tar").extractfile("src/camera-app/config.py").read().decode()
prompt = "Here are two Python modules.\n\n" + src + "\n\nWrite a pytest test file for the first module. Code only."
def ask(m, n):
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": prompt}], "max_tokens": n,
                       "temperature": 0, "ignore_eos": True}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=1800))
for m in models:
    t = time.time()
    try:
        ask(m, 1)
    except Exception as e:
        print(f"{m}\tLOAD-FAIL\t{e}"); continue
    load = time.time() - t
    vram = subprocess.run(["nvidia-smi", "--query-gpu=pci.bus_id,memory.used", "--format=csv,noheader,nounits"],
                          capture_output=True, text=True).stdout.split("\n")
    vram = " ".join(f"{l.split(',')[0][-7:-5]}:{int(l.split(',')[1])/1024:.1f}G" for l in vram if l)
    ask(m, 8)  # warm the cache path once
    d = ask(m + "", 256)
    # second request with same prompt would hit prompt cache; use timings of a fresh prompt instead
    prompt2 = prompt.replace("pytest", "unittest")
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": prompt2}], "max_tokens": 256,
                       "temperature": 0, "ignore_eos": True}).encode()
    d = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", body,
                  {"Content-Type": "application/json"}), timeout=1800))
    tm = d.get("timings", {})
    print(f"{m}\tload {load:.0f}s\tprompt {tm.get('prompt_n')} tok @ {tm.get('prompt_per_second', 0):.0f} tok/s"
          f"\tgen {tm.get('predicted_n')} tok @ {tm.get('predicted_per_second', 0):.1f} tok/s\t{vram}", flush=True)
