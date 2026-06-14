"""
Social Media Automation Tool - Flask Backend
Supports AI mode, Manual mode, scheduled posting via n8n webhook,
and a persistent SQLite queue for bulk scheduled posts.
"""

import os
import sqlite3
import threading
import time
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# ── Config ────────────────────────────────────────────────────────────────────
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024   # 16 MB
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

N8N_WEBHOOK_URL = os.getenv(
    'N8N_WEBHOOK_URL',
    'https://intellifytechnology.app.n8n.cloud/webhook/0e383072-9f3d-4da2-8e47-ca164ae15191'
)
# NOTE: /webhook-test/ only works when the n8n workflow is open & in "test" mode.
# For production, set N8N_WEBHOOK_URL env var to the /webhook/ (production) URL instead.

DB_PATH = os.getenv('DB_PATH', 'posts.db')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('post_images', exist_ok=True)  # permanent storage for queued images


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                mode           TEXT    NOT NULL,          -- 'ai' | 'manual'
                platforms      TEXT    NOT NULL,
                caption        TEXT,                      -- manual mode
                image_path     TEXT,                      -- manual mode (local path)
                image_filename TEXT,                      -- original filename
                image_mimetype TEXT,
                prompt         TEXT,                      -- ai mode
                tone           TEXT,                      -- ai mode
                scheduled_time TEXT    NOT NULL,          -- ISO-8601
                status         TEXT    NOT NULL DEFAULT 'pending',  -- pending|posted|failed
                created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                fired_at       TEXT,
                error_msg      TEXT
            )
        """)
        conn.commit()


init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_scheduled_time(raw: str) -> str:
    if not raw:
        return ''
    try:
        dt = datetime.fromisoformat(raw)
        return dt.isoformat()
    except ValueError:
        return raw


def fire_post(post: dict):
    """Send a single post dict to n8n. Returns (success: bool, message: str)."""
    try:
        if post['mode'] == 'ai':
            payload = {
                'mode':           'ai',
                'prompt':         post['prompt'] or '',
                'tone':           post['tone'] or '',
                'platforms':      post['platforms'],
                'scheduled_time': post['scheduled_time'],
            }
            resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=15)
            resp.raise_for_status()
            return True, 'Posted successfully!'

        else:  # manual
            img_path = post['image_path']
            if not img_path or not os.path.exists(img_path):
                return False, 'Image file not found on disk.'

            with open(img_path, 'rb') as f:
                files = {'image': (post['image_filename'], f, post['image_mimetype'] or 'image/jpeg')}
                form_data = {
                    'mode':           'manual',
                    'caption':        post['caption'] or '',
                    'platforms':      post['platforms'],
                    'scheduled_time': post['scheduled_time'],
                }
                resp = requests.post(N8N_WEBHOOK_URL, files=files, data=form_data, timeout=15)
                resp.raise_for_status()
            return True, 'Posted successfully!'

    except requests.exceptions.ConnectionError:
        return False, 'n8n webhook unreachable'
    except requests.exceptions.RequestException as exc:
        return False, f'Webhook error: {exc}'


# ── Background Scheduler ──────────────────────────────────────────────────────

def scheduler_loop():
    """Runs in a daemon thread. Every 30 s checks for posts due to fire."""
    while True:
        try:
            now = datetime.now().isoformat(timespec='seconds')
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT * FROM posts WHERE status='pending' AND scheduled_time <= ?",
                    (now,)
                ).fetchall()

            for row in rows:
                post = dict(row)
                app.logger.info('Scheduler firing post id=%s', post['id'])
                ok, msg = fire_post(post)
                with get_db() as conn:
                    conn.execute(
                        """UPDATE posts SET status=?, fired_at=datetime('now'), error_msg=?
                           WHERE id=?""",
                        ('posted' if ok else 'failed', None if ok else msg, post['id'])
                    )
                    conn.commit()
        except Exception as exc:
            app.logger.error('Scheduler error: %s', exc)

        time.sleep(30)


scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
scheduler_thread.start()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    """Quick check: is the n8n webhook reachable?"""
    try:
        # Send a HEAD-like ping (GET may 404 on webhooks, so we send a tiny POST)
        resp = requests.post(N8N_WEBHOOK_URL, json={'ping': True}, timeout=6)
        reachable = resp.status_code < 500
        return jsonify({
            'status': 'ok' if reachable else 'error',
            'webhook_url': N8N_WEBHOOK_URL,
            'http_status': resp.status_code,
            'message': 'n8n reachable' if reachable else f'n8n returned {resp.status_code}'
        })
    except requests.exceptions.ConnectionError:
        return jsonify({'status': 'error', 'webhook_url': N8N_WEBHOOK_URL,
                        'message': 'Connection refused — is n8n running and the workflow active?'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'message': 'Timed out after 6 s'}), 504
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 500


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    """
    Original single-post endpoint. Still works exactly as before.
    If scheduled_time is set, saves to DB queue instead of firing now.
    """
    mode = request.form.get('mode') or (request.get_json(silent=True) or {}).get('mode')
    if not mode:
        return jsonify({'status': 'error', 'message': 'No mode specified.'}), 400

    # ── AI MODE ───────────────────────────────────────────────────────────────
    if mode == 'ai':
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON payload.'}), 400

        prompt    = data.get('prompt', '').strip()
        tone      = data.get('tone', '').strip()
        platforms = data.get('platforms', '').strip()
        scheduled = parse_scheduled_time(data.get('scheduled_time', ''))

        if not prompt:
            return jsonify({'status': 'error', 'message': 'Post idea cannot be empty.'}), 400
        if not platforms:
            return jsonify({'status': 'error', 'message': 'Please select a platform.'}), 400

        if scheduled:
            # Save to queue
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO posts (mode, platforms, prompt, tone, scheduled_time)
                       VALUES (?, ?, ?, ?, ?)""",
                    ('ai', platforms, prompt, tone, scheduled)
                )
                conn.commit()
            return jsonify({'status': 'success', 'message': f'Queued for {scheduled}!'})

        # Post immediately
        payload = {'mode': 'ai', 'prompt': prompt, 'tone': tone,
                   'platforms': platforms, 'scheduled_time': ''}
        try:
            resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=15)
            resp.raise_for_status()
            return jsonify({'status': 'success', 'message': 'Posted successfully!'})
        except requests.exceptions.ConnectionError:
            return jsonify({'status': 'success', 'message': 'Submitted! (webhook offline – mock)'})
        except requests.exceptions.RequestException as exc:
            return jsonify({'status': 'error', 'message': f'Webhook error: {exc}'}), 502

    # ── MANUAL MODE ───────────────────────────────────────────────────────────
    elif mode == 'manual':
        caption   = request.form.get('caption', '').strip()
        platforms = request.form.get('platforms', '').strip()
        scheduled = parse_scheduled_time(request.form.get('scheduled_time', ''))
        image     = request.files.get('image')

        if not caption:
            return jsonify({'status': 'error', 'message': 'Caption cannot be empty.'}), 400
        if not platforms:
            return jsonify({'status': 'error', 'message': 'Please select a platform.'}), 400
        if not image or image.filename == '':
            return jsonify({'status': 'error', 'message': 'Please upload an image.'}), 400
        if not allowed_file(image.filename):
            return jsonify({'status': 'error', 'message': 'Only image files are allowed.'}), 400

        filename  = secure_filename(image.filename)

        if scheduled:
            # Persist image permanently for later firing
            save_path = os.path.join('post_images', filename)
            image.save(save_path)
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO posts
                       (mode, platforms, caption, image_path, image_filename, image_mimetype, scheduled_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    ('manual', platforms, caption, save_path, filename,
                     image.mimetype, scheduled)
                )
                conn.commit()
            return jsonify({'status': 'success', 'message': f'Queued for {scheduled}!'})

        # Post immediately (original behaviour)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(save_path)
        try:
            with open(save_path, 'rb') as f:
                files    = {'image': (filename, f, image.mimetype)}
                form_data = {'mode': 'manual', 'caption': caption,
                             'platforms': platforms, 'scheduled_time': ''}
                resp = requests.post(N8N_WEBHOOK_URL, files=files, data=form_data, timeout=15)
                resp.raise_for_status()
            return jsonify({'status': 'success', 'message': 'Posted successfully!'})
        except requests.exceptions.ConnectionError:
            return jsonify({'status': 'success', 'message': 'Submitted! (webhook offline – mock)'})
        except requests.exceptions.RequestException as exc:
            return jsonify({'status': 'error', 'message': f'Webhook error: {exc}'}), 502
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    else:
        return jsonify({'status': 'error', 'message': f'Unknown mode: {mode}'}), 400


