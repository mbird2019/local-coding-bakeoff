FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip git ffmpeg ca-certificates curl \
      libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0 \
      libxkbcommon-x11-0 libxcb-cursor0 procps \
    && rm -rf /var/lib/apt/lists/*
# Project toolchain the agents' code runs in
RUN python3 -m venv /opt/proj && /opt/proj/bin/pip install --no-cache-dir "PySide6>=6.5" pytest ruff hatchling
# Coding agents
RUN python3 -m venv /opt/aider && /opt/aider/bin/pip install --no-cache-dir aider-chat
RUN python3 -m venv /opt/mini && /opt/mini/bin/pip install --no-cache-dir mini-swe-agent
RUN npm install -g opencode-ai @qwen-code/qwen-code @anthropic-ai/claude-code && npm cache clean --force
RUN useradd -m -u 1500 agent
ENV PATH=/opt/proj/bin:/opt/aider/bin:/opt/mini/bin:$PATH QT_QPA_PLATFORM=offscreen
USER agent
WORKDIR /work
