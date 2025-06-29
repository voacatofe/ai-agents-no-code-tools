# 🚀 Guia de Deploy no EasyPanel

## ⚠️ CONFIGURAÇÃO CRÍTICA - STORAGE PERSISTENTE

**SEM essa configuração, os arquivos serão perdidos a cada restart do container!**

## 📋 **Passo a Passo no EasyPanel:**

### **1️⃣ Criar Volume Persistente**

No EasyPanel, acesse sua aplicação e vá em **Volumes**:

```yaml
# Configuração do Volume
Nome: media-storage
Tipo: Persistent Volume
Tamanho: 20GB  # Ajuste conforme necessário
Mount Path: /app/media
```

### **2️⃣ Configurar Variáveis de Ambiente**

Vá em **Environment Variables** e adicione:

```bash
# Storage persistente
STORAGE_PATH=/app/media

# Configurações de CPU (ajustar conforme VPS)
MAX_CPU_THREADS=2
CPU_USAGE_LIMIT=0.7
MAX_CONCURRENT_TTS=1
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=2

# Configurações PyTorch
OMP_NUM_THREADS=2
MKL_NUM_THREADS=2
TORCH_NUM_THREADS=2
```

### **3️⃣ Configuração de Recursos**

**Para VPS de 4GB RAM:**
```yaml
Resources:
  CPU: 2 cores
  Memory: 3GB
  Disk: 50GB SSD
```

**Para VPS de 8GB RAM:**
```yaml
Resources:
  CPU: 4 cores
  Memory: 6GB
  Disk: 100GB SSD
```

### **4️⃣ Deploy Configuration**

```yaml
# Build
Source: Git Repository
Branch: main
Build Context: .
Dockerfile: Dockerfile

# Networking
Port: 8000
Protocol: HTTP
```

## 🔍 **Verificação Pós-Deploy:**

### **1. Teste de Storage:**
```bash
# Acesse via SSH ou terminal do container
ls -la /app/media/
# Deve mostrar as pastas: image/ video/ audio/ tmp/ folders/
```

### **2. Verificar Logs:**
```bash
# Procure por essas mensagens nos logs:
✅ "CPU Optimization: Max TTS: 1, Max Video: 1"
✅ "Storage initialized at: /app/media"
```

### **3. Teste de Upload:**
- Acesse o file manager: `https://sua-app.com/files`
- Faça upload de um arquivo pequeno
- Reinicie o container
- Verifique se o arquivo ainda existe

## ⚠️ **Problemas Comuns:**

### **Container trava durante upload:**
```bash
# Verificar se volume está montado
df -h /app/media

# Verificar logs
docker logs container-name --tail 100
```

### **Arquivos somem após restart:**
- ❌ Volume não configurado
- ❌ Mount path incorreto  
- ❌ Permissões incorretas

### **Erro de espaço em disco:**
```bash
# Verificar espaço usado
du -sh /app/media/*

# Limpar arquivos temporários
rm -rf /app/media/tmp/*
```

## 🎯 **Monitoramento:**

### **APIs de Status:**
```bash
# Health check
GET /health

# Storage stats
GET /api/v1/media/storage/stats

# Lista de arquivos
GET /api/v1/media/storage/list
```

## 🚨 **Troubleshooting:**

### **1. Container não inicia:**
- Verificar se mount path `/app/media` existe
- Verificar permissões do volume

### **2. Upload falha:**
- Verificar espaço em disco
- Verificar limite de upload do EasyPanel
- Verificar logs de erro

### **3. Performance baixa:**
- Aumentar recursos de CPU/RAM
- Ajustar variáveis de concorrência
- Verificar se SSD está sendo usado

## 📊 **Configurações Otimizadas por Tamanho de VPS:**

### **VPS 2GB RAM:**
```bash
MAX_CPU_THREADS=1
MAX_CONCURRENT_TTS=1
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=1
```

### **VPS 4GB RAM:**
```bash
MAX_CPU_THREADS=2
MAX_CONCURRENT_TTS=1
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=2
```

### **VPS 8GB+ RAM:**
```bash
MAX_CPU_THREADS=4
MAX_CONCURRENT_TTS=2
MAX_CONCURRENT_VIDEO=1
MAX_CONCURRENT_HEAVY_TASKS=3
```

---

## ✅ **Checklist Final:**

- [ ] Volume persistente configurado em `/app/media`
- [ ] Variáveis de ambiente definidas
- [ ] Recursos adequados alocados
- [ ] Deploy realizado com sucesso
- [ ] Storage teste aprovado
- [ ] File manager acessível
- [ ] APIs funcionando corretamente

**Com essa configuração, seu sistema será estável e não perderá dados!** 🎉 