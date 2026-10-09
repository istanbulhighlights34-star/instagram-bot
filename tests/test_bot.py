import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import bot

class BotTests(unittest.TestCase):
    def setUp(self):
        # Tests must never emit production status to the Actions summary.
        self.summary_patch = patch.dict('os.environ', {'GITHUB_STEP_SUMMARY': ''})
        self.summary_patch.start()
        self.addCleanup(self.summary_patch.stop)
        self.catalog_patch = patch.object(bot, 'PLAYER_MEDIA_CATALOG', Path('/tmp/missing-test-player-catalog'))
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)
        self.article_patch = patch('bot.download_article_image', return_value=False)
        self.article_patch.start()
        self.addCleanup(self.article_patch.stop)
        self.branding_patch = patch('bot.apply_claw_branding', return_value=True)
        self.branding_patch.start()
        self.addCleanup(self.branding_patch.stop)
        self.web_patch = patch('bot.download_web_image', return_value=False)
        self.web_patch.start()
        self.addCleanup(self.web_patch.stop)

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    @patch('bot.time.sleep')
    @patch('bot.requests.post')
    def test_retries(self, post, sleep):
        for status in (503, 200):
            post.reset_mock()
            sleep.reset_mock()
            post.return_value = Mock(status_code=status)
            post.return_value.json.return_value = {'candidates': []}
            self.assertIsNone(bot.gemini_request('model', {}))
            self.assertEqual(post.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertNotIn('test-key', post.call_args.args[0])

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_failures_do_not_record(self):
        news = {'title': 'Başlık', 'summary': 'Özet', 'link': 'https://news.test/1'}
        for caption, image in ((None, True), ('Metin', False), ('Metin', True)):
            with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value=caption), patch('bot.generate_ai_image', return_value=image), patch('bot.download_article_image', return_value=image), patch('bot.publish', side_effect=RuntimeError('failed')) as publish, patch('bot.save_posted_news') as save:
                if caption and image:
                    with self.assertRaises(RuntimeError):
                        bot.post_news()
                    self.assertEqual(publish.call_count, 1)
                else:
                    bot.post_news()
                    publish.assert_not_called()
                save.assert_not_called()

    @patch('bot.gemini_request')
    def test_real_jpeg(self, request):
        stream = io.BytesIO()
        Image.new('RGB', (32, 32), 'black').save(stream, 'PNG')
        request.return_value = {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(stream.getvalue()).decode()}}]}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'image.jpg'
            self.assertTrue(bot.generate_ai_image('Haber', path))
            with Image.open(path) as picture:
                self.assertEqual(picture.format, 'JPEG')
                self.assertEqual(picture.size, (1080, 1080))

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_success_records_after_upload(self):
        news = {'title': 'Başlık', 'summary': 'Özet', 'link': 'https://news.test/1'}
        events = []
        with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.generate_ai_image', return_value=False), patch('bot.download_article_image', return_value=True), patch('bot.publish', side_effect=lambda *args: events.append('upload') or 123), patch('bot.save_posted_news', side_effect=lambda link: events.append('save')):
            bot.post_news()
        self.assertEqual(events, ['upload', 'save'])


    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_ai_error_uses_fallback_and_publishes(self):
        news = {'title': 'Başlık', 'summary': 'Özet', 'link': 'https://news.test/1'}
        for error in (False, RuntimeError('429 quota')):
            with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.generate_ai_image', side_effect=error if isinstance(error, Exception) else None, return_value=False), patch('bot.download_article_image', return_value=True) as fallback, patch('bot.publish', return_value=456) as publish, patch('bot.save_posted_news') as save:
                bot.post_news()
                fallback.assert_called_once()
                publish.assert_called_once()
                self.assertNotIn('Wikimedia', publish.call_args.args[1])
                self.assertNotIn('yapay zekâ ile üretilmiştir', publish.call_args.args[1])
                save.assert_called_once_with(news['link'])


    @patch('bot.gemini_request')
    def test_edit_sends_reference_and_preserves_original(self, request):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.jpg'
            Image.new('RGB', (400, 400), 'white').save(source, 'JPEG')
            original = source.read_bytes()
            request.return_value = None
            self.assertFalse(bot.generate_ai_image_unbounded('Miretti', Path(folder) / 'design.jpg', source))
            parts = request.call_args.args[1]['contents'][0]['parts']
            self.assertEqual(base64.b64decode(parts[1]['inlineData']['data']), original)
            self.assertIn('Preserve', parts[0]['text'])
            self.assertEqual(source.read_bytes(), original)

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_edit_failure_keeps_source_photo(self):
        self.branding_patch.stop()
        news = {'title': 'Miretti', 'summary': 'Özet', 'link': 'https://news.test/1'}
        def download(news, destination):
            Image.new('RGB', (400, 400), 'white').save(destination, 'JPEG')
            return True
        def publish(destination, caption):
            self.assertEqual(Path(destination).name, 'filigranli.jpg')
            self.assertTrue(Path(destination).is_file())
            return 123
        with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.download_article_image', side_effect=download), patch('bot.render_free_design', return_value=False), patch('bot.generate_ai_image') as paid, patch('bot.publish', side_effect=publish) as upload, patch('bot.save_posted_news'):
            bot.post_news()
            upload.assert_called_once()
            paid.assert_not_called()

    def test_free_design_output_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.jpg'; dest = Path(folder) / 'design.jpg'
            Image.new('RGB', (800, 500), 'green').save(source, 'JPEG')
            original = source.read_bytes()
            self.assertTrue(bot.render_free_design(source, dest, 'Beşiktaş için transfer iddiası'))
            self.assertEqual(source.read_bytes(), original)
            with Image.open(dest) as picture:
                self.assertEqual(picture.size, (1080, 1080))
                self.assertEqual(picture.format, 'JPEG')

    def test_rotation_excludes_used_and_last_at_boundary(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'FALLBACK_HISTORY', Path(folder) / 'history.txt'):
            bot.save_fallback_photo(bot.FALLBACK_PHOTOS[0])
            self.assertNotIn(bot.FALLBACK_PHOTOS[0], bot.fallback_candidates())
            for title in bot.FALLBACK_PHOTOS[1:]:
                bot.save_fallback_photo(title)
            self.assertNotIn(bot.FALLBACK_PHOTOS[-1], bot.fallback_candidates())
            self.assertEqual(len(bot.fallback_candidates()), len(bot.FALLBACK_PHOTOS) - 1)


    def test_hung_image_worker_is_terminated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'partial.jpg'
            path.write_bytes(b'partial')
            context = Mock()
            worker = context.Process.return_value
            worker.is_alive.side_effect = [True, False]
            with patch('bot.multiprocessing.get_context', return_value=context):
                self.assertFalse(bot.generate_ai_image('Haber', path))
            worker.terminate.assert_called_once()
            self.assertEqual(worker.join.call_args_list[0].kwargs['timeout'], 180)
            self.assertFalse(path.exists())


    def test_caption_club_tags_before_person_and_no_links(self):
        caption = bot.format_caption('Miretti hazır! https://news.test/a #Miretti #BJK #Miretti')
        self.assertTrue(caption.endswith('#Beşiktaş #BJK #KaraKartal #Miretti'))
        self.assertNotIn('https://', caption)
        self.assertEqual(caption.count('#Miretti'), 1)
        self.assertLessEqual(len(bot.format_caption('x' * 3000 + ' #Miretti')), 2200)


    def test_player_match_and_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / 'players'
            player = media / 'miretti'
            player.mkdir(parents=True)
            for filename in ('one.jpg', 'two.jpg'):
                Image.new('RGB', (80, 80), 'black').save(player / filename)
            catalog = root / 'players.json'
            catalog.write_text('{"players":[{"name":"Fabio Miretti","aliases":["Miretti"],"folder":"miretti"}]}')
            with patch.object(bot, 'PLAYER_MEDIA_ROOT', media), patch.object(bot, 'PLAYER_MEDIA_CATALOG', catalog), patch.object(bot, 'PLAYER_MEDIA_HISTORY', root / 'history.json'):
                first = bot.choose_player_photo("Beşiktaş'ta Miretti, 11'e göz kırptı!", root / 'image.jpg')
                self.assertEqual(first['status'], 'ready')
                bot.save_player_photo(first)
                second = bot.choose_player_photo('Miretti hazır', root / 'image.jpg')
                self.assertNotEqual(first['key'], second['key'])
                self.assertEqual(bot.choose_player_photo('Mirettininho transferi', root / 'image.jpg')['status'], 'no-match')



    def test_article_image_metadata(self):
        parser = bot.ArticleImageParser()
        parser.feed('<meta content="/miretti.jpg" property="og:image"><meta name="twitter:image" content="/miretti.jpg">')
        self.assertEqual(parser.images, ['/miretti.jpg'])

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_article_cover_is_last_resort(self):
        news = {'title': 'Miretti', 'summary': 'Özet', 'link': 'https://news.test/1'}
        with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.download_article_image', return_value=True) as article, patch('bot.generate_ai_image', return_value=False) as ai, patch('bot.download_fallback_image') as fallback, patch('bot.publish', return_value=789), patch('bot.save_posted_news'):
            bot.post_news()
            article.assert_called_once()
            ai.assert_not_called()
            fallback.assert_not_called()



    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_photo_before_local_design_order(self):
        news = {'title': 'Miretti', 'summary': 'Özet', 'link': 'https://news.test/1'}
        calls = []
        with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.render_free_design', side_effect=lambda *a, **kw: calls.append('design') or False), patch('bot.download_web_image', side_effect=lambda *a: calls.append('web') or False), patch('bot.download_article_image', side_effect=lambda *a: calls.append('article') or True), patch('bot.publish', return_value=123), patch('bot.save_posted_news'):
            bot.post_news()
        self.assertEqual(calls, ['web', 'article', 'design'])


