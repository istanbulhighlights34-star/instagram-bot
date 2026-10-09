"""Run the existing news pipeline once and retain the exact published artifact."""
import json
import logging
from pathlib import Path
import shutil
import bot


def main():
    logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
    news=bot.get_latest_unposted_news()
    if not news:
        raise RuntimeError('Paylaşılacak yeni haber bulunamadı.')
    output=Path('published')
    output.mkdir(exist_ok=True)
    (output/'source.json').write_text(json.dumps(news,ensure_ascii=False,indent=2))
    original_publish=bot.publish
    result={}
    def publish(path,caption):
        shutil.copyfile(path,output/'haber.jpg')
        (output/'caption.txt').write_text(caption)
        media_id=original_publish(path,caption)
        result['media_id']=str(media_id)
        (output/'result.json').write_text(json.dumps(result))
        return media_id
    bot.get_latest_unposted_news=lambda:news
    bot.publish=publish
    bot.post_news()
    if not result:
        raise RuntimeError('Haber hazırlanamadı; Instagram paylaşımı yapılmadı.')


if __name__=='__main__':
    main()
