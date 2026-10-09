"""Publish only owner-approved jobs. No automatic retry after an upload starts."""
import os
from pathlib import Path
import tempfile
from instagrapi import Client
import json
from panel.store import Store


def run(store=None, client_factory=Client):
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        print('Panel dosya alanı henüz bağlı değil; işlem yapılmadı.')
        return
    store = store or Store()
    candidates = store.rows(status='eq.queued', order='created_at.asc', limit='1')
    if not candidates:
        print('Onaylanmış panel gönderisi yok.')
        return
    job = candidates[0]
    job_id = job['id']
    if not store.change(job_id, 'queued', status='processing'):
        return
    uploading = False
    try:
        content = store.download(job_id)
        with tempfile.TemporaryDirectory(prefix='kartal-panel-') as folder:
            image = Path(folder) / 'post.jpg'
            image.write_bytes(content)
            client = client_factory()
            settings = json.loads(os.environ['IG_SESSION'])
            if not isinstance(settings, dict):
                raise ValueError('Oturum biçimi uygun değil.')
            client.set_settings(settings)
            client.login(os.environ['IG_USERNAME'], os.environ['IG_PASSWORD'])
            if not store.change(job_id, 'processing', status='uploading'):
                return
            uploading = True
            media = client.photo_upload(str(image), job['caption'])
            if not media or not getattr(media, 'pk', None) or not getattr(media, 'code', None):
                raise RuntimeError('Instagram sonucu doğrulanamadı.')
            store.change(job_id, 'uploading', status='published', media_id=str(media.pk),
                         instagram_url='https://www.instagram.com/p/' + media.code + '/')
            print('Panel gönderisi Instagram tarafından doğrulandı. Medya kimliği: ' + str(media.pk))
    except Exception as exc:
        # An uncertain response must never be blindly retried (duplicate post risk).
        state = 'uploading' if uploading else 'processing'
        try:
            store.change(job_id, state, status='uncertain' if uploading else 'failed',
                         error='Paylaşım sonucu belirsiz; Instagram hesabını kontrol edin.' if uploading else 'Paylaşım başlamadı. Giriş veya dosya bağlantısı kontrol edilmeli.')
        except Exception:
            pass
        print('Panel işlemi tamamlanamadı. Hata türü: ' + type(exc).__name__)
        raise SystemExit(1) from None

if __name__ == '__main__':
    run()
