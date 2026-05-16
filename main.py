# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════╗
# ║       IncomeApp — Telegram Bot (main.py)             ║
# ║   Firestore  ·  Optimized Reads  ·  Cache Layer      ║
# ╚══════════════════════════════════════════════════════╝

import logging
import os
import json
import asyncio
import time
import random
import string
from datetime import datetime, date
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import firebase_admin
from firebase_admin import credentials, firestore, db as rtdb

# ═══════════════════════════════════════════════════════
#   KEEP-ALIVE  (Replit / Render)
# ═══════════════════════════════════════════════════════
flask_app = Flask('')

@flask_app.route('/')
def home():
    cache_count = len(_user_cache)
    return f"IncomeApp Bot ✅ Running | Cache: {cache_count} users"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ═══════════════════════════════════════════════════════
#   CONFIGURATION
#   Render Secret Files-এ এই key গুলো যোগ করুন:
#     BOT_TOKEN      → BotFather-এর token
#     ADMIN_ID       → আপনার Telegram numeric ID
#     FIREBASE_KEYS  → Service Account JSON-এর পুরো কন্টেন্ট
# ═══════════════════════════════════════════════════════
API_TOKEN    = os.getenv('BOT_TOKEN', '')
ADMIN_ID     = int(os.getenv('ADMIN_ID', '0'))

storage = MemoryStorage()
bot     = Bot(token=API_TOKEN, parse_mode="HTML")
dp      = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log     = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#   FIREBASE INITIALIZATION
#
#   Render → Environment Variables-এ দুটো variable যোগ করুন:
#
#   FIREBASE_KEYS     → Service Account JSON-এর পুরো কন্টেন্ট
#                       (Firebase Console → Project Settings →
#                        Service Accounts → Generate New Private Key)
#
#   FIREBASE_DB_URL   → Realtime Database URL
#                       (Firebase Console → Project Settings →
#                        General → Your apps → databaseURL)
#                       উদাহরণ:
#                       https://your-project-default-rtdb.asia-southeast1.firebasedatabase.app
#
#   ভবিষ্যতে database পরিবর্তন হলে শুধু Render থেকে
#   FIREBASE_DB_URL আপডেট করুন — কোড ছুঁতে হবে না।
# ═══════════════════════════════════════════════════════
_firebase_keys_raw = os.getenv('FIREBASE_KEYS', '')
_firebase_ok       = False
db                 = None  # Firestore client

# Render → Environment Variables → FIREBASE_DB_URL
RTDB_URL = os.environ.get('FIREBASE_DB_URL', '')

if _firebase_keys_raw:
    try:
        _cred_dict = json.loads(_firebase_keys_raw)
        _cred      = credentials.Certificate(_cred_dict)
        if RTDB_URL:
            firebase_admin.initialize_app(_cred, {'databaseURL': RTDB_URL})
            log.info("✅ Firestore + Realtime Database initialized")
        else:
            firebase_admin.initialize_app(_cred)
            log.warning("⚠️ FIREBASE_DB_URL নেই — Realtime Database stats কাজ করবে না")
        db = firestore.client()
        _firebase_ok = True
    except json.JSONDecodeError as _e:
        log.error(f"❌ FIREBASE_KEYS JSON parse error: {_e}")
    except Exception as _e:
        log.error(f"❌ Firebase init error: {_e}")
else:
    log.error("❌ FIREBASE_KEYS পাওয়া যায়নি!")

# ═══════════════════════════════════════════════════════
#   FIRESTORE HELPERS
# ═══════════════════════════════════════════════════════
def fs_get_user(uid: str) -> dict | None:
    """Firestore থেকে একটি ইউজার আনো।"""
    try:
        doc = db.collection("users").document(uid).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        log.error(f"fs_get_user error [{uid}]: {e}")
        return None

def fs_set_user(uid: str, data: dict):
    """Firestore-এ নতুন ইউজার সেট করো।"""
    try:
        db.collection("users").document(uid).set(data)
    except Exception as e:
        log.error(f"fs_set_user error [{uid}]: {e}")

def fs_update_user(uid: str, fields: dict):
    """Firestore-এ ইউজার আপডেট করো।"""
    try:
        db.collection("users").document(uid).update(fields)
    except Exception as e:
        log.error(f"fs_update_user error [{uid}]: {e}")

def fs_get(collection: str, doc_id: str) -> dict | None:
    """যেকোনো collection থেকে একটি document আনো।"""
    try:
        doc = db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        log.error(f"fs_get error [{collection}/{doc_id}]: {e}")
        return None

def fs_set(collection: str, doc_id: str, data: dict):
    """যেকোনো collection-এ document সেট করো।"""
    try:
        db.collection(collection).document(doc_id).set(data)
    except Exception as e:
        log.error(f"fs_set error [{collection}/{doc_id}]: {e}")

def fs_update(collection: str, doc_id: str, fields: dict):
    """যেকোনো collection-এ document আপডেট করো।"""
    try:
        db.collection(collection).document(doc_id).update(fields)
    except Exception as e:
        log.error(f"fs_update error [{collection}/{doc_id}]: {e}")

def fs_delete(collection: str, doc_id: str):
    """যেকোনো collection থেকে document মুছো।"""
    try:
        db.collection(collection).document(doc_id).delete()
    except Exception as e:
        log.error(f"fs_delete error [{collection}/{doc_id}]: {e}")

def fs_add(collection: str, data: dict) -> str | None:
    """collection-এ auto-ID দিয়ে document যোগ করো।"""
    try:
        _, ref = db.collection(collection).add(data)
        return ref.id
    except Exception as e:
        log.error(f"fs_add error [{collection}]: {e}")
        return None

def fs_txn_add(uid: str, balance_delta: float = 0, points_delta: int = 0) -> bool:
    """
    Race Condition-safe balance ও points আপডেট।
    Firestore transaction ব্যবহার করে।
    """
    if balance_delta == 0 and points_delta == 0:
        return True
    try:
        user_ref = db.collection("users").document(uid)

        @firestore.transactional
        def _update_in_txn(transaction, user_ref):
            snapshot = user_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            data = snapshot.to_dict()
            updates = {}
            if balance_delta != 0:
                new_bal = round(max(0, data.get("balance", 0) + balance_delta), 2)
                updates["balance"] = new_bal
            if points_delta != 0:
                new_pts = max(0, data.get("points", 0) + points_delta)
                updates["points"] = new_pts
            transaction.update(user_ref, updates)
            return True

        transaction = db.transaction()
        result = _update_in_txn(transaction, user_ref)
        cache_invalidate_user(uid)
        log.debug(f"txn_add uid={uid} bal={balance_delta:+} pts={points_delta:+}")
        return result
    except Exception as e:
        log.error(f"fs_txn_add error uid={uid}: {e}")
        return False

def increment_refer_stat(referrer_uid: str):
    """
    রেফার হলে referStats collection-এ +১ করে।
    টপ রেফারার দেখাতে পুরো users স্ক্যান লাগবে না।
    """
    try:
        ref = db.collection("referStats").document(referrer_uid)
        ref.set({"count": firestore.Increment(1)}, merge=True)
    except Exception as e:
        log.error(f"increment_refer_stat error: {e}")

# ═══════════════════════════════════════════════════════
#   REALTIME DATABASE — STATS HELPERS
#   stats/main  নোডে সব counter রাখা হয়।
#   ১টা read-এ পুরো dashboard পাওয়া যায়।
#   লক্ষ ইউজারেও Firebase free tier handle করতে পারে।
#
#   Render-এ নতুন env variable যোগ করুন:
#     RTDB_URL = https://YOUR-PROJECT-default-rtdb.REGION.firebasedatabase.app
# ═══════════════════════════════════════════════════════

def _rtdb_ref(path: str):
    """RTDB reference বানাও। RTDB_URL না থাকলে None।"""
    if not RTDB_URL:
        return None
    try:
        return rtdb.reference(path)
    except Exception as e:
        log.error(f"_rtdb_ref error [{path}]: {e}")
        return None

def rtdb_increment(path: str, delta):
    """Realtime Database-এ atomic increment।"""
    try:
        ref = _rtdb_ref(path)
        if ref is None:
            return
        ref.transaction(lambda current: (current or 0) + delta)
    except Exception as e:
        log.error(f"rtdb_increment error [{path}]: {e}")

def rtdb_stats_new_verification(fee: float):
    """
    ভেরিফিকেশন অ্যাপ্রুভ হলে কল করো।
    → total_verifications +1
    → total_income += fee
    → daily_income[আজকের তারিখ] += fee
    """
    try:
        if not RTDB_URL:
            return
        today_key = datetime.now().strftime("%Y-%m-%d")
        rtdb_increment("stats/main/total_verifications", 1)
        rtdb_increment("stats/main/total_income", fee)
        rtdb_increment(f"stats/daily_income/{today_key}", fee)
    except Exception as e:
        log.error(f"rtdb_stats_new_verification error: {e}")

def rtdb_stats_new_withdrawal(amount: float, uid: str, name: str):
    """
    উইথড্র paid হলে কল করো।
    → total_withdrawals +1
    → total_withdrawal_amount += amount
    → top100_withdrawers আপডেট
    """
    try:
        if not RTDB_URL:
            return
        rtdb_increment("stats/main/total_withdrawals", 1)
        rtdb_increment("stats/main/total_withdrawal_amount", amount)
        # top withdrawer entry আপডেট
        w_ref = _rtdb_ref(f"stats/top_withdrawers/{uid}")
        if w_ref:
            def _update_w(current):
                c = current or {"name": name, "total": 0}
                c["total"] = round((c.get("total") or 0) + amount, 2)
                c["name"]  = name
                return c
            w_ref.transaction(_update_w)
    except Exception as e:
        log.error(f"rtdb_stats_new_withdrawal error: {e}")

def rtdb_stats_update_refer(uid: str, name: str, earn: float):
    """
    রেফার বোনাস দেওয়া হলে কল করো।
    → total_refer_paid += earn
    → top_referrers[uid] count +1
    """
    try:
        if not RTDB_URL:
            return
        rtdb_increment("stats/main/total_refer_paid", earn)
        r_ref = _rtdb_ref(f"stats/top_referrers/{uid}")
        if r_ref:
            def _update_r(current):
                c = current or {"name": name, "count": 0}
                c["count"] = (c.get("count") or 0) + 1
                c["name"]  = name
                return c
            r_ref.transaction(_update_r)
    except Exception as e:
        log.error(f"rtdb_stats_update_refer error: {e}")

