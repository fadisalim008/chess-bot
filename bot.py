import logging
import os
import random
import sqlite3
from contextlib import closing

import chess
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# الإعدادات
# =========================
BOT_TOKEN = "8654558605:AAHYRfVvKiAPjiDEkeFTAMFvgeVoWdR9wtw"
REQUIRED_CHANNEL = "@fadigva"  # مثال: @fadifva

DB_NAME = "chess_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================
# قاعدة البيانات
# =========================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            status TEXT NOT NULL, -- waiting, active, finished
            challenger_id INTEGER NOT NULL,
            challenger_name TEXT NOT NULL,
            opponent_id INTEGER,
            opponent_name TEXT,
            white_id INTEGER,
            black_id INTEGER,
            turn_id INTEGER,
            fen TEXT,
            message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS players_stats (
            user_id INTEGER PRIMARY KEY,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0
        )
        """)

        conn.commit()


def get_conn():
    return sqlite3.connect(DB_NAME)


def ensure_player_stats(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO players_stats (user_id) VALUES (?)", (user_id,))
        conn.commit()


def add_win(user_id: int):
    ensure_player_stats(user_id)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE players_stats SET wins = wins + 1 WHERE user_id = ?", (user_id,))
        conn.commit()


def add_loss(user_id: int):
    ensure_player_stats(user_id)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE players_stats SET losses = losses + 1 WHERE user_id = ?", (user_id,))
        conn.commit()


def add_draw(user_id: int):
    ensure_player_stats(user_id)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE players_stats SET draws = draws + 1 WHERE user_id = ?", (user_id,))
        conn.commit()


def get_stats(user_id: int):
    ensure_player_stats(user_id)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT wins, losses, draws FROM players_stats WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row if row else (0, 0, 0)


def get_waiting_or_active_game_by_user(group_id: int, user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM games
            WHERE group_id = ?
            AND status IN ('waiting', 'active')
            AND (
                challenger_id = ?
                OR opponent_id = ?
                OR white_id = ?
                OR black_id = ?
            )
            ORDER BY id DESC
            LIMIT 1
        """, (group_id, user_id, user_id, user_id, user_id))
        return c.fetchone()


def get_waiting_game(group_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM games
            WHERE group_id = ? AND status = 'waiting'
            ORDER BY id DESC
            LIMIT 1
        """, (group_id,))
        return c.fetchone()


def get_active_game_by_group(group_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM games
            WHERE group_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """, (group_id,))
        return c.fetchone()


def create_waiting_game(group_id: int, challenger_id: int, challenger_name: str, message_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO games (
                group_id, status, challenger_id, challenger_name, message_id
            ) VALUES (?, 'waiting', ?, ?, ?)
        """, (group_id, challenger_id, challenger_name, message_id))
        conn.commit()
        return c.lastrowid


def activate_game(game_id: int, opponent_id: int, opponent_name: str, white_id: int, black_id: int, turn_id: int, fen: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE games
            SET status = 'active',
                opponent_id = ?,
                opponent_name = ?,
                white_id = ?,
                black_id = ?,
                turn_id = ?,
                fen = ?
            WHERE id = ?
        """, (opponent_id, opponent_name, white_id, black_id, turn_id, fen, game_id))
        conn.commit()


