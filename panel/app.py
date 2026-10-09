"""Single-owner photo panel. Instagram credentials stay in GitHub Actions."""
import functools
import hmac
import io
import os
from pathlib import Path
import secrets
import tempfile
import time
import uuid
import base64
from collections import defaultdict
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image, UnidentifiedImageError
from bot import render_free_design, apply_claw_branding
from panel.store import Store


def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('PANEL_SESSION_SECRET'),
                      MAX_CONTENT_LENGTH=46 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_SAMESITE='Strict', PERMANENT_SESSION_LIFETIME=3600)
    attempts = defaultdict(list)

    def csrf():
        if not session.get('csrf'):
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    app.jinja_env.globals['csrf'] = csrf

    @app.before_request
    def checks():
        if request.path == '/health':
            return
        if not app.secret_key or not os.environ.get('PANEL_PASSWORD'):
            return 'Panel giriş ayarları tamamlanmadı.', 503
        if request.method == 'POST':
            submitted = request.headers.get('X-CSRF-Token') or request.form.get('csrf', '')
            if not hmac.compare_digest(submitted, session.get('csrf', '')) or not submitted:
                abort(403)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
        return response

    def protected(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('owner'):
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapped

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.get('/brand-logo')
    def brand_logo():
        logo = Path(__file__).resolve().parents[1] / 'media' / 'kartalpenche1903-logo.b64'
        return send_file(io.BytesIO(base64.b64decode(logo.read_text())), mimetype='image/png')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            ip = request.remote_addr or 'unknown'
            now = time.monotonic()
            attempts[ip] = [t for t in attempts[ip] if now - t < 600]
            if len(attempts[ip]) >= 5:
                return render_template('login.html', error='Çok fazla deneme. 10 dakika sonra tekrar deneyin.'), 429
            attempts[ip].append(now)
            if hmac.compare_digest(request.form.get('password', '').encode(), os.environ['PANEL_PASSWORD'].encode()):
                session.clear()
                session['owner'] = True
                session.permanent = True
                csrf()
                attempts.pop(ip, None)
                return redirect(url_for('index'))
            error = 'Panel şifresi doğru değil.'
        return render_template('login.html', error=error)

    @app.post('/logout')
    @protected
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @protected
    def index():
        try:
            posts = Store().rows(order='created_at.desc', limit='20')
            return render_template('index.html', posts=posts)
        except RuntimeError:
            return render_template('index.html', posts=[], setup=True)

    @app.post('/preview')
    @protected
    def preview():
        caption = request.form.get('caption', '').strip()
        if not caption or len(caption) > 2200:
            return render_template('error.html', message='Açıklama 1–2200 karakter olmalı.'), 400
        upload = request.files.get('photo')
        if not upload:
            return render_template('error.html', message='Bir fotoğraf seçin.'), 400
        kind = request.form.get('kind', 'photo')
        if kind not in ('photo','video','reel'):
            abort(400)
        if kind in ('video','reel'):
            raw = upload.read(45 * 1024 * 1024 + 1)
            if len(raw) > 45 * 1024 * 1024 or upload.filename.rsplit('.',1)[-1].lower() not in ('mp4','mov'):
                return render_template('error.html', message='MP4 veya MOV video seçin; en fazla 45 MB ve 60 saniye olabilir.'),400
            store = Store()
            job_id = str(uuid.uuid4())
            store.upload_video(job_id, raw, raw=True)
            try:
                store.save_metadata(job_id, kind, 'raw')
                store.insert({'id':job_id,'caption':caption,'status':'processing'})
            except Exception:
                store.delete(job_id)
                raise
            return redirect(url_for('post',job_id=job_id))
        raw = upload.read(15 * 1024 * 1024 + 1)
        if len(raw) > 15 * 1024 * 1024:
            return render_template('error.html', message='Fotoğraf en fazla 15 MB olabilir.'), 400
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 60000000:
                    raise ValueError('Fotoğraf biçimi veya boyutu uygun değil.')
                image.verify()
            with tempfile.TemporaryDirectory(prefix='kartal-preview-') as temp:
                source, frame, final = [Path(temp) / f for f in ('source', 'frame.jpg', 'final.jpg')]
                source.write_bytes(raw)
                render_free_design(source, frame, '')
                apply_claw_branding(frame, final)
                content = final.read_bytes()
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
            return render_template('error.html', message='JPEG, PNG veya WebP fotoğraf seçin. HEIC fotoğrafı önce JPEG olarak dışa aktarın.'), 400
        store = Store()
        job_id = str(uuid.uuid4())
        store.upload(job_id, content)
        try:
            store.insert({'id': job_id, 'caption': caption, 'status': 'ready'})
        except Exception:
            store.delete(job_id)
            raise
        return redirect(url_for('post', job_id=job_id))

    @app.get('/posts/<job_id>')
    @protected
    def post(job_id):
        return render_template('post.html', post=Store().get(job_id))

    @app.get('/posts/<job_id>/image')
    @protected
    def image(job_id):
        item = Store().get(job_id)
        if item.get('kind') in ('video','reel'):
            if item['phase'] != 'prepared':
                abort(409)
            return send_file(io.BytesIO(Store().download_video(job_id)),mimetype='video/mp4',conditional=True)
        return send_file(io.BytesIO(Store().download(job_id)), mimetype='image/jpeg')

    @app.get('/posts/<job_id>/status')
    @protected
    def status(job_id):
        item = Store().get(job_id)
        return jsonify(status=item['status'], instagram_url=item.get('instagram_url'), error=item.get('error'))

    @app.post('/posts/<job_id>/publish')
    @protected
    def publish(job_id):
        # Atomic transition: repeat taps cannot create a second queued publication.
        Store().change(job_id, 'ready', status='queued')
        return redirect(url_for('post', job_id=job_id))

    @app.post('/posts/<job_id>/delete')
    @protected
    def delete(job_id):
        store = Store()
        item = store.get(job_id)
        if item['status'] not in ('ready', 'published', 'failed', 'queued'):
            abort(409)
        if not store.change(job_id, item['status'], status='deleting'):
            abort(409)
        store.delete(job_id)
        store.change(job_id, 'deleting', status='deleted')
        return redirect(url_for('index'))

    @app.errorhandler(413)
    def too_large(_error):
        return render_template('error.html', message='Fotoğraf en fazla 15 MB olabilir.'), 413

    @app.errorhandler(LookupError)
    @app.errorhandler(ValueError)
    def not_found(_error):
        return render_template('error.html', message='Gönderi bulunamadı.'), 404

    @app.errorhandler(RuntimeError)
    def service_error(_error):
        return render_template('error.html', message='Özel dosya alanına ulaşılamadı. Lütfen daha sonra yeniden deneyin.'), 503

    return app

app = create_app()
