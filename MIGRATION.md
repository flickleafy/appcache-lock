# Migration Guide: Bash to Python

This guide helps you migrate from the legacy bash implementation to the new Python version of AppCache-Lock.

## Why Migrate?

The Python version offers several advantages:

- **Better Performance:** Concurrent processing of multiple directories
- **Improved Reliability:** Better error handling and validation
- **Enhanced Features:** Built-in size calculation, verbose logging, configuration validation
- **Easier Maintenance:** Modern, well-documented code
- **Professional Integration:** Proper signal handling and graceful shutdown

## Migration Steps

### 1. Backup Current Configuration

```bash
# Backup your current configuration files
cp app_commands app_commands.backup
cp resource_dirs resource_dirs.backup
```

### 2. Test the New Version

Before removing the old installation, test the new Python version:

```bash
# Check what will be cached and sizes
python3 appcache_lock.py verify-sizes

# Test preloading (dry run without service)
python3 appcache_lock.py preload --verbose
```

### 3. Remove Old Bash Installation

```bash
# Stop the old service
sudo systemctl stop appcache-lock.service
sudo systemctl disable appcache-lock.service

# Remove old files
sudo rm /etc/systemd/system/appcache-lock.service
sudo rm -rf /usr/local/bin/appcache-lock

# Reload systemd
sudo systemctl daemon-reload
```

### 4. Install Python Version

```bash
# Install the new Python version
sudo python3 appcache_lock.py install

# Start the new service
sudo systemctl start appcache-lock.service

# Verify it's working
sudo systemctl status appcache-lock.service
```

## Configuration Compatibility

Your existing `app_commands` and `resource_dirs` files are fully compatible with the Python version. No changes are needed.

## Service Differences

| Feature | Bash Version | Python Version |
|---------|-------------|----------------|
| Concurrent Processing | No | Yes (ThreadPoolExecutor) |
| Error Handling | Basic | Comprehensive |
| Logging | Echo statements | Professional logging |
| Size Verification | Separate script | Built-in command |
| Installation | Separate installer | Built-in installer |
| Configuration Validation | None | Full validation |
| Signal Handling | Basic | Graceful shutdown |

## Performance Improvements

The Python version includes several performance optimizations:

- **Parallel Processing:** Multiple directories locked simultaneously
- **Intelligent Deduplication:** More efficient duplicate removal
- **Better Resource Management:** Proper cleanup of processes
- **Configurable Timeouts:** Prevent hanging operations

## Troubleshooting Migration Issues

### Service Won't Start

```bash
# Check service logs
sudo journalctl -u appcache-lock.service -f

# Verify Python script
python3 appcache_lock.py preload --verbose
```

### Configuration Issues

```bash
# Verify configuration files
ls -la app_commands resource_dirs

# Test configuration loading
python3 appcache_lock.py verify-sizes
```

### Permission Problems

```bash
# Ensure script is executable
chmod +x appcache_lock.py

# Verify vmtouch is available
which vmtouch
```

## Rollback Procedure

If you need to rollback to the bash version:

1. Stop the Python service:
   ```bash
   sudo systemctl stop appcache-lock.service
   sudo python3 appcache_lock.py uninstall
   ```

2. Reinstall bash version:
   ```bash
   sudo ./installer.sh
   ```

## Support

If you encounter issues during migration:

1. Check the logs: `sudo journalctl -u appcache-lock.service`
2. Run with verbose output: `python3 appcache_lock.py preload --verbose`
3. Open an issue on GitHub with the error details
