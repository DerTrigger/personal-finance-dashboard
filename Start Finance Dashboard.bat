@echo off
rem Opens the finance dashboard in the browser. Local only; close this window to stop it.
cd /d "%~dp0"
"C:\Users\<you>\.venvs\finance-dashboard\Scripts\python.exe" -m streamlit run app\dashboard.py
