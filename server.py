from fastapi import FastAPI, status, APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal, Optional
import os
import signal
import sys
from loguru import logger
from video.tts import TTS
from video.stt import STT
from video.storage import Storage
from video.caption import Caption
from video.media import MediaUtils
from video.builder import VideoBuilder
from video.config import device

CHUNK_SIZE = 1024 * 1024 * 10  # 10MB chunks

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

def iterfile(path: str):
    with open(path, mode="rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            yield chunk


def signal_handler(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI()

@app.get("/health")
def read_root():
    return {"status": "ok"}


@app.get("/debug/folders")
def debug_folders():
    """
    Debug endpoint to check folder structure and force creation if needed.
    """
    try:
        import os
        
        # Verificar caminhos importantes
        storage_abs_path = os.path.abspath(storage.storage_path)
        folders_path = os.path.join(storage.storage_path, "folders")
        temp_path = os.path.join(folders_path, "temp")
        bg_music_path = os.path.join(folders_path, "Background Music")
        
        # Force create default folders
        print("🔄 Forçando criação de pastas padrão...")
        storage._create_default_folders()
        
        # Get folder info
        folders = storage.list_folders()
        root_contents = storage.list_folder_contents("")
        
        # Check each folder individually
        folder_checks = {}
        for folder_name in ["temp", "Background Music"]:
            folder_path = os.path.join(folders_path, folder_name)
            folder_checks[folder_name] = {
                "exists": os.path.exists(folder_path),
                "path": folder_path,
                "files_count": len(os.listdir(folder_path)) if os.path.exists(folder_path) else 0
            }
        
        return {
            "storage_path": storage_abs_path,
            "folders_path": folders_path,
            "folders_path_exists": os.path.exists(folders_path),
            "folder_checks": folder_checks,
            "folders": folders,
            "root_contents": root_contents,
            "temp_path_exists": os.path.exists(temp_path),
            "bg_music_path_exists": os.path.exists(bg_music_path),
            "success": True,
            "message": "Debug completed successfully"
        }
    except Exception as e:
        return {
            "error": str(e),
            "success": False,
            "storage_path": getattr(storage, 'storage_path', 'unknown') if 'storage' in locals() else 'storage not initialized'
        }


@app.get("/files", response_class=HTMLResponse)
def file_manager():
    """
    Interface web para gerenciar arquivos.
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
                <p>O arquivo de template não foi encontrado. Verifique se existe o arquivo templates/file_manager.html</p>
            </body>
        </html>
        """, status_code=404)


@app.get("/templates/file_manager.css")
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
    storage_path=os.path.abspath(os.path.join(os.path.dirname(__file__), "media"))
)


@v1_media_api_router.get("/audio-tools/tts/kokoro/languages")
def get_kokoro_languages():
    """
    Get available Kokoro languages.
    """
    from video.tts import LANGUAGE_VOICE_CONFIG
    languages = list(LANGUAGE_VOICE_CONFIG.keys())
    return {"languages": languages}


@v1_media_api_router.get("/audio-tools/tts/kokoro/voices")
def get_kokoro_voices(lang_code: Optional[str] = None):
    """
    Get available Kokoro voices.
    
    Args:
        lang_code: Language code (e.g., 'pt-br', 'en-us', 'pt'). If not provided, returns all voices.
    """
    tts_manager = TTS()
    voices = tts_manager.valid_kokoro_voices(lang_code=lang_code)
    return {"voices": voices, "language": lang_code or "all"}


