# Finds the Slay the Spire 2 install. Sourced by plugin/build.sh and install/install_bridge.sh.
#
# Override with:
#   STS2_GAME_DIR       the game folder ("Slay the Spire 2"), for the install script and for finding the data folder
#   STS2_GAME_DATA_DIR  the folder that holds sts2.dll, for the build
# Without them the game is looked for in the usual Steam places (Linux native, snap, Flatpak, macOS) and in
# every library folder Steam lists in libraryfolders.vdf.

sts2_steam_roots() {
  local root
  for root in \
      "$HOME/snap/steam/common/.local/share/Steam" \
      "$HOME/.local/share/Steam" \
      "$HOME/.steam/steam" \
      "$HOME/.steam/root" \
      "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" \
      "$HOME/Library/Application Support/Steam"; do
    if [ -d "$root/steamapps" ]; then
      echo "$root"
    fi
  done
  return 0
}

# Every Steam root, then every library folder those list.
sts2_library_dirs() {
  local root vdf
  while IFS= read -r root; do
    echo "$root"
    vdf="$root/steamapps/libraryfolders.vdf"
    if [ -f "$vdf" ]; then
      sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)".*/\1/p' "$vdf"
    fi
  done < <(sts2_steam_roots)
  return 0
}

# Prints the game folder, or fails.
sts2_find_game_root() {
  if [ -n "${STS2_GAME_DIR:-}" ]; then
    [ -d "$STS2_GAME_DIR" ] || return 1
    echo "$STS2_GAME_DIR"
    return 0
  fi
  local lib game
  while IFS= read -r lib; do
    game="$lib/steamapps/common/Slay the Spire 2"
    if [ -d "$game" ]; then
      echo "$game"
      return 0
    fi
  done < <(sts2_library_dirs)
  return 1
}

# The folder with sts2.dll inside a game folder, or fails.
sts2_data_dir_of() {
  local dir
  for dir in \
      "$1/data_sts2_linuxbsd_x86_64" \
      "$1/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64" \
      "$1/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_x86_64"; do
    if [ -f "$dir/sts2.dll" ]; then
      echo "$dir"
      return 0
    fi
  done
  return 1
}

# Where mods go for a game folder.
sts2_mods_dir_of() {
  if [ -d "$1/SlayTheSpire2.app" ]; then
    echo "$1/SlayTheSpire2.app/Contents/MacOS/mods"
  else
    echo "$1/mods"
  fi
}
