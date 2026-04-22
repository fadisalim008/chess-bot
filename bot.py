from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8654558605:AAHYRfVvKiAPjiDEkeFTAMFvgeVoWdR9wtw"
CHANNEL = "@fadifva"

games = {}  # تخزين التحديات


async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# بدء التحدي بكلمة "شطرنج"
async def chess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # تحقق الاشتراك
    if not await is_subscribed(context.bot, user.id):
        btn = [[InlineKeyboardButton("اشترك بالقناة", url=f"https://t.me/{CHANNEL.replace('@','')}")]]
        await update.message.reply_text("❌ لازم تشترك بالقناة أول", reply_markup=InlineKeyboardMarkup(btn))
        return

    games[chat_id] = {"player1": user.id, "player2": None}

    keyboard = [
        [InlineKeyboardButton("🎮 انضمام للتحدي", callback_data="join")]
    ]

    await update.message.reply_text(
        f"♟️ {user.first_name} يريد يلعب شطرنج\nاضغط للانضمام 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# زر الانضمام
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id

    await query.answer()

    if chat_id not in games:
        return

    game = games[chat_id]

    if game["player1"] == user.id:
        await query.answer("❌ ما تگدر تلعب ويا نفسك", show_alert=True)
        return

    # تحقق الاشتراك
    if not await is_subscribed(context.bot, user.id):
        await query.answer("❌ اشترك بالقناة أول", show_alert=True)
        return

    game["player2"] = user.id

    keyboard = [
        [InlineKeyboardButton("▶️ فتح اللعبة", url="https://your-site-url")]
    ]

    await query.edit_message_text(
        "✅ تم بدء اللعبة!\nاضغط لفتح الشطرنج 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # أمر "شطرنج"
    app.add_handler(MessageHandler(filters.Regex(r"^شطرنج$"), chess))

    # زر الانضمام
    app.add_handler(CallbackQueryHandler(join, pattern="join"))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
