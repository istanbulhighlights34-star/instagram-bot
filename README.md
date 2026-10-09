# Beşiktaş Instagram haber botu

En yeni paylaşılmamış RSS haberini seçer, metni yeniden yazar ve özgün temsili görsel üretir. Geçici API hatalarında ve boş yanıtlarda üç deneme yapılır. Kalıcı hatalarda tekrar denenmez. Metin oluşmazsa haber kaydedilmez; sonraki çalışmada hâlâ en yeni aday ise tekrar denenir. Görsel üretimi başarısız olursa CC0 lisanslı Beşiktaş stadyum fotoğrafı indirilir ve paylaşım sürdürülür. Hem yapay zekâ hem yedek fotoğraf başarısızsa haber kaydedilmez.

GitHub Secrets: GEMINI_API_KEY, IG_USERNAME, IG_PASSWORD; isteğe bağlı IG_SESSION (instagrapi oturum JSON verisi). Oturum yüklendikten sonra giriş doğrulanır. Instagram ek doğrulama isteyebilir. Şifreleri dosyalara yazmayın.

Model ayarları bot.yml dosyasında açıkça sabitlenmiştir; eski GitHub Variables değerleri kullanılmaz. Güncel modeller gemini-3.8-flash ve gemini-nano-banana-2.1. Hesabın model erişimi, kotası ve görsel üretim faturalandırması gerçek önizleme çalışmasında doğrulanmalıdır.

Actions → Instagram AI Bot → Run workflow: Önizleme varsayılan olarak açık. Üretim başarılı olursa haber-onizleme çıktısında fotoğraf ve metin bulunur; Instagram'a bağlanılmaz ve geçmiş değiştirilmez. Önizleme de Google API kullanımı oluşturur. Canlı paylaşım için önizlemeyi kapatın. Program Türkiye saatine göre 11:00, 15:00, 19:00, 22:00; GitHub çalışmaları geciktirebilir.

Test: python -m unittest discover -s tests -v
Gerçek API önizlemesi: python bot.py --dry-run

Paylaşım geçmişi yalnızca Instagram yüklemesi doğrulanınca kaydedilir. Yanıt kaybı veya geçmişin GitHub'a kaydedilememesi tekrar paylaşım riski oluşturur. Başarısız çalışmayı yeniden başlatmadan önce Instagram'ı kontrol edin. Yükleme otomatik tekrarlanmaz.

Metni yeniden yazmak veya yapay zekâyla görsel üretmek telif garantisi sağlamaz. Kaynak bağlantısı eklenir ve görseller temsili olarak işaretlenir.


9 Ekim 2026 güncellemesi: Metin Gemini 3.8 Flash, görsel Nano Banana 2.1; generateContent v1 API ve responseFormat görsel ayarları. Python 3.14; checkout v7.0.1, setup-python v7.0.0, upload-artifact v7.0.2. Ubuntu 24.04 açıkça seçilir. Çalışma özetinde üretim/paylaşım sonucu ayrı olarak gösterilir.


B planı: 429 kota hatasında doğrudan yedek fotoğrafa geçilir. Diğer görsel hatalarında en fazla üç deneme yapılır; başarısızlık veya istisna sonrası yedek fotoğraf kullanılır. Kaynak: https://commons.wikimedia.org/wiki/File:Vodafone_Park,_Istanbul_(from_outside).jpg — Olos88, CC0. Paylaşım metninde temsili arşiv fotoğrafı olduğu ve kaynak belirtilir. Yedek fotoğraf indirilemiyorsa görselsiz Instagram fotoğraf paylaşımı yapılamaz; haber kaydedilmez. Önizleme modu Instagram'a paylaşım yapmaz.


Yedek görseller artık dört farklı CC0/kamu malı stadyum ve takım arşiv fotoğrafından seçilir. Kullanılan görseller kullanilan_yedek_gorseller.txt içinde saklanır; havuz tüketilmeden aynı fotoğraf seçilmez. Havuz tükendiğinde yeni döngü başlar, son fotoğraf arka arkaya tekrar edilmez. Görsel indirilemezse kullanılmamış başka fotoğraf denenir. Önizleme ve başarısız Instagram yüklemesi görsel geçmişini tüketmez. Kaynak bağlantısı her görsele göre değişir; fotoğraflar güncel olay fotoğrafı olarak sunulmaz.
