@echo off
title NovaERP - Agente de impresion
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" tools\agente_impresion_windows.py
echo.
echo El agente se detuvo. Presione una tecla para cerrar esta ventana.
pause > nul
