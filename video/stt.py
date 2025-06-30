from faster_whisper import WhisperModel
from loguru import logger
from video.config import device
import re
import os


class STT:
    def __init__(self, model_size="small", compute_type="float16"):
        """
        Inicializa o modelo STT com configurações otimizadas para qualidade
        
        Args:
            model_size: Tamanho do modelo ("tiny", "base", "small", "medium", "large")
                       "small" oferece bom equilíbrio entre qualidade e velocidade
            compute_type: Tipo de computação ("float16", "int8", "float32")
                         "float16" oferece melhor qualidade que "int8"
        """
        # Usar modelo maior por padrão para melhor qualidade
        self.model_size = model_size
        self.compute_type = compute_type
        
        # Ajustar compute_type baseado no dispositivo
        if device.type == "cpu":
            # Para CPU, usar int8 para melhor performance
            self.compute_type = "int8"
        
        logger.info(f"Inicializando modelo Whisper: {model_size} com compute_type: {self.compute_type}")
        self.model = WhisperModel(model_size, compute_type=self.compute_type)

    def preprocess_text(self, text: str) -> str:
        """
        Normaliza e limpa o texto transcrito para melhor legibilidade
        """
        if not text:
            return ""
        
        # Remove espaços extras
        text = re.sub(r'\s+', ' ', text)
        
        # Capitaliza primeira letra de sentenças
        text = re.sub(r'([.!?]\s*)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
        
        # Garante que a primeira palavra da frase comece com maiúscula
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        # Remove espaços no início e fim
        text = text.strip()
        
        return text

    def transcribe(self, audio_path, beam_size=10, language="pt", temperature=0.0, 
                  condition_on_previous_text=True, compression_ratio_threshold=2.4,
                  log_prob_threshold=-1.0, no_speech_threshold=0.6):
        """
        Transcreve áudio com parâmetros otimizados para melhor qualidade
        
        Args:
            audio_path: Caminho para o arquivo de áudio
            beam_size: Tamanho do beam search (maior = melhor qualidade, mais lento)
            language: Idioma para transcrição
            temperature: Temperatura para sampling (0.0 = determinístico)
            condition_on_previous_text: Usar contexto das frases anteriores
            compression_ratio_threshold: Limite para detectar texto repetitivo
            log_prob_threshold: Limite de probabilidade logarítmica
            no_speech_threshold: Limite para detectar ausência de fala
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
        
        logger.bind(
            device=device.type,
            model_size=self.model_size,
            beam_size=beam_size,
            language=language
        ).info("Iniciando transcrição com parâmetros otimizados")
        
        try:
            segments, info = self.model.transcribe(
                audio_path, 
                beam_size=beam_size, 
                word_timestamps=True, 
                language=language,
                temperature=temperature,
                condition_on_previous_text=condition_on_previous_text,
                compression_ratio_threshold=compression_ratio_threshold,
                log_prob_threshold=log_prob_threshold,
                no_speech_threshold=no_speech_threshold,
                # Parâmetros adicionais para melhor qualidade
                vad_filter=True,  # Filtro de detecção de atividade vocal
                vad_parameters=dict(min_silence_duration_ms=500)  # Mínimo de silêncio
            )

            duration = info.duration
            captions = []
            
            logger.info(f"Duração do áudio: {duration:.2f}s, Idioma detectado: {info.language}")
            
            for segment in segments:
                # Log do segmento para debug
                logger.debug(f"Segmento: {segment.text} [{segment.start:.2f}s - {segment.end:.2f}s]")
                
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        if word.word and word.word.strip():  # Verifica se a palavra não está vazia
                            # Pré-processa cada palavra
                            processed_word = self.preprocess_text(word.word)
                            if processed_word:  # Só adiciona se não estiver vazia após processamento
                                captions.append({
                                    "text": processed_word,
                                    "start_ts": word.start,
                                    "end_ts": word.end,
                                })
                else:
                    # Fallback: se não há palavras individuais, usar o texto do segmento
                    if segment.text and segment.text.strip():
                        processed_text = self.preprocess_text(segment.text)
                        if processed_text:
                            captions.append({
                                "text": processed_text,
                                "start_ts": segment.start,
                                "end_ts": segment.end,
                            })
            
            logger.info(f"Transcrição concluída: {len(captions)} palavras processadas")
            return captions, duration
            
        except Exception as e:
            logger.error(f"Erro durante a transcrição: {e}")
            raise e

    def transcribe_segment_level(self, audio_path, language="pt", **kwargs):
        """
        Transcreve áudio retornando segmentos em vez de palavras individuais
        Útil para textos mais fluidos
        """
        logger.info("Iniciando transcrição em nível de segmento")
        
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=False,  # Não precisamos de timestamps de palavras
            **kwargs
        )
        
        captions = []
        for segment in segments:
            if segment.text and segment.text.strip():
                processed_text = self.preprocess_text(segment.text)
                if processed_text:
                    captions.append({
                        "text": processed_text,
                        "start_ts": segment.start,
                        "end_ts": segment.end,
                    })
        
        return captions, info.duration
