@echo off
REM Windows Gorev Zamanlayici bunu cagirir.
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -m bist_screener.daily
