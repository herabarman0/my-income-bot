# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════╗
# ║          IncomeApp — Telegram Bot (main.py)          ║
# ║   Firebase Realtime DB  ·  Admin Panel Compatible    ║
# ╚══════════════════════════════════════════════════════╝

import logging
import os
import asyncio
import requests
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

# ═══════════════════════════════════════════════════════
#   KEEP-ALIVE  (Replit / Render)
# ═══════════════════════════════════════════════════════
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "IncomeApp Bot is Running! ✅"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ═══════════════════════════════════════════════════════
#   CONFIGURATION
# ═══════════════════════════════════════════════════════
API_TOKEN      = os.getenv('BOT_TOKEN', '')
ADMIN_ID       = int(os.getenv('ADMIN_ID', '0'))
FIREBASE_URL   = os.getenv('FIREBASE_URL', 'https://incomeapp-947c9-default-rtdb.firebaseio.com')

storage = MemoryStorage()
bot     = Bot(token=API_TOKEN, parse_mode="HTML")
dp      = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log     = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#   FIREBASE HELPERS
# ═══════════════════════════════════════════════════════
def fb_get(path: str):
    try:
        r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=8)
        return r.json()
    except Exception as e:
        log.error(f"fb_get error [{path}]: {e}")
        return None

def fb_put(path: str, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
    except Exception as e:
        log.error(f"fb_put error [{path}]: {e}")

def fb_update(path: str, data):
    try:
        requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
    except Exception as e:
        log.error(f"fb_update error [{path}]: {e}")

def fb_push(path: str, data):
    """Adds a new child node (like Firebase push)"""
    try:
        r = requests.post(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
        return r.json().get('name')
    except Exception as e:
        log.error(f"fb_push error [{path}]: {e}")
        return None

def fb_delete(path: str):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=8)
    except Exception as e:
        log.error(f"fb_delete error [{path}]: {e}")

# ═══════════════════════════════════════════════════════
#   LOCAL CACHE  (RAM — no TTL, invalidate-on-write)
#
#   শুধু  users/{uid}  নোড ক্যাশ করা হয়।
#   যখনই কোনো ফাংশন  users/{uid}  আপডেট করে,
#   সেই UID-এর ক্যাশ সাথে সাথে মুছে যায়।
#   পরের রিড-এ নতুন ডেটা Firebase থেকে আসে
#   এবং আবার ক্যাশে জমা হয়।
# ═══════════════════════════════════════════════════════
_user_cache: dict = {}   # { uid: user_dict }

def cache_get_user(uid: str):
    """RAM থেকে ইউজার ডেটা দাও। না থাকলে None।"""
    return _user_cache.get(uid)

def cache_set_user(uid: str, data: dict):
    """RAM-এ ইউজার ডেটা রাখো।"""
    if data:
        _user_cache[uid] = dict(data)   # shallow copy

def cache_invalidate_user(uid: str):
    """ইউজারের ক্যাশ মুছে ফেলো (ডেটা পরিবর্তন হলে)।"""
    _user_cache.pop(uid, None)
    log.debug(f"Cache invalidated: {uid}")

# ── cached user fetch (drop-in replacement for fb_get("users/uid")) ──
def get_user(uid: str) -> dict | None:
    """
    প্রথমে RAM চেক করে। না থাকলে Firebase থেকে আনে
    এবং RAM-এ রেখে দেয়।
    """
    cached = cache_get_user(uid)
    if cached is not None:
        log.debug(f"Cache HIT: {uid}")
        return cached
    log.debug(f"Cache MISS: {uid}  → Firebase read")
    data = fb_get(f"users/{uid}")   # ← সরাসরি Firebase
    if data:
        cache_set_user(uid, data)
    return data

# ── cache-aware write helpers ──
def update_user(uid: str, fields: dict):
    """Firebase আপডেট করে, তারপর ক্যাশ invalidate করে।"""
    fb_update(f"users/{uid}", fields)   # ← সরাসরি Firebase
    cache_invalidate_user(uid)

def put_user(uid: str, data: dict):
    """Firebase-এ নতুন ইউজার রাখে, তারপর ক্যাশ সেট করে।"""
    fb_put(f"users/{uid}", data)
    cache_set_user(uid, data)   # নতুন ডেটাই ক্যাশে রাখো

# ═══════════════════════════════════════════════════════
#   SETTINGS HELPER
# ═══════════════════════════════════════════════════════
def get_settings() -> dict:
    s = fb_get("settings") or {}
    return {
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
        "dailyBonus": s.get("dailyBonus", 5),
    }

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
    users = fb_get("users") or {}
    return not any(u.get("referCode") == code for u in users.values())

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
    try:
        s = str(int(float(n)))
        d = {'0':'০','1':'১','2':'২','3':'৩','4':'৪','5':'৫','6':'৬','7':'৭','8':'৮','9':'৯'}
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
    """Returns True if app is ON and user is allowed."""
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

    # Admin shortcut
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👑 <b>অ্যাডমিন প্যানেলে স্বাগতম!</b>\n\n"
            "নিচের মেনু থেকে যেকোনো অপশন বেছে নিন।",
            reply_markup=admin_kb()
        )
        return

    user = get_user(uid)

    # ── NEW USER ──
    if not user:
        if not s["regOn"]:
            await message.answer("❌ নতুন নিবন্ধন সাময়িকভাবে বন্ধ আছে।")
            return
        args = message.get_args()
        ref_by = args if args else None
        # Verify ref code exists
        if ref_by:
            users_all = fb_get("users") or {}
            if not any(u.get("referCode") == ref_by for u in users_all.values()):
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

    # ── EXISTING USER ──
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

    # active
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
    if len(phone) != 11 or not phone.isdigit():
        await message.answer("❌ সঠিক ১১ সংখ্যার ফোন নম্বর দিন:")
        return
    # Check duplicate phone
    users = fb_get("users") or {}
    if any(u.get("phone") == phone for u in users.values()):
        await message.answer("❌ এই ফোন নম্বরে আগেই অ্যাকাউন্ট আছে! অন্য নম্বর দিন:")
        return
    await state.update_data(phone=phone)
    await Reg.ref_code.set()
    await message.answer(
        "🎟 বন্ধুর <b>রেফার কোড</b> থাকলে লিখুন, না থাকলে <b>skip</b> লিখুন:"
    )

