"""Private storage and atomic queue transitions through Supabase's service API."""
import os
import re
import requests

ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

class Store:
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        if not self.url.startswith('https://') or not self.key:
            raise RuntimeError('Özel dosya alanı henüz bağlanmadı.')
        self.headers = {'apikey': self.key}
        if not self.key.startswith('sb_secret_'):
            self.headers['Authorization'] = 'Bearer ' + self.key

    def call(self, method, path, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop('headers', {}))
        response = requests.request(method, self.url + path, headers=headers, timeout=(10, 60), **kwargs)
        if not response.ok:
            raise RuntimeError('Dosya alanı işlemi tamamlanamadı (HTTP %s).' % response.status_code)
        return response

    def rows(self, **params):
        return self.call('GET', '/rest/v1/panel_posts', params=params).json()

    def get(self, job_id):
        if not ID.fullmatch(job_id):
            raise ValueError('Geçersiz gönderi.')
        rows = self.rows(id='eq.' + job_id, limit='1')
        if not rows:
            raise LookupError('Gönderi bulunamadı.')
        return rows[0]

    def insert(self, data):
        self.call('POST', '/rest/v1/panel_posts', json=data)

    def change(self, job_id, old, **data):
        if not ID.fullmatch(job_id):
            raise ValueError('Geçersiz gönderi.')
        return self.call('PATCH', '/rest/v1/panel_posts', params={'id': 'eq.' + job_id, 'status': 'eq.' + old},
                         headers={'Prefer': 'return=representation'}, json=data).json()

    def object_path(self, job_id):
        if not ID.fullmatch(job_id):
            raise ValueError('Geçersiz gönderi.')
        return '/storage/v1/object/kartal-panel/' + job_id + '.jpg'

    def upload(self, job_id, content):
        self.call('POST', self.object_path(job_id), data=content,
                  headers={'Content-Type': 'image/jpeg', 'x-upsert': 'false'})

    def download(self, job_id):
        response = self.call('GET', self.object_path(job_id), stream=True)
        with response:
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 15 * 1024 * 1024:
                    raise ValueError('Görsel boyutu sınırı aşıldı.')
        return bytes(content)

    def delete(self, job_id):
        self.call('DELETE', '/storage/v1/object/kartal-panel', json={'prefixes': [job_id + '.jpg']})
