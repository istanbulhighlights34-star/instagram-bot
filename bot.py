import os
import json
import time
import requests
import feedparser
import cloudscraper
from instagrapi import Client
from google import genai
from google.genai import types

# Şifreler GitHub Secrets kasasından güvenle çekilir
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_SESSION = os.getenv("IG_SESSION")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RSS_FEEDS = [
    "https://ortacizgi.com/feed",
    "https://www.fanatik.com.tr/rss/besiktas",
    "https://www.kartalhaber.com/rss.xml",
    "https://www.duhuliye.com/rss"
]

POSTED_FILE = "paylasilan_haberler.txt"
TEMP_IMAGE = "gecici_haber_resmi.jpg"

def load_posted_news():
    if not os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            pass
        return []
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def save_posted_news(link):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def get_latest_unposted_news():
    posted = load_posted_news()
    scraper = cloudscraper.create_scraper(browser='chrome')
    
    for feed_url in RSS_FEEDS:
        try:
            xml_data = scraper.get(feed_url).text
            feed = feedparser.parse(xml_data)
            for entry in feed.entries:
                link = entry.link
                if link not in posted:
                    title = entry.title
                    summary = entry.get('summary', title)
                    
                    image_url = None
                    if 'media_content' in entry and len(entry.media_content) > 0:
                        image_url = entry.media_content[0]['url']
                    elif 'links' in entry:
                        for item in entry.links:
                            if 'image' in item.get('type', ''):
                                image_url = item.get('href')
                    
                    if not image_url:
                        image_url = "https://upload.wikimedia.org/wikipedia/commons/2/22/Besiktas_JK_Logo.svg"

                    return {"title": title, "summary": summary, "link": link, "image_url": image_url}
        except BaseException as e:
            print(f"Hata: {feed_url} okunamadı. ({e})")
    
    return None

def generate_caption(title, summary):
    print("Gemini API metni hazırlıyor...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        Sen koyu bir Beşiktaş taraftarı ve çok takipçili bir Instagram spor sayfasının yöneticisisin.
        Aşağıdaki haberi okuyup, Instagram'da paylaşmak için samimi, enerjik, ateşli ve takipçilere soru soran bir dil ile yeniden yaz. 
        Lütfen metnin sonuna mutlaka #Beşiktaş, #BJK, #KaraKartal gibi popüler etiketleri ekle. 
        Metin doğrudan kopyalanıp Instagram'a yapıştırılacak formatta olmalı. Sadece paylaşılacak metni ver.

        Haber Başlığı: {title}
        Haber Detayı: {summary}
        """
        
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=prompt,
                )
                return response.text.strip()
            except BaseException as e:
                print(f"Gemini API çok yoğun veya koptu. (Deneme {attempt+1}/2)...")
                time.sleep(5)
                
    except BaseException as e:
        print(f"Yapay zeka metin üretirken tamamen koptu: {e}")
        
    print("Yapay zeka yanıt vermedi! Telif riski olmaması için paylaşım İPTAL edildi.")
    return None

def generate_ai_image(title):
    print("Yapay Zeka (Imagen 3) habere özel özgün görsel çiziyor...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"A highly detailed, cinematic, energetic sports illustration representing Beşiktaş football club. Theme: {title}. Black and white colors with subtle red accents. No text or words in the image. High quality, photorealistic but artistic."
        
        for attempt in range(2):
            try:
                result = client.models.generate_images(
                    model='imagen-3.0-generate-001',
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1"
                    )
                )
                for generated_image in result.generated_images:
                    with open(TEMP_IMAGE, 'wb') as f:
                        f.write(generated_image.image.image_bytes)
                print("Özgün görsel başarıyla çizildi!")
                return True
            except BaseException as e:
                print(f"Görsel oluşturulamadı (Bağlantı Koptu/Yoğun). (Deneme {attempt+1}/2)")
                time.sleep(3)
                
    except BaseException as e:
        print(f"Yapay zeka görsel motoru çöktü: {e}")
        
    print("Yapay Zeka görsel çizemedi. Orijinal haber görseline (B Planı) dönülüyor.")
    return False

def download_image(url):
    print(f"Orijinal resim indiriliyor: {url}")
    try:
        response = requests.get(url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(TEMP_IMAGE, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except BaseException as e:
        print(f"Orijinal resim indirilemedi: {e}")
    return False

def post_news():
    print("Yeni haber kontrolü yapılıyor...")
    news = get_latest_unposted_news()
    
    if not news:
        print("Paylaşılacak yeni haber bulunamadı.")
        return

    print(f"Yeni Haber Bulundu: {news['title']}")
    caption = generate_caption(news['title'], news['summary'])
    
    if not caption:
        print("İşlem iptal edildi. Bir sonraki programlı saatte tekrar denenecek.")
        return
        
    image_ready = generate_ai_image(news['title'])
    if not image_ready:
        image_ready = download_image(news['image_url'])

    if image_ready:
        print("Instagram'a VIP giriş yapılıyor (Güvenli Anahtar ile)...")
        try:
            cl = Client()
            
            # Eğer VIP biletimiz varsa sadece onu cihaza tanıtıp geçiyoruz.
            # Kesinlikle .login() (şifre soran kapı) kullanmıyoruz!
            if IG_SESSION:
                cl.set_settings(json.loads(IG_SESSION))
            else:
                cl.login(IG_USERNAME, IG_PASSWORD)
                
            print("Fotoğraf yükleniyor...")
            cl.photo_upload(TEMP_IMAGE, caption)
            print("BAŞARILI! Haber paylaşıldı.")
            save_posted_news(news['link'])
            
        except BaseException as e:
            print(f"Instagram'a yüklenirken hata oluştu: {e}")
    else:
        print("Hiçbir resim bulunamadığı için paylaşılamadı.")

if __name__ == "__main__":
    post_news()
