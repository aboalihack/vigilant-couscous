#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║         OTC SNIPER AI — Telegram Bot for PocketOption           ║
║       نسخة مخصصة للهواتف (Pydroid/Termux) — بدون مكتبة OpenAI     ║
║                  (النسخة الأصلية الكــــامــــلــــة)                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import subprocess
import os

# ══════════════════════════════════════════════════════════════════════════════
#  ⚙️  نظام التثبيت التلقائي للمكتبات (تم حذف openai لتجنب مشاكل الهاتف)
# ══════════════════════════════════════════════════════════════════════════════
def ensure_libraries():
    required = {
        "telegram": "python-telegram-bot>=20",
        "httpx": "httpx",
        "dotenv": "python-dotenv",
        "nest_asyncio": "nest_asyncio"
    }
    print("⏳ جاري فحص المكتبات الأساسية...")
    for module, pkg in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"📦 جاري تثبيت المكتبة الناقصة: {pkg}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
                print(f"✅ تم تثبيت {pkg} بنجاح.")
            except Exception as e:
                print(f"❌ خطأ أثناء تثبيت {pkg}: {e}")
                sys.exit(1)

ensure_libraries()

# تطبيق nest_asyncio لتجنب مشاكل الـ Event Loop في بعض بيئات التشغيل المحمولة
import nest_asyncio
nest_asyncio.apply()

import asyncio
import datetime
import json
import logging
import math
import re
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ══════════════════════════════════════════════════════════════════════════════
#  ⚙️  الإعدادات 
# ══════════════════════════════════════════════════════════════════════════════
ENV_FILE = ".env"

if not os.path.exists(ENV_FILE):
    print("\n⚠️ ملف الإعدادات غير موجود. سيتم إنشاؤه الآن.")
    bot_token_input = input("أدخل توكن البوت (BOT_TOKEN): ").strip()
    openrouter_input = input("أدخل مفتاح OpenRouter (OPENROUTER_KEY): ").strip()
    admin_input = input("أدخل معرف المشرف (ADMIN_IDS) [مثال: 5634813261]: ").strip()
    
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"BOT_TOKEN={bot_token_input}\n")
        f.write(f"OPENROUTER_KEY={openrouter_input}\n")
        f.write(f"ADMIN_IDS={admin_input}\n")
    print("✅ تم إنشاء ملف الإعدادات .env بنجاح!\n")

load_dotenv(ENV_FILE)

BOT_TOKEN      = os.environ.get("BOT_TOKEN",      "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
MODEL          = "qwen/qwen3-vl-32b-instruct"

_raw_admins    = os.environ.get("ADMIN_IDS", "5634813261")
ADMIN_IDS      = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}

