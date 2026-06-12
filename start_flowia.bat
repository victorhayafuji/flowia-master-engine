@echo off
TITLE FlowIA Master Engine - Launcher
echo.
echo ==========================================
echo    INICIALIZANDO FLOWIA MASTER ENGINE
echo ==========================================
echo.

:: Diretorio base e deploy (multi-tenant ou tenants\slug)
set "PROJECT_ROOT=%~dp0"
set "DEPLOY=%~1"
if "%DEPLOY%"=="" set "DEPLOY=multi-tenant"
cd /d "%PROJECT_ROOT%"

echo [DEBUG] Pasta Raiz: %PROJECT_ROOT%
echo [DEBUG] Deploy: deployments\%DEPLOY%

:: Carrega .env do template de deploy se .env nao existir
if not exist ".env" (
    if exist "deployments\%DEPLOY%\.env.example" (
        echo [INFO] Copiando deployments\%DEPLOY%\.env.example para .env
        copy /Y "deployments\%DEPLOY%\.env.example" ".env" >nul
    ) else (
        echo [AVISO] deployments\%DEPLOY%\.env.example nao encontrado; use .env na raiz.
    )
)

:: Verifica Python
if not exist "venv\Scripts\python.exe" (
    echo [ERRO] venv\Scripts\python.exe nao encontrado!
    echo Certifique-se de que o ambiente virtual foi criado.
    echo.
    pause
    exit /b
)

:: Seleciona o Node 24 do nvm-windows (projeto padronizado em Node 24 LTS).
:: O Node do PATH (standalone) pode ser uma versao antiga que nao roda o Vite.
set "NVM_ROOT=%LOCALAPPDATA%\nvm"
set "NODE_DIR="
for /f "delims=" %%v in ('dir /b /ad /o-n "%NVM_ROOT%\v24.*" 2^>nul') do (
    if not defined NODE_DIR set "NODE_DIR=%NVM_ROOT%\%%v"
)
if defined NODE_DIR (
    echo [INFO] Usando Node 24 do nvm: %NODE_DIR%
    set "PATH=%NODE_DIR%;%PATH%"
) else (
    echo [AVISO] Node 24 nao encontrado em %NVM_ROOT%. Rode: nvm install 24
    echo [AVISO] O Vite pode falhar com Node antigo.
)

:: Backend
echo [INFO] Iniciando Backend (FastAPI) na porta 8000...
start "FlowIA - Backend (FastAPI)" cmd /c "venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: Frontend salao
echo [INFO] Iniciando Frontend (React/Vite) na porta 5173...
start "FlowIA - Frontend (Vite)" cmd /c "cd apps\salon\dashboard && npm run dev"

echo.
echo ==========================================
echo [SUCESSO] Os servidores estao inicializando!
echo - Backend: porta 8000
echo - Frontend salao: porta 5173
echo - Deploy: %DEPLOY%
echo ==========================================
echo.
echo Uso: start_flowia.bat [multi-tenant ^| tenants\beauty-express]
echo.
echo Pressione qualquer tecla para fechar este inicializador...
pause >nul
