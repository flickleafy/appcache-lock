#!/usr/bin/env bash
#
# preload-apps.sh
#
# Dynamically find application executables, resolve real paths,
# then lock all directories (including known resource dirs) in RAM using vmtouch,
# avoiding duplicates.

# You may remove 'sudo' below if you run the script as root via systemd unit.
# Or keep it if you want to run it from a non-root context that can sudo without password.

###############################################################################
# 1. Define the commands to find via 'which'
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

###############################################################################
# 2. We'll collect directories in this array, then remove duplicates.
###############################################################################
declare -a directories_to_lock=()

###############################################################################
# 3. Discover directories for each command in PATH
###############################################################################
for cmd in "${app_commands[@]}"; do
  if command -v "$cmd" &>/dev/null; then
    # Resolve the symlink to get the real path of the executable
    real_exe="$(realpath "$(command -v "$cmd")")"
    # Get the directory containing that executable
    exe_dir="$(dirname "$real_exe")"
    echo "Found '$cmd' at '$real_exe' -> adding directory: $exe_dir"
    directories_to_lock+=("$exe_dir")
  else
    echo "Command '$cmd' not found. Skipping..."
  fi
done

###############################################################################
# 4. Preload/lock known resource or data directories
#    Uncomment or add to these as needed.
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
    echo "Adding known resource dir: $dir"
    directories_to_lock+=("$dir")
  fi
done

###############################################################################
# 5. Remove duplicates to avoid locking the same dir multiple times
###############################################################################
unique_dirs=()
declare -A seen
for d in "${directories_to_lock[@]}"; do
  if [[ -z "${seen[$d]}" ]]; then
    unique_dirs+=("$d")
    seen[$d]=1
  fi
done

###############################################################################
# 6. Lock each unique directory with vmtouch
###############################################################################
for udir in "${unique_dirs[@]}"; do
  echo "Locking directory in background with timeout: $udir"
  timeout 300s sudo vmtouch -vl "$udir" &
done

# Wait for all to finish or timeout
wait
echo "All done!"