def rtdb_get_dashboard() -> dict:
    """
    Dashboard-এর জন্য RTDB থেকে সব stats একসাথে আনো।
    মাত্র ১টা read — লক্ষ ইউজারেও ফ্রি।
    """
    try:
        if not RTDB_URL:
            return {}
        ref = _rtdb_ref("stats/main")
        if ref is None:
            return {}
        data = ref.get()
        return data or {}
    except Exception as e:
        log.error(f"rtdb_get_dashboard error: {e}")
        return {}

def rtdb_get_top_referrers(limit: int = 100) -> list:
    """
    RTDB থেকে টপ রেফারারদের তালিকা আনো (max limit জন)।
    """
    try:
        if not RTDB_URL:
            return []
        ref = _rtdb_ref("stats/top_referrers")
        if ref is None:
            return []
        data = ref.order_by_child("count").limit_to_last(limit).get()
        if not data:
            return []
        items = [{"uid": k, **v} for k, v in data.items()]
        items.sort(key=lambda x: x.get("count", 0), reverse=True)
        return items
    except Exception as e:
        log.error(f"rtdb_get_top_referrers error: {e}")
        return []

def rtdb_get_top_withdrawers(limit: int = 100) -> list:
    """
    RTDB থেকে টপ উইথড্রকারীদের তালিকা আনো (max limit জন)।
    """
    try:
        if not RTDB_URL:
            return []
        ref = _rtdb_ref("stats/top_withdrawers")
        if ref is None:
            return []
        data = ref.order_by_child("total").limit_to_last(limit).get()
        if not data:
            return []
        items = [{"uid": k, **v} for k, v in data.items()]
        items.sort(key=lambda x: x.get("total", 0), reverse=True)
        return items
    except Exception as e:
        log.error(f"rtdb_get_top_withdrawers error: {e}")
        return []

# ═══════════════════════════════════════════════════════
#   LOCAL CACHE  (RAM — TTL 120 সেকেন্ড)
# ═══════════════════════════════════════════════════════
MAX_CACHE_SIZE = 5000
USER_CACHE_TTL = 120
_user_cache: dict = {}

def cache_get_user(uid: str):
    entry = _user_cache.get(uid)
    if entry is None:
        return None
    if (time.time() - entry["ts"]) > USER_CACHE_TTL:
        del _user_cache[uid]
        return None
    return entry["data"]

def cache_set_user(uid: str, data: dict):
    if not data:
        return
    if len(_user_cache) >= MAX_CACHE_SIZE:
        remove_count = MAX_CACHE_SIZE // 10
        # ✅ সবচেয়ে পুরনো entries আগে বের করো (timestamp অনুযায়ী)
        oldest_keys = sorted(_user_cache, key=lambda k: _user_cache[k]["ts"])[:remove_count]
        for key in oldest_keys:
            del _user_cache[key]
        log.debug(f"Cache evicted {remove_count} oldest entries")
    _user_cache[uid] = {"data": dict(data), "ts": time.time()}

def cache_invalidate_user(uid: str):
    _user_cache.pop(uid, None)
    log.debug(f"Cache invalidated: {uid}")

def get_user(uid: str) -> dict | None:
    """
    RAM চেক → TTL ১২০ সেকেন্ড।
    Cache miss হলে Firestore থেকে আনে।
    """
    cached = cache_get_user(uid)
    if cached is not None:
        return cached
    log.debug(f"Cache MISS: {uid} → Firestore read")
    data = fs_get_user(uid)
    if data:
        cache_set_user(uid, data)
    return data

def update_user(uid: str, fields: dict):
    """Firestore আপডেট + cache invalidate।"""
    fs_update_user(uid, fields)
    cache_invalidate_user(uid)

def put_user(uid: str, data: dict):
    """Firestore-এ নতুন ইউজার + cache set।"""
    fs_set_user(uid, data)
    cache_set_user(uid, data)

# ═══════════════════════════════════════════════════════
#   SETTINGS CACHE
#   ✅ Realtime Database থেকে পড়ে — Admin Panel সাথে সাথে sync।
#   TTL 60 সেকেন্ড — প্রতি মিনিটে একবার fresh হয়।
#   Admin Panel settings save করলে সর্বোচ্চ ৬০ সেকেন্ডে bot পাবে।
# ═══════════════════════════════════════════════════════
SETTINGS_TTL = 60
_settings_cache: dict = {"data": None, "ts": 0.0}

def get_settings() -> dict:
    now = time.time()
    if _settings_cache["data"] and (now - _settings_cache["ts"]) < SETTINGS_TTL:
        return _settings_cache["data"]

    # ✅ Realtime Database থেকে পড়ো — Admin Panel এখানেই লেখে
    s = {}
    if RTDB_URL:
        try:
            s = rtdb.reference("settings").get() or {}
        except Exception as e:
            log.error(f"get_settings RTDB error: {e}")
            # fallback: Firestore থেকে পড়ো
            s = fs_get("config", "settings") or {}
    else:
        # RTDB না থাকলে Firestore fallback
        s = fs_get("config", "settings") or {}

    result = {
        "bkash":      s.get("bkash",      "01XXXXXXXXX"),
        "nagad":      s.get("nagad",      "01XXXXXXXXX"),
        "fee":        s.get("fee",        50),
        "notice":     s.get("notice",     ""),
        "popup":      s.get("popup",      ""),
        "appOn":      s.get("appOn",      True),
        "regOn":      s.get("regOn",      True),
        "lvl2Start":  s.get("lvl2Start",  1000),
        "lvl3Start":  s.get("lvl3Start",  2000),
        "earn1":      s.get("earn1",      20),
        "earn2":      s.get("earn2",      25),
        "earn3":      s.get("earn3",      30),
        "dailyBonus": s.get("dailyBonus", 10),
    }
    _settings_cache["data"] = result
    _settings_cache["ts"]   = now
    return result

def invalidate_settings_cache():
    _settings_cache["data"] = None
    _settings_cache["ts"]   = 0.0

# ═══════════════════════════════════════════════════════
#   LEVEL & EARN LOGIC
# ═══════════════════════════════════════════════════════
def get_level(points: int, s: dict) -> int:
    if points >= s["lvl3Start"]: return 3
    if points >= s["lvl2Start"]: return 2
    return 1

def get_earn(level: int, s: dict) -> int:
    return s.get(f"earn{level}", 20)

def get_min_withdraw(level: int) -> int:
    return 100 if level >= 2 else 150

# ═══════════════════════════════════════════════════════
#   UNIQUE REFER CODE
# ═══════════════════════════════════════════════════════
def generate_refer_code(name: str) -> str:
    prefix = (name[:3] if len(name) >= 3 else name).upper()
    suffix = ''.join(random.choices(string.digits, k=4))
    return prefix + suffix

def is_refer_code_unique(code: str) -> bool:
    """Firestore indexed query — পুরো users স্ক্যান করে না।"""
    try:
        docs = db.collection("users").where("referCode", "==", code).limit(1).get()
        return len(docs) == 0
    except Exception as e:
        log.error(f"is_refer_code_unique error: {e}")
        return True

def make_unique_refer_code(name: str) -> str:
    for _ in range(20):
        code = generate_refer_code(name)
        if is_refer_code_unique(code):
            return code
    return name[:2].upper() + str(int(time.time()))[-6:]

# ═══════════════════════════════════════════════════════
#   BENGALI NUMBER CONVERTER
# ═══════════════════════════════════════════════════════
def bn(n) -> str:
    """সংখ্যাকে বাংলা অঙ্কে রূপান্তর। দশমিক থাকলে দুই ঘর দেখাবে।"""
    try:
        f = float(n)
        # দশমিক অংশ অর্থপূর্ণ হলে দেখাও, না হলে integer
        if f != int(f):
            s = f"{f:.2f}"
        else:
            s = str(int(f))
        d = {'0':'০','1':'১','2':'২','3':'৩','4':'৪',
             '5':'৫','6':'৬','7':'৭','8':'৮','9':'৯','.':'.','-':'-'}
        return ''.join(d.get(c, c) for c in s)
    except:
        return "০"

# ═══════════════════════════════════════════════════════
#   FSM STATES
# ═══════════════════════════════════════════════════════
class Reg(StatesGroup):
    phone    = State()
    ref_code = State()

class Pay(StatesGroup):
    choose_method = State()
    sender_phone  = State()
    txn_id        = State()

class Withdraw(StatesGroup):
    choose_method = State()
    number        = State()
    amount        = State()

class Report(StatesGroup):
    message = State()

class AdminState(StatesGroup):
    broadcast     = State()
    edit_uid      = State()
    edit_field    = State()
    edit_value    = State()

# ═══════════════════════════════════════════════════════
#   KEYBOARDS
# ═══════════════════════════════════════════════════════
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🏠 হোম"),
        KeyboardButton("📊 আমার প্রোফাইল"),
        KeyboardButton("💸 টাকা উত্তোলন"),
        KeyboardButton("👥 রেফার করুন"),
        KeyboardButton("☀️ ডেইলি বোনাস"),
        KeyboardButton("📋 পেমেন্ট হিস্ট্রি"),
        KeyboardButton("ℹ️ নিয়মাবলী"),
        KeyboardButton("🚨 রিপোর্ট করুন"),
    )
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("📊 ড্যাশবোর্ড"),
        KeyboardButton("⏳ পেন্ডিং ভেরিফিকেশন"),
        KeyboardButton("💸 পেন্ডিং উইথড্রয়াল"),
        KeyboardButton("📋 উইথড্র হিস্ট্রি"),
        KeyboardButton("👥 একটিভ ইউজার লিস্ট"),
        KeyboardButton("🏆 টপ রেফারার"),
        KeyboardButton("🏧 টপ উইথড্রয়ার"),
        KeyboardButton("📢 ব্রডকাস্ট করুন"),
        KeyboardButton("⚙️ সেটিংস দেখুন"),
        KeyboardButton("🏠 মেইন মেনু"),
    )
    return kb

def method_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📱 বিকাশ", callback_data="method_bkash"),
        InlineKeyboardButton("💚 নগদ",  callback_data="method_nagad"),
    )
    return kb

def approve_reject_kb(uid: str, kind: str = "ver"):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ অ্যাপ্রুভ",  callback_data=f"approve_{kind}_{uid}"),
        InlineKeyboardButton("❌ রিজেক্ট",    callback_data=f"reject_{kind}_{uid}"),
    )
    return kb

def paid_reject_kb(wid: str):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Mark as Paid",  callback_data=f"paid_{wid}"),
        InlineKeyboardButton("❌ রিজেক্ট",       callback_data=f"wreject_{wid}"),
    )
    return kb

