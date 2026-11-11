from pathlib import Path
import requests
import json
import sys
import time
import subprocess

print("Booting server...")
proc = subprocess.Popen(["python", "server.py"])
time.sleep(10)

test_file = str(Path(__file__).resolve().parent) + r"\data\disease\PlantVillage\Tomato_healthy\000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"

print("Sending test image to /api/analyze...")
try:
    with open(test_file, 'rb') as f:
        files = {'file': ('test.jpg', f, 'image/jpeg')}
        data = {'crop': 'Tomato'}
        res = requests.post("http://127.0.0.1:8000/api/analyze", files=files, data=data)
        
    print(f"Status Code: {res.status_code}")
    rj = res.json()
    print("Crop:", rj.get('crop'))
    print("Diagnosis:", rj.get('disease', {}).get('class'))
    
    advice = rj.get('advice', {})
    print("Advice Keys:", advice.keys())
    print("Emergency Tab Source:", advice.get('source'))
    
    print("\nFull JSON Response Summary:")
    print(json.dumps(rj, indent=2)[:500] + "...")
except Exception as e:
    print("Integration test failed:", e)
finally:
    proc.terminate()
