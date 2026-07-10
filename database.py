import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._tablolari_olustur()
        self._migrasyonlari_calistir()
        self._seed_ilk_veri()

    # ---- Genel yardımcılar ----
    def calistir(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid

    def sorgula(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def sorgula_tek(self, sql, params=()):
        r = self.sorgula(sql, params)
        return r[0] if r else None

    def _kolon_ekle_gerekirse(self, tablo, kolon, tip):
        mevcut = [r["name"] for r in self.sorgula(f"PRAGMA table_info({tablo})")]
        if kolon not in mevcut:
            self.calistir(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tip}")

    def _migrasyonlari_calistir(self):
        self._kolon_ekle_gerekirse("tetkikler", "sonuc", "TEXT")
        self._kolon_ekle_gerekirse("tetkikler", "sonuc_tarihi", "TEXT")

    def _tablolari_olustur(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS hastalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            tc TEXT,
            dogum_tarihi TEXT,
            cinsiyet TEXT,
            kan_grubu TEXT,
            telefon TEXT,
            adres TEXT,
            acil_ad TEXT,
            acil_tel TEXT,
            gecmis TEXT,
            kayit_tarihi TEXT
        );
        CREATE TABLE IF NOT EXISTS doktorlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            uzmanlik TEXT,
            poliklinik TEXT,
            uygunluk TEXT
        );
        CREATE TABLE IF NOT EXISTS personeller (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            rol TEXT,
            birim TEXT,
            telefon TEXT,
            kullanici_adi TEXT UNIQUE,
            sifre TEXT,
            durum TEXT
        );
        CREATE TABLE IF NOT EXISTS poliklinikler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS randevular (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hasta_id INTEGER,
            doktor_id INTEGER,
            tarih TEXT,
            saat TEXT,
            durum TEXT
        );
        CREATE TABLE IF NOT EXISTS muayeneler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            randevu_id INTEGER,
            hasta_ad TEXT,
            doktor_ad TEXT,
            sikayet TEXT,
            tani TEXT,
            not_ TEXT,
            tarih TEXT
        );
        CREATE TABLE IF NOT EXISTS receteler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            muayene_id INTEGER,
            ilac TEXT,
            doz TEXT,
            aciklama TEXT
        );
        CREATE TABLE IF NOT EXISTS servis_yatislari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hasta_id INTEGER,
            servis TEXT,
            oda TEXT,
            yatak TEXT,
            yatis_tarihi TEXT,
            tani TEXT,
            durum TEXT
        );
        CREATE TABLE IF NOT EXISTS ameliyatlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hasta_id INTEGER,
            doktor_id INTEGER,
            ameliyat_adi TEXT,
            tarih TEXT,
            saat TEXT,
            salon TEXT,
            durum TEXT
        );
        CREATE TABLE IF NOT EXISTS tetkikler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hasta_id INTEGER,
            kodu TEXT,
            tetkik_adi TEXT,
            adet INTEGER,
            durum TEXT,
            isteyen_doktor TEXT,
            tarih TEXT
        );
        CREATE TABLE IF NOT EXISTS loglar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            kullanici_adi TEXT,
            rol TEXT,
            kategori TEXT,
            islem TEXT,
            aciklama TEXT,
            sonuc TEXT
        );
        """)
        self.conn.commit()

    def _seed_ilk_veri(self):
        if self.sorgula("SELECT COUNT(*) as c FROM poliklinikler")[0]["c"] == 0:
            for p in ["Kardiyoloji", "Dahiliye", "Ortopedi", "Genel Cerrahi",
                      "Göz Hastalıkları", "Kulak Burun Boğaz", "Nöroloji", "Üroloji"]:
                self.calistir("INSERT INTO poliklinikler (ad) VALUES (?)", (p,))

        if self.sorgula("SELECT COUNT(*) as c FROM doktorlar")[0]["c"] == 0:
            self.calistir("INSERT INTO doktorlar (ad_soyad, uzmanlik, poliklinik, uygunluk) VALUES (?,?,?,?)",
                          ("TEMEL BULUT", "Genel Cerrahi", "Genel Cerrahi", "Müsait"))
            self.calistir("INSERT INTO doktorlar (ad_soyad, uzmanlik, poliklinik, uygunluk) VALUES (?,?,?,?)",
                          ("AYŞE YILMAZ", "Kardiyoloji", "Kardiyoloji", "Müsait"))

        if self.sorgula("SELECT COUNT(*) as c FROM personeller")[0]["c"] == 0:
            self.calistir("""INSERT INTO personeller (ad_soyad, rol, birim, telefon, kullanici_adi, sifre, durum)
                              VALUES (?,?,?,?,?,?,?)""",
                          ("Sistem Yöneticisi", "Yönetici", "Genel Yönetim", "-", "admin",
                           generate_password_hash("1234"), "Aktif"))
            self.calistir("""INSERT INTO personeller (ad_soyad, rol, birim, telefon, kullanici_adi, sifre, durum)
                              VALUES (?,?,?,?,?,?,?)""",
                          ("TEMEL BULUT", "Doktor", "Genel Cerrahi", "-", "temel.bulut",
                           generate_password_hash("1234"), "Aktif"))

        if self.sorgula("SELECT COUNT(*) as c FROM hastalar")[0]["c"] == 0:
            self.calistir("""INSERT INTO hastalar (ad_soyad, tc, dogum_tarihi, cinsiyet, kan_grubu, telefon, adres,
                              acil_ad, acil_tel, gecmis, kayit_tarihi) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                          ("FİKRET AKMAN", "12345678901", "21.05.1945", "Erkek", "A Rh+", "0532 000 00 00",
                           "İstanbul", "Ayşe Akman", "0533 111 11 11", "Hipertansiyon, Tip 2 Diyabet",
                           datetime.now().strftime("%d.%m.%Y %H:%M")))

    # ---- Giriş ----
    def giris_kontrol(self, kadi, sifre):
        kullanici = self.sorgula_tek("SELECT * FROM personeller WHERE kullanici_adi=? AND durum='Aktif'", (kadi,))
        if kullanici and check_password_hash(kullanici["sifre"], sifre):
            return kullanici
        return None

    # ---- Hastalar ----
    def hastalari_getir(self, arama=None):
        if arama:
            like = f"%{arama}%"
            return self.sorgula("SELECT * FROM hastalar WHERE ad_soyad LIKE ? OR tc LIKE ? ORDER BY id DESC", (like, like))
        return self.sorgula("SELECT * FROM hastalar ORDER BY id DESC")

    def hasta_getir_tek(self, hid):
        return self.sorgula_tek("SELECT * FROM hastalar WHERE id=?", (hid,))

    def hasta_ekle(self, v):
        return self.calistir("""INSERT INTO hastalar (ad_soyad, tc, dogum_tarihi, cinsiyet, kan_grubu, telefon,
                                 adres, acil_ad, acil_tel, gecmis, kayit_tarihi) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                             (v["ad_soyad"], v["tc"], v["dogum_tarihi"], v["cinsiyet"], v["kan_grubu"], v["telefon"],
                              v["adres"], v["acil_ad"], v["acil_tel"], v["gecmis"], v["kayit_tarihi"]))

    def hasta_guncelle(self, hid, v):
        self.calistir("""UPDATE hastalar SET ad_soyad=?, tc=?, dogum_tarihi=?, cinsiyet=?, kan_grubu=?, telefon=?,
                          adres=?, acil_ad=?, acil_tel=?, gecmis=? WHERE id=?""",
                     (v["ad_soyad"], v["tc"], v["dogum_tarihi"], v["cinsiyet"], v["kan_grubu"], v["telefon"],
                      v["adres"], v["acil_ad"], v["acil_tel"], v["gecmis"], hid))

    def hasta_sil(self, hid):
        self.calistir("DELETE FROM hastalar WHERE id=?", (hid,))

    # ---- Doktorlar ----
    def doktorlari_getir(self):
        return self.sorgula("SELECT * FROM doktorlar ORDER BY id DESC")

    def doktor_getir_tek(self, did):
        return self.sorgula_tek("SELECT * FROM doktorlar WHERE id=?", (did,))

    def doktor_ekle(self, v):
        return self.calistir("INSERT INTO doktorlar (ad_soyad, uzmanlik, poliklinik, uygunluk) VALUES (?,?,?,?)",
                             (v["ad_soyad"], v["uzmanlik"], v["poliklinik"], v["uygunluk"]))

    def doktor_guncelle(self, did, v):
        self.calistir("UPDATE doktorlar SET ad_soyad=?, uzmanlik=?, poliklinik=?, uygunluk=? WHERE id=?",
                     (v["ad_soyad"], v["uzmanlik"], v["poliklinik"], v["uygunluk"], did))

    def doktor_sil(self, did):
        self.calistir("DELETE FROM doktorlar WHERE id=?", (did,))

    # ---- Personel ----
    def personelleri_getir(self):
        return self.sorgula("SELECT * FROM personeller ORDER BY id DESC")

    def personel_getir_tek(self, pid):
        return self.sorgula_tek("SELECT * FROM personeller WHERE id=?", (pid,))

    def personel_ekle(self, v):
        return self.calistir("""INSERT INTO personeller (ad_soyad, rol, birim, telefon, kullanici_adi, sifre, durum)
                                 VALUES (?,?,?,?,?,?,?)""",
                             (v["ad_soyad"], v["rol"], v["birim"], v["telefon"], v["kullanici_adi"],
                              generate_password_hash(v["sifre"]), v["durum"]))

    def personel_guncelle(self, pid, v):
        self.calistir("""UPDATE personeller SET ad_soyad=?, rol=?, birim=?, telefon=?, kullanici_adi=?, sifre=?, durum=?
                          WHERE id=?""",
                     (v["ad_soyad"], v["rol"], v["birim"], v["telefon"], v["kullanici_adi"], v["sifre"], v["durum"], pid))

    def personel_sil(self, pid):
        self.calistir("DELETE FROM personeller WHERE id=?", (pid,))

    # ---- Poliklinikler ----
    def poliklinikleri_getir(self):
        return [r["ad"] for r in self.sorgula("SELECT ad FROM poliklinikler ORDER BY ad")]

    def poliklinik_ekle(self, ad):
        self.calistir("INSERT INTO poliklinikler (ad) VALUES (?)", (ad,))

    def poliklinik_sil(self, ad):
        self.calistir("DELETE FROM poliklinikler WHERE ad=?", (ad,))

    # ---- Randevular ----
    def randevulari_getir(self):
        return self.sorgula("""SELECT r.id, r.tarih, r.saat, r.durum, h.ad_soyad as hasta_ad, d.ad_soyad as doktor_ad
                                FROM randevular r JOIN hastalar h ON r.hasta_id=h.id
                                JOIN doktorlar d ON r.doktor_id=d.id ORDER BY r.id DESC""")

    def randevu_getir_tek(self, rid):
        return self.sorgula_tek("""SELECT r.*, h.ad_soyad as hasta_ad, d.ad_soyad as doktor_ad FROM randevular r
                             JOIN hastalar h ON r.hasta_id=h.id JOIN doktorlar d ON r.doktor_id=d.id WHERE r.id=?""", (rid,))

    def bekleyen_randevulari_getir(self):
        return self.sorgula("""SELECT r.id, r.tarih, r.saat, h.ad_soyad as hasta_ad, d.ad_soyad as doktor_ad
                                FROM randevular r JOIN hastalar h ON r.hasta_id=h.id
                                JOIN doktorlar d ON r.doktor_id=d.id WHERE r.durum='Bekliyor' ORDER BY r.id DESC""")

    def bugunun_randevulari_getir(self):
        bugun = datetime.now().strftime("%d.%m.%Y")
        return self.sorgula("""SELECT r.id, r.tarih, r.saat, r.durum, h.ad_soyad as hasta_ad, d.ad_soyad as doktor_ad
                                FROM randevular r JOIN hastalar h ON r.hasta_id=h.id
                                JOIN doktorlar d ON r.doktor_id=d.id WHERE r.tarih=? ORDER BY r.saat""", (bugun,))

    def randevu_ekle(self, hasta_id, doktor_id, tarih, saat):
        return self.calistir("INSERT INTO randevular (hasta_id, doktor_id, tarih, saat, durum) VALUES (?,?,?,?,'Bekliyor')",
                             (hasta_id, doktor_id, tarih, saat))

    def randevu_cakisma_var_mi(self, doktor_id, tarih, saat):
        r = self.sorgula("""SELECT COUNT(*) as c FROM randevular
                             WHERE doktor_id=? AND tarih=? AND saat=? AND durum != 'İptal Edildi'""",
                          (doktor_id, tarih, saat))
        return r[0]["c"] > 0

    def randevu_durum_guncelle(self, rid, durum):
        self.calistir("UPDATE randevular SET durum=? WHERE id=?", (durum, rid))

    def randevu_sil(self, rid):
        self.calistir("DELETE FROM randevular WHERE id=?", (rid,))

    def hasta_randevulari_getir(self, hasta_id):
        return self.sorgula("""SELECT r.*, d.ad_soyad as doktor_ad FROM randevular r
                                JOIN doktorlar d ON r.doktor_id=d.id WHERE r.hasta_id=? ORDER BY r.id DESC""", (hasta_id,))

    # ---- Muayene / Reçete ----
    def muayene_kaydet(self, randevu_id, hasta_ad, doktor_ad, sikayet, tani, not_, recete_listesi):
        muayene_id = self.calistir("""INSERT INTO muayeneler (randevu_id, hasta_ad, doktor_ad, sikayet, tani, not_, tarih)
                                       VALUES (?,?,?,?,?,?,?)""",
                                   (randevu_id, hasta_ad, doktor_ad, sikayet, tani, not_,
                                    datetime.now().strftime("%d.%m.%Y")))
        for ilac in recete_listesi:
            self.calistir("INSERT INTO receteler (muayene_id, ilac, doz, aciklama) VALUES (?,?,?,?)",
                         (muayene_id, ilac["ilac"], ilac["doz"], ilac["aciklama"]))
        self.randevu_durum_guncelle(randevu_id, "Tamamlandı")
        return muayene_id

    def recete_getir(self, muayene_id):
        return self.sorgula("SELECT * FROM receteler WHERE muayene_id=?", (muayene_id,))

    def muayeneleri_getir(self):
        return self.sorgula("SELECT * FROM muayeneler ORDER BY id DESC")

    def muayene_getir_tek(self, mid):
        return self.sorgula_tek("SELECT * FROM muayeneler WHERE id=?", (mid,))

    def hasta_muayeneleri_getir(self, hasta_id):
        return self.sorgula("""SELECT m.* FROM muayeneler m JOIN randevular r ON m.randevu_id=r.id
                                WHERE r.hasta_id=? ORDER BY m.id DESC""", (hasta_id,))

    # ---- Servis / Yatış ----
    def yatislari_getir(self):
        return self.sorgula("""SELECT y.*, h.ad_soyad as hasta_ad FROM servis_yatislari y
                                JOIN hastalar h ON y.hasta_id=h.id ORDER BY y.id DESC""")

    def yatis_getir_tek(self, yid):
        return self.sorgula_tek("""SELECT y.*, h.ad_soyad as hasta_ad FROM servis_yatislari y
                                JOIN hastalar h ON y.hasta_id=h.id WHERE y.id=?""", (yid,))

    def yatis_ekle(self, hasta_id, servis, oda, yatak, yatis_tarihi, tani):
        return self.calistir("""INSERT INTO servis_yatislari (hasta_id, servis, oda, yatak, yatis_tarihi, tani, durum)
                                 VALUES (?,?,?,?,?,?, 'Yatıyor')""",
                             (hasta_id, servis, oda, yatak, yatis_tarihi, tani))

    def yatis_durum_guncelle(self, yid, durum):
        self.calistir("UPDATE servis_yatislari SET durum=? WHERE id=?", (durum, yid))

    def yatis_sil(self, yid):
        self.calistir("DELETE FROM servis_yatislari WHERE id=?", (yid,))

    def hasta_yatislari_getir(self, hasta_id):
        return self.sorgula("SELECT * FROM servis_yatislari WHERE hasta_id=? ORDER BY id DESC", (hasta_id,))

    # ---- Ameliyat ----
    def ameliyatlari_getir(self):
        return self.sorgula("""SELECT a.*, h.ad_soyad as hasta_ad, d.ad_soyad as cerrah_ad FROM ameliyatlar a
                                JOIN hastalar h ON a.hasta_id=h.id JOIN doktorlar d ON a.doktor_id=d.id
                                ORDER BY a.id DESC""")

    def ameliyat_getir_tek(self, aid):
        return self.sorgula_tek("""SELECT a.*, h.ad_soyad as hasta_ad, d.ad_soyad as cerrah_ad FROM ameliyatlar a
                                JOIN hastalar h ON a.hasta_id=h.id JOIN doktorlar d ON a.doktor_id=d.id WHERE a.id=?""", (aid,))

    def ameliyat_ekle(self, hasta_id, doktor_id, ameliyat_adi, tarih, saat, salon):
        return self.calistir("""INSERT INTO ameliyatlar (hasta_id, doktor_id, ameliyat_adi, tarih, saat, salon, durum)
                                 VALUES (?,?,?,?,?,?, 'Planlandı')""",
                             (hasta_id, doktor_id, ameliyat_adi, tarih, saat, salon))

    def ameliyat_durum_guncelle(self, aid, durum):
        self.calistir("UPDATE ameliyatlar SET durum=? WHERE id=?", (durum, aid))

    def ameliyat_sil(self, aid):
        self.calistir("DELETE FROM ameliyatlar WHERE id=?", (aid,))

    def bugunku_ameliyat_sayisi(self):
        bugun = datetime.now().strftime("%d.%m.%Y")
        return self.sorgula("SELECT COUNT(*) as c FROM ameliyatlar WHERE tarih=?", (bugun,))[0]["c"]

    def hasta_ameliyatlari_getir(self, hasta_id):
        return self.sorgula("""SELECT a.*, d.ad_soyad as cerrah_ad FROM ameliyatlar a
                                JOIN doktorlar d ON a.doktor_id=d.id WHERE a.hasta_id=? ORDER BY a.id DESC""", (hasta_id,))

    # ---- Tetkikler ----
    def tetkikleri_getir(self):
        return self.sorgula("""SELECT t.*, h.ad_soyad as hasta_ad FROM tetkikler t
                                JOIN hastalar h ON t.hasta_id=h.id ORDER BY t.id DESC""")

    def tetkik_getir_tek(self, tid):
        return self.sorgula_tek("""SELECT t.*, h.ad_soyad as hasta_ad FROM tetkikler t
                                    JOIN hastalar h ON t.hasta_id=h.id WHERE t.id=?""", (tid,))

    def tetkik_ekle(self, hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor):
        return self.calistir("""INSERT INTO tetkikler (hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor, tarih)
                                 VALUES (?,?,?,?,?,?,?)""",
                             (hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor,
                              datetime.now().strftime("%d.%m.%Y")))

    def tetkik_sonuc_kaydet(self, tid, sonuc):
        self.calistir("UPDATE tetkikler SET sonuc=?, sonuc_tarihi=?, durum='Sonuçlandı' WHERE id=?",
                     (sonuc, datetime.now().strftime("%d.%m.%Y %H:%M"), tid))

    def bekleyen_tetkik_sayisi(self):
        return self.sorgula("SELECT COUNT(*) as c FROM tetkikler WHERE durum='İstem Bekliyor'")[0]["c"]

    def hasta_tetkikleri_getir(self, hasta_id):
        return self.sorgula("SELECT * FROM tetkikler WHERE hasta_id=? ORDER BY id DESC", (hasta_id,))

    # ---- İstatistikler / Dashboard ----
    def istatistikleri_getir(self):
        toplam_hasta = self.sorgula("SELECT COUNT(*) as c FROM hastalar")[0]["c"]
        bugun = datetime.now().strftime("%d.%m.%Y")
        bugunku_randevu = self.sorgula("SELECT COUNT(*) as c FROM randevular WHERE tarih=?", (bugun,))[0]["c"]
        yatan_hasta = self.sorgula("SELECT COUNT(*) as c FROM servis_yatislari WHERE durum='Yatıyor'")[0]["c"]
        bekleyen_randevu = self.sorgula("SELECT COUNT(*) as c FROM randevular WHERE durum='Bekliyor'")[0]["c"]
        return toplam_hasta, bugunku_randevu, yatan_hasta, bekleyen_randevu

    def son_hastalar_getir(self, limit=5):
        return self.sorgula("SELECT * FROM hastalar ORDER BY id DESC LIMIT ?", (limit,))

    def son_7_gun_trend(self):
        gunler, hasta_sayilari, randevu_sayilari = [], [], []
        for i in range(6, -1, -1):
            gun = datetime.now() - timedelta(days=i)
            gun_str = gun.strftime("%d.%m.%Y")
            gunler.append(gun.strftime("%d.%m"))
            hasta_sayilari.append(
                self.sorgula("SELECT COUNT(*) as c FROM hastalar WHERE kayit_tarihi LIKE ?", (f"{gun_str}%",))[0]["c"])
            randevu_sayilari.append(
                self.sorgula("SELECT COUNT(*) as c FROM randevular WHERE tarih=?", (gun_str,))[0]["c"])
        return gunler, hasta_sayilari, randevu_sayilari

    # ---- Loglar ----
    def log_ekle(self, kullanici_adi, rol, kategori, islem, aciklama, sonuc="Başarılı"):
        self.calistir("""INSERT INTO loglar (tarih, kullanici_adi, rol, kategori, islem, aciklama, sonuc)
                          VALUES (?,?,?,?,?,?,?)""",
                     (datetime.now().strftime("%d.%m.%Y %H:%M:%S"), kullanici_adi or "-", rol or "-",
                      kategori, islem, aciklama, sonuc))

    def loglari_getir(self, kategori=None, kullanici=None, sonuc=None):
        sql = "SELECT * FROM loglar WHERE 1=1"
        params = []
        if kategori:
            sql += " AND kategori=?"
            params.append(kategori)
        if kullanici:
            sql += " AND kullanici_adi LIKE ?"
            params.append(f"%{kullanici}%")
        if sonuc:
            sql += " AND sonuc=?"
            params.append(sonuc)
        sql += " ORDER BY id DESC LIMIT 500"
        return self.sorgula(sql, tuple(params))

    def log_kategorileri_getir(self):
        return [r["kategori"] for r in self.sorgula("SELECT DISTINCT kategori FROM loglar ORDER BY kategori")]