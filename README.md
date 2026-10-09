# Beşiktaş Instagram haber botu

En yeni paylaşılmamış RSS haberini seçer ve metni yeniden yazar. Metin üretilemezse haber kaydedilmez; sonraki çalışmada yeniden aday olabilir.

## Görsel seçimi

1. Habere uygun yapay zekâ görseli: toplam en fazla 180 saniye. Hata veya süre aşımında sonraki kaynağa geçilir.
2. İsimle eşleşen oyuncu fotoğraf havuzu; ardından Bing web aramasındaki farklı sitelerden oyuncu ve Beşiktaş konusuna uygun sayfaların görselleri. Site listesi Wikimedia ile sınırlandırılmaz. En fazla üç uygun sonuç sayfası denenir; sonuç alınamazsa Commons araması da denenir.
3. Son seçenek olarak aynı haberin kaynak sayfasındaki kapak fotoğrafı.

Arama, herkese açık ve arama motorunun indekslediği sayfalarla sınırlıdır. Sayfa başlığı ve açıklaması konu eşleşmesi için kullanılır; fotoğraftaki kişinin kimliği veya forması otomatik olarak kesin doğrulanmaz. Bütün kaynaklar başarısızsa haber kaydedilmez.

Oyuncu havuzu media/players.json dosyasında tanımlanır. Kullanılan havuz fotoğrafları yalnızca başarılı paylaşım sonrası geçmişe kaydedilir. Önizleme geçmişi tüketmez.

## Metin ve paylaşım

Açıklamada kaynak bağlantısı ve arşiv fotoğrafı satırı bulunmaz. Etiketler önce #Beşiktaş #BJK #KaraKartal, ardından haberde geçen kişilerle ilgili etiketlerdir.

GitHub Secrets: GEMINI_API_KEY, IG_USERNAME, IG_PASSWORD; isteğe bağlı IG_SESSION (instagrapi oturum JSON verisi).

Actions → Instagram AI Bot → Run workflow: Önizleme varsayılan olarak açık. Başarılı önizlemenin haber-onizleme çıktısında fotoğraf ve metin bulunur; Instagram'a bağlanılmaz ve geçmiş değiştirilmez. Canlı paylaşım için önizlemeyi kapatın.

Program Türkiye saatine göre 11:00, 15:00, 19:00, 22:00. GitHub çalışmaları geciktirebilir. Bot adımının sınırı 12 dakika, post işinin sınırı 15 dakikadır; görsel üretiminin kendi sınırı 3 dakikadır.

Paylaşım geçmişi Instagram yüklemesi doğrulanınca kaydedilir. Yükleme otomatik tekrarlanmaz.

Test: python -m unittest discover -s tests -v
Gerçek API önizlemesi: python bot.py --dry-run
