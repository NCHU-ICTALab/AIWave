#!/usr/bin/env bash
set -Eeuo pipefail

# AIWave temporary sharing launcher.
# Starts the current Partner fake, legacy Vendor fake, platform API, Vite, then exposes only Vite through
# a TryCloudflare Quick Tunnel. Ctrl+C stops every process started by this script.

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="${ROOT_DIR}/web/app"
CONTROL_KEY="${VENDOR_FAKE_CONTROL_KEY:-local-demo-key}"
PARTNER_PORT="${PARTNER_FAKE_PORT:-8020}"
LEGACY_VENDOR_PORT="${LEGACY_VENDOR_FAKE_PORT:-8021}"
API_PORT="${AIWAVE_API_PORT:-8000}"
WEB_PORT="${AIWAVE_WEB_PORT:-5173}"
SHARE_DATA_DIR="${AIWAVE_SHARE_DATA_DIR:-${ROOT_DIR}/tmp/cloudflare-demo}"
LOG_ROOT="${ROOT_DIR}/tmp/run-logs"
LOG_DIR="${LOG_ROOT}/$(date +%Y%m%d-%H%M%S)"
RESET_ON_START="${AIWAVE_RESET_ON_START:-1}"
PIDS=()

die() {
  printf '錯誤：%s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "找不到 $1。請先安裝後再執行 bash run.sh。"
}

stop_children() {
  local pid
  trap - EXIT INT TERM
  printf '\n正在停止 AIWave 暫時服務…\n'
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  for pid in "${PIDS[@]:-}"; do
    wait "$pid" >/dev/null 2>&1 || true
  done
  printf '已停止。Log 保留於：%s\n' "$LOG_DIR"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local pid="$3"
  local log_file="$4"
  local attempt
  for attempt in {1..60}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      printf '%s 啟動失敗，最後 40 行 log：\n' "$name" >&2
      tail -n 40 "$log_file" >&2 || true
      return 1
    fi
    if curl --fail --silent --show-error --max-time 1 "$url" >/dev/null 2>&1; then
      printf '✓ %s 已就緒：%s\n' "$name" "$url"
      return 0
    fi
    sleep 0.25
  done
  printf '%s 等待逾時，最後 40 行 log：\n' "$name" >&2
  tail -n 40 "$log_file" >&2 || true
  return 1
}

ensure_port_is_free() {
  local name="$1"
  local url="$2"
  if curl --silent --max-time 1 "$url" >/dev/null 2>&1; then
    die "$name 看起來已在執行（$url）。請先停止原本的服務，避免連到不同資料狀態。"
  fi
}

require_command uv
require_command node
require_command curl
if command -v cloudflared >/dev/null 2>&1; then
  CLOUDFLARED_BIN="cloudflared"
elif command -v cloudflared.exe >/dev/null 2>&1; then
  CLOUDFLARED_BIN="cloudflared.exe"
else
  die "找不到 cloudflared。請依 https://developers.cloudflare.com/tunnel/downloads/ 安裝。"
fi

[[ -d "${WEB_DIR}/node_modules" ]] || die "前端依賴尚未安裝，請先執行：cd web/app && npm install"
[[ -f "${WEB_DIR}/node_modules/vite/bin/vite.js" ]] || die "找不到 Vite，請先執行：cd web/app && npm install"

ensure_port_is_free "Partner fake API" "http://127.0.0.1:${PARTNER_PORT}/healthz"
ensure_port_is_free "Legacy Vendor fake API" "http://127.0.0.1:${LEGACY_VENDOR_PORT}/healthz"
ensure_port_is_free "平台 API" "http://127.0.0.1:${API_PORT}/healthz"
ensure_port_is_free "Vite" "http://127.0.0.1:${WEB_PORT}"

mkdir -p "$SHARE_DATA_DIR" "$LOG_DIR"
trap stop_children EXIT INT TERM

printf 'AIWave 暫時分享環境\n'
printf '  資料目錄：%s\n' "$SHARE_DATA_DIR"
printf '  Log 目錄：%s\n' "$LOG_DIR"
printf '  注意：Quick Tunnel 網址是公開的；測試結束後請按 Ctrl+C。\n\n'

