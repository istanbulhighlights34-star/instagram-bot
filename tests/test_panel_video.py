import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import imageio_ffmpeg
from PIL import Image
from test_panel import MemoryStore
from panel.video import prepare_video

class VideoStore(MemoryStore):
    def __init__(self):
        super().__init__();self.meta={};self.raw={};self.video={}
    def metadata(self, job_id): return self.meta.get(job_id, {'kind':'photo','phase':'prepared'})
    def get(self, job_id): return dict(super().get(job_id), **self.metadata(job_id))
    def save_metadata(self, job_id, kind, phase): self.meta[job_id]={'kind':kind,'phase':phase}
    def upload_video(self, job_id, content, raw=False): (self.raw if raw else self.video)[job_id]=content
    def download_video(self, job_id, raw=False): return (self.raw if raw else self.video)[job_id]
    def remove_raw_video(self, job_id): self.raw.pop(job_id,None)

class VideoTests(unittest.TestCase):
    def test_real_video_processing_for_feed_and_reel_preserves_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=240x320:rate=15','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','2','-c:v','libx264','-c:a','aac',str(source)],check=True)
            for kind,expected in [('video',(720,900)),('reel',(720,1280))]:
                final=Path(folder)/(kind+'.mp4');prepare_video(source,final,kind)
                reader=imageio_ffmpeg.read_frames(str(final));info=next(reader);frame=next(reader);reader.close()
                self.assertEqual(info['size'],expected)
                self.assertAlmostEqual(info['duration'],2,delta=.2)
                frame_image=Image.frombytes('RGB',expected,frame)
                self.assertGreater(len(frame_image.crop((0,0,720,146)).getcolors(1000000)),100)
                details=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-i',str(final)],capture_output=True,text=True).stderr
                self.assertIn('Audio: aac',details)
    def test_preview_never_publishes_and_reel_uses_clip_upload_once(self):
        from panel.worker import run
        env={'SUPABASE_URL':'https://test.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test','IG_USERNAME':'test','IG_PASSWORD':'test','IG_SESSION':'{}','CHECK_ONLY':'false'}
        store=VideoStore();job='12345678-1234-1234-1234-123456789abc'
        store.insert({'id':job,'caption':'Test','status':'processing'});store.save_metadata(job,'reel','raw');store.raw[job]=b'raw'
        client=Mock();client.clip_upload.return_value=Mock(pk=123,code='reelcode')
        def fake_prepare(source,destination,kind): destination.write_bytes(b'branded')
        with patch.dict(os.environ,env),patch('panel.worker.prepare_video',side_effect=fake_prepare):
            run(store,lambda:client)
            self.assertEqual(store.get(job)['status'],'ready');client.clip_upload.assert_not_called()
            self.assertNotIn(job,store.raw)
            store.change(job,'ready',status='queued');run(store,lambda:client);run(store,lambda:client)
            client.clip_upload.assert_called_once();client.photo_upload.assert_not_called()
            self.assertEqual(store.get(job)['status'],'published')
    def test_invalid_video_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'bad.mp4';source.write_bytes(b'not a video')
            with self.assertRaises((ValueError,OSError,RuntimeError)):
                prepare_video(source,Path(folder)/'out.mp4','reel')
