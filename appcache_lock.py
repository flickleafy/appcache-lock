#!/usr/bin/env python3
"""
AppCache-Lock: Memory Cache Management System

A professional Python implementation for preloading and locking application 
executables and resource directories into memory using vmtouch to improve 
performance by reducing disk I/O for frequently used applications.

Author: flickleafy
License: GPL-3.0
"""

import argparse
import json
import logging
import os
import psutil
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, NamedTuple
import signal

__version__ = "2.0.0"

class MemoryInfo(NamedTuple):
    """Memory information structure."""
    total: int
    available: int
    used: int
    free: int
    percent: float

class DirectoryInfo(NamedTuple):
    """Directory information structure."""
    path: str
    size: int
    priority: int
    source: str  # 'app' or 'resource'

class AppCacheLock:
    """Main class for managing application cache locking operations."""
    
    def __init__(self, config_dir: Path = None, verbose: bool = False, memory_limit_percent: float = 50.0):
        """
        Initialize AppCache-Lock.
        
        Args:
            config_dir: Directory containing configuration files
            verbose: Enable verbose logging
            memory_limit_percent: Maximum percentage of system memory to use for caching
        """
        self.config_dir = config_dir or Path.cwd()
        self.memory_limit_percent = memory_limit_percent
        self.logger = self._setup_logging(verbose)
        self.app_commands_file = self.config_dir / "app_commands"
        self.resource_dirs_file = self.config_dir / "resource_dirs"
        self.locked_dirs: Set[str] = set()
        self.processes: List[subprocess.Popen] = []
        
        # Handle signals for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self, verbose: bool) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('appcache-lock')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        return logger
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._cleanup_processes()
        sys.exit(0)
    
    def _cleanup_processes(self) -> None:
        """Clean up running vmtouch processes."""
        for process in self.processes:
            if process.poll() is None:  # Process is still running
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        self.processes.clear()
    
    def get_memory_info(self) -> MemoryInfo:
        """
        Get current system memory information.
        
        Returns:
            MemoryInfo object with memory statistics
        """
        memory = psutil.virtual_memory()
        return MemoryInfo(
            total=memory.total,
            available=memory.available,
            used=memory.used,
            free=memory.free,
            percent=memory.percent
        )
    
    def get_memory_limit(self) -> int:
        """
        Calculate the maximum memory that can be used for caching.
        
        Returns:
            Maximum cache size in bytes
        """
        memory_info = self.get_memory_info()
        limit = int(memory_info.total * (self.memory_limit_percent / 100))
        self.logger.debug(f"Memory limit set to {self._format_size(limit)} "
                         f"({self.memory_limit_percent}% of {self._format_size(memory_info.total)})")
        return limit
    
    def log_memory_statistics(self, before: MemoryInfo, after: MemoryInfo, cached_size: int) -> None:
        """
        Log detailed memory statistics before and after caching.
        
        Args:
            before: Memory info before caching
            after: Memory info after caching
            cached_size: Total size of cached data
        """
        self.logger.info("=" * 60)
        self.logger.info("MEMORY STATISTICS")
        self.logger.info("=" * 60)
        self.logger.info(f"Total System RAM:     {self._format_size(before.total)}")
        self.logger.info(f"Memory Limit (50%):   {self._format_size(self.get_memory_limit())}")
        self.logger.info("")
        self.logger.info("BEFORE CACHING:")
        self.logger.info(f"  Used Memory:        {self._format_size(before.used)} ({before.percent:.1f}%)")
        self.logger.info(f"  Available Memory:   {self._format_size(before.available)}")
        self.logger.info("")
        self.logger.info("CACHING OPERATION:")
        self.logger.info(f"  Data Cached:        {self._format_size(cached_size)}")
        self.logger.info("")
        self.logger.info("AFTER CACHING:")
        self.logger.info(f"  Used Memory:        {self._format_size(after.used)} ({after.percent:.1f}%)")
        self.logger.info(f"  Available Memory:   {self._format_size(after.available)}")
        self.logger.info(f"  Memory Increase:    {self._format_size(after.used - before.used)}")
        self.logger.info("=" * 60)
    
    def get_directory_size(self, directory: str) -> int:
        """
        Calculate the total size of a directory and its contents.
        
        Args:
            directory: Path to the directory
            
        Returns:
            Size in bytes, or 0 if directory doesn't exist or is inaccessible
        """
        try:
            total_size = 0
            dir_path = Path(directory)
            
            if not dir_path.exists():
                return 0
                
            for file_path in dir_path.rglob('*'):
                try:
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                except OSError:
                    # Skip files we can't read
                    continue
                    
            return total_size
        except Exception as e:
            self.logger.debug(f"Error calculating size for {directory}: {e}")
            return 0
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format size in bytes to human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string (e.g., "1.5 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def prioritize_directories(self, directories: List[str]) -> List[DirectoryInfo]:
        """
        Analyze directories, calculate sizes, and prioritize them.
        
        Args:
            directories: List of directory paths
            
        Returns:
            List of DirectoryInfo objects sorted by priority
        """
        self.logger.info("Analyzing directory sizes and priorities...")
        dir_info_list = []
        
        # Get app directories (higher priority)
        app_commands = self._load_config_file(self.app_commands_file)
        app_dirs = self._find_executable_directories(app_commands) if app_commands else []
        
        for directory in directories:
            size = self.get_directory_size(directory)
            if size > 0:
                # Determine priority and source
                if directory in app_dirs:
                    priority = 1  # High priority for apps
                    source = "app"
                else:
                    priority = 2  # Lower priority for resources
                    source = "resource"
                
                dir_info = DirectoryInfo(
                    path=directory,
                    size=size,
                    priority=priority,
                    source=source
                )
                dir_info_list.append(dir_info)
        
        # Sort by priority (1=highest) then by size (largest first)
        dir_info_list.sort(key=lambda x: (x.priority, -x.size))
        
        return dir_info_list
    
    def select_directories_within_limit(self, dir_info_list: List[DirectoryInfo]) -> Tuple[List[str], int]:
        """
        Select directories to cache within the memory limit.
        
        Args:
            dir_info_list: List of DirectoryInfo objects sorted by priority
            
        Returns:
            Tuple of (selected_directories, total_size)
        """
        memory_limit = self.get_memory_limit()
        selected_dirs = []
        total_size = 0
        
        self.logger.info(f"Selecting directories within memory limit: {self._format_size(memory_limit)}")
        self.logger.info("")
        self.logger.info("DIRECTORY ANALYSIS:")
        self.logger.info("-" * 80)
        self.logger.info(f"{'Priority':<8} {'Source':<8} {'Size':<12} {'Status':<10} {'Directory'}")
        self.logger.info("-" * 80)
        
        for dir_info in dir_info_list:
            if total_size + dir_info.size <= memory_limit:
                selected_dirs.append(dir_info.path)
                total_size += dir_info.size
                status = "SELECTED"
            else:
                status = "SKIPPED"
            
            self.logger.info(
                f"{dir_info.priority:<8} {dir_info.source:<8} "
                f"{self._format_size(dir_info.size):<12} {status:<10} {dir_info.path}"
            )
        
        self.logger.info("-" * 80)
        self.logger.info(f"Selected: {len(selected_dirs)} directories, "
                        f"Total size: {self._format_size(total_size)}")
        self.logger.info("")
        
        return selected_dirs, total_size
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        try:
            result = subprocess.run(['vmtouch', '--version'], 
                                  capture_output=True, check=True)
            self.logger.debug(f"vmtouch version: {result.stdout.decode().strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error(
                "vmtouch is not installed or not in PATH. "
                "Please install it: sudo apt install vmtouch"
            )
            return False
    
    def _load_config_file(self, file_path: Path) -> List[str]:
        """
        Load configuration from a file, filtering out comments and empty lines.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            List of configuration entries
        """
        if not file_path.exists():
            self.logger.warning(f"Configuration file not found: {file_path}")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Filter out comments and empty lines
            config_entries = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    config_entries.append(line)
            
            self.logger.debug(f"Loaded {len(config_entries)} entries from {file_path}")
            return config_entries
            
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {e}")
            return []
    
    def _find_executable_directories(self, app_commands: List[str]) -> List[str]:
        """
        Find directories containing application executables.
        
        Args:
            app_commands: List of command names to search for
            
        Returns:
            List of directories containing the executables
        """
        directories = []
        
        for cmd in app_commands:
            try:
                # Find the command in PATH
                result = subprocess.run(['which', cmd], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    exe_path = result.stdout.strip()
                    # Resolve symlinks to get the real path
                    real_path = Path(exe_path).resolve()
                    exe_dir = str(real_path.parent)
                    
                    self.logger.info(f"Found '{cmd}' at '{real_path}' -> adding directory: {exe_dir}")
                    directories.append(exe_dir)
                else:
                    self.logger.warning(f"Command '{cmd}' not found in PATH")
                    
            except Exception as e:
                self.logger.error(f"Error finding command '{cmd}': {e}")
        
        return directories
    
    def _validate_directories(self, directories: List[str]) -> List[str]:
        """
        Validate that directories exist and are accessible.
        
        Args:
            directories: List of directory paths
            
        Returns:
            List of valid, existing directories
        """
        valid_dirs = []
        
        for directory in directories:
            dir_path = Path(directory)
            if dir_path.exists() and dir_path.is_dir():
                if os.access(directory, os.R_OK):
                    valid_dirs.append(directory)
                    self.logger.debug(f"Validated directory: {directory}")
                else:
                    self.logger.warning(f"Directory not readable: {directory}")
            else:
                self.logger.warning(f"Directory does not exist: {directory}")
        
        return valid_dirs
    
    def _remove_duplicates(self, directories: List[str]) -> List[str]:
        """
        Remove duplicate directories while preserving order.
        
        Args:
            directories: List of directory paths
            
        Returns:
            List of unique directories
        """
        seen = set()
        unique_dirs = []
        
        for directory in directories:
            # Normalize the path
            normalized = str(Path(directory).resolve())
            if normalized not in seen:
                seen.add(normalized)
                unique_dirs.append(normalized)
        
        duplicates_removed = len(directories) - len(unique_dirs)
        if duplicates_removed > 0:
            self.logger.info(f"Removed {duplicates_removed} duplicate directories")
        
        return unique_dirs
    
    def _lock_directory(self, directory: str, timeout: int = 300) -> Tuple[str, bool]:
        """
        Lock a directory into memory using vmtouch.
        
        Args:
            directory: Directory path to lock
            timeout: Timeout in seconds for the vmtouch command
            
        Returns:
            Tuple of (directory, success_flag)
        """
        try:
            self.logger.info(f"Locking directory: {directory}")
            
            # Use timeout to prevent hanging
            cmd = ['timeout', str(timeout), 'vmtouch', '-vl', directory]
            
            # If not running as root, try with sudo
            if os.geteuid() != 0:
                cmd = ['sudo'] + cmd
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes.append(process)
            _, stderr = process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"Successfully locked: {directory}")
                self.locked_dirs.add(directory)
                return directory, True
            else:
                self.logger.error(f"Failed to lock {directory}: {stderr}")
                return directory, False
                
        except Exception as e:
            self.logger.error(f"Exception while locking {directory}: {e}")
            return directory, False
    
    def calculate_directory_sizes(self, directories: List[str]) -> Dict[str, int]:
        """
        Calculate sizes of directories in MB.
        
        Args:
            directories: List of directory paths
            
        Returns:
            Dictionary mapping directory paths to sizes in MB
        """
        sizes = {}
        total_size_kb = 0
        
        self.logger.info("Calculating directory sizes...")
        
        for directory in directories:
            try:
                result = subprocess.run(
                    ['du', '-s', directory],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                size_kb = int(result.stdout.split()[0])
                size_mb = size_kb // 1024
                sizes[directory] = size_mb
                total_size_kb += size_kb
                
                self.logger.info(f"{size_mb:6d} MB  |  {directory}")
                
            except (subprocess.CalledProcessError, ValueError) as e:
                self.logger.warning(f"Could not calculate size for {directory}: {e}")
                sizes[directory] = 0
        
        total_size_mb = total_size_kb // 1024
        self.logger.info(f"Total size: {total_size_mb} MB")
        
        return sizes
    
    def preload_applications(self, max_workers: int = 4, timeout: int = 300) -> bool:
        """
        Main method to preload applications and resources into memory with memory management.
        
        Args:
            max_workers: Maximum number of concurrent vmtouch processes
            timeout: Timeout in seconds for each vmtouch command
            
        Returns:
            True if all operations completed successfully
        """
        if not self._check_dependencies():
            return False
        
        # Get memory info before caching
        memory_before = self.get_memory_info()
        
        # Load configuration
        app_commands = self._load_config_file(self.app_commands_file)
        resource_dirs = self._load_config_file(self.resource_dirs_file)
        
        if not app_commands and not resource_dirs:
            self.logger.error("No applications or resource directories configured")
            return False
        
        # Collect all directories
        all_directories = []
        
        # Find executable directories
        if app_commands:
            exe_dirs = self._find_executable_directories(app_commands)
            all_directories.extend(exe_dirs)
        
        # Add resource directories
        if resource_dirs:
            all_directories.extend(resource_dirs)
        
        # Validate and deduplicate directories
        valid_dirs = self._validate_directories(all_directories)
        unique_dirs = self._remove_duplicates(valid_dirs)
        
        if not unique_dirs:
            self.logger.error("No valid directories found to lock")
            return False
        
        # Prioritize directories and check memory limits
        dir_info_list = self.prioritize_directories(unique_dirs)
        selected_dirs, total_cache_size = self.select_directories_within_limit(dir_info_list)
        
        if not selected_dirs:
            self.logger.error("No directories selected within memory limit")
            return False
        
        self.logger.info(f"Locking {len(selected_dirs)} directories into memory...")
        
        # Lock directories concurrently
        success_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dir = {
                executor.submit(self._lock_directory, directory, timeout): directory
                for directory in selected_dirs
            }
            
            for future in as_completed(future_to_dir):
                _, success = future.result()
                if success:
                    success_count += 1
        
        # Get memory info after caching
        memory_after = self.get_memory_info()
        
        # Log comprehensive statistics
        self.log_memory_statistics(memory_before, memory_after, total_cache_size)
        
        self.logger.info(
            f"Completed: {success_count}/{len(selected_dirs)} directories locked successfully"
        )
        
        return success_count == len(selected_dirs)
    
    def verify_sizes(self) -> bool:
        """
        Calculate and display sizes of configured directories with memory analysis.
        
        Returns:
            True if verification completed successfully
        """
        # Get current memory info
        memory_info = self.get_memory_info()
        memory_limit = self.get_memory_limit()
        
        # Load configuration
        app_commands = self._load_config_file(self.app_commands_file)
        resource_dirs = self._load_config_file(self.resource_dirs_file)
        
        if not app_commands and not resource_dirs:
            self.logger.error("No applications or resource directories configured")
            return False
        
        # Collect all directories
        all_directories = []
        
        # Find executable directories
        if app_commands:
            exe_dirs = self._find_executable_directories(app_commands)
            all_directories.extend(exe_dirs)
        
        # Add resource directories
        if resource_dirs:
            all_directories.extend(resource_dirs)
        
        # Validate and deduplicate directories
        valid_dirs = self._validate_directories(all_directories)
        unique_dirs = self._remove_duplicates(valid_dirs)
        
        if not unique_dirs:
            self.logger.error("No valid directories found")
            return False
        
        # Prioritize directories and analyze memory usage
        dir_info_list = self.prioritize_directories(unique_dirs)
        selected_dirs, total_cache_size = self.select_directories_within_limit(dir_info_list)
        
        # Display summary
        self.logger.info("")
        self.logger.info("MEMORY ANALYSIS SUMMARY:")
        self.logger.info("=" * 60)
        self.logger.info(f"Total System RAM:     {self._format_size(memory_info.total)}")
        self.logger.info(f"Currently Used:       {self._format_size(memory_info.used)} ({memory_info.percent:.1f}%)")
        self.logger.info(f"Available for Cache:  {self._format_size(memory_limit)}")
        self.logger.info(f"Will be Cached:       {self._format_size(total_cache_size)}")
        self.logger.info(f"Remaining Limit:      {self._format_size(memory_limit - total_cache_size)}")
        self.logger.info("")
        self.logger.info(f"Directories Found:    {len(unique_dirs)}")
        self.logger.info(f"Directories Selected: {len(selected_dirs)}")
        self.logger.info(f"Directories Skipped:  {len(unique_dirs) - len(selected_dirs)}")
        self.logger.info("=" * 60)
        
        if len(selected_dirs) < len(unique_dirs):
            skipped = len(unique_dirs) - len(selected_dirs)
            self.logger.warning(f"{skipped} directories will be skipped due to memory limits")
        
        return True


class AppCacheLockInstaller:
    """Installer class for setting up AppCache-Lock as a system service."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the installer."""
        self.logger = self._setup_logging(verbose)
        self.script_dir = Path(__file__).parent.resolve()
        self.dest_dir = Path("/usr/local/bin/appcache-lock")
        self.service_file = Path("/etc/systemd/system/appcache-lock.service")
    
    def _setup_logging(self, verbose: bool) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('appcache-lock-installer')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        return logger
    
    def _check_root_privileges(self) -> bool:
        """Check if running with root privileges."""
        if os.geteuid() != 0:
            self.logger.error("Please run the installer as root (sudo python3 appcache_lock.py install)")
            return False
        return True
    
    def _copy_files(self) -> bool:
        """Copy necessary files to the destination directory."""
        try:
            # Create destination directory
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created destination directory: {self.dest_dir}")
            
            # Copy the main script
            script_dest = self.dest_dir / "appcache_lock.py"
            shutil.copy2(__file__, script_dest)
            script_dest.chmod(0o755)
            self.logger.info(f"Copied main script to {script_dest}")
            
            # Copy configuration files if they exist
            for config_file in ["app_commands", "resource_dirs"]:
                src_file = self.script_dir / config_file
                if src_file.exists():
                    dest_file = self.dest_dir / config_file
                    shutil.copy2(src_file, dest_file)
                    self.logger.info(f"Copied {config_file} to {dest_file}")
                else:
                    # Create example file if original doesn't exist
                    example_file = self.script_dir / f"{config_file}.example"
                    if example_file.exists():
                        dest_file = self.dest_dir / config_file
                        shutil.copy2(example_file, dest_file)
                        self.logger.info(f"Copied {config_file}.example to {dest_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying files: {e}")
            return False
    
    def _create_systemd_service(self) -> bool:
        """Create systemd service file."""
        try:
            service_content = f"""[Unit]
Description=AppCache-Lock - Preload and lock apps into RAM
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {self.dest_dir}/appcache_lock.py preload --config-dir {self.dest_dir}
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
"""
            
            with open(self.service_file, 'w') as f:
                f.write(service_content)
            
            self.logger.info(f"Created systemd service file: {self.service_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating systemd service: {e}")
            return False
    
    def _enable_service(self) -> bool:
        """Enable and configure the systemd service."""
        try:
            # Reload systemd daemon
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            self.logger.info("Reloaded systemd daemon")
            
            # Enable the service
            subprocess.run(['systemctl', 'enable', 'appcache-lock.service'], check=True)
            self.logger.info("Enabled appcache-lock.service")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error configuring systemd service: {e}")
            return False
    
    def install(self) -> bool:
        """Perform the complete installation."""
        if not self._check_root_privileges():
            return False
        
        self.logger.info("Starting AppCache-Lock installation...")
        
        if not self._copy_files():
            return False
        
        if not self._create_systemd_service():
            return False
        
        if not self._enable_service():
            return False
        
        self.logger.info("Installation completed successfully!")
        self.logger.info("You can now:")
        self.logger.info("  - Start the service: sudo systemctl start appcache-lock.service")
        self.logger.info("  - Check status: sudo systemctl status appcache-lock.service")
        self.logger.info("  - The service will start automatically on boot")
        
        return True
    
    def uninstall(self) -> bool:
        """Remove AppCache-Lock from the system."""
        if not self._check_root_privileges():
            return False
        
        try:
            # Stop and disable service
            subprocess.run(['systemctl', 'stop', 'appcache-lock.service'], 
                         capture_output=True)
            subprocess.run(['systemctl', 'disable', 'appcache-lock.service'], 
                         capture_output=True)
            
            # Remove service file
            if self.service_file.exists():
                self.service_file.unlink()
                self.logger.info(f"Removed service file: {self.service_file}")
            
            # Remove installation directory
            if self.dest_dir.exists():
                shutil.rmtree(self.dest_dir)
                self.logger.info(f"Removed installation directory: {self.dest_dir}")
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            
            self.logger.info("AppCache-Lock uninstalled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during uninstall: {e}")
            return False


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="AppCache-Lock: Memory Cache Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s preload                    # Preload apps with default config
  %(prog)s preload --verbose          # Preload with verbose output
  %(prog)s preload --memory-limit 40  # Use 40%% of system memory
  %(prog)s verify-sizes               # Check sizes of configured directories
  %(prog)s install                    # Install as system service
  %(prog)s uninstall                  # Remove system service
        """
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--config-dir', type=Path, default=Path.cwd(),
                       help='Directory containing config files (default: current directory)')
    parser.add_argument('--memory-limit', type=float, default=50.0,
                       help='Maximum percentage of system memory to use for caching (default: 50)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Preload command
    preload_parser = subparsers.add_parser('preload', 
                                          help='Preload applications into memory')
    preload_parser.add_argument('--max-workers', type=int, default=4,
                               help='Maximum concurrent processes (default: 4)')
    preload_parser.add_argument('--timeout', type=int, default=300,
                               help='Timeout for each lock operation in seconds (default: 300)')
    
    # Verify sizes command
    subparsers.add_parser('verify-sizes', 
                         help='Calculate and display directory sizes')
    
    # Install command
    subparsers.add_parser('install', 
                         help='Install as system service')
    
    # Uninstall command
    subparsers.add_parser('uninstall', 
                         help='Remove system service')
    
    args = parser.parse_args()
    
    # Validate memory limit
    if not 1 <= args.memory_limit <= 90:
        print("Error: Memory limit must be between 1 and 90 percent", file=sys.stderr)
        sys.exit(1)
    
    if args.command == 'preload':
        app = AppCacheLock(
            config_dir=args.config_dir, 
            verbose=args.verbose,
            memory_limit_percent=args.memory_limit
        )
        success = app.preload_applications(
            max_workers=args.max_workers,
            timeout=args.timeout
        )
        sys.exit(0 if success else 1)
    
    elif args.command == 'verify-sizes':
        app = AppCacheLock(
            config_dir=args.config_dir, 
            verbose=args.verbose,
            memory_limit_percent=args.memory_limit
        )
        success = app.verify_sizes()
        sys.exit(0 if success else 1)
    
    elif args.command == 'install':
        installer = AppCacheLockInstaller(verbose=args.verbose)
        success = installer.install()
        sys.exit(0 if success else 1)
    
    elif args.command == 'uninstall':
        installer = AppCacheLockInstaller(verbose=args.verbose)
        success = installer.uninstall()
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
