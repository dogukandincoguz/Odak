# Odak

Windows açılışında sağ üstte başlayan, diğer normal pencerelerin üzerinde duran yerel görev takipçisi. Görev çubuğunda görünmez; simgesi sağ alttaki sistem tepsisindedir. İnternet veya hesap gerektirmez. Kapatma düğmesi uygulamayı tamamen kapatır; sonraki Windows oturumunda yeniden açılır.

## Çalıştırma

Python 3.13+ ve uv kullanılır. Depoyu klonlayıp proje klasörüne geçin:

```powershell
git clone https://github.com/dogukandincoguz/Odak.git
cd Odak
```

Kurulum tamamlandıktan sonra masaüstündeki **Odak** kısayoluna çift tıklamak yeterlidir. Terminal açılmaz. Proje klasörünü taşımayın; kısayollar bu konumu kullanır. Taşınırsa aşağıdaki kurulum komutunu yeni konumda yeniden çalıştırın.

Geliştirme ortamı ve bağımlılıklar:

```powershell
uv sync --locked
uv run --locked python app.py
```

Masaüstü ve Windows başlangıç kısayollarını oluşturup uygulamayı açmak için:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Launch
```

Otomatik başlatmayı kapatmak için `Win+R` → `shell:startup` klasöründeki **Odak** kısayolunu kaldırın. Uygulama veya görev verileri silinmez.

## Kullanım

- **Yeni görev / Ctrl+N:** başlık zorunlu; not, tarih ve saat isteğe bağlıdır.
- Yalnız tarih seçilirse o gün **23.59**; yalnız saat seçilirse **bugünün seçilen saati** kabul edilir.
- Deadline'a **24 saatten az** kalan işler kırmızı, **24–72 saat** kalanlar sarıdır. Daha uzak veya deadlinesız görevler normal renktedir.
- Süresi dolan işler **Geçenler → Deadline’ı geçenler** bölümüne otomatik taşınır.
- Tik simgesi görevi tamamlar; tamamlananlar **Bitenler** bölümünden yeniden açılabilir.
- Silinen işler **Silinenler → Son silinenler** alanından **10 dakika** boyunca geri alınabilir. Süre uygulama kapalıyken de ilerler. Süre dolunca kalıcı olarak temizlenir.
- Kalem simgesi başlığı, notu ve deadline'ı düzenler. **Ctrl+F** aramayı açar; arama seçili bölümde başlık ve notları tarar.
- Eksi düğmesi pencereyi sistem tepsisine gizler. Sağ alttaki tepsi simgesine tıklayarak veya sağ tık → **Odak’ı göster** ile pencereyi geri açabilirsiniz. Üç nokta menüsünden sağ üste yeniden yerleştirilebilir.
- Pencereyi üstteki logo veya başlık alanından sol tıkla tutup sürükleyerek taşıyabilirsiniz. Konum kaydedilmez; her yeni açılışta yine sağ üst köşede başlar.
- Kenarlardan veya sağ alt köşedeki tutamaktan pencereyi boyutlandırabilirsiniz. Boyut kaydedilir; sonraki açılışta bu boyutla sağ üstte açılır. Yeni görev, hatırlatma ve şablon pencereleri kendi üst barlarından taşınır; üstteki kutusuz `×` formu kapatır.
- Uygulama birlikte gelen **Inter** yazı tipini kullanır; ayrıca font kurulumu gerekmez. Yazı tipi lisansı `assets/fonts/OFL.txt` içindedir.
- `×` uygulamayı kapatır. Odak kısayolunu tekrar açmak var olan pencereyi öne getirir; ikinci kopya çalışmaz.

## Günlük plan ve fikirler

- **Bugün:** görev seçeneklerinden **Bugün yapacağım** ile günlük listenizi seçin. Tarih değişince günlük seçim sıfırlanır; görevler silinmez.
- **Bugünkü sıra:** arama boşken kartın solundaki altı noktalı tutamağı sürükleyerek çalışma sıranızı belirleyin. Bırakılacak yer çizgiyle gösterilir. Sıra kaydedilir; deadline değişmez. Tutamak klavye odağındayken yukarı/aşağı okları da sıralamayı değiştirir.
- **Bir gün:** henüz başlamayacağınız fikirleri bu bölümde saklayın. Görev seçeneklerinden aktif listeye veya Bugün'e taşıyabilirsiniz. Bu bölümdeki fikirler deadline'ı geçenler listesine girmez.
- **Alt adımlar:** görev formunda her satıra bir adım yazın. Karttaki **Adımlar** düğmesi listeyi açar; tamamlanan adımların sayısı gösterilir. Aynı adımlar düzenleme ve sıralama sırasında tamamlanma durumlarını korur.
- **Türkçe tarih önerisi:** başlığa `Yarın 18.00 raporu gönder`, `Cuma kitap al`, `3 gün sonra taslağı bitir` veya `25.10.2026 saat 09:30 sunum` yazabilirsiniz. Algılanan tarih öneri olarak gösterilir; **Uygula** düğmesine bastığınızda başlık temizlenir ve tarih/saat alanları dolar. Tarih önerisini uygulamak zorunlu değildir.

## Görev şablonları

Yeni görev penceresindeki **Şablon kullan** alanından hazır başlık, not ve adımları seçebilirsiniz. **Bu görevden şablon oluştur** mevcut formdaki alanları şablon olarak kaydeder. Üç nokta menüsündeki **Görev şablonları** veya şablon seçiminin yanındaki menü üzerinden şablon ekleyebilir, düzenleyebilir ve silebilirsiniz.

Şablonlar tarih, saat, günlük seçim veya tamamlanma durumu kopyalamaz. Her kullanım bağımsız bir görev ve bağımsız adımlar oluşturur. Şablonun silinmesi ondan oluşturulan görevleri etkilemez. Form doluyken başka bir şablon seçilirse alanların değiştirilmesi için onay istenir.

## Hatırlatmalar

Üstteki **Hatırlatmalar** bölümünden başlık, tekrar türü, tarih ve etkinlik saati seçin. Not ve toplantı bağlantısı isteğe bağlıdır.

- **Haftalık:** haftanın birden çok günü, **Her gün** veya **Hafta içi**; 1–52 haftada bir tekrar. Başlangıç tarihinin haftası temel alınır; örneğin iki haftada bir pazartesi o haftadan başlayarak ilerler.
- **Bir kez:** gelecekteki bir tarih ve saatte tek bildirim. Bildirimden sonra erteleme için kayıt geçici olarak kalır; etkinlikten veya son ertelemeden 24 saat sonra otomatik temizlenir. Eski tek seferlik kayıtlar birikmez.
- **Aylık · belirli gün:** 1–31 veya **Ayın son günü**, 1–52 ayda bir. Seçilen günün bulunmadığı aylar atlanır; son gün seçimi şubat ve artık yılları takip eder.
- **Aylık · haftanın belirli günü:** ilk, ikinci, üçüncü, dördüncü veya son pazartesi/cuma gibi bir gün; 1–52 ayda bir.
- **Bildirim:** etkinlik saatinde veya 5, 10, 30 dakika önce. Örneğin 14.00 toplantısı için 10 dakika önce seçilirse 13.50'de haber verilir; 14.00'te ikinci bildirim oluşmaz. Kartta etkinlik saati ile bildirim tercihi ayrı görünür.
- **Toplantıyı aç:** kaydedilmiş HTTP/HTTPS bağlantısını varsayılan tarayıcıda açar. Bağlantı hem karttan hem bildirime tıklayınca açılan pencereden kullanılabilir.

- Her hatırlatma tek kayıttır; tekrarlarda yeni görev veya geçmiş kaydı üretilmez.
- Zamanı gelince Windows bildirimi çıkar. Bildirime tıklayarak **10 dakika sonra hatırlat** seçebilirsiniz. Bu işlem düzenli programı değiştirmez.
- Düzenli hatırlatmalarda **Bu tekrarı atla**, sıradaki takvim zamanını atlar. **Duraklat / devam ettir** programı silmeden kapatıp açar. Tek seferlik hatırlatmanın tarihini düzenleyebilir veya kaydı silebilirsiniz.
- Tamamlandı düğmesi bulunmaz; hatırlatmalar görev veya deadline'ı geçenler listelerine eklenmez.
- Silinen hatırlatmalar bu bölümün sağındaki **Son silinenler** sekmesinden 10 dakika geri alınabilir.
- Uygulama kapalıyken geçen eski bildirimler birikmez. Açılışta son 15 dakikada gelen veya etkinliği henüz başlamamış bir hatırlatma gösterilebilir; daha eskileri sonraki takvim zamanına ilerler. Yeni hatırlatmanın ön bildirim saati geçmişse ve etkinlik hâlâ gelecekteyse hemen haber verilir.

## Odak sayacı

Üstteki **Odaklan** bölümünden görev seçin veya **Serbest odak** kullanın. Varsayılan süreler 25 dakika çalışma ve 5 dakika moladır; değiştirilebilir. Başlatma, duraklatma ve sıfırlama desteklenir. Süre bitince bildirim gelir; sonraki çalışma veya mola süresini kendiniz başlatırsınız. Görevler otomatik tamamlanmaz.

Sayaç tepsiye gizlendiğinde çalışır ve açılışlar arasında durumunu korur. Yalnızca ayarlar ve geçerli sayaç durumu tutulur; oturum geçmişi biriktirilmez.

## Yedekleme ve aktarım

Üç nokta menüsünden:

- **Dışa aktar:** görevleri, adımları, günlük sıralamayı, hatırlatma kurallarını ve şablonları taşınabilir JSON dosyasına kaydeder.
- **İçe aktar:** JSON'daki yeni kayıtları ekler. Aynı kimlikli mevcut kayıtları değiştirmez.
- **Şimdi yedek al:** veritabanının güvenli anlık kopyasını alır.
- **Yedekten geri yükle:** mevcut verileri seçilen yedekle değiştirir; işlem öncesi mevcut durumun yedeği alınır.

Uygulama açıkken günlük otomatik yedek alınır. **data/backups** altında en fazla **3 yedek** tutulur; otomatik ve elle alınan kopyalar aynı sınıra dahildir. Bildirim geçmişi, sayaç oturum geçmişi veya ek dosyalar saklanmadığı için büyüme esas olarak yazdığınız metin ve alt adımlara bağlıdır.

Örnek ölçümde, her biri 500 bayt not içeren 3.650 görev yaklaşık 2,7 MB; 36.500 görev yaklaşık 27 MB yer kapladı. Her göreve ayrıca beş alt adım eklendiğinde boyutlar sırasıyla yaklaşık 6,6 MB ve 65,6 MB oldu. Daha uzun metinler bu boyutu artırır. Üç tam yedek yaklaşık üç ek veritabanı kadar alan kullanır. Bu ölçümler bir boyut garantisi değildir.

## Veriler

Tüm görevler ve düzenli hatırlatmalar proje içindeki **data/odak.sqlite3** dosyasına her değişiklikte kaydedilir. Veri tamamen bu bilgisayarda kalır. Elle klasör yedeği almak için uygulamayı kapatıp **data** klasörünü kopyalayın veya uygulamadaki yedekleme menüsünü kullanın. Eski sürümün görevleri ilk açılışta yeni alanlar eklenerek korunur. Uygulamayı kaldırmak isterseniz önce verilerinizi yedekleyin. Hata kayıtları `data/odak.log` dosyasındadır.

Deadline'lar bilgisayarın yerel saatine göre değerlendirilir. Otomatik başlatma, Windows hesabına girişte gerçekleşir. Windows'un güvenli masaüstü ve özel tam ekran uygulamaları normal pencere sıralamasını geçersiz kılabilir.

## Kontrol

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python tools/preview.py
```

Testler geçici veritabanları kullanır. Önizlemeler `artifacts/` klasörüne yazılır; gerçek görevlerinize örnek veri eklenmez.

Windows'ta görev formunun ana pencerenin önünde açıldığını ve gerçek pencere üzerinden görev ekleme/düzenlemenin çalıştığını kontrol etmek için:

```powershell
uv run --locked python tools/check_task_dialog.py
```

Bu kontrol kısa süreli bir test penceresi açar ve geçici veritabanı kullanır.

Gerçek fare olaylarıyla Bugün listesini sıralama, köşeden boyutlandırma ve form üst barından taşımayı kontrol etmek için:

```powershell
uv run --locked python tools/check_features.py
```

Bu kontrol fareyi birkaç saniye hareket ettirir; gerçek görev verilerini kullanmaz.
