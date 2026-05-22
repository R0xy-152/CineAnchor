# CineAnchor 后端启动器 (含公网隧道)
$env:CUDA_HOME = 'C:\Users\27079\miniconda3\Library'
$env:TORCH_CUDA_ARCH_LIST = '8.9'
$msvc = 'D:\VisualStudio\VC\Tools\MSVC\14.44.35207'
$sdk = 'C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0'
$env:INCLUDE = "$msvc\include;$sdk\ucrt;$sdk\shared;$sdk\um;$sdk\winrt;$sdk\cppwinrt"
$env:LIB = "$msvc\lib\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\ucrt\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\um\x64"
$env:PATH = "$msvc\bin\Hostx64\x64;$env:CUDA_HOME\bin;$env:PATH"
$env:HTTP_PROXY = 'http://127.0.0.1:7890'
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:MSYS2_ARG_CONV_EXCL = '*'

Write-Host "=== CineAnchor Backend ===" -ForegroundColor Cyan
Write-Host "API:  http://127.0.0.1:8001" -ForegroundColor Green
Write-Host "Docs: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Cyan

# 启动 Cloudflare Tunnel (后台)
$tunnel = Start-Process -FilePath "cloudflared" -ArgumentList "tunnel","--url","http://localhost:8001" -PassThru -NoNewWindow -RedirectStandardOutput "$env:TEMP\cloudflared.log"

Start-Sleep -Seconds 5
$log = Get-Content "$env:TEMP\cloudflared.log" -Tail 20
$tunnelUrl = ($log | Select-String -Pattern 'https://.*trycloudflare.com').Matches.Value
if ($tunnelUrl) {
    Write-Host "Public: $tunnelUrl" -ForegroundColor Yellow
    Write-Host "Frontend API config: window.CINEANCHOR_API = '$tunnelUrl'" -ForegroundColor Yellow
}

# 启动 FastAPI
python -m uvicorn main:app --host 0.0.0.0 --port 8001

# 清理
Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