(
  cd "$ROOT_DIR"
  export VENDOR_FAKE_CONTROL_KEY="$CONTROL_KEY"
  export VENDOR_FAKE_HOST="127.0.0.1"
  export VENDOR_FAKE_PORT="$PARTNER_PORT"
  export PARTNER_FAKE_API_KEY="aiwave-partner"
  exec uv run python -m fake_upstreams.partner_app
) >"${LOG_DIR}/partner.log" 2>&1 &
PARTNER_PID="$!"
PIDS+=("$PARTNER_PID")
wait_for_http "Partner fake API" "http://127.0.0.1:${PARTNER_PORT}/healthz" "$PARTNER_PID" "${LOG_DIR}/partner.log"

(
  cd "$ROOT_DIR"
  export VENDOR_FAKE_CONTROL_KEY="$CONTROL_KEY"
  export VENDOR_FAKE_HOST="127.0.0.1"
  export VENDOR_FAKE_PORT="$LEGACY_VENDOR_PORT"
  exec uv run python -m fake_upstreams.vendor_app
) >"${LOG_DIR}/legacy-vendor.log" 2>&1 &
LEGACY_VENDOR_PID="$!"
PIDS+=("$LEGACY_VENDOR_PID")
wait_for_http "Legacy Vendor fake API" "http://127.0.0.1:${LEGACY_VENDOR_PORT}/healthz" "$LEGACY_VENDOR_PID" "${LOG_DIR}/legacy-vendor.log"

(
  cd "$ROOT_DIR"
  export DATA_DIR="$SHARE_DATA_DIR"
  export PROVIDER_MODE="standard"
  export PARTNER_MODE="fake"
  export PARTNER_FAKE_URL="http://127.0.0.1:${PARTNER_PORT}"
  export PARTNER_API_KEY="aiwave-partner"
  export VENDOR_MODE="fake"
  export VENDOR_FAKE_URL="http://127.0.0.1:${LEGACY_VENDOR_PORT}"
  export VENDOR_FAKE_CONTROL_KEY="$CONTROL_KEY"
  export DEMO_RESET_ENABLED="true"
  exec uv run uvicorn api.app:app --host 127.0.0.1 --port "$API_PORT"
) >"${LOG_DIR}/api.log" 2>&1 &
API_PID="$!"
PIDS+=("$API_PID")
wait_for_http "平台 API" "http://127.0.0.1:${API_PORT}/healthz" "$API_PID" "${LOG_DIR}/api.log"

if [[ "$RESET_ON_START" == "1" ]]; then
  curl --fail --silent --show-error \
    -X POST \
    -H "X-Fake-Control-Key: ${CONTROL_KEY}" \
    "http://127.0.0.1:${LEGACY_VENDOR_PORT}/__fake__/reset" >/dev/null
  curl --fail --silent --show-error \
    -X POST \
    -H "Authorization: Bearer aiwave-admin" \
    "http://127.0.0.1:${API_PORT}/api/v1/platform/demo/reset" >/dev/null
  printf '✓ 已同步還原平台、Partner fake 與 legacy Vendor fake 的初始 Demo 資料\n'
fi

(
  cd "$WEB_DIR"
  export VITE_API_TARGET="http://127.0.0.1:${API_PORT}"
  # Vite 官方提供的額外 host 白名單；只放行 TryCloudflare，不使用 allowedHosts=true。
  export __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=".trycloudflare.com"
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEB_PORT" --strictPort
) >"${LOG_DIR}/web.log" 2>&1 &
WEB_PID="$!"
PIDS+=("$WEB_PID")
wait_for_http "Vite" "http://127.0.0.1:${WEB_PORT}" "$WEB_PID" "${LOG_DIR}/web.log"

if [[ -f "${HOME:-}/.cloudflared/config.yml" || -f "${HOME:-}/.cloudflared/config.yaml" ]]; then
  printf '\n提醒：Cloudflare 官方說 Quick Tunnel 不支援現有 config.yml/config.yaml；若啟動失敗，請暫時改名該檔案。\n'
fi

printf '\nCloudflare 正在建立公開測試網址。請把下方產生的 https://*.trycloudflare.com 分享給同學。\n'
printf '按 Ctrl+C 會同時停止 Tunnel、Vite、平台 API 與兩個 fake upstream。\n\n'

"$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:${WEB_PORT}"
