"""
Haber İzleme Sistemi - cPanel/Passenger için
his.utftoplulugu.com
7/24 otomatik güncelleme
"""

from flask import Flask, render_template_string, jsonify, request, redirect, session
import feedparser
import hashlib
import secrets
import threading
import time
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ==========================================
# AYARLAR - BUNLARI DEĞİŞTİR!
# ==========================================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"  # ÖNEMLİ: Bunu değiştir!
TARAMA_ARALIGI = 5  # dakika

# ==========================================
# VERİ DEPOSU
# ==========================================
haberler_db = {"son_guncelleme": "-", "istatistikler": {"toplam": 0}, "haberler": []}
son_tarama = None

# ==========================================
# KATEGORİLER VE ANAHTAR KELİMELER
# ==========================================
KATEGORILER = {
    "ekonomi": ["ekonomi", "economy", "büyüme", "growth", "enflasyon", "inflation", "faiz", "interest", "merkez bankası", "central bank", "tcmb", "fed", "gdp", "gsyih", "tüik", "hazine", "bütçe", "budget", "vergi", "tax", "işsizlik", "unemployment"],
    "finans": ["finans", "finance", "banka", "bank", "kredi", "credit", "yatırım", "investment", "döviz", "currency", "dolar", "dollar", "euro", "altın", "gold", "tahvil", "bond", "bddk", "spk"],
    "borsa": ["borsa", "stock", "hisse", "share", "bist", "nasdaq", "dow jones", "s&p", "endeks", "index", "wall street", "ipo", "halka arz", "rally", "trading"],
    "lojistik": ["lojistik", "logistics", "tedarik", "supply chain", "kargo", "cargo", "nakliye", "shipping", "konteyner", "container", "liman", "port", "depo", "warehouse"],
    "ticaret": ["ticaret", "trade", "ihracat", "export", "ithalat", "import", "gümrük", "customs", "tarife", "tariff", "yaptırım", "sanction", "embargo"],
    "tarim": ["tarım", "agriculture", "çiftçi", "farmer", "buğday", "wheat", "mısır", "corn", "gıda", "food", "hasat", "harvest", "tmo", "gübre"],
    "surdurulebilirlik": ["sürdürülebilirlik", "sustainability", "yeşil enerji", "green energy", "solar", "güneş", "rüzgar", "wind", "karbon", "carbon", "iklim", "climate", "esg", "elektrikli araç"],
    "yapay_zeka": ["yapay zeka", "artificial intelligence", " ai ", "çip", "chip", "nvidia", "openai", "chatgpt", "machine learning", "robot", "otomasyon", "gpu", "semiconductor"],
    "politika": ["trump", "biden", "erdoğan", "putin", "başkan", "president", "hükümet", "government", "seçim", "election", "politika", "policy", "yasa", "law"]
}

YUKSEK_ONEM = ["acil", "urgent", "kriz", "crisis", "rekor", "record", "tarihi", "historic", "şok", "shock", "breaking", "son dakika", "savaş", "war", "çöküş", "crash"]