@dp.message_handler(state=Reg.ref_code)
async def reg_ref_code(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    data = await state.get_data()
    code = message.text.strip().upper()
    s    = get_settings()

    referred_by_uid = None
    if code != "SKIP" and code:
        users_all = fb_get("users") or {}
        match = next((k for k, v in users_all.items() if v.get("referCode") == code), None)
        if match:
            referred_by_uid = match
        else:
            await message.answer("⚠️ রেফার কোড পাওয়া যায়নি। Skip করুন বা সঠিক কোড দিন:")
            return

    # Override from /start args if present
    if data.get("referred_by") and not referred_by_uid:
        # referred_by is a referCode from start args
        users_all = fb_get("users") or {}
        match = next(
            (k for k, v in users_all.items() if v.get("referCode") == data["referred_by"]),
            None
        )
        referred_by_uid = match

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
    put_user(uid, user_data)   # Firebase write + cache set
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

    await Pay.txn_id.set()
    await call.message.answer(
        f"✅ মেথড: <b>{'বিকাশ' if method=='bkash' else 'নগদ'}</b>\n\n"
        f"🆔 আপনার ট্রান্জেকশন আইডি দিন:"
    )
    await call.answer()

def _validate_txn(txn: str, method: str) -> tuple[bool, str]:
    """
    Validate transaction ID silently.
    Rules (hidden from user):
      bkash: exactly 10 chars, must contain both letters and digits
      nagad:  exactly 8 chars, must contain both letters and digits
    Returns (is_valid, error_message)
    """
    expected = 10 if method == "bkash" else 8
    txn_up   = txn.upper()

    has_letter = any(c.isalpha() for c in txn_up)
    has_digit  = any(c.isdigit() for c in txn_up)
    is_alnum   = all(c.isalnum() for c in txn_up)

    if not txn or len(txn_up) != expected:
        return False, "❌ ট্রান্জেকশন আইডি সঠিক নয়। আবার চেষ্টা করুন:"
    if not is_alnum:
        return False, "❌ ট্রান্জেকশন আইডি সঠিক নয়। আবার চেষ্টা করুন:"
    if not has_letter or not has_digit:
        return False, "❌ ট্রান্জেকশন আইডি সঠিক নয়। আবার চেষ্টা করুন:"
    return True, ""

@dp.message_handler(state=Pay.txn_id)
async def pay_txn_id(message: types.Message, state: FSMContext):
    uid    = str(message.from_user.id)
    data   = await state.get_data()
    txn    = message.text.strip()
    method = data.get("method", "bkash")

    valid, err_msg = _validate_txn(txn, method)
    if not valid:
        await message.answer(err_msg)
        return

    user = get_user(uid) or {}
    s    = get_settings()

    # Save verification request
    ver_data = {
        "uid":           uid,
        "name":          user.get("name", "?"),
        "phone":         user.get("phone", "?"),
        "method":        method,
        "transactionId": txn,
        "status":        "pending",
        "submittedAt":   int(time.time() * 1000),
    }
    vid = fb_push("verifications", ver_data)
    update_user(uid, {"status": "review"})

    # Notify admin via Telegram
    admin_text = (
        f"🔔 <b>নতুন ভেরিফিকেশন রিকোয়েস্ট</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 নাম:  {user.get('name','?')}\n"
        f"📞 ফোন: {user.get('phone','?')}\n"
        f"💳 মেথড: {method.upper()}\n"
        f"🆔 TxnID: <code>{txn}</code>\n"
        f"🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"UID: <code>{uid}</code>  |  VID: <code>{vid}</code>"
    )
    try:
        await bot.send_message(
            ADMIN_ID, admin_text,
            reply_markup=approve_reject_kb(f"{uid}|{vid}", "ver")
        )
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
    parts  = call.data.replace("approve_ver_", "").split("|")
    uid    = parts[0]
    vid    = parts[1] if len(parts) > 1 else None
    s      = get_settings()

    update_user(uid, {"status": "active", "verifiedAt": int(time.time() * 1000)})
    if vid:
        fb_update(f"verifications/{vid}", {"status": "approved", "approvedAt": int(time.time() * 1000)})

    # Credit referrer
    user = get_user(uid) or {}
    ref_uid = user.get("referredBy")
    if ref_uid:
        ref_user = get_user(ref_uid) or {}
        ref_pts  = ref_user.get("points", 0)
        ref_bal  = ref_user.get("balance", 0)
        lvl      = get_level(ref_pts, s)
        earn     = get_earn(lvl, s)
        update_user(ref_uid, {
            "balance": ref_bal + earn,
            "points":  ref_pts + earn,
        })
        try:
            await bot.send_message(
                int(ref_uid),
                f"🎊 <b>রেফার বোনাস পেয়েছেন!</b>\n\n"
                f"আপনার রেফার করা বন্ধু একটিভ হয়েছেন।\n"
                f"💰 আপনার ব্যালেন্সে <b>৳{earn}</b> যোগ হয়েছে!\n"
                f"🎯 পয়েন্ট: +{earn}"
            )
        except:
            pass

    # Notify new user
    try:
        await bot.send_message(
            int(uid),
            f"✅ <b>অভিনন্দন! একাউন্ট একটিভ হয়েছে।</b>\n\n"
            f"এখন রেফার করে আয় শুরু করুন! 🎉",
            reply_markup=main_kb()
        )
    except:
        pass

    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>অ্যাপ্রুভড</b> — {datetime.now().strftime('%H:%M')}"
    )
    await call.answer("অ্যাপ্রুভ সম্পন্ন!")


