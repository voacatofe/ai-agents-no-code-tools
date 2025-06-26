import time
import warnings
from typing import List
from kokoro import KPipeline
import numpy as np
import soundfile as sf
from loguru import logger
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
from video.config import device

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
    def kokoro(
        self, text: str, output_path: str, voice="af_heart", speed=1
    ) -> tuple[str, List[dict], float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
        if not lang_code:
            raise ValueError(f"Voice '{voice}' not found in LANGUAGE_VOICE_MAP")
        # Removida a restrição para permitir outros idiomas além do inglês americano
        start = time.time()

        context_logger = logger.bind(
            voice=voice,
            speed=speed,
            text_length=len(text),
            device=device.type,
        )

        context_logger.debug("Starting TTS generation with kokoro")
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device)

        generator = pipeline(text, voice=voice, speed=speed)

        captions = []
        audio_data = []
        full_audio_length = 0
        for _, result in enumerate(generator):
            data = result.audio
            audio_length = len(data) / 24000
            audio_data.append(data)
            if result.tokens:
                tokens = result.tokens
                for t in tokens:
                    if t.start_ts is None or t.end_ts is None:
                        if captions:
                            captions[-1]["text"] += t.text
                            captions[-1]["end_ts"] = full_audio_length + audio_length
                        continue
                    try:
                        captions.append(
                            {
                                "text": t.text,
                                "start_ts": full_audio_length + t.start_ts,
                                "end_ts": full_audio_length + t.end_ts,
                            }
                        )
                    except Exception as e:
                        logger.error(
                            "Error processing token: {}, Error: {}",
                            t,
                            e,
                        )
                        raise ValueError(f"Error processing token: {t}, Error: {e}")
            full_audio_length += audio_length

        audio_data = np.concatenate(audio_data)
        audio_data = np.column_stack((audio_data, audio_data))
        sf.write(output_path, audio_data, 24000, format="WAV")
        context_logger.bind(
            execution_time=time.time() - start,
            audio_length=full_audio_length,
            speedup=full_audio_length / (time.time() - start),
            youtube_channel="https://www.youtube.com/@aiagentsaz"
        ).debug(
            "TTS generation completed with kokoro",
        )
        return captions, full_audio_length

    def chatterbox(
        self,
        text: str,
        output_path: str,
        sample_audio_path: str = None,
        exaggeration=0.5,
        cfg_weight=0.5,
        temperature=0.8,
    ):
        start = time.time()
        context_logger = logger.bind(
            text_length=len(text),
            sample_audio_path=sample_audio_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            model="ChatterboxTTS",
            language="en-US",
            device=device.type,
        )
        context_logger.debug("starting TTS generation with Chatterbox")
        model = ChatterboxTTS.from_pretrained(device=device)

        if sample_audio_path:
            wav = model.generate(
                text,
                audio_prompt_path=sample_audio_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )
        else:
            wav = model.generate(
                text,
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
            speedup=audio_length / (time.time() - start),
            youtube_channel="https://www.youtube.com/@aiagentsaz"
        ).debug(
            "TTS generation with Chatterbox completed",
        )

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
