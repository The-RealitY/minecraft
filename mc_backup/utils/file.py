import os
import tarfile
import zipfile
import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

from mc_backup import ProcessWebhook


class FileArchive:
    def __init__(self, wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION):
        self.webhook: ProcessWebhook = wh
        self.log = log
        self.mc_data_path = MC_DATA_PATH
        self.backup_path = BACKUP_PATH
        self.num_backup_retain = RETENTION
        self.filename = None
        self.compression_level = 6  # Balanced compression level
        self.chunk_size = 1024 * 1024  # 1MB chunks for better memory management
        self.max_retries = 3
        self.retry_delay = 2

    def _create_archived_path(self, ext):
        """
        Create an archived file path with a timestamped name.

        :param ext: Extension for the archive file (e.g., .zip or .tar.gz)
        :return: Full path to the archive file
        """
        os.makedirs(self.backup_path, exist_ok=True)
        file_prefix = "MCB"
        tz = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"{file_prefix}_{tz}{ext}"
        arch_path = os.path.join(self.backup_path, self.filename)
        self.log.info(f"Compress Path: {arch_path}")
        self.webhook.edit_message(f"Compress Path: {arch_path}")
        return arch_path

    def _validate_source_path(self):
        """
        Validate that the source directory exists and is accessible.
        """
        src_path = Path(self.mc_data_path)
        if not src_path.exists() or not src_path.is_dir():
            self.log.error(f"Source path '{self.mc_data_path}' does not exist or is not a directory.")
            self.webhook.edit_message(f"Source path '{self.mc_data_path}' does not exist or is not a directory.")
            return None
        
        # Check if we have read permissions
        if not os.access(src_path, os.R_OK):
            self.log.error(f"No read permission for source path '{self.mc_data_path}'.")
            self.webhook.edit_message(f"No read permission for source path '{self.mc_data_path}'.")
            return None
            
        return src_path

    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of directory in bytes."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, IOError):
                        continue
        except Exception as e:
            self.log.warning(f"Error calculating directory size: {e}")
        return total_size

    def _check_disk_space(self, required_space: int) -> bool:
        """Check if there's enough disk space for the backup."""
        try:
            statvfs = os.statvfs(self.backup_path)
            available_space = statvfs.f_frsize * statvfs.f_bavail
            return available_space > required_space * 1.2  # 20% buffer
        except Exception as e:
            self.log.warning(f"Could not check disk space: {e}")
            return True  # Assume we have space if we can't check

    def _validate_zip_integrity(self, zip_path: str) -> bool:
        """Validate the integrity of a zip file."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Test the zip file
                bad_file = zip_ref.testzip()
                if bad_file:
                    self.log.error(f"Corrupted file in zip: {bad_file}")
                    return False
                return True
        except Exception as e:
            self.log.error(f"Zip integrity check failed: {e}")
            return False

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file for integrity verification."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.log.warning(f"Could not calculate hash for {file_path}: {e}")
            return ""

    def retain_backup(self):
        """Optimized backup retention with better error handling."""
        try:
            if not os.path.exists(self.backup_path):
                self.log.warning(f"Backup path does not exist: {self.backup_path}")
                return

            # Use os.scandir for better performance
            files_with_mtime = []
            with os.scandir(self.backup_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.endswith(('.zip', '.tar.gz')):
                        try:
                            files_with_mtime.append((entry.name, entry.stat().st_mtime))
                        except (OSError, IOError) as e:
                            self.log.warning(f"Could not get stats for {entry.name}: {e}")
                            continue

            # Sort by modification time (newest first)
            files_with_mtime.sort(key=lambda x: x[1], reverse=True)
            
            if len(files_with_mtime) > self.num_backup_retain:
                files_to_delete = files_with_mtime[self.num_backup_retain:]
                deleted_count = 0
                total_size_freed = 0
                
                for filename, _ in files_to_delete:
                    file_path = os.path.join(self.backup_path, filename)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size_freed += file_size
                        self.log.info(f"Deleted file: {filename} ({file_size / (1024*1024):.2f} MB)")
                    except (OSError, IOError) as e:
                        self.log.error(f"Failed to delete {filename}: {e}")
                        continue
                
                if deleted_count > 0:
                    self.webhook.edit_message(
                        f"Retention cleanup: Deleted {deleted_count} files, "
                        f"freed {total_size_freed / (1024*1024):.2f} MB"
                    )
            else:
                self.log.info(f"Retention folder has {len(files_with_mtime)} files (limit: {self.num_backup_retain}). No cleanup needed.")
                
        except Exception as e:
            self.log.error(f"Error during backup retention: {e}")
            self.webhook.edit_message(f"Error during backup retention: {e}")

    def compress_to_zip(self):
        """
        Compress a directory into a .zip file with progress tracking and integrity validation.
        """
        for attempt in range(self.max_retries):
            try:
                src_path = self._validate_source_path()
                if not src_path:
                    return None

                # Pre-flight checks
                total_size = self._get_directory_size(src_path)
                if total_size == 0:
                    self.log.warning("Source directory is empty")
                    self.webhook.edit_message("Source directory is empty")
                    return None

                if not self._check_disk_space(total_size):
                    self.log.error("Insufficient disk space for backup")
                    self.webhook.edit_message("Insufficient disk space for backup")
                    return None

                dest_path = self._create_archived_path('.zip')
                
                # Progress tracking variables
                processed_files = 0
                processed_size = 0
                start_time = time.time()
                
                self.log.info(f"Starting compression of {total_size / (1024*1024):.2f} MB")
                self.webhook.edit_message(f"Starting compression of {total_size / (1024*1024):.2f} MB")

                with zipfile.ZipFile(dest_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=self.compression_level) as zipf:
                    # Collect all files first for better progress tracking
                    all_files = []
                    for root, _, files in os.walk(src_path):
                        for file in files:
                            file_path = Path(root) / file
                            try:
                                file_size = file_path.stat().st_size
                                all_files.append((file_path, file_path.relative_to(src_path), file_size))
                            except (OSError, IOError) as e:
                                self.log.warning(f"Skipping file {file_path}: {e}")
                                continue

                    total_files = len(all_files)
                    
                    for file_path, arc_name, file_size in all_files:
                        try:
                            # Add file to zip
                            zipf.write(file_path, arc_name)
                            
                            processed_files += 1
                            processed_size += file_size
                            
                            # Update progress every 10 files or 50MB
                            if processed_files % 10 == 0 or processed_size - (processed_files - 10) * (processed_size / max(processed_files, 1)) > 50 * 1024 * 1024:
                                progress = (processed_size / total_size) * 100
                                elapsed = time.time() - start_time
                                speed = processed_size / elapsed / (1024 * 1024) if elapsed > 0 else 0
                                
                                self.webhook.edit_message(
                                    f"Compression progress: {progress:.1f}% "
                                    f"({processed_files}/{total_files} files, "
                                    f"{processed_size / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB, "
                                    f"{speed:.1f} MB/s)"
                                )
                                
                        except (OSError, IOError) as e:
                            self.log.warning(f"Failed to add {file_path} to archive: {e}")
                            continue

                # Validate the created zip file
                if not self._validate_zip_integrity(dest_path):
                    self.log.error("Created zip file failed integrity check")
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    if attempt < self.max_retries - 1:
                        self.log.info(f"Retrying compression (attempt {attempt + 2}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                        continue
                    return None

                # Final statistics
                final_size = os.path.getsize(dest_path)
                compression_ratio = (1 - final_size / total_size) * 100 if total_size > 0 else 0
                elapsed_time = time.time() - start_time
                
                self.log.info(
                    f"Compression completed: {final_size / (1024*1024):.2f} MB "
                    f"({compression_ratio:.1f}% compression) in {elapsed_time:.1f}s"
                )
                self.webhook.edit_message(
                    f"Compression completed: {final_size / (1024*1024):.2f} MB "
                    f"({compression_ratio:.1f}% compression) in {elapsed_time:.1f}s"
                )
                
                return dest_path
                
            except Exception as e:
                self.log.error(f"Compression attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    self.log.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.webhook.edit_message(f"Compression failed after {self.max_retries} attempts: {e}")
                    
        return None

    def decompress_zip(self, backup_name, buffer_size=1024 * 1024):
        """
        Unzips a file with progress tracking and better error handling.
        """
        for attempt in range(self.max_retries):
            try:
                src_path = os.path.join(self.backup_path, backup_name)
                if not os.path.exists(src_path):
                    self.log.error(f"Backup file not found: {src_path}")
                    self.webhook.edit_message(f"Backup file not found: {src_path}")
                    return False

                # Validate zip file before extraction
                if not self._validate_zip_integrity(src_path):
                    self.log.error(f"Backup file is corrupted: {src_path}")
                    self.webhook.edit_message(f"Backup file is corrupted: {src_path}")
                    return False

                dest_path = os.path.join(self.mc_data_path)

                # Backup existing data folder with retry logic
                if os.path.exists(dest_path) and os.path.is_dir(dest_path):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_dest = f"{dest_path}-backup-{timestamp}"
                    
                    for rename_attempt in range(5):
                        try:
                            if os.path.exists(backup_dest):
                                shutil.rmtree(backup_dest)
                            os.rename(dest_path, backup_dest)
                            self.log.info(f"Backed up existing data folder to {backup_dest}")
                            self.webhook.edit_message(f"Backed up existing data folder to {backup_dest}")
                            break
                        except OSError as e:
                            if e.errno == 16:  # Resource busy
                                self.log.warning(f"Rename attempt {rename_attempt+1}: Resource busy, retrying in 3 seconds...")
                                time.sleep(3)
                            else:
                                self.log.error(f"Failed to backup existing data folder: {e}")
                                self.webhook.edit_message(f"Failed to backup existing data folder: {e}")
                                return False
                    else:
                        self.log.error("Failed to backup existing data folder after multiple attempts")
                        self.webhook.edit_message("Failed to backup existing data folder after multiple attempts")
                        return False

                # Create destination directory
                os.makedirs(dest_path, exist_ok=True)

                # Extract with progress tracking
                with zipfile.ZipFile(src_path, 'r') as zip_ref:
                    file_list = zip_ref.infolist()
                    total_files = len([f for f in file_list if not f.is_dir()])
                    extracted_files = 0
                    start_time = time.time()
                    
                    self.log.info(f"Starting extraction of {total_files} files")
                    self.webhook.edit_message(f"Starting extraction of {total_files} files")

                    for file_info in file_list:
                        try:
                            target_path = os.path.join(dest_path, file_info.filename)
                            
                            if file_info.is_dir():
                                os.makedirs(target_path, exist_ok=True)
                            else:
                                # Ensure parent directory exists
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                
                                # Extract file with chunked reading
                                with zip_ref.open(file_info) as source:
                                    with open(target_path, "wb") as target:
                                        while True:
                                            chunk = source.read(buffer_size)
                                            if not chunk:
                                                break
                                            target.write(chunk)
                                
                                extracted_files += 1
                                
                                # Update progress every 10 files
                                if extracted_files % 10 == 0 or extracted_files == total_files:
                                    progress = (extracted_files / total_files) * 100
                                    elapsed = time.time() - start_time
                                    speed = extracted_files / elapsed if elapsed > 0 else 0
                                    
                                    self.webhook.edit_message(
                                        f"Extraction progress: {progress:.1f}% "
                                        f"({extracted_files}/{total_files} files, "
                                        f"{speed:.1f} files/s)"
                                    )
                                    
                        except (OSError, IOError) as e:
                            self.log.warning(f"Failed to extract {file_info.filename}: {e}")
                            continue

                elapsed_time = time.time() - start_time
                self.log.info(f"Extraction completed: {extracted_files} files in {elapsed_time:.1f}s")
                self.webhook.edit_message(f"Extraction completed: {extracted_files} files in {elapsed_time:.1f}s")
                return True
                
            except Exception as e:
                self.log.error(f"Extraction attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    self.log.info(f"Retrying extraction in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.webhook.edit_message(f"Extraction failed after {self.max_retries} attempts: {e}")
                    
        return False

    def compress_to_tar(self):
        """
        Compress a directory into a .tar.gz file with progress tracking.
        """
        for attempt in range(self.max_retries):
            try:
                src_path = self._validate_source_path()
                if not src_path:
                    return None

                # Pre-flight checks
                total_size = self._get_directory_size(src_path)
                if total_size == 0:
                    self.log.warning("Source directory is empty")
                    self.webhook.edit_message("Source directory is empty")
                    return None

                if not self._check_disk_space(total_size):
                    self.log.error("Insufficient disk space for backup")
                    self.webhook.edit_message("Insufficient disk space for backup")
                    return None

                dest_path = self._create_archived_path('.tar.gz')
                start_time = time.time()
                
                self.log.info(f"Starting tar.gz compression of {total_size / (1024*1024):.2f} MB")
                self.webhook.edit_message(f"Starting tar.gz compression of {total_size / (1024*1024):.2f} MB")

                with tarfile.open(dest_path, "w:gz", compresslevel=self.compression_level) as tarf:
                    tarf.add(src_path, arcname=".", recursive=True)

                # Validate the created tar file
                try:
                    with tarfile.open(dest_path, "r:gz") as test_tar:
                        test_tar.getmembers()  # This will raise an exception if corrupted
                except Exception as e:
                    self.log.error(f"Created tar.gz file failed integrity check: {e}")
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    if attempt < self.max_retries - 1:
                        self.log.info(f"Retrying tar.gz compression (attempt {attempt + 2}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                        continue
                    return None

                # Final statistics
                final_size = os.path.getsize(dest_path)
                compression_ratio = (1 - final_size / total_size) * 100 if total_size > 0 else 0
                elapsed_time = time.time() - start_time
                
                self.log.info(
                    f"Tar.gz compression completed: {final_size / (1024*1024):.2f} MB "
                    f"({compression_ratio:.1f}% compression) in {elapsed_time:.1f}s"
                )
                self.webhook.edit_message(
                    f"Tar.gz compression completed: {final_size / (1024*1024):.2f} MB "
                    f"({compression_ratio:.1f}% compression) in {elapsed_time:.1f}s"
                )
                
                return dest_path
                
            except Exception as e:
                self.log.error(f"Tar.gz compression attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    self.log.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.webhook.edit_message(f"Tar.gz compression failed after {self.max_retries} attempts: {e}")
                    
        return None