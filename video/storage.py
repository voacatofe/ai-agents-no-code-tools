from typing import Tuple
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

        Args:
            media_id (str): Media ID to get path for

        Returns:
            str: Safe file path
        """
        media_type, filename = self._validate_media_id(media_id)
        file_path = os.path.join(self.storage_path, media_type, filename)

        # Double-check that the resolved path is within the storage directory
        resolved_path = os.path.abspath(file_path)
        storage_abs_path = os.path.abspath(self.storage_path)

        if not resolved_path.startswith(storage_abs_path):
            raise ValueError("Path traversal attempt detected")

        return file_path

    def upload_media(
        self, media_type: MediaType, media_data: bytes, file_extension: str = ""
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
        self, media_type: MediaType, file_extension: str = ""
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
        self, media_type: MediaType, file_extension: str = ""
    ) -> Tuple[str, str]:
        file_id = self.create_media_filename(media_type, file_extension)
        return file_id, self.get_media_path(file_id)

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

    def get_media_type(self, media_id: str) -> MediaType:
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
        self, media_type: MediaType, url: str
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
    
    def list_media(self, media_type: str = None) -> list:
        """
        Lista todos os arquivos de mídia armazenados.
        
        Args:
            media_type (str, optional): Tipo específico de mídia para filtrar
            
        Returns:
            list: Lista de dicionários com informações dos arquivos
        """
        files = []
        
        media_types = [media_type] if media_type else [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO]
        
        for mt in media_types:
            media_path = os.path.join(self.storage_path, mt)
            if not os.path.exists(media_path):
                continue
                
            for filename in os.listdir(media_path):
                if filename.startswith('.'):  # Ignorar arquivos ocultos
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
                        # Log erro mas continua listando outros arquivos
                        print(f"Erro ao processar arquivo {filename}: {e}")
                        
        # Ordena por data de criação (mais recentes primeiro)
        files.sort(key=lambda x: x["created_at"], reverse=True)
        return files
    
    def get_media_info(self, media_id: str) -> dict:
        """
        Obtém informações detalhadas sobre um arquivo específico.
        
        Args:
            media_id (str): ID do arquivo
            
        Returns:
            dict: Informações detalhadas do arquivo
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
        Obtém estatísticas gerais do storage.
        
        Returns:
            dict: Estatísticas do storage
        """
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "by_type": {}
        }
        
        for media_type in [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]:
            files = self.list_media(media_type)
            count = len(files)
            size = sum(f["size_bytes"] for f in files)
            
            stats["by_type"][media_type] = {
                "count": count,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2)
            }
            
            stats["total_files"] += count
            stats["total_size_bytes"] += size
            
        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        return stats
    
    def _create_default_folders(self):
        """
        Cria pastas padrão no sistema.
        """
        default_folders = ["temp"]
        for folder_name in default_folders:
            self.create_folder(folder_name)
    
    def create_folder(self, folder_name: str, parent_folder: str = "") -> bool:
        """
        Cria uma nova pasta no sistema.
        
        Args:
            folder_name (str): Nome da pasta a ser criada
            parent_folder (str): Pasta pai (caminho relativo)
            
        Returns:
            bool: True se criada com sucesso, False se já existe
        """
        # Validar nome da pasta
        if not folder_name or ".." in folder_name or "/" in folder_name or "\\" in folder_name:
            raise ValueError("Invalid folder name")
        
        # Construir caminho da pasta
        if parent_folder:
            folder_path = os.path.join(self.storage_path, "folders", parent_folder, folder_name)
        else:
            folder_path = os.path.join(self.storage_path, "folders", folder_name)
        
        # Verificar se já existe
        if os.path.exists(folder_path):
            return False
            
        # Criar pasta
        os.makedirs(folder_path, exist_ok=True)
        return True
    
    def list_folders(self, parent_folder: str = "") -> list:
        """
        Lista pastas no sistema.
        
        Args:
            parent_folder (str): Pasta pai para listar subpastas
            
        Returns:
            list: Lista de pastas com informações
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
                    # Contar arquivos na pasta
                    file_count = self._count_files_in_folder(os.path.join(parent_folder, item) if parent_folder else item)
                    
                    folders.append({
                        "name": item,
                        "path": os.path.join(parent_folder, item) if parent_folder else item,
                        "created_at": stat.st_ctime,
                        "modified_at": stat.st_mtime,
                        "file_count": file_count
                    })
                except Exception as e:
                    print(f"Erro ao processar pasta {item}: {e}")
        
        # Ordena por nome
        folders.sort(key=lambda x: x["name"])
        return folders
    
    def delete_folder(self, folder_path: str) -> bool:
        """
        Deleta uma pasta e todo seu conteúdo.
        
        Args:
            folder_path (str): Caminho da pasta a ser deletada
            
        Returns:
            bool: True se deletada com sucesso
        """
        if not folder_path or folder_path == "temp":
            raise ValueError("Cannot delete temp folder or empty path")
        
        full_path = os.path.join(self.storage_path, "folders", folder_path)
        
        if not os.path.exists(full_path):
            return False
        
        import shutil
        shutil.rmtree(full_path)
        return True
    
    def _count_files_in_folder(self, folder_path: str) -> int:
        """
        Conta arquivos em uma pasta específica.
        """
        full_path = os.path.join(self.storage_path, "folders", folder_path)
        if not os.path.exists(full_path):
            return 0
        
        count = 0
        for root, dirs, files in os.walk(full_path):
            count += len(files)
        return count
    
    def upload_media_to_folder(self, media_type: str, media_data: bytes, 
                              file_extension: str = "", folder_path: str = "") -> str:
        """
        Faz upload de mídia para uma pasta específica.
        
        Args:
            media_type (str): Tipo de mídia
            media_data (bytes): Dados binários do arquivo
            file_extension (str): Extensão do arquivo
            folder_path (str): Caminho da pasta de destino
            
        Returns:
            str: Media ID do arquivo criado
        """
        # Validar tipo de mídia
        valid_types = [MediaType.IMAGE, MediaType.VIDEO, MediaType.AUDIO, MediaType.TMP]
        if media_type not in valid_types:
            raise ValueError(f"Invalid media type: {media_type}")
        
        # Validar extensão
        if file_extension and (
            ".." in file_extension or "/" in file_extension or "\\" in file_extension
        ):
            raise ValueError("File extension contains invalid characters")
        
        # Criar ID e nome do arquivo
        asset_id = str(uuid.uuid4())
        filename = f"{asset_id}{file_extension}" if file_extension else asset_id
        
        # Determinar caminho do arquivo
        if folder_path:
            # Criar pasta se não existe
            folder_full_path = os.path.join(self.storage_path, "folders", folder_path)
            os.makedirs(folder_full_path, exist_ok=True)
            file_path = os.path.join(folder_full_path, filename)
            media_id = f"folder_{folder_path.replace('/', '_')}_{media_type}_{filename}"
        else:
            file_path = os.path.join(self.storage_path, media_type, filename)
            media_id = f"{media_type}_{filename}"
        
        # Verificação de segurança
        resolved_path = os.path.abspath(file_path)
        storage_abs_path = os.path.abspath(self.storage_path)
        if not resolved_path.startswith(storage_abs_path):
            raise ValueError("Path traversal attempt detected")
        
        # Escrever arquivo
        with open(file_path, "wb") as f:
            f.write(media_data)
        
        return media_id
    
    def get_media_from_folder(self, media_id: str) -> bytes:
        """
        Recupera mídia de pasta.
        """
        file_path = self._get_folder_file_path(media_id)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file {media_id} not found.")
        
        with open(file_path, "rb") as f:
            return f.read()
    
    def _get_folder_file_path(self, media_id: str) -> str:
        """
        Obtém caminho do arquivo em pasta.
        """
        if media_id.startswith("folder_"):
            # Formato: folder_{folder_path}_{media_type}_{filename}
            parts = media_id.split("_", 3)
            if len(parts) >= 4:
                folder_path = parts[1].replace("_", "/")
                media_type = parts[2]
                filename = parts[3]
                return os.path.join(self.storage_path, "folders", folder_path, filename)
        
        # Fallback para arquivos normais
        return self._get_safe_file_path(media_id)
    
    def list_folder_contents(self, folder_path: str = "") -> dict:
        """
        Lista conteúdo de uma pasta (subpastas e arquivos).
        
        Args:
            folder_path (str): Caminho da pasta
            
        Returns:
            dict: Dicionário com folders e files
        """
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
        
        # Listar subpastas
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isdir(item_path):
                stat = os.stat(item_path)
                result["folders"].append({
                    "name": item,
                    "path": os.path.join(folder_path, item) if folder_path else item,
                    "created_at": stat.st_ctime,
                    "file_count": self._count_files_in_folder(os.path.join(folder_path, item) if folder_path else item)
                })
            elif os.path.isfile(item_path):
                # Listar arquivos
                stat = os.stat(item_path)
                result["files"].append({
                    "name": item,
                    "path": os.path.join(folder_path, item) if folder_path else item,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": stat.st_ctime,
                    "modified_at": stat.st_mtime,
                    "file_extension": os.path.splitext(item)[1].lower()
                })
        
        # Ordenar
        result["folders"].sort(key=lambda x: x["name"])
        result["files"].sort(key=lambda x: x["name"])
        
        return result
