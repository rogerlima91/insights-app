# tasks.ps1 — PowerShell equivalent of the Makefile
# Usage: .\tasks.ps1 <target>
# Targets: install, run, dev, clean, freeze

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "run", "dev", "clean", "freeze")]
    [string]$Target
)

switch ($Target) {
    "install" {
        Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
        pip install -r requirements.txt
    }
    "run" {
        Write-Host "Starting Streamlit app..." -ForegroundColor Cyan
        streamlit run app.py
    }
    "dev" {
        Write-Host "Starting Streamlit app (dev mode — auto-reload on save)..." -ForegroundColor Cyan
        streamlit run app.py --server.runOnSave true
    }
    "clean" {
        Write-Host "Removing __pycache__ directories and .pyc files..." -ForegroundColor Cyan
        Get-ChildItem -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force
        Get-ChildItem -Recurse -Include "*.pyc", "*.pyo" | Remove-Item -Force
        Write-Host "Clean complete." -ForegroundColor Green
    }
    "freeze" {
        Write-Host "Freezing current environment into requirements.txt..." -ForegroundColor Cyan
        pip freeze | Out-File -FilePath requirements.txt -Encoding utf8
        Write-Host "requirements.txt updated." -ForegroundColor Green
    }
}
