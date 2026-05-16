@echo off
rem Использование:
rem   run.bat URL [URL2 URL3 ...]
rem             [--length МИНУТЫ]
rem             [--insert YT_URL [YT_URL2 ...]]
rem             [--note "любые указания"]
rem
rem Примеры:
rem   run.bat https://the-flow.ru/article
rem   run.bat https://the-flow.ru/article --length 10
rem   run.bat https://news.ru/art1 https://youtube.com/watch?v=xxx --length 8
rem   run.bat https://the-flow.ru/article --insert https://yt.com/v=aaa https://yt.com/v=bbb
rem   run.bat https://the-flow.ru/article --length 12 --note "сделай упор на конфликт, добавь хронологию"

set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python script_agent.py %*
