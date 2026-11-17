# local coding bake-off 2026-11-16: opencode Glob/Grep need rg on PATH (no internet in the sandbox to fetch it).
FROM bakeoff-sandbox:v1
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep && rm -rf /var/lib/apt/lists/*
USER agent
