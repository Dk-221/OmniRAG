import os
import sys
import logging
from pathlib import Path

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

import uvicorn

if __name__ == "__main__":
    print("OmniRag backend starting on http://127.0.0.1:8000...", flush=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
