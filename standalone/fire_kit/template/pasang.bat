@echo off
rem Pasang sekali: membuat lingkungan Python di folder .venv dan memasang pustaka dari requirements.txt
cd /d "%~dp0"
python --version || (echo Python tidak ditemukan. Pasang Python 3.11-3.13 64-bit dari python.org, centang "Add python.exe to PATH". & pause & exit /b 1)
python -m venv .venv || (pause & exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Pemasangan gagal. & pause & exit /b 1)
echo.
echo Selesai. Letakkan data di folder data, periksa config.yaml, lalu jalankan jalankan.bat
pause
