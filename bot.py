from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8654558605:AAHYRfVvKiAPjiDEkeFTAMFvgeVoWdR9wtw"

games = {}

async def chess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    games[chat_id] = {"player1": user.id, "player1_name": user.first_name}

    keyboard = [
        [InlineKeyboardButton("🎮 انضمام للتحدي", callback_data="join")]
    ]

    await update.message.reply_text(
        f"♟️ {user.first_name} يريد يلعب شطرنج\nاضغط للانضمام 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id

    await query.answer()

    if chat_id not in games:
        await query.answer("ماكو تحدي حاليًا", show_alert=True)
        return

    game = games[chat_id]

    if game["player1"] == user.id:
        await query.answer("ما تگدر تلعب ويا نفسك", show_alert=True)
        return

    await query.edit_message_text(
        f"✅ تم قبول التحدي\n\n"
        f"اللاعب الأول: {game['player1_name']}\n"
        f"اللاعب الثاني: {user.first_name}\n\n"
        f"المرحلة الجاية نربط واجهة اللعبة."
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r"^شطرنج$"), chess))
    app.add_handler(CallbackQueryHandler(join, pattern="^join$"))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
