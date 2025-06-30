import time
import warnings
from typing import List, Optional
from kokoro import KPipeline
import numpy as np
import soundfile as sf
from loguru import logger
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
from video.config import device
import re
import unicodedata

# Suppress PyTorch warnings
warnings.filterwarnings("ignore")

LANGUAGE_CONFIG = {
    "en-us": {
        "lang_code": "a",
        "international": False,
    },
    "en": {
        "lang_code": "a",
        "international": False,
    },
    "en-gb": {
        "lang_code": "b",
        "international": False,
    },
    "es": {"lang_code": "e", "international": True},
    "fr": {"lang_code": "f", "international": True},
    "hi": {"lang_code": "h", "international": True},
    "it": {"lang_code": "i", "international": True},
    "pt": {"lang_code": "p", "international": True},
    "ja": {"lang_code": "j", "international": True},
    "zh": {"lang_code": "z", "international": True},
}
LANGUAGE_VOICE_CONFIG = {
    "en-us": [
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ],
    "en-gb": [
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    ],
    "zh": [
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoxiao",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ],
    "es": ["ef_dora", "em_alex", "em_santa"],
    "fr": ["ff_siwis"],
    "it": ["if_sara", "im_nicola"],
    "pt": ["pf_dora", "pm_alex", "pm_santa"],
    "hi": ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"],
}

LANGUAGE_VOICE_MAP = {}
for lang, voices in LANGUAGE_VOICE_CONFIG.items():
    for voice in voices:
        if lang in LANGUAGE_CONFIG:
            LANGUAGE_VOICE_MAP[voice] = LANGUAGE_CONFIG[lang]
        else:
            print(f"Warning: Language {lang} not found in LANGUAGE_CONFIG")


class TTS:
    def __init__(self):
        """
        Inicializa o sistema TTS com configurações otimizadas
        """
        self.abbreviations = {
            "dr.": "doutor",
            "dra.": "doutora", 
            "sr.": "senhor",
            "sra.": "senhora",
            "prof.": "professor",
            "profa.": "professora",
            "etc.": "etcetera",
            "ex.": "exemplo",
            "vs.": "versus",
            "p.": "página",
            "pp.": "páginas",
            "vol.": "volume",
            "cap.": "capítulo",
            "art.": "artigo",
            "inc.": "incorporado",
            "ltd.": "limitada",
            "s.a.": "sociedade anônima",
            "ltda.": "limitada",
            "cia.": "companhia",
            "jr.": "júnior",
            "sr.": "sênior",
        }
        
        self.number_patterns = {
            r'\b(\d+)º\b': r'\1 graus',
            r'\b(\d+)ª\b': r'\1 graus',
            r'\b(\d+)%\b': r'\1 por cento',
            r'\b(\d+),(\d+)\b': r'\1 vírgula \2',
            r'\b(\d{4})-(\d{4})\b': r'\1 a \2',
        }

    def preprocess_text(self, text: str, language: str = "pt") -> str:
        """
        Processa e normaliza o texto para melhor síntese TTS
        
        Args:
            text: Texto para processar
            language: Idioma do texto (pt, en, es, etc.)
        """
        if not text or not text.strip():
            return ""
        
        # Normalização Unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Remove caracteres de controle
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normaliza espaçamento
        text = re.sub(r'\s+', ' ', text)
        
        # Expande abreviações (principalmente para português)
        if language in ["pt", "pt-br"]:
            for abbrev, expansion in self.abbreviations.items():
                text = re.sub(r'\b' + re.escape(abbrev), expansion, text, flags=re.IGNORECASE)
        
        # Processa números e símbolos
        for pattern, replacement in self.number_patterns.items():
            text = re.sub(pattern, replacement, text)
        
        # Remove URLs e emails
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '[link]', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', text)
        
        # Normaliza pontuação para melhor prosódia
        text = re.sub(r'\.{2,}', '...', text)  # Múltiplos pontos para reticências
        text = re.sub(r'!{2,}', '!', text)     # Múltiplas exclamações
        text = re.sub(r'\?{2,}', '?', text)    # Múltiplas interrogações
        
        # Adiciona pausas em pontuações se necessário
        text = re.sub(r'([.!?])\s*', r'\1 ', text)
        text = re.sub(r'([,;:])\s*', r'\1 ', text)
        
        # Remove espaços extras
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Garante terminação adequada
        if text and text[-1] not in '.!?':
            text += '.'
        
        return text

    def split_text_into_chunks(self, text: str, max_length: int = 500) -> List[str]:
        """
        Divide texto longo em chunks menores para melhor processamento TTS
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        sentences = re.split(r'([.!?]+\s*)', text)
        current_chunk = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i] if i < len(sentences) else ""
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + punctuation
            
            if len(current_chunk + full_sentence) <= max_length:
                current_chunk += full_sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = full_sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def kokoro(
        self, text: str, output_path: str, voice="af_heart", speed=1
    ) -> tuple[List[dict], float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        
        lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
        if not lang_code:
            raise ValueError(f"Voice '{voice}' not found in LANGUAGE_VOICE_MAP")
        
        # Detectar idioma baseado na voz
        language = "pt" if lang_code == "p" else "en"
        
        # Pré-processar texto para melhor qualidade
        processed_text = self.preprocess_text(text, language)
        
        logger.info(f"Texto original: {text[:100]}...")
        logger.info(f"Texto processado: {processed_text[:100]}...")
        
        start = time.time()

        context_logger = logger.bind(
            voice=voice,
            speed=speed,
            text_length=len(processed_text),
            device=device.type,
            language=language
        )

        context_logger.info("Iniciando síntese TTS com Kokoro (texto processado)")
        
        try:
            pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device)

            # Dividir texto em chunks se muito longo
            text_chunks = self.split_text_into_chunks(processed_text, max_length=300)
            
            all_captions = []
            all_audio_data = []
            full_audio_length = 0
            
            for chunk_idx, chunk in enumerate(text_chunks):
                context_logger.debug(f"Processando chunk {chunk_idx + 1}/{len(text_chunks)}: {chunk[:50]}...")
                
                generator = pipeline(chunk, voice=voice, speed=speed)

                chunk_captions = []
                chunk_audio_data = []
                chunk_audio_length = 0
                
                for _, result in enumerate(generator):
                    data = result.audio
                    audio_length = len(data) / 24000
                    chunk_audio_data.append(data)
                    
                    if result.tokens:
                        tokens = result.tokens
                        for t in tokens:
                            if t.start_ts is None or t.end_ts is None:
                                if chunk_captions:
                                    chunk_captions[-1]["text"] += t.text
                                    chunk_captions[-1]["end_ts"] = chunk_audio_length + audio_length
                                continue
                            try:
                                chunk_captions.append({
                                    "text": t.text,
                                    "start_ts": full_audio_length + chunk_audio_length + t.start_ts,
                                    "end_ts": full_audio_length + chunk_audio_length + t.end_ts,
                                })
                            except Exception as e:
                                logger.error(f"Erro processando token: {t}, Erro: {e}")
                                continue
                    
                    chunk_audio_length += audio_length
                
                # Adicionar dados do chunk ao total
                all_captions.extend(chunk_captions)
                all_audio_data.extend(chunk_audio_data)
                full_audio_length += chunk_audio_length
            
            # Concatenar todo o áudio
            if all_audio_data:
                audio_data = np.concatenate(all_audio_data)
                audio_data = np.column_stack((audio_data, audio_data))
                sf.write(output_path, audio_data, 24000, format="WAV")
            else:
                raise ValueError("Nenhum áudio foi gerado")
            
            context_logger.bind(
                execution_time=time.time() - start,
                audio_length=full_audio_length,
                speedup=full_audio_length / (time.time() - start) if (time.time() - start) > 0 else 0,
                chunks_processed=len(text_chunks),
                captions_generated=len(all_captions)
            ).info("Síntese TTS concluída com sucesso")
            
            return all_captions, full_audio_length
            
        except Exception as e:
            context_logger.error(f"Erro na síntese TTS: {e}")
            raise e

    def chatterbox(
        self,
        text: str,
        output_path: str,
        sample_audio_path: Optional[str] = None,
        exaggeration=0.5,
        cfg_weight=0.5,
        temperature=0.8,
    ):
        # Pré-processar texto
        processed_text = self.preprocess_text(text, "en")
        
        start = time.time()
        context_logger = logger.bind(
            text_length=len(processed_text),
            sample_audio_path=sample_audio_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            model="ChatterboxTTS",
            language="en-US",
            device=device.type,
        )
        context_logger.info("Iniciando síntese TTS com Chatterbox (texto processado)")
        
        try:
            model = ChatterboxTTS.from_pretrained(device=device)

            if sample_audio_path:
                wav = model.generate(
                    processed_text,
                    audio_prompt_path=sample_audio_path,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                )
            else:
                wav = model.generate(
                    processed_text,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                )

            if wav.dim() == 2 and wav.shape[0] == 1:
                wav = wav.repeat(2, 1)
            elif wav.dim() == 1:
                wav = wav.unsqueeze(0).repeat(2, 1)

            audio_length = wav.shape[1] / model.sr
            ta.save(output_path, wav, model.sr)
            
            context_logger.bind(
                execution_time=time.time() - start,
                audio_length=audio_length,
                speedup=audio_length / (time.time() - start) if (time.time() - start) > 0 else 0,
            ).info("Síntese TTS com Chatterbox concluída")
            
        except Exception as e:
            context_logger.error(f"Erro na síntese Chatterbox: {e}")
            raise e

    def valid_kokoro_voices(self, lang_code: str = None) -> List[str]:
        """
        Returns a list of valid voices for the given language code.
        If no language code is provided, returns all voices.
        """
        if lang_code:
            return LANGUAGE_VOICE_CONFIG.get(lang_code, [])
        else:
            return [
                voice for voices in LANGUAGE_VOICE_CONFIG.values() for voice in voices
            ]
