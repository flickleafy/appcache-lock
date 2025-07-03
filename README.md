# AppCache-Lock

AppCache-Lock is a professional Python utility designed to preload application executables and resource directories into memory. By locking these directories using [vmtouch](https://hoytech.com/vmtouch/), the application helps prevent them from being swapped out, potentially improving performance for frequently used applications and resources.

## Overview

This project consists of the following components:

- **appcache_lock.py**  
  The main Python application that:
  - Searches for application executables listed in `app_commands`.
  - Resolves their real paths and extracts the directories.
  - Adds additional resource directories from `resource_dirs`.
  - Locks these directories in memory using vmtouch with concurrent processing.
  - Provides installation, verification, and management capabilities.

- **app_commands**  
  A text file listing application command names (one per line) that the script will locate in your system's PATH.

- **resource_dirs**  
  A text file listing directories (one per line) that contain resources to be locked in memory.

- **Legacy bash scripts** (now deprecated):
  - `preload-apps.sh`, `installer.sh`, `verify-size.sh` - Original bash implementation

## Features

- **Modern Python Implementation:** Professional, maintainable Python code with proper error handling
- **Intelligent Memory Management:** Automatically respects system memory limits (default: 50% of total RAM)
- **Application Prioritization:** Apps are cached before resource directories to maximize performance impact
- **Concurrent Processing:** Uses ThreadPoolExecutor for efficient parallel vmtouch operations
- **Dynamic Discovery:** Automatically locates application executables and determines their installation directories
- **Memory Locking:** Uses vmtouch to lock directories in RAM, ensuring key data remains in the OS page cache
- **Duplicate Prevention:** Filters out duplicate directories to avoid redundant operations
- **Configuration Management:** Easily update which applications and directories are targeted via configuration files
- **Integrated Installation:** Built-in installer that sets up systemd service for automated execution
- **Comprehensive Analysis:** Calculate and display directory sizes, memory usage, and caching statistics
- **Graceful Shutdown:** Proper signal handling for clean process termination
- **Comprehensive Logging:** Detailed logging with configurable verbosity levels
- **Root Privilege Handling:** Intelligent sudo usage when needed

## Prerequisites

Before installing AppCache-Lock, ensure you have:

- Python 3.6 or higher
- A Unix-like operating system with systemd support
- [vmtouch](https://hoytech.com/vmtouch/) installed and available in your PATH (`sudo apt install vmtouch` on Debian/Ubuntu)
- Root privileges to install the scripts and configure systemd (for installation only)

## Installation

### Quick Installation

1. **Clone or Download the Repository**  
   ```bash
   git clone https://github.com/flickleafy/appcache-lock.git
   cd appcache-lock
   ```

2. **Install as System Service**  
   ```bash
   sudo python3 appcache_lock.py install
   ```

3. **Start the service**  
   ```bash
   sudo systemctl start appcache-lock.service
   ```

### Manual Usage

You can also run AppCache-Lock manually without installing it as a service:

```bash
# Preload applications into memory
python3 appcache_lock.py preload

# Check directory sizes before locking
python3 appcache_lock.py verify-sizes

# Run with verbose output
python3 appcache_lock.py preload --verbose

## Configuration

AppCache-Lock uses two main configuration files:

### app_commands

This file contains the list of application commands that AppCache-Lock will search for. Each command should be on a new line. Comments start with `#`.

```plaintext
# List of application commands to preload
google-chrome
code
firefox
vlc
gimp
libreoffice
```

### resource_dirs

This file contains additional directories to lock into memory. These are typically resource directories that applications use frequently.

```plaintext
# List of resource directories to preload
/opt/google/chrome
/usr/share/code
/usr/share/firefox
/usr/lib/vlc
```

## Command Line Options

```bash
# Basic usage
python3 appcache_lock.py <command> [options]

# Available commands:
preload         # Preload applications into memory with intelligent management
verify-sizes    # Calculate and display directory sizes with memory analysis
install         # Install as system service
uninstall       # Remove system service

# Global options:
--verbose, -v           # Enable verbose output with detailed logging
--config-dir DIR        # Use custom configuration directory
--memory-limit N        # Maximum percentage of system memory to use (default: 50)

# Preload-specific options:
--max-workers N         # Maximum concurrent processes (default: 4)
--timeout N             # Timeout per operation in seconds (default: 300)
```

## Examples

```bash
# Check what directories will be cached and their sizes
python3 appcache_lock.py verify-sizes

# Preload with verbose output
python3 appcache_lock.py --verbose preload

# Use only 30% of system memory for caching
python3 appcache_lock.py --memory-limit 30 preload

# Preload with custom settings
python3 appcache_lock.py preload --max-workers 8 --timeout 600

# Analyze memory usage with detailed output
python3 appcache_lock.py --verbose --memory-limit 40 verify-sizes

# Install as system service
sudo python3 appcache_lock.py install

# Remove system service
sudo python3 appcache_lock.py uninstall
```

## Service Management

After installation, you can manage the service using standard systemctl commands:

```bash
# Start the service
sudo systemctl start appcache-lock.service

# Stop the service
sudo systemctl stop appcache-lock.service

# Check service status
sudo systemctl status appcache-lock.service

# View service logs
sudo journalctl -u appcache-lock.service

# Disable automatic startup
sudo systemctl disable appcache-lock.service

# Enable automatic startup
sudo systemctl enable appcache-lock.service
```
## Performance Impact

AppCache-Lock can significantly improve application startup times and responsiveness by:

- **Reducing Disk I/O:** Frequently accessed files remain in memory
- **Faster Application Startup:** Executables and libraries load from RAM instead of disk
- **Improved Responsiveness:** Resource files are immediately available
- **SSD Longevity:** Reduced read operations extend SSD lifespan

### Benchmarking

Use the `verify-sizes` command to understand memory usage before implementation:

```bash
python3 appcache_lock.py verify-sizes
```

This will show you exactly how much RAM will be used for caching.

## Troubleshooting

### Common Issues

1. **vmtouch not found**
   ```bash
   sudo apt install vmtouch  # Debian/Ubuntu
   sudo yum install vmtouch  # CentOS/RHEL
   ```

2. **Permission denied errors**
   - Ensure you run with appropriate privileges
   - The script automatically uses sudo when needed

3. **Service fails to start**
   ```bash
   # Check service logs
   sudo journalctl -u appcache-lock.service -f
   
   # Verify configuration files exist
   ls -la /usr/local/bin/appcache-lock/
   ```

4. **High memory usage**
   - Use `verify-sizes` to check memory requirements
   - Remove large directories from configuration if needed
   - Monitor with `free -h` or `htop`

### Debug Mode

Run with verbose output for detailed information:

```bash
python3 appcache_lock.py preload --verbose
```

## Migration from Bash Version

If you're upgrading from the bash version:

1. **Backup your configuration:**
   ```bash
   cp app_commands app_commands.backup
   cp resource_dirs resource_dirs.backup
   ```

2. **Uninstall old version:**
   ```bash
   sudo systemctl stop appcache-lock.service
   sudo systemctl disable appcache-lock.service
   sudo rm /etc/systemd/system/appcache-lock.service
   sudo rm -rf /usr/local/bin/appcache-lock
   sudo systemctl daemon-reload
   ```

3. **Install new Python version:**
   ```bash
   sudo python3 appcache_lock.py install
   ```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues on GitHub.

## License

This project is licensed under the GPL-3.0 License - see the LICENSE file for details.

## Changelog

### Version 2.0.0

- Complete rewrite in Python for better maintainability and features
- **Intelligent Memory Management:** Respects system memory limits (configurable, default 50%)
- **Application Prioritization:** Apps cached before resources for maximum performance impact
- **Comprehensive Memory Analysis:** Detailed statistics of memory usage before and after caching
- **Smart Directory Selection:** Automatically selects directories within memory constraints
- Concurrent processing for improved performance
- Built-in installation and service management
- Enhanced error handling and logging
- Configuration validation
- Size calculation and verification
- Graceful shutdown handling

### Version 1.x (Legacy)

- Original bash implementation
- Basic vmtouch integration
- Simple systemd service setup

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