if not BOT_TOKEN or not OPENROUTER_KEY:
    raise SystemExit("❌ البيانات في ملف .env غير مكتملة. يرجى حذف الملف وإعادة تشغيل الكود لإدخالها مجدداً.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)


# ─── أزواج OTC ───────────────────────────────────────────────────────────────
OTC_PAIRS = [
    {"id": "eurusd",  "label": "🇪🇺🇺🇸 EUR/USD OTC",  "yahoo": "EURUSD=X"},
    {"id": "gbpusd",  "label": "🇬🇧🇺🇸 GBP/USD OTC",  "yahoo": "GBPUSD=X"},
    {"id": "usdjpy",  "label": "🇺🇸🇯🇵 USD/JPY OTC",  "yahoo": "JPY=X"},
    {"id": "usdcad",  "label": "🇺🇸🇨🇦 USD/CAD OTC",  "yahoo": "CAD=X"},
    {"id": "audusd",  "label": "🇦🇺🇺🇸 AUD/USD OTC",  "yahoo": "AUDUSD=X"},
    {"id": "nzdusd",  "label": "🇳🇿🇺🇸 NZD/USD OTC",  "yahoo": "NZDUSD=X"},
    {"id": "usdchf",  "label": "🇺🇸🇨🇭 USD/CHF OTC",  "yahoo": "CHF=X"},
    {"id": "eurgbp",  "label": "🇪🇺🇬🇧 EUR/GBP OTC",  "yahoo": "EURGBP=X"},
    {"id": "eurjpy",  "label": "🇪🇺🇯🇵 EUR/JPY OTC",  "yahoo": "EURJPY=X"},
    {"id": "gbpjpy",  "label": "🇬🇧🇯🇵 GBP/JPY OTC",  "yahoo": "GBPJPY=X"},
    {"id": "usdzar",  "label": "🇺🇸🇿🇦 USD/ZAR OTC",  "yahoo": "ZAR=X"},
    {"id": "usdmxn",  "label": "🇺🇸🇲🇽 USD/MXN OTC",  "yahoo": "MXN=X"},
    {"id": "usdbrl",  "label": "🇺🇸🇧🇷 USD/BRL OTC",  "yahoo": "BRL=X"},
    {"id": "usdinr",  "label": "🇺🇸🇮🇳 USD/INR OTC",  "yahoo": "INR=X"},
    {"id": "usdtry",  "label": "🇺🇸🇹🇷 USD/TRY OTC",  "yahoo": "TRY=X"},
    {"id": "btcusd",  "label": "₿ BTC/USD OTC",       "yahoo": "BTC-USD"},
    {"id": "ethusd",  "label": "Ξ ETH/USD OTC",       "yahoo": "ETH-USD"},
    {"id": "xrpusd",  "label": "✦ XRP/USD OTC",       "yahoo": "XRP-USD"},
    {"id": "ltcusd",  "label": "◆ LTC/USD OTC",       "yahoo": "LTC-USD"},
    {"id": "bnbusd",  "label": "⬡ BNB/USD OTC",       "yahoo": "BNB-USD"},
    {"id": "eurcad",  "label": "🇪🇺🇨🇦 EUR/CAD OTC",  "yahoo": "EURCAD=X"},
    {"id": "eurchf",  "label": "🇪🇺🇨🇭 EUR/CHF OTC",  "yahoo": "EURCHF=X"},
    {"id": "euraud",  "label": "🇪🇺🇦🇺 EUR/AUD OTC",  "yahoo": "EURAUD=X"},
    {"id": "gbpaud",  "label": "🇬🇧🇦🇺 GBP/AUD OTC",  "yahoo": "GBPAUD=X"},
    {"id": "gbpcad",  "label": "🇬🇧🇨🇦 GBP/CAD OTC",  "yahoo": "GBPCAD=X"},
    {"id": "gbpchf",  "label": "🇬🇧🇨🇭 GBP/CHF OTC",  "yahoo": "GBPCHF=X"},
    {"id": "audcad",  "label": "🇦🇺🇨🇦 AUD/CAD OTC",  "yahoo": "AUDCAD=X"},
    {"id": "audjpy",  "label": "🇦🇺🇯🇵 AUD/JPY OTC",  "yahoo": "AUDJPY=X"},
    {"id": "audnzd",  "label": "🇦🇺🇳🇿 AUD/NZD OTC",  "yahoo": "AUDNZD=X"},
    {"id": "cadjpy",  "label": "🇨🇦🇯🇵 CAD/JPY OTC",  "yahoo": "CADJPY=X"},
    {"id": "chfjpy",  "label": "🇨🇭🇯🇵 CHF/JPY OTC",  "yahoo": "CHFJPY=X"},
]

EXPIRY_OPTIONS = [
    {"key": "5s",  "label": "⚡ 5 ثواني",  "tf1": "1m",  "tf2": "1m",  "tf3": "2m"},
    {"key": "15s", "label": "⚡ 15 ثانية", "tf1": "1m",  "tf2": "2m",  "tf3": "5m"},
    {"key": "30s", "label": "🕐 30 ثانية", "tf1": "1m",  "tf2": "2m",  "tf3": "5m"},
    {"key": "1m",  "label": "🕒 1 دقيقة",  "tf1": "1m",  "tf2": "2m",  "tf3": "5m"},
    {"key": "3m",  "label": "🕓 3 دقائق",  "tf1": "2m",  "tf2": "5m",  "tf3": "15m"},
    {"key": "5m",  "label": "🕔 5 دقائق",  "tf1": "5m",  "tf2": "15m", "tf3": "30m"},
    {"key": "15m", "label": "🕕 15 دقيقة", "tf1": "15m", "tf2": "30m", "tf3": "60m"},
]

STRATEGIES = [
    {"id": "trend_follow",   "name": "📈 تتبع الترند",          "desc": "EMA9/21/50 + MACD",
     "prompt": "استراتيجية تتبع الترند: استخدم EMA9/21/50 و MACD. لا تعطِ إشارات عكس الترند إلا إذا كان هناك تقاطع واضح."},
    {"id": "reversal",       "name": "🔄 انعكاس الترند",         "desc": "RSI ذروة + نمط شموع + BB",
     "prompt": "استراتيجية الانعكاس: ابحث عن RSI < 30 أو > 70 مع نمط شمعة انعكاسي وسعر عند حافة Bollinger."},
    {"id": "scalping",       "name": "⚡ سكالبينج سريع",         "desc": "Stochastic + RSI + 3 شموع",
     "prompt": "استراتيجية السكالبينج: Stochastic < 20 أو > 80 + RSI متطرف + آخر 3 شموع. قرار خلال ثوانٍ."},
    {"id": "breakout",       "name": "💥 كسر المستويات",         "desc": "دعم/مقاومة + BB",
     "prompt": "استراتيجية الاختراق: حدد مستويات الدعم/المقاومة. اعطِ إشارة عند الكسر الواضح مع تأكيد BB."},
    {"id": "momentum",       "name": "🚀 الزخم القوي",           "desc": "MACD + RSI + EMA",
     "prompt": "استراتيجية الزخم: MACD histogram متصاعد + RSI 50-70 للـ CALL أو 30-50 للـ PUT."},
    {"id": "bb_strategy",    "name": "📊 Bollinger الكلاسيكي",   "desc": "BB + RSI حواف النطاق",
     "prompt": "استراتيجية Bollinger: سعر عند الحافة السفلى + RSI < 40 = CALL. حافة العلوية + RSI > 60 = PUT."},
    {"id": "double_confirm", "name": "✅ تأكيد مزدوج",           "desc": "5 مؤشرات يجب أن تتفق",
     "prompt": "استراتيجية التأكيد المزدوج: يجب توافق 5 مؤشرات على الأقل. إذا اختلف أي منها، قل محايد."},
    {"id": "support_resist", "name": "🎯 دعم ومقاومة",           "desc": "S&R الدقيقة + تأكيد شمعة",
     "prompt": "استراتيجية الدعم/المقاومة: الشمعة التي تلمس المستوى وترتد = إشارة قوية."},
    {"id": "candle_pattern", "name": "🕯 الشموع اليابانية",      "desc": "ابتلاع + مطرقة + نجمة المساء",
     "prompt": "استراتيجية الشموع اليابانية: ابحث عن أنماط ابتلاع صاعد/هابط، مطرقة، شهاب، نجمة الصباح/المساء. هذه الأنماط وحدها كافية لقرار CALL أو PUT."},
    {"id": "fibonacci",      "name": "📐 ارتداد فيبوناتشي",      "desc": "مستويات 38.2% و50% و61.8%",
     "prompt": "استراتيجية فيبوناتشي: حدد أعلى وأدنى موجة سابقة. مستويات 38.2% و50% و61.8% هي نقاط ارتداد محتملة. أعطِ إشارة CALL عند تأكيد الارتداد الصاعد، PUT عند الهابط."},
    {"id": "golden_cross",   "name": "🔀 التقاطع الذهبي",        "desc": "تقاطع EMA50 مع EMA200",
     "prompt": "استراتيجية التقاطع الذهبي: EMA50 يكسر EMA200 من الأسفل = CALL قوي جداً. يكسر من الأعلى = PUT قوي. إشارة نادرة ولكنها موثوقة جداً. أضف تأكيد RSI وMACD."},
    {"id": "double_top_bot", "name": "🏔 القمة والقاع المزدوج",  "desc": "نمط M (بيع) أو W (شراء)",
     "prompt": "استراتيجية القمة/القاع المزدوج: نمط M (قمتان متساويتان) = انعكاس هابط PUT. نمط W (قاعان متساويان) = انعكاس صاعد CALL. أعطِ إشارة عند كسر الخط الأوسط مع تأكيد حجم."},
    {"id": "rsi_divergence", "name": "🌊 تباعد RSI الكلاسيكي",   "desc": "RSI عكس السعر = انعكاس وشيك",
     "prompt": "استراتيجية تباعد RSI: السعر يصنع قمة جديدة لكن RSI لا يؤكدها = PUT. السعر يصنع قاعاً جديداً لكن RSI يرتفع = CALL. هذا التباعد الكلاسيكي من أقوى إشارات الانعكاس."},
    {"id": "hidden_momentum","name": "🔮 الزخم الخفي",            "desc": "تباعد خفي = الاتجاه يتجدد",
     "prompt": "استراتيجية الزخم الخفي: إذا كان RSI يصنع قيعاناً أعلى بينما السعر يصنع قيعاناً أدنى = CALL (الاتجاه الصاعد يتجدد). السعر يصنع قمماً أعلى لكن RSI ينخفض = PUT. قوي جداً مع الترند."},
]

OTC_EXPLOITS = [
    {"id": "exhaustion", "name": "🔥 إرهاق الاتجاه",      "desc": "5+ شموع متتالية → انعكاس إحصائي قوي",
     "prompt": "ثغرة الإرهاق: 4+ شموع متتالية بنفس الاتجاه → احتمال الانعكاس > 70%. أعطِ إشارة عكسية عند أول علامة تباطؤ."},
    {"id": "wick",       "name": "⚡ رفض الذيل",           "desc": "ذيل > 70% = رفض قوي، ادخل عكسه",
     "prompt": "ثغرة الذيل: ذيل أي من آخر 3 شموع > 70% من الطول الكلي = رفض قوي. أعطِ إشارة عكس اتجاه الذيل."},
    {"id": "doji",       "name": "🎯 Doji اللحظة الحاسمة", "desc": "Doji = تردد، الشمعة التالية محسومة",
     "prompt": "ثغرة Doji: بعد Doji تأتي شمعة قوية. CALL إذا صاعدة بعد Doji، PUT إذا هابطة."},
    {"id": "bb_exp",     "name": "💥 انفجار Bollinger",    "desc": "BB ضيق → انفجار وشيك",
     "prompt": "ثغرة BB Squeeze: نطاق بولينجر الضيق = ضغط متراكم. أعطِ إشارة في اتجاه آخر شمعة مكتملة."},
    {"id": "mean_rev",   "name": "🧲 المغناطيس EMA50",     "desc": "السعر بعيد عن EMA50 → سيعود",
     "prompt": "ثغرة Mean Reversion: السعر بعيد > 0.5% عن EMA50 = سحب مغناطيسي. أعطِ إشارة باتجاه EMA50."},
    {"id": "inside",     "name": "📦 Inside Bar الانطلاق", "desc": "شمعة داخل السابقة = طاقة مضغوطة",
     "prompt": "ثغرة Inside Bar: الشمعة الأخيرة داخل أعلى/أدنى السابقة = ضغط. CALL إذا الاتجاه صاعد، PUT إذا هابط."},
]

# جداول بحث سريع
PAIR_BY_ID     = {p["id"]: p for p in OTC_PAIRS}
EXPIRY_BY_KEY  = {e["key"]: e for e in EXPIRY_OPTIONS}
STRATEGY_BY_ID = {s["id"]: s for s in STRATEGIES}
EXPLOIT_BY_ID  = {e["id"]: e for e in OTC_EXPLOITS}
PAIRS_PER_PAGE = 10

# ─── قاعدة بيانات الاشتراكات ──────────────────────────────────────────────────
DB_PATH = Path("users.json")

def load_db() -> dict:
    if DB_PATH.exists():
        try:
            return json.loads(DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_db(db: dict) -> None:
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def has_access(uid: int) -> bool:
    if uid in ADMIN_IDS:
        return True
    db = load_db()
    entry = db.get(str(uid))
    if not entry:
        return False
    if entry.get("type") == "lifetime":
        return True
    exp = entry.get("expiresAt", 0)
    return bool(exp and time.time() * 1000 < exp)

def grant_access(uid: int, days: int) -> None:
    db = load_db()
    if days == -1:
        db[str(uid)] = {"type": "lifetime", "grantedAt": int(time.time() * 1000)}
    else:
        db[str(uid)] = {
            "type": "trial",
            "expiresAt": int((time.time() + days * 86400) * 1000),
            "grantedAt": int(time.time() * 1000),
        }
    save_db(db)

def revoke_access(uid: int) -> None:
    db = load_db()
    db.pop(str(uid), None)
    save_db(db)

def no_access_msg(uid: int) -> str:
    return (
        f"🔒 *ليس لديك صلاحية الوصول*\n\n"
        f"معرفك: `{uid}`\n\n"
        f"للاشتراك تواصل مع الأدمن."
    )

# ─── حالة المستخدمين (في الذاكرة) ────────────────────────────────────────────
_states: dict[int, dict] = {}

def get_state(uid: int) -> dict:
    if uid not in _states:
        _states[uid] = {}
    return _states[uid]

# ─── كاش الشموع (60 ثانية) ───────────────────────────────────────────────────
_candle_cache: dict[str, dict] = {}

def _get_cache(key: str) -> Optional[list]:
    h = _candle_cache.get(key)
    return h["data"] if h and time.time() - h["at"] < 60 else None

def _set_cache(key: str, data: list) -> None:
    _candle_cache[key] = {"data": data, "at": time.time()}

# ─── Yahoo Finance ────────────────────────────────────────────────────────────
_RANGE = {"1m": "1d", "2m": "1d", "5m": "5d", "15m": "5d", "30m": "60d", "60m": "60d"}

async def fetch_candles(yahoo: str, interval: str) -> list:
    key = f"{yahoo}|{interval}"
    cached = _get_cache(key)
    if cached is not None:
        return cached

    rng = _RANGE.get(interval, "1d")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}"
        f"?interval={interval}&range={rng}&includePrePost=false"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        })
    resp.raise_for_status()
    j = resp.json()

    result = (j.get("chart") or {}).get("result") or []
    if not result:
        raise ValueError("No Yahoo result")
    r  = result[0]
    ts = r.get("timestamp", [])
    q  = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    opens  = q.get("open",  [])
    highs  = q.get("high",  [])
    lows   = q.get("low",   [])
    closes = q.get("close", [])

    candles = []
    for i in range(len(ts)):
        o = opens[i]  if i < len(opens)  else None
        h = highs[i]  if i < len(highs)  else None
        l = lows[i]   if i < len(lows)   else None
        c = closes[i] if i < len(closes) else None
        if None in (o, h, l, c):
            continue
        candles.append({"ts": ts[i], "O": o, "H": h, "L": l, "C": c})

    _set_cache(key, candles)
    return candles

