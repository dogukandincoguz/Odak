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
- `×` uygulamayı kapatır. Odak kısayolunu tekrar açmak var olan pencereyi öne getirir; ikinci kopya çalışmaz.

## Veriler

Tüm görevler proje içindeki **data/odak.sqlite3** dosyasına her değişiklikte kaydedilir. Veri tamamen bu bilgisayarda kalır. Yedek almak için uygulamayı kapatıp **data** klasörünü kopyalayın. Uygulamayı kaldırmak isterseniz önce verilerinizi yedekleyin. Hata kayıtları `data/odak.log` dosyasındadır.

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
