@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PORT=5000"

echo.
echo   英语精读教练 - 启动中
echo   ------------------------------------------

if not exist "%PY%" (
    echo   [1/3] 首次运行：创建虚拟环境...
    where python >nul 2>nul
    if errorlevel 1 (
        echo   [错误] 没有找到 python。请先安装 Python 3.10+ 并勾选 "Add to PATH"。
        echo          下载地址 https://www.python.org/downloads/
        goto :fail
    )
    python -m venv "%~dp0.venv"
    if errorlevel 1 goto :fail
    echo   [2/3] 安装依赖（第一次会比较慢）...
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install -r "%~dp0backend\requirements.txt"
    if errorlevel 1 goto :fail
) else (
    echo   [1/3] 虚拟环境已存在
)

cd backend

echo   [2/3] 检查数据库结构...
"%PY%" -m flask --app wsgi db upgrade >nul 2>&1
if errorlevel 1 (
    echo   [提示] db upgrade 未执行成功，改用自动建表。
)

echo   [3/3] 启动服务（浏览器会自动打开）...
echo.
"%PY%" -m flask --app wsgi serve --port %PORT%
set "EXITCODE=%errorlevel%"

if not "%EXITCODE%"=="0" (
    echo.
    echo   [错误] 服务异常退出，代码 %EXITCODE%
    echo   常见原因：端口 %PORT% 被占用，或依赖未安装完成。
    pause
)
exit /b %EXITCODE%

:fail
echo.
echo   启动失败，请把上面的报错发给我。
pause
exit /b 1
