#!/usr/bin/env python3
"""
Monitor de recursos do AI Agents No-Code Tools
"""

import requests
import time
import psutil
import os
import sys
from datetime import datetime

def get_server_status(base_url="http://localhost:8000"):
    """Verifica o status do servidor"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def get_system_resources():
    """Obtém informações dos recursos do sistema"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_gb": memory.available / (1024**3),
        "memory_total_gb": memory.total / (1024**3)
    }

def test_server_load(base_url="http://localhost:8000"):
    """Testa a carga do servidor com uma requisição TTS"""
    try:
        response = requests.post(
            f"{base_url}/api/v1/media/audio-tools/tts/kokoro",
            data={
                "text": "teste de monitoramento",
                "voice": "af_heart"
            },
            timeout=10
        )
        
        if response.status_code == 429:
            return "BUSY"
        elif response.status_code == 200:
            return "OK"
        else:
            return f"ERROR_{response.status_code}"
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except:
        return "CONNECTION_ERROR"

def print_status(status, resources):
    """Imprime o status formatado"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n{'='*60}")
    print(f"🕐 {timestamp}")
    print(f"{'='*60}")
    
    # Status do servidor
    server_online = get_server_status()
    print(f"🖥️  Servidor: {'🟢 ONLINE' if server_online else '🔴 OFFLINE'}")
    
    if server_online:
        load_status = test_server_load()
        load_emoji = {
            "OK": "🟢",
            "BUSY": "🟡", 
            "TIMEOUT": "🔴",
            "CONNECTION_ERROR": "🔴"
        }
        print(f"⚡ Carga: {load_emoji.get(load_status, '🔴')} {load_status}")
    
    # Recursos do sistema
    print(f"\n📊 RECURSOS DO SISTEMA:")
    print(f"   CPU: {resources['cpu_percent']:.1f}%")
    print(f"   Memória: {resources['memory_percent']:.1f}% " +
          f"({resources['memory_available_gb']:.1f}GB livre de {resources['memory_total_gb']:.1f}GB)")
    
    # Avisos
    if resources['cpu_percent'] > 80:
        print(f"⚠️  AVISO: CPU alta ({resources['cpu_percent']:.1f}%)")
    
    if resources['memory_percent'] > 85:
        print(f"⚠️  AVISO: Memória alta ({resources['memory_percent']:.1f}%)")
    
    # Configurações atuais
    print(f"\n⚙️  CONFIGURAÇÕES:")
    print(f"   MAX_CPU_THREADS: {os.environ.get('MAX_CPU_THREADS', '4 (padrão)')}")
    print(f"   CPU_USAGE_LIMIT: {os.environ.get('CPU_USAGE_LIMIT', '0.7 (padrão)')}")
    print(f"   MAX_CONCURRENT_TTS: {os.environ.get('MAX_CONCURRENT_TTS', '2 (padrão)')}")
    print(f"   MAX_CONCURRENT_VIDEO: {os.environ.get('MAX_CONCURRENT_VIDEO', '1 (padrão)')}")

def main():
    """Função principal"""
    print("🚀 AI Agents No-Code Tools - Monitor de Recursos")
    print("📡 Monitorando servidor... (Ctrl+C para parar)")
    
    try:
        while True:
            resources = get_system_resources()
            print_status("monitoring", resources)
            time.sleep(30)  # Atualiza a cada 30 segundos
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitor finalizado pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro no monitor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Verificar se psutil está instalado
    try:
        import psutil
    except ImportError:
        print("❌ Erro: psutil não está instalado")
        print("💡 Instale com: pip install psutil")
        sys.exit(1)
    
    main() 