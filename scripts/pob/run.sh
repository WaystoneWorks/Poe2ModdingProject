#!/usr/bin/env bash
# Runs a Lua driver inside headless PoB2: scripts/pob/run.sh <driver.lua> [args...]
set -euo pipefail
hub="$(cd "$(dirname "$0")/../.." && pwd)"
driver="$(realpath "$1")"; shift
cd "$hub/third_party/PathOfBuilding-PoE2/src"
export LUA_PATH="$hub/scripts/pob/?.lua;../runtime/lua/?.lua;../runtime/lua/?/init.lua;;"
export LUA_CPATH="$hub/third_party/lua-utf8/?.so;;"
exec luajit "$driver" "$@"
