#!/usr/bin/env bash
#
# verify-size.sh
#
# Dynamically find application executables, resolve real paths,
# and then calculate the size of these directories (in MB).
# Also includes known resource directories.
#

###############################################################################
# 1. Identify directories via the main executables in PATH.
###############################################################################
# Ensure the file with app commands exists
if [[ ! -f "app_commands" ]]; then
  echo "Error: app_commands file not found."
  exit 1
fi

# Load app commands from file into the array.
# Each line in the file becomes an element in the array.
mapfile -t app_commands < <(grep -v '^\s*#' app_commands)

# declare -a app_commands=(
#   "google-chrome"
#   "code"               # VSCode
# )

# We'll store all discovered directories here.
declare -a directories_to_check=()

for cmd in "${app_commands[@]}"; do
  if command -v "$cmd" &>/dev/null; then
    # Resolve the symlink to get the real path of the executable
    real_exe="$(realpath "$(command -v "$cmd")")"
    # Get the directory containing that executable
    exe_dir="$(dirname "$real_exe")"
    # Check that it's a valid directory (it should be, but just in case)
    if [ -d "$exe_dir" ]; then
      echo "Found '$cmd' at '$real_exe' (directory: '$exe_dir')"
      directories_to_check+=("$exe_dir")
    fi
  else
    echo "Command '$cmd' not found in PATH. Skipping..."
  fi
done

###############################################################################
# 2. (Optional) Include known resource/data directories.
#    (These are common install/resource paths for each app.)
###############################################################################
# Ensure the file with resource dirs exists
if [[ ! -f "resource_dirs" ]]; then
  echo "Error: resource_dirs file not found."
  exit 1
fi

# Load resource directories from file into the array.
mapfile -t resource_dirs < <(grep -v '^\s*#' resource_dirs)

# declare -a resource_dirs=(
#   "/opt/google/chrome"    # Chrome typically installs here
#   "/usr/share/code"       # VSCode resources
# )

for dir in "${resource_dirs[@]}"; do
  if [ -d "$dir" ]; then
    directories_to_check+=("$dir")
  fi
done

###############################################################################
# 3. Remove duplicates (optional) to avoid double-counting the same directory.
###############################################################################
unique_dirs=()
declare -A seen
for d in "${directories_to_check[@]}"; do
  if [[ -z "${seen[$d]}" ]]; then
    unique_dirs+=("$d")
    seen[$d]=1
  fi
done

###############################################################################
# 4. Calculate and display directory sizes.
###############################################################################
total_size_kb=0

echo
echo "=== Directory Size Summary (MB) ==="

for d in "${unique_dirs[@]}"; do
  # 'du -s' gives size in 1K blocks by default.
  size_kb=$(du -s "$d" 2>/dev/null | cut -f1)
  if [[ -n "$size_kb" ]]; then
    size_mb=$(( size_kb / 1024 ))   # integer division (rounded down)
    echo "$(printf '%6d' "$size_mb") MB  |  $d"
    (( total_size_kb += size_kb ))
  else
    echo "   ??? MB  |  $d (couldn't determine size)"
  fi
done

total_size_mb=$(( total_size_kb / 1024 ))

echo "-------------------------------------"
echo "Total: $total_size_mb MB"
echo

exit 0

