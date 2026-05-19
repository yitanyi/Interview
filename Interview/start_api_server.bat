@echo off
chcp 65001
echo ========================================
echo    Interview API Server
echo ========================================
echo.

echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python，请先安装Python 3.x
    pause
    exit /b 1
)

echo.
echo 检查依赖...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 错误：依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo 检查配置文件...
if not exist config.ini (
    echo 错误：未找到config.ini配置文件
    echo 请先复制config.ini.template为config.ini并配置API密钥
    pause
    exit /b 1
)

echo.
echo 启动API服务器...
echo.
python api_server.py

pause
