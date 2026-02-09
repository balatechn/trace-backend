"""
Vercel Serverless Function Entry Point
This file exports the FastAPI app for Vercel's Python runtime
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from app.main import app

# Mangum adapter for AWS Lambda / Vercel
handler = Mangum(app, lifespan="off")

