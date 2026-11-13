@echo off
rem Menjalankan analisis. Contoh: jalankan.bat   atau   jalankan.bat --province Riau   atau   jalankan.bat --steps check
cd /d "%~dp0"
.venv\Scripts\python.exe -m kebakaran_lahan --config config.yaml %*
pause