# ─── المؤشرات الفنية ─────────────────────────────────────────────────────────
def _ema(values: list, period: int) -> list:
    if len(values) < period:
        return []
    k  = 2 / (period + 1)
    v  = sum(values[:period]) / period
    out = [v]
    for x in values[period:]:
        v = x * k + v * (1 - k)
        out.append(v)
    return out

def _rsi(closes: list, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    return round(100.0 if al == 0 else 100 - 100 / (1 + ag / al), 1)

def _macd(closes: list) -> Optional[dict]:
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    if not fast or not slow:
        return None
    n = min(len(fast), len(slow))
    ml = [fast[-n + i] - slow[-n + i] for i in range(n)]
    sig = _ema(ml, 9)
    if not sig:
        return None
    return {
        "macd":   round(ml[-1],  6),
        "signal": round(sig[-1], 6),
        "hist":   round(ml[-1] - sig[-1], 6),
    }

def _stoch(candles: list, kp: int = 14, dp: int = 3) -> Optional[dict]:
    if len(candles) < kp:
        return None
    ks = []
    for i in range(kp - 1, len(candles)):
        win = candles[i - kp + 1 : i + 1]
        hi  = max(c["H"] for c in win)
        lo  = min(c["L"] for c in win)
        cl  = candles[i]["C"]
        ks.append(round((cl - lo) / (hi - lo) * 100 if hi != lo else 50, 1))
    d = round(sum(ks[-dp:]) / dp, 1) if len(ks) >= dp else round(ks[-1], 1)
    return {"K": ks[-1], "D": d}

def _bb(closes: list, period: int = 20, mult: float = 2.0) -> Optional[dict]:
    if len(closes) < period:
        return None
    win = closes[-period:]
    avg = sum(win) / period
    std = math.sqrt(sum((x - avg) ** 2 for x in win) / period)
    upper = avg + mult * std
    lower = avg - mult * std
    price = closes[-1]
    pct = round((price - lower) / (upper - lower) * 100, 1) if upper != lower else 50
    return {"upper": round(upper, 5), "lower": round(lower, 5), "mid": round(avg, 5), "pct": pct}

def _pattern(candles: list) -> str:
    if len(candles) < 3:
        return "غير محدد"
    c, p, pp = candles[-1], candles[-2], candles[-3]
    body  = abs(c["C"] - c["O"])
    total = c["H"] - c["L"]
    if total > 0 and body / total < 0.15:
        return "دوجي (تردد)"
    if c["C"] > c["O"] and p["C"] < p["O"] and c["C"] > p["O"] and c["O"] < p["C"]:
        return "ابتلاع صاعد"
    if c["C"] < c["O"] and p["C"] > p["O"] and c["C"] < p["O"] and c["O"] > p["C"]:
        return "ابتلاع هابط"
    if c["C"] > c["O"] and total > 0 and (c["O"] - c["L"]) / total > 0.6:
        return "مطرقة (انعكاس صاعد)"
    if c["C"] < c["O"] and total > 0 and (c["H"] - c["C"]) / total > 0.6:
        return "شهاب (انعكاس هابط)"
    if c["C"] > c["O"] and p["C"] > p["O"] and pp["C"] > pp["O"]:
        return "3 شموع صاعدة"
    if c["C"] < c["O"] and p["C"] < p["O"] and pp["C"] < pp["O"]:
        return "3 شموع هابطة"
    return "شمعة عادية"

def _sr(candles: list) -> dict:
    if not candles:
        return {"support": 0, "resistance": 0}
    w  = candles[-30:] if len(candles) >= 30 else candles
    hs = sorted(c["H"] for c in w)
    ls = sorted(c["L"] for c in w)
    n  = max(1, len(hs) // 5)
    return {
        "support":    round(sum(ls[:n]) / n, 5),
        "resistance": round(sum(hs[-n:]) / n, 5),
    }

def _trend(closes: list) -> str:
    if len(closes) < 10:
        return "محايد"
    e9  = _ema(closes, 9)
    e21 = _ema(closes, 21)
    if not e9 or not e21:
        return "محايد"
    if e9[-1] > e21[-1] and closes[-1] > e9[-1]:
        return "صاعد قوي 📈"
    if e9[-1] < e21[-1] and closes[-1] < e9[-1]:
        return "هابط قوي 📉"
    if e9[-1] > e21[-1]:
        return "صاعد ↗"
    if e9[-1] < e21[-1]:
        return "هابط ↘"
    return "محايد ➖"

# ─── تقرير كامل ──────────────────────────────────────────────────────────────
async def build_report(yahoo: str, interval: str) -> Optional[dict]:
    try:
        candles = await asyncio.wait_for(fetch_candles(yahoo, interval), timeout=12)
    except Exception as e:
        logger.warning(f"fetch_candles failed ({yahoo} {interval}): {e}")
        return None
    if len(candles) < 20:
        return None
    closes = [c["C"] for c in candles]
    e9  = _ema(closes, 9)
    e21 = _ema(closes, 21)
    e50 = _ema(closes, 50)
    return {
        "tf":      interval,
        "price":   round(closes[-1], 5),
        "pattern": _pattern(candles),
        "trend":   _trend(closes),
        "rsi14":   _rsi(closes, 14),
        "macd":    _macd(closes),
        "stoch":   _stoch(candles),
        "bb":      _bb(closes),
        "sr":      _sr(candles),
        "ema9":    round(e9[-1],  5) if e9  else None,
        "ema21":   round(e21[-1], 5) if e21 else None,
        "ema50":   round(e50[-1], 5) if e50 else None,
    }

def score_report(r: dict) -> dict:
    cs, ps, reasons = 0, 0, []
    rsi = r.get("rsi14")
    if rsi is not None:
        if rsi < 30:   cs += 3; reasons.append("RSI ذروة بيع")
        elif rsi < 45: cs += 1
        elif rsi > 70: ps += 3; reasons.append("RSI ذروة شراء")
        elif rsi > 55: ps += 1
    mc = r.get("macd")
    if mc:
        if mc["hist"] > 0:  cs += 2; reasons.append("MACD صاعد")
        elif mc["hist"] < 0: ps += 2; reasons.append("MACD هابط")
    st = r.get("stoch")
    if st:
        if st["K"] < 20 and st["K"] > st["D"]:  cs += 2; reasons.append("Stoch ذروة بيع")
        elif st["K"] > 80 and st["K"] < st["D"]: ps += 2; reasons.append("Stoch ذروة شراء")
    bb = r.get("bb")
    if bb:
        if bb["pct"] < 10:  cs += 2; reasons.append("BB حافة سفلى")
        elif bb["pct"] > 90: ps += 2; reasons.append("BB حافة علوية")
    tr = r.get("trend", "")
    if "صاعد قوي" in tr:  cs += 3; reasons.append("ترند صاعد قوي")
    elif "صاعد" in tr:    cs += 1
    elif "هابط قوي" in tr: ps += 3; reasons.append("ترند هابط قوي")
    elif "هابط" in tr:    ps += 1
    pat = r.get("pattern", "")
    if any(x in pat for x in ("صاعد", "مطرقة")): cs += 2; reasons.append(f"نمط: {pat}")
    elif any(x in pat for x in ("هابط", "شهاب")): ps += 2; reasons.append(f"نمط: {pat}")
    e9 = r.get("ema9"); e21 = r.get("ema21"); price = r.get("price", 0)
    if e9 and e21:
        if e9 > e21 and price > e9:   cs += 1
        elif e9 < e21 and price < e9: ps += 1
    return {"callScore": cs, "putScore": ps, "reasons": list(dict.fromkeys(reasons))}

def report_to_text(r: dict) -> str:
    lines = [f"TF: {r['tf']} | السعر: {r['price']} | نمط: {r['pattern']} | اتجاه: {r['trend']}"]
    if r.get("rsi14") is not None: lines.append(f"RSI14: {r['rsi14']}")
    mc = r.get("macd")
    if mc: lines.append(f"MACD: {mc['macd']} | Signal: {mc['signal']} | Hist: {mc['hist']}")
    st = r.get("stoch")
    if st: lines.append(f"Stoch K/D: {st['K']}/{st['D']}")
    bb = r.get("bb")
    if bb: lines.append(f"BB %B: {bb['pct']}% | Upper: {bb['upper']} | Lower: {bb['lower']}")
    sr = r.get("sr")
    if sr: lines.append(f"دعم: {sr['support']} | مقاومة: {sr['resistance']}")
    for k, l in (("ema9", "EMA9"), ("ema21", "EMA21"), ("ema50", "EMA50")):
        if r.get(k): lines.append(f"{l}: {r[k]}")
    return "\n".join(lines)

# ─── الذكاء الاصطناعي (معدل للعمل بدون مكتبة openai وبصورة مباشرة) ───────────
async def call_ai(messages: list, attempt: int = 0) -> Optional[str]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1200
    }
    
    try:
        # وقت أطول للاستجابة لأن معالجة الصور قد تأخذ وقتاً
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI error: {e}")
        if attempt < 5:
            await asyncio.sleep(2 ** attempt)
            return await call_ai(messages, attempt + 1)
        return None

# ─── دوال التحليل ────────────────────────────────────────────────────────────
def _parse_verdict(verdict: Optional[str], default_dir: str, default_conf: int = 70) -> tuple:
    ai_dir, ai_conf, ai_reason = default_dir, default_conf, ""
    if verdict:
        vm = re.search(r"VERDICT:\s*(CALL|PUT)", verdict, re.I)
        cm = re.search(r"CONFIDENCE:\s*(\d+)",   verdict)
        rm = re.search(r"REASON:\s*(.+)",         verdict)
        if vm: ai_dir    = vm.group(1).upper()
        if cm: ai_conf   = int(cm.group(1))
        if rm: ai_reason = rm.group(1).strip()[:120]
    return ai_dir, ai_conf, ai_reason

def _build_msg(pair_label, expiry_label, reports, scores, ai_dir, ai_conf, ai_reason,
               mode_name: Optional[str] = None, strat_fit: str = "") -> str:
    de  = "📈" if ai_dir == "CALL" else "📉"
    bar = "█" * round(ai_conf / 20) + "░" * (5 - round(ai_conf / 20))
    lvl = "🔥 عالية" if ai_conf >= 80 else "✅ جيدة" if ai_conf >= 65 else "⚠️ متوسطة"
    p   = reports[0]
    msg  = "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 *{pair_label}* | ⏱ {expiry_label}\n"
    if mode_name: msg += f"{'🧠' if mode_name[0] not in '🔓' else '🔓'} *{mode_name}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 *القرار: {ai_dir} {de}*\n"
    msg += f"📊 *الثقة: {ai_conf}%* {bar} {lvl}\n"
    if strat_fit: msg += f"🏆 *الملاءمة: {strat_fit}*\n"
    msg += f"💰 *السعر: {p['price']}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    for r, s in zip(reports, scores):
        d = "CALL 📈" if s["callScore"] > s["putScore"] else "PUT 📉" if s["putScore"] > s["callScore"] else "محايد ➖"
        msg += f"  [{r['tf'].upper()}] {d} | {r['trend']}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    rsi = p.get("rsi14")
    if rsi is not None:
        msg += f"  RSI: *{rsi}* {'🔥 ذروة بيع' if rsi < 30 else '🔥 ذروة شراء' if rsi > 70 else ''}\n"
    st = p.get("stoch")
    if st: msg += f"  Stoch: *{st['K']}/{st['D']}* {'🔥' if st['K'] < 20 or st['K'] > 80 else ''}\n"
    bb = p.get("bb")
    if bb:
        bn = "← حافة سفلى" if bb["pct"] < 15 else "← حافة علوية" if bb["pct"] > 85 else ""
        msg += f"  BB %B: *{bb['pct']}%* {bn}\n"
    msg += f"  نمط: *{p['pattern']}*\n"
    msg += f"  اتجاه: *{p['trend']}*\n"
    sr = p.get("sr")
    if sr: msg += f"  دعم: {sr['support']} | مقاومة: {sr['resistance']}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    reasons = list(dict.fromkeys(r for s in scores for r in s["reasons"]))[:4]
    if reasons: msg += "📌 *الإشارات:* " + " | ".join(reasons) + "\n"
    if ai_reason: msg += f"🔑 *{ai_reason}*\n"
    msg += f"⏱ *ادخل الآن — {ai_dir} {de}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━"
    return msg

async def analyze_all_tf(pair_label: str, yahoo: str, expiry_key: str, expiry_label: str) -> str:
    exp = EXPIRY_BY_KEY.get(expiry_key, EXPIRY_BY_KEY["5m"])
    raws = await asyncio.gather(
        build_report(yahoo, exp["tf1"]),
        build_report(yahoo, exp["tf2"]),
        build_report(yahoo, exp["tf3"]),
        return_exceptions=True,
    )
    reports = [r for r in raws if isinstance(r, dict)]
    if not reports:
        return f"⚠️ *تعذر جلب بيانات {pair_label}*\n\nتحقق من الاتصال وأعد المحاولة."
    scores = [score_report(r) for r in reports]
    ct = sum(s["callScore"] for s in scores)
    pt = sum(s["putScore"]  for s in scores)
    verdict = await call_ai([
        {"role": "system", "content": "محلل خيارات ثنائية OTC. قرار حاسم CALL أو PUT.\nأجب:\nVERDICT: CALL|PUT\nCONFIDENCE: X%\nREASON: [جملة]"},
        {"role": "user",   "content": "\n\n".join(report_to_text(r) for r in reports) + f"\nCALL={ct} | PUT={pt}"},
    ])
    dd = "CALL" if ct >= pt else "PUT"
    d, c, reason = _parse_verdict(verdict, dd)
    return _build_msg(pair_label, expiry_label, reports, scores, d, c, reason)

async def analyze_with_strategy(pair_label: str, yahoo: str, expiry_key: str, expiry_label: str, sid: str) -> str:
    strat = STRATEGY_BY_ID.get(sid)
    if not strat:
        return await analyze_all_tf(pair_label, yahoo, expiry_key, expiry_label)
    exp = EXPIRY_BY_KEY.get(expiry_key, EXPIRY_BY_KEY["5m"])
    raws = await asyncio.gather(
        build_report(yahoo, exp["tf1"]),
        build_report(yahoo, exp["tf2"]),
        build_report(yahoo, exp["tf3"]),
        return_exceptions=True,
    )
    reports = [r for r in raws if isinstance(r, dict)]
    if not reports:
        return f"⚠️ *تعذر جلب بيانات {pair_label}*"
    scores = [score_report(r) for r in reports]
    ct = sum(s["callScore"] for s in scores)
    pt = sum(s["putScore"]  for s in scores)
    verdict = await call_ai([
        {"role": "system", "content": f"خبير خيارات ثنائية OTC.\nالاستراتيجية: {strat['name']}\n{strat['prompt']}\n\nأجب:\nVERDICT: CALL|PUT\nCONFIDENCE: X%\nSTRATEGY_FIT: [الملاءمة]\nREASON: [جملة]"},
        {"role": "user",   "content": "\n\n".join(report_to_text(r) for r in reports) + f"\nCALL={ct} | PUT={pt}"},
    ])
    dd = "CALL" if ct >= pt else "PUT"
    d, c, reason = _parse_verdict(verdict, dd)
    fit = ""
    if verdict:
        fm = re.search(r"STRATEGY_FIT:\s*(.+)", verdict)
        if fm: fit = fm.group(1).strip()[:60]
    return _build_msg(pair_label, expiry_label, reports, scores, d, c, reason, strat["name"], fit)

async def analyze_with_exploit(pair_label: str, yahoo: str, expiry_key: str, expiry_label: str, eid: str) -> str:
    exploit = EXPLOIT_BY_ID.get(eid)
    if not exploit:
        return await analyze_all_tf(pair_label, yahoo, expiry_key, expiry_label)
    exp = EXPIRY_BY_KEY.get(expiry_key, EXPIRY_BY_KEY["5m"])
    r = await build_report(yahoo, exp["tf1"])
    if not r:
        return f"⚠️ *تعذر جلب بيانات {pair_label}*"
    s = score_report(r)
    verdict = await call_ai([
        {"role": "system", "content": f"خبير ثغرات OTC.\nالثغرة: {exploit['name']}\n{exploit['prompt']}\n\nأجب:\nVERDICT: CALL|PUT\nCONFIDENCE: X%\nREASON: [جملة]"},
        {"role": "user",   "content": f"{pair_label} | {expiry_label}\n{report_to_text(r)}\nCALL={s['callScore']} | PUT={s['putScore']}"},
    ])
    dd = "CALL" if s["callScore"] >= s["putScore"] else "PUT"
    d, c, reason = _parse_verdict(verdict, dd, 73)

    de  = "📈" if d == "CALL" else "📉"
    bar = "█" * round(c / 20) + "░" * (5 - round(c / 20))
    lvl = "🔥 عالية" if c >= 80 else "✅ جيدة" if c >= 65 else "⚠️ متوسطة"

    msg  = "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 *{pair_label}* | ⏱ {expiry_label}\n"
    msg += f"🔓 *{exploit['name']}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 *القرار: {d} {de}*\n"
    msg += f"📊 *الثقة: {c}%* {bar} {lvl}\n"
    msg += f"💰 *السعر: {r['price']}*\n"
    sr = r.get("sr")
    if sr: msg += f"📐 دعم: {sr['support']} | مقاومة: {sr['resistance']}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    rsi = r.get("rsi14")
    if rsi is not None:
        msg += f"  RSI: *{rsi}* {'🔥 ذروة بيع' if rsi < 30 else '🔥 ذروة شراء' if rsi > 70 else ''}\n"
    st = r.get("stoch")
    if st: msg += f"  Stoch: *{st['K']}/{st['D']}* {'🔥' if st['K'] < 20 or st['K'] > 80 else ''}\n"
    bb = r.get("bb")
    if bb:
        bn = "← حافة سفلى" if bb["pct"] < 15 else "← حافة علوية" if bb["pct"] > 85 else ""
        msg += f"  BB %B: *{bb['pct']}%* {bn}\n"
    msg += f"  نمط: *{r['pattern']}*\n"
    msg += f"  اتجاه: *{r['trend']}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔓 *الثغرة: {reason or exploit['desc']}*\n"
    msg += f"⏱ *ادخل الآن — {d} {de}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━"
    return msg

async def analyze_image(file_url: str, pair: str, expiry_label: str) -> str:
    prompt = (
        f"أنت خبير تداول بالخيارات الثنائية OTC على PocketOption.\n"
        f"الزوج: {pair} | المدة: {expiry_label}\n\n"
        f"حلل هذا الشارت بدقة:\n"
        f"1. اتجاه الترند\n2. المؤشرات الظاهرة\n3. نمط الشموع\n4. الدعم والمقاومة\n\n"
        f"أجب:\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *{pair}* | ⏱ {expiry_label}\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *القرار: CALL 📈 / PUT 📉*\n📊 *الثقة: X%*\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *التحليل:*\n• الاتجاه: ...\n• المؤشرات: ...\n• الشموع: ...\n• الدعم/المقاومة: ...\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n🔑 *العامل الحاسم:* ...\n⏱ *ادخل الآن — CALL/PUT*\n━━━━━━━━━━━━━━━━━━━━━"
    )
    result = await call_ai([{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": file_url}},
            {"type": "text",      "text": prompt},
        ],
    }])
    return result or "⚠️ تعذر تحليل الصورة. أرسل صورة أوضح."

