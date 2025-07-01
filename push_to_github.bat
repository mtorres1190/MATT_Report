@echo off
cd /d "%~dp0"

echo Adding all changes...
git add .

echo Committing changes...
git commit -m "Auto-push update"

echo Pulling latest changes from GitHub...
git pull origin main --no-edit

echo Pushing to GitHub...
git push origin main

echo Done.
pause
