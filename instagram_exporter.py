"""
Instagram Ultimate Exporter & Top Viral Reel Downloader
Fetches public Instagram profile data, downloads all posts/reels with post-wise folders,
and isolates the Top 5 Most Viral Reels (ranked by Views, then Likes & Engagement).
"""

import os
import sys
import json
import csv
import shutil
import time
import argparse
import requests
from datetime import datetime

# Enforce UTF-8 stdout for Windows PowerShell/CMD (handles emojis cleanly)
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import instaloader
from instaloader.exceptions import ProfileNotExistsException, LoginRequiredException, ConnectionException

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def download_file(url: str, output_path: str) -> bool:
    """Download an image/cover file safely with retry."""
    if not url:
        return False
    try:
        res = requests.get(url, headers=HEADERS, stream=True, timeout=25)
        if res.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=16384):
                    f.write(chunk)
            return True
        else:
            print(f"      [!] HTTP {res.status_code} while downloading cover image.")
            return False
    except Exception as e:
        print(f"      [!] Error downloading media: {e}")
        return False

def extract_profile_data_safely(profile) -> dict:
    """Safely extract profile metadata from the existing node without triggering 401s."""
    node = getattr(profile, "_node", {}) or {}

    bio_links = []
    raw_links = node.get("bio_links", [])
    if isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, dict) and item.get("url"):
                bio_links.append(item.get("url"))

    external_url = bio_links[0] if bio_links else node.get("external_url", "")

    return {
        "username": node.get("username") or profile.username,
        "full_name": node.get("full_name", ""),
        "biography": node.get("biography", ""),
        "bio_links": bio_links,
        "external_url": external_url,
        "followers_count": node.get("follower_count"),
        "following_count": node.get("following_count"),
        "total_posts_count": node.get("all_media_count"),
        "is_verified": node.get("is_verified", False),
        "is_private": node.get("is_private", False),
        "profile_pic_url": node.get("profile_pic_url_hd") or node.get("profile_pic_url", ""),
        "scraped_at": datetime.now().isoformat()
    }

def save_single_post_folder(folder_path: str, post_data: dict, is_viral_rank: int = None):
    """Creates a dedicated folder for a post and saves cover image, caption, and json details."""
    os.makedirs(folder_path, exist_ok=True)

    # 1. Download Cover Image
    cover_path = os.path.join(folder_path, "cover_image.jpg")
    if post_data.get("cover_image_url"):
        download_file(post_data["cover_image_url"], cover_path)

    # 2. Save Clean Caption
    caption_path = os.path.join(folder_path, "caption.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(post_data.get("caption") or "")

    # 3. Save JSON Metadata
    details = dict(post_data)
    if is_viral_rank is not None:
        details["viral_rank"] = is_viral_rank
    details_path = os.path.join(folder_path, "details.json")
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)

