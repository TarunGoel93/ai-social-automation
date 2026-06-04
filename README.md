<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=200&section=header&text=AI%20Social%20Automation&fontSize=52&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Flask%20%7C%20n8n%20%7C%20SQLite%20%7C%20LinkedIn%20%7C%20Instagram&descAlignY=60&descSize=18" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![n8n](https://img.shields.io/badge/n8n-Workflow-EA4B71?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Supported-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com)
[![Instagram](https://img.shields.io/badge/Instagram-Supported-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://instagram.com)

<br/>

> **AI-powered social media automation** — Generate, schedule, and publish content across LinkedIn & Instagram with a beautiful dashboard UI and a persistent post queue.

<br/>

[🚀 Quick Start](#-quick-start) · [✨ Features](#-features) · [🏗 Architecture](#-architecture) · [📡 API Reference](#-api-reference) · [⚙️ n8n Setup](#%EF%B8%8F-n8n-workflow-setup) · [🤝 Contributing](#-contributing)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🤖 AI Mode
Describe your idea and let the AI craft the perfect post — captions, tone, hashtags, and all. Just give a prompt and choose your audience.

</td>
<td width="50%">

### ✍️ Manual Mode
Upload your own image, write your caption, and post it directly with full control over every word and pixel.

</td>
</tr>
<tr>
<td width="50%">

### 🕐 Scheduled Queue
Queue posts for any future date and time. A background daemon checks every 30 seconds and fires them automatically via the n8n webhook.

</td>
<td width="50%">

### 📋 Queue Dashboard
View all pending, posted, and failed posts in a live queue panel. Cancel pending posts or manually fire them on demand.

</td>
</tr>
<tr>
<td width="50%">

### 🔗 n8n Integration
Seamless webhook-driven delivery to LinkedIn and Instagram through n8n workflows — no platform SDK headaches.

</td>
<td width="50%">

### 💾 Persistent SQLite Store
Every queued post — including uploaded images — is stored durably so nothing is lost on server restart.

</td>
</tr>
</table>

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Browser / Dashboard UI                        │
│        (index.html · style.css · script.js)                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │  HTTP (JSON / multipart)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Flask Backend  (app.py)                       │
│                                                                   │
│   /submit       – immediate or scheduled single post              │
│   /queue        – add directly to the persistent queue            │
│   /posts        – list all queued posts                           │
│   /posts/:id    – delete a pending post                           │
│   /posts/:id/fire – manually trigger a queued post               │
│   /health       – webhook reachability check                      │
│                                                                   │
│   ┌──────────────────┐     ┌──────────────────────────────────┐  │
│   │  Background       │     │       SQLite  (posts.db)         │  │
│   │  Scheduler Thread │────▶│  id · mode · platforms           │  │
│   │  (every 30s)      │     │  caption · prompt · tone         │  │
│   └──────────────────┘     │  image_path · scheduled_time      │  │
│                             │  status · fired_at · error_msg    │  │
│                             └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                           │  POST webhook (JSON / multipart)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     n8n Workflow                                   │
│                                                                   │
│   Webhook  ──▶  Code (JS transform)  ──▶  LinkedIn Post Node     │
│                                                                   │
│   (worflow.json — import directly into n8n)                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
ai-social-automation/
│
├── app.py                  # Flask backend — all routes & scheduler
├── n1.py                   # Helper / utility script
├── requirements.txt        # Python dependencies
├── worflow.json            # n8n workflow (import into n8n)
│
├── posts.db                # SQLite database (auto-created)
├── post_images/            # Persistent storage for queued images
├── uploads/                # Temp storage for immediate posts
│
├── templates/
│   └── index.html          # Single-page dashboard UI
│
└── static/
    ├── style.css           # Dashboard styles (Syne + DM Sans)
    └── script.js           # Frontend logic & queue management
```

---

## 🚀 Quick Start

### 1 · Clone the repo

```bash
git clone https://github.com/TarunGoel93/ai-social-automation.git
cd ai-social-automation
```

### 2 · Install dependencies

```bash
pip install -r requirements.txt
```

> **requirements.txt**
> ```
> flask>=3.0
> flask-cors>=4.0
> requests>=2.31
> ```

### 3 · Configure the n8n webhook

```bash
# Option A — environment variable (recommended for production)
export N8N_WEBHOOK_URL="https://<your-n8n-instance>/webhook/<your-path>"

# Option B — edit the default in app.py
N8N_WEBHOOK_URL = "https://..."
```

> ⚠️ The default URL uses `/webhook-test/` which only works while the n8n workflow is open in **test mode**. For production, use the `/webhook/` (production) URL.

### 4 · Run the server

```bash
python app.py
```

Open **http://localhost:5000** and you're live. 🎉

---

## ⚙️ n8n Workflow Setup

1. Open your n8n instance and go to **Workflows → Import from file**.
2. Import `worflow.json` from this repo.
3. The workflow contains three nodes:

| Node | Type | Purpose |
|------|------|---------|
| **Webhook** | Webhook trigger | Receives POST from Flask |
| **Code in JavaScript** | Code node | Extracts `caption` and `image` binary |
| **Create a post** | LinkedIn node | Publishes to a LinkedIn organization |

4. Connect your LinkedIn credentials to the **Create a post** node.
5. Activate the workflow and copy the **production webhook URL** into `N8N_WEBHOOK_URL`.

> 💡 To add Instagram support, extend the workflow with an Instagram node in parallel with the LinkedIn node and route based on the `platforms` field in the payload.

---

## 📡 API Reference

### `POST /submit`
Submit a post for immediate publishing or scheduled queueing.

**AI Mode (JSON body)**
```json
{
  "mode": "ai",
  "prompt": "Announce our new product launch with excitement",
  "tone": "professional",
  "platforms": "linkedin",
  "scheduled_time": "2025-12-01T10:00:00"   // optional — omit for immediate
}
```

**Manual Mode (multipart/form-data)**
```
mode=manual
caption=<string>
platforms=linkedin|instagram|both
image=<file>
scheduled_time=<ISO-8601>    # optional
```

---

### `POST /queue`
Add a post directly to the persistent queue (scheduled_time required).

Same fields as `/submit` but `scheduled_time` is **required**.

---

### `GET /posts`
List all posts in the queue.

```
GET /posts             → all posts
GET /posts?status=pending
GET /posts?status=posted
GET /posts?status=failed
```

**Response**
```json
{
  "status": "success",
  "posts": [
    {
      "id": 1,
      "mode": "manual",
      "platforms": "linkedin",
      "caption": "Hello world",
      "scheduled_time": "2025-12-01T10:00:00",
      "status": "pending",
      "created_at": "2025-11-30T08:00:00",
      "fired_at": null,
      "error_msg": null
    }
  ]
}
```

---

### `DELETE /posts/:id`
Cancel and delete a **pending** post (also removes stored image from disk).

---

### `POST /posts/:id/fire`
Manually trigger a pending post immediately, bypassing the scheduler.

---

### `GET /health`
Check whether the n8n webhook is reachable.

```json
{
  "status": "ok",
  "webhook_url": "https://...",
  "http_status": 200,
  "message": "n8n reachable"
}
```

---

## 🗄 Database Schema

```sql
CREATE TABLE posts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    mode           TEXT    NOT NULL,          -- 'ai' | 'manual'
    platforms      TEXT    NOT NULL,          -- 'instagram' | 'linkedin' | 'both'
    caption        TEXT,                      -- manual mode
    image_path     TEXT,                      -- local path to stored image
    image_filename TEXT,                      -- original filename
    image_mimetype TEXT,                      -- e.g. image/jpeg
    prompt         TEXT,                      -- ai mode
    tone           TEXT,                      -- ai mode tone hint
    scheduled_time TEXT    NOT NULL,          -- ISO-8601 datetime
    status         TEXT    NOT NULL DEFAULT 'pending',  -- pending|posted|failed
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    fired_at       TEXT,                      -- when the scheduler fired it
    error_msg      TEXT                       -- error detail if status=failed
);
```

---

## 🖥 Dashboard UI

The single-page dashboard ships with three tabs:

| Tab | Description |
|-----|-------------|
| **⚡ AI Mode** | Prompt + tone → platform → optional schedule → Generate & Post |
| **✏️ Manual Mode** | Drag-and-drop image + caption → platform → optional schedule → Post |
| **📋 Queue** | Live table of all queued posts with status badges and action buttons |

Built with **Syne** and **DM Sans** fonts, animated orb backgrounds, a dark glassmorphism card, and a smooth three-tab slider.

---

## 🔧 Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `N8N_WEBHOOK_URL` | `https://intellifytechnology.app.n8n.cloud/webhook-test/...` | n8n webhook endpoint |
| `DB_PATH` | `posts.db` | SQLite database file path |
| `MAX_CONTENT_LENGTH` | `16 MB` | Maximum upload size |
| Scheduler interval | `30 s` | How often the background thread checks for due posts |

---

## 🛡 Security Notes

- The `image_path` field is **never exposed** in `/posts` API responses.
- All uploaded filenames are sanitised with `werkzeug.utils.secure_filename`.
- CORS is enabled globally via `flask-cors` — tighten the `origins` parameter before deploying publicly.
- The default webhook URL contains a test token; **always** replace it with your production webhook before going live.

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

```bash
# 1. Fork the repo and clone your fork
git clone https://github.com/<your-username>/ai-social-automation.git

# 2. Create a feature branch
git checkout -b feature/add-twitter-support

# 3. Make your changes and commit
git commit -m "feat: add Twitter/X platform support"

# 4. Push and open a pull request
git push origin feature/add-twitter-support
```

**Ideas for contributions:**
- 🐦 Twitter / X platform support
- 📊 Analytics dashboard (post reach, engagement)
- 🔁 Recurring post schedules (cron-style)
- 🐳 Docker + docker-compose setup
- ✅ Unit and integration tests

---

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" width="100%"/>

Made with ❤️ by [Tarun Goel](https://github.com/TarunGoel93)

⭐ **Star this repo if it helped you!** ⭐

</div>
