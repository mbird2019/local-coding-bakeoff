#!/bin/bash
# Inside the sandbox: run one harness once on /home/agent/prompt.txt against $URL ($MODEL).
# Env: H URL MODEL MOD (MOD optional: files to hand aider). Working dir /work.
set -u
cd /work
[ -d /work/.venv ] && export PATH=/work/.venv/bin:$PATH VIRTUAL_ENV=/work/.venv
P=$(cat /home/agent/prompt.txt)
export OPENAI_API_KEY=none OPENAI_BASE_URL=$URL/v1 OPENAI_API_BASE=$URL/v1
case "$H" in
aider)
  files=()
  [ -n "${MOD:-}" ] && files=(src/camera-app/$MOD.py)
  [ -n "${FILES:-}" ] && read -r -a files <<< "$FILES"
  aider --model "openai/$MODEL" --openai-api-base "$URL/v1" --openai-api-key none \
    --yes-always --no-auto-commits --no-check-update --no-analytics --no-show-model-warnings \
    --no-pretty --no-stream --no-gitignore \
    ${TEST_CMD:+--test-cmd "$TEST_CMD" --auto-test} \
    --message "$P" "${files[@]}" ;;
opencode)
  # Report 6: warm the model first (a dead or loading server makes opencode retry silently), stdin from /dev/null.
  curl -sf -m 900 -o /dev/null "$URL/v1/chat/completions" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" || { echo "HEALTH-FAIL $URL $MODEL"; exit 3; }
  mkdir -p ~/.config/opencode
  # RKEEP=1: reasoning model; opencode sends earlier thinking back as reasoning_content (opencode 1.19.5 names this
  # interleaved.field; the report calls it reasoningField).
  RJ=""; [ "${RKEEP:-0}" = 1 ] && RJ=',"reasoning":true,"interleaved":{"field":"reasoning_content"}'
  # Reasoning counts against max_tokens: with output 8192 and --reasoning-budget 8192 a long think ended the turn (finish=length, no edit). Reasoning models get 16384.
  OUT=8192; [ "${RKEEP:-0}" = 1 ] && OUT=16384
  cat > ~/.config/opencode/opencode.json <<EOF
{"\$schema":"https://opencode.ai/config.json","autoupdate":false,"share":"disabled",
 "provider":{"local":{"npm":"@ai-sdk/openai-compatible","name":"local","options":{"baseURL":"$URL/v1","apiKey":"none"},
   "models":{"$MODEL":{"name":"$MODEL","limit":{"context":${CTX:-32768},"output":$OUT}$RJ}}}},
 "model":"local/$MODEL","permission":{"edit":"allow","bash":"allow","webfetch":"deny","external_directory":"allow"}}
EOF
  opencode run --model "local/$MODEL" "$P" < /dev/null ;;
qwen)
  mkdir -p ~/.qwen
  echo '{"security":{"auth":{"selectedType":"openai"}},"selectedAuthType":"openai","usageStatisticsEnabled":false}' > ~/.qwen/settings.json
  OPENAI_MODEL=$MODEL qwen --yolo --openai-base-url "$URL/v1" --openai-api-key none -m "$MODEL" -p "$P" ;;
mini)
  export MSWEA_COST_TRACKING=ignore_errors MSWEA_CONFIGURED=true LITELLM_LOCAL_MODEL_COST_MAP=True
  mini --model "openai/$MODEL" --task "$P" --yolo --exit-immediately ;;
claude)
  export ANTHROPIC_BASE_URL=$URL ANTHROPIC_AUTH_TOKEN=none ANTHROPIC_MODEL=$MODEL ANTHROPIC_SMALL_FAST_MODEL=$MODEL \
    ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_AUTOUPDATER=1 DISABLE_TELEMETRY=1
  claude -p "$P" --dangerously-skip-permissions --model "$MODEL" ;;
*) echo "unknown harness $H"; exit 2 ;;
esac
