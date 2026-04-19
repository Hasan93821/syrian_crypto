import ccxt.pro as ccxt
import pandas as pd
import ta
import logging
import asyncio
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)
exchange = ccxt.kucoin({'enableRateLimit': True})

_cached_pairs = []
_pairs_cache_time = 0

POPULAR_PAIRS_PRIORITY = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "SOL/USDT",
    "ADA/USDT", "DOGE/USDT", "TRX/USDT", "DOT/USDT", "MATIC/USDT",
    "LTC/USDT", "AVAX/USDT", "LINK/USDT", "UNI/USDT", "ATOM/USDT",
    "ETC/USDT", "XLM/USDT", "FIL/USDT", "NEAR/USDT", "APT/USDT",
    "OP/USDT", "ARB/USDT", "SUI/USDT", "INJ/USDT", "PEPE/USDT",
    "SHIB/USDT", "FTM/USDT", "SAND/USDT", "MANA/USDT", "CRV/USDT",
    "AAVE/USDT", "MKR/USDT", "COMP/USDT", "SNX/USDT", "GRT/USDT",
    "1INCH/USDT", "ENJ/USDT", "CHZ/USDT", "HOT/USDT", "VET/USDT",
    "ALGO/USDT", "ICP/USDT", "EOS/USDT", "XTZ/USDT", "EGLD/USDT",
    "HBAR/USDT", "ZEC/USDT", "DASH/USDT", "NEO/USDT", "IOTA/USDT",
]

FALLBACK_POPULAR_PAIRS = POPULAR_PAIRS_PRIORITY


async def get_all_usdt_pairs():
    """
    يجلب أزواج USDT من Binance مع تخزين مؤقت لمدة ساعة.
    يرجع قائمة احتياطية من الأزواج الشائعة عند الفشل.
    """
    global _cached_pairs, _pairs_cache_time

    import time
    now = time.time()

    if _cached_pairs and (now - _pairs_cache_time) < 3600:
        logger.info(f"Using cached pairs ({len(_cached_pairs)} pairs).")
        return _cached_pairs

    try:
        logger.info("Fetching USDT pairs from KuCoin...")
        markets = await asyncio.wait_for(exchange.load_markets(), timeout=15)
        all_usdt = set(symbol for symbol in markets if symbol.endswith('/USDT'))
        if all_usdt:
            popular_first = [p for p in POPULAR_PAIRS_PRIORITY if p in all_usdt]
            rest = sorted(all_usdt - set(popular_first))
            usdt_pairs = popular_first + rest
            _cached_pairs = usdt_pairs
            _pairs_cache_time = now
            logger.info(f"Successfully fetched {len(usdt_pairs)} USDT pairs from KuCoin (popular first).")
            return usdt_pairs
        else:
            logger.warning("Empty pairs list from KuCoin, using fallback.")
            return FALLBACK_POPULAR_PAIRS
    except Exception as e:
        logger.error(f"Failed to fetch pairs from KuCoin: {e}. Using fallback list.")
        if _cached_pairs:
            return _cached_pairs
        return FALLBACK_POPULAR_PAIRS


async def get_crypto_data(symbol='BTC/USDT', timeframe='1h', limit=200):
    """
    يجلب بيانات OHLCV لرمز معين.
    يُرجع DataFrame فارغاً في حالة الخطأ.
    """
    try:
        logger.info(f"Fetching OHLCV data for {symbol} - {timeframe}.")
        ohlcv = await asyncio.wait_for(
            exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit),
            timeout=20
        )
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        logger.info(f"Successfully fetched {len(df)} candles for {symbol}.")
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()


def generate_trading_signal(df):
    """
    يولد إشارة تداول (شراء/بيع) بناءً على مؤشرات فنية.
    """
    if df is None or df.empty or len(df) < 21:
        logger.warning("Insufficient data to generate signal.")
        return None

    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd_diff()

    df['ema21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()

    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()

    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch'] = stoch.stoch()

    last = df.iloc[-1]

    score_buy = 0
    score_sell = 0

    if last['rsi'] < 30: score_buy += 1
    if last['macd'] > 0: score_buy += 1
    if last['close'] > last['ema21']: score_buy += 1
    if last['close'] < last['bb_low']: score_buy += 1
    if last['stoch'] < 20: score_buy += 1

    if last['rsi'] > 70: score_sell += 1
    if last['macd'] < 0: score_sell += 1
    if last['close'] < last['ema21']: score_sell += 1
    if last['close'] > last['bb_high']: score_sell += 1
    if last['stoch'] > 80: score_sell += 1

    if score_buy >= 2:
        logger.info(f"Generated BUY signal. Scores: Buy={score_buy}, Sell={score_sell}")
        return {
            'action': 'شراء ✅',
            'entry': last['close'],
            'target': round(last['close'] * 1.02, 4),
            'stop_loss': round(last['close'] * 0.98, 4)
        }
    elif score_sell >= 2:
        logger.info(f"Generated SELL signal. Scores: Buy={score_buy}, Sell={score_sell}")
        return {
            'action': 'بيع 🚨',
            'entry': last['close'],
            'target': round(last['close'] * 0.98, 4),
            'stop_loss': round(last['close'] * 1.02, 4)
        }
    logger.info(f"No strong signal. Scores: Buy={score_buy}, Sell={score_sell}")
    return None


def format_signal(signal, symbol):
    """
    يقوم بتنسيق إشارة التداول في رسالة MarkdownV2.
    """
    if not signal:
        return escape_markdown("❌ لا توجد توصية حاليًا.", version=2)

    escaped_symbol = escape_markdown(symbol, version=2)
    escaped_action = escape_markdown(signal['action'], version=2)
    escaped_entry = escape_markdown(f"{signal['entry']:.4f}", version=2)
    escaped_target = escape_markdown(f"{signal['target']:.4f}", version=2)
    escaped_stop = escape_markdown(f"{signal['stop_loss']:.4f}", version=2)

    return (
        f"📈 توصية تداول \\({escaped_symbol}\\)\n"
        f"العملية: \\*{escaped_action}\\*\n"
        f"نقطة الدخول: `{escaped_entry}` USDT\n"
        f"الهدف: 🎯 `{escaped_target}` USDT\n"
        f"وقف الخسارة: 🛑 `{escaped_stop}` USDT"
    )