# ─── لوحات المفاتيح ───────────────────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحليل مباشر بالشموع الحقيقية", callback_data="mode_live")],
        [InlineKeyboardButton("📸 تحليل بصورة الشارت",          callback_data="mode_image")],
        [InlineKeyboardButton("🧠 استراتيجيات احترافية",          callback_data="mode_strategies")],
        [InlineKeyboardButton("🔓 ثغرات OTC الإحصائية",          callback_data="mode_exploits")],
    ])

def _grid_kb(items, cb_prefix, back="main_menu") -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i]["name"], callback_data=f"{cb_prefix}{items[i]['id']}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i+1]["name"], callback_data=f"{cb_prefix}{items[i+1]['id']}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data=back)])
    return InlineKeyboardMarkup(rows)

def strategies_kb() -> InlineKeyboardMarkup:
    return _grid_kb(STRATEGIES, "strat_")

def exploits_kb() -> InlineKeyboardMarkup:
    return _grid_kb(OTC_EXPLOITS, "expl_")

def pairs_kb(page: int = 0) -> InlineKeyboardMarkup:
    start = page * PAIRS_PER_PAGE
    slc   = OTC_PAIRS[start : start + PAIRS_PER_PAGE]
    rows  = []
    for i in range(0, len(slc), 2):
        row = [InlineKeyboardButton(slc[i]["label"], callback_data=f"pair_{slc[i]['id']}")]
        if i + 1 < len(slc):
            row.append(InlineKeyboardButton(slc[i+1]["label"], callback_data=f"pair_{slc[i+1]['id']}"))
        rows.append(row)
    total = math.ceil(len(OTC_PAIRS) / PAIRS_PER_PAGE)
    nav   = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"pp_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if start + PAIRS_PER_PAGE < len(OTC_PAIRS):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"pp_{page+1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def expiry_kb(pair_id: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(EXPIRY_OPTIONS), 2):
        row = [InlineKeyboardButton(EXPIRY_OPTIONS[i]["label"], callback_data=f"exp_{pair_id}_{EXPIRY_OPTIONS[i]['key']}")]
        if i + 1 < len(EXPIRY_OPTIONS):
            row.append(InlineKeyboardButton(EXPIRY_OPTIONS[i+1]["label"], callback_data=f"exp_{pair_id}_{EXPIRY_OPTIONS[i+1]['key']}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def after_kb(pair_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 إعادة التحليل", callback_data=f"re_{pair_id}"),
         InlineKeyboardButton("📊 زوج آخر",       callback_data="pp_0")],
        [InlineKeyboardButton("🧠 الاستراتيجيات", callback_data="mode_strategies"),
         InlineKeyboardButton("🔓 الثغرات",        callback_data="mode_exploits")],
        [InlineKeyboardButton("🏠 الرئيسية",       callback_data="main_menu")],
    ])

