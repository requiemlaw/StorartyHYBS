# -*- coding: utf-8 -*-
"""
RequiemHBYS - 2. asama demo veri guclendirici.

Bu script:
  1) Var olan hastalarin kayit_tarihi SAATLERINI mesai ici (08:00-18:30) araligina
     cekerek duzeltir (tarihi degistirmez, sadece gerceksiz gece saatlerini onarir).
  2) Cok daha fazla hasta ekler (haftaici/haftasonu yogunluguna gore agirlikli,
     ve kronolojik sirayla eklenir ki "Son Kaydedilen Hastalar" listesi mantikli gorunsun).
  3) Cok daha fazla randevu ekler; BUGUNE ozel minimum bir randevu sayisi GARANTI eder
     (dashboard'da "Bugunku Randevu" cok dusuk kalmasin diye).
  4) Ameliyat sayisini ciddi artirir, bugune de birkac ameliyat garantiler.
  5) "Son 7 Gun Trendi" grafiginin duz degil, hafta ici/hafta sonu iniş-cikisli ve
     dogal gorunmesini saglar.

Kullanim: database.py ile ayni klasore koy, calistir:
    python seed_data_v2.py
Onceki seed_data.py'yi calistirmis olman gerekmez, bagimsiz calisir;
ama zaten calistirdiysan da sorun yok, uzerine ekler / duzeltir.
"""

import math
import random
from datetime import datetime, timedelta

from database import Database

DB_PATH = "web_hastane.db"

WORK_START_HOUR = 8
WORK_END_HOUR = 18

# Pazartesi=0 ... Pazar=6 (python weekday())
HAFTA_YOGUNLUK = {0: 1.00, 1: 1.05, 2: 1.10, 3: 1.00, 4: 0.95, 5: 0.55, 6: 0.20}

ERKEK_ISIMLER = [
    "Ahmet", "Mehmet", "Mustafa", "Ali", "Hüseyin", "Hasan", "İbrahim", "Osman",
    "Yusuf", "Murat", "Emre", "Burak", "Kemal", "Cem", "Volkan", "Serkan",
    "Tolga", "Fatih", "Kadir", "Selim", "Onur", "Barış", "Erhan", "Necmi",
    "Turgay", "Recep", "Halil", "Cengiz", "Gökhan", "Levent", "Erdem", "Sinan",
    "Metin", "Doğan", "Alper", "Ergün", "Şükrü", "Bülent", "Nihat", "Ozan",
]

KADIN_ISIMLER = [
    "Ayşe", "Fatma", "Emine", "Hatice", "Zeynep", "Elif", "Meryem", "Sultan",
    "Nur", "Esra", "Songül", "Gül", "Derya", "Sibel", "Pınar", "Aylin",
    "Yasemin", "Nazlı", "Merve", "Buse", "Selin", "Ebru", "Tuba", "Canan",
    "Hülya", "Nesrin", "Filiz", "Gonca", "Ceren", "Deniz", "İrem", "Betül",
    "Aysel", "Nalan", "Şule", "Aslı", "Damla", "Gizem", "Özlem", "Rukiye",
]

SOYISIMLER = [
    "Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk",
    "Aydın", "Özdemir", "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara",
    "Koç", "Kurt", "Özkan", "Şimşek", "Erdoğan", "Güneş", "Aksoy", "Polat",
    "Bulut", "Akman", "Uçar", "Er", "Duman", "Tekin", "Aktaş", "Türkmen",
    "Karaca", "Çakır", "Avcı", "Sarı", "Bozkurt", "Aygün", "Ekşi", "Yalçın",
    "Güler", "Korkmaz", "Şen", "Keskin", "Bayrak", "Coşkun", "Acar", "Tunç",
]

SEHIRLER_ADRES = [
    "Kepez, Antalya", "Karşıyaka, İzmir", "Kadıköy, İstanbul", "Çankaya, Ankara",
    "Nilüfer, Bursa", "Selçuklu, Konya", "Yenişehir, Mersin", "Melikgazi, Kayseri",
    "Odunpazarı, Eskişehir", "Merkezefendi, Denizli", "Merkez, Çanakkale",
    "Atakum, Samsun", "Osmangazi, Bursa", "Muratpaşa, Antalya", "Etimesgut, Ankara",
    "Bornova, İzmir", "Maltepe, İstanbul", "Tepebaşı, Eskişehir", "İnegöl, Bursa",
]

