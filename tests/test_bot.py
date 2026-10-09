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
            with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value=caption), patch('bot.generate_ai_image', return_value=image), patch('bot.download_fallback_image', return_value=False), patch('bot.publish', side_effect=RuntimeError('failed')) as publish, patch('bot.save_posted_news') as save:
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
        with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.generate_ai_image', return_value=True), patch('bot.publish', side_effect=lambda *args: events.append('upload') or 123), patch('bot.save_posted_news', side_effect=lambda link: events.append('save')):
            bot.post_news()
        self.assertEqual(events, ['upload', 'save'])


    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    def test_ai_error_uses_fallback_and_publishes(self):
        news = {'title': 'Başlık', 'summary': 'Özet', 'link': 'https://news.test/1'}
        for error in (False, RuntimeError('429 quota')):
            with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value='Metin'), patch('bot.generate_ai_image', side_effect=error if isinstance(error, Exception) else None, return_value=False), patch('bot.download_fallback_image', return_value={'title': 'Bjk Stadyum.jpg', 'source': 'https://commons.wikimedia.org/wiki/File:Bjk_Stadyum.jpg'}) as fallback, patch('bot.save_fallback_photo'), patch('bot.publish', return_value=456) as publish, patch('bot.save_posted_news') as save:
                bot.post_news()
                fallback.assert_called_once()
                publish.assert_called_once()
                self.assertNotIn('Wikimedia', publish.call_args.args[1])
                self.assertNotIn('yapay zekâ ile üretilmiştir', publish.call_args.args[1])
                save.assert_called_once_with(news['link'])


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
            self.assertEqual(worker.join.call_args_list[0].kwargs['timeout'], 45)
            self.assertFalse(path.exists())


    def test_caption_club_tags_before_person_and_no_links(self):
        caption = bot.format_caption('Miretti hazır! https://news.test/a #Miretti #BJK #Miretti')
        self.assertTrue(caption.endswith('#Beşiktaş #BJK #KaraKartal #Miretti'))
        self.assertNotIn('https://', caption)
        self.assertEqual(caption.count('#Miretti'), 1)
        self.assertLessEqual(len(bot.format_caption('x' * 3000 + ' #Miretti')), 2200)

if __name__ == '__main__':
    unittest.main()
