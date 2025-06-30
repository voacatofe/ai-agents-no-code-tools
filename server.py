from fastapi import FastAPI, status, APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal, Optional
import os
import signal
import sys
import asyncio
from asyncio import Semaphore
from loguru import logger
from video.tts import TTS
from video.stt import STT
from video.storage import Storage
from video.caption import Caption
from video.media import MediaUtils
from video.builder import VideoBuilder
from video.config import device

CHUNK_SIZE = 1024 * 1024 * 10  # 10MB chunks

# OTIMIZAÇÃO: Sistema de controle de concorrência
MAX_CONCURRENT_TTS = int(os.environ.get("MAX_CONCURRENT_TTS", "2"))  # Máximo 2 TTS simultâneos
MAX_CONCURRENT_VIDEO = int(os.environ.get("MAX_CONCURRENT_VIDEO", "1"))  # Máximo 1 vídeo simultâneo
MAX_CONCURRENT_HEAVY_TASKS = int(os.environ.get("MAX_CONCURRENT_HEAVY_TASKS", "3"))  # Total de tarefas pesadas

# Semáforos para controlar concorrência
tts_semaphore = Semaphore(MAX_CONCURRENT_TTS)
video_semaphore = Semaphore(MAX_CONCURRENT_VIDEO)
heavy_tasks_semaphore = Semaphore(MAX_CONCURRENT_HEAVY_TASKS)

logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | <blue>{extra}</blue>",
    level="DEBUG",
)

logger.info("This server was created by the 'AI Agents A-Z' YouTube channel")
logger.info("https://www.youtube.com/@aiagentsaz")
logger.info("Using device: {}", device)
logger.info("CPU Optimization: Max TTS: {}, Max Video: {}, Max Heavy Tasks: {}", 
           MAX_CONCURRENT_TTS, MAX_CONCURRENT_VIDEO, MAX_CONCURRENT_HEAVY_TASKS)