KAN_GRUPLARI = ["A Rh+", "A Rh-", "B Rh+", "B Rh-", "0 Rh+", "0 Rh-", "AB Rh+", "AB Rh-"]

GECMIS_HAVUZU = [
    "Özellik yok", "Hipertansiyon", "Tip 2 Diyabet", "Astım", "Hipertansiyon, Tip 2 Diyabet",
    "Koroner Arter Hastalığı", "Guatr", "Migren", "Alerjik Rinit", "Geçirilmiş apandisit ameliyatı",
    "Kronik Böbrek Yetmezliği takibi", "Osteoporoz", "Reflü (GÖRH)", "Özellik yok",
    "Özellik yok", "Sigara kullanımı (20 paket/yıl)", "Ailede kalp hastalığı öyküsü",
]

POLIKLINIK_VERI = {
    "Kardiyoloji": {
        "sikayet": ["Göğüs ağrısı", "Çarpıntı", "Nefes darlığı", "Efor sonrası yorgunluk", "Baş dönmesi"],
        "tani": ["Hipertansiyon", "Aritmi", "Koroner arter hastalığı şüphesi", "Stabil anjina", "Bulgu yok - rutin kontrol"],
        "ilac": [("Coraspin 100mg", "1x1", "Sabah aç karnına"), ("Concor 5mg", "1x1", "Sabah"), ("Lipitor 20mg", "1x1", "Akşam")],
    },
    "Dahiliye": {
        "sikayet": ["Halsizlik", "Karın ağrısı", "Bulantı", "Kilo kaybı", "Ateş"],
        "tani": ["Gastrit", "Demir eksikliği anemisi", "Tip 2 Diyabet", "Üst solunum yolu enfeksiyonu", "Bulgu yok - rutin kontrol"],
        "ilac": [("Nexium 40mg", "1x1", "Sabah aç karnına"), ("Glucophage 850mg", "2x1", "Yemekle"), ("Parasetamol 500mg", "3x1", "Ağrı olduğunda")],
    },
    "Ortopedi": {
        "sikayet": ["Diz ağrısı", "Bel ağrısı", "Omuz ağrısı", "Düşme sonrası ağrı", "Eklem sertliği"],
        "tani": ["Lomber disk hernisi", "Gonartroz", "Rotator manşet sıkışması", "Kırık şüphesi", "Kas gerginliği"],
        "ilac": [("Arveles 25mg", "2x1", "Yemekten sonra"), ("Majezik 100mg", "2x1", "Yemekten sonra"), ("Voltaren jel", "3x1", "Bölgeye sürülerek")],
    },
    "Genel Cerrahi": {
        "sikayet": ["Karın ağrısı", "Şişkinlik", "Kasıkta şişlik", "Ameliyat sonrası kontrol", "Yara yeri ağrısı"],
        "tani": ["Kronik kolesistit", "Kasık fıtığı", "Apandisit", "Hemoroid", "Ameliyat sonrası kontrol - sorun yok"],
        "ilac": [("Augmentin 1000mg", "2x1", "Yemekten sonra 7 gün"), ("Parol 500mg", "3x1", "Ağrı olduğunda"), ("Nexium 40mg", "1x1", "Sabah")],
    },
    "Göz Hastalıkları": {
        "sikayet": ["Bulanık görme", "Göz kuruluğu", "Göz kızarıklığı", "Baş ağrısı ile birlikte görme bozukluğu", "Rutin göz muayenesi"],
        "tani": ["Miyopi", "Kuru göz sendromu", "Konjonktivit", "Katarakt başlangıcı", "Bulgu yok - rutin kontrol"],
        "ilac": [("Optive göz damlası", "4x1", "Her göze"), ("Tobrex damla", "3x1", "7 gün"), ("Numaralı gözlük reçetesi", "-", "Kontrol 6 ay sonra")],
    },
    "Kulak Burun Boğaz": {
        "sikayet": ["Boğaz ağrısı", "Kulak ağrısı", "Burun tıkanıklığı", "İşitme azlığı", "Baş dönmesi"],
        "tani": ["Akut farenjit", "Orta kulak iltihabı", "Alerjik rinit", "Sinüzit", "Vertigo"],
        "ilac": [("Augmentin 1000mg", "2x1", "Yemekten sonra 7 gün"), ("Otrivin sprey", "3x1", "Her burun deliğine"), ("Cinnarizine 25mg", "2x1", "Yemekle")],
    },
    "Nöroloji": {
        "sikayet": ["Baş ağrısı", "Uyuşma", "Denge kaybı", "Unutkanlık", "Migren atağı"],
        "tani": ["Migren", "Gerilim tipi baş ağrısı", "Periferik nöropati şüphesi", "Bulgu yok - rutin kontrol", "Vertigo"],
        "ilac": [("Depakin 500mg", "2x1", "Sabah akşam"), ("Majezik 100mg", "2x1", "Ağrı döneminde"), ("B12 vitamini", "1x1", "Sabah")],
    },
    "Üroloji": {
        "sikayet": ["İdrar yaparken yanma", "Sık idrara çıkma", "Bel-kasık ağrısı", "İdrarda kanama", "Rutin kontrol"],
        "tani": ["İdrar yolu enfeksiyonu", "Böbrek taşı şüphesi", "Prostat hiperplazisi", "Bulgu yok - rutin kontrol", "Sistit"],
        "ilac": [("Cipro 500mg", "2x1", "Yemekten sonra 5 gün"), ("Ürolizin", "3x1", "Yemekten sonra"), ("Tamsulosin 0.4mg", "1x1", "Akşam")],
    },
}

