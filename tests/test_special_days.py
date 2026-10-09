from datetime import date, datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import special_days as sd


class SpecialDaysTests(unittest.TestCase):
    def setUp(self):
        quiet=patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':''})
        quiet.start();self.addCleanup(quiet.stop)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state=patch.object(sd,'STATE',Path(self.temp.name)/'state.json')
        self.state.start();self.addCleanup(self.state.stop)

    def test_verified_dates_and_different_christian_calendars(self):
        self.assertIn('republic',sd.events_on(date(2026,10,29)))
        self.assertIn('regaib',sd.events_on(date(2026,12,10)))
        self.assertIn('ramazan',sd.events_on(date(2027,3,9)))
        self.assertIn('mirac',sd.events_on(date(2027,12,24)))
        self.assertIn('youth',sd.events_on(date(2027,5,19)))
        self.assertIn('kurban',sd.events_on(date(2027,5,19)))
        self.assertEqual(sd.easter(2026),date(2026,4,5))
        self.assertEqual(sd.easter(2026,True),date(2026,4,12))
        self.assertEqual(sd.easter(2027),date(2027,3,28))
        self.assertEqual(sd.easter(2027,True),date(2027,5,2))

    def photo(self,event,path):
        Image.new('RGB',(900,1200),'#42aa73').save(path,'JPEG')
        return {'source':'https://example.test/photo'}

    def test_1030_utc_is_local_1330_and_10_november_starts_0830(self):
        with patch('special_days.download_photo',side_effect=self.photo),patch('bot.publish',return_value=123) as upload:
            sd.run(datetime(2026,11,10,5,29,tzinfo=timezone.utc))
            upload.assert_not_called()
            sd.run(datetime(2026,11,10,5,30,tzinfo=timezone.utc))
            upload.assert_called_once()
            sd.run(datetime(2026,11,10,6,5,tzinfo=timezone.utc))
            upload.assert_called_once()

    def test_normal_posts_wait_until_special_post_is_verified(self):
        now=datetime(2026,10,29,8,tzinfo=sd.ISTANBUL)
        self.assertTrue(sd.first_post_pending(now))
        sd.save_state({'2026-10-29:republic':{'status':'uncertain'}})
        self.assertTrue(sd.first_post_pending(now))
        sd.save_state({'2026-10-29:republic':{'status':'published'}})
        self.assertFalse(sd.first_post_pending(now))
        self.assertFalse(sd.first_post_pending(datetime(2026,10,30,8,tzinfo=sd.ISTANBUL)))

    def test_ambiguous_upload_is_never_retried(self):
        now=datetime(2026,10,29,8,tzinfo=sd.ISTANBUL)
        with patch('special_days.download_photo',side_effect=self.photo),patch('bot.publish',side_effect=TimeoutError) as upload:
            with self.assertRaises(TimeoutError):sd.run(now)
            sd.run(now)
            upload.assert_called_once()
            self.assertEqual(sd.read_state()['2026-10-29:republic']['status'],'uncertain')

    def test_no_claw_asset_or_brand_logo_in_special_renderer(self):
        source=Path(self.temp.name)/'source.jpg';output=source.with_name('card.jpg')
        self.photo('ataturk',source)
        with patch('bot.apply_claw_branding',side_effect=AssertionError),patch('bot.claw_mark',side_effect=AssertionError),patch('bot.brand_asset',side_effect=AssertionError):
            sd.render_card(source,output,'ataturk')
        with Image.open(output) as image:
            self.assertEqual(image.size,(1080,1350))
            r,g,b=image.getpixel((500,500))
            self.assertEqual(r,g);self.assertEqual(g,b)
        caption=sd.EVENTS['ataturk'][2]
        self.assertNotIn('kutlu',caption.lower())
        self.assertNotIn('🦅',caption)

    def test_missing_photo_does_not_publish_or_mark_history(self):
        with patch('special_days.download_photo',side_effect=RuntimeError),patch('bot.publish') as upload:
            with self.assertRaises(RuntimeError):sd.run(datetime(2026,10,29,8,tzinfo=sd.ISTANBUL))
            upload.assert_not_called()
            self.assertEqual(sd.read_state(),{})

    def test_custom_date_cannot_publish_for_real(self):
        with self.assertRaises(ValueError):sd.run(preview_date=date(2026,11,10))

    def test_istanbul_day_rollover_blocks_news_before_special(self):
        now=datetime(2026,10,28,21,1,tzinfo=timezone.utc)
        self.assertTrue(sd.first_post_pending(now))
        with patch('special_days.first_post_pending',return_value=True),patch('bot.get_latest_unposted_news') as news:
            import bot
            bot.post_news()
            news.assert_not_called()

    def test_new_year_incomplete_calendar_is_rejected(self):
        from unittest.mock import Mock
        response=Mock(content=b'<table><tr><td>empty</td></tr></table>')
        with patch('special_days.requests.get',return_value=response):
            with self.assertRaises(RuntimeError):sd.refresh_calendar(2030)

    def test_match_publishing_waits_for_special_day(self):
        import matches
        with patch('special_days.first_post_pending',return_value=True),patch('bot.publish') as upload:
            matches.run(object(),datetime(2026,10,29,8,tzinfo=sd.ISTANBUL))
            upload.assert_not_called()

    def test_queued_panel_post_waits_without_losing_approval(self):
        from unittest.mock import Mock
        from panel.worker import run
        from test_panel import MemoryStore
        store=MemoryStore();store.insert({'id':'queued','caption':'test','status':'queued'})
        client=Mock()
        with patch.dict(os.environ,{'SUPABASE_URL':'https://test.invalid','SUPABASE_SERVICE_ROLE_KEY':'fake','CHECK_ONLY':'false'}),patch('special_days.first_post_pending',return_value=True):
            run(store,lambda:client)
        self.assertEqual(store.get('queued')['status'],'queued')
        client.photo_upload.assert_not_called()

    def test_download_strips_thumbnail_tracking_and_preserves_source(self):
        from unittest.mock import Mock
        raw=io.BytesIO();Image.new('RGB',(600,700),'green').save(raw,'JPEG')
        search=Mock()
        search.json.return_value={'query':{'pages':{'1':{'index':1,'imageinfo':[{'url':'https://upload.wikimedia.org/photo.jpg?tracking=1','thumburl':'https://thumb.wikimedia.org/bad','extmetadata':{'LicenseShortName':{'value':'Public domain'}}}]}}}}
        photo=Mock();photo.__enter__=Mock(return_value=photo);photo.__exit__=Mock(return_value=False);photo.iter_content.return_value=[raw.getvalue()]
        destination=Path(self.temp.name)/'photo.jpg'
        with patch('special_days.requests.get',side_effect=[search,photo]) as get:
            sd.download_photo('ataturk',destination)
            self.assertEqual(get.call_args.args[0],'https://upload.wikimedia.org/photo.jpg')
            self.assertTrue(destination.exists())
