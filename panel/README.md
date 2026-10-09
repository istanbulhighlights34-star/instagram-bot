# Kartalpenche özel paylaşım paneli

İlk sürüm: özel şifreli giriş, JPEG/PNG/WebP fotoğraf (15 MB), mevcut botla aynı kare çerçeve/logo/pençe, 2200 karakter açıklama, önizleme, kullanıcının açık yayınlama düğmesi, durum ve doğrulanmış Instagram bağlantısı. Video/Reels/hikâye bu sürümde yoktur.

## Bağlantı

1. Supabase Free projesi oluşturun. SQL Editor'da `panel/setup.sql` çalıştırın.
2. Project URL ve legacy `service_role` anahtarını Render'a `SUPABASE_URL` ve `SUPABASE_SERVICE_ROLE_KEY` olarak ekleyin. Aynı iki değeri GitHub Actions repository secrets olarak kaydedin. Bu anahtarları tarayıcıya, koda, sohbete veya loglara koymayın.
3. Render Free web service `pip install -r panel/requirements.txt`; başlangıç `gunicorn panel.app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`. Panel şifresi `PANEL_PASSWORD`, ayrı rastgele imzalama anahtarı `PANEL_SESSION_SECRET`.
4. Mevcut `IG_USERNAME`, `IG_PASSWORD`, `IG_SESSION` yalnızca GitHub'da kalır.
5. Panelde deneme fotoğrafı yükleyin. Önizleme hiçbir şekilde Instagram'a gönderilmez. Publish düğmesi `ready` kaydını atomik olarak `queued` yapar.
6. `panel.yml` sadece queued kayıtları paylaşır. Beş dakika aralıklı GitHub zamanlaması gecikebilir; kesin süre garantisi yoktur. Haber ve maç botuyla aynı concurrency kullanılır.

## Güvenlik ve kayıtlar

Özel bucket, tablo RLS, anon/authenticated rollerine kapalı; yalnızca sunucular service_role kullanır. Güvenli HttpOnly SameSite cookie, CSRF doğrulaması, giriş denemesi sınırı, EXIF bilgilerinin JPEG dönüşümünde kaldırılması. Kullanıcı açıklaması otomatik değiştirilmez, HTML olarak çalıştırılmaz.

Instagram girişinden önce hata alırsa `failed`. Yüklemeye başlandıktan sonra hata olursa `uncertain`; otomatik yeniden deneme yapılmaz. İşlem kesilirse `processing/uploading` olarak kalabilir; önce Instagram kontrol edilmeli. Aynı düğmeye tekrar basılması ikinci yükleme başlatmaz. Dosyalar ücretsiz 1 GB alanı doldurabilir; panelde silme işlemiyle terminal kayıtlar temizlenebilir. Yayımlanmamış sıradaki kayıtlar silinemez.

Gizli Supabase verisi ve fotoğraf GitHub deposuna/loglara/artifactlere yazılmaz. Paylaşılan fotoğraf Instagram'da normal olarak görünür. Render yeniden başlasa da kuyruğun durumu Supabase'de korunur.
