# Local coding-agent bake-off on mixed Quadro cards

Scripts, configs and raw results from a repeat-until-it-holds comparison of open-weight coding models on two pairs of older workstation GPUs (20 GB and 24 GB).

Short answer: Qwen3.8-27B, ThinkingCap and Swift 1.5 tie on score; Swift 1.5 is about 25% faster; thinking off beats medium thinking at these speeds.

## What is here

| Path | What it is |
|---|---|
| `bench/results-tierA-raw.tsv` | One row per module run: id, harness, model, lane, module, hidden tests passed and total, minutes, nudges, lint result |
| `bench/results.tsv` | Earlier legs in one format: module runs, and step-by-step app builds with a one-line cause for every failure |
| `bench/queues/*.txt` | The exact job lists that were run. `r9-void.txt` lists runs left out and why |
| `bench/cfg/bake-*.yaml` | llama-swap entries per lane, with every llama-server flag used |
| `bench/compose.yml` | The two model-server containers, one per CPU socket |
| `bench/image/` | Sandbox image for the agent: no internet, ripgrep baked in |
| `bench/bin/run_tierA.sh`, `prep_tierA.py`, `agent.sh`, `queue.sh` | The module test: stub a module, hide half the tests, run the agent under a time cap, score on the hidden tests |
| `bench/bin/r9-table.py` | Builds the tables in the post from the raw rows |
| `bench/bin/steps.sh`, `plan.sh`, `bench`, `prompts/` | The step-by-step build loop: fresh session per step, test as the done condition, three nudges at most |
| `bench/bin/gate.py` | Rules-only check that a green step is not faked |
| `bench/review/` | Nine labelled past steps, four fake and five honest, and the gate's replay on them |
| `bench/bin/speed.py`, `gguf-info.py`, `fatbin-arch.py`, `tap.py`, `pdl.sh` | Small tools: tokens per second, GGUF tensor listing, which GPU generations a CUDA build has native code for, a request tap, a checksummed downloader |

## What is not here

- The app under test. It is a private project. `prep_tierA.py` shows how a module is stubbed and how tests are split, so you can point it at your own code.
- Model files. Names and quants are in `cfg/`.
- Agent transcripts (30 GB).

Paths, host names and GPU ids are replaced with placeholders (`/opt/bakeoff`, `/opt/models`, `gpu-host`, `GPU-UUID-HERE`), and the app's name is replaced with `camera-app`. The scripts will not run unchanged.

## Method in five lines

1. Pick one real project with tests. For each module: stub every function, keep half the tests visible, hide the rest.
2. Give the agent the README, the layout and the visible tests. Cap it at 40 minutes. Nudge at most three times by pasting the failing output.
3. Score on the hidden tests only.
4. Run every model on the same lane as the baseline, and repeat. Treat 1-2 tests of 42 as noise.
5. A win must repeat. On a tie keep the baseline or take the faster model.

## Hardware and software

- Dual-socket server; P5000 16 GB, 2x RTX 4000 8 GB, RTX A2000 12 GB.
- llama.cpp server build 6d5ac3c (CUDA), llama-swap, opencode 1.19.5.
- Q4_K_M, context 49152, q8 KV cache, MTP draft depth 2.

## Licence

MIT, for the scripts, configs and results alike. See `LICENSE`.
