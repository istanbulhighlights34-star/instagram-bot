import os
import requests
import feedparser
import cloudscraper
from instagrapi import Client
from google import genai

# Şifreler GitHub Secrets kasasından güvenle çekilir
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
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
        # Dosya yoksa boş oluştur ki GitHub hata vermesin
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
        except Exception as e:
            print(f"Hata: {feed_url} okunamadı. ({e})")
    
    return None

def generate_caption(title, summary):
    print("Gemini API metni hazırlıyor...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Sen koyu bir Beşiktaş taraftarı ve çok takipçili bir Instagram spor sayfasının yöneticisisin.
    Aşağıdaki haberi okuyup, Instagram'da paylaşmak için samimi, enerjik, ateşli ve takipçilere soru soran bir dil ile yeniden yaz. 
    Lütfen metnin sonuna mutlaka #Beşiktaş, #BJK, #KaraKartal gibi popüler etiketleri ekle. 
    Metin doğrudan kopyalanıp Instagram'a yapıştırılacak formatta olmalı. Sadece paylaşılacak metni ver.

    Haber Başlığı: {title}
    Haber Detayı: {summary}
    """
    
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt,
    )
    return response.text.strip()

def download_image(url):
    print(f"Resim indiriliyor: {url}")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(TEMP_IMAGE, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    return False

def post_news():
    print("Yeni haber kontrolü yapılıyor...")
    news = get_latest_unposted_news()
    
    if not news:
        print("Paylaşılacak yeni haber bulunamadı.")
        return

    print(f"Yeni Haber Bulundu: {news['title']}")
    caption = generate_caption(news['title'], news['summary'])
    
    if download_image(news['image_url']):
        print("Instagram'a giriş yapılıyor...")
        cl = Client()
        cl.login(IG_USERNAME, IG_PASSWORD)
        
        print("Fotoğraf yükleniyor...")
        cl.photo_upload(TEMP_IMAGE, caption)
        print("BAŞARILI! Haber paylaşıldı.")
        
        save_posted_news(news['link'])
    else:
        print("Resim indirilemediği için paylaşılamadı.")

if __name__ == "__main__":
    post_news()
