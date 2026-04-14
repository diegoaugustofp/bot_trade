# Configuração de Notificações no Discord

Este guia explica como configurar o bot de trading para enviar notificações automáticas no Discord.

## O que será notificado?

- **Bot iniciado / encerrado** — quando o bot começa ou para de operar
- **Ordem colocada** — quando uma ordem limite é enviada ao MetaTrader 5
- **Trade ativado** — quando a ordem é preenchida e a posição abre
- **Fechamento parcial** — quando a parcial 1 ou parcial 2 é executada
- **Trade fechado** — quando a posição é encerrada (stop, alvo ou manual)
- **Limite diário de stops atingido** — alerta quando o bot bloqueia novas operações

---

## Passo 1 — Criar um Webhook no Discord

1. Abra o Discord e vá para o **servidor** onde deseja receber as notificações.
2. Clique com o botão direito no **canal de texto** desejado e selecione **Editar Canal**.
3. No menu lateral, clique em **Integrações** → **Webhooks**.
4. Clique em **Novo Webhook**.
5. Dê um nome (por exemplo, `Trade Bot`) e escolha o ícone que quiser.
6. Clique em **Copiar URL do Webhook** para copiar a URL.
7. Clique em **Salvar**.

---

## Passo 2 — Configurar a variável de ambiente

Escolha a opção mais adequada ao seu ambiente:

---

### Opção A — Rodando localmente no Windows

**PowerShell:**
```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/SEU_ID/SEU_TOKEN"
python run_bot.py --symbol EURUSD --strategy ma200_rejection
```

**CMD (Prompt de Comando):**
```cmd
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/SEU_ID/SEU_TOKEN
python run_bot.py --symbol EURUSD --strategy ma200_rejection
```

**Permanente no Windows:** Adicione `DISCORD_WEBHOOK_URL` via *Painel de Controle → Sistema → Configurações avançadas do sistema → Variáveis de Ambiente*.

---

### Opção B — Usando arquivo `.env` (com `python-dotenv`)

Instale a dependência:
```bash
pip install python-dotenv
```

Crie um arquivo `.env` na raiz do projeto (mesmo diretório de `run_bot.py`):
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/SEU_ID/SEU_TOKEN
DATABASE_URL=postgresql://user:senha@host:5432/dbname
```

O arquivo `.env` é carregado automaticamente pelo `run_bot.py` via `python-dotenv`. **Nunca versione este arquivo** — adicione ao `.gitignore`:
```
.env
```

---

### Opção C — Replit Secrets (para o servidor API no Replit)

O servidor API que controla o toggle do Discord roda no Replit. Para que ele detecte o webhook:

1. No Replit, abra a aba **Secrets** (ícone de cadeado no painel lateral).
2. Clique em **New Secret**.
3. Nome: `DISCORD_WEBHOOK_URL`
4. Valor: cole a URL do webhook copiada no Passo 1.
5. Clique em **Add Secret**.
6. Reinicie o workflow **"API Server"** para que o novo secret seja carregado.

> **Nota:** O Replit Secrets injeta automaticamente a variável como `process.env.DISCORD_WEBHOOK_URL` no servidor Node.js. No bot Python local, utilize a Opção A ou B.

---

## Passo 3 — Ativar no Dashboard

1. Abra o dashboard no navegador.
2. Vá para a página **Configuration**.
3. Role até a seção **Integrações**.
4. Verifique se o status mostra **"Webhook configurado"** (ícone verde).
5. Ative o toggle do **Discord**.

> Se o status mostrar **"Webhook não configurado"** (ícone vermelho), a variável `DISCORD_WEBHOOK_URL` não está definida no processo do servidor API. Reinicie o servidor após definir a variável.

---

## Solução de problemas

| Problema | Causa provável | Solução |
|---|---|---|
| Toggle desativado (cinza) | `DISCORD_WEBHOOK_URL` não está definido | Defina a variável e reinicie o servidor |
| Notificações não chegam | Toggle está desligado | Ative o toggle na aba Configuration |
| Erro 404 no webhook | URL incorreta ou webhook deletado | Recrie o webhook e atualize a variável |
| Mensagens duplicadas | Múltiplas instâncias do bot rodando | Verifique se há apenas um processo `run_bot.py` por símbolo/estratégia |

---

## Exemplo de notificação

```
🚀 Bot Iniciado
Símbolo: EURUSD
Estratégia: MA200 Rejection
Lote: 0.10 | Timeframe: 15m
```

```
📋 Ordem Colocada
Símbolo: EURUSD | BUY
Preço: 1.08450
Stop Loss: 1.08350
Lote: 0.10
Estratégia: MA200 Rejection
```

```
✅ Trade Fechado
Símbolo: EURUSD | BUY
PnL: +R$ 85.00
Motivo: alvo
Stops hoje: 0
Estratégia: MA200 Rejection
```