# ─── الرسالة الرئيسية ─────────────────────────────────────────────────────────
HOME_TEXT = (
    "🤖 *OTC SNIPER AI — PocketOption*\n\n"
    "📊 تحليل مباشر بشموع حقيقية (EMA/RSI/MACD/BB)\n"
    "🧠 8 استراتيجيات احترافية مخصصة OTC\n"
    "🔓 6 ثغرات إحصائية في أزواج OTC\n"
    "📸 تحليل أي صورة شارت\n\n"
    "اختر نوع التحليل:"
)

# ─── معالجات الأوامر ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not has_access(uid):
        await ctx.bot.send_message(cid, no_access_msg(uid), parse_mode=ParseMode.MARKDOWN)
        return
    await ctx.bot.send_message(cid, HOME_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    db = load_db()
    msg = (
        f"🔧 *لوحة الأدمن*\n\nالمشتركون: *{len(db)}*\n\n"
        "الأوامر:\n"
        "`/grant <uid> <أيام>` — منح وصول\n"
        "`/grant <uid> -1` — وصول مدى الحياة\n"
        "`/revoke <uid>` — إلغاء الوصول\n"
        "`/users` — قائمة المشتركين"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_grant(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = ctx.args or []
    if len(args) < 2:
        await update.message.reply_text("الاستخدام: /grant <uid> <أيام>"); return
    try:
        uid  = int(args[0])
        days = int(args[1])
        grant_access(uid, days)
        label = "مدى الحياة ♾" if days == -1 else f"{days} يوم"
        await update.message.reply_text(f"✅ تم منح `{uid}` وصولاً — {label}", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ بيانات غير صحيحة.")

async def cmd_revoke(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("الاستخدام: /revoke <uid>"); return
    try:
        uid = int(args[0])
        revoke_access(uid)
        await update.message.reply_text(f"✅ تم إلغاء وصول `{uid}`", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ بيانات غير صحيحة.")

async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    db = load_db()
    if not db:
        await update.message.reply_text("لا يوجد مشتركون بعد."); return
    lines = ["*قائمة المشتركين:*\n"]
    for uid, info in db.items():
        if info.get("type") == "lifetime":
            lines.append(f"• `{uid}` — مدى الحياة ♾")
        else:
            exp_ms = info.get("expiresAt", 0)
            active = "✅" if time.time() * 1000 < exp_ms else "❌"
            exp_str = datetime.datetime.fromtimestamp(exp_ms / 1000).strftime("%Y-%m-%d")
            lines.append(f"• `{uid}` — {active} حتى {exp_str}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ─── معالج الأزرار ────────────────────────────────────────────────────────────
async def btn_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    uid   = query.from_user.id
    cid   = query.message.chat_id
    mid   = query.message.message_id
    data  = query.data or ""

    if not has_access(uid):
        await query.message.reply_text(no_access_msg(uid), parse_mode=ParseMode.MARKDOWN)
        return

    state = get_state(uid)

    async def edit(text: str, kb=None):
        try:
            await ctx.bot.edit_message_text(
                text, cid, mid, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                logger.warning(f"edit_message_text: {e}")

    if data == "noop":
        return

    if data == "main_menu":
        state.clear()
        await edit(HOME_TEXT, main_menu_kb())
        return

    if data == "mode_live":
        state.clear()
        await edit("📊 *اختر زوج OTC:*", pairs_kb(0))
        return

    if data == "mode_image":
        state.clear()
        state["awaitingImagePair"] = True
        await edit(
            "📸 *تحليل بصورة الشارت*\n\nأولاً: اختر الزوج:",
            pairs_kb(0)
        )
        return

    if data == "mode_strategies":
        state["pendingStrategy"] = None
        desc = "\n".join(f"• *{s['name']}* — {s['desc']}" for s in STRATEGIES)
        await edit(f"🧠 *الاستراتيجيات الاحترافية*\n\nاختر:\n\n{desc}", strategies_kb())
        return

    if data == "mode_exploits":
        state["pendingExploit"]  = None
        state["pendingStrategy"] = None
        desc = "\n".join(f"• *{e['name']}* — {e['desc']}" for e in OTC_EXPLOITS)
        await edit(f"🔓 *ثغرات OTC الإحصائية*\n\nأنماط إحصائية متكررة:\n\n{desc}", exploits_kb())
        return

    if data.startswith("strat_"):
        sid   = data[6:]
        strat = STRATEGY_BY_ID.get(sid)
        if not strat: return
        state["pendingStrategy"]  = sid
        state["pendingExploit"]   = None
        state["awaitingImage"]    = False
        await edit(f"🧠 *{strat['name']}*\n\n📌 {strat['desc']}\n\n📊 *اختر زوج OTC:*", pairs_kb(0))
        return

    if data.startswith("expl_"):
        eid     = data[5:]
        exploit = EXPLOIT_BY_ID.get(eid)
        if not exploit: return
        state["pendingExploit"]  = eid
        state["pendingStrategy"] = None
        state["awaitingImage"]   = False
        await edit(f"🔓 *{exploit['name']}*\n\n📌 {exploit['desc']}\n\n📊 *اختر الزوج:*", pairs_kb(0))
        return

    if data.startswith("pp_"):
        page = int(data[3:]) if data[3:].isdigit() else 0
        await edit("📊 *اختر زوج OTC:*", pairs_kb(page))
        return

    if data.startswith("pair_"):
        pid  = data[5:]
        pair = PAIR_BY_ID.get(pid)
        if not pair: return
        state["pendingPairId"]    = pid
        state["pendingPairLabel"] = pair["label"]
        state["pendingPairYahoo"] = pair["yahoo"]
        await edit(f"✅ *{pair['label']}*\n\n⏱ *اختر مدة الصفقة:*", expiry_kb(pid))
        return

    if data.startswith("exp_"):
        parts = data.split("_")
        ekey  = parts[-1]
        pid   = "_".join(parts[1:-1])
        pair  = PAIR_BY_ID.get(pid)
        exp   = EXPIRY_BY_KEY.get(ekey)
        if not pair or not exp: return

        state["pendingPairId"]    = pid
        state["pendingPairLabel"] = pair["label"]
        state["pendingPairYahoo"] = pair["yahoo"]
        state["pendingExpiry"]    = ekey

        exploit_id  = state.get("pendingExploit")
        strategy_id = state.get("pendingStrategy")
        is_image    = state.get("awaitingImage") or state.get("awaitingImagePair")

        if is_image:
            state["awaitingImage"]    = True
            state["awaitingImagePair"] = False
            state["imageExpiry"]      = ekey
            await edit(
                f"📸 *{pair['label']}* | {exp['label']}\n\n"
                f"أرسل الآن صورة الشارت وسأحللها فوراً:",
            )
            return

        mode_name = (
            EXPLOIT_BY_ID.get(exploit_id, {}).get("name")  if exploit_id  else
            STRATEGY_BY_ID.get(strategy_id, {}).get("name") if strategy_id else None
        )
        loading = (
            f"⏳ *جارٍ تطبيق {mode_name}...*\n\n📊 {pair['label']} | ⏱ {exp['label']}"
            if mode_name else
            f"⏳ *جارٍ جلب بيانات {pair['label']}...*\n\n📊 EMA+RSI+MACD+Stoch+BB | 3 إطارات\n⏱ {exp['label']}"
        )
        await edit(loading)

        try:
            result = await asyncio.wait_for(
                (analyze_with_exploit(pair["label"], pair["yahoo"], ekey, exp["label"], exploit_id)  if exploit_id  else
                 analyze_with_strategy(pair["label"], pair["yahoo"], ekey, exp["label"], strategy_id) if strategy_id else
                 analyze_all_tf(pair["label"], pair["yahoo"], ekey, exp["label"])),
                timeout=120,
            )
            await edit(result, after_kb(pid))
        except asyncio.TimeoutError:
            await edit("❌ *انتهى الوقت.* أعد المحاولة.", after_kb(pid))
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await edit("❌ *حدث خطأ.* أعد المحاولة.", after_kb(pid))
        return

    if data.startswith("re_"):
        pid         = data[3:]
        actual_pid  = state.get("pendingPairId", pid)
        pair        = PAIR_BY_ID.get(actual_pid)
        ekey        = state.get("pendingExpiry", "5m")
        exp         = EXPIRY_BY_KEY.get(ekey, EXPIRY_BY_KEY["5m"])
        exploit_id  = state.get("pendingExploit")
        strategy_id = state.get("pendingStrategy")
        if not pair:
            await edit("📊 *اختر زوجاً:*", pairs_kb(0))
            return
        await edit(f"🔄 *إعادة التحليل — {pair['label']}...*\n⏳ يجلب أحدث البيانات...")
        try:
            result = await asyncio.wait_for(
                (analyze_with_exploit(pair["label"], pair["yahoo"], ekey, exp["label"], exploit_id)  if exploit_id  else
                 analyze_with_strategy(pair["label"], pair["yahoo"], ekey, exp["label"], strategy_id) if strategy_id else
                 analyze_all_tf(pair["label"], pair["yahoo"], ekey, exp["label"])),
                timeout=120,
            )
            await edit(result, after_kb(actual_pid))
        except asyncio.TimeoutError:
            await edit("❌ *انتهى الوقت.* أعد المحاولة.", after_kb(actual_pid))
        except Exception as e:
            logger.error(f"Re-analysis error: {e}")
            await edit("❌ *حدث خطأ.* أعد المحاولة.", after_kb(actual_pid))

# ─── معالج الصور ─────────────────────────────────────────────────────────────
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not has_access(uid):
        await ctx.bot.send_message(cid, no_access_msg(uid), parse_mode=ParseMode.MARKDOWN)
        return

    state = get_state(uid)
    if not state.get("awaitingImage"):
        return  # تجاهل الصور غير المطلوبة

    if update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
    else:
        return

    pair_label   = state.get("pendingPairLabel", "غير محدد")
    ekey         = state.get("imageExpiry", state.get("pendingExpiry", "5m"))
    expiry_label = EXPIRY_BY_KEY.get(ekey, EXPIRY_BY_KEY["5m"])["label"]

    msg = await ctx.bot.send_message(cid, f"⏳ *جارٍ تحليل صورة {pair_label}...*", parse_mode=ParseMode.MARKDOWN)

    try:
        file     = await ctx.bot.get_file(file_id)
        file_url = file.file_path
        result   = await asyncio.wait_for(analyze_image(file_url, pair_label, expiry_label), timeout=60)
        await ctx.bot.edit_message_text(
            result, cid, msg.message_id,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 صورة أخرى",   callback_data="mode_image"),
                 InlineKeyboardButton("📊 تحليل مباشر", callback_data="mode_live")],
                [InlineKeyboardButton("🏠 الرئيسية",    callback_data="main_menu")],
            ]),
        )
    except asyncio.TimeoutError:
        await ctx.bot.edit_message_text(
            "❌ *انتهى الوقت.* أرسل صورة أخرى.", cid, msg.message_id,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Image handler error: {e}")
        await ctx.bot.edit_message_text(
            "❌ *حدث خطأ.* أرسل صورة أوضح.", cid, msg.message_id,
            parse_mode=ParseMode.MARKDOWN
        )

# ─── التشغيل الدائم وإعداد الخادم الوهمي ─────────────────────────────────────
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is awake and running 24/7!")

def run_dummy_server():
    # استخدام المتغير PORT إذا كان موجوداً في الاستضافة، وإلا يتم استخدام المنفذ 8080
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    logger.info(f"🌐 بدء تشغيل الخادم الوهمي على المنفذ {port} للحفاظ على البوت نشطاً...")
    server.serve_forever()

def keep_alive():
    t = threading.Thread(target=run_dummy_server)
    t.daemon = True
    t.start()

def main() -> None:
    # تشغيل الخادم الوهمي قبل تشغيل البوت
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_start))
    app.add_handler(CommandHandler("admin",  cmd_admin))
    app.add_handler(CommandHandler("grant",  cmd_grant))
    app.add_handler(CommandHandler("revoke", cmd_revoke))
    app.add_handler(CommandHandler("users",  cmd_users))
    app.add_handler(CallbackQueryHandler(btn_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_handler))

    logger.info("🤖 OTC SNIPER AI — بدء التشغيل (polling)...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