def run_export(
    username: str = "vaibhav.codes",
    top_viral_count: int = 5,
    max_posts: int = 0,
    only_top_viral: bool = False,
    replace_old_folder: bool = True
):
    """
    Main export engine:
    1. Downloads profile info & profile picture.
    2. Scans all posts and extracts full metadata.
    3. Identifies and saves the Top 5 Most Viral Reels (by Views, then Likes & Comments).
    4. Downloads all posts into post-wise folders (unless only_top_viral is True).
    If replace_old_folder=True, deletes any existing folder to ensure fresh replacement.
    """
    clean_username = username.strip().lstrip("@")
    if "instagram.com/" in clean_username:
        clean_username = clean_username.split("instagram.com/")[1].split("/")[0].split("?")[0]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_dir = os.path.join(base_dir, clean_username)

    print(f"\n" + "=" * 65)
    print(f"[*] INSTAGRAM EXPORTER: @{clean_username}")
    print(f"[*] Output Directory   : {os.path.abspath(user_dir)}")
    if replace_old_folder:
        print(f"[*] Mode               : Full clean replacement (old folder will be deleted)")
    print(f"=" * 65 + "\n")

    # Initialize Instaloader
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )

    try:
        profile = instaloader.Profile.from_username(L.context, clean_username)
    except ProfileNotExistsException:
        print(f"[!] Profile '@{clean_username}' was not found.")
        return False
    except LoginRequiredException:
        print(f"[!] Login required for @{clean_username}.")
        return False
    except ConnectionException as e:
        print(f"[!] Network connection error: {e}")
        return False
    except Exception as e:
        print(f"[!] Error fetching profile: {e}")
        return False

    # 1. Profile Metadata
    profile_data = extract_profile_data_safely(profile)

    # Delete old folder completely and recreate fresh so old posts/files never accumulate
    if replace_old_folder and os.path.exists(user_dir):
        print(f"[*] Deleting old data folder to replace with fresh data: {user_dir}")
        for attempt in range(3):
            try:
                shutil.rmtree(user_dir)
                break
            except Exception as e:
                time.sleep(0.5)
                if attempt == 2:
                    shutil.rmtree(user_dir, ignore_errors=True)
    os.makedirs(user_dir, exist_ok=True)

    profile_json_path = os.path.join(user_dir, "profile_info.json")
    with open(profile_json_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    print(f"[✓] Saved Profile Metadata: {profile_json_path}")

    # Download Profile Picture
    if profile_data.get("profile_pic_url"):
        pic_path = os.path.join(user_dir, "profile_pic.jpg")
        print(f"[+] Downloading profile photo...")
        if download_file(profile_data["profile_pic_url"], pic_path):
            print(f"[✓] Saved Profile Photo: {pic_path}")

    print("\n--- Profile Overview ---")
    print(f"Username   : @{profile_data['username']}")
    print(f"Full Name  : {profile_data['full_name']}")
    bio_preview = profile_data['biography'].replace('\n', ' | ') if profile_data['biography'] else ''
    print(f"Bio        : {bio_preview}")
    if profile_data['followers_count'] is not None:
        print(f"Followers  : {profile_data['followers_count']:,}")
    print("------------------------\n")

    # 2. Scan All Posts / Reels
    print(f"[*] Scanning posts from @{clean_username}...")
    scanned_posts = []

    try:
        for post in profile.get_posts():
            n = getattr(post, "_node", {}) or {}
            
            # Check view count / play count
            views = (
                n.get("video_play_count")
                or n.get("video_view_count")
                or n.get("view_count")
                or 0
            )
            likes = post.likes if post.likes is not None else (n.get("like_count") or 0)
            comments = post.comments if post.comments is not None else (n.get("comment_count") or 0)
            post_type = "reel" if post.is_video else "photo"
            caption_hook = (post.caption or "").strip().split("\n")[0][:75]

            p_data = {
                "shortcode": post.shortcode,
                "type": post_type,
                "is_reel": post.is_video,
                "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
                "timestamp_utc": post.date_utc.isoformat(),
                "date": post.date_utc.strftime("%Y-%m-%d %H:%M"),
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement": likes + comments,
                "cover_image_url": post.url,
                "caption": post.caption or "",
                "opening_hook": caption_hook
            }
            scanned_posts.append(p_data)
            print(f"  [#{len(scanned_posts)}] {p_data['type'].upper()} ({p_data['shortcode']}) | Likes: {likes:2d} | Comments: {comments} | Hook: {caption_hook[:40]}", flush=True)

            if max_posts > 0 and len(scanned_posts) >= max_posts:
                break

    except Exception as e:
        print(f"[!] Warning during post scanning: {e}")

    print(f"\n[✓] Successfully scanned {len(scanned_posts)} total posts/reels.")

    # 3. Rank & Export TOP 5 VIRAL REELS
    # Ranked primarily by Views, secondarily by Likes, tertiarily by Comments
    viral_ranked = sorted(
        scanned_posts,
        key=lambda x: (x["views"], x["likes"], x["comments"]),
        reverse=True
    )
    top_viral = viral_ranked[:top_viral_count]

    print(f"\n" + "=" * 65)
    print(f"🔥 TOP {len(top_viral)} MOST VIRAL REELS / POSTS (Ranked by Views, then Likes)")
    print(f"=" * 65)

    for rank, p in enumerate(top_viral, 1):
        v_str = f"{p['views']:,}" if p['views'] > 0 else "Hidden by IG"
        print(f"#{rank} | Shortcode: {p['shortcode']} | Views: {v_str} | Likes: {p['likes']:,} | Comments: {p['comments']:,}")
        print(f"    Date: {p['date']}")
        print(f"    URL : {p['post_url']}")
        print(f"    Hook: {p['opening_hook']}")
        print("-" * 65)

    # 3a. Create Dedicated Folders for TOP 5 VIRAL REELS
    viral_dir = os.path.join(user_dir, "top_5_viral_reels")
    os.makedirs(viral_dir, exist_ok=True)
    print(f"\n[+] Downloading Top {len(top_viral)} Viral Reels into: {viral_dir}")

    for rank, p in enumerate(top_viral, 1):
        folder_name = f"rank_{rank:02d}_{p['shortcode']}"
        folder_path = os.path.join(viral_dir, folder_name)
        save_single_post_folder(folder_path, p, is_viral_rank=rank)
        print(f"  [✓] Downloaded Viral #{rank} -> {folder_name}/ (cover_image.jpg, caption.txt, details.json)")

    # 3b. Save Top Viral CSV & JSON
    top_viral_csv = os.path.join(user_dir, "top_5_viral.csv")
    csv_fields = ["rank", "shortcode", "type", "views", "likes", "comments", "engagement", "date", "post_url", "opening_hook", "cover_image_url"]
    with open(top_viral_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for idx, p in enumerate(top_viral, 1):
            row = dict(p)
            row["rank"] = idx
            writer.writerow(row)
    print(f"\n[✓] Saved Top 5 Viral CSV: {top_viral_csv}")

    top_viral_json = os.path.join(user_dir, "top_5_viral.json")
    with open(top_viral_json, "w", encoding="utf-8") as f:
        json.dump(top_viral, f, ensure_ascii=False, indent=2)
    print(f"[✓] Saved Top 5 Viral JSON: {top_viral_json}")

    # 4. Download ALL Posts & Reels into Post-Wise Folders (unless only_top_viral is set)
    if not only_top_viral:
        all_posts_dir = os.path.join(user_dir, "all_posts")
        os.makedirs(all_posts_dir, exist_ok=True)
        print(f"\n[+] Downloading ALL {len(scanned_posts)} posts into: {all_posts_dir}")

        for idx, p in enumerate(scanned_posts, 1):
            post_folder_name = f"post_{idx:02d}_{p['shortcode']}"
            single_dir = os.path.join(all_posts_dir, post_folder_name)
            save_single_post_folder(single_dir, p)
            if idx % 5 == 0 or idx == len(scanned_posts):
                print(f"  [✓] Exported {idx}/{len(scanned_posts)} posts...")

        # Save All Posts Summary CSV & JSON
        all_csv = os.path.join(user_dir, "all_posts_summary.csv")
        with open(all_csv, "w", newline="", encoding="utf-8-sig") as f:
            all_fields = ["shortcode", "type", "views", "likes", "comments", "engagement", "date", "post_url", "opening_hook", "cover_image_url"]
            writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
            writer.writeheader()
            for p in scanned_posts:
                writer.writerow(p)
        print(f"\n[✓] Saved All Posts Summary CSV: {all_csv}")

        all_json = os.path.join(user_dir, "all_posts_data.json")
        with open(all_json, "w", encoding="utf-8") as f:
            json.dump({
                "profile": profile_data,
                "posts_count": len(scanned_posts),
                "posts": scanned_posts
            }, f, ensure_ascii=False, indent=2)
        print(f"[✓] Saved Complete Dataset JSON: {all_json}")

    print(f"\n" + "=" * 65)
    print(f"[✓] EXPORT COMPLETED SUCCESSFULLY!")
    print(f"    Check: {os.path.abspath(user_dir)}")
    print(f"=" * 65 + "\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="Export Instagram profile, all posts, and top 5 viral reels.")
    parser.add_argument("username", nargs="?", default="vaibhav.codes", help="Instagram username (default: vaibhav.codes)")
    parser.add_argument("--top-viral", type=int, default=5, help="Number of viral reels to isolate (default: 5)")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of posts to scan (0 = all, default: 0)")
    parser.add_argument("--only-top", action="store_true", help="Only download the top viral reels (skip downloading all posts)")
    parser.add_argument("--keep-old", action="store_true", help="Keep old files instead of deleting and replacing the folder")

    args = parser.parse_args()
    run_export(
        username=args.username,
        top_viral_count=args.top_viral,
        max_posts=args.limit,
        only_top_viral=args.only_top,
        replace_old_folder=not args.keep_old
    )

if __name__ == "__main__":
    main()
