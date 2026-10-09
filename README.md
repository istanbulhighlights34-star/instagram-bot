# Beşiktaş Instagram haber botu

En yeni paylaşılmamış RSS haberini seçer, metni yeniden yazar ve özgün temsili görsel üretir. Geçici API hatalarında ve boş yanıtlarda üç deneme yapılır. Kalıcı hatalarda tekrar denenmez. Metin/görsel oluşmazsa haber kaydedilmez; sonraki çalışmada hâlâ en yeni aday ise tekrar denenir. Haber sitelerinin fotoğrafları indirilmez.

GitHub Secrets: GEMINI_API_KEY, IG_USERNAME, IG_PASSWORD; isteğe bağlı IG_SESSION (instagrapi oturum JSON verisi). Oturum yüklendikten sonra giriş doğrulanır. Instagram ek doğrulama isteyebilir. Şifreleri dosyalara yazmayın.

Model değişkenleri: GEMINI_TEXT_MODEL ve GEMINI_IMAGE_MODEL. Varsayılanlar gemini-3.8-flash ve gemini-3.1-flash-image. Hesabın model erişimi, kotası ve görsel üretim faturalandırması gerçek önizleme çalışmasında doğrulanmalıdır.

Actions → Instagram AI Bot → Run workflow: Önizleme varsayılan olarak açık. Üretim başarılı olursa haber-onizleme çıktısında fotoğraf ve metin bulunur; Instagram'a bağlanılmaz ve geçmiş değiştirilmez. Önizleme de Google API kullanımı oluşturur. Canlı paylaşım için önizlemeyi kapatın. Program Türkiye saatine göre 11:00, 15:00, 19:00, 22:00; GitHub çalışmaları geciktirebilir.

Test: python -m unittest discover -s tests -v
Gerçek API önizlemesi: python bot.py --dry-run

Paylaşım geçmişi yalnızca Instagram yüklemesi doğrulanınca kaydedilir. Yanıt kaybı veya geçmişin GitHub'a kaydedilememesi tekrar paylaşım riski oluşturur. Başarısız çalışmayı yeniden başlatmadan önce Instagram'ı kontrol edin. Yükleme otomatik tekrarlanmaz.

Metni yeniden yazmak veya yapay zekâyla görsel üretmek telif garantisi sağlamaz. Kaynak bağlantısı eklenir ve görseller temsili olarak işaretlenir.
