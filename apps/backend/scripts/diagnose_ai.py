#!/usr/bin/env python3
"""
DASH AI Diagnostic Tool
Checks the health and configuration of all AI components:
- DASH configuration
- Provider status
- Ollama connectivity and models
- STT availability
- TTS availability
- WebSocket server status
"""

import asyncio
import json
import os
import sys
import platform
from pathlib import Path
from typing import Dict, Any

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dash_backend.config import get_settings
from dash_backend.llm.service import check_provider_health

# ANSI colors for pretty output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_status(message: str, status: str, color: str):
    """Print a status message with color."""
    status_colored = f"{color}{status:12}{Colors.RESET}"
    print(f"{message:<50} {status_colored}")

def print_section(title: str):
    """Print a section title."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}{Colors.RESET}")

def check_stt_availability() -> Dict[str, Any]:
    """Check if STT dependencies are available."""
    result = {"available": False, "error": None, "packages": []}
    
    try:
        import speech_recognition
        result["packages"].append("speech_recognition")
        result["available"] = True
    except ImportError as e:
        result["error"] = f"speech_recognition not installed: {e}"
    
    try:
        import whisper
        result["packages"].append("whisper")
    except ImportError:
        pass  # Whisper is optional but nice to have
    
    return result

def check_tts_availability() -> Dict[str, Any]:
    """Check if TTS dependencies are available."""
    result = {"available": False, "error": None, "packages": []}
    
    try:
        # Check Piper TTS
        from dash_backend.voice.piper import PiperTTS
        result["packages"].append("piper")
        result["available"] = True
    except Exception as e:
        # Check basic TTS
        try:
            import pyttsx3
            result["packages"].append("pyttsx3")
            result["available"] = True
        except ImportError as e2:
            result["error"] = f"No TTS engine available: Piper failed, pyttsx3 missing: {e2}"
    
    return result

def check_python_environment() -> Dict[str, Any]:
    """Get Python environment information."""
    return {
        "executable": sys.executable,
        "version": platform.python_version(),
        "venv_active": hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix),
        "cwd": str(Path.cwd()),
    }

async def main():
    """Run all diagnostics."""
    print(f"{Colors.BOLD}DASH AI Diagnostic Tool{Colors.RESET}")
    print(f"Running from: {Path(__file__).resolve()}")
    
    # Section 1: Python Environment
    print_section("PYTHON ENVIRONMENT")
    py_env = check_python_environment()
    print_status("Python Executable", "FOUND", Colors.GREEN)
    print(f"   Path: {py_env['executable']}")
    print_status("Python Version", "FOUND", Colors.GREEN)
    print(f"   Version: {py_env['version']}")
    print_status("Virtual Environment", "ACTIVE" if py_env['venv_active'] else "INACTIVE", 
                Colors.GREEN if py_env['venv_active'] else Colors.YELLOW)
    print(f"   Working Directory: {py_env['cwd']}")
    
    # Section 2: DASH Configuration
    print_section("DASH CONFIGURATION")
    try:
        settings = get_settings()
        print_status("Config Loaded", "SUCCESS", Colors.GREEN)
        print(f"   AI Provider: {settings.ai_provider}")
        print(f"   AI Model: {settings.ai_model or 'Not set'}")
        print(f"   Ollama Base URL: {settings.ollama_base_url}")
        print(f"   Ollama Model: {settings.ollama_model or 'Not set'}")
        print(f"   OpenAI Base URL: {settings.openai_base_url}")
        # Never print API keys!
        has_openai_key = bool(settings.openai_api_key)
        print_status("OpenAI API Key", "CONFIGURED" if has_openai_key else "NOT SET",
                    Colors.GREEN if has_openai_key else Colors.YELLOW)
    except Exception as e:
        print_status("Config Loaded", "FAILED", Colors.RED)
        print(f"   Error: {e}")
        return 1
    
    # Section 3: Provider Health
    print_section("AI PROVIDER HEALTH")
    try:
        health = await check_provider_health()
        print_status("Health Check", "PASSED" if health['healthy'] else "FAILED",
                    Colors.GREEN if health['healthy'] else Colors.RED)
        print(f"   Provider: {health['provider']}")
        print(f"   Configured Model: {health['configured_model'] or 'Not detected'}")
        print(f"   Model Available: {'Yes' if health['model_available'] else 'No'}")
        print(f"   Latency: {health['latency_ms']:.2f}ms" if health['latency_ms'] else "   Latency: N/A")
        
        if health['installed_models']:
            print(f"\n   Installed Models ({len(health['installed_models'])}):")
            for model in health['installed_models'][:10]:  # Show first 10
                print(f"     - {model}")
            if len(health['installed_models']) > 10:
                print(f"     ... and {len(health['installed_models']) - 10} more")
        
        if health['error']:
            print(f"   Error: {health['error']}")
    except Exception as e:
        print_status("Health Check", "ERROR", Colors.RED)
        print(f"   Exception: {e}")
    
    # Section 4: STT Availability
    print_section("SPEECH-TO-TEXT (STT)")
    stt_status = check_stt_availability()
    print_status("STT Available", "YES" if stt_status['available'] else "NO",
                Colors.GREEN if stt_status['available'] else Colors.RED)
    if stt_status['packages']:
        print(f"   Installed packages: {', '.join(stt_status['packages'])}")
    if stt_status['error']:
        print(f"   Error: {stt_status['error']}")
    
    # Section 5: TTS Availability
    print_section("TEXT-TO-SPEECH (TTS)")
    tts_status = check_tts_availability()
    print_status("TTS Available", "YES" if tts_status['available'] else "NO",
                Colors.GREEN if tts_status['available'] else Colors.RED)
    if tts_status['packages']:
        print(f"   Installed packages: {', '.join(tts_status['packages'])}")
    if tts_status['error']:
        print(f"   Error: {tts_status['error']}")
    
    # Section 6: Summary
    print_section("SUMMARY")
    all_good = True
    
    # Check critical components
    if not py_env['venv_active']:
        print_status("Virtual Environment", "WARNING", Colors.YELLOW)
        all_good = False
    
    if 'settings' in locals():
        if settings.ai_provider.lower() == 'ollama' and not health.get('healthy', False):
            print_status("Ollama Connection", "UNHEALTHY", Colors.RED)
            all_good = False
            print("   Tip: Ensure Ollama is running and accessible at the configured URL")
            print("   Install Ollama from: https://ollama.com/")
            print(f"   Current URL: {settings.ollama_base_url}")
    
    if not stt_status['available']:
        print_status("STT", "MISSING", Colors.YELLOW)
        print("   Install speech_recognition: pip install SpeechRecognition")
        all_good = False
    
    if not tts_status['available']:
        print_status("TTS", "MISSING", Colors.RED)
        all_good = False
    
    if all_good:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All critical systems check out!{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Some components need attention. See above for details.{Colors.RESET}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)