def update_game_state(game_id: int, fen: str, turn_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE games
            SET fen = ?, turn_id = ?
            WHERE id = ?
        """, (fen, turn_id, game_id))
        conn.commit()


def finish_game(game_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE games SET status = 'finished' WHERE id = ?", (game_id,))
        conn.commit()


def cancel_waiting_game(game_id: int):
    finish_game(game_id)


# =========================
# أدوات
# =========================
ARABIC_PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
    ".": "·"
}


def get_display_name(user):
    return user.full_name if user.full_name else user.first_name


def board_to_text(board: chess.Board) -> str:
    rows = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece:
                row.append(ARABIC_PIECES[piece.symbol()])
            else:
                row.append(ARABIC_PIECES["."])
        rows.append(f"{rank+1} " + " ".join(row))
    rows.append("  a b c d e f g h")
    return "\n".join(rows)


def result_text(board: chess.Board):
    if board.is_checkmate():
        winner = "الأبيض" if board.turn == chess.BLACK else "الأسود"
        return f"كش مات. الفائز: {winner}"
    if board.is_stalemate():
        return "تعادل بسبب Stalemate"
    if board.is_insufficient_material():
        return "تعادل بسبب عدم كفاية القطع"
    if board.can_claim_threefold_repetition():
        return "تعادل بسبب تكرار النقلات"
    if board.can_claim_fifty_moves():
        return "تعادل بسبب قاعدة 50 نقلة"
    return None


async def is_subscribed(bot, user_id: int) -> bool:
    """
    لازم البوت يكون مضاف للقناة، والأفضل مشرف حتى يفحص العضوية بدون مشاكل.
    """
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"Subscription check failed: {e}")
        return False


async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    ok = await is_subscribed(context.bot, user_id)
    if not ok:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك بالقناة", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")]
        ])
        text = (
            "لازم تشترك بالقناة أول حتى تگدر تلعب.\n"
            f"القناة المطلوبة: {REQUIRED_CHANNEL}"
        )

        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.answer("لازم تشترك بالقناة أول", show_alert=True)
        return False
    return True


def game_status_text(challenger_name, white_name, black_name, current_turn_name, board: chess.Board) -> str:
    turn_color = "الأبيض" if board.turn == chess.WHITE else "الأسود"
    check_text = "\n⚠️ كش" if board.is_check() else ""
    return (
        f"♟️ لعبة شطرنج\n\n"
        f"المنشئ: {challenger_name}\n"
        f"الأبيض: {white_name}\n"
        f"الأسود: {black_name}\n"
        f"الدور: {current_turn_name} ({turn_color}){check_text}\n\n"
        f"<pre>{board_to_text(board)}</pre>\n\n"
        f"أرسل النقلة بهذا الشكل:\n"
        f"<code>e2e4</code>\n"
        f"وللاستسلام اكتب:\n"
        f"<code>استسلام</code>"
    )


def parse_move_from_text(text: str):
    text = text.strip().lower().replace(" ", "")
    if len(text) < 4:
        return None
    # مثال e2e4 أو e7e8q
    try:
        return chess.Move.from_uci(text)
    except Exception:
        return None


async def edit_or_send_game_message(context, group_id: int, message_id: int | None, text: str):
    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=group_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML"
            )
            return message_id
        except Exception:
            pass

    msg = await context.bot.send_message(
        chat_id=group_id,
        text=text,
        parse_mode="HTML"
    )
    return msg.message_id


def get_names_from_game_row(row):
    """
    ترتيب الأعمدة:
    0 id
    1 group_id
    2 status
    3 challenger_id
    4 challenger_name
    5 opponent_id
    6 opponent_name
    7 white_id
    8 black_id
    9 turn_id
    10 fen
    11 message_id
    12 created_at
    """
    return {
        "id": row[0],
        "group_id": row[1],
        "status": row[2],
        "challenger_id": row[3],
        "challenger_name": row[4],
        "opponent_id": row[5],
        "opponent_name": row[6],
        "white_id": row[7],
        "black_id": row[8],
        "turn_id": row[9],
        "fen": row[10],
        "message_id": row[11],
    }


# =========================
# الأوامر
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "أهلًا بيك ببوت الشطرنج ♟️\n\n"
        "داخل الكروب:\n"
        "/chess - بدء تحدي\n"
        "/cancel - إلغاء التحدي المنتظر\n"
        "/stats - إحصائياتي\n\n"
        "أثناء اللعبة أرسل النقلة مثل:\n"
        "e2e4\n\n"
        "وللاستسلام:\n"
        "استسلام"
    )
    await update.message.reply_text(text)


async def chess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("هذا الأمر يشتغل داخل الكروب فقط.")
        return

    user = update.effective_user
    group_id = update.effective_chat.id

    if not await require_subscription(update, context, user.id):
        return

    existing = get_waiting_or_active_game_by_user(group_id, user.id)
    if existing:
        await update.message.reply_text("عندك لعبة شغالة أو تحدي مفتوح بالفعل داخل هذا الكروب.")
        return

    waiting = get_waiting_game(group_id)
    if waiting:
        await update.message.reply_text("أكو تحدي مفتوح حاليًا. اضغط قبول عليه أو انتظر ينتهي.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ قبول التحدي", callback_data="accept_chess")],
    ])

    msg = await update.message.reply_text(
        f"♟️ {get_display_name(user)} يريد يلعب شطرنج.\n"
        f"اللي يريد يلعب يضغط زر القبول.",
        reply_markup=keyboard
    )

    create_waiting_game(
        group_id=group_id,
        challenger_id=user.id,
        challenger_name=get_display_name(user),
        message_id=msg.message_id
    )


async def accept_chess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    group_id = update.effective_chat.id

    if not await require_subscription(update, context, user.id):
        return

    row = get_waiting_game(group_id)
    if not row:
        await query.edit_message_text("ماكو تحدي متاح هسه.")
        return

    game = get_names_from_game_row(row)

    if user.id == game["challenger_id"]:
        await query.answer("ما تگدر تقبل تحديك بنفسك.", show_alert=True)
        return

    existing = get_waiting_or_active_game_by_user(group_id, user.id)
    if existing:
        await query.answer("عندك لعبة شغالة أو تحدي آخر.", show_alert=True)
        return

    board = chess.Board()

    players = [game["challenger_id"], user.id]
    random.shuffle(players)
    white_id, black_id = players
    turn_id = white_id

    white_name = game["challenger_name"] if white_id == game["challenger_id"] else get_display_name(user)
    black_name = game["challenger_name"] if black_id == game["challenger_id"] else get_display_name(user)

    activate_game(
        game_id=game["id"],
        opponent_id=user.id,
        opponent_name=get_display_name(user),
        white_id=white_id,
        black_id=black_id,
        turn_id=turn_id,
        fen=board.fen()
    )

    current_turn_name = white_name
    text = game_status_text(
        challenger_name=game["challenger_name"],
        white_name=white_name,
        black_name=black_name,
        current_turn_name=current_turn_name,
        board=board
    )

    await query.edit_message_text(text=text, parse_mode="HTML")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("هذا الأمر داخل الكروب فقط.")
        return

    user = update.effective_user
    group_id = update.effective_chat.id

    row = get_waiting_game(group_id)
    if not row:
        await update.message.reply_text("ماكو تحدي منتظر حتى يتلغي.")
        return

    game = get_names_from_game_row(row)
    if game["challenger_id"] != user.id:
        await update.message.reply_text("فقط صاحب التحدي يگدر يلغيه.")
        return

    cancel_waiting_game(game["id"])
    await update.message.reply_text("تم إلغاء التحدي.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wins, losses, draws = get_stats(user.id)

    await update.message.reply_text(
        f"إحصائياتك ♟️\n\n"
        f"فوز: {wins}\n"
        f"خسارة: {losses}\n"
        f"تعادل: {draws}"
    )


async def handle_move_or_resign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = update.effective_user
    group_id = update.effective_chat.id

    row = get_active_game_by_group(group_id)
    if not row:
        return

    game = get_names_from_game_row(row)

    if user.id not in [game["white_id"], game["black_id"]]:
        return

    board = chess.Board(game["fen"])

    white_name = game["challenger_name"] if game["white_id"] == game["challenger_id"] else game["opponent_name"]
    black_name = game["challenger_name"] if game["black_id"] == game["challenger_id"] else game["opponent_name"]

    # استسلام
    if text in ["استسلام", "انسحب", "/resign"]:
        winner_id = game["black_id"] if user.id == game["white_id"] else game["white_id"]
        loser_id = user.id

        winner_name = white_name if winner_id == game["white_id"] else black_name
        loser_name = white_name if loser_id == game["white_id"] else black_name

        add_win(winner_id)
        add_loss(loser_id)
        finish_game(game["id"])

        await update.message.reply_text(
            f"🏳️ {loser_name} استسلم.\n"
            f"🏆 الفائز: {winner_name}"
        )
        return

    # مو دورك
    if user.id != game["turn_id"]:
        return

    move = parse_move_from_text(text)
    if not move:
        return

    if move not in board.legal_moves:
        await update.message.reply_text("نقلة غير قانونية.")
        return

    board.push(move)
    next_turn_id = game["black_id"] if user.id == game["white_id"] else game["white_id"]

    # نهاية اللعبة؟
    end_result = result_text(board)
    if end_result:
        finish_game(game["id"])

        if board.is_checkmate():
            winner_id = user.id
            loser_id = next_turn_id
            add_win(winner_id)
            add_loss(loser_id)
        else:
            add_draw(game["white_id"])
            add_draw(game["black_id"])

        final_text = (
            f"♟️ انتهت اللعبة\n\n"
            f"الأبيض: {white_name}\n"
            f"الأسود: {black_name}\n\n"
            f"<pre>{board_to_text(board)}</pre>\n\n"
            f"النتيجة: {end_result}"
        )

        await update.message.reply_text(final_text, parse_mode="HTML")
        return

    update_game_state(game["id"], board.fen(), next_turn_id)

    current_turn_name = white_name if next_turn_id == game["white_id"] else black_name
    text_out = game_status_text(
        challenger_name=game["challenger_name"],
        white_name=white_name,
        black_name=black_name,
        current_turn_name=current_turn_name,
        board=board
    )

    await update.message.reply_text(text_out, parse_mode="HTML")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)


def main():
    init_db()

    if BOT_TOKEN == "PUT_BOT_TOKEN_HERE":
        print("حط توكن البوت داخل BOT_TOKEN أول.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chess", chess_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(accept_chess, pattern="^accept_chess$"))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_move_or_resign)
    )

    app.add_error_handler(error_handler)

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
