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
