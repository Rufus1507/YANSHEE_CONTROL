# Kích hoạt môi trường ảo .venv cho dự án
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$scriptDir\.venv\Scripts\Activate.ps1"
Write-Host "Da kich hoat moi truong ao .venv (Python 3.11)!" -ForegroundColor Green
