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
    # রেন্ডার অটোমেটিক পোর্ট সেট করে দেয়
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
# রেন্ডারের জন্য প্রক্সি প্রয়োজন নেই, তাই সরাসরি কানেক্ট করা হলো
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
        await message.answer("🛠 অ্যাডমিন প্যানেলে স্বাগতম!\nনিচের বাটন থেকে সিস্টেম নিয়ন্ত্রণ করুন।", reply_markup=admin_menu())
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
            f"আমাদের বিশ্বস্ত অনলাইন ইনকাম প্ল্যাটফর্মে আপনাকে স্বাগতম। ইনকাম শুরু করার পূর্বে আপনার অ্যাকাউন্টটি ভেরিফাই করা প্রয়োজন।\n\n"
            f"💠 ভেরিফিকেশন নিয়মাবলী:\n"
            f"১. নিচে দেওয়া ব্যক্তিগত নম্বরে ৫০ টাকা Send Money করুন।\n"
            f"২. টাকা পাঠানোর পর আপনার নম্বর ও TrxID প্রদান করুন।\n\n"
            f"📌 বিকাশ/নগদ নম্বর: {PAYMENT_NUMBER}\n"
            f"💰 অ্যাকাউন্ট ফি: ৫০ টাকা মাত্র।\n\n"
            f"টাকা পাঠানো সম্পন্ন হলে নিচের বাটনে ক্লিক করুন।"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay_form"))
        await message.answer(welcome_text, reply_markup=kb)
    else:
        await message.answer(f"✅ স্বাগতম সম্মানিত গ্রাহক {user[1]}!\nআপনার ড্যাশবোর্ড সক্রিয় আছে।", reply_markup=main_menu())

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
               f"💰 মোট ইনভেস্ট: {(stats[1] or 0) * 50} Tk\n"
               f"💸 পেন্ডিং পেআউট: {stats[2] or 0} Tk")
        await message.answer(stats_msg) # এখানে মূল কোডে কিছুটা মিসিং ছিল, ঠিক করে দিলাম

    elif "👥 ইউজার লিস্ট" in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT full_name, username, user_id FROM users LIMIT 30")
        rows = cursor.fetchall(); conn.close()
        text = "👥 একটিভ ইউজার লিস্ট\n━━━━━━━━━━━━━━\n\n"
        for r in rows:
            text += f"👤 নাম: {r[0]}\n🔗 ইউজারনেম: {r[1]}\n🆔 আইডি: {r[2]}\n──────────────\n"
        await message.answer(text)

    elif "📜 পেমেন্ট রিপোর্ট" in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT name, amount, method, date FROM payment_reports ORDER BY id DESC LIMIT 15")
        reports = cursor.fetchall(); conn.close()
        if not reports:
            await message.answer("📭 কোনো পেমেন্ট রেকর্ড নেই।")
            return
        rep_text = "📜 পেমেন্ট সাকসেস রিপোর্ট\n━━━━━━━━━━━━━━\n\n"
        for r in reports:
            rep_text += f"👤 {r[0]}\n💰 এমাউন্ট: {r[1]} Tk\n🏦 মেথড: {r[2]}\n⏰ তারিখ: {r[3]}\n──────────────\n"
        await message.answer(rep_text)

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

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        dashboard = (f"📊 আপনার প্রোফাইল\n━━━━━━━━━━━━━━\n"
                     f"👤 নাম: {user[1]}\n"
                     f"💰 বর্তমান ব্যালেন্স: {bn_num(user[4])} টাকা\n"
                     f"👥 মোট সফল রেফার: {bn_num(user[6])} জন\n"
                     f"🆔 ইউজার আইডি: {user_id}\n\n"
                     f"🔗 রেফার লিংক: https://t.me/{bot_info.username}?start={user_id}")
        await message.answer(dashboard)

    elif "💸 টাকা উত্তোলন" in message.text:
        if user[4] < MIN_WITHDRAW:
            await message.answer(f"❌ দুঃখিত! আপনার ব্যালেন্স পর্যাপ্ত নয়।\nউত্তোলন করতে কমপক্ষে {bn_num(MIN_WITHDRAW)} টাকা প্রয়োজন।")
        else:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🟠 বিকাশ", callback_data="meth_Bkash"),
                                           InlineKeyboardButton("🔴 নগদ", callback_data="meth_Nagad"))
            await Form.selecting_method.set()
            await message.answer("🏦 পেমেন্ট মেথড নির্বাচন করুন\n━━━━━━━━━━━━━━\nআপনি কোন মাধ্যমে টাকা উত্তোলন করতে চান?", reply_markup=kb)

    elif "📞 সাহায্য ও সাপোর্ট" in message.text:
        await message.answer(f"📞 কাস্টমার সাপোর্ট টিম\n━━━━━━━━━━━━━━\nঅ্যাডমিন আইডি: {ADMIN_USERNAME}\nসময়: ২৪/৭ অনলাইন সাপোর্ট")

