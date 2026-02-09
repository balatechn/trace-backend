"""Run the server - development mode"""
import subprocess
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([
    "D:/Trace/.venv/Scripts/python.exe", 
    "-m", "uvicorn", 
    "app.main:app", 
    "--reload", 
    "--port", "8000"
])