@v1_media_api_router.post("/audio-tools/tts/kokoro")
def generate_kokoro_tts(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text to convert to speech"),
    voice: Optional[str] = Form(None, description="Voice name for kokoro TTS"),
    speed: Optional[float] = Form(None, description="Speed for kokoro TTS"),
    name: Optional[str] = Form(None, description="Custom name for the audio file (optional)")
):
    """
    Generate audio from text using specified TTS engine.
    """
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
        media_type="audio", file_extension=".wav", custom_name=name
    )
    tmp_file_id = storage.create_tmp_file(audio_id)

    def bg_task():
        tts_manager.kokoro(
            text=text,
            output_path=audio_path,
            voice=voice,
            speed=speed if speed else 1.0,
        )
        storage.delete_media(tmp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": audio_id}


@v1_media_api_router.post("/audio-tools/tts/chatterbox")
def generate_chatterbox_tts(
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
        if not sample_audio_file.filename.endswith(".wav"):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Sample audio file must be a .wav file."},
            )
        sample_audio_id = storage.upload_media(
            media_type="tmp",
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

    def bg_task():
        try:
            tts_manager.chatterbox(
                text=text,
                output_path=audio_path,
                sample_audio_path=sample_audio_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )
        except Exception as e:
            logger.error(f"Error in Chatterbox TTS: {e}")
        finally:
            storage.delete_media(tmp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": audio_id}


@v1_media_api_router.post("/storage")
def upload_file(
    file: Optional[UploadFile] = File(None, description="File to upload"),
    url: Optional[str] = Form(None, description="URL of the file to upload (optional)"),
    media_type: Literal["image", "video", "audio"] = Form(
        ..., description="Type of media being uploaded"
    ),
    name: Optional[str] = Form(None, description="Custom name for the file (optional)")
):
    """
    Upload a file and return its ID.
    """
    if media_type not in ["image", "video", "audio"]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid media type: {media_type}"},
        )
    if file:
        file_id = storage.upload_media(
            media_type=media_type,
            media_data=file.file.read(),
            file_extension=os.path.splitext(file.filename)[1],
            custom_name=name
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
            file_id = storage.upload_media(
                media_type=media_type,
                media_data=response.content,
                file_extension=file_extension,
                custom_name=name
            )
        else:
            file_id = storage.upload_media_from_url(media_type=media_type, url=url)
        return {"file_id": file_id}


# Endpoints específicos PRIMEIRO (ordem importa no FastAPI!)
@v1_media_api_router.get("/storage/list")
def list_files(media_type: Optional[str] = None, limit: Optional[int] = None):
    """
    Lista arquivos armazenados no sistema.
    
    Args:
        media_type: Filtrar por tipo (image, video, audio)
        limit: Limitar número de resultados
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
            content={"error": f"Erro ao listar arquivos: {str(e)}"}
        )


@v1_media_api_router.get("/storage/stats")
def get_storage_stats():
    """
    Obtém estatísticas gerais do storage.
    """
    try:
        stats = storage.get_storage_stats()
        return stats
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Erro ao obter estatísticas: {str(e)}"}
        )


# Endpoints com parâmetros DEPOIS
@v1_media_api_router.get("/storage/{file_id}/info")
def get_file_info(file_id: str):
    """
    Obtém informações detalhadas sobre um arquivo específico.
    """
    try:
        info = storage.get_media_info(file_id)
        return info
    except FileNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Arquivo {file_id} não encontrado"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Erro ao obter informações: {str(e)}"}
        )


@v1_media_api_router.get("/storage/{file_id}/status")
def file_status(file_id: str):
    """
    Check the status of a file by its ID.
    """
    tmp_id = storage.create_tmp_file_id(file_id)
    if storage.media_exists(tmp_id):
        return {"status": "processing"}
    elif storage.media_exists(file_id):
        return {"status": "ready"}
    return {"status": "not_found"}


@v1_media_api_router.get("/storage/{file_id}")
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


@v1_media_api_router.delete("/storage/{file_id}")
def delete_file(file_id: str):
    """
    Delete a file by its
    """
    if storage.media_exists(file_id):
        storage.delete_media(file_id)
    return {"status": "success"}


# ==================== FOLDER MANAGEMENT ENDPOINTS ====================

@v1_media_api_router.get("/folders")
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


@v1_media_api_router.post("/folders")
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


@v1_media_api_router.delete("/folders/{folder_path:path}")
def delete_folder(folder_path: str):
    """
    Delete a folder and all its contents.
    
    Args:
        folder_path: Path of the folder to delete
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


@v1_media_api_router.get("/folders/root/contents")
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


@v1_media_api_router.get("/folders/{folder_path:path}/contents")
def get_folder_contents(folder_path: str):
    """
    Get contents of a specific folder (subfolders and files).
    
    Args:
        folder_path: Path of the folder to explore
    """
    try:
        contents = storage.list_folder_contents(folder_path)
        return contents
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error getting folder contents: {str(e)}"}
        )


@v1_media_api_router.post("/folders/{folder_path:path}/upload")
def upload_file_to_folder(
    folder_path: str,
    file: UploadFile = File(..., description="File to upload"),
    media_type: Literal["image", "video", "audio"] = Form(..., description="Type of media being uploaded")
):
    """
    Upload a file to a specific folder.
    
    Args:
        folder_path: Path of the folder to upload to
        file: File to upload
        media_type: Type of media being uploaded
    """
    try:
        if media_type not in ["image", "video", "audio"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": f"Invalid media type: {media_type}"}
            )
        
        file_id = storage.upload_media_to_folder(
            media_type=media_type,
            media_data=file.file.read(),
            file_extension=os.path.splitext(file.filename)[1],
            folder_path=folder_path
        )
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "folder_path": folder_path,
            "media_type": media_type
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error uploading file to folder: {str(e)}"}
        )


@v1_media_api_router.post("/video-tools/merge")
def merge_videos(
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
    video_ids = video_ids.split(",") if video_ids else []
    if not video_ids:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "At least one video ID is required."},
        )

    merged_video_id, merged_video_path = storage.create_media_filename_with_id(
        media_type="video", file_extension=".mp4", custom_name=name
    )

    video_paths = []
    for video_id in video_ids:
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

    def bg_task():
        utils.merge_videos(
            video_paths=video_paths,
            output_path=merged_video_path,
            background_music_path=background_music_path,
            background_music_volume=background_music_volume,
        )
        storage.delete_media(temp_file_id)

    background_tasks.add_task(bg_task)

    return {"file_id": merged_video_id}


