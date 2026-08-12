@echo off
rem psh - pinned shell. Replays context pins, then runs your command.
if "%PIN_PY%"=="" set PIN_PY=pin.py
python "%PIN_PY%" wrap -- %*
exit /b %ERRORLEVEL%
