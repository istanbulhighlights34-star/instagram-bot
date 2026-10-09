"""Run the existing news pipeline once and retain the exact published artifact."""
import json
import logging
import os
import io
import requests
from PIL import Image
from pathlib import Path
import shutil
import bot


def main():
    logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
    if os.getenv('APPROVED_NEWS_PATH'):
        publish_prepared(Path(os.environ['APPROVED_NEWS_PATH']))
        return
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


def publish_prepared(path):
    data=json.loads(path.read_text())
    if data['link'] in bot.load_posted_news():
        bot.report_outcome('Bu haber daha önce paylaşılmış; ikinci gönderi oluşturulmadı.')
        return
    output=Path('published')
    output.mkdir(exist_ok=True)
    (output/'source.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    (output/'caption.txt').write_text(data['caption'])
    response=requests.get(data['image_url'],timeout=(5,20))
    response.raise_for_status()
    if len(response.content)>15*1024*1024:
        raise RuntimeError('Fotoğraf boyutu sınırı aşıldı.')
    with Image.open(io.BytesIO(response.content)) as picture:
        if min(picture.size)<300:
            raise RuntimeError('Fotoğraf çözünürlüğü yetersiz.')
        picture.convert('RGB').save(output/'source.jpg',quality=95)
    bot.render_free_design(output/'source.jpg',output/'design.jpg',data['title'])
    bot.apply_claw_branding(output/'design.jpg',output/'haber.jpg',framed=True)
    media_id=bot.publish(output/'haber.jpg',data['caption'])
    bot.save_posted_news(data['link'])
    (output/'result.json').write_text(json.dumps({'media_id':str(media_id)}))
    bot.report_outcome(f'Instagram paylaşımı doğrulandı; medya kimliği: {media_id}.')


if __name__=='__main__':
    main()
