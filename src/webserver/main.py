from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
import zlib
from pydantic import BaseModel, HttpUrl
import sqlite3
import logging
import os
from redis import Redis
from contextlib import contextmanager

# Models for API requests and responses
class ShortenResponse(BaseModel):
    shortened_url: str

class ShortenRequest(BaseModel):
    url: HttpUrl  # Validate URL format

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Centralized environment variables
DB_PATH = f"/data/{os.getenv('DB_NAME', 'shorten.db')}"
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
FRONTEND_PORT = int(os.getenv('FRONTEND_PORT', 19000))
# Initialize SQLite database
def initialize_db():
    logger.info("Initializing DB if not exists")
    conn = sqlite3.connect(DB_PATH)
    with conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS urls (hash INTEGER PRIMARY KEY, url TEXT)""")
    conn.close()

initialize_db()

# Context manager for SQLite connection
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

# Function to get Redis connection
def get_redis_connection():
    return Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Shorten URL endpoint
@app.post("/v1/shorten", response_model=ShortenResponse)
def shorten_url(shorten_request: ShortenRequest):
    logger.info(f"Shortening URL: {shorten_request.url}")
    url = str(shorten_request.url)
    url_hash = zlib.crc32(url.encode())

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if the hash already exists in SQLite
        cursor.execute("SELECT url FROM urls WHERE hash=?", (url_hash,))
        existing_url = cursor.fetchone()
        if existing_url:
            # Handle hash collision
            if existing_url[0] != url:
                raise HTTPException(status_code=409, detail="Hash collision detected.")
            logger.info(f"URL already shortened: {existing_url[0]}")
        else:
            # Insert the new hash and URL into the SQLite database
            cursor.execute("INSERT INTO urls (hash, url) VALUES (?, ?)", (url_hash, url))
            conn.commit()
            logger.info(f"Inserted new URL with hash {url_hash}")

    # Cache the URL in Redis for faster access
    redis = get_redis_connection()
    if not redis.exists(url_hash):
        redis.set(url_hash, url)

    shortened_url = f"http://127.0.0.1:{FRONTEND_PORT}/{url_hash}"
    return ShortenResponse(shortened_url=shortened_url)

# Redirect URL endpoint
@app.get("/{url_hash}")
def redirect_url(url_hash: int):
    logger.info(f"Redirecting hash {url_hash}")
    redis = get_redis_connection()

    # Check if the URL is in Redis cache
    url = redis.get(url_hash)
    if url:
        logger.info(f"Found hash {url_hash} in Redis, redirecting to {url}")
        return RedirectResponse(url=url)

    # If not in Redis, check SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM urls WHERE hash=?", (url_hash,))
        result = cursor.fetchone()
        if result:
            url = result[0]
            # Cache the URL in Redis
            redis.set(url_hash, url)
            logger.info(f"Found hash {url_hash} in SQLite, redirecting to {url}")
            return RedirectResponse(url=url)
        else:
            logger.error(f"Hash {url_hash} not found in both Redis and SQLite")
            raise HTTPException(status_code=404, detail="URL not found")