@dp.callback_query_handler(lambda c: c.data.startswith("reject_ver_"))
async def cb_reject_ver(call: types.CallbackQuery):
    parts = call.data.replace("reject_ver_", "").split("|")
    uid   = parts[0]
    vid   = parts[1] if len(parts) > 1 else None

    update_user(uid, {"status": "rejected"})
    if vid:
        fb_update(f"verifications/{vid}", {"status": "rejected", "rejectedAt": int(time.time() * 1000)})

    try:
        await bot.send_message(
            int(uid),
            "❌ <b>পেমেন্ট ভেরিফিকেশন ব্যর্থ হয়েছে।</b>\n\n"
            "ট্রান্জেকশন আইডি সঠিক ছিল না।\n"
            "পুনরায় সঠিক পেমেন্ট করে /pay দিন।"
        )
    except:
        pass

    await call.message.edit_text(
        call.message.text + f"\n\n❌ <b>রিজেক্টেড</b> — {datetime.now().strftime('%H:%M')}"
    )
    await call.answer("রিজেক্ট সম্পন্ন!")

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
    uid  = str(message.from_user.id)

    if not await app_check(uid, message):
        return

    user = get_user(uid)
    if not user:
        await message.answer("প্রথমে /start দিন।")
        return
    if user.get("status") != "active":
        await cmd_start(message, state)
        return

    s   = get_settings()
    txt = message.text

    # ── হোম ──
    if txt == "🏠 হোম":
        await _show_home(message, uid, user, s)

    # ── প্রোফাইল ──
    elif txt == "📊 আমার প্রোফাইল":
        pts  = user.get("points", 0)
        bal  = user.get("balance", 0)
        lvl  = get_level(pts, s)
        earn = get_earn(lvl, s)
        minw = get_min_withdraw(lvl)

        # Refer stats
        all_users    = fb_get("users") or {}
        total_refs   = sum(1 for u in all_users.values() if u.get("referredBy") == uid)
        active_refs  = sum(1 for u in all_users.values() if u.get("referredBy") == uid and u.get("status") == "active")

        me       = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start={user.get('referCode','')}"

        # Level progress
        lvl2 = s["lvl2Start"]
        lvl3 = s["lvl3Start"]
        if lvl == 1:
            next_pts  = lvl2 - pts
            next_info = f"লেভেল ২ তে আর {next_pts} পয়েন্ট"
        elif lvl == 2:
            next_pts  = lvl3 - pts
            next_info = f"লেভেল ৩ তে আর {next_pts} পয়েন্ট"
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
            url=f"https://t.me/share/url?url={ref_link}&text=IncomeApp-এ যোগ দিন, রেফার করে আয় করুন!%0A%0Aআমার রেফার কোড: {ref_code}"
        ))
        await message.answer(text, reply_markup=kb)

    # ── ডেইলি বোনাস ──
    elif txt == "☀️ ডেইলি বোনাস":
        last_claim = user.get("lastDailyBonus", 0)
        today_ts   = int(datetime(date.today().year, date.today().month, date.today().day).timestamp() * 1000)
        bonus      = s["dailyBonus"]

        if last_claim >= today_ts:
            await message.answer(
                f"☀️ <b>ডেইলি বোনাস</b>\n\n"
                f"আজকের বোনাস ইতোমধ্যে নেওয়া হয়েছে।\n"
                f"কাল আবার আসুন! ⏰"
            )
        else:
            new_pts = user.get("points", 0) + bonus
            update_user(uid, {
                "points":         new_pts,
                "lastDailyBonus": int(time.time() * 1000),
            })
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

    # ── পেমেন্ট হিস্ট্রি ──
    elif txt == "📋 পেমেন্ট হিস্ট্রি":
        withdrawals = fb_get("withdrawals") or {}
        my_list = [
            w for w in withdrawals.values()
            if w.get("uid") == uid
        ]
        my_list.sort(key=lambda x: x.get("requestedAt", 0), reverse=True)

        if not my_list:
            await message.answer("📋 <b>পেমেন্ট হিস্ট্রি</b>\n\nকোনো উত্তোলনের রেকর্ড নেই।")
            return

        lines = ["📋 <b>পেমেন্ট হিস্ট্রি</b>\n━━━━━━━━━━━━━━━━━━"]
        for w in my_list[:10]:
            st_icon = "✅" if w.get("status") == "success" else "⏳" if w.get("status") == "pending" else "❌"
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
            await message.answer(
                "⚠️ ২৪ ঘণ্টায় মাত্র একটি রিপোর্ট করা যাবে।\n"
                "কাল আবার চেষ্টা করুন।"
            )
            return
        await Report.message.set()
        await message.answer(
            "🚨 <b>সমস্যা রিপোর্ট করুন</b>\n\n"
            "আপনার সমস্যাটি বিস্তারিত লিখুন:\n"
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

    wid = fb_push("withdrawals", {
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
    wid = call.data.replace("paid_", "")
    w   = fb_get(f"withdrawals/{wid}")
    if not w:
        await call.answer("রিকোয়েস্ট পাওয়া যায়নি!", show_alert=True)
        return

    fb_update(f"withdrawals/{wid}", {"status": "success", "paidAt": int(time.time() * 1000)})
    uid  = w.get("uid")
    user = get_user(uid) or {}
    new_bal = max(0, user.get("balance", 0) - float(w.get("amount", 0)))
    update_user(uid, {"balance": new_bal})

    try:
        await bot.send_message(
            int(uid),
            f"✅ <b>পেমেন্ট সম্পন্ন হয়েছে!</b>\n\n"
            f"💰 ৳{w.get('amount')} আপনার {w.get('method','?').upper()} নম্বরে পাঠানো হয়েছে।\n"
            f"📱 নম্বর: {w.get('number','?')}"
        )
    except:
        pass

    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>PAID</b> — {datetime.now().strftime('%H:%M')}"
    )
    await call.answer("পেমেন্ট মার্ক করা হয়েছে!")


@dp.callback_query_handler(lambda c: c.data.startswith("wreject_"))
async def cb_reject_withdraw(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("শুধু অ্যাডমিন করতে পারবেন!", show_alert=True)
        return
    wid = call.data.replace("wreject_", "")
    w   = fb_get(f"withdrawals/{wid}")
    if not w:
        await call.answer("রিকোয়েস্ট পাওয়া যায়নি!", show_alert=True)
        return

    fb_update(f"withdrawals/{wid}", {"status": "rejected", "rejectedAt": int(time.time() * 1000)})
    # Refund
    uid  = w.get("uid")
    user = get_user(uid) or {}
    update_user(uid, {"balance": user.get("balance", 0) + float(w.get("amount", 0))})

    try:
        await bot.send_message(
            int(uid),
            f"❌ <b>উত্তোলনের আবেদন বাতিল হয়েছে।</b>\n\n"
            f"৳{w.get('amount')} আপনার ব্যালেন্সে ফেরত দেওয়া হয়েছে।\n"
            f"সমস্যায় /support লিখুন।"
        )
    except:
        pass

    await call.message.edit_text(
        call.message.text + f"\n\n❌ <b>REJECTED</b> — {datetime.now().strftime('%H:%M')}"
    )
    await call.answer("রিজেক্ট করা হয়েছে!")

# ═══════════════════════════════════════════════════════
#   REPORT FLOW
# ═══════════════════════════════════════════════════════
@dp.message_handler(state=Report.message)
async def report_message(message: types.Message, state: FSMContext):
    uid  = str(message.from_user.id)
    user = get_user(uid) or {}

    fb_push("reports", {
        "uid":       uid,
        "name":      user.get("name", "?"),
        "phone":     user.get("phone", "?"),
        "message":   message.text,
        "read":      False,
        "createdAt": int(time.time() * 1000),
    })
    update_user(uid, {"lastReport": int(time.time() * 1000)})

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚨 <b>নতুন রিপোর্ট</b>\n"
            f"👤 {user.get('name','?')} | 📞 {user.get('phone','?')}\n"
            f"UID: <code>{uid}</code>\n\n"
            f"📝 {message.text}"
        )
    except:
        pass

    await state.finish()
    await message.answer(
        "✅ <b>রিপোর্ট পাঠানো হয়েছে।</b>\n\nঅ্যাডমিন শীঘ্রই ব্যবস্থা নেবেন।",
        reply_markup=main_kb()
    )

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
        users  = fb_get("users") or {}
        vers   = fb_get("verifications") or {}
        withs  = fb_get("withdrawals") or {}
        s      = get_settings()

        total      = len(users)
        active_u   = sum(1 for u in users.values() if u.get("status") == "active")
        ver_pend   = sum(1 for v in vers.values()  if v.get("status") in ("pending","review"))
        wit_pend   = sum(1 for w in withs.values() if w.get("status") == "pending")

        today = date.today().isoformat()
        rev   = sum(
            s["fee"] for u in users.values()
            if u.get("verifiedAt") and
            datetime.fromtimestamp(u["verifiedAt"] / 1000).date().isoformat() == today
        )

        await message.answer(
            f"📊 <b>লাইভ ড্যাশবোর্ড</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট ইউজার:          {bn(total)}\n"
            f"✅ একটিভ ইউজার:        {bn(active_u)}\n"
            f"⏳ ভেরিফিকেশন পেন্ডিং: {bn(ver_pend)}\n"
            f"💸 উইথড্র পেন্ডিং:    {bn(wit_pend)}\n"
            f"💰 আজকের রেভিনিউ:     ৳{rev}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

    # ── পেন্ডিং ভেরিফিকেশন ──
    elif "⏳ পেন্ডিং ভেরিফিকেশন" in txt:
        vers  = fb_get("verifications") or {}
        plist = [(vid, v) for vid, v in vers.items() if v.get("status") in ("pending", "review")]

        if not plist:
            await message.answer("✅ কোনো পেন্ডিং ভেরিফিকেশন নেই!")
            return

        await message.answer(f"⏳ <b>পেন্ডিং ভেরিফিকেশন ({len(plist)} টি)</b>")
        for vid, v in plist[:10]:
            uid = v.get("uid", "?")
            kb  = approve_reject_kb(f"{uid}|{vid}", "ver")
            await message.answer(
                f"👤 {v.get('name','?')} | 📞 {v.get('phone','?')}\n"
                f"💳 {v.get('method','?').upper()} | 🆔 <code>{v.get('transactionId','?')}</code>",
                reply_markup=kb
            )
            await asyncio.sleep(0.2)

    # ── পেন্ডিং উইথড্রয়াল ──
    elif "💸 পেন্ডিং উইথড্রয়াল" in txt:
        withs  = fb_get("withdrawals") or {}
        plist  = [(wid, w) for wid, w in withs.items() if w.get("status") == "pending"]

        if not plist:
            await message.answer("✅ কোনো পেন্ডিং উইথড্রয়াল নেই!")
            return

        await message.answer(f"💸 <b>পেন্ডিং উইথড্রয়াল ({len(plist)} টি)</b>")
        for wid, w in plist[:10]:
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
        user = get_user(str(message.from_user.id)) or {}
        s    = get_settings()
        await _show_home(message, str(message.from_user.id), user, s)

    else:
        # fallback — treat admin as user if not a command
        pass


@dp.message_handler(state=AdminState.broadcast)
async def admin_broadcast(message: types.Message, state: FSMContext):
    notice_text = message.text
    await state.finish()
    users = fb_get("users") or {}
    await message.answer(f"⏳ {len(users)} জনের কাছে পাঠানো হচ্ছে...")

    sent = 0
    for uid_str in users:
        try:
            await bot.send_message(
                int(uid_str),
                f"📢 <b>নতুন আপডেট:</b>\n\n{notice_text}"
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await message.answer(
        f"✅ সফলভাবে {bn(sent)} জনের কাছে পাঠানো হয়েছে।",
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
    st   = user.get("status", "?")
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
    await message.answer("📝 আপনার সমস্যা লিখুন:")

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
    await message.answer(
        "ℹ️ নিচের মেনু থেকে অপশন বেছে নিন।",
        reply_markup=main_kb()
    )

# ═══════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════
if __name__ == '__main__':
    keep_alive()
    log.info("IncomeApp Bot starting...")
    executor.start_polling(dp, skip_updates=True)
