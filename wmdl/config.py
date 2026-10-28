"""
Configuration and constants for wmdl
"""

import os
from pathlib import Path

# Shinigami API configuration
BASE_URL = "https://app.shinigami.asia"
API_URL = "https://api.shngm.io"
CDN_URL = "https://storage.shngm.id"

# Download settings
DEFAULT_DOWNLOAD_DIR = Path("downloads")
MAX_CONCURRENT_DOWNLOADS = 5
DOWNLOAD_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = "wmdl.log"
