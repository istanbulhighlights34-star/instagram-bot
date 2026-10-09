"""Publish only owner-approved jobs. No automatic retry after an upload starts."""
import os
from pathlib import Path
import tempfile
from instagrapi import Client
import json
from panel.store import Store
from panel.video import prepare_video


def prepare_next_video(store):
    for job in store.rows(status='eq.processing', order='created_at.asc', limit='10'):
        meta = store.metadata(job['id'])
        if meta['kind'] not in ('video','reel') or meta['phase'] != 'raw':
            continue
        job_id = job['id']
        if not store.change(job_id, 'processing', status='uploading'):
            continue
        try:
            with tempfile.TemporaryDirectory(prefix='kartal-video-') as folder:
                source, final = Path(folder)/'source.mp4', Path(folder)/'branded.mp4'
                source.write_bytes(store.download_video(job_id, raw=True))
                prepare_video(source, final, meta['kind'])
                store.upload_video(job_id, final.read_bytes())
                store.save_metadata(job_id, meta['kind'], 'prepared')
                store.change(job_id, 'uploading', status='ready')
                store.remove_raw_video(job_id)
            print('Filigranlı video önizlemesi hazır. Instagram paylaşımı yapılmadı.')
        except Exception as exc:
            store.change(job_id,'uploading',status='failed',error='Video hazırlanamadı. MP4/MOV, 1–60 saniye ve 45 MB sınırlarını kontrol edin.')
            print('Video önizleme hatası: '+type(exc).__name__)
        return


def run(store=None, client_factory=Client):
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        if os.getenv('CHECK_ONLY') == 'true':
            raise RuntimeError('GitHub panel bağlantı ayarları eksik.')
        print('Panel dosya alanı henüz bağlı değil; işlem yapılmadı.')
        return
    store = store or Store()
    if os.getenv('CHECK_ONLY') == 'true':
        store.rows(select='id', limit='1')
        bucket = store.call('GET', '/storage/v1/bucket/kartal-panel').json()
        if bucket.get('public') is not False:
            raise RuntimeError('Panel dosya alanı özel olmalı.')
        print('GitHub özel panel bağlantısı doğrulandı. Instagram paylaşımı yapılmadı.')
        return
    if hasattr(store, 'metadata'):
        prepare_next_video(store)
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
        meta = store.metadata(job_id) if hasattr(store,'metadata') else {'kind':'photo','phase':'prepared'}
        if meta['phase'] != 'prepared':
            raise ValueError('Önizleme tamamlanmalı.')
        video = meta['kind'] in ('video','reel')
        content = store.download_video(job_id) if video else store.download(job_id)
        with tempfile.TemporaryDirectory(prefix='kartal-panel-') as folder:
            image = Path(folder) / ('post.mp4' if video else 'post.jpg')
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
            if meta['kind'] == 'reel':
                media = client.clip_upload(image, job['caption'])
            elif meta['kind'] == 'video':
                media = client.video_upload(image, job['caption'])
            else:
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
