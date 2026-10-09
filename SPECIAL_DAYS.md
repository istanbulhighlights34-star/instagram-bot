# Özel gün gönderileri

Türkiye saatine göre özel günlerde ilk paylaşım 08:00 için planlanır. 10 Kasım anması 08:30’da başlar; 08:50 ve 09:00 kontrolleri görsel hazırlama sorunlarında yeniden dener. GitHub zamanlaması kesin dakika garantisi vermez. Görsel hazır değilse alakasız fotoğraf paylaşılmaz. Instagram cevabı belirsizse tekrar yükleme yapılmaz.

Takvim: 1 Ocak; 23 Nisan; 1 Mayıs; 19 Mayıs; 15 Temmuz; 30 Ağustos; 29 Ekim; 10 Kasım. Ramazan başlangıcı, Ramazan/Kurban bayramının her günü, Regaip/Miraç/Berat/Mevlid kandilleri, Kadir Gecesi ve Aşure Günü. Hristiyan günleri: 25 Aralık Noel, 6 Ocak Epifani/Theofani ve Ermeni Noel’i, 7 Ocak Noel’i, Katolik/Protestan ve Ortodoks Paskalya, Kutsal Cuma, Yükseliş Bayramı ve Pentekost takvimleri ayrı hesaplanır. 25 Mart Müjde Bayramı ve 15 Ağustos Meryem’e adanan bayram da dahildir.

2026–2027 İslami günler Diyanet’in doğrulanmış yıllık listelerinden gelir. Sonraki yılın tarihleri Diyanet’ten alınır; liste doğrulanamazsa tahmini bir tarihte paylaşılmaz. Kaynaklar `media/special-calendar.json` içindedir. Paskalya hesapları 2026 ve 2027 kilise takvimlerine karşı test edilir.

- Diyanet: https://vakithesaplama.diyanet.gov.tr/dinigunler.php?yil=2026
- Diyanet 2027: https://vakithesaplama.diyanet.gov.tr/icerik.php?icerik=154
- Katolik takvimi: https://www.vatican.va/content/liturgy/en/events/year.dir.html/2026.html
- Ortodoks takvimi: https://www.goarch.org/chapel/paschalion?year=2027

İnternetten güne uygun kamu malı/CC0 gerçek fotoğraflar aranır. Pençe varlığı veya pençe içeren marka logosu kullanılmaz. Özel çerçeve, marka adı, gün başlığı ve kısa alt başlık uygulanır. 10 Kasım görseli siyah-beyaz; metni sade, saygılı ve özlem doludur. Kutlama emojisi, taraftar sloganı ve reklam dili yoktur.

Özel günün bütün gönderileri doğrulanana kadar haber, maç ve panel yayınları bekler. Bu kural normal haberlerin sadece Beşiktaş olması filtresinden bağımsızdır. Aynı tarihe farklı özel günler denk gelirse her biri hazırlanır ve diğer yayınlardan önce gelir. Ortak GitHub çalışma kilidi ile süreçler eşzamanlı paylaşım yapmaz. Her çalışma güncel `main` dalını okuyarak kayıtlı özel gönderiyi tekrar yüklemez.

Önizleme (Instagram bağlantısı/yayını yok): `python special_days.py --dry-run --date 2026-11-10`. Kaynak bağlantısı `.json`, açıklama `.txt`, görsel `.jpg` dosyalarına ayrı kaydedilir; kaynak linki gönderi açıklamasına eklenmez.