# --- পেমেন্ট ও উইথড্র ফর্ম লজিক ---
@dp.callback_query_handler(text="submit_pay_form")
async def pay_start(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("📱 ধাপ-১:\nযে নম্বর থেকে টাকা পাঠিয়েছেন তা লিখুন:")

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(n=message.text); await Form.waiting_for_trx_id.set()
    await message.answer("🆔 ধাপ-২:\nআপনার পেমেন্টের ট্রানজেকশন আইডি (TrxID) লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); user_id = message.from_user.id
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
                                           InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    await bot.send_message(ADMIN_ID, f"🔔 ভেরিফিকেশন রিকোয়েস্ট\n━━━━━━━━━━━━━━\nID: {user_id}\nপ্রেরক নম্বর: {data['n']}\nTrxID: {message.text}", reply_markup=admin_kb)
    await message.answer("⌛ তথ্য জমা হয়েছে। যাচাই শেষে সক্রিয় করা হবে।", reply_markup=main_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('meth_'), state=Form.selecting_method)
async def meth_sel(call: types.CallbackQuery, state: FSMContext):
    m = call.data.split('_')[1]; await state.update_data(m=m); await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text(f"✅ আপনি {m} নির্বাচন করেছেন। এখন আপনার নম্বরটি লিখুন:")

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def withdraw_final(message: types.Message, state: FSMContext):
    d = await state.get_data(); user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (user_id,))
    u = cursor.fetchone(); conn.close()
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Paid Done", callback_data=f"clear_{user_id}"),
                                           InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    msg = (f"💸 উইথড্র রিকোয়েস্ট\n━━━━━━━━━━━━━━\n👤 নাম: {u[0]}\n🆔 আইডি: {user_id}\n🏦 মেথড: {d['m']}\n📱 নম্বর: {message.text}\n💰 ব্যালেন্স: {u[1]} Tk")
    await bot.send_message(ADMIN_ID, msg, reply_markup=admin_kb)
    await message.answer("✅ আপনার রিকোয়েস্টটি পাঠানো হয়েছে।", reply_markup=main_menu())
    await state.finish()

# --- অ্যাডমিন ডিসিশন ও রিপোর্ট ---
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
        await bot.send_message(tid, "🎊 অভিনন্দন! অ্যাকাউন্ট সক্রিয় হয়েছে।", reply_markup=main_menu())
        await call.message.edit_text(f"✅ অ্যাকাউন্ট এপ্রুভড\n━━━━━━━━━━━━━━\n👤 নাম: {u[0]}\n🆔 আইডি: {tid}\n⏰ সময়: {now}")
    
    elif act == "clear":
        info = call.message.text
        method_part = info.split("🏦 মেথড:")[1].split("\n")[0].strip() if "🏦 মেথড:" in info else "Withdraw"
        
        cursor.execute("INSERT INTO payment_reports (user_id, name, amount, method, date) VALUES (?,?,?,?,?)",
                       (tid, u[0], u[1], method_part, now))
        cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id=?", (tid,))
        await bot.send_message(tid, "✅ পেমেন্ট সফলভাবে পাঠানো হয়েছে।")
        await call.message.edit_text(f"💰 পেমেন্ট ক্লিয়ার\n━━━━━━━━━━━━━━\n👤 নাম: {u[0]}\n💵 পরিমাণ: {u[1]} Tk\n🏦 মেথড: {method_part}\n⏰ সময়: {now}")

    elif act == "reject":
        await bot.send_message(tid, "❌ তথ্য ভুল থাকায় বাতিল করা হয়েছে।")
        await call.message.edit_text(f"❌ রিকোয়েস্ট রিজেক্টেড\n━━━━━━━━━━━━━━\n🆔 আইডি: {tid}\n⏰ সময়: {now}")

    conn.commit(); conn.close()

if __name__ == '__main__':
    keep_alive() # রেন্ডারের জন্য সার্ভার চালু করবে
    executor.start_polling(dp, skip_updates=True)
