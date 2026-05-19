@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo    简历拷打面试官 - Interview
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo [*] 首次运行，正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [!] 创建虚拟环境失败，请确认已安装 Python 并加入 PATH
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

REM 检查依赖是否已安装
python -c "import langchain_huggingface" 2>nul
if errorlevel 1 (
    echo [*] 正在升级 pip...
    python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo [*] 正在安装依赖...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [!] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [*] 启动面试程序...
echo.
python main.py

pause