def iterfile(path: str):
    with open(path, mode="rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            yield chunk


def signal_handler(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI()

@app.get("/health", tags=["Health Check"])
def read_root():
    return {"status": "ok"}





@app.get("/files", response_class=HTMLResponse, tags=["File Manager"])
def file_manager():
    """
    Web interface for file management.
    """
    template_path = os.path.join(os.path.dirname(__file__), "templates", "file_manager.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <html>
            <body>
                <h1>Erro: Template não encontrado</h1>
                <p>Template file not found. Please check if the file templates/file_manager.html exists</p>
            </body>
        </html>
        """, status_code=404)


@app.get("/templates/file_manager.css", tags=["File Manager"])
def serve_file_manager_css():
    """
    Serve the CSS file for the file manager.
    """
    css_path = os.path.join(os.path.dirname(__file__), "templates", "file_manager.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/css")
    except FileNotFoundError:
        return Response(content="/* CSS file not found */", media_type="text/css", status_code=404)


api_router = APIRouter()
v1_api_router = APIRouter()
v1_media_api_router = APIRouter()

storage = Storage(
    storage_path=os.environ.get("STORAGE_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "media")))
)


@v1_media_api_router.get("/audio-tools/tts/kokoro/languages", tags=["TTS - Text to Speech"])
def get_kokoro_languages():
    """
    Get available Kokoro languages.
    """
    from video.tts import LANGUAGE_VOICE_CONFIG
    languages = list(LANGUAGE_VOICE_CONFIG.keys())
    return {"languages": languages}


@v1_media_api_router.get("/audio-tools/tts/kokoro/voices", tags=["TTS - Text to Speech"])
def get_kokoro_voices(lang_code: Optional[str] = None):
    """
    Get available Kokoro voices.
    
    Args:
        lang_code: Language code (e.g., 'pt-br', 'en-us', 'pt'). If not provided, returns all voices.
    """
    tts_manager = TTS()
    voices = tts_manager.valid_kokoro_voices(lang_code=lang_code if lang_code else "")
    return {"voices": voices, "language": lang_code or "all"}


@v1_media_api_router.post("/audio-tools/tts/kokoro", tags=["TTS - Text to Speech"])
async def generate_kokoro_tts(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text to convert to speech"),
    voice: Optional[str] = Form(None, description="Voice name for kokoro TTS"),
    speed: Optional[float] = Form(None, description="Speed for kokoro TTS"),
    name: Optional[str] = Form(None, description="Custom name for the audio file (optional)")
):
    """
    Generate audio from text using specified TTS engine.
    """
    # OTIMIZAÇÃO: Verificar se há capacidade para processar
    if tts_semaphore.locked() or heavy_tasks_semaphore.locked():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Server busy processing other TTS requests. Please try again later."},
        )
    
    if not voice:
        voice = "af_heart"
    tts_manager = TTS()
    voices = tts_manager.valid_kokoro_voices()
    if voice not in voices:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid voice: {voice}. Valid voices: {voices}"},
        )
    audio_id, audio_path = storage.create_media_filename_with_id(
        media_type="audio", file_extension=".wav", custom_name=name or ""
    )
    tmp_file_id = storage.create_tmp_file(audio_id)

    async def bg_task():
        async with tts_semaphore:
            async with heavy_tasks_semaphore:
                logger.info("Starting Kokoro TTS processing for audio_id: {}", audio_id)
                try:
                    # Executar TTS em thread separada para não bloquear
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: tts_manager.kokoro(
                            text=text,
                            output_path=audio_path,
                            voice=voice,
                            speed=int(speed) if speed else 1,
                        )
                    )
                    logger.info("Completed Kokoro TTS processing for audio_id: {}", audio_id)
                except Exception as e:
                    logger.error("Error in Kokoro TTS processing: {}", e)
                finally:
                    storage.delete_media(tmp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": audio_id}


@v1_media_api_router.post("/audio-tools/tts/chatterbox", tags=["TTS - Text to Speech"])
async def generate_chatterbox_tts(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text to convert to speech"),
    sample_audio_id: Optional[str] = Form(
        None, description="Sample audio ID for voice cloning"
    ),
    sample_audio_file: Optional[UploadFile] = File(
        None, description="Sample audio file for voice cloning"
    ),
    exaggeration: Optional[float] = Form(
        0.5, description="Exaggeration factor for voice cloning"
    ),
    cfg_weight: Optional[float] = Form(0.5, description="CFG weight for voice cloning"),
    temperature: Optional[float] = Form(
        0.8, description="Temperature for voice cloning (default: 0.8)"
    ),
):
    """
    Generate audio from text using Chatterbox TTS.
    """
    # OTIMIZAÇÃO: Verificar se há capacidade para processar
    if tts_semaphore.locked() or heavy_tasks_semaphore.locked():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Server busy processing other TTS requests. Please try again later."},
        )
    
    tts_manager = TTS()
    
    # Create file in temp folder (intermediate file)
    import uuid
    asset_id = str(uuid.uuid4())
    filename = f"{asset_id}.wav"
    temp_folder_path = os.path.join(storage.storage_path, "folders", "temp")
    os.makedirs(temp_folder_path, exist_ok=True)
    audio_path = os.path.join(temp_folder_path, filename)
    audio_id = f"folder_temp_audio_{filename}"

    sample_audio_path = None
    if sample_audio_file:
        if not sample_audio_file.filename or not sample_audio_file.filename.endswith(".wav"):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Sample audio file must be a .wav file."},
            )
        sample_audio_id = storage.upload_media(
            media_type="audio",
            media_data=sample_audio_file.file.read(),
            file_extension=".wav",
        )
        sample_audio_path = storage.get_media_path(sample_audio_id)
    elif sample_audio_id:
        if not storage.media_exists(sample_audio_id):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Sample audio with ID {sample_audio_id} not found."},
            )
        sample_audio_path = storage.get_media_path(sample_audio_id)

    tmp_file_id = storage.create_tmp_file(audio_id)

    async def bg_task():
        async with tts_semaphore:
            async with heavy_tasks_semaphore:
                logger.info("Starting Chatterbox TTS processing for audio_id: {}", audio_id)
                try:
                    if sample_audio_path:
                        # Executar TTS em thread separada para não bloquear
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            lambda: tts_manager.chatterbox(
                                text=text,
                                output_path=audio_path,
                                sample_audio_path=sample_audio_path,
                                exaggeration=exaggeration or 0.5,
                                cfg_weight=cfg_weight or 0.5,
                                temperature=temperature or 0.8,
                            )
                        )
                    logger.info("Completed Chatterbox TTS processing for audio_id: {}", audio_id)
                except Exception as e:
                    logger.error("Error in Chatterbox TTS processing: {}", e)
                finally:
                    storage.delete_media(tmp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": audio_id}


@v1_media_api_router.post("/storage/{folder_path:path}", tags=["File Storage"])
@v1_media_api_router.post("/storage", tags=["File Storage"])
def upload_file(
    folder_path: Optional[str] = None,
    file: Optional[UploadFile] = File(None, description="File to upload"),
    url: Optional[str] = Form(None, description="URL of the file to upload (optional)"),
    media_type: Literal["image", "video", "audio"] = Form(
        ..., description="Type of media being uploaded"
    ),
    name: Optional[str] = Form(None, description="Custom name for the file (optional)")
):
    """
    Upload a file and return its ID.
    Accepts both real names and normalized folder IDs.
    
    Args:
        folder_path: Target folder path (nome real ou ID normalizado). Optional - if not provided, saves to default media folders.
    """
    if media_type not in ["image", "video", "audio"]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid media type: {media_type}"},
        )
    
    if file:
        if folder_path:
            file_id = storage.upload_media_stream_to_folder(
                media_type=media_type,
                file_stream=file.file,
                file_extension=os.path.splitext(file.filename or "")[1],
                folder_path=folder_path,
                custom_name=name or ""
            )
        else:
            file_id = storage.upload_media_stream(
                media_type=media_type,
                file_stream=file.file,
                file_extension=os.path.splitext(file.filename or "")[1],
                custom_name=name or ""
            )

        return {"file_id": file_id}
    elif url:
        if not storage.is_valid_url(url):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": f"Invalid URL: {url}"},
            )
        file_extension = os.path.splitext(url)[1]
        if name:
            # Para URL, fazer download e upload com nome customizado
            import requests
            response = requests.get(url)
            if response.status_code != 200:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": f"Failed to download media from {url}"}
                )
            if folder_path:
                file_id = storage.upload_media_to_folder(
                    media_type=media_type,
                    media_data=response.content,
                    file_extension=file_extension,
                    folder_path=folder_path,
                    custom_name=name
                )
            else:
                file_id = storage.upload_media(
                    media_type=media_type,
                    media_data=response.content,
                    file_extension=file_extension,
                    custom_name=name
                )
        else:
            # For URL without custom name
            if folder_path:
                import requests
                response = requests.get(url)
                if response.status_code != 200:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"error": f"Failed to download media from {url}"}
                    )
                file_extension = os.path.splitext(url)[1]
                file_id = storage.upload_media_to_folder(
                    media_type=media_type,
                    media_data=response.content,
                    file_extension=file_extension,
                    folder_path=folder_path
                )
            else:
                file_id = storage.upload_media_from_url(media_type=media_type, url=url)
        return {"file_id": file_id}


# Specific endpoints FIRST (order matters in FastAPI!)
@v1_media_api_router.get("/storage/list", tags=["File Storage"])
def list_files(media_type: Optional[str] = None, limit: Optional[int] = None):
    """
    List stored files in the system.
    
    Args:
        media_type: Filter by type (image, video, audio)
        limit: Limit number of results
    """
    try:
        files = storage.list_media(media_type)
        
        if limit:
            files = files[:limit]
            
        return {
            "files": files,
            "total": len(files),
            "media_type_filter": media_type or "all"
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error listing files: {str(e)}"}
        )


@v1_media_api_router.get("/storage/stats", tags=["File Storage"])
def get_storage_stats():
    """
    Get general storage statistics.
    """
    try:
        stats = storage.get_storage_stats()
        return stats
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error getting statistics: {str(e)}"}
        )


# Endpoints with parameters AFTER
@v1_media_api_router.get("/storage/{file_id}/info", tags=["File Storage"])
def get_file_info(file_id: str):
    """
    Get detailed information about a specific file.
    """
    try:
        info = storage.get_media_info(file_id)
        return info
    except FileNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"File {file_id} not found"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error getting information: {str(e)}"}
        )


@v1_media_api_router.get("/storage/{folder_path:path}/{file_id}/status", tags=["File Storage"])
@v1_media_api_router.get("/storage/{file_id}/status", tags=["File Storage"])
def file_status(file_id: str, folder_path: Optional[str] = None):
    """
    Check the status of a file by its ID.
    Works with UUID-only files in folders and old format files.
    
    Args:
        file_id: File ID to check status
        folder_path: Folder path where the file should be (optional)
    """
    # For files in folders, use the UUID directly (new system)
    # The folder_path is just for organization in the URL, actual files use UUID-only IDs
    if folder_path:
        # Files in folders use clean UUIDs, not prefixed format
        expected_file_id = file_id
    else:
        # For files in default media folders, use the file_id as is
        expected_file_id = file_id
    
    # Check if temporary file exists (processing)
    tmp_id = storage.create_tmp_file_id(expected_file_id)
    if storage.media_exists(tmp_id):
        return {"status": "processing", "file_id": expected_file_id}
    
    # Check if final file exists (ready)
    elif storage.media_exists(expected_file_id):
        return {"status": "ready", "file_id": expected_file_id}
    
    # File not found
    return {"status": "not_found", "file_id": expected_file_id}


@v1_media_api_router.get("/storage/{file_id}", tags=["File Storage"])
def download_file(file_id: str):
    """
    Download a file by its ID.
    """
    if not storage.media_exists(file_id):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"File with ID {file_id} not found."},
        )

    file_path = storage.get_media_path(file_id)
    return StreamingResponse(
        iterfile(file_path),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={os.path.basename(file_path)}"
        },
    )


@v1_media_api_router.delete("/storage/{folder_path:path}/{file_id}", tags=["File Storage"])
@v1_media_api_router.delete("/storage/{file_id}", tags=["File Storage"])
def delete_file(file_id: str, folder_path: Optional[str] = None):
    """
    Delete a file by its ID.
    Works with UUID-only files in folders and old format files.
    
    Args:
        file_id: File ID to delete
        folder_path: Folder path where the file is located (optional)
    """
    # For files in folders, use the UUID directly (new system)
    # The folder_path is just for organization in the URL, actual files use UUID-only IDs
    if folder_path:
        # Files in folders use clean UUIDs, not prefixed format
        expected_file_id = file_id
    else:
        # For files in default media folders, use the file_id as is
        expected_file_id = file_id
    
    if storage.media_exists(expected_file_id):
        storage.delete_media(expected_file_id)
        return {"status": "success", "file_id": expected_file_id}
    else:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"File {expected_file_id} not found"}
        )


# ==================== FOLDER MANAGEMENT ENDPOINTS ====================

@v1_media_api_router.get("/folders", tags=["Folder Management"])
def list_folders(parent_folder: Optional[str] = None):
    """
    List folders in the system.
    
    Args:
        parent_folder: Parent folder path to list subfolders
    """
    try:
        folders = storage.list_folders(parent_folder or "")
        return {
            "folders": folders,
            "parent_folder": parent_folder or "",
            "total": len(folders)
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error listing folders: {str(e)}"}
        )


@v1_media_api_router.post("/folders", tags=["Folder Management"])
def create_folder(
    folder_name: str = Form(..., description="Name of the folder to create"),
    parent_folder: Optional[str] = Form("", description="Parent folder path")
):
    """
    Create a new folder.
    
    Args:
        folder_name: Name of the folder to create
        parent_folder: Parent folder path (optional)
    """
    try:
        created = storage.create_folder(folder_name, parent_folder or "")
        if created:
            return {
                "success": True,
                "message": f"Folder '{folder_name}' created successfully",
                "folder_name": folder_name,
                "parent_folder": parent_folder or ""
            }
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": f"Folder '{folder_name}' already exists"}
            )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error creating folder: {str(e)}"}
        )


@v1_media_api_router.delete("/folders/{folder_path:path}", tags=["Folder Management"])
def delete_folder(folder_path: str):
    """
    Delete a folder and all its contents.
    Accepts both real names and normalized folder IDs.
    
    Args:
        folder_path: Path of the folder to delete (real name or normalized ID)
    """
    try:
        deleted = storage.delete_folder(folder_path)
        if deleted:
            return {
                "success": True,
                "message": f"Folder '{folder_path}' deleted successfully"
            }
        else:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Folder '{folder_path}' not found"}
            )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error deleting folder: {str(e)}"}
        )


@v1_media_api_router.get("/folders/root/contents", tags=["Folder Management"])
def get_root_folder_contents():
    """
    Get contents of the root folder.
    """
    try:
        contents = storage.list_folder_contents("")
        return contents
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error getting root folder contents: {str(e)}"}
        )


@v1_media_api_router.get("/folders/{folder_path:path}/contents", tags=["Folder Management"])
def get_folder_contents(folder_path: str):
    """
    Get contents of a specific folder (subfolders and files).
    Accepts both real names and normalized folder IDs.
    
    Args:
        folder_path: Path of the folder to explore (real name or normalized ID)
    """
    try:
        contents = storage.list_folder_contents(folder_path)
        return contents
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error getting folder contents: {str(e)}"}
        )





@v1_media_api_router.post("/video-tools/merge", tags=["Video Tools"])
async def merge_videos(
    background_tasks: BackgroundTasks,
    video_ids: str = Form(..., description="List of video IDs to merge"),
    background_music_id: Optional[str] = Form(
        None, description="Background music ID (optional)"
    ),
    background_music_volume: Optional[float] = Form(
        0.5, description="Volume for background music (0.0 to 1.0)"
    ),
    name: Optional[str] = Form(None, description="Custom name for the merged video (optional)")
):
    """
    Merge multiple videos into one.
    """
    # OTIMIZAÇÃO: Verificar se há capacidade para processar vídeo
    if video_semaphore.locked() or heavy_tasks_semaphore.locked():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Server busy processing other video tasks. Please try again later."},
        )
    
    video_id_list = video_ids.split(",") if video_ids else []
    if not video_id_list:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "At least one video ID is required."},
        )

    merged_video_id, merged_video_path = storage.create_media_filename_with_id(
        media_type="video", file_extension=".mp4", custom_name=name or ""
    )

    video_paths = []
    for video_id in video_id_list:
        if not storage.media_exists(video_id):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Video with ID {video_id} not found."},
            )
        video_paths.append(storage.get_media_path(video_id))

    if background_music_id and not storage.media_exists(background_music_id):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Background music with ID {background_music_id} not found."
            },
        )
    background_music_path = (
        storage.get_media_path(background_music_id) if background_music_id else None
    )

    utils = MediaUtils()

    temp_file_id = storage.create_tmp_file(merged_video_id)

    async def bg_task():
        async with video_semaphore:
            async with heavy_tasks_semaphore:
                logger.info("Starting video merge processing for video_id: {}", merged_video_id)
                try:
                    # Executar merge em thread separada para não bloquear
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: utils.merge_videos(
                            video_paths=video_paths,
                            output_path=merged_video_path,
                            background_music_path=background_music_path or "",
                            background_music_volume=background_music_volume or 0.5,
                        )
                    )
                    logger.info("Completed video merge processing for video_id: {}", merged_video_id)
                except Exception as e:
                    logger.error("Error in video merge processing: {}", e)
                finally:
                    storage.delete_media(temp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": merged_video_id}


@v1_media_api_router.post("/video-tools/generate/tts-captioned-video", tags=["Video Tools"])
async def generate_captioned_video(
    background_tasks: BackgroundTasks,
    background_id: str = Form(..., description="Background image or video ID"),
    text: Optional[str] = Form(None, description="Text to generate video from"),
    width: Optional[int] = Form(1080, description="Width of the video (default: 1080)"),
    height: Optional[int] = Form(
        1920, description="Height of the video (default: 1920)"
    ),
    audio_id: Optional[str] = Form(
        None, description="Audio ID for the video (optional)"
    ),
    kokoro_voice: Optional[str] = Form(
        "af_heart", description="Voice for kokoro TTS (default: af_heart)"
    ),
    kokoro_speed: Optional[float] = Form(
        1.0, description="Speed for kokoro TTS (default: 1.0)"
    ),
    name: Optional[str] = Form(None, description="Custom name for the video (optional)")
):
    """
    Generate a captioned video from text and background image or video.
    
    For background images: Applies Ken Burns effect (subtle zoom)
    For background videos: No zoom effect, just scales to fit dimensions
    """
    # OTIMIZAÇÃO: Verificar se há capacidade para processar vídeo + TTS
    if video_semaphore.locked() or tts_semaphore.locked() or heavy_tasks_semaphore.locked():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Server busy processing other heavy tasks. Please try again later."},
        )
    
    if audio_id and not storage.media_exists(audio_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Audio with ID {audio_id} not found."},
        )
    ttsManager = TTS()  # Agora usa configurações otimizadas
    if not audio_id and kokoro_voice not in ttsManager.valid_kokoro_voices():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid voice: {kokoro_voice}."},
        )
    media_type = storage.get_media_type(background_id)
    if media_type not in ["image", "video"]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid media type: {media_type}. Must be 'image' or 'video'"},
        )
    if not storage.media_exists(background_id):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Background image with ID {background_id} not found."},
        )

    # Generate video in temp folder
    import uuid
    asset_id = str(uuid.uuid4())
    video_filename = f"{asset_id}.mp4"
    temp_folder_path = os.path.join(storage.storage_path, "folders", "temp")
    os.makedirs(temp_folder_path, exist_ok=True)
    output_path = os.path.join(temp_folder_path, video_filename)
    output_id = asset_id  # Clean UUID for media ID
    
    dimensions = (width or 1080, height or 1920)
    builder = VideoBuilder(
        dimensions=dimensions,
    )
    builder.set_media_utils(MediaUtils())

    tmp_file_id = storage.create_tmp_file(output_id)

    async def bg_task(
        tmp_file_id: str = tmp_file_id,
    ):
        async with video_semaphore:
            async with heavy_tasks_semaphore:
                logger.info("Starting captioned video generation for video_id: {}", output_id)
                try:
                    tmp_file_ids = [tmp_file_id]
        
                    # Setup temp folder path for intermediate files
                    import uuid
                    temp_folder_path = os.path.join(storage.storage_path, "folders", "temp")
                    os.makedirs(temp_folder_path, exist_ok=True)

                    # set audio, generate captions
                    captions = None
                    tts_audio_id = audio_id
                    if tts_audio_id:
                        audio_path = storage.get_media_path(tts_audio_id)
                        stt = STT(model_size="base")  # Modelo melhor para maior qualidade
                        # Detect language based on selected voice
                        from video.tts import LANGUAGE_VOICE_MAP
                        lang_info = LANGUAGE_VOICE_MAP.get(kokoro_voice, {})
                        whisper_language = "pt" if lang_info.get("lang_code") == "p" else "en"
                        captions = stt.transcribe(audio_path=audio_path, language=whisper_language)[0]
                        builder.set_audio(audio_path)
                    # generate TTS and set audio
                    else:
                        # Create TTS audio in temp folder (intermediate file)
                        import uuid
                        asset_id = str(uuid.uuid4())
                        filename = f"{asset_id}.wav"
                        temp_folder_path = os.path.join(storage.storage_path, "folders", "temp")
                        os.makedirs(temp_folder_path, exist_ok=True)
                        audio_path = os.path.join(temp_folder_path, filename)
                        tts_audio_id = asset_id  # Use clean UUID for temp audio file
                        tmp_file_ids.append(tts_audio_id)
                        
                        # Generate TTS audio
                        tts_captions = ttsManager.kokoro(
                            text=text or "",
                            output_path=audio_path,
                            voice=kokoro_voice or "",
                            speed=int(kokoro_speed or 1),
                        )[0]
                        
                        # Debug log for TTS captions
                        logger.debug(f"Captions returned by TTS: {len(tts_captions) if tts_captions else 0} items")
                        
                        # For Portuguese, always use Whisper STT as Kokoro doesn't return correct timestamps
                        from video.tts import LANGUAGE_VOICE_MAP
                        lang_info = LANGUAGE_VOICE_MAP.get(kokoro_voice, {})
                        is_portuguese = lang_info.get("lang_code") == "p"
                        
                        if is_portuguese or not tts_captions:
                            logger.debug("Using Whisper STT to generate captions (Portuguese language or TTS without timestamps)")
                            stt = STT(model_size="base")  # Modelo melhor para maior qualidade
                            whisper_language = "pt" if is_portuguese else "en"
                            captions = stt.transcribe(audio_path=audio_path, language=whisper_language)[0]
                            logger.debug(f"Captions generated by Whisper STT: {len(captions) if captions else 0} items")
                        else:
                            captions = tts_captions
                            logger.debug("Using TTS captions")
                            
                    builder.set_audio(audio_path)

                    # create subtitle
                    captionsManager = Caption()
                    # Create subtitle in temp folder (intermediate file)
                    subtitle_asset_id = str(uuid.uuid4())
                    subtitle_filename = f"{subtitle_asset_id}.ass"
                    subtitle_path = os.path.join(temp_folder_path, subtitle_filename)
                    subtitle_id = subtitle_asset_id  # Use clean UUID for temp subtitle file
                    tmp_file_ids.append(subtitle_id)
                    segments = captionsManager.create_subtitle_segments_english(
                        captions=captions if isinstance(captions, list) else [],
                        lines=1,  # Uma palavra por vez
                        max_length=1,  # Uma palavra por legenda
                    )
                    logger.debug(f"Subtitle segments created: {len(segments) if segments else 0}")
                    if segments and len(segments) > 0:
                        logger.debug(f"Example segment: {segments[0]}")
                        
                    captionsManager.create_subtitle(
                        segments=segments,
                        font_size=120,
                        output_path=subtitle_path,
                        dimensions=dimensions,
                        shadow_blur=10,
                        stroke_size=5,
                    )
                    logger.debug(f"Subtitle file created at: {subtitle_path}")
                    builder.set_captions(
                        file_path=subtitle_path,
                    )

                    # Set background based on media type
                    background_path = storage.get_media_path(background_id)
                    if media_type == "image":
                        builder.set_background_image(background_path)
                    elif media_type == "video":
                        builder.set_background_video(background_path)

                    builder.set_output_path(output_path)

                    builder.execute()
                    
                    # Save metadata for the final video in temp folder
                    if name:  # If custom name was provided
                        storage._save_file_metadata(output_id, {
                            "custom_name": name,
                            "original_filename": name,
                            "media_type": "video",
                            "folder_path": "temp",
                            "file_extension": ".mp4"
                        })

                    for tmp_file_id in tmp_file_ids:
                        if storage.media_exists(tmp_file_id):
                            storage.delete_media(tmp_file_id)
                    
                    logger.info("Completed captioned video generation for video_id: {}", output_id)
                except Exception as e:
                    logger.error("Error in captioned video generation: {}", e)
                    # Cleanup temporary files in case of error
                    if 'tmp_file_ids' in locals():
                        for tmp_file_id in tmp_file_ids:
                            if storage.media_exists(tmp_file_id):
                                storage.delete_media(tmp_file_id)

    background_tasks.add_task(bg_task, tmp_file_id=tmp_file_id)

    return {
        "file_id": output_id,
    }


v1_api_router.include_router(v1_media_api_router, prefix="/media", tags=["media"])
api_router.include_router(v1_api_router, prefix="/v1", tags=["v1"])
app.include_router(api_router, prefix="/api", tags=["api"])
