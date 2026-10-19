"""Corg.ly survey demo. Run locally with Python 3.10 or newer."""
import json
import os
import sqlite3
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB = os.environ.get('CORGLY_DB', str(ROOT / 'surveys.sqlite3'))

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db

def initialize():
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS polls
        (id INTEGER PRIMARY KEY, question TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS options
        (id INTEGER PRIMARY KEY, poll_id INTEGER NOT NULL REFERENCES polls(id),
        label TEXT NOT NULL, votes INTEGER NOT NULL DEFAULT 0);''')

class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def poll_result(db, poll_id):
    row = db.execute('SELECT * FROM polls WHERE id=?', (poll_id,)).fetchone()
    if row is None:
        raise ApiError(404, 'Санал асуулга олдсонгүй.')
    options = [dict(r) for r in db.execute(
        'SELECT id,label,votes FROM options WHERE poll_id=? ORDER BY id', (poll_id,))]
    return dict(id=row['id'], question=row['question'], options=options,
                total_votes=sum(o['votes'] for o in options))

def dispatch(method, path, data):
    with connect() as db:
        if method == 'GET' and path == '/api/polls':
            return 200, [poll_result(db, r[0]) for r in db.execute('SELECT id FROM polls ORDER BY id DESC')]
        if method == 'POST' and path == '/api/polls':
            q, opts = data.get('question'), data.get('options')
            if not isinstance(q, str) or not 1 <= len(q.strip()) <= 200:
                raise ApiError(400, 'Асуултаа 1–200 тэмдэгтээр бичнэ үү.')
            if not isinstance(opts, list) or not 2 <= len(opts) <= 6 or any(
                not isinstance(x, str) or not 1 <= len(x.strip()) <= 80 for x in opts):
                raise ApiError(400, '2–6 сонголт оруулна уу. Сонголт бүр 1–80 тэмдэгт байна.')
            opts = [x.strip() for x in opts]
            if len(set(x.casefold() for x in opts)) != len(opts):
                raise ApiError(400, 'Давхардсан сонголтоо өөрчилнө үү.')
            pid = db.execute('INSERT INTO polls(question) VALUES(?)', (q.strip(),)).lastrowid
            db.executemany('INSERT INTO options(poll_id,label) VALUES(?,?)', [(pid, x) for x in opts])
            return 201, poll_result(db, pid)
        parts = path.strip('/').split('/')
        if len(parts) in (3, 4) and parts[:2] == ['api', 'polls'] and parts[2].isdigit():
            pid = int(parts[2])
            poll = poll_result(db, pid)
            if method == 'GET' and len(parts) == 3:
                return 200, poll
            if method == 'POST' and parts[3:] == ['votes']:
                oid = data.get('option_id')
                if type(oid) is not int or oid not in [o['id'] for o in poll['options']]:
                    raise ApiError(400, 'Жагсаалтаас нэг сонголт сонгоно уу.')
                db.execute('UPDATE options SET votes=votes+1 WHERE id=? AND poll_id=?', (oid, pid))
                return 200, poll_result(db, pid)
            if method == 'POST' and parts[3:] == ['slack']:
                url = os.environ.get('SLACK_WEBHOOK_URL', '')
                if not url:
                    raise ApiError(503, 'Slack холболтыг сервер дээр тохируулна уу.')
                if not url.startswith('https://hooks.slack.com/services/'):
                    raise ApiError(503, 'Slack webhook хаягийн тохиргоог шалгана уу.')
                summary = poll['question'] + '\n' + '\n'.join(
                    f"{o['label']}: {o['votes']}" for o in poll['options'])
                payload = json.dumps({'text': summary}).encode()
                req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status != 200 or response.read().strip() != b'ok':
                            raise ValueError('Unexpected Slack response')
                except Exception:
                    raise ApiError(502, 'Slack руу илгээж чадсангүй. Холболтоо шалгаад дахин оролдоно уу.')
                return 200, {'ok': True}
        raise ApiError(404, 'API зам олдсонгүй.')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def respond(self, status, payload, content_type='application/json; charset=utf-8'):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def handle_api(self):
        try:
            data = {}
            if self.command == 'POST':
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 16384:
                        raise ValueError()
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError()
                except (ValueError, UnicodeDecodeError):
                    raise ApiError(400, 'Зөв JSON объект илгээнэ үү. Дээд хэмжээ 16 KB.')
            status, body = dispatch(self.command, self.path.split('?')[0], data)
            self.respond(status, body)
        except ApiError as e:
            self.respond(e.status, {'error': e.message})
        except Exception:
            self.respond(500, {'error': 'Серверийн алдаа гарлаа. Дахин оролдоно уу.'})

    def do_GET(self):
        if self.path.split('?')[0] == '/':
            self.respond(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        else:
            self.handle_api()

    def do_POST(self):
        self.handle_api()

if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', '8000'))
    print(f'Corg.ly: http://127.0.0.1:{port}', flush=True)
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()
