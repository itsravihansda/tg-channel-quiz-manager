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

```
.
├── quiz_channel_bot.py
├── README.md
└── quizbot.db               # auto-created on first run
```

---

## 🔧 Setup

1. **Create a bot** using [@BotFather](https://t.me/BotFather) and copy its token.  
2. **Add your bot** to the target Telegram channel and promote it to **Admin**.  
3. **Clone this repo** and install dependencies:
   ```bash
   git clone https://github.com/<your-username>/tg-channel-quiz-manager.git
   cd tg-channel-quiz-manager
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -U python-telegram-bot~=21.0
   ```
4. **Configure environment:**
   Edit `quiz_channel_bot.py` and set:
   ```python
   BOT_TOKEN = os.getenv("BOT_TOKEN", "xxxxxxxxxxxxxxxxx")
   BOT_USERNAME = os.getenv("BOT_USERNAME", "xxx")  # without @
   CHANNEL_ID = os.getenv("CHANNEL_ID", "@xxxx")
   ADMINS = {123456789}  # your Telegram user IDs here
   ```

---

## ▶️ Run the Bot

```bash
python quiz_channel_bot.py
```
The bot will initialize the database (`quizbot.db`) and start polling.

---

## 👮 Admin Commands & Workflow

> Only users listed in `ADMINS` can perform these actions.

| Command | Description |
|--------|-------------|
| `/start` | Displays help message |
| `/setchannel @channelname` | Sets target channel dynamically |
| **Send JSON** | Upload quiz JSON (text or file) to store it |
| `/postjson` | Posts the last stored quiz to the channel |
| `/results <poll_id>` | Shows collected answers for a poll |

---

## 🧩 JSON Format

Minimum fields:
```json
{
  "question": "कवि रामधारी सिंह ‘दिनकर’ की दृष्टि में ज्ञान के देवता कहाँ मिलते हैं?",
  "options": ["खेड़–खेलाड़ियों में", "तपस्वियों में", "राजाओं में", "दार्शनिकों में"]
}
```

Optional fields:
```json
{
  "correct_option": 1,
  "is_anonymous": false,
  "allows_multiple_answers": false,
  "open_period": 60,
  "explanation": "दिनकर के अनुसार यह उत्तर सही है।",
  "parse_mode": "HTML"
}
```

**Behavior Notes**
- If `correct_option` is valid → **Quiz** poll (with solution).  
- If omitted/invalid → **Regular** poll.  
- `parse_mode` may be `HTML` or `MarkdownV2` (explanation).

---

## 🗃️ Database Schema

SQLite database: `quizbot.db`

| Table | Fields |
|------|--------|
| `polls` | `poll_id`, `message_id`, `chat_id`, `question`, `options_json`, `created_at` |
| `answers` | `id`, `poll_id`, `user_id`, `option_ids_json`, `answered_at` |

---

## ✅ Requirements

- Bot must be **admin** of the channel it posts to  
- `ADMINS` must include authorized Telegram user IDs  
- JSON payloads ≤ **200 KB**  

---

## 🧪 Quick Test

1. `/setchannel @yourchannel`  
2. Send a JSON quiz (as text or file)  
3. `/postjson` → posts poll  
4. Vote on the channel poll  
5. `/results <poll_id>` → shows answers

---

## 🔒 Security Notes

- Keep your **BOT_TOKEN** private  
- Validate any external JSON inputs  
- Restrict access to known admins  

---

## 🐛 Troubleshooting

- **“Unauthorized”** → Add your Telegram ID to `ADMINS`  
- **“Failed to send poll”** → Bot isn’t admin in the target channel or `CHANNEL_ID` is wrong  
- **No answers recorded** → Ensure users vote in bot-created polls  
- **Explanation not showing** → Escape MarkdownV2 chars or switch to `HTML`

---

## 🚀 Deployment

### Docker Example
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install -U python-telegram-bot~=21.0
ENV BOT_TOKEN=your_token_here
ENV CHANNEL_ID=@yourchannel
CMD ["python", "quiz_channel_bot.py"]
```

---

## 🗺️ Roadmap

- Export results (CSV/JSON)
- List recent polls
- Web dashboard for admins
- Inline publish/retry buttons

---

## 📄 License

MIT License © 2025 — Your Name

---

## 💬 Repo Info (GitHub About)

**Name:** `tg-channel-quiz-manager`  
**Description:** A Telegram bot that lets admins upload quizzes in JSON format and post them as interactive polls to any channel. Supports both regular and quiz-type polls, stores responses in SQLite, and allows fetching results by poll ID — ideal for managing channel-based quiz content easily.
