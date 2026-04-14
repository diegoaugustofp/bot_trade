#!/usr/bin/env bash
# ============================================================
#  start-local.sh — Sobe API + Painel localmente (Linux/macOS)
# ============================================================
#
#  PRE-REQUISITOS:
#    1. Node.js >= 18  (https://nodejs.org)
#    2. pnpm >= 9      (npm install -g pnpm)
#    3. PostgreSQL local com o banco criado (rode neon_setup.sql)
#
#  CONFIGURACAO:
#    Edite as variaveis DATABASE_URL e SESSION_SECRET abaixo,
#    ou defina-as antes de executar o script:
#      DATABASE_URL="..." SESSION_SECRET="..." ./start-local.sh
#
#  EXECUCAO:
#    chmod +x start-local.sh
#    ./start-local.sh
# ============================================================

set -e

# --- Edite aqui (ou sobrescreva via variavel de ambiente) ---
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:SENHA@localhost:5432/tradebot}"
export SESSION_SECRET="${SESSION_SECRET:-troque-por-uma-chave-secreta-aleatoria}"

# --- Instala dependencias (apenas na primeira vez) ---
if ! command -v pnpm &> /dev/null; then
    echo "[ERRO] pnpm nao encontrado. Instale com: npm install -g pnpm"
    exit 1
fi

echo "Instalando dependencias..."
pnpm install

# --- Sobe a API server na porta 8080 ---
echo "Iniciando API Server em http://localhost:8080 ..."
PORT=8080 pnpm --filter @workspace/api-server run dev &
API_PID=$!

# Pequena pausa para a API subir antes do dashboard
sleep 2

# --- Sobe o painel web na porta 3000 ---
echo "Iniciando Trade Dashboard em http://localhost:3000 ..."
PORT=3000 BASE_PATH=/ pnpm --filter @workspace/trade-dashboard run dev &
DASH_PID=$!

echo ""
echo " ============================================================"
echo "  Servidores iniciados:"
echo "    API Server:      http://localhost:8080"
echo "    Trade Dashboard: http://localhost:3000"
echo ""
echo "  Pressione Ctrl+C para encerrar ambos."
echo " ============================================================"
echo ""

# Encerra ambos os processos ao pressionar Ctrl+C
cleanup() {
    echo "Encerrando servidores..."
    kill "$API_PID" "$DASH_PID" 2>/dev/null || true
    wait "$API_PID" "$DASH_PID" 2>/dev/null || true
    echo "Encerrado."
}
trap cleanup INT TERM

wait