# ── Queue Endpoints ───────────────────────────────────────────────────────────

@app.route('/queue', methods=['POST'])
def add_to_queue():
    """
    Dedicated endpoint to add a post directly to the queue.
    Accepts multipart/form-data with fields:
      mode, platforms, scheduled_time,
      caption (manual), image file (manual),
      prompt (ai), tone (ai)
    """
    mode      = request.form.get('mode', '').strip()
    platforms = request.form.get('platforms', '').strip()
    scheduled = parse_scheduled_time(request.form.get('scheduled_time', ''))

    if not mode:
        return jsonify({'status': 'error', 'message': 'mode is required'}), 400
    if not platforms:
        return jsonify({'status': 'error', 'message': 'platforms is required'}), 400
    if not scheduled:
        return jsonify({'status': 'error', 'message': 'scheduled_time is required for queue'}), 400

    if mode == 'ai':
        prompt = request.form.get('prompt', '').strip()
        tone   = request.form.get('tone', '').strip()
        if not prompt:
            return jsonify({'status': 'error', 'message': 'prompt is required'}), 400
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO posts (mode, platforms, prompt, tone, scheduled_time) VALUES (?,?,?,?,?)",
                ('ai', platforms, prompt, tone, scheduled)
            )
            conn.commit()
            post_id = cur.lastrowid
        return jsonify({'status': 'success', 'message': 'Added to queue', 'id': post_id})

    elif mode == 'manual':
        caption = request.form.get('caption', '').strip()
        image   = request.files.get('image')
        if not caption:
            return jsonify({'status': 'error', 'message': 'caption is required'}), 400
        if not image or image.filename == '':
            return jsonify({'status': 'error', 'message': 'image is required'}), 400
        if not allowed_file(image.filename):
            return jsonify({'status': 'error', 'message': 'Only image files allowed'}), 400

        filename  = secure_filename(image.filename)
        save_path = os.path.join('post_images', filename)
        image.save(save_path)

        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO posts
                   (mode, platforms, caption, image_path, image_filename, image_mimetype, scheduled_time)
                   VALUES (?,?,?,?,?,?,?)""",
                ('manual', platforms, caption, save_path, filename, image.mimetype, scheduled)
            )
            conn.commit()
            post_id = cur.lastrowid
        return jsonify({'status': 'success', 'message': 'Added to queue', 'id': post_id})

    else:
        return jsonify({'status': 'error', 'message': f'Unknown mode: {mode}'}), 400


@app.route('/posts', methods=['GET'])
def list_posts():
    """Return all posts in the queue (newest first)."""
    status_filter = request.args.get('status')   # optional: pending|posted|failed
    with get_db() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM posts WHERE status=? ORDER BY scheduled_time ASC",
                (status_filter,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM posts ORDER BY scheduled_time ASC"
            ).fetchall()

    posts = []
    for r in rows:
        p = dict(r)
        p.pop('image_path', None)   # don't expose server paths
        posts.append(p)
    return jsonify({'status': 'success', 'posts': posts})


@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Cancel (delete) a pending post."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            return jsonify({'status': 'error', 'message': 'Post not found'}), 404
        if row['status'] != 'pending':
            return jsonify({'status': 'error', 'message': 'Only pending posts can be deleted'}), 400

        # Remove stored image if any
        if row['image_path'] and os.path.exists(row['image_path']):
            os.remove(row['image_path'])

        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.commit()
    return jsonify({'status': 'success', 'message': 'Post deleted'})


@app.route('/posts/<int:post_id>/fire', methods=['POST'])
def fire_now(post_id):
    """Manually trigger a pending post immediately."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            return jsonify({'status': 'error', 'message': 'Post not found'}), 404
        if row['status'] != 'pending':
            return jsonify({'status': 'error', 'message': 'Post is not pending'}), 400

    ok, msg = fire_post(dict(row))
    with get_db() as conn:
        conn.execute(
            "UPDATE posts SET status=?, fired_at=datetime('now'), error_msg=? WHERE id=?",
            ('posted' if ok else 'failed', None if ok else msg, post_id)
        )
        conn.commit()
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