# ==========================================
# RSS KAYNAKLARI (70+)
# ==========================================
RSS_KAYNAKLAR = {
    # === YABANCI KAYNAKLAR ===
    "Reuters Business": ("https://feeds.reuters.com/reuters/businessNews", "en"),
    "Reuters World": ("https://feeds.reuters.com/Reuters/worldNews", "en"),
    "Reuters Tech": ("https://feeds.reuters.com/reuters/technologyNews", "en"),
    "Bloomberg Markets": ("https://feeds.bloomberg.com/markets/news.rss", "en"),
    "Bloomberg Tech": ("https://feeds.bloomberg.com/technology/news.rss", "en"),
    "CNBC": ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "en"),
    "CNBC World": ("https://www.cnbc.com/id/100727362/device/rss/rss.html", "en"),
    "BBC Business": ("http://feeds.bbci.co.uk/news/business/rss.xml", "en"),
    "BBC World": ("http://feeds.bbci.co.uk/news/world/rss.xml", "en"),
    "BBC Tech": ("http://feeds.bbci.co.uk/news/technology/rss.xml", "en"),
    "Financial Times": ("https://www.ft.com/rss/home", "en"),
    "MarketWatch": ("https://feeds.marketwatch.com/marketwatch/topstories/", "en"),
    "NY Times Business": ("https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "en"),
    "NY Times World": ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
    "Guardian Business": ("https://www.theguardian.com/uk/business/rss", "en"),
    "TechCrunch": ("https://techcrunch.com/feed/", "en"),
    "TechCrunch AI": ("https://techcrunch.com/category/artificial-intelligence/feed/", "en"),
    "Wired": ("https://www.wired.com/feed/rss", "en"),
    "The Verge": ("https://www.theverge.com/rss/index.xml", "en"),
    "Ars Technica": ("https://feeds.arstechnica.com/arstechnica/index", "en"),
    "VentureBeat AI": ("https://venturebeat.com/category/ai/feed/", "en"),
    
    # === TÜRK DEVLET KURUMLARI ===
    "TCMB Duyurular": ("https://www.tcmb.gov.tr/wps/wcm/connect/tcmb+tr/tcmb+tr/main+menu/duyurular/rss/duyurular_rss", "tr"),
    "Hazine Bakanlığı": ("https://www.hmb.gov.tr/rss/haberler", "tr"),
    "Ticaret Bakanlığı": ("https://www.ticaret.gov.tr/rss/haberler", "tr"),
    "Tarım Bakanlığı": ("https://www.tarimorman.gov.tr/Rss/Haberler", "tr"),
    "Sanayi Bakanlığı": ("https://www.sanayi.gov.tr/rss/haberler", "tr"),
    "Enerji Bakanlığı": ("https://enerji.gov.tr/rss/haberler", "tr"),
    "TÜİK": ("https://data.tuik.gov.tr/rss/haber.rss", "tr"),
    "BDDK": ("https://www.bddk.org.tr/Rss/Duyurular", "tr"),
    "SPK": ("https://www.spk.gov.tr/rss/duyurular", "tr"),
    "Borsa İstanbul": ("https://www.borsaistanbul.com/tr/rss/haberler", "tr"),
    "KOSGEB": ("https://www.kosgeb.gov.tr/rss/duyurular", "tr"),
    "TÜBİTAK": ("https://www.tubitak.gov.tr/rss/haberler", "tr"),
    
    # === TÜRK MEDYA ===
    "Anadolu Ajansı Ekonomi": ("https://www.aa.com.tr/tr/rss/default.aspx?cat=ekonomi", "tr"),
    "Anadolu Ajansı Gündem": ("https://www.aa.com.tr/tr/rss/default.aspx?cat=gundem", "tr"),
    "Anadolu Ajansı Dünya": ("https://www.aa.com.tr/tr/rss/default.aspx?cat=dunya", "tr"),
    "Anadolu Ajansı Teknoloji": ("https://www.aa.com.tr/tr/rss/default.aspx?cat=bilim-teknoloji", "tr"),
    "DW Türkçe": ("https://rss.dw.com/xml/rss-tur-all", "tr"),
    "NTV Ekonomi": ("https://www.ntv.com.tr/ekonomi.rss", "tr"),
    "NTV Dünya": ("https://www.ntv.com.tr/dunya.rss", "tr"),
    "NTV Teknoloji": ("https://www.ntv.com.tr/teknoloji.rss", "tr"),
    "Hürriyet Ekonomi": ("https://www.hurriyet.com.tr/rss/ekonomi", "tr"),
    "Hürriyet Dünya": ("https://www.hurriyet.com.tr/rss/dunya", "tr"),
    "Sözcü Ekonomi": ("https://www.sozcu.com.tr/rss/ekonomi.xml", "tr"),
    "Sözcü Dünya": ("https://www.sozcu.com.tr/rss/dunya.xml", "tr"),
    "T24 Ekonomi": ("https://t24.com.tr/rss/haber/ekonomi", "tr"),
    "T24 Dünya": ("https://t24.com.tr/rss/haber/dunya", "tr"),
    "Dünya Gazetesi": ("https://www.dunya.com/rss", "tr"),
    "BloombergHT": ("https://www.bloomberght.com/rss", "tr"),
    "BigPara": ("https://bigpara.hurriyet.com.tr/rss/", "tr"),
    "Ekonomim": ("https://www.ekonomim.com/rss", "tr"),
    
    # === TÜRK TEKNOLOJİ ===
    "Shiftdelete": ("https://shiftdelete.net/feed", "tr"),
    "Webtekno": ("https://www.webtekno.com/rss.xml", "tr"),
    "DonanımHaber": ("https://www.donanimhaber.com/rss/tum/", "tr"),
    "Log": ("https://www.log.com.tr/feed/", "tr"),
}


