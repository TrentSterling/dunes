#!/bin/sh
cd "$(dirname "$0")"
( sleep 1; (xdg-open http://localhost:8080 || open http://localhost:8080) >/dev/null 2>&1 ) &
[ -d node_modules/ws ] || npm install --no-audit --no-fund
node server.js 8080
