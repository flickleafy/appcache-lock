#!/usr/bin/env bash
#
# installer.sh
#
# Copies preload-apps.sh, app_commands, and resource_dirs to
# /usr/local/bin/appcache-lock, and sets up a systemd service to run
# it automatically at boot.

set -e

# 1. Determine the directory where this installer script is located.
SCRIPT_DIR="$( cd -- "$( dirname "$0" )" >/dev/null 2>&1 ; pwd -P )"

# 2. Define source file paths.
SRC_SCRIPT="$SCRIPT_DIR/preload-apps.sh"
SRC_APPCOMMANDS="$SCRIPT_DIR/app_commands"
SRC_RESOURCEDIRS="$SCRIPT_DIR/resource_dirs"

# 3. Define destination directory and file paths.
DEST_DIR="/usr/local/bin/appcache-lock"
DEST_SCRIPT="$DEST_DIR/preload-apps.sh"
SERVICE_FILE="/etc/systemd/system/appcache-lock.service"

# 4. Check for root privileges.
if [[ $EUID -ne 0 ]]; then
  echo "Please run this installer as root (sudo ./installer.sh)."
  exit 1
fi

# 5. Create destination directory if it does not exist.
if [[ ! -d "$DEST_DIR" ]]; then
  echo "Creating destination directory: $DEST_DIR"
  mkdir -p "$DEST_DIR"
fi

# 6. Copy preload-apps.sh to the destination directory.
if [[ ! -f "$SRC_SCRIPT" ]]; then
  echo "Error: $SRC_SCRIPT not found. Make sure preload-apps.sh is in the same directory."
  exit 1
fi

echo "Copying $SRC_SCRIPT to $DEST_SCRIPT"
cp "$SRC_SCRIPT" "$DEST_SCRIPT"
chmod +x "$DEST_SCRIPT"

# 7. Copy app_commands file.
if [[ ! -f "$SRC_APPCOMMANDS" ]]; then
  echo "Error: $SRC_APPCOMMANDS not found. Make sure app_commands is in the same directory."
  exit 1
fi

echo "Copying $SRC_APPCOMMANDS to $DEST_DIR/app_commands"
cp "$SRC_APPCOMMANDS" "$DEST_DIR/app_commands"

# 8. Copy resource_dirs file.
if [[ ! -f "$SRC_RESOURCEDIRS" ]]; then
  echo "Error: $SRC_RESOURCEDIRS not found. Make sure resource_dirs is in the same directory."
  exit 1
fi

echo "Copying $SRC_RESOURCEDIRS to $DEST_DIR/resource_dirs"
cp "$SRC_RESOURCEDIRS" "$DEST_DIR/resource_dirs"

# 9. Create systemd service file.
echo "Creating systemd service file: $SERVICE_FILE"
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Preload and lock specific apps into RAM using appcache-lock
After=network.target

[Service]
Type=oneshot
ExecStart=$DEST_SCRIPT
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# 10. Reload systemd and enable the service.
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling appcache-lock.service to run at boot..."
systemctl enable appcache-lock.service

echo "Installation complete!"
echo "You can now manually start the service with: sudo systemctl start appcache-lock.service"
echo "Or simply reboot, and it will run automatically."
