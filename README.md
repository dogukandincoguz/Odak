# Odak

Windows, Linux ve macOS için görev, hatırlatma ve odak sayacı uygulaması. Oturum açıldığında sağ üstte açılır ve diğer normal pencerelerin üzerinde kalır. Varsayılan olarak sistem tepsisinde/macOS menü çubuğunda görünür; menüden görev çubuğu veya Dock simgesi de açılabilir. Kurulumdan sonra çevrimdışı çalışır ve hesap gerektirmez. Görevler bu bilgisayarda saklanır.

## Tek komutla kurulum ve güncelleme

Windows PowerShell 5.1 veya PowerShell 7'yi açıp şu komutu çalıştırın:

```powershell
irm https://raw.githubusercontent.com/dogukandincoguz/Odak/821aa266abfb0fd4de50a63af31fc6494b68c934/bootstrap.ps1 | iex
```

Önceden Git veya Python kurmanız gerekmez; yönetici yetkisi, GitHub hesabı veya token da istenmez. **Kurulum ve güncelleme için internet bağlantısı gerekir.**

Kurulum komutu ve indirilecek uygulama **sabit commitlere bağlıdır**; `dev` veya `main` dalındaki sonraki değişiklikleri kendiliğinden almaz. Betik, uygulama arşivindeki dosya adlarını ve içeriklerini beklenen SHA-256 değeriyle doğrular. Eşleşmezse uygulama dosyalarını ve verileri değiştirmeden durur.

uv yoksa veya sürümü 0.13.5'ten eskiyse [resmi uv 0.13.5 sürüm paketini](https://github.com/astral-sh/uv/releases/tag/0.13.5) indirir; ZIP'i ve `uv.exe` dosyasını ayrı SHA-256 değerleriyle doğruladıktan sonra kullanıcıya özel kurar. Üçüncü taraf bir PowerShell kurucusu çalıştırmaz. Python 3.15.1 yoksa uv üzerinden indirir. Bağımlılıkları `uv.lock` dosyasındaki sürümlerle kurar, masaüstü ve Windows başlangıç kısayollarını oluşturur ve Odak'ı açar.

Kurulumdan sonra masaüstündeki **Odak** kısayolunu kullanabilirsiniz; terminal penceresi açılmaz. **Yeni sürüme geçmek için README'deki güncel kurulum komutunu kullanın.** Önceden kaydettiğiniz komut aynı sürümü yeniden kurar; uygulama güncellemeleri kendiliğinden indirmez.

- Uygulama dosyaları: `%LOCALAPPDATA%\Programs\Odak`
- Görevler, ayarlar ve yedekler: `%LOCALAPPDATA%\Odak\data`
- Otomatik indirilen uv: `%LOCALAPPDATA%\Programs\Odak-Tools\uv\0.13.5\<mimari>`; PATH üzerindeki uv 0.13.5 veya daha yeniyse mevcut kurulum kullanılır.

Uygulama ve veriler ayrı tutulur. Güncelleme öncesi veri yedeği alınır; son üç yedek korunur. Açık Odak normal biçimde kapatılır. Açık bir form veya devam eden bir işlem varsa kurulum durur; formu kaydedip veya kapatıp yeniden deneyin. Ortam doğrulaması başarısız olursa önceki uygulama dosyaları geri konur; aynı komutla yeniden denenebilir. Hedef klasörün boş veya bu betikle yönetilen bir Odak kurulumu olması gerekir.

Eski kaynak kod kurulumundan ilk geçişte mevcut masaüstü kısayolunun veri klasörü bulunur. Yeni konumda henüz veritabanı yoksa eski veritabanı SQLite'ın yedekleme API'siyle kopyalanır; eski veri dosyası korunur. Yeni konumda zaten veritabanı varsa eski kopyayla değiştirilmez.

