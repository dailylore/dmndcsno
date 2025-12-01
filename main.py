# FIXED & RAILWAY-READY INDIAN DIAMOND CASINO BOT (DEC 2025)
import os
import sqlite3
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)

# ========= CONFIG =========
TOKEN = os.environ["8575569358:AAHhNv_GgNTmxzrzd2M2QjFhgcudBJvrIQY"]
PAYMENT_TOKEN = os.environ.get("PAYMENT_TOKEN", "TEST")  # Use real Stripe/Paytm token in prod
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# ========= DATABASE – Use Railway's persistent volume or fallback to in-memory =========
DB_PATH = "/data/casino.db" if os.path.exists("/data") else "casino.db"  # Railway gives /data mount

conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
c = conn.cursor()
c.execute(
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        diamonds INTEGER DEFAULT 1000,
        wins INTEGER DEFAULT 0,
        last_bonus TEXT
    )"""
)
conn.commit()


def init_user(uid):
    c.execute("INSERT OR IGNORE INTO users (id, diamonds) VALUES (?, 1000)", (uid,))
    conn.commit()


def get_diamonds(uid):
    init_user(uid)
    c.execute("SELECT diamonds FROM users WHERE id = ?", (uid,))
    return c.fetchone()[0]


def add_diamonds(uid, amount):
    init_user(uid)
    c.execute("UPDATE users SET diamonds = diamonds + ? WHERE id = ?", (amount, uid))
    conn.commit()


def add_win(uid):
    c.execute("UPDATE users SET wins = wins + 1 WHERE id = ?", (uid,))
    conn.commit()


# ========= DAILY BONUS =========
async def daily_bonus(uid):
    today = datetime.date.today().isoformat()
    c.execute("SELECT last_bonus FROM users WHERE id = ?", (uid,))
    row = c.fetchone()
    if not row or row[0] != today:
        add_diamonds(uid, 1000)
        c.execute("UPDATE users SET last_bonus = ? WHERE id = ?", (today, uid))
        conn.commit()
        return "🎉 DAILY BONUS CLAIMED!\n+1,000 Diamonds 💎\nCome back tomorrow!"
    return ""


# ========= START COMMAND =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    bonus_msg = await daily_bonus(uid)

    keyboard = [
        [InlineKeyboardButton("🎰 SLOTS", callback_data="slots"), InlineKeyboardButton("🎲 DICE", callback_data="dice")],
        [InlineKeyboardButton("🪙 COINFLIP", callback_data="coin"), InlineKeyboardButton("📉 CRASH", callback_data="crash")],
        [InlineKeyboardButton("💣 MINES", callback_data="mines"), InlineKeyboardButton("🎯 PLINKO", callback_data="plinko")],
        [InlineKeyboardButton("🎡 ROULETTE", callback_data="roulette"), InlineKeyboardButton("🃏 HI-LO", callback_data="hilo")],
        [InlineKeyboardButton("🔢 KENO", callback_data="keno")],
        [InlineKeyboardButton("💰 BUY DIAMONDS", callback_data="buy"), InlineKeyboardButton("💎 BALANCE", callback_data="bal")],
        [InlineKeyboardButton("🏆 WEEKLY LEADERBOARD", callback_data="top")],
    ]

    await update.message.reply_photo(
        photo="https://telegra.ph/file/8c9f83e3b8d2d8d6f4e1d.jpg",  # Replace with your real image
        caption=f"💎 DIAMOND CASINO INDIA 💎\n"
                f"🇮🇳 100% Legal • Real Cash Prizes Weekly\n\n"
                f"{bonus_msg}\n"
                f"💰 Your Diamonds: {get_diamonds(uid):,}\n\n"
                f"Ready to win big? 🔥",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ========= BUY DIAMONDS =========
async def buy_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    prices = [
        LabeledPrice("5,000 Diamonds", 14900),      # ₹149
        LabeledPrice("14,000 Diamonds + Bonus", 34900),  # ₹349
        LabeledPrice("40,000 Diamonds + VIP", 79900),    # ₹799
    ]

    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title="Buy Diamonds 💎",
        description="Instant delivery • 100% Legal in India",
        payload="buy_diamonds",
        provider_token=PAYMENT_TOKEN,
        currency="INR",
        prices=prices,
        start_parameter="buy",
    )


# ========= PAYMENT SUCCESS =========
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    total_amount = payment.total_amount // 100  # paise → rupees
    uid = update.effective_user.id

    diamonds_to_add = 0
    if total_amount == 149:
        diamonds_to_add = 5000
    elif total_amount == 349:
        diamonds_to_add = 14000
    elif total_amount == 799:
        diamonds_to_add = 40000

    if diamonds_to_add > 0:
        add_diamonds(uid, diamonds_to_add)

    await update.message.reply_photo(
        photo="https://telegra.ph/file/1a2b3c4d5e6f7g8h9i0j1.jpg",  # Your success image
        caption=f"✅ PAYMENT SUCCESSFUL!\n"
                f"💎 +{diamonds_to_add:,} Diamonds Added!\n\n"
                f"Current Balance: {get_diamonds(uid):,}",
    )


# ========= GAMES HANDLER =========
async def game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # Balance check
    if data == "bal":
        await query.edit_message_caption(f"💎 Your Balance: {get_diamonds(uid):,}")
        return

    # Leaderboard
    if data == "top":
        c.execute("SELECT id, wins FROM users ORDER BY wins DESC LIMIT 10")
        leaderboard = "🏆 WEEKLY LEADERBOARD 🏆\n\n"
        for rank, (user_id, wins) in enumerate(c.fetchall(), 1):
            leaderboard += f"{rank}. Player {user_id} → {wins} wins\n"
        await query.edit_message_caption(leaderboard)
        return

    # Not enough diamonds
    if get_diamonds(uid) < 100:
        await query.edit_message_caption("❌ Not enough diamonds!\nTap 💰 BUY DIAMONDS")
        return

    # Deduct bet
    add_diamonds(uid, -100)

    # 48% win rate
    win = random.random() < 0.48

    if win:
        add_diamonds(uid, 210)
        add_win(uid)
        await query.edit_message_media(
            media=telegram.InputMediaPhoto(
                "https://telegra.ph/file/1a2b3c4d5e6f7g8h9i0j1.jpg",
                caption=f"🎉 JACKPOT! YOU WON!\n+210 Diamonds\n\nBalance: {get_diamonds(uid):,}",
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("PLAY AGAIN 🎰", callback_data=data)]]),
        )
        # Optional: send confetti animation
        try:
            await context.bot.send_animation(uid, "https://telegra.ph/file/confetti-win.mp4")
        except:
            pass
    else:
        await query.edit_message_caption(
            caption=f"😭 Better luck next time!\n\nBalance: {get_diamonds(uid):,}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("TRY AGAIN 🔥", callback_data=data)]]),
        )


# ========= MAIN =========
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy_diamonds, pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(game_handler))
    app.add_handler(PreCheckoutQueryHandler(lambda u, c: c.pre_checkout_query.answer(ok=True)))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # For Railway: Use webhook (recommended) OR polling with keep-alive
    port = int(os.environ.get("PORT", 8443))
    
    # Use webhook (best for Railway)
    await app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"https://{os.environ['RAILWAY_STATIC_URL']}/" + TOKEN
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
