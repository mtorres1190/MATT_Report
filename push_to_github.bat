@echo off
setlocal enabledelayedexpansion

echo -----------------------------------------------------
echo Starting MATT_Report GitHub Sync...
echo -----------------------------------------------------

REM Navigate to your local project folder
cd /d "C:\Users\MiTorres\OneDrive - Lennar Azure AD\Files\Daily Reports\MATT Application"

REM Ensure Git identity is set
git config user.name "Michael Torres"
git config user.email "michael.torres@lennar.com"

REM Initialize git if not already done
if not exist ".git" (
    echo Initializing new git repository...
    git init
    git branch -M main
    git remote add origin https://github.com/michael-torres_lensbx/MATT_Report.git
) else (
    echo Git repository already initialized.
    git remote set-url origin https://github.com/michael-torres_lensbx/MATT_Report.git
)

REM Stage all changes
echo Staging all changes...
git add .

REM Commit changes
set commitmsg=Sync local project with GitHub (scripts and data)
git commit -m "%commitmsg%"

REM Push to GitHub
echo Pushing to remote repository...
git push -u origin main

echo -----------------------------------------------------
echo GitHub Sync Complete!
echo -----------------------------------------------------

pause

