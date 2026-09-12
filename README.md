# BIST Long Tarayıcı

Global-100 Trade Intelligence indikatörünün sinyal mantığı Python'a çevrildi.
Her akşam tüm Borsa İstanbul hisselerini günlük barlarda tarar, **AI Buy** ve
**CCI Long** sinyali üretenleri Telegram'a gönderir. Ayrıca web dashboard'u var.

Bu repo GitHub + Railway kurulumu için hazırlandı.

---

## Dosyalar

```
├── README.md                    bu dosya
├── requirements.txt             Python bağımlılıkları
├── runtime.txt                  Python sürümü (3.12)
├── .gitignore                   .env ve önbelleği repo dışında tutar
├── railway.scanner.json         cron servisinin ayarları
├── railway.dashboard.json       web servisinin ayarları
├── .streamlit/
│   └── config.toml              dashboard teması + statik dosya sunumu
└── bist_screener/
    ├── __init__.py
    ├── pine.py                  Pine Script fonksiyonlarının Python karşılıkları
    ├── engine.py                26 SBS göstergesi + YZ AI + CCI sinyal motoru
    ├── data.py                  BIST sembol listesi ve veri indirme
    ├── scan.py                  tarama döngüsü (terminalden de çalışır)
    ├── notify.py                Telegram gönderimi
    ├── daily.py                 günlük iş — cron bunu çağırır
    ├── pwa.py                   telefon uygulaması etiketleri
    ├── app.py                   Streamlit dashboard
    └── static/                  manifest.json + uygulama simgeleri
```

Hepsi gerekli. Fazladan bir şey yok.

---

## Sembol listesi nereden geliyor

Bot tam BIST listesini sırayla üç kaynaktan dener:

1. **TradingView screener uç noktası** — kimlik doğrulama istemez, ek paket
   gerektirmez, tüm payları tek istekte döner. Normalde bu çalışır.
2. **isyatirimhisse** paketi — kuruluysa.
3. **Repodaki yedek liste** — 109 hisse.

Dashboard'da özet kartlarının altında hangi kaynağın kullanıldığı yazar. Orada
"yedek liste" görüyorsanız ilk iki kaynak başarısız olmuş demektir; taranan hisse
sayısı da 106 civarında kalır. Railway loglarına bakmak gerekir.

---

## Adım 1 — Telegram botu