AMELIYAT_HAVUZU = {
    "Genel Cerrahi": ["Laparoskopik Kolesistektomi", "Apendektomi", "Kasık Fıtığı Onarımı", "Hemoroidektomi", "Tiroidektomi"],
    "Ortopedi": ["Diz Artroskopisi", "Kalça Protezi", "Omuz Artroskopisi", "Kırık Tespiti (Osteosentez)", "El Cerrahisi"],
    "Kardiyoloji": ["Koroner Anjiyografi", "Kalp Pili Takılması", "Balon Anjiyoplasti"],
    "Kulak Burun Boğaz": ["Tonsillektomi", "Septoplasti", "Adenoidektomi"],
    "Üroloji": ["Prostat Rezeksiyonu (TUR-P)", "Böbrek Taşı Kırma (ESWL)", "Sistoskopi"],
    "Göz Hastalıkları": ["Katarakt Ameliyatı (Fakoemülsifikasyon)", "Şaşılık Ameliyatı"],
    "Nöroloji": ["Lomber Disk Cerrahisi", "Karpal Tünel Cerrahisi"],
    "Dahiliye": ["Endoskopi (Girişimsel)", "Kolonoskopik Polipektomi"],
}

SALONLAR = ["Ameliyathane 1", "Ameliyathane 2", "Ameliyathane 3", "Günübirlik Cerrahi Salonu"]
SAATLER = ["08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00",
           "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00"]

DURUM_LOG_ISLEM = [
    ("Hasta Kayıt", "Yeni hasta kaydı oluşturuldu"),
    ("Randevu", "Randevu oluşturuldu"),
    ("Randevu", "Randevu durumu güncellendi"),
    ("Muayene", "Muayene kaydı girildi"),
    ("Tetkik İstem", "Tetkik istemi oluşturuldu"),
    ("Ameliyat", "Ameliyat planlandı"),
]


# ------------------------------------------------------------------
# YARDIMCI FONKSIYONLAR
# ------------------------------------------------------------------

def tc_uret():
    while True:
        digits = [random.randint(1, 9)] + [random.randint(0, 9) for _ in range(8)]
        odd_sum = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
        even_sum = digits[1] + digits[3] + digits[5] + digits[7]
        d10 = ((odd_sum * 7) - even_sum) % 10
        d11 = (sum(digits) + d10) % 10
        return "".join(str(d) for d in (digits + [d10, d11]))


def rastgele_dogum_tarihi():
    yas = random.randint(2, 88)
    gun = random.randint(1, 28)
    ay = random.randint(1, 12)
    yil = datetime.now().year - yas
    return f"{gun:02d}.{ay:02d}.{yil}"


def rastgele_telefon():
    return f"05{random.randint(30,59)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}"


def mesai_saati():
    """Mesai ici bir (saat, dakika) dondurur; kucuk bir ihtimalle mesai disina tasar (nobetci/acil)."""
    if random.random() < 0.93:
        saat = random.randint(WORK_START_HOUR, WORK_END_HOUR - 1)
        dakika = random.randint(0, 59)
    else:
        saat = random.choice([7, 18, 19, 20])
        dakika = random.randint(0, 59)
    return saat, dakika


