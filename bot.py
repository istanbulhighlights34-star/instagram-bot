import os
import json
import requests
import feedparser
import cloudscraper
import base64
from instagrapi import Client

# Şifreler
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
        except Exception:
            pass
    return None

def generate_caption(title, summary):
    print("Gemini API (REST) metni hazırlıyor...", flush=True)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Sen koyu bir Beşiktaş taraftarı ve çok takipçili bir Instagram spor sayfasının yöneticisisin. Aşağıdaki haberi okuyup, Instagram'da paylaşmak için samimi, enerjik, ateşli ve takipçilere soru soran bir dil ile yeniden yaz. Lütfen metnin sonuna mutlaka #Beşiktaş, #BJK, #KaraKartal gibi popüler etiketleri ekle. Metin doğrudan kopyalanıp Instagram'a yapıştırılacak formatta olmalı. Sadece paylaşılacak metni ver.\n\nHaber Başlığı: {title}\n\nHaber Detayı: {summary}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            print(f"Yapay zeka sunucusu dolu veya hata verdi: {response.text}", flush=True)
    except Exception as e:
        print(f"Bağlantı hatası: {e}", flush=True)
        
    print("Telif riski olmaması için paylaşım İPTAL edildi.", flush=True)
    return None

def generate_ai_image(title):
    print("Yapay Zeka (Imagen 3) habere özel özgün görsel çiziyor...", flush=True)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={GEMINI_API_KEY}"
    prompt = f"A highly detailed, cinematic, energetic sports illustration representing Beşiktaş football club. Theme: {title}. Black and white colors with subtle red accents. No text or words in the image. High quality, photorealistic but artistic."
    
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "outputOptions": {"mimeType": "image/jpeg"}
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'predictions' in data and len(data['predictions']) > 0:
                image_b64 = data['predictions'][0].get('bytesBase64Encoded', '')
                if image_b64:
                    with open(TEMP_IMAGE, 'wb') as f:
                        f.write(base64.b64decode(image_b64))
                    print("Özgün görsel başarıyla çizildi!", flush=True)
                    return True
        print(f"Yapay zeka görsel çizemedi: {response.status_code}", flush=True)
    except Exception as e:
        print(f"Görsel çizim hatası: {e}", flush=True)
        
    print("Orijinal haber görseline (B Planı) dönülüyor.", flush=True)
    return False

def download_image(url):
    print(f"Orijinal resim indiriliyor: {url}", flush=True)
    try:
        response = requests.get(url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(TEMP_IMAGE, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False

def post_news():
    print("Yeni haber kontrolü yapılıyor...", flush=True)
    news = get_latest_unposted_news()
    if not news:
        print("Paylaşılacak yeni haber bulunamadı.", flush=True)
        return

    print(f"Yeni Haber Bulundu: {news['title']}", flush=True)
    caption = generate_caption(news['title'], news['summary'])
    if not caption:
        print("İşlem iptal edildi. Bir sonraki programlı saatte tekrar denenecek.", flush=True)
        return
        
    if not generate_ai_image(news['title']):
        download_image(news['image_url'])

    print("Instagram'a VIP giriş yapılıyor (Güvenli Anahtar ile)...", flush=True)
    try:
        cl = Client()
        if IG_SESSION:
            cl.set_settings(json.loads(IG_SESSION))
        else:
            cl.login(IG_USERNAME, IG_PASSWORD)
            
        print("Fotoğraf yükleniyor...", flush=True)
        cl.photo_upload(TEMP_IMAGE, caption)
        print("BAŞARILI! Haber paylaşıldı.", flush=True)
        save_posted_news(news['link'])
    except Exception as e:
        print(f"Instagram'a yüklenirken hata oluştu: {e}", flush=True)

if __name__ == "__main__":
    post_news()