# ═══════════════════════════════════════════════════════
#   MIDDLEWARE — app on/off check
# ═══════════════════════════════════════════════════════
async def app_check(uid: str, message: types.Message) -> bool:
    s = get_settings()
    if not s["appOn"]:
        await message.answer("🔧 অ্যাপটি সাময়িকভাবে মেইনটেন্যান্সে আছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
        return False
    return True

# ═══════════════════════════════════════════════════════
#   /start
# ═══════════════════════════════════════════════════════
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    uid  = str(message.from_user.id)
    s    = get_settings()

    if not s["appOn"]:
        await message.answer("🔧 অ্যাপটি সাময়িক মেইনটেন্যান্সে। পরে আসুন।")
        return

    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👑 <b>অ্যাডমিন প্যানেলে স্বাগতম!</b>\n\nনিচের মেনু থেকে যেকোনো অপশন বেছে নিন।",
            reply_markup=admin_kb()
        )
        return

    # ── cache থেকে আনো — Firestore read বাঁচাতে ──
    user = get_user(uid)

    if not user:
        if not s["regOn"]:
            await message.answer("❌ নতুন নিবন্ধন সাময়িকভাবে বন্ধ আছে।")
            return
        args = message.get_args()
        ref_by = args if args else None
        if ref_by:
            try:
                docs = db.collection("users").where("referCode", "==", ref_by).limit(1).get()
                if not docs:
                    ref_by = None
            except Exception:
                ref_by = None

        await state.update_data(referred_by=ref_by, name=message.from_user.full_name)
        await Reg.phone.set()
        welcome = (
            f"🎉 <b>IncomeApp-এ স্বাগতম!</b>\n\n"
            f"রেফার করুন, প্রতিদিন আয় করুন।\n"
            f"{'✅ রেফার কোড পাওয়া গেছে!' if ref_by else ''}\n\n"
            f"📱 আপনার <b>ফোন নম্বর</b> দিন (১১ সংখ্যা):"
        )
        await message.answer(welcome, reply_markup=ReplyKeyboardRemove())
        return

    st = user.get("status", "pending")

    if st == "banned":
        await message.answer("🚫 আপনার অ্যাকাউন্ট বন্ধ করা হয়েছে। সাপোর্টে যোগাযোগ করুন।")
        return
    if st in ("pending", "new"):
        await _show_payment_screen(message, uid, user, s)
        return
    if st == "review":
        await message.answer(
            "⏳ <b>আপনার পেমেন্ট রিভিউতে আছে।</b>\n\n"
            "অ্যাডমিন চেক করছেন, ২-৩ ঘণ্টার মধ্যে একটিভ হবে।\n\n"
            "📞 দ্রুত যোগাযোগ: /support"
        )
        return
    if st == "rejected":
        await message.answer(
            "❌ <b>আপনার পেমেন্ট রিজেক্ট হয়েছে।</b>\n\n"
            "পুনরায় পেমেন্ট করতে /pay কমান্ড দিন।"
        )
        return

    await _show_home(message, uid, user, s)


async def _show_payment_screen(message, uid, user, s):
    text = (
        f"💳 <b>একাউন্ট একটিভেশন</b>\n\n"
        f"নিচের যেকোনো নম্বরে <b>৳{s['fee']}</b> পাঠান:\n\n"
        f"📱 <b>বিকাশ:</b> <code>{s['bkash']}</code>\n"
        f"💚 <b>নগদ:</b>  <code>{s['nagad']}</code>\n\n"
        f"পাঠানোর পর নিচের বাটনে ক্লিক করুন।"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="start_pay"))
    await message.answer(text, reply_markup=kb)


async def _show_home(message, uid, user, s):
    pts  = user.get("points", 0)
    bal  = user.get("balance", 0)
    lvl  = get_level(pts, s)
    earn = get_earn(lvl, s)
    notice_line = f"\n\n📢 <b>নোটিশ:</b> {s['notice']}" if s.get('notice') else ""

    text = (
        f"🏠 <b>হোম</b>{notice_line}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👋 স্বাগতম, <b>{user.get('name','বন্ধু')}</b>!\n\n"
        f"💰 ব্যালেন্স:  <b>৳{bal}</b>\n"
        f"🎯 পয়েন্ট:   <b>{pts}</b>\n"
        f"🏅 লেভেল:    <b>লেভেল {lvl}</b>\n"
        f"💵 রেফার আয়: <b>৳{earn} প্রতি রেফার</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"নিচের মেনু থেকে যেকোনো অপশন বেছে নিন।"
    )
    await message.answer(text, reply_markup=main_kb())