class ImageSearchTests(unittest.TestCase):
    def test_surname_and_club_context(self):
        result = {'t': 'Miretti Beşiktaş antrenmanı', 'purl': 'https://sports.example/a', 'murl': 'https://cdn.example/a.jpg'}
        self.assertTrue(bot.image_matches_subject(result, 'Fabio Miretti'))
        self.assertFalse(bot.image_matches_subject(dict(result, t='Miretti Juventus'), 'Fabio Miretti'))
        self.assertFalse(bot.image_matches_subject(dict(result, t='Beşiktaş stadyumu'), 'Fabio Miretti'))

    def test_full_size_image_result_and_download(self):
        import html, json
        data = {'t': 'Miretti Beşiktaş forma', 'purl': 'https://sports.example/miretti', 'murl': 'https://cdn.example/miretti.jpg'}
        markup = '<a class="iusc" m="' + html.escape(json.dumps(data), quote=True) + '"></a>'
        parser = bot.SearchImageParser(); parser.feed(markup)
        self.assertEqual(parser.results, [data])
        raw = io.BytesIO(); Image.new('RGB', (500, 500), 'white').save(raw, 'JPEG')
        page = Mock(text=markup)
        photo = Mock(); photo.__enter__ = Mock(return_value=photo); photo.__exit__ = Mock(return_value=False)
        photo.iter_content.return_value = [raw.getvalue()]
        news = {'title': 'Miretti', 'link': 'https://news.example/original'}
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'FALLBACK_HISTORY', Path(folder) / 'history'), patch('bot.requests.get', side_effect=[page, photo]):
            dest = Path(folder) / 'image.jpg'
            self.assertTrue(bot.download_search_image('Fabio Miretti', news, dest))
            self.assertEqual(news['_web_image_url'], data['murl'])
            self.assertTrue(dest.exists())

    def test_claw_alpha_and_photo_branding(self):
        mark = bot.claw_mark((100, 100), .2)
        self.assertLessEqual(mark.getchannel('A').getextrema()[1], 51)
        self.assertEqual(mark.getchannel('A').getextrema()[0], 0)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'original.png'; dest = Path(folder) / 'branded.jpg'
            Image.new('RGB', (1080, 1080), 'black').save(source)
            bot.apply_claw_branding(source, dest)
            with Image.open(dest) as image:
                self.assertEqual(image.size, (1080, 1080))
                self.assertIsNotNone(image.crop((940, 0, 1080, 110)).getbbox())
                self.assertIsNotNone(image.crop((240, 300, 840, 950)).getbbox())
                self.assertEqual(image.getpixel((40, 900)), (0, 0, 0))

    def test_private_image_urls_rejected(self):
        for url in ('http://127.0.0.1/a', 'http://localhost/a', 'http://10.0.0.1/a'):
            self.assertFalse(bot.public_photo_url(url))


if __name__ == '__main__':
    unittest.main()

