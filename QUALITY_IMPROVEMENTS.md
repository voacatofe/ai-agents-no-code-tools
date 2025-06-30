# 🎯 Melhorias de Qualidade para Legendas e Narração

Este documento descreve as melhorias implementadas para resolver problemas com palavras erradas e confusas nas legendas e narração.

## 🔧 Problemas Identificados e Soluções

### **1. Modelo Whisper Muito Pequeno**
**Problema:** Uso do modelo "tiny" resultava em baixa precisão de transcrição
**Solução:** 
- Modelo padrão atualizado para "base" (melhor equilíbrio qualidade/velocidade)
- Configuração adaptativa baseada no hardware disponível
- Opção de usar modelos maiores ("small", "medium", "large") conforme necessário

### **2. Parâmetros de Transcrição Subotimizados**
**Problema:** Configurações básicas resultavam em transcrições imprecisas
**Soluções Implementadas:**
- `beam_size` aumentado de 5 para 10 (melhor busca)
- `temperature` configurado para 0.0 (resultados determinísticos)
- Adicionado filtro VAD (Voice Activity Detection)
- Configurações de threshold otimizadas para cada idioma

### **3. Falta de Pré-processamento de Texto**
**Problema:** Textos não eram normalizados antes da síntese TTS
**Soluções Implementadas:**
- Normalização Unicode completa
- Expansão automática de abreviações (Dr., Sra., etc.)
- Processamento inteligente de números e símbolos
- Remoção de URLs e emails
- Normalização de pontuação para melhor prosódia

### **4. Segmentação de Legendas Inadequada**
**Problema:** Legendas muito curtas ou mal formatadas
**Soluções Implementadas:**
- Aumento de caracteres por linha de 1 para 45-50
- Permitir 2 linhas por legenda para melhor legibilidade
- Processamento inteligente de pontuação
- Evitar sobreposição de timestamps

## 🚀 Como Usar as Melhorias

### **Configuração Automática**
As melhorias são aplicadas automaticamente. O sistema agora:
- Detecta automaticamente o hardware disponível
- Ajusta configurações baseado no idioma
- Usa modelos maiores quando possível
- Aplica pré-processamento inteligente

### **Configuração Manual (Avançada)**
Você pode ajustar parâmetros via variáveis de ambiente:

```bash
# Modelo Whisper (tiny, base, small, medium, large)
export WHISPER_MODEL_SIZE=base

# Qualidade da transcrição (maior = melhor qualidade)
export WHISPER_BEAM_SIZE=10

# Configurações de legenda
export SUBTITLE_MAX_CHARS_PER_LINE=45
export SUBTITLE_MAX_LINES=2

# Tamanho de chunks para TTS
export TTS_MAX_CHUNK_LENGTH=300
```

### **Presets de Qualidade**
```python
from video.quality_settings import get_quality_preset

# Opções: "fast", "balanced", "quality", "max_quality"
settings = get_quality_preset("quality")
```

## 📊 Melhorias por Componente

### **STT (Speech-to-Text) - Whisper**
- ✅ Modelo padrão: `tiny` → `base`
- ✅ Beam size: `5` → `10`
- ✅ Adicionado filtro VAD
- ✅ Configuração adaptativa de compute_type
- ✅ Pré-processamento de texto transcrito
- ✅ Melhor tratamento de erros

### **TTS (Text-to-Speech) - Kokoro**
- ✅ Pré-processamento completo de texto
- ✅ Divisão inteligente em chunks
- ✅ Expansão de abreviações
- ✅ Normalização de números e símbolos
- ✅ Melhor tratamento de pontuação
- ✅ Logs detalhados para debug

### **Processamento de Legendas**
- ✅ Segmentação mais inteligente
- ✅ Melhor formatação visual
- ✅ Prevenção de sobreposição
- ✅ Configurações específicas por idioma
- ✅ Timestamps mais precisos

## 🎛️ Configurações Específicas por Idioma

### **Português**
- Sempre usa Whisper STT para timing (mais preciso)
- Máximo 40 caracteres por linha (palavras mais longas)
- Modelo "base" ou superior recomendado
- Expansão automática de abreviações em português

### **Inglês**
- Pode usar timing do TTS quando disponível
- Máximo 50 caracteres por linha
- Processamento otimizado para inglês americano/britânico

### **Outros Idiomas (Espanhol, Francês, etc.)**
- Configurações balanceadas
- Sempre prefere Whisper STT para timing
- Ajustes específicos de formatação

## 🔍 Monitoramento e Debug

### **Logs Melhorados**
- Logs detalhados de cada etapa do processo
- Informações sobre modelo e parâmetros usados
- Estatísticas de processamento
- Detecção automática de problemas

### **Métricas de Qualidade**
- Contagem de palavras processadas
- Tempo de processamento
- Taxa de erro estimada
- Configurações aplicadas

## ⚡ Otimizações de Performance

### **Configuração Adaptativa**
- **GPU (CUDA):** Modelo "small" + float16
- **Apple Silicon (MPS):** Modelo "base" + float16  
- **CPU Potente (8+ cores):** Modelo "base" + int8
- **CPU Limitado (<8 cores):** Modelo "tiny" + int8

### **Controle de Concorrência**
- Máximo 2 TTS simultâneos
- Máximo 1 processamento de vídeo simultâneo
- Sistema de semáforos para evitar sobrecarga

## 🛠️ Troubleshooting

### **Legendas ainda com problemas?**
1. Verifique a qualidade do áudio de entrada
2. Tente aumentar o modelo Whisper: `WHISPER_MODEL_SIZE=small`
3. Aumente o beam_size: `WHISPER_BEAM_SIZE=15`
4. Para textos específicos, use preset "quality" ou "max_quality"

### **Processamento muito lento?**
1. Use preset "fast" para testes
2. Reduza o modelo: `WHISPER_MODEL_SIZE=tiny`
3. Diminua beam_size: `WHISPER_BEAM_SIZE=5`
4. Verifique se há outros processos pesados rodando

### **Narração com prosódia estranha?**
1. Verifique se o texto está sendo pré-processado corretamente
2. Ajuste pontuação no texto original
3. Use chunks menores: `TTS_MAX_CHUNK_LENGTH=200`
4. Verifique se abreviações estão sendo expandidas

## 📈 Resultados Esperados

Com essas melhorias, você deve observar:

- ✅ **Menos palavras erradas** na transcrição
- ✅ **Legendas mais legíveis** e bem formatadas
- ✅ **Narração mais natural** com melhor prosódia
- ✅ **Timing mais preciso** entre áudio e legendas
- ✅ **Maior estabilidade** no processamento
- ✅ **Logs mais informativos** para debug

---

**💡 Dica:** Comece com as configurações padrão (preset "balanced") e ajuste conforme necessário baseado nos resultados obtidos. 