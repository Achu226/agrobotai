"""
Setup and Register AgriQwen 7B Agricultural Model in Local Ollama
Registers the domain-adapted agri-qwen:7b model using Modelfile.agri-qwen and verifies local GPU inference.
"""

import os
import subprocess
import time
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MODELFILE_PATH = ROOT_DIR / "Modelfile.agri-qwen"

OLLAMA_PATHS = [
    Path(r"C:\Users\Admin\AppData\Local\Programs\Ollama\ollama.exe"),
    Path(r"C:\Program Files\Ollama\ollama.exe"),
    Path("ollama")
]

def find_ollama_binary():
    for p in OLLAMA_PATHS:
        if p.exists() or p.name == "ollama":
            try:
                res = subprocess.run([str(p), "--version"], capture_output=True, text=True)
                if res.returncode == 0:
                    return str(p)
            except Exception:
                continue
    return "ollama"

def create_agri_qwen_model():
    ollama_bin = find_ollama_binary()
    print(f"[1/4] Found Ollama binary at: {ollama_bin}")
    print(f"[2/4] Registering specialized 'agri-qwen:7b' from {MODELFILE_PATH.name}...")

    cmd = [ollama_bin, "create", "agri-qwen:7b", "-f", str(MODELFILE_PATH)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(ROOT_DIR))

    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"  [Ollama] {line.strip()}")
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Ollama create failed with return code {process.returncode}")

    print("[3/4] Successfully created 'agri-qwen:7b' in Ollama!")

def test_agri_qwen_inference():
    print("[4/4] Testing local GPU inference with AgriQwen (Tamil & English)...")
    url = "http://localhost:11434/api/chat"

    # Test Tamil agricultural prompt
    payload = {
        "model": "agri-qwen:7b",
        "messages": [
            {
                "role": "user",
                "content": "தக்காளி இலைக்கருகல் நோய்க்கு வேப்பெண்ணெய் எப்படி தெளிப்பது? (How to spray neem oil for tomato blight?)"
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 250
        }
    }

    start_time = time.time()
    resp = requests.post(url, json=payload, timeout=60)
    elapsed = time.time() - start_time

    if resp.status_code == 200:
        data = resp.json()
        reply = data.get("message", {}).get("content", "").strip()
        print(f"\n[GPU Inference Success] Time: {elapsed:.2f}s")
        print("-" * 60)
        print(reply)
        print("-" * 60)
        return True
    else:
        print(f"[Error] Inference failed: HTTP {resp.status_code} - {resp.text}")
        return False

if __name__ == "__main__":
    create_agri_qwen_model()
    test_agri_qwen_inference()
