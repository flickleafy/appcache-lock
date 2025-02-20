# AppCache-Lock

AppCache-Lock is a utility designed to preload application executables and resource directories into memory. By locking these directories using [vmtouch](https://hoytech.com/vmtouch/), the script helps prevent them from being swapped out, potentially improving performance for frequently used applications and resources.

## Overview

This project consists of the following files:

- **preload-apps.sh**  
  The main script that:
  - Searches for application executables listed in `app_commands`.
  - Resolves their real paths and extracts the directories.
  - Adds additional resource directories from `resource_dirs`.
  - Locks these directories in memory using vmtouch.

- **app_commands**  
  A text file listing application command names (one per line) that the script will locate in your system's PATH.

- **resource_dirs**  
  A text file listing directories (one per line) that contain resources to be locked in memory.

- **installer.sh**  
  An installation script that:
  - Copies the above files into a dedicated folder: `/usr/local/bin/appcache-lock`.
  - Sets up a systemd service to run `preload-apps.sh` automatically at boot.

## Features

- **Dynamic Discovery:** Automatically locates application executables and determines their installation directories.
- **Memory Locking:** Uses vmtouch to lock directories in RAM, ensuring key data remains in the OS page cache.
- **Duplicate Prevention**: Filters out duplicate directories to avoid redundant operations.
- **External Configuration:** Easily update which applications and directories are targeted via the `app_commands` and `resource_dirs` files.
- **Easy Deployment**: An installer that copies files into a dedicated directory and configures a systemd service for automated execution.
- **Automated Startup:** Integrates with systemd to execute the preload script during system boot.

## Prerequisites

Before installing AppCache-Lock, ensure you have:

- A Unix-like operating system with systemd support.
- Bash shell.
- [vmtouch](https://hoytech.com/vmtouch/) installed and available in your PATH. `sudo apt install vmtouch` on Debian/Ubuntu).
- `realpath` command available (typically part of GNU core utilities).
- Root privileges to install the scripts and configure systemd.

## Installation

1. **Clone or Download the Repository**  
   Make sure the repository includes the following files:
   - `preload-apps.sh`
   - `installer.sh`
   - `app_commands`
   - `resource_dirs`

2. **Run the Installer Script**  
   Open a terminal, navigate to the repository directory, and run:

   ```bash
   sudo ./installer.sh
   ```

  This will:

- Create the directory `/usr/local/bin/appcache-lock`.
- Copy `preload-apps.sh`, `app_commands`, and `resource_dirs` into that folder.
- Create a systemd service file named `appcache-lock.service` to run the preload script at boot.
- Reload the systemd daemon and enable the new service.

3. **Start the service manually**  (or reboot to let it run automatically):

   ```bash
   sudo systemctl start appcache-lock.service
   ```

## Configuration

### app\_commands

This file contains the list of application commands that AppCache-Lock will search for. Each command should be on a new line. For example:

```plaintext
# List of application commands
google-chrome
code
```

### resource\_dirs

This file lists the directories that you wish to lock in memory. Each directory should be specified on a separate line. For example:

```plaintext
# List of resource directories
/opt/google/chrome
/usr/share/code
```

Feel free to modify these files to suit your environment.

### Systemd Service

The installer creates a systemd service file at `/etc/systemd/system/appcache-lock.service` with the following configuration:

```ini
[Unit]
Description=Preload and lock specific apps into RAM using appcache-lock
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/appcache-lock/preload-apps.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

This service is set to run once at boot, ensuring that your specified application and resource directories are locked in memory.

## Usage

After installation, the systemd service will automatically run at boot. You can also manage the service manually:

- **Start the Service:**

    ```bash
    sudo systemctl start appcache-lock.service
    ```

- **Check the Service Status:**

    ```bash
    sudo systemctl status appcache-lock.service
    ```

- **Reload Systemd Daemon (if changes are made):**

    ```bash
    sudo systemctl daemon-reload
    ```

## Troubleshooting

- **vmtouch Not Found:**  
    Ensure that vmtouch is installed and its executable is in your system PATH.

- **Service Fails to Start:**  
    Review the service logs using:

    ```bash
    journalctl -u appcache-lock.service
    ```

- **Application Commands Not Found:**  
    Verify that the commands listed in `app_commands` are installed and accessible via your PATH.

- **Permission Issues**  
    Run the installer as root (`sudo ./installer.sh`).

- **File Not Found Errors**  
    Verify that `preload-apps.sh`, `app_commands`, and `resource_dirs` are in the same directory as `installer.sh` before installing.

## Uninstallation

To uninstall AppCache-Lock:

1. Remove the installation directory:

    ```bash
    sudo rm -rf /usr/local/bin/appcache-lock
    ```

2. Delete the systemd service file and reload the daemon:

    ```bash
    sudo rm /etc/systemd/system/appcache-lock.service 
    sudo systemctl daemon-reload 
    sudo systemctl disable appcache-lock.service
    ```

## License

GNU GENERAL PUBLIC LICENSE Version 3

## Contributing

Contributions, feature requests, and bug reports are welcome! Please open an issue or submit a pull request on the repository.
