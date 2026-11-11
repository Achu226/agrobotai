from pathlib import Path
import requests
import json
import sys
import time
import subprocess

print("Booting server on 8001...")
proc = subprocess.Popen(["python", "-m", "uvicorn", "server:app", "--port", "8001"])
time.sleep(10)

test_file = str(Path(__file__).resolve().parent) + r"\data\disease\PlantVillage\Tomato_healthy\000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"

print("Sending test image to /api/analyze...")
try:
    with open(test_file, 'rb') as f:
        files = {'file': ('test.jpg', f, 'image/jpeg')}
        data = {'crop': 'Tomato'}
        res = requests.post("http://127.0.0.1:8001/api/analyze", files=files, data=data)
        
    print(f"Status Code: {res.status_code}")
    if res.status_code == 200:
        rj = res.json()
        print("Crop:", rj.get('crop'))
        print("Diagnosis:", rj.get('disease', {}).get('class'))
        
        advice = rj.get('advice', {})
        print("Advice Keys:", list(advice.keys()))
        print("Emergency Tab Source:", advice.get('source'))
    else:
        print(res.text)
    
except Exception as e:
    print("Integration test failed:", e)
finally:
    proc.terminate()