def gun_agirligi(offset, yakinlik_carpani=8.0):
    """Belirli bir gun (bugune gore offset) icin dogal bir agirlik uretir:
    hafta sonlari daha az, bugune yakin gunler biraz daha yogun."""
    d = datetime.now() + timedelta(days=offset)
    hafta_carpani = HAFTA_YOGUNLUK[d.weekday()]
    yakinlik = math.exp(-abs(offset) / yakinlik_carpani)
    rastgele_gurultu = random.uniform(0.7, 1.3)
    return hafta_carpani * (0.3 + yakinlik) * rastgele_gurultu


def agirlikli_offset_sec(min_off, max_off, yakinlik_carpani=8.0):
    offsets = list(range(min_off, max_off + 1))
    agirliklar = [gun_agirligi(o, yakinlik_carpani) for o in offsets]
    return random.choices(offsets, weights=agirliklar, k=1)[0]


# ------------------------------------------------------------------
# ANA ISLEMLER
# ------------------------------------------------------------------

def mevcut_hasta_saatlerini_duzelt(db):
    """Gece yarisi/sabaha karsi gibi gerceksiz kayit saatlerini mesai icine ceker."""
    hastalar = db.sorgula("SELECT id, kayit_tarihi FROM hastalar")
    duzeltilen = 0
    for h in hastalar:
        kt = h["kayit_tarihi"]
        if not kt or " " not in kt:
            continue
        tarih_kismi, saat_kismi = kt.split(" ", 1)
        try:
            saat = int(saat_kismi.split(":")[0])
        except (ValueError, IndexError):
            continue
        if saat < 7 or saat > 20:
            yeni_saat, yeni_dakika = mesai_saati()
            yeni_kt = f"{tarih_kismi} {yeni_saat:02d}:{yeni_dakika:02d}"
            db.calistir("UPDATE hastalar SET kayit_tarihi=? WHERE id=?", (yeni_kt, h["id"]))
            duzeltilen += 1
    print(f"Duzeltilen (gece saatinden mesai icine cekilen) hasta kaydi: {duzeltilen}")


