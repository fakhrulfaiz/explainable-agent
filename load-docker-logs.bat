@echo off
echo Loading all logs from Docker to local...

REM Method 1: Copy from Docker volume using Alpine container
echo.
echo Method 1: Copying from Docker volume...
docker run --rm -v explainable-agent_backend_logs:/source -v %cd%/backend/logs:/destination alpine sh -c "cp -r /source/* /destination/ 2>/dev/null || echo 'No files to copy from volume'"

REM Method 2: Copy from running container (if available)
echo.
echo Method 2: Copying from running container...
docker cp explainable-agent-backend:/app/logs/. ./backend/logs/ 2>nul || echo "Container not running or logs directory empty"

REM Method 3: Copy all container logs using docker logs
echo.
echo Method 3: Exporting container logs...
docker logs explainable-agent-backend > ./backend/logs/container-logs.txt 2>&1

REM Show what was copied
echo.
echo Logs copied to ./backend/logs/:
dir /b backend\logs

echo.
echo Done! All Docker logs have been loaded to your local backend/logs directory.
pause
