#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$SCRIPT_DIR/bridge_plugin"
DLL="$BUNDLE_DIR/STS2_Bridge.dll"
JSON="$BUNDLE_DIR/STS2_Bridge.json"

source "$SCRIPT_DIR/../game_paths.sh"

if [ ! -f "$DLL" ] || [ ! -f "$JSON" ]; then
  echo "ERROR: bridge plugin files not found in $BUNDLE_DIR" >&2
  echo "Build the bridge first: ../plugin/build.sh" >&2
  exit 1
fi

GAME_ROOT="${1:-$(sts2_find_game_root || true)}"
if [ -z "$GAME_ROOT" ] || [ ! -d "$GAME_ROOT" ]; then
  echo "ERROR: Could not find the Slay the Spire 2 folder." >&2
  echo "Usage: ./install_bridge.sh /path/to/'Slay the Spire 2'  (or set STS2_GAME_DIR)" >&2
  exit 1
fi
MOD_DIR="$(sts2_mods_dir_of "$GAME_ROOT")/STS2_Bridge"

mkdir -p "$MOD_DIR"
cp "$DLL" "$MOD_DIR/STS2_Bridge.dll"
cp "$JSON" "$MOD_DIR/STS2_Bridge.json"

echo "Installed bridge plugin to:"
echo "  $MOD_DIR/STS2_Bridge.dll"
echo "  $MOD_DIR/STS2_Bridge.json"
