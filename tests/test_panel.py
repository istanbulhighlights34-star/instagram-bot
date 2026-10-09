import io
import os
import unittest
from unittest.mock import patch, Mock
from PIL import Image

class MemoryStore:
    def __init__(self): self.jobs, self.images = {}, {}
    def rows(self, **params): return [dict(j) for j in self.jobs.values() if not params.get('status') or j['status'] == params['status'][3:]]
    def insert(self, data): self.jobs[data['id']] = dict(data, created_at='2026-10-09T12:00:00Z')
    def get(self, job_id): return dict(self.jobs[job_id])
    def change(self, job_id, old, **data):
        if self.jobs[job_id]['status'] != old: return []
        self.jobs[job_id].update(data); return [self.get(job_id)]
    def upload(self, job_id, content): self.images[job_id] = content
    def download(self, job_id): return self.images[job_id]
    def delete(self, job_id): self.images.pop(job_id, None)

class PanelTests(unittest.TestCase):
    def setUp(self):
        holiday_guard = patch("special_days.first_post_pending", return_value=False)
        holiday_guard.start(); self.addCleanup(holiday_guard.stop)
        self.env = patch.dict(os.environ, {'PANEL_PASSWORD':'test-only-password','PANEL_SESSION_SECRET':'test-only-session','SUPABASE_URL':'https://example.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test-only-key','IG_USERNAME':'test','IG_PASSWORD':'test','IG_SESSION':'{}'})
        self.env.start()
        from panel.app import create_app
        self.app = create_app(); self.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = self.app.test_client();self.store = MemoryStore()
        self.mock = patch('panel.app.Store', return_value=self.store);self.mock.start()
    def tearDown(self): self.mock.stop(); self.env.stop()
    def token(self):
        with self.client.session_transaction() as session: return session['csrf']
    def login(self):
        self.client.get('/login')
        return self.client.post('/login', data={'password':'test-only-password','csrf':self.token()})
    def prepare(self):
        self.login();data = io.BytesIO();Image.new('RGB',(400,600),'#99aacc').save(data,'PNG');data.seek(0)
        response = self.client.post('/preview',data={'csrf':self.token(),'caption':'Tribündeyiz! 🦅','photo':(data,'photo.png')})
        self.assertEqual(response.status_code,302);return next(iter(self.store.jobs))
    def test_private_routes_and_csrf(self):
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertEqual(self.client.post('/preview').status_code,403)
        self.assertEqual(self.login().status_code,302)
        self.assertEqual(self.client.post('/preview',data={'caption':'x'}).status_code,403)
    def test_preview_does_not_queue_and_double_click_queues_once(self):
        job_id = self.prepare();self.assertEqual(self.store.get(job_id)['status'],'ready')
        with Image.open(io.BytesIO(self.store.images[job_id])) as image:
            self.assertEqual(image.size,(1080,1080));self.assertEqual(image.format,'JPEG')
        self.assertEqual(self.client.get('/posts/'+job_id).status_code,200)
        for _ in range(2): self.client.post('/posts/'+job_id+'/publish',data={'csrf':self.token()})
        self.assertEqual(self.store.get(job_id)['status'],'queued');self.assertEqual(len(self.store.jobs),1)
        self.assertEqual(self.client.post('/posts/'+job_id+'/delete',data={'csrf':self.token()}).status_code,302)
        self.assertEqual(self.store.get(job_id)['status'],'deleted')
    def test_invalid_upload_is_not_saved(self):
        self.login();response=self.client.post('/preview',data={'csrf':self.token(),'caption':'x','photo':(io.BytesIO(b'not an image'),'bad.jpg')})
        self.assertEqual(response.status_code,400);self.assertFalse(self.store.jobs)
    def test_published_once_and_no_retry_after_uncertain_upload(self):
        from panel.worker import run
        job_id = self.prepare();self.store.change(job_id,'ready',status='queued')
        client=Mock();client.photo_upload.return_value=Mock(pk=123,code='abc')
        run(self.store,lambda:client);run(self.store,lambda:client)
        self.assertEqual(client.photo_upload.call_count,1);self.assertEqual(self.store.get(job_id)['status'],'published')
        self.store.change(job_id,'published',status='queued');client.photo_upload.side_effect=TimeoutError()
        with self.assertRaises(SystemExit): run(self.store,lambda:client)
        self.assertEqual(self.store.get(job_id)['status'],'uncertain');run(self.store,lambda:client)
        self.assertEqual(client.photo_upload.call_count,2)
    def test_bad_login_never_uploads(self):
        from panel.worker import run
        job_id=self.prepare();self.store.change(job_id,'ready',status='queued');client=Mock();client.login.side_effect=RuntimeError()
        with self.assertRaises(SystemExit): run(self.store,lambda:client)
        self.assertEqual(self.store.get(job_id)['status'],'failed');client.photo_upload.assert_not_called()
    def test_delete_preview_does_not_publish(self):
        job_id=self.prepare();self.client.post('/posts/'+job_id+'/delete',data={'csrf':self.token()})
        self.assertEqual(self.store.get(job_id)['status'],'deleted');self.assertNotIn(job_id,self.store.images)

    def test_uploading_cannot_be_deleted(self):
        job_id=self.prepare();self.store.change(job_id,'ready',status='uploading')
        response=self.client.post('/posts/'+job_id+'/delete',data={'csrf':self.token()})
        self.assertEqual(response.status_code,409)
        self.assertIn(job_id,self.store.images)

    def test_deleted_posts_hidden_from_gallery(self):
        job_id=self.prepare();self.store.change(job_id,'ready',status='deleted')
        self.assertNotIn(('/posts/'+job_id).encode(),self.client.get('/').data)
