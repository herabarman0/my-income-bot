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

# ---  -  (Flask) ---
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

# ---  ---
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
        en_to_bn = {'0':'', '1':'', '2':'', '3':'', '4':'', '5':'', '6':'', '7':'', '8':'', '9':''}
        return ''.join(en_to_bn.get(char, char) for char in number)
    except: return ""

def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("  "), KeyboardButton("  "))
    keyboard.row(KeyboardButton("   "))
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton(" "), KeyboardButton("  "))
    keyboard.row(KeyboardButton("  "), KeyboardButton("  "))
    keyboard.row(KeyboardButton("  "))
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
        await message.answer("   !", reply_markup=admin_menu())
        return

    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        full_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else ""
        args = message.get_args()
        referrer_id = int(args) if args and args.isdigit() and int(args) != user_id else None
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, full_name, username, 'pending', 0.0, referrer_id, 0))
        conn.commit()
        user = (user_id, full_name, username, 'pending', 0.0, referrer_id, 0)
    conn.close()

    if user[3] == 'pending':
        welcome_text = (
            f"  , {user[1]}!\n\n"
            f"               \n\n"
            f"  :\n"
            f".       Send Money \n"
            f".       TrxID  \n\n"
            f" / : {PAYMENT_NUMBER}\n"
            f"  :   "
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("  ", callback_data="submit_pay_form"))
        await message.answer(welcome_text, reply_markup=kb)
    else:
        await message.answer(f"    {user[1]}!", reply_markup=main_menu())

# ---    ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_panel_logic(message: types.Message, state: FSMContext):
    if " " in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status='active' THEN 1 ELSE 0 END), SUM(balance) FROM users")
        stats = cursor.fetchone(); conn.close()
        msg = (f"  \n\n"
               f"  : {stats[0] or 0} \n"
               f"  : {stats[1] or 0} \n"
               f"  : {(stats[1] or 0) * 50} Tk\n"
               f"  : {stats[2] or 0} Tk")
        await message.answer(msg)

    elif "  " in message.text:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT full_name, username, user_id FROM users LIMIT 30")
        rows = cursor.fetchall(); conn.close()
        text = "  \n\n\n"
        for r in rows:
            text += f" {r[0]} ({r[2]})\n"
        await message.answer(text)

    elif "  " in message.text:
        await Form.waiting_for_broadcast.set()
        await message.answer("      :")

    elif "  " in message.text:
        await message.answer("  ", reply_markup=main_menu())

    elif await state.get_state() == Form.waiting_for_broadcast.state:
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users"); ids = cursor.fetchall(); conn.close()
        for i in ids:
            try: await bot.send_message(i[0], f"  :\n\n{message.text}")
            except: pass
        await message.answer("   ")
        await state.finish()

# ---   ---
@dp.message_handler(state=None)
async def user_main_handler(message: types.Message):
    user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone(); conn.close()
    if not user: return

    if user[3] == 'pending' and any(x in message.text for x in ["  ", "  "]):
        await message.answer("     ")
        return

    if "  " in message.text:
        bot_info = await bot.get_me()
        dashboard = (f" \n : {user[1]}\n : {bn_num(user[4])} Tk\n : {bn_num(user[6])} \n : https://t.me/{bot_info.username}?start={user_id}")
        await message.answer(dashboard)

    elif "  " in message.text:
        if user[4] < MIN_WITHDRAW:
            await message.answer(f"  {bn_num(MIN_WITHDRAW)}  ")
        else:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" ", callback_data="meth_Bkash"),
                                           InlineKeyboardButton(" ", callback_data="meth_Nagad"))
            await Form.selecting_method.set()
            await message.answer("   :", reply_markup=kb)

# ---      ---
@dp.callback_query_handler(text="submit_pay_form")
async def pay_start(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("       :")

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(n=message.text); await Form.waiting_for_trx_id.set()
    await message.answer(" TrxID :")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); user_id = message.from_user.id
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" Approve", callback_data=f"approve_{user_id}"),
                                           InlineKeyboardButton(" Reject", callback_data=f"reject_{user_id}"))
    await bot.send_message(ADMIN_ID, f" \nID: {user_id}\n: {data['n']}\nTrx: {message.text}", reply_markup=admin_kb)
    await message.answer("     ", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('meth_'), state=Form.selecting_method)
async def meth_sel(call: types.CallbackQuery, state: FSMContext):
    m = call.data.split('_')[1]; await state.update_data(m=m); await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text(f" {m}  :")

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def withdraw_final(message: types.Message, state: FSMContext):
    d = await state.get_data(); user_id = message.from_user.id
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users WHERE user_id=?", (user_id,))
    u = cursor.fetchone(); conn.close()
    admin_kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" Paid", callback_data=f"clear_{user_id}"))
    await bot.send_message(ADMIN_ID, f" \nID: {user_id}\n: {d['m']}\n: {message.text}\n: {u[1]}", reply_markup=admin_kb)
    await message.answer("   ", reply_markup=main_menu())
    await state.finish()

# ---   ---
@dp.callback_query_handler(lambda c: c.data.startswith(('approve_', 'reject_', 'clear_')))
async def decision(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    act, tid = call.data.split('_'); tid = int(tid)
    conn = get_db(); cursor = conn.cursor()
    
    if act == "approve":
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (tid,))
        cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (tid,))
        res = cursor.fetchone()
        if res and res[0]:
            cursor.execute("UPDATE users SET balance = balance + ?, total_refers = total_refers + 1 WHERE user_id=?", (REFER_BONUS, res[0]))
            try: await bot.send_message(res[0], f"   {bn_num(REFER_BONUS)} Tk  !")
            except: pass
        await bot.send_message(tid, "   !", reply_markup=main_menu())
        await call.message.edit_text(f"  {tid} ")
    
    elif act == "clear":
        cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id=?", (tid,))
        await bot.send_message(tid, "   ")
        await call.message.edit_text(f"  ")

    elif act == "reject":
        await bot.send_message(tid, "   ")
        await call.message.edit_text(f" ")

    conn.commit(); conn.close()

if __name__ == '__main__':
    keep_alive() 
    executor.start_polling(dp, skip_updates=True)
