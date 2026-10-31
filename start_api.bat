@echo off
title Instagram Reels API Server (Daily 7:30 AM Fetcher)
cd /d "%~dp0"
echo ========================================================
echo  Starting Instagram Reels API Server on port 8000
echo  Daily Cron: 07:30 AM (7.5 AM)
echo  API Documentation: http://localhost:8000/docs
echo ========================================================
python run_server.py --port 8000
pause

