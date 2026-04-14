@echo off
REM ============================================================
REM  start-local.bat - Sobe API + Painel localmente (Windows)
REM ============================================================
REM
REM  PRE-REQUISITOS:
REM    1. Node.js >= 18  (https://nodejs.org)
REM    2. pnpm >= 9      (npm install -g pnpm)
REM    3. PostgreSQL local instalado e rodando
REM       Crie o banco antes:  createdb tradebot
REM       (ou via pgAdmin: banco com nome "tradebot")
REM
REM  CONFIGURACAO:
REM    Edite as variaveis abaixo.
REM    As tabelas sao criadas automaticamente na primeira execucao.
REM
REM    DISCORD_WEBHOOK_URL (opcional):
REM      Para receber notificacoes no Discord, coloque a URL do webhook aqui.
REM      Exemplo: https://discord.com/api/webhooks/123456789/abcdef...
REM      Deixe em branco para desativar as notificacoes Discord.
REM ============================================================

REM --- Edite aqui: credenciais do banco, sessao e Discord ---
SET DATABASE_URL=postgresql://postgres:staffoda@localhost:5432/tradebot?sslmode=disable
SET SESSION_SECRET=1234567890poiuytrewqASDFGHJKLÇ
SET DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1492137692933394483/gYkb20uNu7Lv2pdMOiemS9VOWnkOjQvXn8zN5LGj9SqydX5ffksdpCjuo2ctcNEbZsMQ

echo.
echo ============================================================
echo   Trade Bot MT5 - Inicializacao local
echo ============================================================
echo.

REM --- Verifica se pnpm esta instalado ---
WHERE pnpm >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRO] pnpm nao encontrado. Instale com: npm install -g pnpm
    pause
    exit /b 1
)
echo [OK] pnpm encontrado.

REM --- Instala dependencias ---
REM IMPORTANTE: usar "call pnpm" pois pnpm e um .cmd no Windows.
REM Sem "call", o .bat encerra apos o primeiro comando pnpm.
echo.
echo [1/3] Instalando dependencias...
call pnpm install
echo [1/3] Concluido.

REM --- Cria/atualiza as tabelas no banco de dados ---
echo.
echo [2/3] Aplicando schema no banco de dados...
echo       URL: %DATABASE_URL%
call pnpm --filter @workspace/db run push
IF ERRORLEVEL 1 (
    echo.
    echo [ERRO] Falha ao aplicar schema. Verifique:
    echo   1. PostgreSQL esta rodando?
    echo   2. O banco "tradebot" existe?  ^(crie com: createdb tradebot^)
    echo   3. A senha na DATABASE_URL esta correta?
    echo      Atual: %DATABASE_URL%
    echo.
    pause
    exit /b 1
)
echo [2/3] Concluido.

REM --- Sobe os servidores ---
echo.
echo [3/3] Iniciando servidores...

start "Trade Bot - API Server" cmd /k "SET DATABASE_URL=%DATABASE_URL%&& SET SESSION_SECRET=%SESSION_SECRET%&& SET DISCORD_WEBHOOK_URL=%DISCORD_WEBHOOK_URL%&& SET PORT=8080&& call pnpm --filter @workspace/api-server run dev"

timeout /t 3 /nobreak > nul

start "Trade Bot - Dashboard" cmd /k "SET DATABASE_URL=%DATABASE_URL%&& SET DISCORD_WEBHOOK_URL=%DISCORD_WEBHOOK_URL%&& SET PORT=3000&& SET BASE_PATH=/&& call pnpm --filter @workspace/trade-dashboard run dev"

echo [3/3] Concluido.
echo.
echo ============================================================
echo   Servidores iniciados:
echo     API Server:      http://localhost:8080
echo     Trade Dashboard: http://localhost:3000
echo.
echo   Para parar: feche as duas janelas abertas
echo ============================================================
echo.
pause
