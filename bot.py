import sqlite3
import logging
import datetime
import asyncio
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- রেন্ডার কিপ-অ্যালাইভ সিস্টেম (Flask) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- কনফিগারেশন ---
API_TOKEN = '8432197793:AAHE3bvZYCLrVgOeJr4KNhdz0h4stcrJJow' 
ADMIN_ID = 7125681767  
PAYMENT_NUMBER = "01753850929" 
REFER_BONUS = 25  
MIN_WITHDRAW = 150 
ADMIN_USERNAME = "@luckyhera0"

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

class Form(StatesGroup):
    waiting_for_pay_num = State()   
    waiting_for_trx_id = State()    
    selecting_method = State()      
    waiting_for_withdraw_num = State() 
    waiting_for_broadcast = State() 

def bn_num(number):
    try:
        number = str(int(float(number))) 
        en_to_bn = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}
        return ''.join(en_to_bn.get(char, char) for char in number)
    except: return "০"

def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("📞 সাহায্য ও সাপোর্ট"))
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 ড্যাশবোর্ড"), KeyboardButton("👥 ইউজার লিস্ট"))
    keyboard.row(KeyboardButton("📢 আপডেট পাঠান"), KeyboardButton("📜 পেমেন্ট রিপোর্ট"))
    keyboard.row(KeyboardButton("🔙 মেইন মেনু"))
    return keyboard

