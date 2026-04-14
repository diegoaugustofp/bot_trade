# Trade Bot MT5 — Robô de Trading com Painel Web

Robô de trading automatizado para MetaTrader 5 com painel de monitoramento em tempo real. O bot executa múltiplas estratégias em paralelo, uma por símbolo, e sincroniza as operações com um banco PostgreSQL compartilhado com o painel web.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Pré-requisitos](#pré-requisitos)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Execução](#execução)
- [Banco de Dados](#banco-de-dados)
- [Estratégias](#estratégias)
- [Painel Web](#painel-web)
- [API](#api)

---

## Visão Geral

```
MetaTrader 5 (Windows)
        │
        ▼
  trade_bot (Python)  ──── grava operações ──▶  PostgreSQL
        │                                            │
        └── lê configurações ◀────────────────────┘
                                                     │
                                              API Server (Node.js)
                                                     │
                                          Trade Dashboard (React)
```

**Componentes:**

| Componente | Tecnologia | Função |
|---|---|---|
| Robô | Python 3.8+ + MetaTrader5 | Executa estratégias e envia ordens |
| API Server | Node.js + Express | REST API entre banco e painel |
| Dashboard | React + Vite | Monitoramento e configuração em tempo real |
| Banco de dados | PostgreSQL | Estado compartilhado entre todos os componentes |

---

## Pré-requisitos

### Para o Robô (obrigatório)

- **Windows** com MetaTrader 5 instalado e logado em uma conta
- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **PostgreSQL** rodando localmente ou banco remoto (ex.: [Neon.tech](https://neon.tech))

> **Atenção — PATH do PostgreSQL no Windows:** após instalar o PostgreSQL, adicione
> o diretório `bin` ao PATH do sistema para que o `psycopg2` encontre a `libpq.dll`:
> 1. Pesquise **"Variáveis de Ambiente"** no menu Iniciar
> 2. Em **Variáveis do sistema**, clique em `Path` → **Editar**
> 3. Adicione: `C:\Program Files\PostgreSQL\<versão>\bin` (ex.: `...\16\bin`)
> 4. Abra um novo terminal e teste: `python -c "import psycopg2; print(psycopg2.__version__)"`

### Para o Painel Web (obrigatório)

- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **pnpm 9+** — instalação: `npm install -g pnpm`

---

## Estrutura de Pastas

```
.
├── artifacts/
│   ├── api-server/          # Servidor REST (Node.js + Express + Drizzle)
│   │   └── src/
│   │       └── routes/
│   │           └── bot.ts   # Endpoints: status, trades, configurações
│   └── trade-dashboard/     # Painel web (React + Vite + shadcn/ui)
│       └── src/
│           └── pages/
│               ├── dashboard.tsx  # Status do robô e métricas do dia
│               ├── trades.tsx     # Histórico de operações
│               └── config.tsx     # Configuração por símbolo
│
├── lib/
│   ├── db/                  # Schema do banco (Drizzle ORM)
│   │   └── src/schema/
│   │       ├── bot_config.ts   # Tabela de configurações por símbolo
│   │       ├── bot_status.ts   # Tabela de status do robô
│   │       └── trades.ts       # Tabela de operações
│   ├── api-zod/             # Schemas Zod compartilhados (validação de API)
│   ├── api-spec/            # OpenAPI spec + codegen (orval)
│   └── api-client-react/    # Hooks React gerados automaticamente via codegen
│
├── trade_bot/               # Robô Python
│   ├── engine.py            # Motor principal: loop de trading por símbolo
│   ├── orchestrator.py      # Orquestrador multi-estratégia com bloqueio por símbolo
│   ├── models.py            # Modelos de dados internos do robô
│   ├── db.py                # Integração com PostgreSQL (psycopg2)
│   └── strategies/
│       ├── base.py              # Interface base para estratégias
│       ├── ma200_rejection.py   # Recusa na MA200
│       ├── ema_crossover.py     # Cruzamento de EMAs
│       ├── pullback_trend.py    # Pullback em tendência
│       ├── rsi_divergence.py    # Divergência RSI
│       ├── breakout_nbars.py    # Breakout de N barras
│       ├── macd_signal.py       # Cruzamento MACD/Signal
│       └── poi.py               # Recusa em Pontos de Interesse
│
├── run_bot.py                        # Ponto de entrada do robô (modo single e multi)
├── bot_config.json                   # Configuração ativa do robô
├── bot_config.single.example.json    # Template: modo single, um símbolo
├── bot_config.multi.example.json     # Template: modo multi, vários símbolos
├── start-local.bat                   # Script de inicialização para Windows
├── .env.example                      # Modelo de variáveis de ambiente
└── pnpm-workspace.yaml               # Configuração do monorepo pnpm
```

---

## Instalação

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd <nome-da-pasta>
```

### 2. Instale as dependências Python

```bash
pip install MetaTrader5 psycopg2-binary
```

### 3. Configure o banco de dados

**Opção A — PostgreSQL local:**
```bash
# Crie o banco (via psql ou pgAdmin)
createdb tradebot
```

**Opção B — Banco remoto gratuito (Neon.tech):**
1. Crie uma conta em [neon.tech](https://neon.tech)
2. Crie um projeto e copie a *Connection String*
3. Use essa string como `DATABASE_URL` (já inclui `sslmode=require`)

### 4. Configure as variáveis de ambiente

Edite o arquivo `start-local.bat` e defina:

```bat
SET DATABASE_URL=postgresql://postgres:SENHA@localhost:5432/tradebot?sslmode=disable
SET SESSION_SECRET=uma-chave-aleatoria-longa
```

> Para gerar uma chave segura: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Configuração

### Robô Python — `bot_config.json`

Toda a configuração do robô fica no arquivo `bot_config.json` na raiz do projeto. Ele é lido na inicialização e serve como **fallback offline** quando o banco não estiver disponível.

O projeto inclui dois arquivos de exemplo prontos para copiar:

| Arquivo | Uso |
|---------|-----|
| `bot_config.single.example.json` | Template para modo single — um símbolo com todos os campos documentados |
| `bot_config.multi.example.json` | Template para modo multi — três símbolos com estratégias diferentes |

Para começar, copie o exemplo adequado:

```bash
# Modo single (um símbolo):
copy bot_config.single.example.json bot_config.json   # Windows
cp   bot_config.single.example.json bot_config.json   # Linux/macOS

# Modo multi (vários símbolos em paralelo):
copy bot_config.multi.example.json bot_config.json
cp   bot_config.multi.example.json bot_config.json
```

Edite `bot_config.json` e ajuste pelo menos:
- `symbol` — símbolo exatamente como aparece no MT5
- `strategy_name` — estratégia desejada (ver [Estratégias](#estratégias))
- `lot_size`, `entry_offset`, `stop_loss`, parciais
- `strategy_params` — parâmetros da estratégia escolhida

**Seleção do modo de execução:**

```bash
# Modo single (padrão) — usa o primeiro entry, ou o que bater com SYMBOL
python run_bot.py
SYMBOL=WINM25 python run_bot.py

# Modo multi — executa todos os entries em paralelo
BOT_MODE=multi python run_bot.py
```

**Prioridade de configuração:** quando o banco estiver disponível, o robô usa os valores do banco (editáveis pelo painel) e ignora os do arquivo. Se um símbolo existir no `bot_config.json` mas não no banco, ele é inserido automaticamente. Se o banco estiver indisponível, o arquivo é usado como fallback.

### Painel Web

As configurações por símbolo são gerenciadas diretamente pelo painel (página **Configurações**). Não é necessário editar arquivos.

---

## Execução

### Painel Web (Windows)

Execute `start-local.bat` com duplo clique — ele:
1. Instala as dependências automaticamente (apenas na primeira vez)
2. Cria as tabelas no banco de dados
3. Abre o API Server em `http://localhost:8080`
4. Abre o Dashboard em `http://localhost:3000`

### Painel Web (manual)

```bash
# Terminal 1 — API
PORT=8080 pnpm --filter @workspace/api-server run dev

# Terminal 2 — Dashboard
PORT=3000 BASE_PATH=/ pnpm --filter @workspace/trade-dashboard run dev
```

### Robô Python

```bash
python run_bot.py                      # single — primeiro entry do bot_config.json
SYMBOL=WINM25 python run_bot.py        # single — symbol específico
BOT_MODE=multi python run_bot.py       # multi  — todos os entries em paralelo
```

> O MetaTrader 5 deve estar aberto e logado. Configure o `bot_config.json` antes (ver [Configuração](#configuração)).

---

## Banco de Dados

O banco possui três tabelas. As tabelas são criadas automaticamente na primeira execução do `start-local.bat`.

### `bot_config` — Configurações por símbolo

Cada linha representa a configuração de um símbolo. Um mesmo símbolo pode rodar estratégias diferentes.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | serial | Chave primária |
| `symbol` | text | Símbolo do ativo (ex.: `WINM25`) — único |
| `strategy_name` | text | Estratégia ativa (ver lista abaixo) |
| `strategy_params` | jsonb | Parâmetros específicos da estratégia |
| `lot_size` | real | Tamanho do lote |
| `ma200_period` | integer | Período da média móvel (padrão: 200) |
| `entry_offset` | real | Distância em ticks (trade_tick_size) do preço de referência até a entrada |
| `stop_loss` | real | Stop loss em ticks (trade_tick_size) |
| `partial1_percent` | real | % do lote na 1ª parcial |
| `partial1_points` | real | Alvo em ticks de lucro para a 1ª parcial |
| `partial2_percent` | real | % do lote na 2ª parcial |
| `partial2_points` | real | Alvo em ticks de lucro para a 2ª parcial |
| `partial3_points` | real | Alvo em ticks de lucro para a 3ª parcial (posição restante) |
| `max_open_trades` | integer | Máximo de trades abertos simultaneamente |
| `max_daily_stops` | integer | Máximo de stops no dia antes de bloquear |
| `timeframe_minutes` | integer | Timeframe em minutos (ex.: 5 = M5) |
| `trading_start_time` | text | Horário de início das operações (ex.: `09:15`) |
| `trading_end_time` | text | Horário de encerramento de novas entradas |
| `force_close_time` | text | Horário de fechamento forçado de todas as posições |
| `max_daily_loss_pts` | real | Perda máxima diária em R$ (opcional) |
| `max_daily_profit_pts` | real | Ganho máximo diário em R$ (opcional) |
| `break_even_pts` | real | Ticks de lucro para mover stop para breakeven |
| `cancel_pending_after_bars` | integer | Barras sem fill para cancelar ordem pendente |
| `updated_at` | timestamp | Última atualização |

### `trades` — Operações

Cada linha representa uma ordem enviada pelo robô.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | serial | Chave primária |
| `symbol` | text | Símbolo da operação |
| `direction` | text | Direção: `BUY` ou `SELL` |
| `order_price` | real | Preço da ordem limite |
| `entry_price` | real | Preço de execução (preenchido ao abrir) |
| `stop_loss` | real | Preço do stop loss |
| `ma200_at_entry` | real | Valor da MA200 no momento da entrada |
| `lot_size` | real | Tamanho do lote |
| `status` | text | `pending` → `open` → `closed` / `cancelled` |
| `partial1_closed` | boolean | 1ª parcial executada |
| `partial2_closed` | boolean | 2ª parcial executada |
| `profit_loss` | real | Resultado financeiro (preenchido ao fechar) |
| `close_reason` | text | Motivo do fechamento (stop, alvo, manual, etc.) |
| `opened_at` | timestamp | Momento em que a ordem foi executada |
| `closed_at` | timestamp | Momento em que a operação foi encerrada |
| `created_at` | timestamp | Momento em que o robô criou a ordem |

### `bot_status` — Status do Robô

Linha única atualizada continuamente pelo robô em execução.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | serial | Chave primária |
| `is_running` | boolean | Robô ativo no momento |
| `daily_stops` | integer | Número de stops no dia corrente |
| `current_price` | real | Último preço lido do MT5 |
| `current_ma200` | real | Valor atual da MA200 |
| `last_signal_at` | timestamp | Momento do último sinal gerado |
| `block_reason` | text | Motivo do bloqueio, se houver |
| `updated_at` | timestamp | Última atualização |

---

## Estratégias

As estratégias ficam em `trade_bot/strategies/` e implementam a interface `BaseStrategy`. Cada uma tem seu próprio dataclass de configuração.

| Estratégia | `strategy_name` | Lógica |
|---|---|---|
| Recusa na MA200 | `ma200_rejection` | Preço toca a MA200 e reverte; entra na direção do afastamento |
| Cruzamento de EMAs | `ema_crossover` | EMA rápida cruza a EMA lenta; entra na direção do cruzamento |
| Pullback em Tendência | `pullback_trend` | Tendência confirmada por EMA longa; entrada no recuo à EMA curta |
| Divergência RSI | `rsi_divergence` | Divergência entre preço e RSI sinaliza reversão |
| Breakout de N Barras | `breakout_nbars` | Rompimento da máxima/mínima das últimas N barras |
| Cruzamento MACD | `macd_signal` | MACD cruza a linha de sinal com confirmação do histograma |
| Pontos de Interesse | `poi` | Preço toca nível definido pelo usuário e reverte; cada nível é válido para 1 entrada |

### Dicionário de parâmetros por estratégia (`strategy_params`)

Os parâmetros abaixo são definidos no campo `strategy_params` — tanto no `bot_config.json` quanto na tabela `bot_config` do banco (editável pelo painel).

---

#### `ma200_rejection` — Rejeição na MA200

Sinal quando o preço toca a MA200 e reverte na direção oposta.
BUY: mínima toca a MA de cima para baixo → próxima barra fecha acima da MA.
SELL: máxima toca a MA de baixo para cima → próxima barra fecha abaixo da MA.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `ma_period` | `200` | Período da média móvel |
| `ma_type` | `"sma"` | Tipo da média: `"sma"` (simples) ou `"ema"` (exponencial) |
| `touch_threshold_pts` | `5.0` | Tolerância em pontos para considerar que o preço "tocou" a MA — quanto maior, mais folgado o toque aceito |
| `rejection_candles` | `2` | Barras de confirmação após o toque antes de emitir o sinal. `0` = sinal no próprio candle de toque (mais agressivo) |
| `min_distance_pts` | `0.0` | Distância mínima em pontos que o preço deve estar da MA para sinalizar; `0` desativa o filtro |

---

#### `ema_crossover` — Cruzamento de EMAs

Sinal no cruzamento de uma EMA rápida com uma EMA lenta.
BUY: EMA rápida cruza a EMA lenta de baixo para cima.
SELL: EMA rápida cruza a EMA lenta de cima para baixo.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `fast_period` | `9` | Período da EMA rápida (deve ser menor que `slow_period`) |
| `slow_period` | `21` | Período da EMA lenta |
| `confirmation_candles` | `1` | Barras de confirmação após o cruzamento antes de emitir o sinal |

> No `bot_config.json` e no banco use `fast_period` / `slow_period` (sem prefixo `ema_`).

---

#### `pullback_trend` — Pullback na EMA de Tendência

Sinal quando o preço recua até a EMA de tendência e a toca.
BUY: tendência de alta confirmada → preço toca a EMA (pullback de compra).
SELL: tendência de baixa confirmada → preço toca a EMA (pullback de venda).

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `trend_ema_period` | `34` | Período da EMA usada como referência de tendência e alvo do pullback |
| `touch_threshold_pts` | `8.0` | Tolerância em pontos para considerar que o preço "tocou" a EMA |
| `confirmation_candles` | `2` | Barras de confirmação após o toque antes de emitir o sinal |
| `trend_lookback` | `5` | Número de barras anteriores usadas para determinar a direção da tendência — o preço deve estar consistentemente acima (alta) ou abaixo (baixa) da EMA nesse período |

---

#### `rsi_divergence` — Divergência do RSI

Sinal quando há divergência clássica entre o movimento do preço e o RSI.
BUY (divergência de alta): preço faz mínima mais baixa, RSI faz mínima mais alta.
SELL (divergência de baixa): preço faz máxima mais alta, RSI faz máxima mais baixa.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `rsi_period` | `14` | Período do cálculo do RSI |
| `lookback_bars` | `20` | Número de barras anteriores onde a divergência é buscada |
| `rsi_overbought` | `70.0` | Limite de sobrecompra — divergência de SELL só é válida se o RSI estiver acima deste nível |
| `rsi_oversold` | `30.0` | Limite de sobrevenda — divergência de BUY só é válida se o RSI estiver abaixo deste nível |

---

#### `breakout_nbars` — Rompimento de N Barras

Sinal quando o preço rompe a máxima ou mínima de um período de consolidação.
BUY: candle fecha acima da máxima das últimas N barras.
SELL: candle fecha abaixo da mínima das últimas N barras.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `lookback_bars` | `20` | Número de barras que formam o range de referência |
| `min_range` | `50.0` | Range mínimo em pontos (máxima − mínima do período) para validar o rompimento; evita sinais em períodos de consolidação estreita |

> No `bot_config.json` e no banco use `min_range` (sem sufixo `_pts`).

---

#### `macd_signal` — Cruzamento MACD × Linha de Sinal

Sinal no cruzamento da linha MACD com sua linha de sinal.
BUY: MACD cruza a linha de sinal de baixo para cima (histograma vai de negativo para positivo).
SELL: MACD cruza a linha de sinal de cima para baixo.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `fast_period` | `12` | Período da EMA rápida usada no cálculo do MACD |
| `slow_period` | `26` | Período da EMA lenta usada no cálculo do MACD |
| `signal_period` | `9` | Período da EMA de suavização aplicada sobre o MACD (linha de sinal) |

---

#### `poi` — Pontos de Interesse (Point of Interest)

Sinal quando o preço toca um nível de suporte ou resistência configurado manualmente e reverte.
BUY: preço vem de cima e toca um `buy_level` (suporte).
SELL: preço vem de baixo e toca um `sell_level` (resistência).
Cada nível é consumido após gerar um sinal e só é reutilizado na sessão seguinte.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `buy_levels` | `[]` | Lista de preços de suporte (compra), ex: `[125000, 124500]`. Até 10 níveis. |
| `sell_levels` | `[]` | Lista de preços de resistência (venda), ex: `[126000, 126500]`. Até 10 níveis. |
| `touch_threshold_pts` | `5.0` | Tolerância em pontos para considerar que o preço "tocou" o nível |
| `rejection_candles` | `2` | Barras de confirmação após o toque antes de emitir o sinal. `0` = sinal no candle de toque |

> Para visualizar os níveis POI diretamente no gráfico do MT5, use o indicador `indicators/POI_Levels.mq5` (ver `indicators/README.md`).

---

## Painel Web

O painel é acessado em `http://localhost:3000` e possui três páginas:

| Página | Rota | Descrição |
|---|---|---|
| Dashboard | `/` | Status do robô, preço atual, MA200, stops do dia e métricas |
| Operações | `/trades` | Histórico de trades com filtro por status e símbolo |
| Configurações | `/config` | Criação, edição e remoção de configurações por símbolo |

---

## API

O servidor REST roda em `http://localhost:8080`. Principais endpoints:

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/bot/status` | Status atual do robô |
| `GET` | `/bot/trades` | Lista de operações (aceita `?status=` e `?symbol=`) |
| `GET` | `/bot/configs` | Lista de configurações por símbolo |
| `POST` | `/bot/configs` | Cria uma nova configuração |
| `GET` | `/bot/configs/:symbol` | Busca configuração de um símbolo |
| `PUT` | `/bot/configs/:symbol` | Atualiza configuração de um símbolo |
| `DELETE` | `/bot/configs/:symbol` | Remove configuração de um símbolo |
| `GET` | `/health` | Health check do servidor |

A especificação completa está em `lib/api-spec/openapi.yaml`.