def kategori_bul(metin):
    metin_lower = metin.lower()
    puanlar = {}
    for kat, kelimeler in KATEGORILER.items():
        puan = sum(1 for k in kelimeler if k in metin_lower)
        puanlar[kat] = puan
    if max(puanlar.values()) > 0:
        return max(puanlar, key=puanlar.get)
    return "genel"


def onem_hesapla(metin):
    metin_lower = metin.lower()
    onem = 4
    for kelime in YUKSEK_ONEM:
        if kelime in metin_lower:
            onem += 2
    return min(onem, 10)


def haberleri_tara():
    """Tüm kaynaklardan haberleri çek"""
    global haberler_db, son_tarama
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Tarama başlıyor...")
    
    tum_haberler = []
    
    for kaynak, (url, dil) in RSS_KAYNAKLAR.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                baslik = entry.get("title", "")
                ozet = entry.get("summary", entry.get("description", ""))
                if ozet:
                    ozet = ozet.replace("<p>", "").replace("</p>", "").replace("<br>", " ")[:400]
                link = entry.get("link", "")
                
                tarih = datetime.now()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        tarih = datetime(*entry.published_parsed[:6])
                    except:
                        pass
                
                metin = f"{baslik} {ozet}"
                kategori = kategori_bul(metin)
                onem = onem_hesapla(metin)
                
                # Anahtar kelimeler
                kelimeler = []
                for kat, kels in KATEGORILER.items():
                    for k in kels:
                        if k in metin.lower() and k not in kelimeler:
                            kelimeler.append(k)
                            if len(kelimeler) >= 4:
                                break
                
                haber = {
                    "baslik": baslik,
                    "ozet": ozet or "",
                    "kaynak": kaynak,
                    "url": link,
                    "tarih": tarih.isoformat(),
                    "kategori": kategori,
                    "onem_puani": onem,
                    "anahtar_kelimeler": kelimeler[:4],
                    "dil": dil,
                    "hash": hashlib.md5(f"{baslik}{link}".encode()).hexdigest()[:10]
                }
                tum_haberler.append(haber)
        except Exception as e:
            print(f"[HATA] {kaynak}: {str(e)[:50]}")
        time.sleep(0.1)
    
    # Duplicate temizle
    goruldu = set()
    benzersiz = []
    for h in tum_haberler:
        if h["hash"] not in goruldu:
            goruldu.add(h["hash"])
            benzersiz.append(h)
    
    # Filtrele ve sırala
    benzersiz = [h for h in benzersiz if h["onem_puani"] >= 3]
    benzersiz.sort(key=lambda x: (x["onem_puani"], x["tarih"]), reverse=True)
    benzersiz = benzersiz[:400]
    
    # İstatistikler
    tr_count = sum(1 for h in benzersiz if h["dil"] == "tr")
    en_count = sum(1 for h in benzersiz if h["dil"] == "en")
    
    istatistikler = {"toplam": len(benzersiz), "turkce": tr_count, "ingilizce": en_count}
    for h in benzersiz:
        kat = h["kategori"]
        istatistikler[kat] = istatistikler.get(kat, 0) + 1
    
    haberler_db = {
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "istatistikler": istatistikler,
        "haberler": benzersiz
    }
    
    son_tarama = datetime.now()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(benzersiz)} haber yüklendi")
    
    return benzersiz


def arkaplan_tarayici():
    """Arka planda sürekli tarama"""
    while True:
        try:
            haberleri_tara()
        except Exception as e:
            print(f"Tarama hatası: {e}")
        time.sleep(TARAMA_ARALIGI * 60)


