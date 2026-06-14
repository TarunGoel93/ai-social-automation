import os
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://intellifytechnology.app.n8n.cloud/webhook/0e383072-9f3d-4da2-8e47-ca164ae15191')
DATABASE_URL    = os.getenv('DATABASE_URL')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('post_images', exist_ok=True)


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id             SERIAL PRIMARY KEY,
                    mode           TEXT NOT NULL,
                    platforms      TEXT NOT NULL,
                    caption        TEXT,
                    image_path     TEXT,
                    image_filename TEXT,
                    image_mimetype TEXT,
                    prompt         TEXT,
                    tone           TEXT,
                    scheduled_time TIMESTAMPTZ NOT NULL,
                    status         TEXT NOT NULL DEFAULT 'pending',
                    created_at     TIMESTAMPTZ DEFAULT NOW(),
                    fired_at       TIMESTAMPTZ,
                    error_msg      TEXT
                )
            """)
        conn.commit()

init_db()

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_scheduled_time(raw: str):
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

def fire_post(post: dict):
    try:
        if post['mode'] == 'ai':
            resp = requests.post(N8N_WEBHOOK_URL, json={
                'mode': 'ai',
                'prompt': post['prompt'] or '',
                'tone': post['tone'] or '',
                'platforms': post['platforms'],
            }, timeout=15)
            resp.raise_for_status()
            return True, 'Posted successfully!'
        else:
            img_path = post['image_path']
            if not img_path or not os.path.exists(img_path):
                return False, 'Image file not found on disk.'
            with open(img_path, 'rb') as f:
                resp = requests.post(N8N_WEBHOOK_URL,
                    files={'image': (post['image_filename'], f, post['image_mimetype'] or 'image/jpeg')},
                    data={'mode': 'manual', 'caption': post['caption'] or '', 'platforms': post['platforms']},
                    timeout=15)
                resp.raise_for_status()
            return True, 'Posted successfully!'
    except requests.exceptions.ConnectionError:
        return False, 'n8n webhook unreachable'
    except requests.exceptions.RequestException as e:
        return False, f'Webhook error: {e}'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')



@app.route('/health')
def health():
    try:
        # Just check DB connection, don't ping n8n webhook
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({
            'status': 'ok',
            'message': 'DB connected',
            'webhook_url': N8N_WEBHOOK_URL
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/run-cron', methods=['GET', 'POST'])
def run_cron():
    """Called by cron-job.org every 5 minutes to fire due posts."""
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM posts WHERE status='pending' AND scheduled_time <= %s",
                (now,)
            )
            due = cur.fetchall()

    fired = 0
    results = []
    for post in due:
        post = dict(post)
        ok, msg = fire_post(post)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET status=%s, fired_at=NOW(), error_msg=%s WHERE id=%s",
                    ('posted' if ok else 'failed', None if ok else msg, post['id'])
                )
            conn.commit()
        fired += 1
        results.append({
            'id': post['id'],
            'status': 'posted' if ok else 'failed',
            'message': msg
        })

    return jsonify({
        'status': 'ok',
        'fired': fired,
        'checked_at': now.isoformat(),
        'results': results
    })

@app.route('/submit', methods=['POST'])
def submit():
    mode = request.form.get('mode') or (request.get_json(silent=True) or {}).get('mode')
    if not mode:
        return jsonify({'status': 'error', 'message': 'No mode specified.'}), 400

    if mode == 'ai':
        data      = request.get_json(silent=True) or {}
        prompt    = data.get('prompt', '').strip()
        tone      = data.get('tone', '').strip()
        platforms = data.get('platforms', '').strip()
        scheduled = parse_scheduled_time(data.get('scheduled_time', ''))

        if not prompt:    return jsonify({'status': 'error', 'message': 'Post idea cannot be empty.'}), 400
        if not platforms: return jsonify({'status': 'error', 'message': 'Please select a platform.'}), 400

        if scheduled:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO posts (mode,platforms,prompt,tone,scheduled_time) VALUES (%s,%s,%s,%s,%s)",
                        ('ai', platforms, prompt, tone, scheduled)
                    )
                conn.commit()
            return jsonify({'status': 'success', 'message': f'Queued for {scheduled.strftime("%b %d %H:%M")}!'})

        try:
            resp = requests.post(N8N_WEBHOOK_URL,
                json={'mode':'ai','prompt':prompt,'tone':tone,'platforms':platforms}, timeout=15)
            resp.raise_for_status()
            return jsonify({'status': 'success', 'message': 'Posted successfully!'})
        except requests.exceptions.ConnectionError:
            return jsonify({'status': 'success', 'message': 'Submitted! (webhook offline)'})
        except requests.exceptions.RequestException as e:
            return jsonify({'status': 'error', 'message': f'Webhook error: {e}'}), 502

    elif mode == 'manual':
        caption   = request.form.get('caption', '').strip()
        platforms = request.form.get('platforms', '').strip()
        scheduled = parse_scheduled_time(request.form.get('scheduled_time', ''))
        image     = request.files.get('image')

        if not caption:                      return jsonify({'status': 'error', 'message': 'Caption cannot be empty.'}), 400
        if not platforms:                    return jsonify({'status': 'error', 'message': 'Please select a platform.'}), 400
        if not image or not image.filename:  return jsonify({'status': 'error', 'message': 'Please upload an image.'}), 400
        if not allowed_file(image.filename): return jsonify({'status': 'error', 'message': 'Only image files are allowed.'}), 400

        filename = secure_filename(image.filename)

        if scheduled:
            save_path = os.path.join('post_images', filename)
            image.save(save_path)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO posts (mode,platforms,caption,image_path,image_filename,image_mimetype,scheduled_time)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        ('manual', platforms, caption, save_path, filename, image.mimetype, scheduled)
                    )
                conn.commit()
            return jsonify({'status': 'success', 'message': f'Queued for {scheduled.strftime("%b %d %H:%M")}!'})

        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(save_path)
        try:
            with open(save_path, 'rb') as f:
                resp = requests.post(N8N_WEBHOOK_URL,
                    files={'image': (filename, f, image.mimetype)},
                    data={'mode':'manual','caption':caption,'platforms':platforms},
                    timeout=15)
                resp.raise_for_status()
            return jsonify({'status': 'success', 'message': 'Posted successfully!'})
        except requests.exceptions.ConnectionError:
            return jsonify({'status': 'success', 'message': 'Submitted! (webhook offline)'})
        except requests.exceptions.RequestException as e:
            return jsonify({'status': 'error', 'message': f'Webhook error: {e}'}), 502
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    return jsonify({'status': 'error', 'message': f'Unknown mode: {mode}'}), 400

@app.route('/posts', methods=['GET'])
def list_posts():
    status_filter = request.args.get('status')
    with get_db() as conn:
        with conn.cursor() as cur:
            if status_filter:
                cur.execute("SELECT * FROM posts WHERE status=%s ORDER BY scheduled_time ASC", (status_filter,))
            else:
                cur.execute("SELECT * FROM posts ORDER BY scheduled_time ASC")
            rows = cur.fetchall()
    posts = []
    for r in rows:
        p = dict(r)
        p.pop('image_path', None)
        for k, v in p.items():
            if isinstance(v, datetime):
                p[k] = v.isoformat()
        posts.append(p)
    return jsonify({'status': 'success', 'posts': posts})

@app.route('/debug-posts')
def debug_posts():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, mode, caption, scheduled_time, status, fired_at, error_msg, created_at, NOW() as server_now FROM posts ORDER BY created_at DESC LIMIT 5")
            rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        out.append(d)
    return jsonify(out)

@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM posts WHERE id=%s", (post_id,))
            row = cur.fetchone()
        if not row:
            return jsonify({'status': 'error', 'message': 'Post not found'}), 404
        if row['status'] != 'pending':
            return jsonify({'status': 'error', 'message': 'Only pending posts can be deleted'}), 400
        if row['image_path'] and os.path.exists(row['image_path']):
            os.remove(row['image_path'])
        with conn.cursor() as cur:
            cur.execute("DELETE FROM posts WHERE id=%s", (post_id,))
        conn.commit()
    return jsonify({'status': 'success', 'message': 'Post deleted'})

@app.route('/posts/<int:post_id>/fire', methods=['POST'])
def fire_now(post_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM posts WHERE id=%s", (post_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({'status': 'error', 'message': 'Post not found'}), 404
    if row['status'] != 'pending':
        return jsonify({'status': 'error', 'message': 'Post is not pending'}), 400
    ok, msg = fire_post(dict(row))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status=%s, fired_at=NOW(), error_msg=%s WHERE id=%s",
                ('posted' if ok else 'failed', None if ok else msg, post_id)
            )
        conn.commit()
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
