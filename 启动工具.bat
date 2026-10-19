@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   抖音主页视频批量分析工具  启动中...
echo ============================================
echo.

REM ---- 选定 Python 解释器 ----
REM 优先用 py -3.12；若启动器找不到（本机常见），回退到 uv 管理的 3.12 路径
set "PYEXE="
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=py -3.12"
) else if exist "C:\Users\49388\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" (
    set "PYEXE=C:\Users\49388\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
) else (
    echo [错误] 未找到 Python 3.12，请先安装 Python 3.12 后再运行本脚本。
    pause
    exit /b 1
)

echo [1/3] 使用解释器: %PYEXE%

REM ---- 首次运行：创建虚拟环境并安装依赖 ----
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [首次运行] 正在创建虚拟环境并安装依赖，需要几分钟，请耐心等待...
    echo （之后再启动就会很快）
    echo.
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请把上面的报错截图反馈。
        pause
        exit /b 1
    )
    echo.
    echo 依赖安装完成！
)

echo [2/3] 启动本地服务...
REM 延迟 3 秒后自动打开浏览器
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"

echo [3/3] 浏览器将自动打开 http://127.0.0.1:8000
echo 关闭本窗口即停止服务。
echo.
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

pause