# ═══════════════════════════════════════════════════════
#   REGISTRATION FLOW
# ═══════════════════════════════════════════════════════
@dp.message_handler(state=Reg.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()

    if not phone.isdigit():
        await message.answer("❌ ফোন নম্বরে শুধু সংখ্যা থাকবে।\nউদাহরণ: <code>01712345678</code>")
        return
    if len(phone) != 11:
        await message.answer(f"❌ ফোন নম্বর ঠিক ১১ সংখ্যার হতে হবে।\nআপনি দিয়েছেন {len(phone)} সংখ্যা।")
        return
    if not phone.startswith("01"):
        await message.answer("❌ বাংলাদেশের নম্বর <b>01</b> দিয়ে শুরু হওয়া উচিত।")
        return
    valid_prefixes = ("011","013","014","015","016","017","018","019")
    if not any(phone.startswith(p) for p in valid_prefixes):
        await message.answer("❌ সঠিক অপারেটর কোড দিন (011-019)।")
        return

    # Duplicate চেক — Firestore indexed query
    try:
        docs = db.collection("users").where("phone", "==", phone).limit(1).get()
        if docs:
            existing = docs[0].to_dict()
            st = existing.get("status", "pending")
            if st == "active":
                await message.answer("❌ এই ফোন নম্বরে আগেই একটি একটিভ অ্যাকাউন্ট আছে।")
            elif st in ("pending", "review", "new"):
                await message.answer("⚠️ এই ফোন নম্বরে একটি অ্যাকাউন্ট ভেরিফিকেশনের অপেক্ষায় আছে।")
            else:
                await message.answer("❌ এই ফোন নম্বর দিয়ে অ্যাকাউন্ট তৈরি করা যাবে না।")
            return
    except Exception:
        pass

    await state.update_data(phone=phone)
    await Reg.ref_code.set()
    await message.answer("🎟 বন্ধুর <b>রেফার কোড</b> থাকলে লিখুন, না থাকলে <b>skip</b> লিখুন:")

@dp.message_handler(state=Reg.ref_code)
async def reg_ref_code(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    data = await state.get_data()
    code = message.text.strip().upper()
    s    = get_settings()

    referred_by_uid = None
    if code != "SKIP" and code:
        try:
            docs = db.collection("users").where("referCode", "==", code).limit(1).get()
            if docs:
                referred_by_uid = docs[0].id
            else:
                await message.answer("⚠️ রেফার কোড পাওয়া যায়নি। Skip করুন বা সঠিক কোড দিন:")
                return
        except Exception:
            pass

    if data.get("referred_by") and not referred_by_uid:
        try:
            docs = db.collection("users").where("referCode", "==", data["referred_by"]).limit(1).get()
            if docs:
                referred_by_uid = docs[0].id
        except Exception:
            pass

    refer_code = make_unique_refer_code(data["name"])

    user_data = {
        "name":        data["name"],
        "phone":       data["phone"],
        "referCode":   refer_code,
        "referredBy":  referred_by_uid,
        "status":      "new",
        "balance":     0,
        "points":      0,
        "createdAt":   int(time.time() * 1000),
        "deviceId":    f"tg_{uid}",
    }
    put_user(uid, user_data)
    await state.finish()
    await _show_payment_screen(message, uid, user_data, s)

# ═══════════════════════════════════════════════════════
#   PAYMENT FLOW
# ═══════════════════════════════════════════════════════
@dp.callback_query_handler(lambda c: c.data == "start_pay", state="*")
async def cb_start_pay(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    uid  = str(call.from_user.id)
    user = get_user(uid)
    if not user:
        await call.answer("প্রথমে /start দিন।", show_alert=True)
        return
    s = get_settings()
    await Pay.choose_method.set()
    await call.message.answer(
        f"💳 পেমেন্ট মেথড বেছে নিন:\n\n"
        f"📱 বিকাশ নম্বর: <code>{s['bkash']}</code>\n"
        f"💚 নগদ নম্বর:  <code>{s['nagad']}</code>",
        reply_markup=method_kb()
    )
    await call.answer()

@dp.message_handler(commands=['pay'], state="*")
async def cmd_pay(message: types.Message, state: FSMContext):
    await state.finish()
    uid  = str(message.from_user.id)
    user = get_user(uid)
    if not user:
        await message.answer("প্রথমে /start দিন।")
        return
    s = get_settings()
    await Pay.choose_method.set()
    await message.answer(
        f"💳 পেমেন্ট মেথড বেছে নিন:\n\n"
        f"📱 বিকাশ: <code>{s['bkash']}</code>\n"
        f"💚 নগদ:  <code>{s['nagad']}</code>",
        reply_markup=method_kb()
    )

@dp.callback_query_handler(lambda c: c.data.startswith("method_"), state=Pay.choose_method)
async def pay_method(call: types.CallbackQuery, state: FSMContext):
    method = call.data.split("_")[1]
    await state.update_data(method=method)
    await Pay.sender_phone.set()
    await call.message.answer(
        f"✅ মেথড: <b>{'বিকাশ' if method=='bkash' else 'নগদ'}</b>\n\n"
        f"📱 যে নম্বর থেকে টাকা পাঠিয়েছেন সেই <b>ফোন নম্বর</b> দিন (১১ সংখ্যা):"
    )
    await call.answer()

@dp.message_handler(state=Pay.sender_phone)
async def pay_sender_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("01"):
        await message.answer("❌ সঠিক ১১ সংখ্যার নম্বর দিন। উদাহরণ: <code>01712345678</code>")
        return
    valid_prefixes = ("011", "013", "014", "015", "016", "017", "018", "019")
    if not any(phone.startswith(p) for p in valid_prefixes):
        await message.answer("❌ সঠিক অপারেটর কোড দিন (011-019)।")
        return
    await state.update_data(sender_phone=phone)
    data   = await state.get_data()
    method = data.get("method", "bkash")
    await Pay.txn_id.set()
    await message.answer(
        f"✅ নম্বর সেভ হয়েছে: <code>{phone}</code>\n\n"
        f"🆔 এখন আপনার <b>ট্রান্জেকশন আইডি (TxnID)</b> দিন:\n\n"
        f"{'📱 বিকাশ TxnID: ঠিক ১০ অক্ষর।' if method=='bkash' else '💚 নগদ TxnID: ঠিক ৮ অক্ষর।'}\n"
        f"{'উদাহরণ: <code>DDO8HH4U5K</code>' if method=='bkash' else 'উদাহরণ: <code>AB12CD34</code>'}\n"
        f"(ছোট হাতে লিখলেও স্বয়ংক্রিয়ভাবে বড় হাতে হয়ে যাবে)"
    )

def _validate_txn(txn: str, method: str) -> tuple[bool, str]:
    """
    বিকাশ: ঠিক ১০ অক্ষর, শুধু বড় হাতের অক্ষর (A-Z) ও সংখ্যা (0-9)।
            উদাহরণ: DDO8HH4U5K
    নগদ:   ঠিক ৮ অক্ষর, একই ফরম্যাট।
    """
    expected = 10 if method == "bkash" else 8
    txn_up   = txn.strip().upper()

    if not txn_up:
        return False, (
            f"❌ ট্রান্জেকশন আইডি খালি রাখা যাবে না।\n"
            f"{'বিকাশ' if method=='bkash' else 'নগদ'} TxnID ঠিক {expected} অক্ষরের হয়।\n"
            f"উদাহরণ: {'DDO8HH4U5K' if method=='bkash' else 'AB12CD34'}"
        )

    if len(txn_up) != expected:
        return False, (
            f"❌ {'বিকাশ' if method=='bkash' else 'নগদ'} TxnID ঠিক <b>{expected} অক্ষরের</b> হয়।\n"
            f"আপনি দিয়েছেন: {len(txn_up)} অক্ষর।\n"
            f"উদাহরণ: {'DDO8HH4U5K' if method=='bkash' else 'AB12CD34'}"
        )

    # শুধু A-Z এবং 0-9 অনুমোদিত
    if not all(c.isupper() or c.isdigit() for c in txn_up):
        return False, (
            f"❌ TxnID-তে শুধু বড় হাতের অক্ষর (A-Z) ও সংখ্যা (0-9) থাকবে।\n"
            f"বিশেষ চিহ্ন বা ছোট হাতের অক্ষর গ্রহণযোগ্য নয়।\n"
            f"উদাহরণ: {'DDO8HH4U5K' if method=='bkash' else 'AB12CD34'}"
        )

    has_letter = any(c.isalpha() for c in txn_up)
    has_digit  = any(c.isdigit() for c in txn_up)
    if not has_letter or not has_digit:
        return False, (
            f"❌ TxnID-তে অন্তত একটি অক্ষর ও একটি সংখ্যা থাকতে হবে।\n"
            f"উদাহরণ: {'DDO8HH4U5K' if method=='bkash' else 'AB12CD34'}"
        )

    return True, ""

@dp.message_handler(state=Pay.txn_id)
async def pay_txn_id(message: types.Message, state: FSMContext):
    uid    = str(message.from_user.id)
    data   = await state.get_data()
    txn    = message.text.strip()
    method = data.get("method", "bkash")
    sender_phone = data.get("sender_phone", "?")

    valid, err_msg = _validate_txn(txn, method)
    if not valid:
        await message.answer(err_msg)
        return

    # Duplicate TxnID চেক — Firestore indexed query
    txn_upper = txn.upper()
    try:
        docs = db.collection("verifications").where("transactionId", "==", txn_upper).limit(1).get()
        if docs:
            await message.answer(
                "❌ এই ট্রান্জেকশন আইডিটি আগেই ব্যবহার করা হয়েছে।\n"
                "সঠিক TxnID দিন বা সাপোর্টে যোগাযোগ করুন: /support"
            )
            return
    except Exception:
        pass

    user = get_user(uid) or {}
    s    = get_settings()

    ver_data = {
        "uid":           uid,
        "name":          user.get("name", "?"),
        "phone":         user.get("phone", "?"),
        "senderPhone":   sender_phone,
        "method":        method,
        "transactionId": txn_upper,
        "status":        "pending",
        "submittedAt":   int(time.time() * 1000),
    }
    vid = fs_add("verifications", ver_data)
    update_user(uid, {"status": "review"})

    admin_text = (
        f"🔔 <b>নতুন ভেরিফিকেশন রিকোয়েস্ট</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 নাম:  {user.get('name','?')}\n"
        f"📞 রেজিস্ট্রেশন ফোন: {user.get('phone','?')}\n"
        f"📱 পেমেন্ট নম্বর: <code>{sender_phone}</code>\n"
        f"💳 মেথড: {method.upper()}\n"
        f"🆔 TxnID: <code>{txn_upper}</code>\n"
        f"🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"UID: <code>{uid}</code>  |  VID: <code>{vid}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=approve_reject_kb(f"{uid}|{vid}", "ver"))
    except Exception as e:
        log.warning(f"Admin notify error: {e}")

    await state.finish()
    await message.answer(
        "⏳ <b>পর্যালোচনা চলছে</b>\n\n"
        "আপনার পেমেন্ট আইডিটি অ্যাডমিন চেক করছেন।\n"
        "২-৩ ঘণ্টার মধ্যে একাউন্ট একটিভ হবে।\n\n"
        "স্ট্যাটাস জানতে /status দিন।"
    )

# ═══════════════════════════════════════════════════════
#   ADMIN — APPROVE / REJECT VERIFICATION
# ═══════════════════════════════════════════════════════
@dp.callback_query_handler(lambda c: c.data.startswith("approve_ver_"))
async def cb_approve_ver(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("শুধু অ্যাডমিন এই কাজ করতে পারবেন!", show_alert=True)
        return

    await call.answer("⏳ প্রসেস হচ্ছে...")

    parts = call.data.replace("approve_ver_", "").split("|")
    uid   = parts[0]
    vid   = parts[1] if len(parts) > 1 else None
    s     = get_settings()

    # approve করার আগে পুরনো status দেখো
    existing_user   = get_user(uid) or {}
    was_ever_active = existing_user.get("status") == "active"

    update_user(uid, {"status": "active", "verifiedAt": int(time.time() * 1000)})
    if vid:
        fs_update("verifications", vid, {"status": "approved", "approvedAt": int(time.time() * 1000)})

    # stats counter — Firestore Increment (race-safe)
    # total_users শুধু তখনই +১ হবে যখন ইউজার আগে কখনো active ছিল না
    try:
        stats_update = {"active_users": firestore.Increment(1)}
        if not was_ever_active:
            stats_update["total_users"] = firestore.Increment(1)
        db.collection("stats").document("main").set(stats_update, merge=True)
    except Exception:
        pass

    # আজকের revenue আপডেট
    today_key = datetime.now().strftime("%Y-%m-%d")
    fee_now   = s.get("fee", 50)
    try:
        db.collection("dailyRevenue").document(today_key).set(
            {"amount": firestore.Increment(fee_now)}, merge=True
        )
    except Exception:
        pass

    # Credit referrer
    user = get_user(uid) or {}
    ref_uid = user.get("referredBy")
    if ref_uid:
        ref_user = get_user(ref_uid) or {}
        lvl      = get_level(ref_user.get("points", 0), s)
        earn     = get_earn(lvl, s)
        REF_POINTS = 100
        fs_txn_add(ref_uid, balance_delta=earn, points_delta=REF_POINTS)
        # referStats নোড আপডেট — টপ রেফারারের জন্য
        increment_refer_stat(ref_uid)
        # ✅ RTDB-তে রেফার stats আপডেট
        ref_name = (get_user(ref_uid) or {}).get("name", "?")
        rtdb_stats_update_refer(ref_uid, ref_name, earn)
        try:
            await bot.send_message(
                int(ref_uid),
                f"🎊 <b>রেফার বোনাস পেয়েছেন!</b>\n\n"
                f"আপনার রেফার করা বন্ধু একটিভ হয়েছেন।\n"
                f"💰 আপনার ব্যালেন্সে <b>৳{earn}</b> যোগ হয়েছে!\n"
                f"🎯 পয়েন্ট: +{REF_POINTS}"
            )
        except Exception:
            pass

    # ✅ RTDB-তে ভেরিফিকেশন ও ইনকাম stats আপডেট
    rtdb_stats_new_verification(float(s.get("fee", 50)))

    try:
        await bot.send_message(
            int(uid),
            f"✅ <b>অভিনন্দন! একাউন্ট একটিভ হয়েছে।</b>\n\n"
            f"এখন রেফার করে আয় শুরু করুন! 🎉",
            reply_markup=main_kb()
        )
    except Exception:
        pass

    old_text = call.message.text or ""
    new_text = old_text + f"\n\n✅ অ্যাপ্রুভড — {datetime.now().strftime('%d/%m %H:%M')}"
    try:
        await call.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await call.message.answer(f"✅ <b>অ্যাপ্রুভড!</b>\nUID: <code>{uid}</code>")


@dp.callback_query_handler(lambda c: c.data.startswith("reject_ver_"))
async def cb_reject_ver(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("শুধু অ্যাডমিন এই কাজ করতে পারবেন!", show_alert=True)
        return

    await call.answer("⏳ প্রসেস হচ্ছে...")

    parts = call.data.replace("reject_ver_", "").split("|")
    uid   = parts[0]
    vid   = parts[1] if len(parts) > 1 else None

    update_user(uid, {"status": "rejected"})
    if vid:
        fs_update("verifications", vid, {"status": "rejected", "rejectedAt": int(time.time() * 1000)})

    try:
        await bot.send_message(
            int(uid),
            "❌ <b>পেমেন্ট ভেরিফিকেশন ব্যর্থ হয়েছে।</b>\n\n"
            "ট্রান্জেকশন আইডি সঠিক ছিল না।\n"
            "পুনরায় সঠিক পেমেন্ট করে /pay দিন।"
        )
    except Exception:
        pass

    old_text = call.message.text or ""
    new_text = old_text + f"\n\n❌ রিজেক্টেড — {datetime.now().strftime('%d/%m %H:%M')}"
    try:
        await call.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await call.message.answer(f"❌ <b>রিজেক্টেড!</b>\nUID: <code>{uid}</code>")

# ═══════════════════════════════════════════════════════
#   MAIN MENU HANDLERS
# ═══════════════════════════════════════════════════════
@dp.message_handler(lambda m: m.from_user.id != ADMIN_ID and m.text in [
    "🏠 হোম", "📊 আমার প্রোফাইল", "💸 টাকা উত্তোলন",
    "👥 রেফার করুন", "☀️ ডেইলি বোনাস", "📋 পেমেন্ট হিস্ট্রি",
    "ℹ️ নিয়মাবলী", "🚨 রিপোর্ট করুন"
], state="*")
async def menu_handler(message: types.Message, state: FSMContext):
    await state.finish()
    uid = str(message.from_user.id)

    if not await app_check(uid, message):
        return

    # ✅ cache থেকে আনো — সরাসরি Firestore নয়
    user = get_user(uid)
    if not user:
        await message.answer("প্রথমে /start দিন।")
        return
    if user.get("status") == "banned":
        await message.answer("🚫 আপনার অ্যাকাউন্ট বন্ধ করা হয়েছে।")
        return
    if user.get("status") != "active":
        await cmd_start(message, state)
        return

    s   = get_settings()
    txt = message.text

    # ── হোম ──
    if txt == "🏠 হোম":
        # cache invalidate করে fresh data আনো
        cache_invalidate_user(uid)
        user = get_user(uid) or user
        await _show_home(message, uid, user, s)

    # ── প্রোফাইল ──
    elif txt == "📊 আমার প্রোফাইল":
        # cache invalidate করে fresh আনো
        cache_invalidate_user(uid)
        user = get_user(uid) or user

        pts  = user.get("points", 0)
        bal  = user.get("balance", 0)
        lvl  = get_level(pts, s)
        earn = get_earn(lvl, s)
        minw = get_min_withdraw(lvl)

        # ✅ referStats থেকে আনো — পুরো users স্ক্যান নয়
        try:
            ref_stat_doc = db.collection("referStats").document(uid).get()
            total_refs = ref_stat_doc.to_dict().get("count", 0) if ref_stat_doc.exists else 0
        except Exception:
            total_refs = 0

        # active refs — শুধু এই ইউজারের রেফার করা active users গণনা
        try:
            active_docs = db.collection("users")\
                .where("referredBy", "==", uid)\
                .where("status", "==", "active")\
                .select([])\
                .get()
            active_refs = len(active_docs)
        except Exception:
            active_refs = 0

        me       = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start={user.get('referCode','')}"

        lvl2 = s["lvl2Start"]
        lvl3 = s["lvl3Start"]
        if lvl == 1:
            next_info = f"লেভেল ২ তে আর {lvl2 - pts} পয়েন্ট"
        elif lvl == 2:
            next_info = f"লেভেল ৩ তে আর {lvl3 - pts} পয়েন্ট"
        else:
            next_info = "সর্বোচ্চ লেভেলে আছেন 🏆"

        text = (
            f"📊 <b>আপনার প্রোফাইল</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 নাম:    {user.get('name','?')}\n"
            f"📞 ফোন:   <code>{user.get('phone','?')}</code>\n"
            f"🔑 রেফার কোড: <code>{user.get('referCode','?')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 ব্যালেন্স:  <b>৳{bal}</b>\n"
            f"🎯 পয়েন্ট:   <b>{bn(pts)}</b>\n"
            f"🏅 লেভেল:    <b>লেভেল {lvl}</b>\n"
            f"📈 {next_info}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট রেফার:   {bn(total_refs)} জন\n"
            f"✅ একটিভ রেফার: {bn(active_refs)} জন\n"
            f"💵 রেফার আয়:   ৳{earn} প্রতি জন\n"
            f"💸 সর্বনিম্ন উত্তোলন: ৳{minw}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>রেফার লিংক:</b>\n{ref_link}"
        )
        await message.answer(text)

    # ── রেফার ──
    elif txt == "👥 রেফার করুন":
        me       = await bot.get_me()
        ref_code = user.get("referCode", "")
        ref_link = f"https://t.me/{me.username}?start={ref_code}"
        lvl      = get_level(user.get("points", 0), s)
        earn     = get_earn(lvl, s)

        text = (
            f"👥 <b>রেফার করুন, আয় করুন!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"আপনার রেফার কোড: <code>{ref_code}</code>\n\n"
            f"🔗 রেফার লিংক:\n{ref_link}\n\n"
            f"💰 প্রতিটি সফল রেফারে আপনি পাবেন: <b>৳{earn}</b>\n\n"
            f"📤 নিচের বাটনে ক্লিক করে শেয়ার করুন:"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            "📤 শেয়ার করুন",
            url=f"https://t.me/share/url?url={ref_link}&text=IncomeApp-এ যোগ দিন!%0Aরেফার কোড: {ref_code}"
        ))
        await message.answer(text, reply_markup=kb)

    # ── ডেইলি বোনাস ──
    elif txt == "☀️ ডেইলি বোনাস":
        last_claim = user.get("lastDailyBonus", 0)
        today_ts   = int(datetime(date.today().year, date.today().month, date.today().day).timestamp() * 1000)
        bonus      = s["dailyBonus"]

        if last_claim >= today_ts:
            await message.answer(
                f"☀️ <b>ডেইলি বোনাস</b>\n\nআজকের বোনাস ইতোমধ্যে নেওয়া হয়েছে।\nকাল আবার আসুন! ⏰"
            )
        else:
            # ✅ Race-condition safe: একটি transaction-এ points ও lastDailyBonus একসাথে আপডেট
            today_claim_ts = int(time.time() * 1000)
            try:
                user_ref = db.collection("users").document(uid)

                @firestore.transactional
                def _claim_daily(transaction, ref):
                    snap = ref.get(transaction=transaction)
                    if not snap.exists:
                        return False, 0
                    d = snap.to_dict()
                    # double-claim চেক transaction-এর ভেতরেও
                    if d.get("lastDailyBonus", 0) >= today_ts:
                        return False, 0
                    new_pts = max(0, d.get("points", 0) + bonus)
                    transaction.update(ref, {
                        "points":         new_pts,
                        "lastDailyBonus": today_claim_ts,
                    })
                    return True, new_pts

                txn = db.transaction()
                claimed, new_pts = _claim_daily(txn, user_ref)
                cache_invalidate_user(uid)
            except Exception as e:
                log.error(f"Daily bonus txn error uid={uid}: {e}")
                claimed, new_pts = False, 0

            if not claimed:
                await message.answer(
                    f"☀️ <b>ডেইলি বোনাস</b>\n\nআজকের বোনাস ইতোমধ্যে নেওয়া হয়েছে।\nকাল আবার আসুন! ⏰"
                )
            else:
                await message.answer(
                    f"🎁 <b>ডেইলি বোনাস পেয়েছেন!</b>\n\n"
                    f"✅ +{bonus} পয়েন্ট আপনার একাউন্টে যোগ হয়েছে।\n"
                    f"🎯 এখন আপনার পয়েন্ট: <b>{bn(new_pts)}</b>\n\n"
                    f"কাল আবার এসে বোনাস নিন! 😊"
                )

    # ── উত্তোলন ──
    elif txt == "💸 টাকা উত্তোলন":
        pts  = user.get("points", 0)
        bal  = user.get("balance", 0)
        lvl  = get_level(pts, s)
        minw = get_min_withdraw(lvl)

        if bal < minw:
            await message.answer(
                f"💸 <b>টাকা উত্তোলন</b>\n\n"
                f"❌ আপনার ব্যালেন্স: <b>৳{bal}</b>\n"
                f"সর্বনিম্ন উত্তোলন: <b>৳{minw}</b> (লেভেল {lvl})\n\n"
                f"আরও রেফার করুন এবং ব্যালেন্স বাড়ান।"
            )
            return

        await Withdraw.choose_method.set()
        await message.answer(
            f"💸 <b>উত্তোলনের মেথড বেছে নিন</b>\n\n"
            f"আপনার ব্যালেন্স: <b>৳{bal}</b>\n"
            f"সর্বনিম্ন: <b>৳{minw}</b>",
            reply_markup=method_kb()
        )

    # ── পেমেন্ট হিস্ট্রি — ✅ শুধু এই ইউজারের ১০টা আনো ──
    elif txt == "📋 পেমেন্ট হিস্ট্রি":
        try:
            docs = db.collection("withdrawals")\
                .where("uid", "==", uid)\
                .order_by("requestedAt", direction=firestore.Query.DESCENDING)\
                .limit(10)\
                .get()
            my_list = [d.to_dict() for d in docs]
        except Exception:
            my_list = []

        if not my_list:
            await message.answer("📋 <b>পেমেন্ট হিস্ট্রি</b>\n\nকোনো উত্তোলনের রেকর্ড নেই।")
            return

        lines = ["📋 <b>পেমেন্ট হিস্ট্রি</b>\n━━━━━━━━━━━━━━━━━━"]
        for w in my_list:
            st_icon = "✅" if w.get("status") in ("paid", "success") else "⏳" if w.get("status") == "pending" else "❌"
            ts = datetime.fromtimestamp(w.get("requestedAt", 0) / 1000).strftime('%d/%m %H:%M')
            lines.append(
                f"{st_icon} ৳{w.get('amount','?')} → {w.get('number','?')} "
                f"[{w.get('method','?').upper()}] — {ts}"
            )
        await message.answer('\n'.join(lines))

    # ── নিয়মাবলী ──
    elif txt == "ℹ️ নিয়মাবলী":
        lvl2 = s["lvl2Start"]
        lvl3 = s["lvl3Start"]
        text = (
            f"ℹ️ <b>নিয়মাবলী ও লেভেল গাইড</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏅 <b>লেভেল ১</b> (০–{lvl2-1} পয়েন্ট)\n"
            f"• রেফার আয়: ৳{s['earn1']}\n"
            f"• সর্বনিম্ন উত্তোলন: ৳১৫০\n\n"
            f"🥇 <b>লেভেল ২</b> ({lvl2}–{lvl3-1} পয়েন্ট)\n"
            f"• রেফার আয়: ৳{s['earn2']}\n"
            f"• সর্বনিম্ন উত্তোলন: ৳১০০\n\n"
            f"💎 <b>লেভেল ৩</b> ({lvl3}+ পয়েন্ট)\n"
            f"• রেফার আয়: ৳{s['earn3']}\n"
            f"• সর্বনিম্ন উত্তোলন: ৳১০০\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"☀️ ডেইলি বোনাস: +{s['dailyBonus']} পয়েন্ট\n\n"
            f"⚠️ <b>গুরুত্বপূর্ণ নিয়ম:</b>\n"
            f"• জালিয়াতি করলে স্থায়ী ব্যান\n"
            f"• একটি আইডিতে একটি অ্যাকাউন্ট\n"
            f"• ভুল TxnID দিলে রিজেক্ট হবে"
        )
        await message.answer(text)

    # ── রিপোর্ট ──
    elif txt == "🚨 রিপোর্ট করুন":
        last_report = user.get("lastReport", 0)
        if (time.time() * 1000) - last_report < 86_400_000:
            remaining_ms  = 86_400_000 - ((time.time() * 1000) - last_report)
            remaining_hrs = int(remaining_ms / 3_600_000)
            remaining_min = int((remaining_ms % 3_600_000) / 60_000)
            await message.answer(
                f"⚠️ ২৪ ঘণ্টায় মাত্র একটি রিপোর্ট করা যাবে।\n"
                f"⏰ আরও {remaining_hrs} ঘণ্টা {remaining_min} মিনিট পর পাঠাতে পারবেন।"
            )
            return
        await Report.message.set()
        await message.answer(
            "🚨 <b>সমস্যা রিপোর্ট করুন</b>\n\n"
            "আপনার সমস্যাটি সংক্ষেপে লিখুন:\n"
            "⚠️ সর্বোচ্চ <b>২৫০ অক্ষর</b>\n"
            "(বাতিল করতে /cancel লিখুন)"
        )

# ═══════════════════════════════════════════════════════
#   WITHDRAW FLOW
# ═══════════════════════════════════════════════════════
@dp.callback_query_handler(lambda c: c.data.startswith("method_"), state=Withdraw.choose_method)
async def withdraw_method(call: types.CallbackQuery, state: FSMContext):
    method = call.data.split("_")[1]
    await state.update_data(method=method)
    await Withdraw.number.set()
    await call.message.answer(
        f"💳 মেথড: <b>{'বিকাশ' if method=='bkash' else 'নগদ'}</b>\n\n"
        f"📱 আপনার <b>নম্বর</b> দিন (১১ সংখ্যা):"
    )
    await call.answer()

@dp.message_handler(state=Withdraw.number)
async def withdraw_number(message: types.Message, state: FSMContext):
    num = message.text.strip()
    if len(num) != 11 or not num.isdigit():
        await message.answer("❌ সঠিক ১১ সংখ্যার নম্বর দিন:")
        return
    await state.update_data(number=num)
    await Withdraw.amount.set()
    uid  = str(message.from_user.id)
    user = get_user(uid) or {}
    bal  = user.get("balance", 0)
    s    = get_settings()
    lvl  = get_level(user.get("points", 0), s)
    minw = get_min_withdraw(lvl)
    await message.answer(
        f"💰 উত্তোলনের পরিমাণ লিখুন:\n\n"
        f"আপনার ব্যালেন্স: <b>৳{bal}</b>\n"
        f"সর্বনিম্ন: <b>৳{minw}</b>"
    )

@dp.message_handler(state=Withdraw.amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid) or {}
    s    = get_settings()
    data = await state.get_data()
    lvl  = get_level(user.get("points", 0), s)
    minw = get_min_withdraw(lvl)
    bal  = user.get("balance", 0)

    try:
        amount = float(message.text.strip())
    except:
        await message.answer("❌ সঠিক পরিমাণ লিখুন (শুধু সংখ্যা):")
        return

    if amount < minw:
        await message.answer(f"❌ সর্বনিম্ন ৳{minw} উত্তোলন করুন।")
        return
    if amount > bal:
        await message.answer(f"❌ পর্যাপ্ত ব্যালেন্স নেই। আপনার ব্যালেন্স: ৳{bal}")
        return

    # ✅ Atomic: pending চেক + balance deduct একই transaction-এ — double-spend অসম্ভব
    try:
        user_ref = db.collection("users").document(uid)

        @firestore.transactional
        def _atomic_withdraw(transaction, ref):
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                return "no_user"
            d = snap.to_dict()
            current_bal = d.get("balance", 0)
            if current_bal < amount:
                return "insufficient"
            transaction.update(ref, {"balance": round(current_bal - amount, 2)})
            return "ok"

        txn    = db.transaction()
        result = _atomic_withdraw(txn, user_ref)
        cache_invalidate_user(uid)
    except Exception as e:
        log.error(f"Withdraw atomic txn error uid={uid}: {e}")
        result = "error"

    if result == "no_user":
        await message.answer("❌ অ্যাকাউন্ট পাওয়া যায়নি।", reply_markup=main_kb())
        await state.finish()
        return
    if result == "insufficient":
        await message.answer(f"❌ পর্যাপ্ত ব্যালেন্স নেই।", reply_markup=main_kb())
        await state.finish()
        return
    if result == "error":
        await message.answer("❌ ব্যালেন্স আপডেটে সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        return

    wid = fs_add("withdrawals", {
        "uid":         uid,
        "name":        user.get("name", "?"),
        "phone":       user.get("phone", "?"),
        "number":      data["number"],
        "amount":      amount,
        "method":      data["method"],
        "status":      "pending",
        "requestedAt": int(time.time() * 1000),
    })
    await state.finish()

    admin_text = (
        f"💸 <b>উইথড্রয়াল রিকোয়েস্ট</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 নাম:   {user.get('name','?')}\n"
        f"📞 ফোন:  {user.get('phone','?')}\n"
        f"💳 মেথড: {data['method'].upper()}\n"
        f"📱 নম্বর: <code>{data['number']}</code>\n"
        f"💰 পরিমাণ: <b>৳{amount}</b>\n"
        f"🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"UID: <code>{uid}</code>  |  WID: <code>{wid}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=paid_reject_kb(wid))
    except Exception as e:
        log.warning(f"Withdraw notify error: {e}")

    await message.answer(
        f"✅ <b>উত্তোলনের আবেদন পাঠানো হয়েছে!</b>\n\n"
        f"💰 পরিমাণ: ৳{amount}\n"
        f"📱 {data['method'].upper()}: {data['number']}\n\n"
        f"অ্যাডমিন পেমেন্ট করলে আপনাকে জানানো হবে।",
        reply_markup=main_kb()
    )

# ═══════════════════════════════════════════════════════
#   ADMIN — MARK PAID / REJECT WITHDRAW
# ═══════════════════════════════════════════════════════
@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def cb_mark_paid(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("শুধু অ্যাডমিন করতে পারবেন!", show_alert=True)
        return

    await call.answer("⏳ প্রসেস হচ্ছে...")

    wid = call.data.replace("paid_", "")
    w   = fs_get("withdrawals", wid)
    if not w:
        await call.message.answer("❌ রিকোয়েস্ট পাওয়া যায়নি!")
        return
    if w.get("status") in ("paid", "success"):
        await call.message.answer("⚠️ এটা আগেই পেমেন্ট হয়ে গেছে!")
        return

    uid    = w.get("uid")
    amount = float(w.get("amount", 0))
    fs_update("withdrawals", wid, {"status": "paid", "paidAt": int(time.time() * 1000)})
    # ✅ RTDB-তে উইথড্র stats আপডেট
    w_name = w.get("name", "?")
    rtdb_stats_new_withdrawal(amount, uid, w_name)
    await _notify_user_paid(uid, w)

    old_text = call.message.text or ""
    new_text = old_text + f"\n\n✅ PAID — {datetime.now().strftime('%d/%m %H:%M')}"
    try:
        await call.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await call.message.answer(f"✅ <b>পেমেন্ট মার্ক হয়েছে!</b>\nWID: <code>{wid}</code> | ৳{amount}")


@dp.callback_query_handler(lambda c: c.data.startswith("wreject_"))
async def cb_reject_withdraw(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("শুধু অ্যাডমিন করতে পারবেন!", show_alert=True)
        return

    await call.answer("⏳ প্রসেস হচ্ছে...")

    wid = call.data.replace("wreject_", "")
    w   = fs_get("withdrawals", wid)
    if not w:
        await call.message.answer("❌ রিকোয়েস্ট পাওয়া যায়নি!")
        return
    if w.get("status") in ("paid", "success"):
        await call.message.answer("⚠️ এই উইথড্র আগেই পেমেন্ট হয়ে গেছে!")
        return
    if w.get("status") == "rejected":
        await call.message.answer("⚠️ এটা আগেই রিজেক্ট হয়েছে!")
        return

    fs_update("withdrawals", wid, {"status": "rejected", "rejectedAt": int(time.time() * 1000)})
    uid    = w.get("uid")
    amount = float(w.get("amount", 0))
    fs_txn_add(uid, balance_delta=+amount)
    await _notify_user_rejected(uid, w)

    old_text = call.message.text or ""
    new_text = old_text + f"\n\n❌ REJECTED — {datetime.now().strftime('%d/%m %H:%M')}"
    try:
        await call.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await call.message.answer(f"❌ <b>রিজেক্ট হয়েছে!</b>\nWID: <code>{wid}</code> | ৳{amount} রিফান্ড হয়েছে।")

# ═══════════════════════════════════════════════════════
#   NOTIFICATION HELPERS
# ═══════════════════════════════════════════════════════
async def _notify_user_paid(uid: str, w: dict):
    try:
        await bot.send_message(
            int(uid),
            f"✅ <b>পেমেন্ট সম্পন্ন হয়েছে!</b>\n\n"
            f"💰 ৳{w.get('amount')} আপনার "
            f"{w.get('method','?').upper()} নম্বরে পাঠানো হয়েছে।\n"
            f"📱 নম্বর: {w.get('number','?')}"
        )
    except Exception as e:
        log.warning(f"Paid notify error uid={uid}: {e}")

async def _notify_user_rejected(uid: str, w: dict):
    try:
        await bot.send_message(
            int(uid),
            f"❌ <b>উত্তোলনের আবেদন বাতিল হয়েছে।</b>\n\n"
            f"৳{w.get('amount')} আপনার ব্যালেন্সে ফেরত দেওয়া হয়েছে।\n"
            f"সমস্যায় /support লিখুন।"
        )
    except Exception as e:
        log.warning(f"Reject notify error uid={uid}: {e}")

async def watch_admin_paid_notifications():
    """
    Admin Panel থেকে paid করলে ইউজারকে notify করে।
    প্রতি ৮ সেকেন্ডে চেক করে।
    ✅ শুধু adminPaidNotify আছে এমন docs আনে — পুরো collection নয়।
    ✅ notified_wids set সরানো হয়েছে — Firestore field মুছলেই যথেষ্ট।
    """
    while True:
        try:
            docs = db.collection("withdrawals")\
                .where("adminPaidNotify", "!=", None)\
                .limit(20)\
                .get()
            for doc in docs:
                wid = doc.id
                w = doc.to_dict()
                notify_uid = w.get("adminPaidNotify")
                if notify_uid and w.get("status") in ("paid", "success"):
                    await _notify_user_paid(notify_uid, w)
                    # field মুছে দিলে পরের query-তে আর আসবে না
                    fs_update("withdrawals", wid, {"adminPaidNotify": firestore.DELETE_FIELD})
        except Exception as e:
            log.debug(f"watch_admin_paid_notifications error: {e}")
        await asyncio.sleep(8)

async def _auto_delete_report(rid: str):
    await asyncio.sleep(5)
    fs_delete("reports", rid)

# ═══════════════════════════════════════════════════════
#   REPORT FLOW
# ═══════════════════════════════════════════════════════
@dp.message_handler(state=Report.message)
async def report_message(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid) or {}

    raw_text = message.text or ""
    if len(raw_text) > 250:
        await message.answer(
            f"❌ রিপোর্ট সর্বোচ্চ ২৫০ অক্ষর হতে পারবে।\n"
            f"আপনি লিখেছেন {len(raw_text)} অক্ষর।\n\nসংক্ষেপ করে আবার লিখুন:"
        )
        return

    last_report = user.get("lastReport", 0)
    if (time.time() * 1000) - last_report < 86_400_000:
        await state.finish()
        await message.answer("⚠️ ২৪ ঘণ্টায় মাত্র একটি রিপোর্ট করা যাবে।", reply_markup=main_kb())
        return

    update_user(uid, {"lastReport": int(time.time() * 1000)})
    await state.finish()

    report_text = (
        f"🚨 <b>নতুন রিপোর্ট</b>\n"
        f"👤 {user.get('name','?')} | 📞 {user.get('phone','?')}\n"
        f"🆔 UID: <code>{uid}</code>\n"
        f"📝 {raw_text}"
    )
    try:
        await bot.send_message(ADMIN_ID, report_text)
    except Exception as e:
        log.warning(f"Report notify error: {e}")

    await message.answer("✅ <b>রিপোর্ট পাঠানো হয়েছে।</b>\n\nঅ্যাডমিন শীঘ্রই ব্যবস্থা নেবেন।", reply_markup=main_kb())

    rid = fs_add("reports", {
        "uid":       uid,
        "name":      user.get("name", "?"),
        "phone":     user.get("phone", "?"),
        "message":   raw_text,
        "createdAt": int(time.time() * 1000),
    })
    if rid:
        asyncio.get_event_loop().create_task(_auto_delete_report(rid))

# ═══════════════════════════════════════════════════════
#   ADMIN MENU HANDLERS
# ═══════════════════════════════════════════════════════
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, commands=['admin'], state="*")
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("👑 <b>অ্যাডমিন প্যানেল</b>", reply_markup=admin_kb())


@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_handler(message: types.Message, state: FSMContext):
    txt = message.text

    # ── ড্যাশবোর্ড ──
    if "📊 ড্যাশবোর্ড" in txt:
        try:
            # ✅ shallow — শুধু count আনো, পুরো data নয়
            users_count_doc = db.collection("stats").document("main").get()
            stats = users_count_doc.to_dict() if users_count_doc.exists else {}
            total    = stats.get("total_users", "?")
            active_u = stats.get("active_users", "?")
        except Exception:
            total, active_u = "?", "?"

        # ✅ শুধু pending docs আনো
        try:
            ver_pend = len(db.collection("verifications").where("status", "==", "pending").select([]).get())
        except Exception:
            ver_pend = "?"
        try:
            wit_pend = len(db.collection("withdrawals").where("status", "==", "pending").select([]).get())
        except Exception:
            wit_pend = "?"

        today_key = date.today().strftime("%Y-%m-%d")
        try:
            rev_doc = db.collection("dailyRevenue").document(today_key).get()
            rev = rev_doc.to_dict().get("amount", 0) if rev_doc.exists else 0
        except Exception:
            rev = 0

        # ✅ RTDB থেকে সব financial stats — মাত্র ১টা read
        rtdb_main = rtdb_get_dashboard()
        total_income       = rtdb_main.get("total_income", 0)
        daily_inc          = rtdb_main.get(f"daily_{today_key}", 0)
        total_verif        = rtdb_main.get("total_verifications", 0)
        total_withdr       = rtdb_main.get("total_withdrawals", 0)
        total_withdr_amt   = rtdb_main.get("total_withdrawal_amount", 0)
        total_refer_paid   = rtdb_main.get("total_refer_paid", 0)
        # daily income আলাদা নোড থেকে
        try:
            if RTDB_URL:
                di_ref = _rtdb_ref(f"stats/daily_income/{today_key}")
                daily_inc = di_ref.get() or 0 if di_ref else 0
        except Exception:
            daily_inc = 0
        total_transaction  = round(float(total_income or 0) + float(total_refer_paid or 0), 2)

        await message.answer(
            f"📊 <b>লাইভ ড্যাশবোর্ড</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট ইউজার:             {bn(total)}\n"
            f"✅ একটিভ ইউজার:           {bn(active_u)}\n"
            f"⏳ ভেরিফিকেশন পেন্ডিং:   {bn(ver_pend)}\n"
            f"💸 উইথড্র পেন্ডিং:       {bn(wit_pend)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 আজকের রেভিনিউ:        ৳{rev}\n"
            f"📅 আজকের মোট ইনকাম:     ৳{bn(daily_inc)}\n"
            f"💵 সর্বমোট ইনকাম:        ৳{bn(total_income)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔖 মোট ভেরিফিকেশন:      {bn(total_verif)} টি\n"
            f"🏧 মোট উইথড্র:          {bn(total_withdr)} টি\n"
            f"💸 মোট উইথড্র পরিমাণ:   ৳{bn(total_withdr_amt)}\n"
            f"🤝 মোট রেফার পেমেন্ট:   ৳{bn(total_refer_paid)}\n"
            f"🔄 মোট লেনদেন:          ৳{bn(total_transaction)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

    # ── পেন্ডিং ভেরিফিকেশন ──
    elif "⏳ পেন্ডিং ভেরিফিকেশন" in txt:
        try:
            docs = db.collection("verifications")\
                .where("status", "==", "pending")\
                .order_by("submittedAt")\
                .limit(10)\
                .get()
        except Exception as e:
            await message.answer(f"❌ ডেটা আনতে সমস্যা: {e}")
            return

        if not docs:
            await message.answer("✅ কোনো পেন্ডিং ভেরিফিকেশন নেই!")
            return

        await message.answer(f"⏳ <b>পেন্ডিং ভেরিফিকেশন ({len(docs)} টি)</b>")
        for doc in docs:
            vid = doc.id
            v   = doc.to_dict()
            uid = v.get("uid", "?")
            kb  = approve_reject_kb(f"{uid}|{vid}", "ver")
            await message.answer(
                f"👤 {v.get('name','?')} | 📞 রেজি: {v.get('phone','?')}\n"
                f"📱 পেমেন্ট নম্বর: <code>{v.get('senderPhone','?')}</code>\n"
                f"💳 {v.get('method','?').upper()} | 🆔 <code>{v.get('transactionId','?')}</code>",
                reply_markup=kb
            )
            await asyncio.sleep(0.2)

    # ── পেন্ডিং উইথড্রয়াল ──
    elif "💸 পেন্ডিং উইথড্রয়াল" in txt:
        try:
            docs = db.collection("withdrawals")\
                .where("status", "==", "pending")\
                .order_by("requestedAt")\
                .limit(10)\
                .get()
        except Exception as e:
            await message.answer(f"❌ ডেটা আনতে সমস্যা: {e}")
            return

        if not docs:
            await message.answer("✅ কোনো পেন্ডিং উইথড্রয়াল নেই!")
            return

        await message.answer(f"💸 <b>পেন্ডিং উইথড্রয়াল ({len(docs)} টি)</b>")
        for doc in docs:
            wid = doc.id
            w   = doc.to_dict()
            await message.answer(
                f"👤 {w.get('name','?')} | 📞 {w.get('phone','?')}\n"
                f"📱 <code>{w.get('number','?')}</code>\n"
                f"💰 <b>৳{w.get('amount','?')}</b> | {w.get('method','?').upper()}",
                reply_markup=paid_reject_kb(wid)
            )
            await asyncio.sleep(0.2)

    # ── ব্রডকাস্ট ──
    elif "📢 ব্রডকাস্ট করুন" in txt:
        await AdminState.broadcast.set()
        await message.answer("📢 ব্রডকাস্ট মেসেজ লিখুন:\n(বাতিল: /cancel)")

    # ── সেটিংস ──
    elif "⚙️ সেটিংস দেখুন" in txt:
        s = get_settings()
        await message.answer(
            f"⚙️ <b>বর্তমান সেটিংস</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📱 বিকাশ: <code>{s['bkash']}</code>\n"
            f"💚 নগদ:  <code>{s['nagad']}</code>\n"
            f"💰 ভেরিফিকেশন ফি: ৳{s['fee']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏅 লেভেল ২: {s['lvl2Start']} পয়েন্ট থেকে\n"
            f"💎 লেভেল ৩: {s['lvl3Start']} পয়েন্ট থেকে\n"
            f"💵 লেভেল ১ আয়: ৳{s['earn1']}\n"
            f"💵 লেভেল ২ আয়: ৳{s['earn2']}\n"
            f"💵 লেভেল ৩ আয়: ৳{s['earn3']}\n"
            f"☀️ ডেইলি বোনাস: {s['dailyBonus']} পয়েন্ট\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔌 অ্যাপ চালু: {'হ্যাঁ ✅' if s['appOn'] else 'না ❌'}\n"
            f"📝 রেজিস্ট্রেশন: {'চালু ✅' if s['regOn'] else 'বন্ধ ❌'}\n\n"
            f"<i>সেটিংস পরিবর্তন করতে Admin Panel ওয়েব অ্যাপ ব্যবহার করুন।</i>"
        )

    # ── মেইন মেনু ──
    elif "🏠 মেইন মেনু" in txt:
        uid  = str(message.from_user.id)
        user = get_user(uid) or {}
        s    = get_settings()
        await _show_home(message, uid, user, s)

    # ── উইথড্র হিস্ট্রি — ✅ শুধু completed docs ──
    elif "📋 উইথড্র হিস্ট্রি" in txt:
        try:
            docs = db.collection("withdrawals")\
                .where("status", "in", ["paid", "success", "rejected"])\
                .order_by("requestedAt", direction=firestore.Query.DESCENDING)\
                .limit(15)\
                .get()
        except Exception as e:
            await message.answer(f"❌ ডেটা আনতে সমস্যা: {e}")
            return

        if not docs:
            await message.answer("📋 কোনো সম্পন্ন উইথড্রয়াল নেই।")
            return

        lines = [f"📋 <b>উইথড্র হিস্ট্রি (সর্বশেষ {len(docs)} টি)</b>\n"]
        for doc in docs:
            w      = doc.to_dict()
            icon   = "✅" if w.get("status") in ("paid", "success") else "❌"
            ts     = w.get("requestedAt", 0)
            dt_str = datetime.fromtimestamp(ts / 1000).strftime("%d/%m %H:%M") if ts else "?"
            lines.append(
                f"{icon} {w.get('name','?')} | ৳{w.get('amount','?')} | "
                f"{w.get('method','?').upper()} | {dt_str}"
            )
        await message.answer("\n".join(lines))

    # ── একটিভ ইউজার লিস্ট — ✅ শুধু শেষ ২০ জন ──
    elif "👥 একটিভ ইউজার লিস্ট" in txt:
        await message.answer("⏳ একটিভ ইউজার লোড হচ্ছে...")
        try:
            docs = db.collection("users")\
                .where("status", "==", "active")\
                .order_by("verifiedAt", direction=firestore.Query.DESCENDING)\
                .limit(20)\
                .get()
        except Exception as e:
            await message.answer(f"❌ ডেটা আনতে সমস্যা: {e}")
            return

        if not docs:
            await message.answer("কোনো একটিভ ইউজার নেই।")
            return

        lines = [f"✅ <b>একটিভ ইউজার (সর্বশেষ {len(docs)} জন):</b>\n"]
        medals = ["১","২","৩","৪","৫","৬","৭","৮","৯","১০",
                  "১১","১২","১৩","১৪","১৫","১৬","১৭","১৮","১৯","২০"]
        for i, doc in enumerate(docs):
            u      = doc.to_dict()
            ts     = u.get("verifiedAt", 0)
            dt_str = datetime.fromtimestamp(ts / 1000).strftime("%d/%m/%y") if ts else "?"
            lines.append(
                f"{medals[i]}. {u.get('name','?')} | "
                f"📞 {u.get('phone','?')} | "
                f"💰 ৳{u.get('balance', 0)} | {dt_str}"
            )
        await message.answer("\n".join(lines))

    # ── টপ রেফারার — ✅ RTDB থেকে ১০০ জন, ১টা read ──
    elif "🏆 টপ রেফারার" in txt:
        await message.answer("⏳ টপ রেফারার লোড হচ্ছে...")
        items = rtdb_get_top_referrers(100)

        if not items:
            # fallback: Firestore referStats থেকে আনো
            try:
                docs = db.collection("referStats")\
                    .order_by("count", direction=firestore.Query.DESCENDING)\
                    .limit(10)\
                    .get()
                items = [{"uid": d.id, "name": None, "count": d.to_dict().get("count", 0)} for d in docs]
            except Exception as e:
                await message.answer(f"❌ ডেটা আনতে সমস্যা: {e}")
                return

        if not items:
            await message.answer("🏆 এখনো কোনো রেফার হয়নি।")
            return

        medals = ["🥇","🥈","🥉"] + [f"{i}️⃣" for i in range(4, 11)] + \
                 [f"<b>{i}</b>" for i in range(11, 101)]

        # ১০ জন করে ভাগ করে পাঠাও (Telegram message limit)
        chunk_size = 20
        for chunk_start in range(0, min(len(items), 100), chunk_size):
            chunk = items[chunk_start:chunk_start + chunk_size]
            lines = [f"🏆 <b>টপ রেফারার ({chunk_start+1}–{chunk_start+len(chunk)})</b>\n"]
            for i, item in enumerate(chunk):
                rank     = chunk_start + i
                uid_key  = item.get("uid", "?")
                count    = item.get("count", 0)
                name     = item.get("name") or (get_user(uid_key) or {}).get("name", "?")
                medal    = medals[rank] if rank < len(medals) else f"<b>{rank+1}</b>"
                lines.append(
                    f"{medal} {name}\n"
                    f"   👥 রেফার: {bn(count)} জন\n"
                )
            await message.answer("\n".join(lines))
            await asyncio.sleep(0.3)

    # ── টপ উইথড্রয়ার — ✅ RTDB থেকে ১০০ জন, ১টা read ──
    elif "🏧 টপ উইথড্রয়ার" in txt:
        await message.answer("⏳ টপ উইথড্রয়ার লোড হচ্ছে...")
        items = rtdb_get_top_withdrawers(100)

        if not items:
            await message.answer("🏧 এখনো কোনো উইথড্র হয়নি।")
            return

        medals = ["🥇","🥈","🥉"] + [f"{i}️⃣" for i in range(4, 11)] + \
                 [f"<b>{i}</b>" for i in range(11, 101)]

        chunk_size = 20
        for chunk_start in range(0, min(len(items), 100), chunk_size):
            chunk = items[chunk_start:chunk_start + chunk_size]
            lines = [f"🏧 <b>টপ উইথড্রয়ার ({chunk_start+1}–{chunk_start+len(chunk)})</b>\n"]
            for i, item in enumerate(chunk):
                rank  = chunk_start + i
                name  = item.get("name", "?")
                total = item.get("total", 0)
                medal = medals[rank] if rank < len(medals) else f"<b>{rank+1}</b>"
                lines.append(
                    f"{medal} {name}\n"
                    f"   💸 মোট উইথড্র: ৳{bn(total)}\n"
                )
            await message.answer("\n".join(lines))
            await asyncio.sleep(0.3)

    else:
        pass


@dp.message_handler(state=AdminState.broadcast)
async def admin_broadcast(message: types.Message, state: FSMContext):
    notice_text = message.text
    await state.finish()

    # ✅ শুধু UID আনো — পুরো profile নয়
    try:
        # Firestore-এ document ID = UID, তাই select([]) দিয়ে শুধু IDs আনা যায়
        docs = db.collection("users").select([]).get()
        uid_list = [doc.id for doc in docs]
    except Exception as e:
        await message.answer(f"❌ ইউজার তালিকা আনতে সমস্যা: {e}", reply_markup=admin_kb())
        return

    total_users = len(uid_list)
    await message.answer(f"⏳ {bn(total_users)} জনের কাছে পাঠানো শুরু হচ্ছে...")

    sent = 0
    failed = 0
    BATCH = 50
    for i in range(0, total_users, BATCH):
        batch = uid_list[i:i + BATCH]
        for uid_str in batch:
            try:
                await bot.send_message(
                    int(uid_str),
                    f"📢 <b>নতুন আপডেট:</b>\n\n{notice_text}"
                )
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.034)
        if (i + BATCH) % 500 == 0 and i + BATCH < total_users:
            await message.answer(f"⏳ অগ্রগতি: {bn(i + BATCH)}/{bn(total_users)} জন সম্পন্ন...")
        if i + BATCH < total_users:
            await asyncio.sleep(2)

    await message.answer(
        f"✅ ব্রডকাস্ট সম্পন্ন!\n"
        f"📤 পাঠানো হয়েছে: {bn(sent)} জন\n"
        f"❌ ব্যর্থ: {bn(failed)} জন",
        reply_markup=admin_kb()
    )

# ═══════════════════════════════════════════════════════
#   MISC COMMANDS
# ═══════════════════════════════════════════════════════
@dp.message_handler(commands=['status'], state="*")
async def cmd_status(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid)
    if not user:
        await message.answer("আপনার কোনো অ্যাকাউন্ট নেই। /start দিন।")
        return
    st    = user.get("status", "?")
    icons = {"active":"✅","pending":"⏳","review":"🔍","rejected":"❌","banned":"🚫","new":"🆕"}
    await message.answer(
        f"📍 <b>একাউন্ট স্ট্যাটাস</b>\n\n"
        f"{icons.get(st,'❓')} <b>{st.upper()}</b>\n\n"
        f"{'একাউন্ট সক্রিয় আছে।' if st=='active' else 'অ্যাডমিন অ্যাপ্রুভের অপেক্ষায়।' if st in ('pending','review','new') else 'সাপোর্টে যোগাযোগ করুন।'}"
    )

@dp.message_handler(commands=['support'], state="*")
async def cmd_support(message: types.Message, state: FSMContext):
    await message.answer(
        "📞 <b>কাস্টমার সাপোর্ট</b>\n\n"
        "যেকোনো সমস্যায় আমাদের সাথে যোগাযোগ করুন:\n\n"
        "• Telegram: @support_username\n"
        "• WhatsApp: 01XXXXXXXXX\n\n"
        "সমস্যা রিপোর্ট করতে /report লিখুন।"
    )

@dp.message_handler(commands=['report'], state="*")
async def cmd_report(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid) or {}
    last = user.get("lastReport", 0)
    if (time.time() * 1000) - last < 86_400_000:
        await message.answer("⚠️ ২৪ ঘণ্টায় মাত্র একটি রিপোর্ট করা যাবে।")
        return
    await Report.message.set()
    await message.answer(
        "🚨 <b>সমস্যা রিপোর্ট করুন</b>\n\n"
        "আপনার সমস্যাটি সংক্ষেপে লিখুন:\n"
        "⚠️ সর্বোচ্চ <b>২৫০ অক্ষর</b>\n"
        "(বাতিল করতে /cancel লিখুন)"
    )

@dp.message_handler(commands=['cancel'], state="*")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ বাতিল করা হয়েছে।", reply_markup=main_kb())

# ═══════════════════════════════════════════════════════
#   FALLBACK
# ═══════════════════════════════════════════════════════
@dp.message_handler(state="*")
async def fallback(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid)
    if not user or user.get("status") != "active":
        await cmd_start(message, state)
        return
    await message.answer("ℹ️ নিচের মেনু থেকে অপশন বেছে নিন।", reply_markup=main_kb())

# ═══════════════════════════════════════════════════════
#   CACHE CLEANUP
# ═══════════════════════════════════════════════════════
async def cleanup_old_cache():
    """প্রতি ঘণ্টায় মেয়াদ শেষ cache entries মুছে RAM মুক্ত রাখে।"""
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        expired = [uid for uid, entry in list(_user_cache.items())
                   if (now - entry["ts"]) > USER_CACHE_TTL]
        for uid in expired:
            _user_cache.pop(uid, None)
        if expired:
            log.info(f"🧹 Cache cleanup: {len(expired)} expired entries removed. Remaining: {len(_user_cache)}")

# ═══════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════
if __name__ == '__main__':
    keep_alive()
    log.info("IncomeApp Bot starting (Firestore mode)...")

    loop = asyncio.get_event_loop()
    loop.create_task(watch_admin_paid_notifications())
    loop.create_task(cleanup_old_cache())
    executor.start_polling(dp, skip_updates=True, loop=loop)
