# quiz_channel_bot.py
# Requires: python-telegram-bot >= 20
import logging
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

from telegram import Update, Poll
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    PollHandler,            # NEW: for anonymous poll aggregate updates
    filters,
    ContextTypes,
)

# ------------- CONFIG -------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "xxxxxxxxxxxxxxxxx")
BOT_USERNAME = os.getenv("BOT_USERNAME", "xxx")  # without @, e.g. MyQuizBot
CHANNEL_ID = os.getenv("CHANNEL_ID", "@xxxx")
ADMINS = {123456789}  # <-- put your Telegram user IDs here
DB_PATH = "quizbot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # posted polls
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS polls (
            poll_id TEXT PRIMARY KEY,
            message_id INTEGER,
            chat_id TEXT,
            question TEXT,
            options_json TEXT,
            created_at TEXT
        )
        """
    )
    # per-user answers (only for non-anonymous polls)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT,
            user_id INTEGER,
            option_ids_json TEXT,
            answered_at TEXT
        )
        """
    )
    # NEW: aggregates for anonymous polls (totals only)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS poll_stats (
            poll_id TEXT PRIMARY KEY,
            totals_json TEXT,          -- e.g. [3,5,2,0]
            total_voter_count INTEGER, -- Telegram's total_voter_count
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_poll(poll_id: str, message_id: int, chat_id: str, question: str, options: list):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO polls (poll_id, message_id, chat_id, question, options_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (poll_id, message_id, chat_id, question, json.dumps(options), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def save_answer(poll_id: str, user_id: int, option_ids: list):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO answers (poll_id, user_id, option_ids_json, answered_at) VALUES (?, ?, ?, ?)",
        (poll_id, user_id, json.dumps(option_ids), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def save_poll_stats(poll_id: str, totals: list, total_voters: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO poll_stats (poll_id, totals_json, total_voter_count, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (poll_id, json.dumps(totals), int(total_voters), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_results_for_poll(poll_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, option_ids_json, answered_at FROM answers WHERE poll_id = ?",
        (poll_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_poll_meta(poll_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT question, options_json FROM polls WHERE poll_id = ?",
        (poll_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row  # (question, options_json) or None


def get_stats_for_poll(poll_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT totals_json, total_voter_count, updated_at FROM poll_stats WHERE poll_id = ?",
        (poll_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row  # (totals_json, total_voter_count, updated_at) or None


# ---------- Utility ----------
def is_admin(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return int(user_id) in ADMINS


def normalize_parse_mode(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().upper()
    if v == "HTML":
        return ParseMode.HTML
    if v in ("MARKDOWNV2", "MARKDOWN_V2"):
        return ParseMode.MARKDOWN_V2
    return None


# ---------- Bot handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi — send me a JSON quiz file or paste JSON text (admins only).\n\n"
        "Commands:\n"
        "/setchannel @yourchannel — change target channel\n"
        "/postjson — post last stored JSON\n"
        "/results <poll_id> — show results (per-user if non-anonymous, aggregate if anonymous)"
    )


async def setchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setchannel @yourchannelname or /setchannel <chat_id>")
        return
    new_channel = context.args[0]
    global CHANNEL_ID
    CHANNEL_ID = new_channel
    await update.message.reply_text(f"Channel set to: {CHANNEL_ID}")


async def receive_json_file_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Unauthorized. Only admins can upload quizzes.")
        return

    text_payload = None

    # If user sent a JSON file:
    if update.message.document:
        doc = update.message.document
        # Only allow small files: for safety; you can remove size check if needed
        if doc.file_size and doc.file_size > 200_000:  # 200 KB
            await update.message.reply_text("File too large.")
            return
        file = await doc.get_file()
        content = await file.download_as_bytearray()
        text_payload = content.decode("utf-8", errors="replace")
    elif update.message.text and not update.message.text.startswith("/"):
        text_payload = update.message.text

    if not text_payload:
        await update.message.reply_text("No JSON payload found in the message.")
        return

    # Try parse
    try:
        parsed = json.loads(text_payload)
    except Exception as e:
        await update.message.reply_text(f"Invalid JSON: {e}")
        return

    # Basic validation
    if not isinstance(parsed, dict) or "question" not in parsed or "options" not in parsed:
        await update.message.reply_text("JSON must be an object with at least 'question' and 'options' fields.")
        return

    # Save parsed JSON in conversation data for /postjson to use
    context.user_data["last_quiz_json"] = parsed
    await update.message.reply_text(
        "Quiz JSON saved. Use /postjson to post it to the channel, or send another JSON to replace."
    )


async def postjson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Unauthorized.")
        return

    parsed = context.user_data.get("last_quiz_json")
    if not parsed:
        await update.message.reply_text("No stored JSON found. Send me the quiz JSON first (as file or text).")
        return

    # Pull fields from parsed JSON
    question = parsed.get("question")
    options = parsed.get("options")
    correct_option = parsed.get("correct_option")  # zero-based index (optional)
    is_anonymous = parsed.get("is_anonymous", False)
    allows_multiple_answers = parsed.get("allows_multiple_answers", False)
    open_period = parsed.get("open_period")  # seconds (optional)
    explanation = parsed.get("explanation")
    parse_mode = normalize_parse_mode(parsed.get("parse_mode"))  # e.g., HTML or MarkdownV2

    if not question or not isinstance(options, list) or len(options) < 2:
        await update.message.reply_text("Invalid quiz: require 'question' and 'options' (at least 2).")
        return

    # Prepare send_poll args
    poll_kwargs = {
        "question": question,
        "options": options,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
    }

    # Determine poll type
    if isinstance(correct_option, int) and 0 <= correct_option < len(options):
        poll_kwargs["type"] = Poll.QUIZ
        poll_kwargs["correct_option_id"] = int(correct_option)
    else:
        poll_kwargs["type"] = Poll.REGULAR

    if open_period:
        try:
            poll_kwargs["open_period"] = int(open_period)
        except Exception:
            pass

    if explanation:
        poll_kwargs["explanation"] = explanation
        if parse_mode:
            poll_kwargs["explanation_parse_mode"] = parse_mode

    # send poll to CHANNEL_ID
    try:
        sent_message = await context.bot.send_poll(chat_id=CHANNEL_ID, **poll_kwargs)
    except Exception as e:
        logger.exception("Failed to send poll")
        await update.message.reply_text(f"Failed to send poll to channel {CHANNEL_ID}: {e}")
        return

    # Save poll metadata to DB
    poll_id = sent_message.poll.id
    save_poll(poll_id, sent_message.message_id, CHANNEL_ID, question, options)

    await update.message.reply_text(f"Poll posted to {CHANNEL_ID}. poll_id: {poll_id}")


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles users' answers to polls created by this bot (non-anonymous only).
    Telegram sends a PollAnswer update with poll_id, user, option_ids.
    We'll store them in the DB.
    """
    answer = update.poll_answer  # telegram.PollAnswer
    poll_id = answer.poll_id
    user_id = answer.user.id
    option_ids = answer.option_ids  # list (for multiple choice) or single-element list
    # Save to DB
    save_answer(poll_id, user_id, option_ids)
    logger.info("Saved answer: poll=%s user=%s option=%s", poll_id, user_id, option_ids)


async def poll_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives aggregate poll updates for any poll (anonymous and non-anonymous).
    For anonymous polls this is the *only* way to track results (no per-user data).
    """
    p = update.poll
    if not p:
        return
    totals = [opt.voter_count for opt in p.options]
    total_voters = int(getattr(p, "total_voter_count", sum(totals)))
    save_poll_stats(p.id, totals, total_voters)
    logger.info("Saved poll stats: poll=%s totals=%s total_voters=%s", p.id, totals, total_voters)


async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /results <poll_id>")
        return

    poll_id = context.args[0]
    # First try per-user answers (non-anonymous)
    rows = get_results_for_poll(poll_id)

    if rows:
        text_lines = [f"Results for poll_id: {poll_id}", f"Total answers (non-anonymous): {len(rows)}", ""]
        for (user_id, option_json, answered_at) in rows:
            try:
                option_ids = json.loads(option_json)
            except Exception:
                option_ids = []
            text_lines.append(f"user_id: {user_id} | options: {option_ids} | at: {answered_at}")
        await update.message.reply_text("\n".join(text_lines))
        return

    # Fallback to anonymous aggregates
    stats = get_stats_for_poll(poll_id)
    if stats:
        totals_json, total_voters, updated_at = stats
        try:
            totals = json.loads(totals_json)
        except Exception:
            totals = []

        # Pretty-print with option labels if we have meta
        meta = get_poll_meta(poll_id)
        if meta:
            question, options_json = meta
            try:
                options = json.loads(options_json)
            except Exception:
                options = []
            lines = [f"Results for poll_id: {poll_id}", f"(question: {question})"]
            for i, opt_text in enumerate(options):
                cnt = totals[i] if i < len(totals) else 0
                lines.append(f"{opt_text} — {cnt}")
        else:
            lines = [f"Results for poll_id: {poll_id}"]
            lines += [f"Option {i+1} — {cnt}" for i, cnt in enumerate(totals)]

        lines.append(f"Total voters: {total_voters}")
        lines.append(f"Updated at (UTC): {updated_at}")
        await update.message.reply_text("\n".join(lines))
        return

    await update.message.reply_text("No answers or aggregates found for that poll id.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that. Send JSON quiz or use commands.")


# ---------- Main ----------
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setchannel", setchannel))
    application.add_handler(CommandHandler("postjson", postjson))
    application.add_handler(CommandHandler("results", results_command))

    # Messages: accept JSON file or text (admins only)
    application.add_handler(
        MessageHandler(
            filters.Document.ALL | (filters.TEXT & ~filters.COMMAND),
            receive_json_file_or_text
        )
    )

    # PollAnswer handler (non-anonymous per-user answers)
    application.add_handler(PollAnswerHandler(poll_answer_handler))

    # NEW: Poll updates handler (aggregates; works for anonymous polls)
    application.add_handler(PollHandler(poll_update_handler))

    # Fallback
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
