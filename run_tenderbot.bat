@echo off
echo Starting TenderBot morning pipeline...

cd /d C:\Users\vaish\Downloads\tenderbot
docker-compose up -d

start "LiteLLM" cmd /k "cd /d C:\Users\vaish\Downloads\tenderbot && venv\Scripts\activate && litellm --config litellm_config.yaml --port 4000 --drop_params"

start "Python-Main" cmd /k "cd /d C:\Users\vaish\Downloads\tenderbot\agents_python && call ..\venv\Scripts\activate && python main.py"

start "Mastra" cmd /k "cd /d C:\Users\vaish\Downloads\tenderbot\my_mastra_app && npx tsx src/server.ts"

echo Waiting 30 seconds for everything to start up...
timeout /t 30 /nobreak

cd /d C:\Users\vaish\Downloads\tenderbot\agents_python
call ..\venv\Scripts\activate
python fetch_tenders.py

echo Done. Check the other windows for any problems.
pause