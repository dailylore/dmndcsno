import os
import sqlite3
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    PreCheckoutQueryHandler, MessageHandler, filters
)

# ========= CONFIG =========
TOKEN = os.environ["8575569358:AAHhNv_GgNTmxzrzd2M2QjFhgcudBJvrIQY"]
PAYMENT_TOKEN = os.environ.get("PAYMENT_TOKEN", "TEST")
PORT = int(os.environ.get("PORT", 10000))  # Railway uses random port

# ========= DATABASE (Railway persistent volume) =========
DB_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "casino.db")
if DB_PATH != "casino.db":
    DB_PATH = os.path.join(DB_PATH, "casino.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, diamonds INTEGER DEFAULT 1000, wins INTEGER DEFAULT 0, last_bonus TEXT)''')
conn.commit()

def init_user(uid):
    c.execute("INSERT OR IGNORE INTO users (id, diamonds) VALUES (?, 1000)", (uid,))
    conn.commit()

def get_diamonds(uid):
    init_user(uid)
    c.execute("SELECT diamonds FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    return row[0] if row else 1000

def add_diamonds(uid, amount):
    init_user(uid)
    c.execute("UPDATE users SET diamonds = diamonds + ? WHERE id=?", (amount, uid))
    conn.commit()

def add_win(uid):
    c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (uid,))
    conn.commit()

# ========= DAILY BONUS =========
async def daily_bonus(uid):
    today = datetime.date.today().isoformat()
    c.execute("SELECT last_bonus FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    if not row or row[0] != today:
        add_diamonds(uid, 1000)
        c.execute("UPDATE users SET last_bonus=? WHERE id=?", (today, uid))
        conn.commit()
        return "DAILY BONUS\n+1,000 Diamonds!"
    return ""

# ========= COMMANDS & GAMES (same logic, cleaned up) =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bonus = await daily_bonus(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("SLOTS", callback_data="slots"), InlineKeyboardButton("DICE", callback_data="dice")],
        [InlineKeyboardButton("BUY DIAMONDS", callback_data="buy"), InlineKeyboardButton("BALANCE", callback_data="bal")],
        [InlineKeyboardButton("LEADERBOARD", callback_data="top")]
    ])
    await update.message.reply_photo(
        photo="https://telegra.ph/file/8c9f83e3b8d2d8d6f4e1d.jpg",
        caption=f"DIAMOND CASINO\n{bonus}\nDiamonds: {get_diamonds(uid):,}",
        reply_markup=kb
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title="Buy Diamonds",
        description="100% Legal in India",
        payload="diamonds",
        provider_token=PAYMENT_TOKEN,
        currency="INR",
        prices=[LabeledPrice("5,000 Diamonds – ₹149", 14900)]
    )

async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == "bal":
        await query.edit_message_caption(f"Balance: {get_diamonds(uid):,}")
        return
    if data == "top":
        c.execute("SELECT id,wins FROM users ORDER BY wins DESC LIMIT 10")
        text = "TOP 10\n" + "\n".join([f"{i+1}. ID {row[0]} → {row[1]} wins" for i,row in enumerate(c.fetchall())])
        await query.edit_message_caption(text)
        return

    if get_diamonds(uid) < 100:
        await query.edit_message_caption("Not enough diamonds! Buy more.")
        return

    add_diamonds(uid, -100)
    win = random.random() < 0.48
    if win:
        add_diamonds(uid, 210)
        add_win(uid)
        await query.edit_message_media(
            media=InputMediaPhoto("https://telegra.ph/file/1a2b3c4d5e6f7g8h9i0j1.jpg", caption=f"YOU WON +210!\nBalance: {get_diamonds(uid):,}"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Play Again", callback_data=data)]])
        )
    else:
        await query.edit_message_caption(f"Lost!\nBalance: {get_diamonds(uid):,}")

async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    amount = update.message.successful_payment.total_amount // 100
    if amount == 149:
        add_diamonds(uid, 5000)
    await update.message.reply_text(f"Payment Success! +Diamonds\nBalance: {get_diamonds(uid):,}")

# ========= RAILWAY WEBHOOK (THIS FIXES THE ERROR) =========
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(game))
    app.add_handler(PreCheckoutQueryHandler(lambda u,c: c.pre_checkout_query.answer(ok=True)))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment))

    # This is the magic line – Railway requires webhook
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://{os.environ['RAILWAY_STATIC_URL']}.{os.environ.get('RAILWAY_ENVIRONMENT', 'railway.app')}/{TOKEN}"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
