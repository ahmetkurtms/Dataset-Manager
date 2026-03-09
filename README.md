# Dataset Manager

Bu araç, **bitirme projemiz** kapsamında seçtiğimiz veri setini (tez_dataset) incelemek, yönetmek ve temizlemek amacıyla geliştirdiğimiz web tabanlı bir veri seti tarayıcısıdır. YOLO formatında etiketlenmiş görüntü verilerinizi kolayca filtreleyebilir, bounding box çizimlerini gözden geçirebilir ve istemediğiniz/hatalı verileri hızlıca silebilirsiniz.

## Özellikler

- **Detaylı Filtreleme:** Görüntüleri `Split` (train, test, val), `Modalite` (RGB, Thermal), `Sınıf` (airplane, bird, vs.) ve `Boyut` (small, large) parametrelerine göre ayrıştırın.
- **İstatistik ve Kombinasyon Analizi:** Veri setinizdeki veri dağılımını 16'lı kombinasyon ızgarası üzerinden detaylı olarak analiz edin.
- **YOLO Etiket Görüntüleme:** Resimler üzerindeki YOLO formatındaki etiket (bounding box) çizimlerini doğrudan tarayıcı üzerinde görüntüleyin.
- **Hızlı Temizlik:** İhtiyaç duymadığınız resimleri ve bunlara ait `.txt` etiket dosyalarını arayüz üzerinden veya klavye kısayolu ile anında silin.
- **Klavye Kısayolları:** Sağ/Sol ok tuşlarıyla resimler arası geçiş, `Delete` ile silme ve `Esc` ile modal penceresinden çıkış desteği.

## Veri Seti Yapısı ve İsimlendirme Kuralları

Uygulamanın metadataları okuyabilmesi için veri setinin özel bir düzende olması gerekmektedir.

### 1. Dosya İsimlendirme Formatı
Görüntü isimlerinde çift alt tire (`__`) ile ayrılmış metadatalar bulunmalıdır:
`{orijinal_isim}__{modalite}__{sinif}__{obje_boyutu}.ext`

**Örnek:** `frame001__rgb__drone__small.jpg`

- **Modalite (Modality):** `rgb`, `thermal`
- **Sınıf (Class):** `airplane`, `bird`, `drone`, `helicopter`
- **Obje Boyutu (Size):** `small`, `large`

> **Not:** Sistem `.jpg`, `.jpeg`, `.png`, ve `.webp` uzantılarını desteklemektedir.

### 2. Klasör Yapısı
Proje, YOLO klasör ağacını temel alan aşağıdaki yapıyı beklemektedir. Bitirme projemiz için hazırladığımız veri setinde de bu yapı (train/test/val) mevcuttur:

```text
veri_seti_klasoru/
├── train/
│   ├── images/      # Görüntüler burada
│   └── labels/      # YOLO formatlı .txt dosyaları burada
├── test/
│   ├── images/
│   └── labels/
└── val/
    ├── images/
    └── labels/
```

## Kurulum ve Başlangıç

### Gereksinimlerin Kurulması
Projeyi klonladıktan sonra dizine gidin ve gerekli Python kütüphanelerini yükleyin:

```bash
pip install -r requirements.txt
```
*(Proje temel olarak `Flask` ve `Pillow` kullanmaktadır.)*

### Uygulamanın Çalıştırılması

Varsayılan ayarlarla (veri setinin `~/Downloads/tez_dataset/flat_dataset` konumunda olduğu varsayılarak) çalıştırmak için:
```bash
python app.py
```

**Farklı bir veri seti dizini belirtmek için:**
```bash
python app.py --dataset /kendi/veri/setim/yolu --port 8080
```

Tarayıcınızdan `http://localhost:5000` (veya belirlediğiniz port numarası) adresine giderek arayüze ulaşabilirsiniz.

## 🚀 Genel Kullanım Rehberi (Nasıl Kullanılır?)

Uygulamayı başlattıktan sonra tarayıcı üzerinden şu işlemleri gerçekleştirebilirsiniz:

1. **Arayüze Giriş ve İstatistikler:**
   - Sayfanın üst kısmında, veri setinize ait **toplam resim sayısını** ve sınıflara ayrılmış dağılımlarını göreceksiniz.
   - `16 Combinations` (16'lı Kombinasyon) panosuna tıklayarak hangi sınıftan hangi kamerayla (RGB/Thermal) ve ne büyüklükte (Small/Large) kaç adet veri olduğunu inceleyebilirsiniz.

2. **Verileri Filtreleme:**
   - Üst kısımdaki filtreleme butonlarını (Split, Modalite, Sınıf, Obj Size) kullanarak sadece ilgilendiğiniz verileri ekrana getirebilirsiniz. Örneğin: *Sadece Test setindeki, Termal kamerayla çekilmiş, Küçük boyutlu (Small) Dronları (Drone)* görebilirsiniz.
   
3. **Resimleri İnceleme (Bounding Box):**
   - İlgilendiğiniz veya şüpheli bulduğunuz bir resmin üzerine tıklayın.
   - Açılan büyük ekranda (modal) YOLO formatındaki etiketleriniz resmin üzerinde yeşil (veya sınıfa özel renklerde) kutular (bounding box) şeklinde görünecektir. 
   - Kutuların üzerinde etiketin tahmin sınıfı ve kapladığı alan yüzdesi (ör: `drone 15.2%`) yazar.

4. **Veri Temizleme (Hızlı İlerleyiş):**
   - Açılan resim ekranındayken klavyenizin **Sağ/Sol Yön Tuşlarını** (`→` / `←`) kullanarak resimler arasında hızlıca gezinebilirsiniz.
   - Eğer hatalı çizilmiş, bulanık veya bozuk bir etiket/veri görürseniz; klavyenizdeki **`Delete`** tuşuna (veya ekrandaki `🗑 Delete` butonuna) basarak resmi ve ona ait `.txt` dosyasını anında veri setinden silebilirsiniz. (Silmeden önce onaylayıp onaylamadığınız sorulur).
   - Çıkmak için **`Esc`** tuşuna basabilir veya sağ üstteki `x` butonuna tıklayabilirsiniz.
