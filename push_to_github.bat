@echo off
cd /d "%~dp0"

echo Adding all changes...
git add .

echo Committing changes...
set /p msg="Enter Commit Date: "
git commit -m "%msg%"

echo Pushing to GitHub...
git push origin main

echo Done.
pause
