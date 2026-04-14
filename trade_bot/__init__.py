"""
trade_bot — Pacote do Robô de Trade para MetaTrader 5
======================================================

Estrutura do pacote:
    trade_bot/
        models.py           — Enumerações e dataclasses compartilhadas
        engine.py           — Lógica de execução de ordens, gestão de risco e parciais
        strategies/
            base.py         — Classe abstrata BaseStrategy
            ma200_rejection.py — Estratégia original: recusa na MA200
            ema_crossover.py   — Cruzamento de EMAs
            pullback_trend.py  — Pullback em tendência via EMA34
            rsi_divergence.py  — Divergência de RSI
            breakout_nbars.py  — Rompimento de N barras
            macd_signal.py     — Cruzamento de MACD/Signal

Uso rápido:
    from trade_bot.models import BotConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.strategies.ma200_rejection import MA200RejectionStrategy, MA200Config

    strategy = MA200RejectionStrategy()
    config = BotConfig(symbol="WINM25")
    strat_config = MA200Config()
    bot = TradeBotEngine(config, strategy, strat_config)
    bot.run()
"""

from trade_bot.models import Direction, TradeStatus, Trade, BotConfig
from trade_bot.engine import TradeBotEngine

__all__ = [
    "Direction",
    "TradeStatus",
    "Trade",
    "BotConfig",
    "TradeBotEngine",
]
