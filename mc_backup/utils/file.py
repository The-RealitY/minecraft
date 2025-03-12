import os
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from mc_backup import ProcessWebhook


class FileArchive:
    def __init__(self, wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION):
        self.webhook: ProcessWebhook = wh
        self.log = log
        self.mc_data_path = MC_DATA_PATH
        self.backup_path = BACKUP_PATH
        self.num_backup_retain = RETENTION
        self.filename = None

    def _create_archived_path(self, ext):
        """
        Create an archived file path with a timestamped name.

        :param ext: Extension for the archive file (e.g., .zip or .tar.gz)
        :return: Full path to the archive file
        """
        os.makedirs(self.backup_path, exist_ok=True)
        file_prefix = "MineCraftBackup"
        tz = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"{file_prefix}_{tz}{ext}"
        arch_path = os.path.join(self.backup_path, self.filename)
        self.log.info(f"Compress Path: {arch_path}")
        self.webhook.edit_message(f"Compress Path: {arch_path}")
        return arch_path

    def _validate_source_path(self):
        """
        Validate that the source directory exists.
        """
        src_path = Path(self.mc_data_path)
        if not src_path.exists() or not src_path.is_dir():
            self.log.error(f"Source path '{self.mc_data_path}' does not exist or is not a directory.")
            self.webhook.edit_message(f"Source path '{self.mc_data_path}' does not exist or is not a directory.")
            return None
        return src_path

    def retain_backup(self):
        try:
            files_in_retain = [f for f in os.listdir(self.backup_path) if os.path.isfile(os.path.join(self.backup_path, f))]
            files_in_retain.sort(key=lambda f: os.path.getmtime(os.path.join(self.backup_path, f)), reverse=True)
            if len(files_in_retain) > self.num_backup_retain:
                # Files to delete (all files beyond the retention limit)
                files_to_delete = files_in_retain[self.num_backup_retain:]
                for file in files_to_delete:
                    file_path = os.path.join(self.backup_path, file)
                    os.remove(file_path)
                    self.log.info(f"Deleted file: {file_path}")
                    self.webhook.edit_message(f"Deleted file: {file_path}")
            else:
                self.log.info(f"Number of files in retention folder is within the limit ({len(files_in_retain)} files). No deletion necessary.")
                self.webhook.edit_message(f"Number of files in retention folder is within the limit ({len(files_in_retain)} files). No deletion necessary.")
        except Exception as e:
            self.log.error(f"An error occurred while retaining files: {e}")
            self.webhook.edit_message(f"An error occurred while retaining files: {e}")

    def compress_to_zip(self):
        """
        Compress a directory into a .zip file.
        """
        try:
            src_path = self._validate_source_path()
            if not src_path:
                return None
            dest_path = self._create_archived_path('.zip')
            with zipfile.ZipFile(dest_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(src_path):
                    for file in files:
                        file_path = Path(root) / file
                        arc_name = file_path.relative_to(src_path)  # Preserve directory structure
                        zipf.write(file_path, arc_name)
            self.log.info(f"Compressed {src_path} to {dest_path}.")
            self.webhook.edit_message(f"Compressed {src_path} to {dest_path}.")
            return dest_path
        except Exception as e:
            self.log.error(f"Failed to compress to .zip: {e}")
            self.webhook.edit_message(f"Failed to compress to .zip: {e}")
        return None

    def decompress_zip(self, backup_name):
        """
        Quickly extracts a ZIP file, ensuring full overwrite.
        """
        try:
            src_path: Any = os.path.join(self.backup_path, backup_name)
            dest_path = self.mc_data_path

            if not os.path.exists(src_path):
                self.log.error(f"Backup File Not Found: {src_path}")
                self.webhook.edit_message(f"Backup File Not Found: {src_path}")
                return None

            # 🚀 Remove existing world folder for a full reset
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)

            os.makedirs(dest_path, exist_ok=True)

            with zipfile.ZipFile(src_path, 'r') as zip_ref:
                self.log.info('Restoring the Backup. Please wait...')
                self.webhook.edit_message('Restoring the Backup. Please wait...')

                # ⚡ Extract all files in one operation (much faster)
                zip_ref.extractall(dest_path)

            self.log.info("Restoration completed successfully!")
            self.webhook.edit_message("Restoration completed successfully!")
            return True

        except Exception as e:
            self.log.error(f"Error restoring backup: {e}")
            self.webhook.edit_message(f"Error restoring backup: {e}")
            return False

    def compress_to_tar(self):
        """
        Compress a directory into a .tar.gz file.
        """
        try:
            src_path = self._validate_source_path()
            dest_path = self._create_archived_path('.tar.gz')
            with tarfile.open(dest_path, "w:gz") as tarf:
                tarf.add(src_path, arcname=".")  # Add directory structure to the archive
            self.log.info(f"Compressed {src_path} to {dest_path}.")
            self.webhook.edit_message(f"Compressed {src_path} to {dest_path}.")
            return dest_path
        except Exception as e:
            self.log.error(f"Failed to compress to .tar.gz: {e}")
            self.webhook.edit_message(f"Failed to compress to .tar.gz: {e}")
        return None
