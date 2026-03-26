# -*- coding: utf-8 -*-
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

# --- Render Server Keep-Alive ---
app = Flask('')
@app.route('/')
def home(): return "Server is Running..."

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
    waiting_for_private_msg_id = State()
    waiting_for_private_msg_text = State()

def bn_num(number):
    try:
        number = str(int(float(number))) 
        en_to_bn = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}
        return ''.join(en_to_bn.get(char, char) for char in number)
    except: return "০"

# --- ডাটাবেস ফাংশন ---
def get_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, 
                      status TEXT, balance REAL, referred_by INTEGER, points INTEGER DEFAULT 0, 
                      last_bonus TEXT, date TEXT, total_earned REAL DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reports 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, 
                      amount REAL, method TEXT, number TEXT, date TEXT)''')
    conn.commit()
    return conn

# --- কিবোর্ড ডিজাইন ---
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("ℹ️ ইনকাম তথ্য"))
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("🎁 ডেইলি বোনাস"), KeyboardButton("📞 কাস্টমার সাপোর্ট"))
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 সিস্টেম ড্যাশবোর্ড"), KeyboardButton("👥 ইউজার লিস্ট"))
    keyboard.row(KeyboardButton("📢 আপডেট পাঠান"), KeyboardButton("✉️ একক মেসেজ"))
    keyboard.row(KeyboardButton("📜 পেমেন্ট রিপোর্ট"))
    return keyboard

# --- স্টার্ট কমান্ড ---
@dp.message_handler(commands=['start', 'admin'], state="*")
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    if message.text == "/admin" and user_id == ADMIN_ID:
        await message.answer("🛠 অ্যাডমিন কন্ট্রোল প্যানেল\nসিস্টেম পরিচালনা করতে নিচের অপশনগুলো ব্যবহার করুন।", reply_markup=admin_menu())
        return

    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        full_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "নেই"
        args = message.get_args()
        referrer_id = int(args) if args and args.isdigit() and int(args) != user_id else None
        now = datetime.datetime.now().strftime("%d-%m-%Y")
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, full_name, username, 'pending', 0.0, referrer_id, 0, "0", now, 0.0))
        conn.commit()
        user = (user_id, full_name, username, 'pending', 0.0, referrer_id, 0, "0", now, 0.0)
    conn.close()

    if user[3] == 'pending':
        welcome_text = (
            f"👋 আসসালামু আলাইকুম, {user[1]}\n\n"
            f"আমাদের বিশ্বস্ত ইনকাম প্ল্যাটফর্মে আপনাকে স্বাগতম। এখানে প্রতি সফল রেফারে আপনি পাবেন ১৫০ পয়েন্ট বোনাস।\n\n"
            f"💰 রেফারেল ইনকাম লেভেল প্রতি রেফারে:\n"
            f"১. প্রাথমিক লেভেল ০-২৯৯৯ পয়েন্টে : ২৫ টাকা\n"
            f"২. ৩০০০ পয়েন্ট হলে: ৩০ টাকা\n"
            f"৩. ৫০০০ পয়েন্ট হলে: ৩৫ টাকা\n\n"
            f"💠 অ্যাকাউন্ট ভেরিফিকেশন নিয়ম:\n"
            f"১. নিচে দেওয়া নম্বরে ৫০ টাকা Send Money করুন।\n\n"
            f"📌 বিকাশ/নগদ: {PAYMENT_NUMBER}\n\n"
            f"টাকা পাঠানো শেষ হলে নিচের বাটনে ক্লিক করুন।"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay"))
        await message.answer(welcome_text, reply_markup=kb)
    else:
        await message.answer(f"✅ স্বাগতম সম্মানিত সদস্য {user[1]}!\nআপনার ড্যাশবোর্ড সক্রিয় আছে।", reply_markup=main_menu())

# --- ইউজার প্যানেল লজিক ---
@dp.message_handler(state=None)
async def user_panel(message: types.Message):
    user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone(); conn.close()
    if not user: return

    if user[3] == 'pending' and message.text != "ℹ️ ইনকাম তথ্য":
        await message.answer("⚠️ আপনার অ্যাকাউন্টটি এখনও সক্রিয় করা হয়নি। অ্যাডমিন এপ্রুভ করলে ড্যাশবোর্ড সচল হবে।")
        return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        dashboard = (f"📊 আপনার প্রোফাইল কার্ড\n━━━━━━━━━━━━━━\n"
                     f"👤 নাম: {user[1]}\n🆔 আইডি: {user_id}\n🎯 অর্জিত পয়েন্ট: {bn_num(user[6])}\n"
                     f"💰 বর্তমান ব্যালেন্স: {bn_num(user[4])} টাকা\n💰 সর্বমোট ইনকাম: {bn_num(user[9])} টাকা\n📅 যোগদানের তারিখ: {user[8]}\n\n"
                     f"🔗 রেফার লিংক:\nhttps://t.me/{bot_info.username}?start={user_id}")
        await message.answer(dashboard)

    elif "🎁 ডেইলি বোনাস" in message.text:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        if user[7] == today:
            await message.answer("❌ দুঃখিত! আপনি আজকে অলরেডি বোনাস নিয়েছেন। আগামীকাল আবার চেষ্টা করুন।")
        else:
            conn = get_db(); cursor = conn.cursor()
            # লজিক: প্রথম ৭ দিন টাকা, পরে পয়েন্ট ও টাকার অল্টারনেট
            join_date = datetime.datetime.strptime(user[8], "%d-%m-%Y")
            days_active = (datetime.datetime.now() - join_date).days
            
            if days_active <= 7:
                bonus_val = 1.0
                cursor.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, last_bonus = ? WHERE user_id = ?", (bonus_val, bonus_val, today, user_id))
                await message.answer(f"✅ অভিনন্দন! আপনি ডেইলি বোনাস হিসেবে ১ টাকা পেয়েছেন।")
            else:
                if days_active % 2 == 0:
                    cursor.execute("UPDATE users SET points = points + 10, last_bonus = ? WHERE user_id = ?", (today, user_id))
                    await message.answer(f"✅ অভিনন্দন! আপনি ডেইলি বোনাস হিসেবে ১০ পয়েন্ট পেয়েছেন।")
                else:
                    cursor.execute("UPDATE users SET balance = balance + 0.5, total_earned = total_earned + 0.5, last_bonus = ? WHERE user_id = ?", (today, user_id))
                    await message.answer(f"✅ অভিনন্দন! আপনি ডেইলি বোনাস হিসেবে ০.৫ টাকা পেয়েছেন।")
            conn.commit(); conn.close()

    elif "💸 টাকা উত্তোলন" in message.text:
        if user[4] < MIN_WITHDRAW:
            await message.answer(f"❌ দুঃখিত!\n\nটাকা উত্তোলন করতে আপনার ব্যালেন্স কমপক্ষে ১৫০ টাকা হতে হবে। আপনার লক্ষ্য পূরণে আরও রেফার করুন এবং ইনকাম বৃদ্ধি করুন।")
        else:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🟠 বিকাশ", callback_data="w_Bkash"), InlineKeyboardButton("🔴 নগদ", callback_data="w_Nagad"))
            await Form.selecting_method.set()
            await message.answer("🏦 পেমেন্ট মেথড নির্বাচন করুন:\nআপনি কোন মাধ্যমে টাকা নিতে চান?", reply_markup=kb)

    elif "ℹ️ ইনকাম তথ্য" in message.text:
        info = (
            "ℹ️ ইনকাম গাইডলাইন\n━━━━━━━━━━━━━━\n\n"
            "১. রেফার ইনকাম: আপনার রেফার লিংকের মাধ্যমে কাউকে জয়েন করালে ১৫০ পয়েন্ট পাবেন।\n"
            "২. ইনকাম লেভেল: পয়েন্ট যত বাড়বে, প্রতি রেফারে টাকার পরিমাণ তত বাড়বে (২৫ থেকে ৩৫ টাকা)।\n"
            "৩. ডেইলি বোনাস: প্রতিদিন বটে লগইন করে বোনাস সংগ্রহ করুন।\n"
            "৪. পেমেন্ট: ১৫০ টাকা হলেই সরাসরি বিকাশ বা নগদে উইথড্র করতে পারবেন।"
        )
        await message.answer(info)

    elif "📞 কাস্টমার সাপোর্ট" in message.text:
        await message.answer(f"📞 হেল্পলাইন\n━━━━━━━━━━━━━━\nযেকোনো প্রয়োজনে সরাসরি অ্যাডমিনের সাথে যোগাযোগ করুন।\n\n👨‍💻 অ্যাডমিন আইডি: {ADMIN_USERNAME}")

# --- অ্যাডমিন হ্যান্ডলার ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_logic(message: types.Message, state: FSMContext):
    conn = get_db(); cursor = conn.cursor()
    if "📊 সিস্টেম ড্যাশবোর্ড" in message.text:
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status='active' THEN 1 ELSE 0 END), SUM(balance) FROM users")
        stats = cursor.fetchone()
        msg = (f"📊 সিস্টেম ড্যাশবোর্ড\n━━━━━━━━━━━━━━\n"
               f"👥 মোট ইউজার: {stats[0] or 0} জন\n✅ এক্টিভ ইউজার: {stats[1] or 0} জন\n"
               f"💰 মোট ইনভেস্ট: {(stats[1] or 0) * 50} টাকা\n💸 পেন্ডিং পেআউট: {stats[2] or 0} টাকা")
        await message.answer(msg)

    elif "👥 ইউজার লিস্ট" in message.text:
        cursor.execute("SELECT full_name, user_id, points, balance FROM users LIMIT 15")
        rows = cursor.fetchall()
        text = "👥 ইউজার ইনফরমেশন\n━━━━━━━━━━━━━━\n\n"
        for r in rows:
            text += f"👤 নাম: {r[0]}\n🆔 আইডি: {r[1]}\n🎯 পয়েন্ট: {r[2]} | 💰 ব্যালেন্স: {r[3]}\n──────────────\n"
        await message.answer(text)

    elif "📜 পেমেন্ট রিপোর্ট" in message.text:
        cursor.execute("SELECT name, amount, method, number, date FROM reports ORDER BY id DESC LIMIT 10")
        reports = cursor.fetchall()
        text = "📜 পেমেন্ট রিপোর্ট\n━━━━━━━━━━━━━━\n\n"
        for r in reports:
            text += f"👤 {r[0]} | 💰 {r[1]} টাকা\n🏦 {r[2]} | 📱 {r[3]}\n⏰ {r[4]}\n──────────────\n"
        await message.answer(text)

    elif "📢 আপডেট পাঠান" in message.text:
        await Form.waiting_for_broadcast.set()
        await message.answer("📢 সকল মেম্বারকে পাঠানোর জন্য নোটিশটি লিখুন:")

    elif "✉️ একক মেসেজ" in message.text:
        await Form.waiting_for_private_msg_id.set()
        await message.answer("🆔 মেম্বার আইডিটি প্রদান করুন:")
    conn.close()

# --- কলব্যাক এবং ফর্ম লজিক ---
@dp.callback_query_handler(lambda c: c.data.startswith(('approve_', 'reject_', 'clear_', 'w_', 'submit_pay')), state="*")
async def callbacks(call: types.CallbackQuery, state: FSMContext):
    act_data = call.data.split('_')
    act = act_data[0]; tid = int(act_data[1]) if len(act_data) > 1 else 0
    conn = get_db(); cursor = conn.cursor()

    if act == "submit_pay":
        await Form.waiting_for_pay_num.set()
        await call.message.answer("📱 ধাপ-১: যে নম্বর থেকে টাকা পাঠিয়েছেন তা লিখুন:")

    elif act == "approve":
        cursor.execute("SELECT full_name, referred_by FROM users WHERE user_id=?", (tid,))
        u = cursor.fetchone()
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (tid,))
        if u[1]:
            cursor.execute("SELECT points FROM users WHERE user_id=?", (u[1],))
            ref_points = cursor.fetchone()[0]
            bonus = 25.0
            if ref_points >= 5000: bonus = 35.0
            elif ref_points >= 3000: bonus = 30.0
            cursor.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, points = points + 150 WHERE user_id=?", (bonus, bonus, u[1]))
            try: await bot.send_message(u[1], f"🎊 অভিনন্দন! আপনার রেফারে একজন নতুন সদস্য যুক্ত হয়েছে। আপনি {bn_num(bonus)} টাকা বোনাস পেয়েছেন।")
            except: pass
        await bot.send_message(tid, f"✅ অভিনন্দন {u[0]}!\nআপনার অ্যাকাউন্টটি সফলভাবে সক্রিয় করা হয়েছে। এখন আপনি কাজ শুরু করতে পারেন।", reply_markup=main_menu())
        await call.message.edit_text(f"✅ আইডি {tid} এপ্রুভ করা হয়েছে।")

    elif act == "reject":
        await bot.send_message(tid, "❌ দুঃখিত! আপনার পেমেন্ট তথ্য সঠিক ছিল না। অনুগ্রহ করে সঠিক তথ্য দিয়ে আবার চেষ্টা করুন।")
        await call.message.edit_text(f"❌ আইডি {tid} বাতিল করা হয়েছে।")

    elif act == "clear":
        # এখানে উইথড্র তথ্য সেভ করার লজিক
        cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (tid,))
        u_info = cursor.fetchone()
        now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
        # মেথড এবং নম্বর মেসেজ থেকে নেওয়া (সিম্পল ডেমো)
        cursor.execute("INSERT INTO reports (user_id, name, amount, method, number, date) VALUES (?, ?, ?, ?, ?, ?)", 
                       (tid, u_info[0], u_info[1], "Withdraw", "N/A", now))
        cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id=?", (tid,))
        await bot.send_message(tid, "✅ আপনার পেমেন্ট রিকোয়েস্টটি সফলভাবে সম্পন্ন হয়েছে। টাকা আপনার অ্যাকাউন্টে পাঠিয়ে দেওয়া হয়েছে।")
        await call.message.edit_text(f"💰 আইডি {tid} পেমেন্ট ক্লিয়ার করা হয়েছে।")

    elif act == "w":
        method = act_data[1]
        await state.update_data(m=method); await Form.waiting_for_withdraw_num.set()
        await call.message.edit_text(f"✅ আপনি {method} নির্বাচন করেছেন। আপনার নম্বরটি প্রদান করুন:")

    conn.commit(); conn.close()

# --- স্টেট হ্যান্ডলার ---
@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(n=message.text); await Form.waiting_for_trx_id.set()
    await message.answer("🆔 ধাপ-২: আপনার পেমেন্টের ট্রানজেকশন আইডি (TrxID) লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    d = await state.get_data(); uid = message.from_user.id
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    await bot.send_message(ADMIN_ID, f"🔔 নতুন ভেরিফিকেশন আবেদন\n🆔 আইডি: {uid}\n📱 নম্বর: {d['n']}\n🆔 TrxID: {message.text}", reply_markup=kb)
    await message.answer("⌛ তথ্য জমা হয়েছে। অ্যাডমিন যাচাই শেষে আপনার অ্যাকাউন্টটি সক্রিয় করে দেবেন।")
    await state.finish()

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def withdraw_final(message: types.Message, state: FSMContext):
    d = await state.get_data(); uid = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (uid,))
    u = cursor.fetchone(); conn.close()
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট সম্পন্ন", callback_data=f"clear_{uid}"), InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"reject_{uid}"))
    await bot.send_message(ADMIN_ID, f"💸 উইথড্র রিকোয়েস্ট\n👤 নাম: {u[0]}\n🆔 আইডি: {uid}\n🏦 মেথড: {d['m']}\n📱 নম্বর: {message.text}\n💰 টাকা: {u[1]}", reply_markup=kb)
    await message.answer("✅ আপনার রিকোয়েস্টটি পাঠানো হয়েছে। অ্যাডমিন খুব শীঘ্রই পেমেন্ট সম্পন্ন করবেন।", reply_markup=main_menu())
    await state.finish()

# --- ব্রডকাস্টিং এবং প্রাইভেট মেসেজ ---
@dp.message_handler(state=Form.waiting_for_broadcast)
async def broadcast_send(message: types.Message, state: FSMContext):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users"); ids = cursor.fetchall(); conn.close()
    for i in ids:
        try: await bot.send_message(i[0], f"📢 নতুন নোটিশ:\n\n{message.text}")
        except: pass
    await message.answer("✅ নোটিশটি সবার কাছে পাঠানো হয়েছে।")
    await state.finish()

@dp.message_handler(state=Form.waiting_for_private_msg_id)
async def p_msg_id(message: types.Message, state: FSMContext):
    await state.update_data(pid=message.text); await Form.waiting_for_private_msg_text.set()
    await message.answer("💬 মেসেজটি লিখুন:")

@dp.message_handler(state=Form.waiting_for_private_msg_text)
async def p_msg_send(message: types.Message, state: FSMContext):
    d = await state.get_data()
    try:
        await bot.send_message(d['pid'], f"✉️ অ্যাডমিন থেকে মেসেজ:\n\n{message.text}")
        await message.answer("✅ মেসেজটি পাঠানো হয়েছে।")
    except: await message.answer("❌ ইউজার পাওয়া যায়নি।")
    await state.finish()

if __name__ == '__main__':
    keep_alive() 
    executor.start_polling(dp, skip_updates=True)