def yeni_hastalar_ekle(db, adet):
    """Kronolojik sirada (eskiden yeniye) hasta ekler; boylece en son eklenen (en yuksek id)
    en guncel kayit_tarihine sahip olur -> 'Son Kaydedilen Hastalar' listesi mantikli gorunur."""
    aday_tarihler = []
    for _ in range(adet):
        offset = agirlikli_offset_sec(-30, 0, yakinlik_carpani=10.0)
        saat, dakika = mesai_saati()
        dt = (datetime.now() + timedelta(days=offset)).replace(hour=saat, minute=dakika, second=0, microsecond=0)
        aday_tarihler.append(dt)

    # bugune ozel birkac taze kayit garantile (en sonda eklenecekler icin)
    bugun_ekstra = random.randint(3, 7)
    for _ in range(bugun_ekstra):
        saat, dakika = mesai_saati()
        dt = datetime.now().replace(hour=saat, minute=dakika, second=0, microsecond=0)
        aday_tarihler.append(dt)

    aday_tarihler.sort()  # en eski -> en yeni

    eklenen_idler = []
    for kayit_dt in aday_tarihler:
        cinsiyet = random.choice(["Erkek", "Kadin"])
        ad = random.choice(ERKEK_ISIMLER if cinsiyet == "Erkek" else KADIN_ISIMLER)
        soyad = random.choice(SOYISIMLER)
        ad_soyad = f"{ad} {soyad}".upper()
        acil_ad = f"{random.choice(ERKEK_ISIMLER + KADIN_ISIMLER)} {soyad}".title()

        v = {
            "ad_soyad": ad_soyad,
            "tc": tc_uret(),
            "dogum_tarihi": rastgele_dogum_tarihi(),
            "cinsiyet": "Erkek" if cinsiyet == "Erkek" else "Kadın",
            "kan_grubu": random.choice(KAN_GRUPLARI),
            "telefon": rastgele_telefon(),
            "adres": random.choice(SEHIRLER_ADRES),
            "acil_ad": acil_ad,
            "acil_tel": rastgele_telefon(),
            "gecmis": random.choice(GECMIS_HAVUZU),
            "kayit_tarihi": kayit_dt.strftime("%d.%m.%Y %H:%M"),
        }
        hid = db.calistir(
            """INSERT INTO hastalar (ad_soyad, tc, dogum_tarihi, cinsiyet, kan_grubu, telefon,
               adres, acil_ad, acil_tel, gecmis, kayit_tarihi) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (v["ad_soyad"], v["tc"], v["dogum_tarihi"], v["cinsiyet"], v["kan_grubu"], v["telefon"],
             v["adres"], v["acil_ad"], v["acil_tel"], v["gecmis"], v["kayit_tarihi"]),
        )
        eklenen_idler.append(hid)
        db.calistir(
            """INSERT INTO loglar (tarih, kullanici_adi, rol, kategori, islem, aciklama, sonuc)
               VALUES (?,?,?,?,?,?,?)""",
            (kayit_dt.strftime("%d.%m.%Y %H:%M:%S"), "sekreter.cengiz", "Sekreter", "Hasta Kayıt",
             "Yeni hasta kaydı oluşturuldu", f"{v['ad_soyad']} sisteme kaydedildi.", "Başarılı"),
        )

    print(f"Eklenen yeni hasta: {len(eklenen_idler)} (icinde bugune tarihli: {bugun_ekstra})")
    return eklenen_idler


def randevu_ve_muayene_ekle(db, tum_hasta_idler, tum_doktorlar, adet, min_bugun_hedef):
    tamamlanan_muayene = 0
    yazilan_recete = 0

    def tek_randevu_ekle(gun_offset):
        nonlocal tamamlanan_muayene, yazilan_recete
        hasta_id = random.choice(tum_hasta_idler)
        doktor = random.choice(tum_doktorlar)
        poliklinik = doktor["poliklinik"] if doktor["poliklinik"] in POLIKLINIK_VERI else "Dahiliye"

        tarih_dt = datetime.now() + timedelta(days=gun_offset)
        tarih_str = tarih_dt.strftime("%Y-%m-%d")
        saat = random.choice(SAATLER)

        if gun_offset < 0:
            durum = random.choices(["Tamamlandı", "İptal Edildi"], weights=[85, 15])[0]
        elif gun_offset == 0:
            durum = random.choices(["Bekliyor", "Tamamlandı"], weights=[55, 45])[0]
        else:
            durum = "Bekliyor"

        rid = db.calistir(
            "INSERT INTO randevular (hasta_id, doktor_id, tarih, saat, durum) VALUES (?,?,?,?,?)",
            (hasta_id, doktor["id"], tarih_str, saat, durum),
        )

        if durum == "Tamamlandı":
            hasta = db.sorgula_tek("SELECT ad_soyad FROM hastalar WHERE id=?", (hasta_id,))
            veri = POLIKLINIK_VERI[poliklinik]
            sikayet = random.choice(veri["sikayet"])
            tani = random.choice(veri["tani"])
            not_ = random.choice([
                "Hastaya bilgi verildi, kontrol önerildi.",
                "Tedavi planı anlatıldı.",
                "Şikayetler gerilemiş, takipte.",
                "Gerekli görülürse tetkik istenecek.",
                "-",
            ])
            mid = db.calistir(
                """INSERT INTO muayeneler (randevu_id, hasta_ad, doktor_ad, sikayet, tani, not_, tarih)
                   VALUES (?,?,?,?,?,?,?)""",
                (rid, hasta["ad_soyad"], doktor["ad_soyad"], sikayet, tani, not_, tarih_dt.strftime("%d.%m.%Y")),
            )
            tamamlanan_muayene += 1
            if random.random() < 0.55:
                secilenler = random.sample(veri["ilac"], k=min(random.randint(1, 2), len(veri["ilac"])))
                for ilac, doz, aciklama in secilenler:
                    db.calistir(
                        "INSERT INTO receteler (muayene_id, ilac, doz, aciklama) VALUES (?,?,?,?)",
                        (mid, ilac, doz, aciklama),
                    )
                    yazilan_recete += 1

    for _ in range(adet):
        gun_offset = agirlikli_offset_sec(-25, 14, yakinlik_carpani=7.0)
        tek_randevu_ekle(gun_offset)

    # bugun icin minimum garanti
    bugun_str = datetime.now().strftime("%Y-%m-%d")
    mevcut_bugun = db.sorgula("SELECT COUNT(*) c FROM randevular WHERE tarih=?", (bugun_str,))[0]["c"]
    eksik = max(0, min_bugun_hedef - mevcut_bugun)
    for _ in range(eksik):
        tek_randevu_ekle(0)

    print(f"Randevu eklendi: {adet + eksik} (bugune ozel tamamlayici: {eksik}), "
          f"tamamlanan muayene: {tamamlanan_muayene}, recete satiri: {yazilan_recete}")


def ameliyat_ekle(db, tum_hasta_idler, tum_doktorlar, adet, min_bugun_hedef):
    cerrahi_dallar = list(AMELIYAT_HAVUZU.keys())

    def tek_ameliyat_ekle(gun_offset):
        dal = random.choice(cerrahi_dallar)
        uygun_doktorlar = [d for d in tum_doktorlar if d["poliklinik"] == dal] or tum_doktorlar
        doktor = random.choice(uygun_doktorlar)
        hasta_id = random.choice(tum_hasta_idler)
        ameliyat_adi = random.choice(AMELIYAT_HAVUZU[dal])
        tarih_dt = datetime.now() + timedelta(days=gun_offset)

        if gun_offset < 0:
            durum = random.choices(["Tamamlandı", "İptal Edildi"], weights=[90, 10])[0]
        elif gun_offset == 0:
            durum = random.choices(["Planlandı", "Tamamlandı"], weights=[60, 40])[0]
        else:
            durum = "Planlandı"

        db.calistir(
            """INSERT INTO ameliyatlar (hasta_id, doktor_id, ameliyat_adi, tarih, saat, salon, durum)
               VALUES (?,?,?,?,?,?,?)""",
            (hasta_id, doktor["id"], ameliyat_adi, tarih_dt.strftime("%Y-%m-%d"),
             random.choice(SAATLER), random.choice(SALONLAR), durum),
        )

    for _ in range(adet):
        gun_offset = agirlikli_offset_sec(-20, 18, yakinlik_carpani=9.0)
        tek_ameliyat_ekle(gun_offset)

    bugun_str = datetime.now().strftime("%Y-%m-%d")
    mevcut_bugun = db.sorgula("SELECT COUNT(*) c FROM ameliyatlar WHERE tarih=?", (bugun_str,))[0]["c"]
    eksik = max(0, min_bugun_hedef - mevcut_bugun)
    for _ in range(eksik):
        tek_ameliyat_ekle(0)

    print(f"Ameliyat eklendi: {adet + eksik} (bugune ozel tamamlayici: {eksik})")


def main():
    db = Database(DB_PATH)
    print("Veritabani acildi:", DB_PATH)

    # 1) Mevcut gerceksiz kayit saatlerini duzelt
    mevcut_hasta_saatlerini_duzelt(db)

    tum_doktorlar = db.sorgula("SELECT * FROM doktorlar")

    # 2) Cok daha fazla hasta ekle
    YENI_HASTA_SAYISI = 140
    yeni_hasta_idler = yeni_hastalar_ekle(db, YENI_HASTA_SAYISI)

    tum_hasta_idler = [r["id"] for r in db.sorgula("SELECT id FROM hastalar")]
    print(f"Toplam hasta: {len(tum_hasta_idler)}")

    # 3) Cok daha fazla randevu + bugune minimum garanti
    HEDEF_BUGUN_RANDEVU = random.randint(20, 28)
    randevu_ve_muayene_ekle(db, tum_hasta_idler, tum_doktorlar, adet=420, min_bugun_hedef=HEDEF_BUGUN_RANDEVU)

    # 4) Cok daha fazla ameliyat + bugune minimum garanti
    HEDEF_BUGUN_AMELIYAT = random.randint(3, 6)
    ameliyat_ekle(db, tum_hasta_idler, tum_doktorlar, adet=55, min_bugun_hedef=HEDEF_BUGUN_AMELIYAT)

    # 5) Cesitlilik icin ek loglar
    for _ in range(60):
        gun_offset = agirlikli_offset_sec(-20, 0, yakinlik_carpani=8.0)
        saat, dakika = mesai_saati()
        log_dt = (datetime.now() + timedelta(days=gun_offset)).replace(hour=saat, minute=dakika)
        kategori, islem = random.choice(DURUM_LOG_ISLEM)
        kullanici = random.choice(["admin", "temel.bulut", "ayse.yilmaz", "sekreter.cengiz", "hemsire.deniz"])
        db.calistir(
            """INSERT INTO loglar (tarih, kullanici_adi, rol, kategori, islem, aciklama, sonuc)
               VALUES (?,?,?,?,?,?,?)""",
            (log_dt.strftime("%d.%m.%Y %H:%M:%S"), kullanici, "Sistem", kategori, islem,
             "Otomatik demo veri islemi.", random.choices(["Başarılı", "Başarılı", "Başarılı", "Hata"], k=1)[0]),
        )

    print("\nTAMAMLANDI. Veritabani daha gercekci hacim ve saatlerle guncellendi.")
    print("Uygulamayi yeniden baslatip Kontrol Paneli'ni kontrol edebilirsin.")


if __name__ == "__main__":
    main()