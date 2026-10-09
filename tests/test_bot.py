import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import bot

class BotTests(unittest.TestCase):
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
            with patch('bot.get_latest_unposted_news', return_value=news), patch('bot.generate_caption', return_value=caption), patch('bot.generate_ai_image', return_value=image), patch('bot.publish', side_effect=RuntimeError('failed')) as publish, patch('bot.save_posted_news') as save:
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

if __name__ == '__main__':
    unittest.main()
