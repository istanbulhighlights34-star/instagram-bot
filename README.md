# Beşiktaş Instagram haber botu

En yeni paylaşılmamış RSS haberini seçer ve metni yeniden yazar. Metin üretilemezse haber kaydedilmez; sonraki çalışmada yeniden aday olabilir.

## Görsel seçimi

1. Önce oyuncu fotoğraf havuzu ve internet görsel/web aramasından gerçek fotoğraf bulunur.
2. Fotoğraf bulunamazsa haberin kaynak sayfasındaki kapak fotoğrafı denenir.
3. Bulunan fotoğrafa Pillow ile yerel, ücretsiz Beşiktaş tasarımı uygulanır: siyah/beyaz/kırmızı şeritler, özgün kartal motifi ve haber başlığı. Gemini yalnızca metin ve kısa başlık üretir; fotoğraf düzenleme API'si çağrılmaz.
4. Tasarım başarısızsa orijinal fotoğraf korunur. Hiç fotoğraf bulunamazsa haber kaydedilmez.

Gemini metin çağrısı ücretsiz projenin mevcut limitlerine tabidir; ücretsiz kota aşılırsa metin oluşmaz ve haber sonraki çalışmaya bırakılır. Tasarım ek API ücreti gerektirmez.

Arama, herkese açık ve arama motorunun indekslediği sayfalarla sınırlıdır. Oyuncunun soyadı, görsel başlığı, açıklaması ve kaynak adresi konu eşleşmesi için kullanılır; fotoğraftaki kişinin kimliği veya forması otomatik olarak kesin doğrulanmaz. Bütün kaynaklar başarısızsa haber kaydedilmez.

Oyuncu havuzu media/players.json dosyasında tanımlanır. Kullanılan havuz fotoğrafları yalnızca başarılı paylaşım sonrası geçmişe kaydedilir. Önizleme geçmişi tüketmez.

## Metin ve paylaşım

Açıklamada kaynak bağlantısı ve arşiv fotoğrafı satırı bulunmaz. Etiketler önce #Beşiktaş #BJK #KaraKartal, ardından haberde geçen kişilerle ilgili etiketlerdir.

GitHub Secrets: GEMINI_API_KEY, IG_USERNAME, IG_PASSWORD; isteğe bağlı IG_SESSION (instagrapi oturum JSON verisi).

Actions → Instagram AI Bot → Run workflow: Önizleme varsayılan olarak açık. Başarılı önizlemenin haber-onizleme çıktısında fotoğraf ve metin bulunur; Instagram'a bağlanılmaz ve geçmiş değiştirilmez. Canlı paylaşım için önizlemeyi kapatın.

Program Türkiye saatine göre 11:00, 15:00, 19:00, 22:00. GitHub çalışmaları geciktirebilir. Bot adımının sınırı 12 dakika, post işinin sınırı 15 dakikadır; yerel tasarımda görsel üretim kotası veya 3 dakikalık AI beklemesi yoktur.

Paylaşım geçmişi Instagram yüklemesi doğrulanınca kaydedilir. Yükleme otomatik tekrarlanmaz.

Test: python -m unittest discover -s tests -v
Gerçek API önizlemesi: python bot.py --dry-run

Başarıyla paylaşılan doğrudan arama fotoğraflarının URL geçmişi tutulur ve aynı URL yeniden seçilmez. Önizleme geçmişi tüketmez. Arama servisi alakasız veya boş sonuç döndürebilir; bulunan sonuç ve uygun aday sayıları çalışma kaydında gösterilir.
