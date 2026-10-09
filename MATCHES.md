# Maç paylaşımları

Erkek futbol A takımı: ESPN'de bulunan Türkiye ve Avrupa karşılaşmaları. Türkiye Kupası verisi sağlayıcıda bulunmadığında kayıt uyarısı oluşur; bu turnuvanın kapsamı garanti edilmez.

Erkek basketbol A takımı: EuroLeague ve EuroCup resmi veri servisleri. Türkiye Basketbol Süper Ligi ve Türkiye Kupası henüz desteklenmiyor; erişilebilir, saat ve kesin sonuç sağlayan ücretsiz veri kaynağı gerekiyor.

Maç kontrolü beş dakikada bir planlanır. GitHub Actions yoğunlukta gecikebilir; tam 30 dakika önce paylaşım garantisi yoktur. Başlangıca 30 dakika kaldığından maç başlayana kadar duyuru penceresi kullanılır. Futbolda 11 farklı başlangıç oyuncusu doğrulanmadan paylaşım yapılmaz. Sonuçlar yalnızca tamamlandığı doğrulanmış ve başlangıcı son 12 saat içinde olan maçlardan alınır.

Görsellerde iki takımın gerçek logoları, Türkiye saati, Kartalpenche1903 logosu ve merkezde pençe filigranı bulunur. Sonuç görselinde ev sahibi ve deplasman sırasıyla skor gösterilir. Kadro yalnızca futbol ön duyurusuna eklenir.

`python matches.py --dry-run` yalnızca o anda paylaşım penceresi içinde olan maçları önizler; Instagram'a bağlanmaz ve geçmişi değiştirmez. `preview/` içeriği manuel önizleme çalışmasında çıktı olarak kaydedilir.

`paylasilan_maclar.json` her doğrulanmış Instagram yüklemesinden sonra yazılır. Aynı maç duyurusu veya sonucu yeniden paylaşılmaz. Haber botuyla aynı eşzamanlılık grubunda çalışır.
