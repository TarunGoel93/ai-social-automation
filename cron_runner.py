import os
import requests
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL    = os.environ['DATABASE_URL']
N8N_WEBHOOK_URL = os.environ['N8N_WEBHOOK_URL']

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def fire_post(post):
    try:
        if post['mode'] == 'ai':
            resp = requests.post(N8N_WEBHOOK_URL, json={
                'mode': 'ai', 'prompt': post['prompt'] or '',
                'tone': post['tone'] or '', 'platforms': post['platforms'],
            }, timeout=15)
            resp.raise_for_status()
            return True, 'ok'
        else:
            img_path = post['image_path']
            if not img_path or not os.path.exists(img_path):
                return False, 'Image not found'
            with open(img_path, 'rb') as f:
                resp = requests.post(N8N_WEBHOOK_URL,
                    files={'image': (post['image_filename'], f, post['image_mimetype'] or 'image/jpeg')},
                    data={'mode': 'manual', 'caption': post['caption'] or '', 'platforms': post['platforms']},
                    timeout=15)
                resp.raise_for_status()
            return True, 'ok'
    except Exception as e:
        return False, str(e)

def run():
    now = datetime.now(timezone.utc)
    print(f"[cron] Running at {now.isoformat()}")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM posts WHERE status='pending' AND scheduled_time <= %s", (now,)
            )
            due = cur.fetchall()
    print(f"[cron] Found {len(due)} due post(s)")
    for post in due:
        post = dict(post)
        print(f"[cron] Firing post id={post['id']} mode={post['mode']}")
        ok, msg = fire_post(post)
        print(f"[cron] id={post['id']} → {'OK' if ok else 'FAIL'}: {msg}")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET status=%s, fired_at=NOW(), error_msg=%s WHERE id=%s",
                    ('posted' if ok else 'failed', None if ok else msg, post['id'])
                )
            conn.commit()

if __name__ == '__main__':
    run()
