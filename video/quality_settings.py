# -*- coding: utf-8 -*-
"""
Configurações de qualidade para TTS e STT
Ajuste estes parâmetros para melhorar a qualidade das legendas e narração
"""
import os

# ====== CONFIGURAÇÕES DO WHISPER (STT) ======

# Modelo Whisper - trade-off entre qualidade e velocidade
# Opções: "tiny", "base", "small", "medium", "large"
# tiny: mais rápido, menor qualidade
# base: bom equilíbrio
# small: melhor qualidade, ainda razoável
# medium/large: máxima qualidade, mais lento
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")

# Parâmetros de qualidade do Whisper
WHISPER_BEAM_SIZE = int(os.environ.get("WHISPER_BEAM_SIZE", "10"))  # Maior = melhor qualidade
WHISPER_TEMPERATURE = float(os.environ.get("WHISPER_TEMPERATURE", "0.0"))  # 0.0 = determinístico
WHISPER_NO_SPEECH_THRESHOLD = float(os.environ.get("WHISPER_NO_SPEECH_THRESHOLD", "0.6"))
WHISPER_LOG_PROB_THRESHOLD = float(os.environ.get("WHISPER_LOG_PROB_THRESHOLD", "-1.0"))
WHISPER_COMPRESSION_RATIO_THRESHOLD = float(os.environ.get("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4"))

# ====== CONFIGURAÇÕES DE PROCESSAMENTO DE TEXTO ======

# Configurações para segmentação de legendas
SUBTITLE_MAX_CHARS_PER_LINE = int(os.environ.get("SUBTITLE_MAX_CHARS_PER_LINE", "45"))
SUBTITLE_MAX_LINES = int(os.environ.get("SUBTITLE_MAX_LINES", "2"))

# Configurações visuais das legendas
SUBTITLE_FONT_SIZE = int(os.environ.get("SUBTITLE_FONT_SIZE", "120"))
SUBTITLE_SHADOW_BLUR = int(os.environ.get("SUBTITLE_SHADOW_BLUR", "10"))
SUBTITLE_STROKE_SIZE = int(os.environ.get("SUBTITLE_STROKE_SIZE", "5"))

# ====== CONFIGURAÇÕES DO TTS ======

# Comprimento máximo de chunks para TTS
TTS_MAX_CHUNK_LENGTH = int(os.environ.get("TTS_MAX_CHUNK_LENGTH", "300"))

# ====== CONFIGURAÇÕES BASEADAS NO HARDWARE ======

def get_optimal_whisper_settings():
    """
    Retorna configurações otimizadas baseadas no hardware disponível
    """
    import torch
    from video.config import device
    
    if device.type == "cuda":
        # GPU disponível - usar configurações de alta qualidade
        return {
            "model_size": "small",  # Pode usar modelo maior
            "compute_type": "float16",
            "beam_size": 15,
            "batch_size": 8,
        }
    elif device.type == "mps":
        # Apple Silicon - configurações otimizadas
        return {
            "model_size": "base",
            "compute_type": "float16",
            "beam_size": 10,
            "batch_size": 4,
        }
    else:
        # CPU - configurações balanceadas
        cpu_count = os.cpu_count() or 4
        if cpu_count >= 8:
            # CPU potente
            return {
                "model_size": "base",
                "compute_type": "int8",
                "beam_size": 8,
                "batch_size": 2,
            }
        else:
            # CPU limitado
            return {
                "model_size": "tiny",
                "compute_type": "int8", 
                "beam_size": 5,
                "batch_size": 1,
            }

def get_quality_preset(preset: str = "balanced"):
    """
    Retorna configurações predefinidas de qualidade
    
    Args:
        preset: "fast", "balanced", "quality", "max_quality"
    """
    presets = {
        "fast": {
            "whisper_model": "tiny",
            "whisper_beam_size": 5,
            "subtitle_max_chars": 60,
            "subtitle_lines": 1,
            "tts_chunk_length": 500,
        },
        "balanced": {
            "whisper_model": "base",
            "whisper_beam_size": 10,
            "subtitle_max_chars": 45,
            "subtitle_lines": 2,
            "tts_chunk_length": 300,
        },
        "quality": {
            "whisper_model": "small",
            "whisper_beam_size": 15,
            "subtitle_max_chars": 40,
            "subtitle_lines": 2,
            "tts_chunk_length": 200,
        },
        "max_quality": {
            "whisper_model": "medium",
            "whisper_beam_size": 20,
            "subtitle_max_chars": 35,
            "subtitle_lines": 2,
            "tts_chunk_length": 150,
        }
    }
    
    return presets.get(preset, presets["balanced"])

# ====== CONFIGURAÇÕES PARA DIFERENTES IDIOMAS ======

LANGUAGE_SPECIFIC_SETTINGS = {
    "pt": {
        "whisper_model": "base",  # Português geralmente precisa de modelo melhor
        "subtitle_max_chars": 40,  # Português tem palavras mais longas
        "use_whisper_for_timing": True,  # Sempre usar Whisper para português
    },
    "en": {
        "whisper_model": "base",
        "subtitle_max_chars": 50,  # Inglês é mais compacto
        "use_whisper_for_timing": False,  # Pode usar timing do TTS
    },
    "es": {
        "whisper_model": "base",
        "subtitle_max_chars": 45,
        "use_whisper_for_timing": True,
    },
    "fr": {
        "whisper_model": "base", 
        "subtitle_max_chars": 42,
        "use_whisper_for_timing": True,
    }
} 