# ==========================================
# HTML ŞABLONU
# ==========================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Haber İzleme Sistemi | HIS</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#0f0f1a 0%,#1a1a2e 50%,#16213e 100%);min-height:100vh;color:#e4e4e4}
        .container{max-width:1400px;margin:0 auto;padding:20px}
        
        /* Header */
        header{display:flex;justify-content:space-between;align-items:center;padding:20px 0;border-bottom:1px solid #333;margin-bottom:30px;flex-wrap:wrap;gap:15px}
        .logo h1{font-size:2rem;background:linear-gradient(90deg,#00d2ff,#3a7bd5);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
        .logo p{color:#888;font-size:.9rem;margin-top:5px}
        .header-right{display:flex;align-items:center;gap:15px;flex-wrap:wrap}
        .auto-badge{background:rgba(0,255,100,.1);border:1px solid rgba(0,255,100,.3);color:#0f8;padding:6px 12px;border-radius:20px;font-size:.8rem;animation:pulse 2s infinite}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
        .user-badge{background:rgba(0,210,255,.1);border:1px solid rgba(0,210,255,.3);padding:8px 15px;border-radius:20px;color:#00d2ff;font-size:.85rem}
        .logout-btn{padding:10px 20px;border:1px solid rgba(255,68,68,.3);border-radius:8px;background:rgba(255,68,68,.1);color:#ff6666;cursor:pointer;text-decoration:none;font-size:.9rem;transition:all .3s}
        .logout-btn:hover{background:rgba(255,68,68,.2)}
        
        /* Stats */
        .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:25px}
        .stat-card{background:rgba(255,255,255,.05);border-radius:12px;padding:15px 10px;text-align:center;border:1px solid rgba(255,255,255,.1);cursor:pointer;transition:all .3s}
        .stat-card:hover,.stat-card.active{transform:translateY(-3px);border-color:#3a7bd5;background:rgba(58,123,213,.15)}
        .stat-number{font-size:1.6rem;font-weight:bold;color:#00d2ff}
        .stat-label{color:#888;font-size:.7rem;margin-top:5px;text-transform:uppercase}
        
        /* Filters */
        .controls{margin-bottom:20px}
        .search-box{margin-bottom:15px}
        .search-input{width:100%;padding:14px 20px;border:1px solid rgba(255,255,255,.1);border-radius:25px;background:rgba(255,255,255,.05);color:#fff;font-size:.95rem}
        .search-input:focus{outline:none;border-color:#3a7bd5}
        .filters{display:flex;gap:8px;flex-wrap:wrap}
        .filter-btn{padding:8px 14px;border:1px solid rgba(255,255,255,.1);border-radius:20px;cursor:pointer;font-size:.8rem;background:rgba(255,255,255,.05);color:#e4e4e4;transition:all .3s}
        .filter-btn:hover,.filter-btn.active{background:#3a7bd5;border-color:#3a7bd5;color:#fff}
        .lang-filters{margin-top:10px;display:flex;gap:8px}
        .lang-btn{padding:6px 12px;border:1px solid rgba(255,255,255,.1);border-radius:15px;cursor:pointer;font-size:.75rem;background:rgba(255,255,255,.05);color:#aaa;transition:all .3s}
        .lang-btn:hover,.lang-btn.active{background:rgba(0,210,255,.2);border-color:#00d2ff;color:#00d2ff}
        
        /* News */
        .news-grid{display:grid;gap:12px}
        .news-card{background:rgba(255,255,255,.05);border-radius:12px;padding:18px;border-left:4px solid #3a7bd5;transition:all .3s}
        .news-card:hover{background:rgba(255,255,255,.08);transform:translateX(5px)}
        .news-card.high{border-left-color:#ff4444}
        .news-card.medium{border-left-color:#ffaa00}
        .news-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;gap:12px}
        .news-title{font-size:1rem;font-weight:600;color:#fff;flex:1;line-height:1.4}
        .news-title a{color:inherit;text-decoration:none}
        .news-title a:hover{color:#00d2ff}
        .badge{padding:4px 10px;border-radius:12px;font-size:.65rem;font-weight:bold;white-space:nowrap}
        .badge.high{background:rgba(255,68,68,.2);color:#ff4444}
        .badge.medium{background:rgba(255,170,0,.2);color:#ffaa00}
        .badge.low{background:rgba(0,210,255,.2);color:#00d2ff}
        .badge.lang{background:rgba(255,255,255,.1);color:#aaa;margin-left:5px}
        .news-meta{display:flex;gap:12px;font-size:.75rem;color:#888;margin-bottom:8px;flex-wrap:wrap}
        .news-summary{color:#bbb;line-height:1.5;margin-bottom:10px;font-size:.85rem}
        .tags{display:flex;gap:5px;flex-wrap:wrap}
        .tag{background:rgba(58,123,213,.2);color:#3a7bd5;padding:3px 8px;border-radius:10px;font-size:.7rem}
        .tag.cat{background:rgba(0,210,255,.2);color:#00d2ff}
        
        /* Footer */
        .footer{text-align:center;padding:20px;color:#666;font-size:.8rem;margin-top:30px;border-top:1px solid #333}
        .footer .update{color:#00d2ff}
        
        /* Loading */
        .loading{text-align:center;padding:60px;color:#888}
        .spinner{width:40px;height:40px;border:3px solid rgba(255,255,255,.1);border-top-color:#3a7bd5;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
        @keyframes spin{to{transform:rotate(360deg)}}
        
        /* Login */
        .login-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
        .login-box{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:40px;width:100%;max-width:400px;backdrop-filter:blur(10px)}
        .login-box .icon{text-align:center;font-size:4rem;margin-bottom:20px}
        .login-box h1{text-align:center;font-size:1.5rem;margin-bottom:10px;color:#fff}
        .login-box .subtitle{text-align:center;color:#888;margin-bottom:30px;font-size:.9rem}
        .form-group{margin-bottom:20px}
        .form-group label{display:block;color:#aaa;margin-bottom:8px;font-size:.9rem}
        .form-group input{width:100%;padding:14px;border:1px solid rgba(255,255,255,.1);border-radius:10px;background:rgba(255,255,255,.05);color:#fff;font-size:1rem}
        .form-group input:focus{outline:none;border-color:#3a7bd5}
        .login-btn{width:100%;padding:14px;border:none;border-radius:10px;background:linear-gradient(135deg,#00d2ff,#3a7bd5);color:#fff;font-size:1rem;font-weight:600;cursor:pointer;transition:all .3s}
        .login-btn:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(58,123,213,.4)}
        .error{background:rgba(255,68,68,.1);border:1px solid rgba(255,68,68,.3);color:#ff4444;padding:12px;border-radius:8px;margin-bottom:20px;text-align:center}
        
        /* Responsive */
        @media(max-width:768px){
            .logo h1{font-size:1.5rem}
            .stats-grid{grid-template-columns:repeat(3,1fr)}
            .stat-number{font-size:1.3rem}
            .news-header{flex-direction:column;gap:8px}
            .header-right{width:100%;justify-content:center}
        }
        @media(max-width:480px){
            .stats-grid{grid-template-columns:repeat(2,1fr)}
            .container{padding:15px}
        }
    </style>
</head>
<body>
{% if not logged_in %}
<div class="login-page">
    <div class="login-box">
        <div class="icon">📊</div>
        <h1>Haber İzleme Sistemi</h1>
        <p class="subtitle">his.utftoplulugu.com</p>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Kullanıcı Adı</label>
                <input type="text" name="username" required placeholder="Kullanıcı adınız">
            </div>
            <div class="form-group">
                <label>Şifre</label>
                <input type="password" name="password" required placeholder="Şifreniz">
            </div>
            <button type="submit" class="login-btn">Giriş Yap</button>
        </form>
    </div>
</div>
{% else %}
<div class="container">
    <header>
        <div class="logo">
            <h1>📊 Haber İzleme Sistemi</h1>
            <p>Ekonomi • Finans • Borsa • Ticaret • Tarım • AI</p>
        </div>
        <div class="header-right">
            <span class="auto-badge">🟢 7/24 OTOMATİK</span>
            <span class="user-badge">👤 {{ username }}</span>
            <a href="/logout" class="logout-btn">Çıkış</a>
        </div>
    </header>
    
    <div class="stats-grid" id="stats">
        <div class="loading"><div class="spinner"></div>Yükleniyor...</div>
    </div>
    
    <div class="controls">
        <div class="search-box">
            <input type="text" class="search-input" id="search" placeholder="🔍 Haberlerde ara...">
        </div>
        <div class="filters" id="filters">
            <button class="filter-btn active" data-cat="all">Tümü</button>
            <button class="filter-btn" data-cat="ekonomi">📈 Ekonomi</button>
            <button class="filter-btn" data-cat="finans">💰 Finans</button>
            <button class="filter-btn" data-cat="borsa">📊 Borsa</button>
            <button class="filter-btn" data-cat="lojistik">🚚 Lojistik</button>
            <button class="filter-btn" data-cat="ticaret">🤝 Ticaret</button>
            <button class="filter-btn" data-cat="tarim">🌾 Tarım</button>
            <button class="filter-btn" data-cat="surdurulebilirlik">🌱 Sürdürülebilirlik</button>
            <button class="filter-btn" data-cat="yapay_zeka">🤖 Yapay Zeka</button>
            <button class="filter-btn" data-cat="politika">🏛️ Politika</button>
        </div>
        <div class="lang-filters">
            <button class="lang-btn active" data-lang="all">🌍 Tümü</button>
            <button class="lang-btn" data-lang="tr">🇹🇷 Türkçe</button>
            <button class="lang-btn" data-lang="en">🇬🇧 İngilizce</button>
        </div>
    </div>
    
    <div class="news-grid" id="news">
        <div class="loading"><div class="spinner"></div>Haberler yükleniyor...</div>
    </div>
    
    <div class="footer">
        Son güncelleme: <span class="update" id="update">-</span> | Otomatik yenileme: Her {{ interval }} dakika | 
        <strong>his.utftoplulugu.com</strong>
    </div>
</div>

<script>
let data = {haberler: [], istatistikler: {}};
let filter = 'all';
let langFilter = 'all';
let search = '';

const catLabels = {
    ekonomi: '📈 EKONOMİ', finans: '💰 FİNANS', borsa: '📊 BORSA',
    lojistik: '🚚 LOJİSTİK', ticaret: '🤝 TİCARET', tarim: '🌾 TARIM',
    surdurulebilirlik: '🌱 SÜRDÜRÜLEBİLİRLİK', yapay_zeka: '🤖 YAPAY ZEKA',
    politika: '🏛️ POLİTİKA', genel: '📰 GENEL'
};

const catEmoji = {
    toplam: '📰', turkce: '🇹🇷', ingilizce: '🇬🇧',
    ekonomi: '📈', finans: '💰', borsa: '📊', ticaret: '🤝',
    lojistik: '🚚', tarim: '🌾', surdurulebilirlik: '🌱',
    yapay_zeka: '🤖', politika: '🏛️', genel: '📄'
};

async function loadData() {
    try {
        const r = await fetch('/api/haberler');
        if (!r.ok) throw new Error('API error');
        data = await r.json();
        renderStats();
        renderNews();
        document.getElementById('update').textContent = data.son_guncelleme || '-';
    } catch (e) {
        console.error(e);
        document.getElementById('news').innerHTML = '<div class="loading">Veriler yüklenirken hata oluştu</div>';
    }
}

function renderStats() {
    const order = ['toplam', 'turkce', 'ingilizce', 'ekonomi', 'finans', 'borsa', 'ticaret', 'lojistik', 'tarim', 'surdurulebilirlik', 'yapay_zeka', 'politika'];
    let html = '';
    for (const k of order) {
        if (data.istatistikler[k] && data.istatistikler[k] > 0) {
            const cat = k === 'toplam' ? 'all' : k;
            html += `<div class="stat-card${filter === cat ? ' active' : ''}" data-cat="${cat}">
                <div class="stat-number">${data.istatistikler[k]}</div>
                <div class="stat-label">${catEmoji[k] || ''} ${k}</div>
            </div>`;
        }
    }
    document.getElementById('stats').innerHTML = html || '<div class="loading">İstatistik yok</div>';
    document.querySelectorAll('.stat-card').forEach(c => {
        c.onclick = () => {
            if (['turkce', 'ingilizce'].includes(c.dataset.cat)) {
                setLangFilter(c.dataset.cat === 'turkce' ? 'tr' : 'en');
            } else {
                setFilter(c.dataset.cat);
            }
        };
    });
}

function renderNews() {
    let news = data.haberler || [];
    
    if (filter !== 'all') news = news.filter(n => n.kategori === filter);
    if (langFilter !== 'all') news = news.filter(n => n.dil === langFilter);
    if (search) {
        const q = search.toLowerCase();
        news = news.filter(n => n.baslik.toLowerCase().includes(q) || (n.ozet && n.ozet.toLowerCase().includes(q)));
    }
    
    if (!news.length) {
        document.getElementById('news').innerHTML = '<div class="loading">🔍 Haber bulunamadı</div>';
        return;
    }
    
    let html = '';
    for (const n of news) {
        const imp = n.onem_puani >= 8 ? 'high' : n.onem_puani >= 6 ? 'medium' : 'low';
        const impText = n.onem_puani >= 8 ? 'ÇOK ÖNEMLİ' : n.onem_puani >= 6 ? 'ÖNEMLİ' : 'NORMAL';
        const langBadge = n.dil === 'tr' ? '🇹🇷' : '🇬🇧';
        const tags = (n.anahtar_kelimeler || []).slice(0, 3).map(t => `<span class="tag">${t}</span>`).join('');
        const date = new Date(n.tarih).toLocaleString('tr-TR');
        
        html += `<div class="news-card ${imp}">
            <div class="news-header">
                <h3 class="news-title"><a href="${n.url}" target="_blank">${n.baslik}</a></h3>
                <div>
                    <span class="badge ${imp}">${impText}</span>
                    <span class="badge lang">${langBadge}</span>
                </div>
            </div>
            <div class="news-meta">
                <span>📰 ${n.kaynak}</span>
                <span>📅 ${date}</span>
                <span>⭐ ${n.onem_puani}/10</span>
            </div>
            <p class="news-summary">${(n.ozet || '').substring(0, 180)}${n.ozet && n.ozet.length > 180 ? '...' : ''}</p>
            <div class="tags">
                <span class="tag cat">${catLabels[n.kategori] || n.kategori}</span>
                ${tags}
            </div>
        </div>`;
    }
    document.getElementById('news').innerHTML = html;
}

function setFilter(f) {
    filter = f;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b.dataset.cat === f));
    document.querySelectorAll('.stat-card').forEach(c => c.classList.toggle('active', c.dataset.cat === f));
    renderNews();
}

function setLangFilter(l) {
    langFilter = l;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === l));
    renderNews();
}

document.getElementById('search').oninput = e => { search = e.target.value.toLowerCase(); renderNews(); };
document.querySelectorAll('.filter-btn').forEach(b => b.onclick = () => setFilter(b.dataset.cat));
document.querySelectorAll('.lang-btn').forEach(b => b.onclick = () => setLangFilter(b.dataset.lang));

// İlk yükleme ve otomatik yenileme
loadData();
setInterval(loadData, 60000);
</script>
{% endif %}
</body>
</html>
'''


# ==========================================
# ROTALAR
# ==========================================
@app.route('/')
def anasayfa():
    """Ana sayfa - landing page"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return redirect('/panel')


@app.route('/panel', methods=['GET', 'POST'])
def panel():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            session['username'] = username
            return redirect('/panel')
        error = "Kullanıcı adı veya şifre hatalı!"
    
    return render_template_string(
        HTML_TEMPLATE,
        logged_in=session.get('logged_in'),
        username=session.get('username', 'Admin'),
        error=error,
        interval=TARAMA_ARALIGI
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/panel')


@app.route('/api/haberler')
def api_haberler():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    # İlk istek veya veriler eskiyse tara
    global son_tarama
    if son_tarama is None or (datetime.now() - son_tarama).seconds > TARAMA_ARALIGI * 60:
        haberleri_tara()
    
    return jsonify(haberler_db)


@app.route('/api/tara')
def api_tara():
    """Manuel tarama tetikle"""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    haberleri_tara()
    return jsonify({"status": "ok", "haber_sayisi": len(haberler_db.get("haberler", []))})


# ==========================================
# BAŞLATMA
# ==========================================
# İlk taramayı yap
print("🚀 Haber İzleme Sistemi başlatılıyor...")
try:
    haberleri_tara()
except Exception as e:
    print(f"İlk tarama hatası: {e}")

# Arka plan tarayıcıyı başlat
tarama_thread = threading.Thread(target=arkaplan_tarayici, daemon=True)
tarama_thread.start()
print(f"✅ Otomatik tarama aktif: Her {TARAMA_ARALIGI} dakikada bir")


# Passenger için
if __name__ == '__main__':
    app.run(debug=False)
