"""
Notificações Discord via Webhook — Trade Bot MT5
================================================

Classe DiscordNotifier para envio de notificações sobre eventos de trading
para um canal Discord via Webhook. O envio é feito de forma assíncrona em
thread separada para não bloquear o loop principal do robô.

A integração é COMPLETAMENTE OPCIONAL e funciona em dois níveis:

1. Nível de ambiente: sem DISCORD_WEBHOOK_URL definida, todos os métodos
   são no-ops silenciosos.
2. Nível de banco (dashboard): mesmo com a URL definida, a flag
   discord_enabled no banco precisa ser True para enviar mensagens.
   O construtor aceita um BotDatabase para checar essa flag.

Configuração:
    Windows (PowerShell):
        $env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."

    Linux / macOS:
        export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

    Ou inclua no arquivo .env na raiz do projeto (lido via python-dotenv):
        DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

try:
    import urllib.request
    _URLLIB_AVAILABLE = True
except ImportError:
    _URLLIB_AVAILABLE = False

if TYPE_CHECKING:
    from trade_bot.db import BotDatabase


# Cores dos embeds Discord (formato decimal)
_COLOR_GREEN  = 0x00C896   # trade aberto / alvo atingido
_COLOR_YELLOW = 0xF5A623   # parcial / aviso
_COLOR_RED    = 0xE74C3C   # stop / bloqueio
_COLOR_GRAY   = 0x95A5A6   # bot parado


class DiscordNotifier:
    """
    Envia notificações de eventos de trading para um canal Discord via Webhook.

    Parâmetros:
        db: Instância opcional de BotDatabase para checar a flag discord_enabled.
            Se None, usa apenas a variável de ambiente para decidir se envia.

    O construtor lê DISCORD_WEBHOOK_URL do ambiente. Se a variável não estiver
    presente, todos os métodos tornam-se no-ops silenciosos.
    """

    def __init__(self, db: Optional[BotDatabase] = None) -> None:
        self._url: Optional[str] = os.environ.get("DISCORD_WEBHOOK_URL")
        self._db: Optional[BotDatabase] = db

        if self._url:
            logger.info(
                "[discord] Webhook configurado. "
                "Notificações ativadas se discord_enabled=true no banco."
            )
        else:
            logger.debug(
                "[discord] DISCORD_WEBHOOK_URL não definida. "
                "Notificações Discord desativadas."
            )

    @property
    def enabled(self) -> bool:
        """True se a URL está definida E a flag discord_enabled está ativa no banco."""
        if not self._url:
            return False
        if self._db is not None:
            return self._db.read_discord_enabled()
        return True

    # ------------------------------------------------------------------
    # Envio interno (fire-and-forget em thread separada)
    # ------------------------------------------------------------------

    def _send(self, payload: dict) -> None:
        """Envia o payload ao webhook em thread separada (não bloqueia o caller)."""
        if not self.enabled:
            return

        def _do_send():
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self._url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status not in (200, 204):
                        logger.warning(
                            "[discord] Webhook retornou status %d.", resp.status
                        )
            except Exception as exc:
                logger.warning("[discord] Falha ao enviar notificação: %s", exc)

        t = threading.Thread(target=_do_send, daemon=True, name="discord-notifier")
        t.start()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _embed(
        self,
        *,
        title: str,
        color: int,
        fields: list[dict],
        description: Optional[str] = None,
    ) -> dict:
        embed: dict = {
            "title": title,
            "color": color,
            "fields": fields,
            "timestamp": self._timestamp(),
        }
        if description:
            embed["description"] = description
        return {"embeds": [embed]}

    # ------------------------------------------------------------------
    # Eventos de trading
    # ------------------------------------------------------------------

    def on_order_placed(
        self,
        *,
        symbol: str,
        direction: str,
        order_price: float,
        stop_loss: float,
        lot_size: float,
        strategy_name: Optional[str] = None,
    ) -> None:
        """Ordem limite enviada ao MT5 (aguardando preenchimento)."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",           "inline": True},
            {"name": "Direção",    "value": f"**{direction}**",       "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—",     "inline": True},
            {"name": "Entry",      "value": f"`{order_price:.2f}`",   "inline": True},
            {"name": "Stop",       "value": f"`{stop_loss:.2f}`",     "inline": True},
            {"name": "Lote",       "value": f"`{lot_size}`",          "inline": True},
        ]
        self._send(self._embed(
            title="📋 Ordem Pendente Criada",
            color=_COLOR_YELLOW,
            fields=fields,
        ))

    def on_trade_activated(
        self,
        *,
        symbol: str,
        direction: str,
        entry_price: float,
        strategy_name: Optional[str] = None,
    ) -> None:
        """Ordem pendente preenchida — posição aberta."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",          "inline": True},
            {"name": "Direção",    "value": f"**{direction}**",      "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—",    "inline": True},
            {"name": "Entry Real", "value": f"`{entry_price:.2f}`",  "inline": True},
        ]
        self._send(self._embed(
            title="✅ Posição Aberta",
            color=_COLOR_GREEN,
            fields=fields,
        ))

    def on_partial_closed(
        self,
        *,
        symbol: str,
        partial_number: int,
        price: float,
        volume: float,
        strategy_name: Optional[str] = None,
    ) -> None:
        """Parcial executada (1ª ou 2ª)."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",           "inline": True},
            {"name": "Parcial",    "value": f"#{partial_number}",     "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—",     "inline": True},
            {"name": "Preço",      "value": f"`{price:.2f}`",         "inline": True},
            {"name": "Volume",     "value": f"`{volume:.2f}`",        "inline": True},
        ]
        self._send(self._embed(
            title=f"✂️ Parcial {partial_number} Executada",
            color=_COLOR_YELLOW,
            fields=fields,
        ))

    def on_trade_closed(
        self,
        *,
        symbol: str,
        direction: str,
        pnl: float,
        close_reason: str,
        daily_stops: int,
        strategy_name: Optional[str] = None,
    ) -> None:
        """Posição fechada (alvo, stop ou forçado)."""
        is_stop = pnl < 0
        title = "🔴 Stop Atingido" if is_stop else "🎯 Alvo Atingido"
        color = _COLOR_RED if is_stop else _COLOR_GREEN
        pnl_str = f"`{'+' if pnl >= 0 else ''}{pnl:.2f} pts`"
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",       "inline": True},
            {"name": "Direção",    "value": direction,            "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—", "inline": True},
            {"name": "PnL",        "value": pnl_str,             "inline": True},
            {"name": "Motivo",     "value": close_reason,        "inline": True},
        ]
        if is_stop:
            fields.append({"name": "Stops Hoje", "value": str(daily_stops), "inline": True})
        self._send(self._embed(
            title=title,
            color=color,
            fields=fields,
        ))

    def on_daily_stop_limit(
        self,
        *,
        symbol: str,
        daily_stops: int,
        max_daily_stops: int,
        strategy_name: Optional[str] = None,
    ) -> None:
        """Limite diário de stops atingido — sem novas operações hoje."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",       "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—", "inline": True},
            {"name": "Stops Hoje", "value": f"{daily_stops}/{max_daily_stops}", "inline": True},
        ]
        self._send(self._embed(
            title="⛔ Limite de Stops Atingido",
            description="O robô está bloqueado para novas entradas hoje neste símbolo.",
            color=_COLOR_RED,
            fields=fields,
        ))

    def on_bot_started(
        self,
        *,
        symbol: str,
        strategy_name: Optional[str] = None,
        lot_size: Optional[float] = None,
        timeframe_minutes: Optional[int] = None,
    ) -> None:
        """Bot iniciado."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",       "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—", "inline": True},
        ]
        if lot_size is not None:
            fields.append({"name": "Lote", "value": str(lot_size), "inline": True})
        if timeframe_minutes is not None:
            fields.append({"name": "Timeframe", "value": f"M{timeframe_minutes}", "inline": True})
        self._send(self._embed(
            title="🤖 Bot Iniciado",
            color=_COLOR_GREEN,
            fields=fields,
        ))

    def on_bot_stopped(
        self,
        *,
        symbol: str,
        strategy_name: Optional[str] = None,
        daily_pnl: Optional[float] = None,
    ) -> None:
        """Bot encerrado."""
        fields = [
            {"name": "Símbolo",    "value": f"`{symbol}`",       "inline": True},
            {"name": "Estratégia", "value": strategy_name or "—", "inline": True},
        ]
        if daily_pnl is not None:
            pnl_str = f"{'+' if daily_pnl >= 0 else ''}{daily_pnl:.2f} pts"
            fields.append({"name": "PnL do Dia", "value": pnl_str, "inline": True})
        self._send(self._embed(
            title="🔌 Bot Encerrado",
            color=_COLOR_GRAY,
            fields=fields,
        ))
