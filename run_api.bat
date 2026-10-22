@echo off
title ShopifyIntel PRO — Headless REST API Server
color 0B
echo ====================================================================
echo   ShopifyIntel PRO — Headless REST API Server
echo   FastAPI Engine ^| Interactive Swagger Docs: http://localhost:8000/docs
echo ====================================================================
echo.
echo Starting Headless REST API on http://localhost:8000 ...
echo Swagger UI Documentation: http://localhost:8000/docs
echo ReDoc Documentation:      http://localhost:8000/redoc
echo.
start "" http://localhost:8000/docs
python api_server.py
pause
