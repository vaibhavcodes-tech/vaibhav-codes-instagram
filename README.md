# Instagram Reels Data Fetcher & REST API Backend

A production-grade Python backend system designed to:
1. **Automate daily scraping at 07:30 AM (7.5 AM)**: Periodically fetch the latest reels and posts from Instagram.
2. **Store media & metadata locally**: Download high-resolution cover images (`cover_image.jpg`), captions (`caption.txt`), and structured metadata (`details.json`) in dedicated post folders under `./<username>/`.
3. **Expose a high-performance REST API**: Dynamic username parameter, sorting by `recent`, `oldest`, and `most_viral`, and home page limit support.
4. **Serve local media files**: Serve cover images through `/media/{username}/...` so that expiring Instagram CDN links never break frontend display.

---

## 📁 Project Structure

```text
insta data/
├── server.py                 # FastAPI application with CORS, static media & scheduler
├── run_server.py             # CLI runner with flags (--port, --user, --sync-now)
├── start_api.bat             # One-click Windows runner
├── instagram_exporter.py     # Core scraper engine using Instaloader
├── requirements.txt          # Python dependencies
├── README.md                 # Documentation
│
└── vaibhav.codes/            # Saved user data folder
    ├── profile_info.json     # Bio, follower count, links
    ├── profile_pic.jpg       # Profile photo
    ├── all_posts_data.json   # Full dataset of all posts & reels
    ├── top_5_viral.json      # Pre-calculated Top 5 viral reels
    ├── all_posts/            # Dedicated folder per post with local cover
    │   ├── post_01_De63i5ENCiN/
    │   │   ├── cover_image.jpg
    │   │   ├── caption.txt
    │   │   └── details.json
    │   └── ...
    └── top_5_viral_reels/    # Dedicated folders for top 5 viral reels
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start API Server
```bash
# Default (runs on http://localhost:8000)
python run_server.py

# Or on a custom port
python run_server.py --port 8000 --user vaibhav.codes

# Or on Windows, double-click:
start_api.bat
```

Interactive Swagger API docs will be live at:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 📡 REST API Endpoints

### 1. Get Reels (Dynamic Username, Sorting & Limit)
`GET /api/reels`

| Query Param | Type | Default | Description |
|---|---|---|---|
| `username` | string | `vaibhav.codes` | Any public Instagram username |
| `sort` | string | `recent` | `recent` (newest first), `oldest` (chronological), or `most_viral` (views + likes) |
| `limit` | integer | `0` | `5` for home page preview, or `0` for all reels |
| `type` | string | `all` | `all`, `reel`, or `photo` |

**Example Requests:**
- Home Page Recent 5: `GET http://localhost:8000/api/reels?username=vaibhav.codes&sort=recent&limit=5`
- Top Viral Reels: `GET http://localhost:8000/api/reels?username=vaibhav.codes&sort=most_viral`
- Oldest Reels: `GET http://localhost:8000/api/reels?username=vaibhav.codes&sort=oldest`

**Response Example:**
```json
{
  "status": "success",
  "username": "vaibhav.codes",
  "profile": {
    "full_name": "Vaibhav | Backend + AI",
    "biography": "...",
    "followers_count": 67
  },
  "sort": "recent",
  "limit": 5,
  "total_count": 38,
  "returned_count": 5,
  "last_synced": "2026-10-28T22:39:09.473957",
  "data": [
    {
      "shortcode": "De_9_3kNHYx",
      "type": "reel",
      "is_reel": true,
      "post_url": "https://www.instagram.com/p/De_9_3kNHYx/",
      "views": 0,
      "likes": 25,
      "comments": 2,
      "engagement": 27,
      "date": "2026-10-25 13:58",
      "opening_hook": "One expired cache key can take your whole database down. 💥",
      "caption": "...",
      "cover_image_url": "https://instagram.fna.fbcdn.net/...",
      "local_cover_url": "http://localhost:8000/media/vaibhav.codes/all_posts/post_04_De_9_3kNHYx/cover_image.jpg",
      "effective_cover_url": "http://localhost:8000/media/vaibhav.codes/all_posts/post_04_De_9_3kNHYx/cover_image.jpg"
    }
  ]
}
```

### 2. Single Reel Detail
`GET /api/reels/{shortcode}?username=vaibhav.codes`
Returns detailed metadata, caption, and local image for a specific reel.

### 3. User Profile
`GET /api/profile?username=vaibhav.codes`
Returns profile bio, avatar URL, follower count, and bio links.

### 4. Trigger Manual Sync / Scrape
`POST /api/sync?username=vaibhav.codes`
Runs an immediate fetch in the background and saves files into `./<username>/`.

### 5. Check Daily Schedule & Sync Status
`GET /api/schedule`
`GET /api/sync/status`
Returns information on the daily 07:30 AM scheduler and last execution.

---

## ⏰ Daily Automated 07:30 AM Fetch (7.5 AM)

The server automatically starts a background scheduler daemon on boot:
```python
schedule.every().day.at("07:30").do(scheduled_daily_job)
```
- Fires automatically at **07:30 AM every morning**.
- Iterates over all tracked users (configured via `DEFAULT_INSTA_USERNAME`).
- Downloads new reels and cover photos.
- Safe and non-destructive: if Instagram restricts access, existing local datasets are retained intact.
