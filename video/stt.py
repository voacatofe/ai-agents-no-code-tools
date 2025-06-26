from faster_whisper import WhisperModel
from loguru import logger
from video.config import device


class STT:
    def __init__(self, model_size="tiny", compute_type="int8"):
        self.model = WhisperModel(model_size, compute_type=compute_type)

    def transcribe(self, audio_path, beam_size=5, language="pt"):
        logger.bind(
            device=device.type,
        ).debug(
            "transcribing audio with Whisper model",
        )
        segments, info = self.model.transcribe(
            audio_path, beam_size=beam_size, word_timestamps=True, language=language
        )

        duration = info.duration
        captions = []
        for segment in segments:
            for word in segment.words:
                captions.append(
                    {
                        "text": word.word,
                        "start_ts": word.start,
                        "end_ts": word.end,
                    }
                )
        return captions, duration