`irm | iex` bağlantıdaki PowerShell kodunu indirip doğrudan çalıştırır. Çalıştırılacak sabit sürümü [buradan inceleyebilirsiniz](https://github.com/dogukandincoguz/Odak/blob/821aa266abfb0fd4de50a63af31fc6494b68c934/bootstrap.ps1).

Kurulum betiğini dosya olarak indirip çalıştırırken aşağıdaki seçenekler kullanılabilir:

| Parametre | İşlev |
| --- | --- |
| `-InstallDir` | Uygulamanın kurulacağı klasörü seçer. |
| `-DataDir` | Verilerin saklanacağı klasörü seçer; uygulama klasöründen ayrı olmalıdır. |
| `-Ref` | Uygulama sürümünü seçer; varsayılan `ae50f29bc22fd500836f6c6189b903d97dee0967` commitidir. Farklı bir kaynak için `-SourceSha256` da gerekir. |
| `-SourceSha256` | Farklı bir kaynağın önceden incelenmiş dosya adları ve içeriklerine ait SHA-256 değerini belirtir. |
| `-NoLaunch` | Kurulum sonunda uygulamayı açmaz. |
| `-NoShortcuts` | Masaüstü ve Windows başlangıç kısayollarını oluşturmaz veya değiştirmez. |

Örneğin, kısayollara dokunmadan kurmak veya güncellemek için:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/dogukandincoguz/Odak/821aa266abfb0fd4de50a63af31fc6494b68c934/bootstrap.ps1' -OutFile .\odak-bootstrap.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\odak-bootstrap.ps1 -NoShortcuts
```

Aynı kuruluma ait veri klasörü kurulum kaydından hatırlanır. Sistemin kalıcı PowerShell yürütme ilkesini değiştirmeniz gerekmez.

## Otomatik başlatma ve kapatma

Kurulum, Windows hesabınıza girişte Odak'ı başlatan bir kısayol oluşturur. Üç nokta menüsündeki **Başlangıçta çalıştırma: etkin / devre dışı** satırına tıklayarak otomatik başlatmayı kapatıp açabilirsiniz. Satırın yanında tik bulunmaz; yazı mevcut durumu gösterir. Aynı menü Linux ve macOS'ta da kullanılabilir. Bu işlem kullanılan veri klasörünü korur ve masaüstü kısayolunu değiştirmez. Elle kapatmak için `Win+R` → `shell:startup` klasöründeki **Odak** kısayolu da kaldırılabilir. Kurulum komutunu yeniden çalıştırmak bu kısayolu tekrar oluşturur; bunu istemiyorsanız `-NoShortcuts` seçeneğini kullanın.

Üç nokta menüsündeki **Görev çubuğunda göster** seçeneği açılışlar arasında hatırlanır. Açıkken **eksi** düğmesi pencereyi görev çubuğuna küçültür; kapalıyken sistem tepsisine gizler. Hatırlatmalar ve sayaç çalışmaya devam eder. **×** düğmesi uygulamayı tamamen kapatır. Bir sonraki Windows oturumunda otomatik başlatma etkinse yeniden açılır. Daha erken açmak için masaüstü kısayolunu kullanabilirsiniz.

## Kaynak koddan çalıştırma

Geliştirme için Git ve [uv 0.13.5 veya daha yenisi](https://docs.astral.sh/uv/getting-started/installation/) gerekir. Proje Python **3.15.1** kullanır; bulunmuyorsa uv indirir:

```powershell
git clone --branch dev https://github.com/dogukandincoguz/Odak.git
cd Odak
uv sync --locked --python 3.15.1
```

Uygulamayı doğrudan çalıştırmak için:

```powershell
uv run --locked python app.py
```

Masaüstü ve Windows başlangıç kısayollarını oluşturup uygulamayı açmak için:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Launch
```

Kısayollar proje klasörünü kullanır. Klasörü taşırsanız kurulum komutunu yeni konumda tekrar çalıştırın. Windows'ta kaynak koddan çalıştırmada veriler varsayılan olarak projenin `data/` klasöründedir; yukarıdaki tek komutla kurulumun veri konumu farklıdır.

### Linux ve macOS

Git ve uv kuruluysa aynı klonlama/bağımlılık adımlarından sonra:

```sh
sh install.sh --launch
```

Bu komut kullanıcı hesabına bir başlatıcı ve oturum açılış kaydı ekler; yönetici yetkisi istemez. Linux'ta uygulama menüsüne `odak.desktop`, macOS'ta `~/Applications/Odak.app` oluşturur. Kaynak klasörünü ve `.venv` ortamını yerinde tutun. Başlangıç kaydını uygulamanın üç nokta menüsünden kapatıp açabilirsiniz. Kayıt macOS'ta sonraki oturum açılışında uygulanır; uygulama çarpıdan kapatıldığında otomatik yeniden başlatılmaz.

| | Linux | macOS |
| --- | --- | --- |
| Varsayılan veri | `$XDG_DATA_HOME/Odak` veya `~/.local/share/Odak` | `~/Library/Application Support/Odak` |
| Otomatik açılış | `$XDG_CONFIG_HOME/autostart/odak.desktop` veya `~/.config/autostart/odak.desktop` | `~/Library/LaunchAgents/io.github.dogukandincoguz.odak.plist` |
| Görünürlük seçeneği | Görev çubuğunda göster | Dock'ta göster |

Eski bir kaynak kurulumunun `data/odak.sqlite3` dosyası varsa aynı konum kullanılmaya devam eder. `--data-dir` ile özel konum seçilebilir; kurulumda seçilen konum başlatıcıya ve başlangıç kaydına aynen aktarılır. `sh install.sh --no-shortcuts` yalnız ortamı hazırlar; başlangıç/başlatıcı kayıtlarını değiştirmez.

Linux'ta Qt'nin ihtiyaç duyduğu masaüstü kitaplıkları da sistemde bulunmalıdır. Debian/Ubuntu'da `libegl1`, `libopengl0`, `libxkbcommon-x11-0` ve `libxcb-cursor0` paketleri gerekebilir. Sistem tepsisi ve bildirim desteği masaüstü ortamına bağlıdır; tepsi bulunamazsa eksi düğmesi pencereyi erişilemez hâle gizlemez. Wayland'da kesin pencere konumu ve üstte tutma politikasını pencere yöneticisi belirler; X11 ile sağ üste yerleştirme kullanılabilir.

Kaldırırken önce uygulamadan otomatik başlatmayı kapatın, uygulamayı kapatıp oluşturulan başlatıcıyı kaldırın. Görevleri korumak için veri klasörünü saklayın.

Arayüz **PySide6-Essentials (Qt)** ile yazılmıştır; veriler **SQLite** içinde saklanır. Python ortamı ve bağımlılıklar **uv** ile yönetilir. Uygulama [Inter](assets/fonts/README.md) yazı tipini kendi dosyalarından yükler.

## Kullanım

- **Yeni görev / Ctrl+N:** başlık zorunlu; not, tarih ve saat isteğe bağlıdır.
- Yalnız tarih seçilirse o gün **23.59**; yalnız saat seçilirse **bugünün seçilen saati** kabul edilir.
- Deadline'a **24 saatten az** kalan işler kırmızı, **24–72 saat** kalanlar sarıdır. Daha uzak veya deadline'ı olmayan görevler normal renktedir.
- Süresi dolan işler **Geçenler → Deadline’ı geçenler** bölümüne otomatik taşınır.
- Tik simgesi görevi tamamlar; tamamlananlar **Bitenler** bölümünden yeniden açılabilir.
- Kartın solundaki altı noktalı tutamağı sürükleyerek görevleri yukarı veya aşağı taşıyabilirsiniz. Her listenin sırası ayrı kaydedilir; **Bugün** sırası diğer listelerden bağımsızdır. İlk elle sıralamadan sonra yeni gelen görevler o listenin sonuna eklenir. Arama sırasında tutamaklar gizlenir; temizleyince geri gelir. Tutamak odaktayken yukarı/aşağı okları da sıralamayı değiştirir.
- Silinen işler **Silinenler → Son silinenler** alanından **10 dakika** boyunca geri alınabilir. Süre uygulama kapalıyken de ilerler; süresi dolan kayıtlar uygulama çalışırken kalıcı olarak temizlenir.
- Kalem simgesi başlığı, notu, deadline'ı ve alt adımları düzenler. **Görevler** bölümünde **Ctrl+F** arama alanına geçer; arama seçili listedeki başlık ve notları tarar.
- Sağ alttaki tepsi simgesine tıklayarak veya sağ tık → **Odak’ı göster** ile pencereyi geri açabilirsiniz. Üç nokta menüsünden sağ üste yeniden yerleştirilebilir.
- Pencereyi üstteki logo veya başlık alanından sol tıkla tutup sürükleyerek taşıyabilirsiniz. Konum kaydedilmez; her yeni açılışta yine sağ üst köşede başlar.
- Kenarlardan veya sağ alt köşedeki tutamaktan pencereyi boyutlandırabilirsiniz. Boyut kaydedilir; sonraki açılışta bu boyutla sağ üstte açılır. Yeni görev, hatırlatma ve şablon pencereleri kendi üst barlarından taşınır; üstteki kutusuz `×` formu kapatır.
- Uygulama birlikte gelen **Inter** yazı tipini kullanır; ayrıca font kurulumu gerekmez. Yazı tipi [SIL Open Font License 1.1](assets/fonts/OFL.txt) lisansıyla dağıtılır.
- Odak kısayolunu tekrar açmak, aynı veri klasörünü kullanan mevcut pencereyi öne getirir; ikinci kopya çalışmaz.

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
- **Bir kez:** gelecekteki bir tarih ve saatte tek bildirim. Bildirimden sonra erteleme için kayıt geçici olarak kalır; etkinlikten veya son ertelemeden 24 saat sonra uygulama çalışırken otomatik temizlenir. Eski tek seferlik kayıtlar birikmez.
- **Aylık · belirli gün:** 1–31 veya **Ayın son günü**, 1–52 ayda bir. Seçilen günün bulunmadığı aylar atlanır; son gün seçimi şubat ve artık yılları takip eder.
- **Aylık · haftanın belirli günü:** ilk, ikinci, üçüncü, dördüncü veya son pazartesi/cuma gibi bir gün; 1–52 ayda bir.
- **Bildirim:** etkinlik saatinde veya 5, 10, 30 dakika önce. Örneğin 14.00 toplantısı için 10 dakika önce seçilirse 13.50'de haber verilir; 14.00'te ikinci bildirim oluşmaz. Kartta etkinlik saati ile bildirim tercihi ayrı görünür.
- **Toplantıyı aç:** kaydedilmiş HTTP/HTTPS bağlantısını varsayılan tarayıcıda açar. Bağlantı hem karttan hem bildirime tıklayınca açılan pencereden kullanılabilir.

Her hatırlatma tek kayıttır; tekrarlarda yeni görev veya geçmiş kaydı üretilmez.

- Bildirimlerin gelmesi için Odak açık olmalıdır; sistem tepsisine gizlenebilir. Windows bildirim ayarları izin verdiğinde zamanı gelince bildirim görünür. Bildirime tıklayarak **10 dakika sonra hatırlat** seçebilirsiniz. Bu işlem düzenli programı değiştirmez.
- Düzenli hatırlatmalarda **Bu tekrarı atla**, sıradaki takvim zamanını atlar. **Duraklat / devam ettir** programı silmeden kapatıp açar. Tek seferlik hatırlatmanın tarihini düzenleyebilir veya kaydı silebilirsiniz.
- Tamamlandı düğmesi bulunmaz; hatırlatmalar görev veya deadline'ı geçenler listelerine eklenmez.
- Silinen hatırlatmalar bu bölümün sağındaki **Son silinenler** sekmesinden 10 dakika geri alınabilir.
- Uygulama kapalıyken geçen eski bildirimler birikmez. Açılışta bildirim saati son 15 dakika içinde geçmiş olan veya bildirim saati geçmiş olsa da etkinliği henüz başlamamış bir hatırlatma gösterilebilir. Daha eski düzenli hatırlatmalar sonraki takvim zamanına ilerler. Yeni hatırlatmanın ön bildirim saati geçmişse ve etkinlik hâlâ gelecekteyse hemen haber verilir.

## Odak sayacı

Üstteki **Odaklan** bölümünden görev seçin veya **Serbest odak** kullanın. Varsayılan süreler 25 dakika çalışma ve 5 dakika moladır; değiştirilebilir. Başlatma, duraklatma ve sıfırlama desteklenir. Süre bitince bildirim gelir; sonraki çalışma veya mola süresini kendiniz başlatırsınız. Görevler otomatik tamamlanmaz.

Sayaç tepsiye gizlendiğinde çalışır ve açılışlar arasında durumunu korur. Uygulama kapalıyken bildirim vermez; yeniden açıldığında geçen süreyi hesaba katar. Yalnızca ayarlar ve geçerli sayaç durumu tutulur; oturum geçmişi biriktirilmez.

## Yedekleme ve aktarım

Üç nokta menüsünden:

- **Dışa aktar:** görevleri, adımları, liste sıralarını, hatırlatma kurallarını ve şablonları taşınabilir JSON dosyasına kaydeder. Pencere ve sayaç ayarları JSON'a dahil edilmez.
- **İçe aktar:** JSON'daki yeni kayıtları ekler. Aynı kimlikli mevcut kayıtları değiştirmez.
- **Şimdi yedek al:** veritabanının güvenli anlık kopyasını alır.
- **Yedekten geri yükle:** mevcut verileri seçilen yedekle değiştirir; işlem öncesi mevcut durumun yedeği alınır.

Uygulama açıkken günlük otomatik yedek alınır. Kullanılan veri klasörünün **backups/** alt klasöründe en fazla **3 yedek** tutulur. Tek komutla kurulumda konumu `%LOCALAPPDATA%\Odak\data\backups`, kaynak koddan çalıştırmada `proje/data/backups` olur. Otomatik, elle ve güncelleme sırasında alınan kopyalar aynı sınıra dahildir. Bildirim geçmişi, sayaç oturum geçmişi veya ek dosyalar saklanmadığı için büyüme esas olarak yazdığınız metin ve alt adımlara bağlıdır.

Örnek ölçümde, her biri 500 bayt not içeren 3.650 görev yaklaşık 2,7 MB; 36.500 görev yaklaşık 27 MB yer kapladı. Her göreve ayrıca beş alt adım eklendiğinde boyutlar sırasıyla yaklaşık 6,6 MB ve 65,6 MB oldu. Daha uzun metinler bu boyutu artırır. Üç tam yedek yaklaşık üç ek veritabanı kadar alan kullanır. Bu ölçümler bir boyut garantisi değildir.

## Veriler

Görevler, hatırlatmalar, şablonlar ve ayarlar her değişiklikte yerel SQLite veritabanına kaydedilir. Windows'taki varsayılan konumlar aşağıdadır; diğer sistemlerin veri klasörleri **Linux ve macOS** bölümünde belirtilmiştir:

| Dosya veya klasör | Tek komutla kurulum | Kaynak koddan çalıştırma |
| --- | --- | --- |
| Veritabanı | `%LOCALAPPDATA%\Odak\data\odak.sqlite3` | `proje/data/odak.sqlite3` |
| Yedekler | `%LOCALAPPDATA%\Odak\data\backups` | `proje/data/backups` |
| Hata kaydı | `%LOCALAPPDATA%\Odak\data\odak.log` | `proje/data/odak.log` |

Özel bir veri klasörü seçtiyseniz kısayolun `--data-dir` argümanı kullanılan konumu gösterir. Uygulama görev verilerini bir sunucuya göndermez. Dışa aktardığınız JSON dosyaları ve veritabanı yedekleri görevlerinizi, notlarınızı ve toplantı bağlantılarınızı içerir; bunları paylaşmadan önce içeriğini kontrol edin.

Elle klasör yedeği almak için uygulamayı kapatıp veri klasörünün tamamını kopyalayın veya uygulamadaki yedekleme menüsünü kullanın. Eski sürümün görevleri ilk açılışta yeni alanlar eklenerek korunur.

Deadline'lar bilgisayarın yerel saatine göre değerlendirilir. Otomatik başlatma, kullanıcı oturumu açıldığında gerçekleşir. Windows'un güvenli masaüstü ve özel tam ekran uygulamaları normal pencere sıralamasını geçersiz kılabilir.

## Kaldırma

Önce verilerinizi yedekleyip Odak'ı kapatın. Masaüstündeki ve `Win+R` → `shell:startup` klasöründeki **Odak** kısayollarını kaldırın. Tek komutla kurduysanız `%LOCALAPPDATA%\Programs\Odak` klasörünü silebilirsiniz; kaynak koddan çalıştırıyorsanız proje klasöründe varsayılan olarak verilerinizin de bulunduğunu unutmayın.

Tek komutla kurulumun veri klasörü uygulama klasöründen ayrıdır. Görevlerinizi saklamak istiyorsanız `%LOCALAPPDATA%\Odak\data` klasörünü koruyun. Özel kurulum veya veri konumu seçtiyseniz kendi klasörlerinizi esas alın.

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

Tek komutla kurulumu gerçek PowerShell 5.1, geçici program/veri klasörleri ve ayrı test kısayollarıyla kontrol etmek için:

```powershell
uv run --locked python tools/check_bootstrap.py --clean-runtime
uv run --locked python tools/check_bootstrap.py --powershell-seven
```

İlk komut uv ve Python'un bulunmadığı durumu da dener. Testler mevcut görevleri veya masaüstü/başlangıç kısayollarını değiştirmez; bağımlılık indirmeleri için internet gerekir.
