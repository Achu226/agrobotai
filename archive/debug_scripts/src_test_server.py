import subprocess
import time
import urllib.request
import signal
import sys
import os

print("Starting server process...")
# Start server in background
proc = subprocess.Popen(["python", "server.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Wait a few seconds for it to boot
time.sleep(10)

print("Checking if server is alive on port 8000...")
try:
    response = urllib.request.urlopen("http://127.0.0.1:8000/")
    print(f"Status Data: {response.read().decode('utf-8')[:200]}")
    print("\nSERVER IS RUNNING SUCCESSFULLY!")
except Exception as e:
    print(f"Failed to connect: {e}")

print("\nShutting down server...")
if os.name == 'nt':
    subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)])
else:
    proc.terminate()