@v1_media_api_router.post("/video-tools/generate/tts-captioned-video")
def generate_captioned_video(
    background_tasks: BackgroundTasks,
    background_id: str = Form(..., description="Background image ID"),
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
    Generate a captioned video from text and background image.

    """
    if audio_id and not storage.media_exists(audio_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Audio with ID {audio_id} not found."},
        )
    ttsManager = TTS()
    if not audio_id and kokoro_voice not in ttsManager.valid_kokoro_voices():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid voice: {kokoro_voice}."},
        )
    media_type = storage.get_media_type(background_id)
    if media_type not in ["image"]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid media type: {media_type}"},
        )
    if not storage.media_exists(background_id):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Background image with ID {background_id} not found."},
        )

    output_id, output_path = storage.create_media_filename_with_id(
        media_type="video", file_extension=".mp4", custom_name=name
    )
    dimensions = (width, height)
    builder = VideoBuilder(
        dimensions=dimensions,
    )
    builder.set_media_utils(MediaUtils())

    tmp_file_id = storage.create_tmp_file(output_id)

    def bg_task(
        tmp_file_id: str = tmp_file_id,
    ):
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
            stt = STT(model_size="tiny")
            # Detecta o idioma baseado na voz selecionada
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
            tts_audio_id = f"folder_temp_audio_{filename}"
            tmp_file_ids.append(tts_audio_id)
            
            # Gera o áudio TTS
            tts_captions = ttsManager.kokoro(
                text=text,
                output_path=audio_path,
                voice=kokoro_voice,
                speed=kokoro_speed,
            )[0]
            
            # Log para debug das legendas do TTS
            logger.debug(f"Captions retornadas pelo TTS: {len(tts_captions) if tts_captions else 0} itens")
            
            # Para português, sempre usar Whisper STT pois Kokoro não retorna timestamps corretos
            from video.tts import LANGUAGE_VOICE_MAP
            lang_info = LANGUAGE_VOICE_MAP.get(kokoro_voice, {})
            is_portuguese = lang_info.get("lang_code") == "p"
            
            if is_portuguese or not tts_captions:
                logger.debug("Usando Whisper STT para gerar legendas (idioma português ou TTS sem timestamps)")
                stt = STT(model_size="tiny")
                whisper_language = "pt" if is_portuguese else "en"
                captions = stt.transcribe(audio_path=audio_path, language=whisper_language)[0]
                logger.debug(f"Captions geradas pelo Whisper STT: {len(captions) if captions else 0} itens")
            else:
                captions = tts_captions
                logger.debug("Usando captions do TTS")
                
        builder.set_audio(audio_path)

        # create subtitle
        captionsManager = Caption()
        # Create subtitle in temp folder (intermediate file)
        subtitle_asset_id = str(uuid.uuid4())
        subtitle_filename = f"{subtitle_asset_id}.ass"
        subtitle_path = os.path.join(temp_folder_path, subtitle_filename)
        subtitle_id = f"folder_temp_tmp_{subtitle_filename}"
        tmp_file_ids.append(subtitle_id)
        segments = captionsManager.create_subtitle_segments_english(
            captions=captions,
            lines=1,
            max_length=1,
        )
        logger.debug(f"Segmentos de legenda criados: {len(segments) if segments else 0}")
        if segments and len(segments) > 0:
            logger.debug(f"Exemplo de segmento: {segments[0]}")
            
        captionsManager.create_subtitle(
            segments=segments,
            font_size=120,
            output_path=subtitle_path,
            dimensions=dimensions,
            shadow_blur=10,
            stroke_size=5,
        )
        logger.debug(f"Arquivo de legenda criado em: {subtitle_path}")
        builder.set_captions(
            file_path=subtitle_path,
        )

        builder.set_background_image(
            storage.get_media_path(background_id),
        )

        builder.set_output_path(output_path)

        builder.execute()

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
