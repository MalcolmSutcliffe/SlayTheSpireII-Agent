#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ./build.sh [--install] [/path/to/game/data/dir]
DO_INSTALL=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--install" ]; then
    DO_INSTALL=1
  else
    ARGS+=("$arg")
  fi
done
set -- "${ARGS[@]+"${ARGS[@]}"}"
PROJECT="$SCRIPT_DIR/STS2_Bridge.csproj"
OUT_DIR="$SCRIPT_DIR/out/STS2_Bridge"
CONFIGURATION="${CONFIGURATION:-Release}"
DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-$SCRIPT_DIR/.dotnet-cli-home}"
INSTALL_DIR="$SCRIPT_DIR/../install/bridge_plugin"

source "$SCRIPT_DIR/../game_paths.sh"

mkdir -p "$DOTNET_CLI_HOME"
mkdir -p "$INSTALL_DIR"
export DOTNET_CLI_HOME
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

find_dotnet() {
  if [ -n "${DOTNET_ROOT:-}" ] && [ -x "$DOTNET_ROOT/dotnet" ]; then
    echo "$DOTNET_ROOT/dotnet"
    return
  fi
  if [ -x "$HOME/.dotnet-arm64/dotnet" ]; then
    echo "$HOME/.dotnet-arm64/dotnet"
    return
  fi
  if [ -x "$HOME/.dotnet/dotnet" ]; then
    echo "$HOME/.dotnet/dotnet"
    return
  fi
  if command -v dotnet >/dev/null 2>&1; then
    command -v dotnet
    return
  fi
  # not on PATH (a terminal that did not read the shell profile): the places an SDK is usually put
  local dir
  for dir in "$HOME/dotnet" "$HOME/.local/share/dotnet" "/usr/share/dotnet" "/usr/lib/dotnet" "/opt/dotnet"; do
    if [ -x "$dir/dotnet" ]; then
      echo "$dir/dotnet"
      return
    fi
  done
  return 1
}

detect_game_data_dir() {
  if [ -n "${STS2_GAME_DATA_DIR:-}" ]; then
    echo "${STS2_GAME_DATA_DIR}"
    return
  fi
  local root
  root="$(sts2_find_game_root)" || return 1
  sts2_data_dir_of "$root"
}

DOTNET_BIN="$(find_dotnet || true)"
if [ -z "$DOTNET_BIN" ]; then
  echo "ERROR: dotnet not found. Install .NET 9 SDK first." >&2
  exit 1
fi

GAME_DATA_DIR="${1:-$(detect_game_data_dir || true)}"
if [ -z "$GAME_DATA_DIR" ]; then
  echo "ERROR: Could not detect Slay the Spire 2 data directory." >&2
  echo "Usage: ./build.sh /path/to/data_sts2_linuxbsd_x86_64" >&2
  echo "Or set STS2_GAME_DIR (the 'Slay the Spire 2' folder) or STS2_GAME_DATA_DIR (the folder with sts2.dll)." >&2
  exit 1
fi

if [ ! -f "$GAME_DATA_DIR/sts2.dll" ]; then
  echo "ERROR: sts2.dll not found in $GAME_DATA_DIR" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "Building STS2_Bridge"
echo "dotnet      : $DOTNET_BIN"
echo "game data   : $GAME_DATA_DIR"
echo "output dir  : $OUT_DIR"
echo

"$DOTNET_BIN" build "$PROJECT" \
  -c "$CONFIGURATION" \
  -o "$OUT_DIR" \
  -p:STS2GameDataDir="$GAME_DATA_DIR"

cp "$OUT_DIR/STS2_Bridge.dll" "$INSTALL_DIR/STS2_Bridge.dll"
cp "$SCRIPT_DIR/bridge_manifest.json" "$INSTALL_DIR/STS2_Bridge.json"

echo
echo "Build succeeded."
echo "Install these files into <game_install>/mods/:"
echo "  $OUT_DIR/STS2_Bridge.dll"
echo "  $SCRIPT_DIR/bridge_manifest.json  ->  STS2_Bridge.json"
echo
echo "Project-local install bundle updated at:"
echo "  $INSTALL_DIR/STS2_Bridge.dll"
echo "  $INSTALL_DIR/STS2_Bridge.json"

if [ "$DO_INSTALL" = "1" ]; then
  echo
  # a data dir given by hand sits directly in the game folder on Linux; otherwise the install script finds the game itself
  INSTALL_ARGS=()
  case "$(basename "$GAME_DATA_DIR")" in
    data_sts2_linuxbsd_*) INSTALL_ARGS=("$(dirname "$GAME_DATA_DIR")") ;;
  esac
  "$SCRIPT_DIR/../install/install_bridge.sh" "${INSTALL_ARGS[@]+"${INSTALL_ARGS[@]}"}"
  echo "Restart the game to load the new build."
fi
