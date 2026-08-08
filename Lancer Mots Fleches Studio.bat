@echo off
rem Lance l'app de bureau sans fenetre de console.
cd /d "%~dp0"
start "" pythonw main.py
