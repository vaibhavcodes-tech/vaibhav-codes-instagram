"""
Instagram Data Fetcher & REST API Server
- Automated daily scheduled fetch at 07:30 AM (7.5 AM)
- Dynamic username support (any username passed from frontend)
- High-performance REST endpoints with sorting (recent, oldest, most_viral)
- Local media file serving for reliable reel covers & thumbnails
"""

import os
import sys
import glob
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import schedule
import uvicorn

# Import exporter engine
try:
    from instagram_exporter import run_export
except ImportError:
    from .instagram_exporter import run_export

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_USERNAME = os.getenv("DEFAULT_INSTA_USERNAME", "vaibhav.codes")
DAILY_SYNC_TIME = os.getenv("DAILY_SYNC_TIME", "07:30")  # 7:30 AM (7.5 AM)

# ============================================================================
# APP INITIALIZATION & CORS
# ============================================================================
app = FastAPI(
    title="Instagram Reels Fetcher & Sync API",
    description="Dynamic Instagram reel scraper, automated daily 7:30 AM scheduler, and sorting API for portfolios.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media directory for serving cover images & profile pictures reliably
app.mount("/media", StaticFiles(directory=BASE_DIR), name="media")

# ============================================================================
# STATE TRACKING
# ============================================================================
sync_state = {
    "is_syncing": False,
    "last_sync_time": None,
    "last_sync_user": None,
    "last_sync_status": "Never run",
    "tracked_users": [DEFAULT_USERNAME],
    "scheduled_daily_time": DAILY_SYNC_TIME,
    "scheduler_running": False,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def clean_user_input(username: str) -> str:
    """Sanitize Instagram username from URL or handle."""
    if not username:
        return DEFAULT_USERNAME
    user = username.strip().lstrip("@")
    if "instagram.com/" in user:
        user = user.split("instagram.com/")[1].split("/")[0].split("?")[0]
    return user.lower()

def get_user_folder(clean_username: str) -> str:
    return os.path.join(BASE_DIR, clean_username)

def find_local_cover_file(clean_username: str, shortcode: str) -> Optional[str]:
    """Find local cover image path for a given reel shortcode."""
    user_folder = get_user_folder(clean_username)
    all_posts_dir = os.path.join(user_folder, "all_posts")
    if not os.path.exists(all_posts_dir):
        return None

    # Search for folder ending with shortcode
    matches = glob.glob(os.path.join(all_posts_dir, f"*_{shortcode}"))
    if matches and os.path.isdir(matches[0]):
        cover_path = os.path.join(matches[0], "cover_image.jpg")
        if os.path.exists(cover_path):
            folder_name = os.path.basename(matches[0])
            return f"/media/{clean_username}/all_posts/{folder_name}/cover_image.jpg"
    return None

def load_user_dataset(clean_username: str) -> Dict[str, Any]:
    """Load cached JSON dataset for a user, or build one if files exist."""
    user_folder = get_user_folder(clean_username)
    data_file = os.path.join(user_folder, "all_posts_data.json")

    profile_data = {}
    profile_json = os.path.join(user_folder, "profile_info.json")
    if os.path.exists(profile_json):
        try:
            with open(profile_json, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
        except Exception:
            pass

    posts = []
    last_synced = None
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                posts = data.get("posts", [])
                if not profile_data:
                    profile_data = data.get("profile", {})
                last_synced = profile_data.get("scraped_at")
        except Exception as e:
            print(f"[!] Error loading {data_file}: {e}")

    # Fallback to profile_pic local URL if exists
    local_pic_path = os.path.join(user_folder, "profile_pic.jpg")
    if os.path.exists(local_pic_path):
        profile_data["local_profile_pic"] = f"/media/{clean_username}/profile_pic.jpg"

    return {
        "profile": profile_data,
        "posts": posts,
        "last_synced": last_synced
    }

def perform_sync(username: str):
    """Run full exporter sync in worker thread."""
    clean_username = clean_user_input(username)
    sync_state["is_syncing"] = True
    sync_state["last_sync_user"] = clean_username
    print(f"\n[SYNC WORKER] Starting export for @{clean_username} at {datetime.now().isoformat()}...")

    try:
        success = run_export(clean_username, top_viral_count=5, max_posts=0, only_top_viral=False)
        sync_state["last_sync_time"] = datetime.now().isoformat()
        sync_state["last_sync_status"] = "Success" if success else "Failed (Check terminal / network)"
        print(f"[SYNC WORKER] Finished export for @{clean_username}. Status: {sync_state['last_sync_status']}")
    except Exception as e:
        print(f"[SYNC WORKER ERROR] {e}")
        sync_state["last_sync_status"] = f"Error: {str(e)}"
    finally:
        sync_state["is_syncing"] = False

# ============================================================================
# DAILY 07:30 AM SCHEDULER (7.5 AM)
# ============================================================================
def scheduled_daily_job():
    """Triggered every day at 07:30 AM."""
    print(f"\n{'='*70}")
    print(f"[SCHEDULER 07:30 AM] Daily scheduled Instagram fetch triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    for user in sync_state["tracked_users"]:
        try:
            print(f"[SCHEDULER] Fetching latest posts for tracked user: @{user}...")
            perform_sync(user)
        except Exception as err:
            print(f"[SCHEDULER ERROR] Failed to sync @{user}: {err}")

def run_scheduler_loop():
    """Background scheduler thread runner."""
    print(f"[*] Scheduler thread initialized. Configured daily at: {DAILY_SYNC_TIME} AM (7.5 AM)")
    schedule.every().day.at(DAILY_SYNC_TIME).do(scheduled_daily_job)
    sync_state["scheduler_running"] = True

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"[SCHEDULER LOOP ERROR] {e}")
            time.sleep(5)

# Start background scheduler thread automatically on startup
scheduler_thread = threading.Thread(target=run_scheduler_loop, daemon=True)
scheduler_thread.start()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root(request: Request):
    """API overview and quick navigation."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "service": "Instagram Reels Fetcher & Sync API",
        "version": "1.0.0",
        "status": "online",
        "documentation": f"{base_url}/docs",
        "endpoints": {
            "get_reels": f"{base_url}/api/reels?username=vaibhav.codes&sort=recent&limit=5",
            "get_reel_by_shortcode": f"{base_url}/api/reels/{{shortcode}}",
            "get_profile": f"{base_url}/api/profile?username=vaibhav.codes",
            "trigger_sync": f"{base_url}/api/sync?username=vaibhav.codes (POST)",
            "sync_status": f"{base_url}/api/sync/status",
            "scheduler_info": f"{base_url}/api/schedule"
        },
        "daily_schedule": f"Every morning at {DAILY_SYNC_TIME} (7.5 AM)"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "is_syncing": sync_state["is_syncing"],
        "scheduler_running": sync_state["scheduler_running"]
    }

@app.get("/api/reels")
def get_reels(
    request: Request,
    username: str = Query(DEFAULT_USERNAME, description="Instagram username (e.g. vaibhav.codes)"),
    sort: str = Query("recent", description="Sort order: 'recent', 'oldest', or 'most_viral'"),
    limit: int = Query(0, ge=0, description="Number of reels to return (0 for all, 5 for home preview)"),
    type: str = Query("all", description="Filter media type: 'all', 'reel', or 'photo'")
):
    """
    Fetch reels for any username with dynamic sorting & optional limit.
    - sort='recent': Newest date first
    - sort='oldest': Oldest date first
    - sort='most_viral': Ranked by views, then likes & comments
    - limit=5: Return top 5 recent or viral reels for homepage preview
    """
    clean_username = clean_user_input(username)
    dataset = load_user_dataset(clean_username)
    raw_posts = dataset["posts"]

    # If user folder does not exist or empty, check if we should auto-trigger or notify
    user_folder = get_user_folder(clean_username)
    if not raw_posts and not os.path.exists(user_folder):
        return JSONResponse(
            status_code=404,
            content={
                "status": "not_found",
                "message": f"No stored data found for @{clean_username}. Call POST /api/sync?username={clean_username} to scrape.",
                "username": clean_username
            }
        )

    # Base URL for local media
    base_url = str(request.base_url).rstrip("/")

    # Filter by type if requested
    filtered = []
    for p in raw_posts:
        if type == "reel" and not p.get("is_reel", False):
            continue
        if type == "photo" and p.get("is_reel", False):
            continue

        item = dict(p)
        shortcode = item.get("shortcode", "")

        # Look up local cover image
        local_cover = find_local_cover_file(clean_username, shortcode)
        if local_cover:
            item["local_cover_url"] = f"{base_url}{local_cover}"
            item["has_local_cover"] = True
        else:
            item["local_cover_url"] = None
            item["has_local_cover"] = False

        # Effective cover URL: local first, fallback to remote CDN
        item["effective_cover_url"] = item["local_cover_url"] or item.get("cover_image_url")
        filtered.append(item)

    # Apply Sorting
    sort_key = sort.lower().strip()
    if sort_key in ["most_viral", "viral", "top"]:
        # Sort by views desc, likes desc, comments desc
        filtered.sort(
            key=lambda x: (
                int(x.get("views") or 0),
                int(x.get("likes") or 0),
                int(x.get("comments") or 0)
            ),
            reverse=True
        )
        for idx, item in enumerate(filtered, 1):
            item["rank"] = idx
    elif sort_key == "oldest":
        filtered.sort(
            key=lambda x: x.get("timestamp_utc") or x.get("date") or "",
            reverse=False
        )
    else:
        # Default: recent
        filtered.sort(
            key=lambda x: x.get("timestamp_utc") or x.get("date") or "",
            reverse=True
        )

    # Apply Limit (e.g. 5 for home preview)
    total_count = len(filtered)
    if limit > 0:
        result_posts = filtered[:limit]
    else:
        result_posts = filtered

    profile_data = dataset.get("profile", {})
    if profile_data.get("local_profile_pic"):
        profile_data["local_profile_pic_full"] = f"{base_url}{profile_data['local_profile_pic']}"

    return {
        "status": "success",
        "username": clean_username,
        "profile": profile_data,
        "sort": sort_key,
        "limit": limit,
        "total_count": total_count,
        "returned_count": len(result_posts),
        "last_synced": dataset.get("last_synced"),
        "data": result_posts
    }

@app.get("/api/reels/{shortcode}")
def get_reel_detail(
    shortcode: str,
    request: Request,
    username: str = Query(DEFAULT_USERNAME, description="Username associated with this shortcode")
):
    """Retrieve full details, caption, and cover for a single reel."""
    clean_username = clean_user_input(username)
    dataset = load_user_dataset(clean_username)
    posts = dataset.get("posts", [])

    base_url = str(request.base_url).rstrip("/")
    for p in posts:
        if p.get("shortcode") == shortcode:
            item = dict(p)
            local_cover = find_local_cover_file(clean_username, shortcode)
            if local_cover:
                item["local_cover_url"] = f"{base_url}{local_cover}"
                item["has_local_cover"] = True
            else:
                item["local_cover_url"] = None
                item["has_local_cover"] = False

            item["effective_cover_url"] = item["local_cover_url"] or item.get("cover_image_url")
            return {
                "status": "success",
                "username": clean_username,
                "data": item
            }

    raise HTTPException(status_code=404, detail=f"Reel with shortcode '{shortcode}' not found for @{clean_username}.")

@app.get("/api/profile")
def get_profile(
    request: Request,
    username: str = Query(DEFAULT_USERNAME, description="Instagram username")
):
    """Get profile bio, statistics, and profile image URL."""
    clean_username = clean_user_input(username)
    dataset = load_user_dataset(clean_username)
    profile = dataset.get("profile", {})

    base_url = str(request.base_url).rstrip("/")
    if profile.get("local_profile_pic"):
        profile["local_profile_pic_full"] = f"{base_url}{profile['local_profile_pic']}"

    return {
        "status": "success",
        "username": clean_username,
        "data": profile
    }

@app.post("/api/sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    username: str = Query(DEFAULT_USERNAME, description="Instagram username to scrape and store"),
):
    """Trigger an immediate export & download of reels in the background."""
    clean_username = clean_user_input(username)

    if sync_state["is_syncing"]:
        return {
            "status": "busy",
            "message": f"A sync is already in progress for @{sync_state['last_sync_user']}. Please wait.",
            "is_syncing": True
        }

    # Add username to tracked users list if not already present
    if clean_username not in sync_state["tracked_users"]:
        sync_state["tracked_users"].append(clean_username)

    # Launch background task
    background_tasks.add_task(perform_sync, clean_username)

    return {
        "status": "started",
        "message": f"Instagram sync started for @{clean_username}. Data and covers will be stored in ./{clean_username}/",
        "username": clean_username,
        "is_syncing": True
    }

@app.get("/api/sync/status")
def get_sync_status():
    """Check current sync state and last execution details."""
    return {
        "status": "success",
        "sync_state": sync_state
    }

@app.get("/api/schedule")
def get_schedule():
    """Information on daily scheduled morning fetch."""
    return {
        "daily_schedule_time": f"{DAILY_SYNC_TIME} AM (7.5 AM)",
        "frequency": "Daily",
        "tracked_users": sync_state["tracked_users"],
        "scheduler_running": sync_state["scheduler_running"],
        "description": f"Fetches all new posts & reels every day at {DAILY_SYNC_TIME} AM and persists them locally."
    }

# ============================================================================
# RUNNER
# ============================================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"\n" + "=" * 65)
    print(f"🚀 INSTAGRAM FETCHER & REST API SERVER")
    print(f"[*] API Server  : http://localhost:{port}")
    print(f"[*] Interactive Docs: http://localhost:{port}/docs")
    print(f"[*] Daily Schedule : {DAILY_SYNC_TIME} AM (7.5 AM)")
    print(f"[*] Default Tracked: @{DEFAULT_USERNAME}")
    print(f"=" * 65 + "\n")
    uvicorn.run("server:app", host=host, port=port, reload=False)

