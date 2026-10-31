#!/usr/bin/env python
"""
Command line runner for the Instagram Fetcher & REST API Server.
Usage:
  python run_server.py               # runs on http://localhost:8000
  python run_server.py --port 8080   # custom port
  python run_server.py --sync-now    # immediately sync before starting server
"""

import sys
import argparse
import uvicorn
import os

def main():
    parser = argparse.ArgumentParser(description="Instagram Reels Fetcher & Daily 7:30 AM Sync API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--sync-now", action="store_true", help="Run sync immediately for default user before starting server")
    parser.add_argument("--user", default="vaibhav.codes", help="Default Instagram username (default: vaibhav.codes)")
    parser.add_argument("--schedule-time", default="07:30", help="Daily sync time in HH:MM (default: 07:30)")

    args = parser.parse_args()

    os.environ["DEFAULT_INSTA_USERNAME"] = args.user
    os.environ["DAILY_SYNC_TIME"] = args.schedule_time

    if args.sync_now:
        print(f"[*] Running pre-start sync for @{args.user}...")
        try:
            from instagram_exporter import run_export
            run_export(args.user)
        except Exception as e:
            print(f"[!] Pre-start sync error: {e}")

    uvicorn.run("server:app", host=args.host, port=args.port, reload=True)

if __name__ == "__main__":
    main()

