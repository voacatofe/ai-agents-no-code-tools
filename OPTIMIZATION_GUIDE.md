# 🚀 Guia de Otimização de CPU

Este guia documenta as otimizações implementadas para reduzir o consumo de CPU e evitar sobrecarga da VPS.

## 🎯 **Problemas Resolvidos**

- ✅ **VPS travando** durante processamento de TTS/Vídeo
- ✅ **Consumo excessivo de CPU** com múltiplas requisições
- ✅ **Processamento simultâneo** descontrolado
- ✅ **Falta de controle de recursos**

## ⚙️ **Otimizações Implementadas**

### **1. 🧵 Controle de Threads do PyTorch**

**Antes:**
```python
num_threads = num_cores * 1.5  # Podia usar 12+ threads
```

**Depois:**
```python
MAX_CPU_THREADS = int(os.environ.get("MAX_CPU_THREADS", "4"))
CPU_USAGE_LIMIT = float(os.environ.get("CPU_USAGE_LIMIT", "0.7"))
num_threads = min(MAX_CPU_THREADS, int(num_cores * CPU_USAGE_LIMIT))
```

### **2. 🔒 Sistema de Semáforos**

**Controla simultaneidade:**
- **TTS**: Máximo 2 processos simultâneos
- **Vídeo**: Máximo 1 processo simultâneo  
- **Total pesado**: Máximo 3 tarefas simultâneas

```python
# Semáforos para controlar concorrência
tts_semaphore = Semaphore(MAX_CONCURRENT_TTS)
video_semaphore = Semaphore(MAX_CONCURRENT_VIDEO)
heavy_tasks_semaphore = Semaphore(MAX_CONCURRENT_HEAVY_TASKS)
```

### **3. 🚫 Rate Limiting**

**Retorna erro 429** quando servidor está ocupado:
```python
if tts_semaphore.locked() or heavy_tasks_semaphore.locked():
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "Server busy. Please try again later."}
    )
```

### **4. 🔄 Processamento Assíncrono**

**Executa tarefas pesadas em threads separadas:**
```python
async def bg_task():
    async with tts_semaphore:
        async with heavy_tasks_semaphore:
            await loop.run_in_executor(None, tts_processing)
```

## 📊 **Configurações por Tipo de VPS**

### **🏠 VPS Pequena (1-2 cores, 2-4GB RAM)**
```env
MAX_CPU_THREADS=2
CPU_USAGE_LIMIT=0.5
MAX_CONCURRENT_TTS=1
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=2
```

### **🏢 VPS Média (2-4 cores, 4-8GB RAM)**
```env
MAX_CPU_THREADS=4
CPU_USAGE_LIMIT=0.7
MAX_CONCURRENT_TTS=2
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=3
```

### **🏭 VPS Grande (4+ cores, 8+ GB RAM)**
```env
MAX_CPU_THREADS=6
CPU_USAGE_LIMIT=0.8
MAX_CONCURRENT_TTS=3
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=4
```

## 🛠️ **Como Configurar**

### **1. Arquivo .env**
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas configurações
nano .env
```

### **2. Docker**
```bash
# Para container com limites baixos
docker run -e MAX_CPU_THREADS=2 -e CPU_USAGE_LIMIT=0.5 ...

# Para VPS média
docker run -e MAX_CPU_THREADS=4 -e CPU_USAGE_LIMIT=0.7 ...
```

### **3. Execução Local**
```bash
# Exportar variáveis antes de executar
export MAX_CPU_THREADS=4
export CPU_USAGE_LIMIT=0.7
export MAX_CONCURRENT_TTS=2

# Executar servidor
fastapi dev server.py --host 0.0.0.0
```

## 📈 **Monitoramento**

### **Logs de Otimização**
O servidor agora logga informações sobre as configurações:

```
CPU Optimization: Max TTS: 2, Max Video: 1, Max Heavy Tasks: 3
Optimized CPU configuration: 4 cores available, using 2 threads (limit: 4)
Starting Kokoro TTS processing for audio_id: abc123
```

### **Verificação de Status**
```bash
# Verificar se o servidor está ocupado
curl -X POST "http://localhost:8000/api/v1/media/audio-tools/tts/kokoro" \
  -F "text=teste" -F "voice=af_heart"

# Resposta se ocupado:
# {"error": "Server busy processing other TTS requests. Please try again later."}
```

## 🎯 **Resultados Esperados**

### **Antes das Otimizações:**
- ❌ VPS travava com 2-3 requisições simultâneas
- ❌ CPU 100% constante
- ❌ Memória esgotada
- ❌ Servidor irresponsivo

### **Depois das Otimizações:**
- ✅ VPS estável mesmo com múltiplas requisições
- ✅ CPU controlado (50-70% máximo)
- ✅ Memória gerenciada
- ✅ Servidor sempre responsivo

## 🔧 **Ajustes Finos**

### **Se ainda houver problemas:**

1. **Reduza mais as threads:**
   ```env
   MAX_CPU_THREADS=1
   CPU_USAGE_LIMIT=0.3
   ```

2. **Limite mais a concorrência:**
   ```env
   MAX_CONCURRENT_TTS=1
   MAX_CONCURRENT_HEAVY_TASKS=1
   ```

3. **Para N8N, adicione delay entre requisições:**
   ```javascript
   // No N8N, adicione um delay de 2-5 segundos entre chamadas
   await new Promise(resolve => setTimeout(resolve, 3000));
   ```

## 📚 **Integrações Recomendadas**

### **N8N**
- Adicione **retry logic** com backoff
- Use **delay nodes** entre processamentos pesados
- Configure **timeout** apropriado (5-10 minutos)

### **Zapier**
- Configure **delay actions** entre steps
- Use **error handling** para retry automático
- Monitore **usage limits**

### **Make**
- Use **sleep modules** entre operações
- Configure **error handlers**
- Implemente **retry scenarios**

## 🚨 **Troubleshooting**

### **Problema: Ainda trava a VPS**
**Solução:** Reduza ainda mais os limites:
```env
MAX_CPU_THREADS=1
MAX_CONCURRENT_HEAVY_TASKS=1
```

### **Problema: Muitos erros 429**
**Solução:** Aumente ligeiramente os limites ou adicione delay no cliente:
```env
MAX_CONCURRENT_TTS=2
MAX_CONCURRENT_HEAVY_TASKS=3
```

### **Problema: Processamento muito lento**
**Solução:** Se a VPS for estável, aumente gradualmente:
```env
MAX_CPU_THREADS=6
CPU_USAGE_LIMIT=0.8
```

---

🎉 **Com essas otimizações, sua VPS deve ficar muito mais estável e não travar mais durante o processamento!** 