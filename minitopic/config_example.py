from datetime import timedelta
from pathlib import Path


BASE_URL = "https://rss.example.com"
API_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

CACHE_PATH = Path(__file__).parent / "cache.pkl"
CACHE_LIFE = timedelta(days=1)
USER_DICT_PATH = Path("./dict/user_dict.txt")