def get_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, 
                      status TEXT, balance REAL, referred_by INTEGER, total_refers INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS payment_reports 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, 
                      amount REAL, method TEXT, date TEXT)''')
    conn.commit()
    return conn

@dp.message_handler(commands=['start', 'admin'], state="*")
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    
    if (message.text == "/admin" or "admin" in message.text) and user_id == ADMIN_ID:
        await message.answer("🛠 অ্যাডমিন প্যানেলে স্বাগতম!", reply_markup=admin_menu())
        return

    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        full_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "নেই"
        args = message.get_args()
        referrer_id = int(args) if args and args.isdigit() and int(args) != user_id else None
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, full_name, username, 'pending', 0.0, referrer_id, 0))
        conn.commit()
        user = (user_id, full_name, username, 'pending', 0.0, referrer_id, 0)
    conn.close()

    if user[3] == 'pending':
        welcome_text = (
            f"👋 আসসালামু আলাইকুম, {user[1]}!\n\n"
            f"আমাদের বিশ্বস্ত অনলাইন ইনকাম প্ল্যাটফর্মে স্বাগতম। ইনকাম শুরু করার পূর্বে অ্যাকাউন্টটি ভেরিফাই করুন।\n\n"
            f"📌 বিকাশ/নগদ নম্বর: {PAYMENT_NUMBER}\n"
            f"💰 অ্যাকাউন্ট ফি: ৫০ টাকা মাত্র।"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay_form"))
        # এখানে এররটি ঠিক করা হয়েছে (reply_markup একবার রাখা হয়েছে)
        await message.answer(welcome_text, reply_markup=kb)
    else:
        await message.answer(f"✅ স্বাগতম সম্মানিত গ্রাহক {user[1]}!", reply_markup=main_menu())

# --- অ্যাডমিন প্যানেল হ্যান্ডলার ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_panel_logic(message: types.Message, state: FSMContext):
    if "📊 ড্যাশবোর্ড" in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status='active' THEN 1 ELSE 0 END), SUM(balance) FROM users")
        stats = cursor.fetchone(); conn.close()
        msg = (f"📊 সিস্টেম ড্যাশবোর্ড\n━━━━━━━━━━━━━━\n"
               f"👥 মোট ইউজার: {stats[0] or 0} জন\n"
               f"✅ এক্টিভ ইউজার: {stats[1] or 0} জন\n"
               f"💸 পেন্ডিং পেআউট: {stats[2] or 0} Tk")
        await message.answer(msg)

    elif "👥 ইউজার লিস্ট" in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT full_name, user_id FROM users LIMIT 30")
        rows = cursor.fetchall(); conn.close()
        text = "👥 একটিভ ইউজার লিস্ট:\n" + "\n".join([f"• {r[0]} ({r[1]})" for r in rows])
        await message.answer(text)

    elif "📢 আপডেট পাঠান" in message.text:
        await Form.waiting_for_broadcast.set()
        await message.answer("📢 সকল ইউজারকে পাঠানোর জন্য নোটিশটি লিখুন:")

    elif "🔙 মেইন মেনু" in message.text:
        await message.answer("🏠 মেইন মেনু", reply_markup=main_menu())

    elif await state.get_state() == Form.waiting_for_broadcast.state:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users"); ids = cursor.fetchall(); conn.close()
        for i in ids:
            try: await bot.send_message(i[0], f"📢 নতুন আপডেট:\n\n{message.text}")
            except: pass
        await message.answer("✅ আপডেট পাঠানো হয়েছে।")
        await state.finish()

# --- ইউজার হ্যান্ডলার ---
@dp.message_handler(state=None)
async def user_main_handler(message: types.Message):
    user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone(); conn.close()
    if not user: return

    if user[3] == 'pending' and any(x in message.text for x in ["📊 আমার প্রোফাইল", "💸 টাকা উত্তোলন"]):
        await message.answer("⚠️ আপনার অ্যাকাউন্টটি এখনও সক্রিয় করা হয়নি। অ্যাডমিন এপ্রুভ করলে আপনি প্রোফাইল দেখতে পারবেন।")
        return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        dashboard = (f"📊 প্রোফাইল\n━━━━━━━━━━━━━━\n👤 নাম: {user[1]}\n💰 ব্যালেন্স: {bn_num(user[4])} টাকা\n👥 সফল রেফার: {bn_num(user[6])} জন\n🔗 রেফার লিংক: https://t.me/{bot_info.username}?start={user_id}")
        await message.answer(dashboard)

    elif "💸 টাকা উত্তোলন" in message.text:
        if user[4] < MIN_WITHDRAW:
            await message.answer(f"❌ কমপক্ষে {bn_num(MIN_WITHDRAW)} টাকা প্রয়োজন।")
        else:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🟠 বিকাশ", callback_data="meth_Bkash"), InlineKeyboardButton("🔴 নগদ", callback_data="meth_Nagad"))
            await Form.selecting_method.set()
            await message.answer("🏦 পেমেন্ট মেথড নির্বাচন করুন:", reply_markup=kb)

    elif "📞 সাহায্য ও সাপোর্ট" in message.text:
        await message.answer(f"📞 অ্যাডমিন আইডি: {ADMIN_USERNAME}")

# --- পেমেন্ট ও উইথড্র ফর্ম লজিক ---
@dp.callback_query_handler(text="submit_pay_form")
async def pay_start(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("📱 ধাপ-১: যে নম্বর থেকে টাকা পাঠিয়েছেন তা লিখুন:")

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(n=message.text); await Form.waiting_for_trx_id.set()
    await message.answer("🆔 ধাপ-২: TrxID লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); user_id = message.from_user.id
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    await bot.send_message(ADMIN_ID, f"🔔 ভেরিফিকেশন রিকোয়েস্ট\nID: {user_id}\nনম্বর: {data['n']}\nTrxID: {message.text}", reply_markup=admin_kb)
    await message.answer("⌛ তথ্য জমা হয়েছে। যাচাই শেষে সক্রিয় করা হবে।", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('meth_'), state=Form.selecting_method)
async def meth_sel(call: types.CallbackQuery, state: FSMContext):
    m = call.data.split('_')[1]; await state.update_data(m=m); await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text(f"✅ {m} নির্বাচন করেছেন। নম্বরটি লিখুন:")

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def withdraw_final(message: types.Message, state: FSMContext):
    d = await state.get_data(); user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (user_id,))
    u = cursor.fetchone(); conn.close()
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Paid Done", callback_data=f"clear_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    await bot.send_message(ADMIN_ID, f"💸 উইথড্র রিকোয়েস্ট\n👤 নাম: {u[0]}\nID: {user_id}\n🏦 মেথড: {d['m']}\n📱 নম্বর: {message.text}\n💰 ব্যালেন্স: {u[1]} Tk", reply_markup=admin_kb)
    await message.answer("✅ রিকোয়েস্টটি পাঠানো হয়েছে।", reply_markup=main_menu())
    await state.finish()

# --- অ্যাডমিন ডিসিশন ---
@dp.callback_query_handler(lambda c: c.data.startswith(('approve_', 'reject_', 'clear_')))
async def decision(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    act, tid = call.data.split('_'); tid = int(tid)
    conn = get_db(); cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("SELECT full_name, balance, referred_by FROM users WHERE user_id=?", (tid,))
    u = cursor.fetchone()

    if act == "approve":
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (tid,))
        if u[2]:
            cursor.execute("UPDATE users SET balance = balance + ?, total_refers = total_refers + 1 WHERE user_id=?", (REFER_BONUS, u[2]))
            try: await bot.send_message(u[2], f"🎊 রেফার বোনাস {REFER_BONUS} টাকা যুক্ত হয়েছে!")
            except: pass
        await bot.send_message(tid, "🎊 অ্যাকাউন্ট সক্রিয় হয়েছে!", reply_markup=main_menu())
        await call.message.edit_text(f"✅ আইডি {tid} এপ্রুভ করা হয়েছে।")
    
    elif act == "clear":
        cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id=?", (tid,))
        await bot.send_message(tid, "✅ পেমেন্ট পাঠানো হয়েছে।")
        await call.message.edit_text(f"💰 আইডি {tid} পেমেন্ট ক্লিয়ার।")

    elif act == "reject":
        await bot.send_message(tid, "❌ তথ্য ভুল ছিল। আবার চেষ্টা করুন।")
        await call.message.edit_text(f"❌ আইডি {tid} রিজেক্টেড।")

    conn.commit(); conn.close()

if __name__ == '__main__':
    keep_alive() 
    executor.start_polling(dp, skip_updates=True)
