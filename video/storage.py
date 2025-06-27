from typing import Tuple, Optional
import uuid
import os
import requests
import datetime


class MediaType:
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TMP = "tmp"


class Storage:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        # make all the subdirectories for the media types
        for media_type in [
            MediaType.IMAGE,
            MediaType.VIDEO,
            MediaType.AUDIO,
            MediaType.TMP,
        ]:
            os.makedirs(os.path.join(self.storage_path, media_type), exist_ok=True)
        
        # Create default folders
        self._create_default_folders()

    def _validate_media_id(self, media_id: str) -> tuple[str, str]:
        """
        Validates and parses a media ID to prevent path traversal attacks.

        Args:
            media_id (str): Media ID to validate

        Returns:
            tuple[str, str]: (media_type, filename)

        Raises:
            ValueError: If media_id is invalid or contains path traversal attempts
        """
        if not media_id or "_" not in media_id:
            raise ValueError("Invalid media ID format")

        media_type, filename = media_id.split("_", 1)

        # Validate media type
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")

        # Prevent path traversal by checking for dangerous patterns
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError(
                "Filename contains invalid characters or path traversal attempt"
            )

        # Additional validation: filename should not be empty and should be reasonable
        if not filename or len(filename) > 255:
            raise ValueError("Invalid filename")

        return media_type, filename

    def _get_safe_file_path(self, media_id: str) -> str:
        """
        Gets a safe file path for the given media ID after validation.
        Funciona com o novo sistema (UUID + metadados) e mantém compatibilidade com formato antigo.

        Args:
            media_id (str): Media ID to get path for

        Returns:
            str: Safe file path
        """
        # Try new system first (UUID + metadata)
        file_path = self._find_file_by_uuid(media_id)
        if file_path and os.path.exists(file_path):
            return file_path
        
        # Fallback para sistema antigo (compatibilidade)
        try:
            media_type, filename = self._validate_media_id(media_id)
            file_path = os.path.join(self.storage_path, media_type, filename)

            # Double-check that the resolved path is within the storage directory
            resolved_path = os.path.abspath(file_path)
            storage_abs_path = os.path.abspath(self.storage_path)

            if not resolved_path.startswith(storage_abs_path):
                raise ValueError("Path traversal attempt detected")

            return file_path
        except:
            raise FileNotFoundError(f"Media file {media_id} not found.")
    
    def _find_file_by_uuid(self, media_id: str) -> str:
        """
        Locates file by UUID in all folders (new system).
        
        Args:
            media_id (str): File UUID
            
        Returns:
            str: File path or empty string if not found
        """
        # Search metadata first
        metadata = self._get_file_metadata(media_id)
        folder_path = metadata.get("folder_path", "")
        file_extension = metadata.get("file_extension", "")
        
        # Build possible filename
        filename = f"{media_id}{file_extension}" if file_extension else media_id
        
        # Try to locate in specific folder
        if folder_path:
            file_path = os.path.join(self.storage_path, "folders", folder_path, filename)
            if os.path.exists(file_path):
                return file_path
        
        # Try to locate in all possible folders
        search_paths = [
            os.path.join(self.storage_path, "folders"),  # Custom folders
            os.path.join(self.storage_path, "image"),    # Default image folder
            os.path.join(self.storage_path, "video"),    # Default video folder
            os.path.join(self.storage_path, "audio"),    # Default audio folder
            os.path.join(self.storage_path, "tmp"),      # Default tmp folder
        ]
        
        for base_path in search_paths:
            if not os.path.exists(base_path):
                continue
                
            # Search file recursively
            for root, dirs, files in os.walk(base_path):
                # Look for file that starts with the UUID
                for file in files:
                    if file.startswith(media_id):
                        file_path = os.path.join(root, file)
                        return file_path
        
        return ""

    def upload_media(
        self, media_type: str, media_data: bytes, file_extension: str = "", custom_name: str = ""
    ) -> str:
        """
        Uploads media to the server.

        Args:
            media_type (str): Type of media, e.g., 'image' or 'video'.
            media_data (bytes): Binary data of the media file.
            file_extension (str): File extension, e.g., '.jpg', '.mp4', '.wav'.

        Returns:
            str: Media ID, e.g., 'image_12345.jpg' or 'video_67890.mp4'.
        """
        # Validate media type
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")

        # Validate file extension to prevent path traversal
        if file_extension and (
            ".." in file_extension or "/" in file_extension or "\\" in file_extension
        ):
            raise ValueError("File extension contains invalid characters")
        
        # Validate custom name to prevent path traversal
        if custom_name and (
            ".." in custom_name or "/" in custom_name or "\\" in custom_name
        ):
            raise ValueError("Custom name contains invalid characters")

        # Use custom name if provided, otherwise generate unique UUID
        if custom_name:
            # Sanitize custom name for security
            safe_name = self._sanitize_filename(custom_name)
            filename = f"{safe_name}{file_extension}" if file_extension else safe_name
        else:
            asset_id = str(uuid.uuid4())
            filename = f"{asset_id}{file_extension}" if file_extension else asset_id
            
        file_path = os.path.join(self.storage_path, media_type, filename)

        # Additional safety check
        resolved_path = os.path.abspath(file_path)
        storage_abs_path = os.path.abspath(self.storage_path)
        if not resolved_path.startswith(storage_abs_path):
            raise ValueError("Path traversal attempt detected")

        with open(file_path, "wb") as f:
            f.write(media_data)

        media_id = f"{media_type}_{filename}"
        return media_id

    def get_media(self, media_id: str) -> bytes:
        """
        Retrieves media by ID.

        Args:
            media_id (str): Media ID, e.g., 'image_12345.jpg' or 'video_67890.mp4'.

        Returns:
            bytes: Binary data of the media file.
        """
        file_path = self._get_safe_file_path(media_id)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file {media_id} not found.")

        with open(file_path, "rb") as f:
            return f.read()

    def delete_media(self, media_id: str) -> None:
        """
        Deletes media by ID.

        Args:
            media_id (str): Media ID, e.g., 'image_12345.jpg' or 'video_67890.mp4'.
        """
        file_path = self._get_safe_file_path(media_id)

        if os.path.exists(file_path):
            os.remove(file_path)
            # Delete metadata too
            self._delete_file_metadata(media_id)
        else:
            raise FileNotFoundError(f"Media file {media_id} not found.")

    def media_exists(self, media_id: str) -> bool:
        """
        Checks if media exists by ID.

        Args:
            media_id (str): Media ID, e.g., 'image_12345.jpg' or 'video_67890.mp4'.

        Returns:
            bool: True if media exists, False otherwise.
        """
        try:
            file_path = self._get_safe_file_path(media_id)
            return os.path.exists(file_path)
        except ValueError:
            return False

    def get_media_path(self, media_id: str) -> str:
        """
        Gets the file path of the media by ID.

        Args:
            media_id (str): Media ID, e.g., 'image_12345.jpg' or 'video_67890.mp4'.

        Returns:
            str: Full file path of the media.
        """
        return self._get_safe_file_path(media_id)

    ### untested
    def create_media_filename(
        self, media_type: str, file_extension: str = ""
    ) -> str:
        # Validate media type
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")

        # Validate file extension to prevent path traversal
        if file_extension and (
            ".." in file_extension or "/" in file_extension or "\\" in file_extension
        ):
            raise ValueError("File extension contains invalid characters")

        asset_id = str(uuid.uuid4())
        filename = f"{asset_id}{file_extension}" if file_extension else asset_id
        return f"{media_type}_{filename}"

    def create_media_filename_with_id(
        self, media_type: str, file_extension: str = "", custom_name: str = ""
    ) -> Tuple[str, str]:
        if custom_name:
            file_id = self.create_media_filename_with_custom_name(media_type, file_extension, custom_name)
        else:
            file_id = self.create_media_filename(media_type, file_extension)
        return file_id, self.get_media_path(file_id)
    
    def create_media_filename_with_custom_name(
        self, media_type: str, file_extension: str = "", custom_name: str = ""
    ) -> str:
        # Validate media type
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")

        # Validate file extension to prevent path traversal
        if file_extension and (
            ".." in file_extension or "/" in file_extension or "\\" in file_extension
        ):
            raise ValueError("File extension contains invalid characters")
        
        # Validate custom name to prevent path traversal
        if custom_name and (
            ".." in custom_name or "/" in custom_name or "\\" in custom_name
        ):
            raise ValueError("Custom name contains invalid characters")

        # Use custom name if provided, otherwise generate unique UUID
        if custom_name:
            # Sanitize custom name for security
            safe_name = self._sanitize_filename(custom_name)
            filename = f"{safe_name}{file_extension}" if file_extension else safe_name
        else:
            asset_id = str(uuid.uuid4())
            filename = f"{asset_id}{file_extension}" if file_extension else asset_id
            
        return f"{media_type}_{filename}"

    def create_tmp_file_id(self, media_id: str) -> str:
        """
        Creates a temporary filename for media upload.

        Args:
            media_id (str): Media ID to create a temporary filename for.

        Returns:
            str: Temporary media ID.
        """
        return f"{media_id}.tmp"

    def create_tmp_file(self, media_id: str) -> str:
        """
        Creates a temporary file for media upload.

        Args:
            media_id (str): Media ID to create a temporary file for.

        Returns:
            str: Temporary media ID.
        """
        tmp_id = f"{media_id}.tmp"
        tmp_path = self.get_media_path(tmp_id)

        with open(tmp_path, "wb") as f:
            pass
        return tmp_id

    def get_media_type(self, media_id: str) -> str:
        """
        Gets the media type of the given media ID.

        Args:
            media_id (str): Media ID to get the type for.

        Returns:
            MediaType: The type of the media.
        """
        media_type, _ = self._validate_media_id(media_id)
        return media_type

    def is_valid_url(self, url: str) -> bool:
        """
        Validates a URL to ensure it is well-formed.

        Args:
            url (str): The URL to validate.

        Returns:
            bool: True if the URL is valid, False otherwise.
        """
        from urllib.parse import urlparse

        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
        
    def upload_media_from_url(
        self, media_type: str, url: str
    ) -> str:
        """
        Uploads media from a URL.

        Args:
            media_type (MediaType): Type of media, e.g., MediaType.IMAGE.
            url (str): URL of the media file.

        Returns:
            str: Media ID, e.g., 'image_12345.jpg'.
        """
        if not self.is_valid_url(url):
            raise ValueError("Invalid URL")

        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to download media from {url}")

        file_extension = os.path.splitext(url)[1]
        return self.upload_media(media_type, response.content, file_extension)
    
    def upload_media_to_folder(self, media_type: str, media_data: bytes, 
                              file_extension: str = "", folder_path: str = "", custom_name: str = "") -> str:
        """
        Upload media to a specific folder.
        Accepts both real names and normalized folder IDs.
        
        Args:
            media_type (str): Type of media
            media_data (bytes): Binary data of the file
            file_extension (str): File extension
            folder_path (str): Target folder path (real name or normalized ID)
            custom_name (str): Custom name for the file
            
        Returns:
            str: Media ID of the created file
        """
        # Validate media type
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")
        
        # Convert normalized ID to real name if necessary
        if folder_path:
            # If contains '/', it's a path - map each part
            if '/' in folder_path:
                path_parts = folder_path.split('/')
                real_parts = []
                current_parent = ""
                
                for part in path_parts:
                    real_name = self._get_folder_name_from_id(part, current_parent)
                    real_parts.append(real_name)
                    current_parent = '/'.join(real_parts) if real_parts else ""
                
                folder_path = '/'.join(real_parts)
            else:
                # It's a single folder
                folder_path = self._get_folder_name_from_id(folder_path)
        
        # Validate extension
        if file_extension and (
            ".." in file_extension or "/" in file_extension or "\\" in file_extension
        ):
            raise ValueError("File extension contains invalid characters")
        
        # Validate custom name
        if custom_name and (
            ".." in custom_name or "/" in custom_name or "\\" in custom_name
        ):
            raise ValueError("Custom name contains invalid characters")
        
        # Use custom name if provided, otherwise generate unique UUID
        if custom_name:
            # Sanitize custom name for security
            safe_name = self._sanitize_filename(custom_name)
            filename = f"{safe_name}{file_extension}" if file_extension else safe_name
        else:
            asset_id = str(uuid.uuid4())
            filename = f"{asset_id}{file_extension}" if file_extension else asset_id
        
        # Generate simple media_id - just UUID
        asset_id = str(uuid.uuid4())
        safe_filename = f"{asset_id}{file_extension}" if file_extension else asset_id
        media_id = asset_id  # Clean Media ID, no prefixes
        
        # Determine file path
        if folder_path:
            # Create folder if it doesn't exist
            folder_full_path = os.path.join(self.storage_path, "folders", folder_path)
            os.makedirs(folder_full_path, exist_ok=True)
            file_path = os.path.join(folder_full_path, safe_filename)
        else:
            file_path = os.path.join(self.storage_path, media_type, safe_filename)
        
        # Security check
        resolved_path = os.path.abspath(file_path)
        storage_abs_path = os.path.abspath(self.storage_path)
        if not resolved_path.startswith(storage_abs_path):
            raise ValueError("Path traversal attempt detected")
        
        # Write file
        with open(file_path, "wb") as f:
            f.write(media_data)
        
        # Save file metadata (including custom name)
        if custom_name:
            self._save_file_metadata(media_id, {
                "custom_name": custom_name,
                "original_filename": custom_name,
                "media_type": media_type,
                "folder_path": folder_path,
                "file_extension": file_extension
            })
        
        return media_id
    
    def list_media(self, media_type: Optional[str] = None) -> list:
        """
        Lists all stored media files.
        
        Args:
            media_type (str, optional): Specific media type to filter
            
        Returns:
            list: List of dictionaries with file information
        """
        files = []
        
        media_types = [media_type] if media_type else [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO]
        
        for mt in media_types:
            media_path = os.path.join(self.storage_path, mt)
            if not os.path.exists(media_path):
                continue
                
            for filename in os.listdir(media_path):
                if filename.startswith('.'):  # Ignore hidden files
                    continue
                    
                file_path = os.path.join(media_path, filename)
                if os.path.isfile(file_path):
                    try:
                        stat = os.stat(file_path)
                        media_id = f"{mt}_{filename}"
                        
                        files.append({
                            "media_id": media_id,
                            "media_type": mt,
                            "filename": filename,
                            "size_bytes": stat.st_size,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "created_at": stat.st_ctime,
                            "modified_at": stat.st_mtime,
                            "file_extension": os.path.splitext(filename)[1].lower()
                        })
                    except Exception as e:
                        # Log error but continue listing other files
                        print(f"Error processing file {filename}: {e}")
                        
        # Sort by creation date (newest first)
        files.sort(key=lambda x: x["created_at"], reverse=True)
        return files
    
    def get_media_info(self, media_id: str) -> dict:
        """
        Gets detailed information about a specific file.
        
        Args:
            media_id (str): File ID
            
        Returns:
            dict: Detailed file information
        """
        file_path = self._get_safe_file_path(media_id)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file {media_id} not found.")
            
        stat = os.stat(file_path)
        media_type, filename = self._validate_media_id(media_id)
        
        return {
            "media_id": media_id,
            "media_type": media_type,
            "filename": filename,
            "file_path": file_path,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "file_extension": os.path.splitext(filename)[1].lower(),
            "exists": True
        }
    
    def get_storage_stats(self) -> dict:
        """
        Gets general storage statistics including ALL folders.
        
        Returns:
            dict: Storage statistics
        """
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "by_type": {}
        }
        
        # Initialize counters by type
        for media_type in [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]:
            stats["by_type"][media_type] = {
                "count": 0,
                "size_bytes": 0,
                "size_mb": 0
            }
        
        # 1. Count files from default folders (image, video, audio, tmp)
        for media_type in [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]:
            files = self.list_media(media_type)
            count = len(files)
            size = sum(f["size_bytes"] for f in files)
            
            stats["by_type"][media_type]["count"] += count
            stats["by_type"][media_type]["size_bytes"] += size
            stats["by_type"][media_type]["size_mb"] = round(stats["by_type"][media_type]["size_bytes"] / (1024 * 1024), 2)
            
            stats["total_files"] += count
            stats["total_size_bytes"] += size
        
        # 2. Count files from ALL custom folders
        folders_path = os.path.join(self.storage_path, "folders")
        if os.path.exists(folders_path):
            self._count_files_in_all_folders(folders_path, "", stats)
            
        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        return stats
    
    def _count_files_in_all_folders(self, base_path: str, current_path: str, stats: dict):
        """
        Recursively counts files in all folders and subfolders.
        
        Args:
            base_path (str): Base path of folders
            current_path (str): Current relative path
            stats (dict): Statistics dictionary to update
        """
        try:
            if current_path:
                full_path = os.path.join(base_path, current_path)
            else:
                full_path = base_path
                
            if not os.path.exists(full_path):
                return
                
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                
                if os.path.isfile(item_path):
                    # It's a file - count in statistics
                    try:
                        stat = os.stat(item_path)
                        file_ext = os.path.splitext(item)[1].lower()
                        media_type = self._detect_media_type_from_extension(file_ext)
                        
                        # Increment counters
                        stats["by_type"][media_type]["count"] += 1
                        stats["by_type"][media_type]["size_bytes"] += stat.st_size
                        stats["by_type"][media_type]["size_mb"] = round(stats["by_type"][media_type]["size_bytes"] / (1024 * 1024), 2)
                        
                        stats["total_files"] += 1
                        stats["total_size_bytes"] += stat.st_size
                        
                    except Exception as e:
                        print(f"Error processing file {item}: {e}")
                        
                elif os.path.isdir(item_path):
                    # It's a folder - recursion to count subfolders
                    new_path = os.path.join(current_path, item) if current_path else item
                    self._count_files_in_all_folders(base_path, new_path, stats)
                    
        except Exception as e:
            print(f"Error processing folder {current_path}: {e}")
    
    def _create_default_folders(self):
        """
        Creates default folders in the system.
        """
        # Ensure the folders directory exists
        folders_path = os.path.join(self.storage_path, "folders")
        os.makedirs(folders_path, exist_ok=True)
        
        default_folders = ["temp", "Background Music"]
        for folder_name in default_folders:
            try:
                self.create_folder(folder_name)
                print(f"✅ Folder '{folder_name}' created successfully")
            except Exception as e:
                print(f"⚠️  Error creating folder '{folder_name}': {e}")
                # Try to create directly if create_folder fails
                folder_path = os.path.join(folders_path, folder_name)
                os.makedirs(folder_path, exist_ok=True)
                print(f"✅ Folder '{folder_name}' created directly")
    
    def create_folder(self, folder_name: str, parent_folder: str = "") -> bool:
        """
        Creates a new folder in the system.
        
        Args:
            folder_name (str): Name of the folder to be created
            parent_folder (str): Parent folder (relative path)
            
        Returns:
            bool: True if created successfully, False if already exists
        """
        # Validate folder name
        if not folder_name or ".." in folder_name or "/" in folder_name or "\\" in folder_name:
            raise ValueError("Invalid folder name")
        
        # Build folder path
        if parent_folder:
            folder_path = os.path.join(self.storage_path, "folders", parent_folder, folder_name)
        else:
            folder_path = os.path.join(self.storage_path, "folders", folder_name)
        
        # Check if already exists
        if os.path.exists(folder_path):
            return False
            
        # Create folder
        os.makedirs(folder_path, exist_ok=True)
        return True
    
    def list_folders(self, parent_folder: str = "") -> list:
        """
        Lists folders in the system.
        
        Args:
            parent_folder (str): Parent folder to list subfolders
            
        Returns:
            list: List of folders with information
        """
        folders = []
        
        if parent_folder:
            base_path = os.path.join(self.storage_path, "folders", parent_folder)
        else:
            base_path = os.path.join(self.storage_path, "folders")
        
        if not os.path.exists(base_path):
            return folders
        
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                try:
                    stat = os.stat(item_path)
                    # Count files in folder
                    file_count = self._count_files_in_folder(os.path.join(parent_folder, item) if parent_folder else item)
                    
                    folders.append({
                        "id": self._normalize_folder_name(item),  # Normalized ID
                        "name": item,
                        "path": os.path.join(parent_folder, item) if parent_folder else item,
                        "created_at": stat.st_ctime,
                        "modified_at": stat.st_mtime,
                        "file_count": file_count
                    })
                except Exception as e:
                    print(f"Error processing folder {item}: {e}")
        
        # Sort by name
        folders.sort(key=lambda x: x["name"])
        return folders
    
    def delete_folder(self, folder_path: str) -> bool:
        """
        Deletes a folder and all its contents.
        Accepts both real names and normalized folder IDs.
        
        Args:
            folder_path (str): Path of the folder to be deleted (real name or normalized ID)
            
        Returns:
            bool: True if deleted successfully
        """
        # Convert normalized ID to real name if necessary
        if folder_path:
            # If contains '/', it's a path - map each part
            if '/' in folder_path:
                path_parts = folder_path.split('/')
                real_parts = []
                current_parent = ""
                
                for part in path_parts:
                    real_name = self._get_folder_name_from_id(part, current_parent)
                    real_parts.append(real_name)
                    current_parent = '/'.join(real_parts) if real_parts else ""
                
                folder_path = '/'.join(real_parts)
            else:
                # It's a single folder
                folder_path = self._get_folder_name_from_id(folder_path)
        
        # List of protected folders that cannot be deleted
        protected_folders = ["temp", "Background Music"]
        
        if not folder_path or folder_path in protected_folders:
            raise ValueError(f"Cannot delete protected folder '{folder_path}' or empty path")
        
        full_path = os.path.join(self.storage_path, "folders", folder_path)
        
        if not os.path.exists(full_path):
            return False
        
        import shutil
        shutil.rmtree(full_path)
        return True
    
    def _count_files_in_folder(self, folder_path: str) -> int:
        """
        Counts files in a specific folder.
        Accepts both real names and normalized folder IDs.
        
        Args:
            folder_path (str): Folder path (real name or normalized ID)
            
        Returns:
            int: Number of files in the folder
        """
        # Convert normalized ID to real name if necessary
        if folder_path:
            # If contains '/', it's a path - map each part
            if '/' in folder_path:
                path_parts = folder_path.split('/')
                real_parts = []
                current_parent = ""
                
                for part in path_parts:
                    real_name = self._get_folder_name_from_id(part, current_parent)
                    real_parts.append(real_name)
                    current_parent = '/'.join(real_parts) if real_parts else ""
                
                folder_path = '/'.join(real_parts)
            else:
                # It's a single folder
                folder_path = self._get_folder_name_from_id(folder_path)
        
        full_path = os.path.join(self.storage_path, "folders", folder_path)
        if not os.path.exists(full_path):
            return 0
        
        count = 0
        for root, dirs, files in os.walk(full_path):
            count += len(files)
        return count
    
    def _detect_media_type_from_extension(self, file_extension: str) -> str:
        """
        Detects media type based on file extension.
        
        Args:
            file_extension (str): File extension (with or without dot)
            
        Returns:
            str: Detected media type
        """
        ext = file_extension.lower().lstrip('.')
        
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'ico']
        video_extensions = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'm4v', '3gp', 'ogv']
        audio_extensions = ['mp3', 'wav', 'ogg', 'aac', 'm4a', 'flac', 'wma', 'opus', 'aiff']
        
        if ext in image_extensions:
            return MediaType.IMAGE
        elif ext in video_extensions:
            return MediaType.VIDEO
        elif ext in audio_extensions:
            return MediaType.AUDIO
        else:
            return MediaType.IMAGE  # fallback
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitizes a filename by removing dangerous characters.
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: Sanitized and safe name
        """
        import re
        
        # Remove dangerous characters and keep only letters, numbers, hyphens, underscores and spaces
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Replace multiple spaces with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Remove spaces at beginning and end
        sanitized = sanitized.strip()
        
        # If empty after sanitization, use UUID
        if not sanitized:
            sanitized = str(uuid.uuid4())
        
        # Limit length (maximum 50 characters)
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        return sanitized
    
    def _save_file_metadata(self, media_id: str, metadata: dict):
        """
        Saves file metadata.
        
        Args:
            media_id (str): File ID
            metadata (dict): Metadata to save
        """
        import json
        
        metadata_dir = os.path.join(self.storage_path, "metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        
        metadata_file = os.path.join(metadata_dir, f"{media_id}.json")
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _get_file_metadata(self, media_id: str) -> dict:
        """
        Retrieves file metadata.
        
        Args:
            media_id (str): File ID
            
        Returns:
            dict: File metadata or empty dict if doesn't exist
        """
        import json
        
        metadata_dir = os.path.join(self.storage_path, "metadata")
        metadata_file = os.path.join(metadata_dir, f"{media_id}.json")
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        
        return {}
    
    def _delete_file_metadata(self, media_id: str):
        """
        Deletes file metadata.
        
        Args:
            media_id (str): File ID
        """
        metadata_dir = os.path.join(self.storage_path, "metadata")
        metadata_file = os.path.join(metadata_dir, f"{media_id}.json")
        
        if os.path.exists(metadata_file):
            try:
                os.remove(metadata_file)
            except Exception:
                pass  # Silent failure if can't delete metadata
    
    def _normalize_folder_name(self, folder_name: str) -> str:
        """
        Normalizes a folder name to create a safe ID.
        Removes accents, converts to lowercase, replaces spaces and special characters with underscore.
        
        Args:
            folder_name (str): Original folder name
            
        Returns:
            str: Normalized folder ID
        """
        import re
        import unicodedata
        
        # Remove accents and special characters
        normalized = unicodedata.normalize('NFD', folder_name)
        normalized = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
        
        # Convert to lowercase
        normalized = normalized.lower()
        
        # Replace spaces and special characters with underscore
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        
        # Remove multiple consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        
        # Remove underscores at beginning and end
        normalized = normalized.strip('_')
        
        # If empty, use 'folder'
        if not normalized:
            normalized = 'folder'
        
        return normalized

    def list_folder_contents(self, folder_path: str = "") -> dict:
        """
        Lists folder contents (subfolders and files).
        Accepts both real names and normalized folder IDs.
        
        Args:
            folder_path (str): Folder path (real name or normalized ID)
            
        Returns:
            dict: Dictionary with folders and files
        """
        # Convert normalized ID to real name if necessary
        if folder_path:
            # If contains '/', it's a path - map each part
            if '/' in folder_path:
                path_parts = folder_path.split('/')
                real_parts = []
                current_parent = ""
                
                for part in path_parts:
                    real_name = self._get_folder_name_from_id(part, current_parent)
                    real_parts.append(real_name)
                    current_parent = '/'.join(real_parts) if real_parts else ""
                
                folder_path = '/'.join(real_parts)
            else:
                # It's a single folder
                folder_path = self._get_folder_name_from_id(folder_path)
        
        if folder_path:
            full_path = os.path.join(self.storage_path, "folders", folder_path)
        else:
            full_path = os.path.join(self.storage_path, "folders")
        
        result = {
            "folders": [],
            "files": [],
            "current_path": folder_path
        }
        
        if not os.path.exists(full_path):
            return result
        
        # List subfolders
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isdir(item_path):
                stat = os.stat(item_path)
                result["folders"].append({
                    "id": self._normalize_folder_name(item),  # Normalized ID
                    "name": item,
                    "path": os.path.join(folder_path, item) if folder_path else item,
                    "created_at": stat.st_ctime,
                    "file_count": self._count_files_in_folder(os.path.join(folder_path, item) if folder_path else item)
                })
            elif os.path.isfile(item_path):
                # List files  
                stat = os.stat(item_path)
                
                # Detect media_type based on extension
                file_ext = os.path.splitext(item)[1].lower()
                media_type = self._detect_media_type_from_extension(file_ext)
                
                # For files, try to find by UUID name  
                # Extract UUID from filename (format: uuid.ext)
                file_uuid = os.path.splitext(item)[0]
                media_id = file_uuid  # Media ID is always the clean UUID
                
                # Search metadata to get custom name
                metadata = self._get_file_metadata(media_id)
                custom_name = metadata.get("custom_name", "")
                
                # Display name: custom name or UUID if none
                display_name = f"{custom_name}{file_ext}" if custom_name else item
                
                result["files"].append({
                    "media_id": media_id,
                    "media_type": media_type,
                    "name": display_name,  # Custom name for display
                    "filename": display_name,  # Consistency
                    "path": os.path.join(folder_path, item) if folder_path else item,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": stat.st_ctime,
                    "modified_at": stat.st_mtime,
                    "file_extension": file_ext
                })
        
        # Sort
        result["folders"].sort(key=lambda x: x["name"])
        result["files"].sort(key=lambda x: x["name"])
        
        return result

    def _get_folder_name_from_id(self, folder_id: str, parent_folder: str = "") -> str:
        """
        Converts a normalized folder ID to the real folder name.
        
        Args:
            folder_id (str): Normalized folder ID
            parent_folder (str): Parent folder (optional)
            
        Returns:
            str: Real folder name or folder_id itself if no match found
        """
        # If it's already a valid folder path, return as is
        if not folder_id:
            return folder_id
            
        # Build parent folder path directly to avoid circular dependency
        if parent_folder:
            base_path = os.path.join(self.storage_path, "folders", parent_folder)
        else:
            base_path = os.path.join(self.storage_path, "folders")
        
        # If base path doesn't exist, return the folder_id as is
        if not os.path.exists(base_path):
            return folder_id
            
        try:
            # List folders directly from filesystem to avoid circular dependency with list_folders
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path):
                    # Check if this folder's normalized ID matches what we're looking for
                    normalized_id = self._normalize_folder_name(item)
                    if normalized_id == folder_id:
                        return item
                    # Also check direct name match for compatibility
                    if item == folder_id:
                        return item
        except Exception:
            # If any error occurs, just return the folder_id as is
            pass
        
        # If not found, return folder_id itself (might be a valid name)
        return folder_id
