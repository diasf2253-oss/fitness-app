#!/bin/bash
# Wrapper so the preview tool can launch Vite with nvm's Node on PATH.
if ! command -v npm >/dev/null 2>&1; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
fi
cd "$(dirname "$0")"
exec npm run dev