1. Telegram'da **@BotFather**'a `/newbot` yazın, isim verin. Size bir token verir.
2. **@userinfobot**'a herhangi bir mesaj atın. `Id` alanındaki sayı chat id'niz.
   Bildirim bir gruba gidecekse botu gruba ekleyip grubun id'sini kullanın
   (grup id'leri `-100` ile başlar).

Bu iki değeri bir kenara not edin, Adım 3'te gireceksiniz.

---

## Adım 2 — GitHub

1. GitHub'da yeni bir **private** repo açın.
2. Bu klasördeki tüm dosyaları repoya yükleyin (web arayüzünden sürükleyip
   bırakabilirsiniz; `bist_screener` klasörünün yapısını koruyun).

`.gitignore` `.env` dosyasını dışarıda tutar. Zaten Railway'de token'ları
dosyaya değil, panele gireceksiniz.

---

## Adım 3 — Railway: tarayıcı servisi

Railway → **New Project** → **Deploy from GitHub repo** → reponuzu seçin.

Servis oluştuktan sonra **Settings** sekmesinde:

| Ayar | Değer |
|---|---|
| Config-as-code / Railway Config File | `railway.scanner.json` |
| Cron Schedule | `30 15 * * 1-5` |

**Variables** sekmesinde:

| Değişken | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'dan aldığınız token |
| `TELEGRAM_CHAT_ID` | @userinfobot'tan aldığınız sayı |
| `TZ` | `Europe/Istanbul` |

**Cron neden 15:30?** Railway cron ifadelerini UTC olarak değerlendirir.
18:30 Türkiye saati = 15:30 UTC. `1-5` pazartesi–cuma demektir.

Kaydedin, Railway otomatik deploy eder.

### Test edin

Beklemeden denemek için Settings → Cron Schedule'ı geçici olarak birkaç dakika
sonrasına alın, mesaj gelince asıl değere geri çevirin. Ya da servisi manuel
redeploy edin — start command hemen çalışır.

İlk çalıştırma tüm piyasa için 2–5 dakika sürer.

---

## Adım 4 — Railway: dashboard servisi (isteğe bağlı)

Sadece Telegram bildirimi istiyorsanız bu adımı atlayın.

Aynı projede **New** → **GitHub Repo** → **aynı repoyu** seçin. İkinci servis
oluşur. Settings'te:

| Ayar | Değer |
|---|---|
| Config-as-code / Railway Config File | `railway.dashboard.json` |
| Networking | **Generate Domain** |
| Cron Schedule | **boş bırakın** |

Variables:

| Değişken | Değer |
|---|---|
| `DASHBOARD_PASSWORD` | kendi seçeceğiniz bir parola |
| `TZ` | `Europe/Istanbul` |

Railway size `xxx.up.railway.app` gibi bir adres verir; telefondan da açılır.

**`DASHBOARD_PASSWORD` mutlaka tanımlayın.** Bu adres herkese açıktır ve
Streamlit'in kendi giriş ekranı yoktur. Değişken tanımlıysa uygulama parola
sorar, tanımlı değilse kapı devre dışı kalır.

Bu servis 7/24 açık kalır ve saatlik ücretlendirilir. Maliyeti sevmiyorsanız
dashboard'u kendi bilgisayarınızda çalıştırın (aşağıda).

---

## Telegram mesajı neye benziyor

```
BIST Long Tarama · 05.09.2026 18:30
Taranan 612 hisse · 14 sinyal · veri 05.09

🔷 STRONG BUY
THYAO     312.50  ▲ 2.41%  AL 21/26  YZ 78

🟩 AI Buy + CCI Long
ASELS      88.75  ▼ 0.62%  AL 19/26  YZ 71

🟢 AI Buy
KRDMD      24.06  ▲ 1.18%  AL 15/26  YZ 64

🔵 CCI Long
SISE       41.90  ▲ 0.33%  AL 14/26  YZ 58
```

Ardından tam liste CSV olarak ek dosya şeklinde gelir. Sinyal çıkmadığı günlerde
de mesaj gider. Tarama hata alırsa hata metni Telegram'a düşer — bot sessizce
ölmez.

---

## Telefona uygulama olarak kurmak (Android)

1. Railway adresinizi telefonda **Chrome** ile açın.
2. Sağ üstteki **⋮** → **Ana ekrana ekle** / **Uygulamayı yükle**.
3. Ana ekranda mum grafiği simgesiyle görünür.

Arayüz telefonda otomatik olarak sadeleşir: kenar çubuğu kapalı açılır, özet
kartları ikişerli dizilir ve 12 kolonlu tablo yerine hisse başına bir kart
listesi gelir. Geniş ekranda tam tablo geri gelir; hangisinin görüneceğine CSS
karar verir, ayar yapmanız gerekmez.

### Adres çubuğu hâlâ görünüyorsa

Chrome'un uygulamayı tam ekran (WebAPK) kurabilmesi için sitenin kökünde bir
service worker olması gerekir. Streamlit dosyaları yalnızca `/app/static/`
altından sunar, o yüzden service worker'ın kapsamı köke ulaşmaz. Sonuç: simge ve
uygulama adı çalışır, ama Chrome bunu tam ekran uygulama yerine kısayol olarak
kurabilir ve üstte ince bir adres çubuğu kalır.

Tam ekran istiyorsanız Streamlit'in önüne kökten dosya sunabilen küçük bir
ters vekil sunucu (Caddy veya nginx) koymak gerekir; bu, dağıtımı Dockerfile'a
çevirmek demektir. Şu anki kurulumu bozmamak için o adımı ayrı tuttum.

---

## Tema

Varsayılan koyu tema `.streamlit/config.toml` dosyasındadır. Sağ üstteki **⋮ →
Settings → Theme** menüsünden açık/koyu arasında anlık geçiş yapabilirsiniz;
arayüz ve grafik ikisine de uyum sağlar.

Açık temayı kalıcı varsayılan yapmak isterseniz `config.toml` içindeki `[theme]`
bloğunu bununla değiştirin:

```toml
[theme]
base = "light"
primaryColor = "#0E8F95"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1F4F8"
textColor = "#16202C"
font = "sans serif"
```

---

## Kenar çubuğundaki ayarlar ne işe yarıyor

Panel iki bölüme ayrılmıştır. **Tarama ayarları** değiştiğinde yeniden tarama
gerekir; değiştirip taramadan bırakırsanız sayfa sizi uyarır. **Liste filtresi**
altındakiler mevcut sonuca anında uygulanır.

| Ayar | Ne yapar |
|---|---|
| **Sinyal tazeliği** | Sinyal, eşiğin kesildiği barda bir kez tetiklenir. 1 sadece bugünü gösterir; 3 yaparsanız son üç günde tetiklenenler de listeye girer. Dün kaçırdığınız sinyalleri yakalar, karşılığında liste eskir ve uzar. |
| **Classifier Sensitivity** | YZ AI motorunun RSI/CCI/ATR periyodu. Düşük değer daha erken ve daha çok sinyal, daha çok gürültü. |
| **Long Threshold** | CCI Long sinyalinin tetiklendiği eşik. |
| **Altın/Ölüm kesişim filtresi** | Açıkken Long girişleri yalnız EMA50 > EMA200 olan hisselerde sayılır. Yalnızca Strong Buy ve Long Giriş etiketlerini etkiler — AI Buy ve CCI Long bundan bağımsızdır. Listeyi bölgeye göre daraltmak istiyorsanız aradığınız şey **Sadece Golden Zone** filtresidir. |
| **Minimum ADX** | ADX trendin gücünü ölçer, yönünü değil. 20'nin altı genelde yatay/kararsız piyasadır ve orada sinyaller sık yanlış çıkar. 20–25 vermek yatay seyredenleri eler, 0 hepsini geçirir. |
| **Minimum SBS AL skoru** | 26 göstergeden en az kaçının AL demesi gerektiği. |

---

## Eşikleri ayarlama

`bist_screener/daily.py` dosyasının başındaki sabitler:

```python
MIN_HACIM = 500_000   # bu lotun altındaki hisseleri eleme
MIN_AL    = 13        # 26 göstergeden en az kaçı AL demeli
LOOKBACK  = 1         # 1 = sadece son kapanmış bar
MAX_SATIR = 40        # mesajda listelenecek azami hisse
```

İlk canlı taramadan sonra listeyi kalabalık bulursanız `MIN_AL`'ı 17'ye çekin.
Dosyayı GitHub'da düzenleyip commit'lediğinizde Railway otomatik yeniden deploy eder.

---

## Kendi bilgisayarınızda çalıştırmak

```bash
pip install -r requirements.txt
streamlit run bist_screener/app.py        # dashboard
python -m bist_screener.scan              # terminalden tarama
```

Telegram'ı yerelde denemek için proje kökünde bir `.env` dosyası açın:

```
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=987654321
```

```bash
python -m bist_screener.daily --test      # bağlantıyı doğrula
python -m bist_screener.daily --zorla     # tam taramayı çalıştır
```

`.env` dosyası `.gitignore`'da, repoya gitmez.

---

## Railway cron'un iki kuralı

1. **Servis işini bitirince çıkmak zorunda.** `daily.py` öyle çalışıyor, ama
   Railway panelinde bir çalıştırma "Active" takılı görünüyorsa sonraki
   tetiklemeler atlanır. Zamanlama durursa ilk oraya bakın.
2. **Minimum aralık 5 dakika.** Günde bir çalıştırma için sorun değil.

`railway.scanner.json` içinde `restartPolicyType` bilerek `NEVER` yapıldı.
Railway'in varsayılanı başarısız bir çalıştırmayı 10 kez tekrarlar — bu da bir
hatada 10 tane hata mesajı demek olurdu.

---

## Bilinmesi gereken iki fark

1. **VWAP.** Pine'ın `ta.vwap`'ı seans başında sıfırlanır. Günlük barda her bar
   bir seans olduğu için VWAP = hlc3'e eşit olur. Kod da bunu böyle uyguluyor,
   TradingView'de günlük grafikte gördüğünüzle aynı sonucu verir.
2. **Veri kaynağı.** yfinance BIST verisi düzeltilmemiş gelir. Temettü ve
   bedelsizlerde uzun vadeli EMA'lar TradingView'in düzeltilmiş serisinden
   sapabilir. İlk kurulumda birkaç hisseyi TradingView'le karşılaştırıp
   doğrulamanız iyi olur.

Motorun doğruluğu için CCI, RSI, linear regression ve Parabolic SAR manuel
hesapla karşılaştırılarak test edildi; Wilder yumuşatması, `ta.dev`, `ta.linreg`
ve `ta.sar` TradingView'in referans uygulamalarına göre yazıldı.

---

Tarama sonuçları bir ön eleme aracıdır, yatırım tavsiyesi değildir.
