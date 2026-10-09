# Maç paylaşımları

Erkek futbol A takımı: ESPN'de bulunan Türkiye ve Avrupa karşılaşmaları. Türkiye Kupası verisi sağlayıcıda bulunmadığında kayıt uyarısı oluşur; bu turnuvanın kapsamı garanti edilmez.

Erkek basketbol A takımı: Maçkolik takım fikstüründe yer alan Türkiye ligi ve Avrupa karşılaşmaları. Maç bitişi detay sayfasındaki postGame ve fullTime durumlarıyla, skor ise hem fikstür hem detay sayfasında aynı değerle doğrulanır. Avrupa maçlarında güncel resmi EuroLeague/EuroCup takım logoları tercih edilir. Kaynakta saat veya kesin sonuç bulunmadığında paylaşım yapılmaz.

Maç kontrolü beş dakikada bir planlanır. GitHub Actions yoğunlukta gecikebilir; tam 30 dakika önce paylaşım garantisi yoktur. Başlangıca 30 dakika kaldığından maç başlayana kadar duyuru penceresi kullanılır. Futbolda 11 farklı başlangıç oyuncusu doğrulanmadan paylaşım yapılmaz. Sonuçlar yalnızca tamamlandığı doğrulanmış ve başlangıcı son 12 saat içinde olan maçlardan alınır.

Görsellerde görselin orta alanında iki takımın gerçek logoları ve her logonun altında takım adı, Türkiye saati, Kartalpenche1903 logosu ve merkezde pençe filigranı bulunur. Sonuç görselinde ev sahibi ve deplasman sırasıyla skor gösterilir. Kadro yalnızca futbol ön duyurusuna eklenir.

`python matches.py --dry-run` yalnızca o anda paylaşım penceresi içinde olan maçları önizler; Instagram'a bağlanmaz ve geçmişi değiştirmez. `preview/` içeriği manuel önizleme çalışmasında çıktı olarak kaydedilir.

`paylasilan_maclar.json` her doğrulanmış Instagram yüklemesinden sonra yazılır. Aynı maç duyurusu veya sonucu yeniden paylaşılmaz. Haber botuyla aynı eşzamanlılık grubunda çalışır.
