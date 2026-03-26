import sqlite3
import logging
import datetime
import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask
from threading import Thread

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

# রেন্ডারে চালানোর জন্য proxy সরিয়ে সরাসরি কানেক্ট করা হয়েছে
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# --- সংখ্যা বাংলায় রূপান্তর ---
def bn_num(number):
    try:
        number = str(int(float(number))) 
        en_to_bn = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}
        return ''.join(en_to_bn.get(char, char) for char in number)
    except:
        return "০"

# --- বাটন ডিজাইন ---
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("📞 সাহায্য ও সাপোর্ট"))
    return keyboard

# --- ডেটাবেস সেটআপ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, 
                      status TEXT, balance REAL, referred_by INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS history 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                      name TEXT, username TEXT, action TEXT, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- স্টার্ট কমান্ড ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "নেই"
    args = message.get_args()
    referrer_id = int(args) if args and args.isdigit() and int(args) != user_id else None

    user = get_user(user_id)
    if not user:
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                       (user_id, full_name, username, 'pending', 0.0, referrer_id))
        conn.commit()
        conn.close()
        user = get_user(user_id)

    if user[3] == 'pending':
        welcome_text = (
            f"👋 **আসসালামু আলাইকুম {full_name}!**\n\n"
            f"আমাদের বিশ্বস্ত রেফারাল প্রোগ্রামে স্বাগতম। ইনকাম শুরু করতে আপনার অ্যাকাউন্টটি একবারের জন্য একটিভ করে নিতে হবে।\n\n"
            f"💠 **অ্যাকাউন্ট একটিভ করার নিয়ম:**\n"
            f"১. নিচে দেওয়া নাম্বারে ৫০ টাকা **Send Money** করুন।\n"
            f"২. টাকা পাঠানোর পর আপনার **বিকাশ/নগদ নম্বর** এবং **TrxID** টি এখানে লিখে পাঠিয়ে দিন।\n\n"
            f"📌 **বিকাশ/নগদ (Personal):** `{PAYMENT_NUMBER}`\n"
            f"💰 **অ্যাকাউন্ট ফি:** ৫০ টাকা মাত্র"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_trx"))
        await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer(f"✅ স্বাগতম **{full_name}**! আপনার ড্যাশবোর্ড নিচে দেওয়া হলো।", reply_markup=main_menu())

# --- মেইন হ্যান্ডলার ---
@dp.message_handler()
async def main_handler(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user: return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        dashboard = (
            f"📊 **আপনার কাজের তথ্য**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 নাম: **{user[1]}**\n"
            f"💰 মোট ব্যালেন্স: **{bn_num(user[4])} টাকা**\n\n"
            f"🔗 **আপনার ব্যক্তিগত রেফার লিংক:**\n`{ref_link}`\n\n"
            f"💡 প্রতি সফল রেফারে পাবেন **{bn_num(REFER_BONUS)} টাকা** বোনাস!"
        )
        await message.answer(dashboard, parse_mode="Markdown")
        return

    elif "💸 টাকা উত্তোলন" in message.text:
        current_balance = float(user[4])
        if current_balance < MIN_WITHDRAW:
            needed = MIN_WITHDRAW - current_balance
            msg = (
                f"❌ **দুঃখিত বন্ধু!**\n\n"
                f"টাকা উত্তোলন করতে আপনার অ্যাকাউন্টে কমপক্ষে **{bn_num(MIN_WITHDRAW)} টাকা** থাকতে হবে।\n"
                f"আপনার লক্ষ্যে পৌঁছাতে আরও মাত্র **{bn_num(needed)} টাকা** প্রয়োজন।\n\n"
                f"📢 দয়া করে বেশি বেশি রেফার করুন!"
            )
            await message.answer(msg, parse_mode="Markdown")
        else:
            withdraw_msg = (
                f"✅ আপনার বর্তমান ব্যালেন্স: **{bn_num(current_balance)} টাকা**।\n\n"
                f"টাকা উত্তোলন করতে নিচের ফরম্যাটে তথ্য লিখে পাঠান:\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"১. মেথড: (বিকাশ/নগদ)\n"
                f"২. নম্বর: (আপনার নম্বর)\n"
                f"৩. পরিমাণ: (কত টাকা তুলতে চান)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ **উদাহরণ:** বিকাশ, 017XXXXXXXX, {int(current_balance)}"
            )
            await message.answer(withdraw_msg, parse_mode="Markdown")
        return

    elif "📞 সাহায্য ও সাপোর্ট" in message.text:
        await message.answer(f"যেকোনো প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে কথা বলুন।\n\n👨‍💻 **অ্যাডমিন আইডি:** {ADMIN_USERNAME}")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "নেই"
    admin_info = (
        f"📩 **নতুন একটি রিকোয়েস্ট এসেছে!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 নাম: {user[1]}\n"
        f"🆔 আইডি: `{user_id}`\n"
        f"🔗 ইউজার: {username}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 **ইউজারের পাঠানো তথ্য:**\n`{message.text}`"
    )

    if user[3] == 'pending':
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
        )
        await bot.send_message(ADMIN_ID, f"🔔 **অ্যাকাউন্ট একটিভেশন রিকোয়েস্ট!**\n\n{admin_info}", reply_markup=kb, parse_mode="Markdown")
        await message.answer("⌛ আপনার তথ্য আমরা পেয়েছি। খুব শীঘ্রই অ্যাডমিন এটি যাচাই করে আপনার অ্যাকাউন্টটি একটিভ করে দেবেন।")
    else:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট ডান (Record)", callback_data=f"clear_{user_id}"))
        await bot.send_message(ADMIN_ID, f"💸 **উইথড্র রিকোয়েস্ট!**\n\n{admin_info}\n💰 ব্যালেন্স: {bn_num(user[4])} টাকা", reply_markup=kb, parse_mode="Markdown")
        await message.answer("✅ আপনার রিকোয়েস্টটি অ্যাডমিনের কাছে পাঠানো হয়েছে। খুব শীঘ্রই পেমেন্ট প্রসেস করা হবে।")

# --- অ্যাডমিন অ্যাকশন ---
@dp.callback_query_handler(lambda c: c.data.startswith(('approve_', 'reject_', 'clear_')))
async def admin_decision(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    action, target_id = call.data.split('_')
    target_id = int(target_id)
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT full_name, username, balance FROM users WHERE user_id=?", (target_id,))
    u_info = cursor.fetchone()

    original_info = call.message.text.split("💬 ইউজারের পাঠানো তথ্য:")[1] if "💬 ইউজারের পাঠানো তথ্য:" in call.message.text else "তথ্য পাওয়া যায়নি"

    if action == "approve":
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (target_id,))
        cursor.execute("INSERT INTO history (user_id, name, username, action, date) VALUES (?, ?, ?, ?, ?)", 
                       (target_id, u_info[0], u_info[1], "Approved", now))
        
        cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (target_id,))
        res = cursor.fetchone()
        if res and res[0]:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (REFER_BONUS, res[0]))
            try: await bot.send_message(res[0], f"🎊 **অভিনন্দন!**\nআপনার রেফারেল লিংক থেকে একজন সফলভাবে যুক্ত হয়েছে। আপনার ব্যালেন্সে **{bn_num(REFER_BONUS)} টাকা** যোগ হয়েছে।")
            except: pass
            
        await bot.send_message(target_id, "🎊 **অভিনন্দন!**\nআপনার অ্যাকাউন্ট সচল হয়েছে। এখন আনলিমিটেড ইনকাম শুরু করুন!", reply_markup=main_menu())
        updated_text = (
            f"✅ **অ্যাকাউন্ট এপ্রুভড!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 নাম: {u_info[0]}\n"
            f"💬 পেমেন্ট তথ্য: `{original_info.strip()}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await call.message.edit_text(updated_text, parse_mode="Markdown")

    elif action == "clear":
        cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id=?", (target_id,))
        await bot.send_message(target_id, "✅ আপনার পেমেন্টটি সফলভাবে পাঠানো হয়েছে।")
        await call.message.edit_text("💰 **পেমেন্ট ক্লিয়ার করা হয়েছে!**")

    elif action == "reject":
        await bot.send_message(target_id, "❌ দুঃখিত! আপনার তথ্য সঠিক ছিল না।")
        await call.message.edit_text("❌ **রিকোয়েস্ট রিজেক্ট করা হয়েছে!**")

    conn.commit()
    conn.close()

@dp.callback_query_handler(text="submit_trx")
async def trx_prompt(call: types.CallbackQuery):
    await call.message.answer("টাকা পাঠানোর পর অনুগ্রহ করে আপনার **নম্বর** এবং **TrxID** টি এখানে লিখে পাঠিয়ে দিন।")

if __name__ == '__main__':
    keep_alive() # রেন্ডার সার্ভার চালু করবে
    executor.start_polling(dp, skip_updates=True)
