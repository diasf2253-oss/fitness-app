#!/bin/bash
# Wrapper so the preview tool can launch Vite with nvm's Node on PATH.
export PATH="/Users/felipedias/.nvm/versions/node/v22.22.3/bin:$PATH"
cd "$(dirname "$0")"
exec npm run dev
