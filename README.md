# tg-channel-quiz-manager

A Telegram bot that lets admins upload quizzes in JSON format and post them as interactive polls to any channel.  
Supports both regular and quiz-type polls, stores responses in SQLite, and allows fetching results by poll ID — ideal for managing channel-based quiz content easily.

---

## ✨ Features

- Accepts quiz **JSON** via text or `.json` file (≤ 200 KB)
- **One stored quiz per admin** at a time
- Posts **Quiz** (with correct answer) or **Regular** polls to a channel
- Persists data using **SQLite**
- Fetches **results** by `poll_id`
- Admin-only control for posting and channel setup

---

## 📦 Tech Stack

- **Python 3.10+**
- **python-telegram-bot v20+**
- **SQLite** (no external DB needed)

---

## 🗂 Project Structure

