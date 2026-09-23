import sys
import os
from pathlib import Path

# Add project root to sys.path so it can find server.py and data/
sys.path.append(str(Path(__file__).parent.parent))

from server import app

# Vercel Serverless environment expects an 'app' object.
