import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import sqlite3
import os
import random
from werkzeug.security import generate_password_hash, check_password_hash


# =====================================================================
#  VERİTABANI KATMANI  (hastane_sistemi.db - kalıcı SQLite dosyası)
# =====================================================================
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._tablolari_olustur()
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

    def randevu_ekle(self, hasta_id, doktor_id, tarih, saat):
        return self.calistir("INSERT INTO randevular (hasta_id, doktor_id, tarih, saat, durum) VALUES (?,?,?,?,'Bekliyor')",
                             (hasta_id, doktor_id, tarih, saat))

    def randevu_durum_guncelle(self, rid, durum):
        self.calistir("UPDATE randevular SET durum=? WHERE id=?", (durum, rid))

    def randevu_sil(self, rid):
        self.calistir("DELETE FROM randevular WHERE id=?", (rid,))

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

    # ---- Tetkikler ----
    def tetkikleri_getir(self):
        return self.sorgula("""SELECT t.*, h.ad_soyad as hasta_ad FROM tetkikler t
                                JOIN hastalar h ON t.hasta_id=h.id ORDER BY t.id DESC""")

    def tetkik_ekle(self, hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor):
        return self.calistir("""INSERT INTO tetkikler (hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor, tarih)
                                 VALUES (?,?,?,?,?,?,?)""",
                             (hasta_id, kodu, tetkik_adi, adet, durum, isteyen_doktor,
                              datetime.now().strftime("%d.%m.%Y")))

    # ---- İstatistikler ----
    def istatistikleri_getir(self):
        toplam_hasta = self.sorgula("SELECT COUNT(*) as c FROM hastalar")[0]["c"]
        bugun = datetime.now().strftime("%d.%m.%Y")
        bugunku_randevu = self.sorgula("SELECT COUNT(*) as c FROM randevular WHERE tarih=?", (bugun,))[0]["c"]
        yatan_hasta = self.sorgula("SELECT COUNT(*) as c FROM servis_yatislari WHERE durum='Yatıyor'")[0]["c"]
        bekleyen_randevu = self.sorgula("SELECT COUNT(*) as c FROM randevular WHERE durum='Bekliyor'")[0]["c"]
        return toplam_hasta, bugunku_randevu, yatan_hasta, bekleyen_randevu


# =====================================================================
#  ARAYÜZ KATMANI
# =====================================================================
class RequiemHBYSPro:
    def __init__(self, root):
        self.root = root
        self.root.title("Requiem HYBS - Yönetim Sistemi")
        self.root.geometry("1400x850")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Desktop.TFrame", background="#2a5a75")
        style.configure("Taskbar.TFrame", background="#e0e0e0")
        style.configure("Treeview.Heading", font=('Arial', 9, 'bold'), background="#d4d0c8")

        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hastane_sistemi.db")
        self.db = Database(db_path)
        self.aktif_kullanici = None

        self.giris_ekrani_olustur()

    # ---------------------------------------------------------------
    #  GİRİŞ EKRANI
    # ---------------------------------------------------------------
    def giris_ekrani_olustur(self):
        self.giris_frame = tk.Frame(self.root, bg="#2a5a75")
        self.giris_frame.pack(fill="both", expand=True)

        kutu = tk.Frame(self.giris_frame, bg="white", padx=40, pady=40)
        kutu.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(kutu, text="REQUIEM HBYS", font=("Arial", 22, "bold"), fg="#2a5a75", bg="white").pack(pady=(0, 5))
        tk.Label(kutu, text="Hastane Bilgi Yönetim Sistemi", font=("Arial", 10), bg="white", fg="#555").pack(pady=(0, 20))

        tk.Label(kutu, text="Kullanıcı Adı:", bg="white", font=("Arial", 10)).pack(anchor="w")
        e_kadi = tk.Entry(kutu, width=30, font=("Arial", 11))
        e_kadi.pack(pady=(0, 10))

        tk.Label(kutu, text="Şifre:", bg="white", font=("Arial", 10)).pack(anchor="w")
        e_sifre = tk.Entry(kutu, width=30, font=("Arial", 11), show="•")
        e_sifre.pack(pady=(0, 15))

        def giris_yap():
            kullanici = self.db.giris_kontrol(e_kadi.get().strip(), e_sifre.get().strip())
            if kullanici:
                self.aktif_kullanici = kullanici
                self.giris_frame.destroy()
                self.ana_ekrani_olustur()
            else:
                messagebox.showerror("Hata", "Kullanıcı adı veya şifre hatalı!", parent=self.root)

        e_sifre.bind("<Return>", lambda e: giris_yap())
        tk.Button(kutu, text="Giriş Yap", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                  width=25, command=giris_yap).pack(pady=5)
        tk.Label(kutu, text="Demo giriş: admin / 1234  (veya temel.bulut / 1234)", bg="white", fg="#999",
                 font=("Arial", 8)).pack(pady=(15, 0))

        e_kadi.focus()

    # ---------------------------------------------------------------
    #  ORTAK YARDIMCILAR
    # ---------------------------------------------------------------
    def _etiketli_entry(self, parent, etiket, satir, sutun=0, width=28, bg="#f0f0f0"):
        tk.Label(parent, text=etiket, bg=bg, font=("Arial", 9)).grid(
            row=satir, column=sutun, sticky="e", padx=5, pady=4)
        ent = tk.Entry(parent, width=width)
        ent.grid(row=satir, column=sutun + 1, sticky="w", padx=5, pady=4)
        return ent

    def _treeview_olustur(self, parent, kolonlar, basliklar, genislikler, height=10):
        tree = ttk.Treeview(parent, columns=kolonlar, show="headings", height=height)
        for col in kolonlar:
            tree.heading(col, text=basliklar[col])
            tree.column(col, width=genislikler[col])
        tree.pack(fill="both", expand=True, padx=5, pady=5)
        return tree

    # ---------------------------------------------------------------
    #  ANA MASAÜSTÜ EKRANI (dashboard + ikonlar)
    # ---------------------------------------------------------------
    def ana_ekrani_olustur(self):
        self.desktop_frame = ttk.Frame(self.root, style="Desktop.TFrame")
        self.desktop_frame.pack(fill="both", expand=True)

        dashboard = tk.Frame(self.desktop_frame, bg="#1e3f52")
        dashboard.pack(fill="x")
        self.dash_labels = {}
        for anahtar, baslik in [("hasta", "Toplam Hasta"), ("randevu", "Bugünkü Randevu"), ("yatan", "Yatan Hasta")]:
            kutu = tk.Frame(dashboard, bg="#1e3f52")
            kutu.pack(side="left", padx=25, pady=10)
            tk.Label(kutu, text=baslik, bg="#1e3f52", fg="#a0c4d8", font=("Arial", 8)).pack()
            lbl = tk.Label(kutu, text="0", bg="#1e3f52", fg="white", font=("Arial", 16, "bold"))
            lbl.pack()
            self.dash_labels[anahtar] = lbl
        tk.Button(dashboard, text="🔄 Yenile", bg="#1e3f52", fg="white", bd=0,
                  command=self.dashboard_guncelle).pack(side="left", padx=15)
        tk.Button(dashboard, text="Çıkış Yap", bg="#c0392b", fg="white", bd=0,
                  command=self.cikis_yap).pack(side="right", padx=15)

        icon_frame = tk.Frame(self.desktop_frame, bg="#2a5a75")
        icon_frame.pack(fill="both", expand=True)

        ikonlar = [
            ("Hasta Kayıt", "📄", 0, 1, self.hasta_kayit_modulunu_ac),
            ("Poliklinik", "🏥", 0, 2, self.poliklinik_modulunu_ac),
            ("Tetkik İstem\n(Lab/Radyoloji)", "🔬", 0, 3, self.tetkik_istem_modulunu_ac),
            ("Servis", "🛏️", 0, 4, self.servis_modulunu_ac),
            ("Ameliyat", "🔪", 0, 5, self.ameliyat_modulunu_ac),
            ("Sistem Yöneticisi", "⚙️", 1, 3, self.sistem_yoneticisi_modulunu_ac),
        ]

        for metin, ikon, satir, sutun, komut in ikonlar:
            btn = tk.Button(icon_frame, text=f"{ikon}\n{metin}", font=("Arial", 10, "bold"),
                            bg="#2a5a75", fg="white", activebackground="#3d7a9e",
                            borderwidth=0, cursor="hand2", width=15, height=4, command=komut)
            btn.grid(row=satir, column=sutun, padx=20, pady=30)

        self.taskbar = ttk.Frame(self.root, style="Taskbar.TFrame", height=40)
        self.taskbar.pack(side="bottom", fill="x")
        ad = self.aktif_kullanici["ad_soyad"]
        rol = self.aktif_kullanici["rol"]
        tk.Label(self.taskbar, text=f"Kullanıcı: {ad} | Rol: {rol} | Durum: Çevrimiçi", bg="#e0e0e0",
                 font=("Arial", 9)).pack(side="right", padx=10, pady=10)

        self.dashboard_guncelle()

    def dashboard_guncelle(self):
        toplam_hasta, bugunku_randevu, yatan_hasta, bekleyen_randevu = self.db.istatistikleri_getir()
        self.dash_labels["hasta"].config(text=str(toplam_hasta))
        self.dash_labels["randevu"].config(text=str(bugunku_randevu))
        self.dash_labels["yatan"].config(text=str(yatan_hasta))

    def cikis_yap(self):
        if messagebox.askyesno("Çıkış", "Oturumu kapatmak istiyor musunuz?", parent=self.root):
            self.desktop_frame.destroy()
            self.taskbar.destroy()
            self.aktif_kullanici = None
            self.giris_ekrani_olustur()

    # =================================================================
    #  1) HASTA KAYIT MODÜLÜ  (DB + arama)
    # =================================================================
    def hasta_kayit_modulunu_ac(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Hasta Kayıt")
        pencere.geometry("1150x800")
        pencere.configure(bg="#f0f0f0")

        form = tk.LabelFrame(pencere, text="Hasta Bilgileri", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        e_ad = self._etiketli_entry(form, "Adı Soyadı:", 0, 0)
        e_tc = self._etiketli_entry(form, "TC Kimlik No:", 0, 2)
        e_dogum = self._etiketli_entry(form, "Doğum Tarihi (gg.aa.yyyy):", 1, 0)

        tk.Label(form, text="Cinsiyet:", bg="#f0f0f0").grid(row=1, column=2, sticky="e", padx=5, pady=4)
        cb_cinsiyet = ttk.Combobox(form, values=["Erkek", "Kadın"], width=25, state="readonly")
        cb_cinsiyet.grid(row=1, column=3, sticky="w", padx=5, pady=4)

        tk.Label(form, text="Kan Grubu:", bg="#f0f0f0").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        cb_kan = ttk.Combobox(form, values=["A Rh+", "A Rh-", "B Rh+", "B Rh-", "AB Rh+", "AB Rh-", "0 Rh+", "0 Rh-"],
                              width=25, state="readonly")
        cb_kan.grid(row=2, column=1, sticky="w", padx=5, pady=4)

        e_tel = self._etiketli_entry(form, "Telefon:", 2, 2)
        e_adres = self._etiketli_entry(form, "Adres:", 3, 0, width=60)
        e_acil_ad = self._etiketli_entry(form, "Acil Kişi Adı:", 4, 0)
        e_acil_tel = self._etiketli_entry(form, "Acil Kişi Telefon:", 4, 2)

        tk.Label(form, text="Hasta Geçmişi / Kronik Hastalıklar:", bg="#f0f0f0").grid(
            row=5, column=0, sticky="ne", padx=5, pady=4)
        txt_gecmis = tk.Text(form, width=70, height=3)
        txt_gecmis.grid(row=5, column=1, columnspan=3, sticky="w", padx=5, pady=4)

        arama_frame = tk.Frame(pencere, bg="#f0f0f0")
        arama_frame.pack(fill="x", padx=10)
        tk.Label(arama_frame, text="🔍 Ara (Ad Soyad / TC):", bg="#f0f0f0", font=("Arial", 9)).pack(side="left", padx=5)
        e_ara = tk.Entry(arama_frame, width=35)
        e_ara.pack(side="left", padx=5, pady=5)

        liste_frame = tk.LabelFrame(pencere, text="Kayıtlı Hastalar", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand=True, padx=10, pady=10)

        kolonlar = ("id", "ad", "tc", "dogum", "cinsiyet", "kan", "tel", "kayit")
        basliklar = {"id": "ID", "ad": "Adı Soyadı", "tc": "TC Kimlik", "dogum": "Doğum Tarihi",
                    "cinsiyet": "Cinsiyet", "kan": "Kan Grubu", "tel": "Telefon", "kayit": "Kayıt Tarihi"}
        genislikler = {"id": 50, "ad": 190, "tc": 100, "dogum": 100, "cinsiyet": 70, "kan": 80, "tel": 110, "kayit": 140}
        tree = self._treeview_olustur(liste_frame, kolonlar, basliklar, genislikler, height=12)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for h in self.db.hastalari_getir(e_ara.get().strip()):
                tree.insert("", "end", iid=str(h["id"]), values=(
                    h["id"], h["ad_soyad"], h["tc"], h["dogum_tarihi"], h["cinsiyet"], h["kan_grubu"],
                    h["telefon"], h["kayit_tarihi"]))

        e_ara.bind("<KeyRelease>", lambda e: listeyi_doldur())

        def formu_temizle():
            for e in (e_ad, e_tc, e_dogum, e_tel, e_adres, e_acil_ad, e_acil_tel):
                e.delete(0, "end")
            cb_cinsiyet.set("")
            cb_kan.set("")
            txt_gecmis.delete("1.0", "end")
            if tree.selection():
                tree.selection_remove(tree.selection())

        def secileni_forma_yukle(event=None):
            secili = tree.selection()
            if not secili:
                return
            h = self.db.hasta_getir_tek(int(secili[0]))
            if not h:
                return
            for e in (e_ad, e_tc, e_dogum, e_tel, e_adres, e_acil_ad, e_acil_tel):
                e.delete(0, "end")
            txt_gecmis.delete("1.0", "end")
            e_ad.insert(0, h["ad_soyad"]); e_tc.insert(0, h["tc"]); e_dogum.insert(0, h["dogum_tarihi"])
            cb_cinsiyet.set(h["cinsiyet"]); cb_kan.set(h["kan_grubu"]); e_tel.insert(0, h["telefon"])
            e_adres.insert(0, h["adres"]); e_acil_ad.insert(0, h["acil_ad"]); e_acil_tel.insert(0, h["acil_tel"])
            txt_gecmis.insert("1.0", h["gecmis"])

        tree.bind("<<TreeviewSelect>>", secileni_forma_yukle)

        def hasta_kaydet():
            if not e_ad.get().strip() or not e_tc.get().strip():
                messagebox.showwarning("Uyarı", "Adı Soyadı ve TC Kimlik No zorunludur!", parent=pencere)
                return
            tc = e_tc.get().strip()
            if not (tc.isdigit() and len(tc) == 11):
                messagebox.showwarning("Uyarı", "TC Kimlik No 11 haneli sayı olmalıdır!", parent=pencere)
                return
            v = {
                "ad_soyad": e_ad.get().strip(), "tc": tc, "dogum_tarihi": e_dogum.get().strip(),
                "cinsiyet": cb_cinsiyet.get(), "kan_grubu": cb_kan.get(), "telefon": e_tel.get().strip(),
                "adres": e_adres.get().strip(), "acil_ad": e_acil_ad.get().strip(),
                "acil_tel": e_acil_tel.get().strip(), "gecmis": txt_gecmis.get("1.0", "end").strip()
            }
            secili = tree.selection()
            if secili:
                self.db.hasta_guncelle(int(secili[0]), v)
                messagebox.showinfo("Bilgi", "Hasta bilgileri güncellendi.", parent=pencere)
            else:
                v["kayit_tarihi"] = datetime.now().strftime("%d.%m.%Y %H:%M")
                self.db.hasta_ekle(v)
                messagebox.showinfo("Bilgi", "Yeni hasta başarıyla kaydedildi.", parent=pencere)
            listeyi_doldur()
            formu_temizle()

        def hasta_sil():
            secili = tree.selection()
            if not secili:
                messagebox.showwarning("Uyarı", "Lütfen silinecek hastayı seçin.", parent=pencere)
                return
            if messagebox.askyesno("Onay", "Seçili hasta kaydı silinsin mi?", parent=pencere):
                self.db.hasta_sil(int(secili[0]))
                listeyi_doldur()
                formu_temizle()

        btn_frame = tk.Frame(form, bg="#f0f0f0")
        btn_frame.grid(row=6, column=0, columnspan=4, pady=10)
        tk.Button(btn_frame, text="Kaydet / Güncelle", bg="#4CAF50", fg="white", font=("Arial", 9, "bold"),
                  width=18, command=hasta_kaydet).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Sil", bg="#f44336", fg="white", font=("Arial", 9, "bold"),
                  width=12, command=hasta_sil).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Formu Temizle", bg="#607d8b", fg="white", font=("Arial", 9, "bold"),
                  width=15, command=formu_temizle).pack(side="left", padx=5)

        listeyi_doldur()

    # =================================================================
    #  2) POLİKLİNİK MODÜLÜ
    # =================================================================
    def poliklinik_modulunu_ac(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Poliklinik Yönetimi")
        pencere.geometry("1300x800")
        pencere.configure(bg="#f0f0f0")

        notebook = ttk.Notebook(pencere)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_pol = ttk.Frame(notebook)
        tab_doktor = ttk.Frame(notebook)
        tab_randevu = ttk.Frame(notebook)
        tab_muayene = ttk.Frame(notebook)

        notebook.add(tab_pol, text="Poliklinikler")
        notebook.add(tab_doktor, text="Doktorlar")
        notebook.add(tab_randevu, text="Randevular")
        notebook.add(tab_muayene, text="Muayene / Reçete")

        self._poliklinikler_sekmesi(tab_pol)
        self._doktorlar_sekmesi(tab_doktor)
        self._randevular_sekmesi(tab_randevu)
        self._muayene_sekmesi(tab_muayene)

    def _poliklinikler_sekmesi(self, parent):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text="Poliklinik / Bölüm Ekle:", bg="white", font=("Arial", 9, "bold")).pack(anchor="w")
        ekle_frame = tk.Frame(frame, bg="white")
        ekle_frame.pack(anchor="w", pady=5)
        e_pol = tk.Entry(ekle_frame, width=30)
        e_pol.pack(side="left", padx=5)

        alt_frame = tk.Frame(frame, bg="white")
        alt_frame.pack(fill="both", expand=True)
        listbox = tk.Listbox(alt_frame, width=50, height=20, font=("Arial", 10))
        listbox.pack(side="left", padx=10, pady=10)

        def listeyi_doldur():
            listbox.delete(0, "end")
            for p in self.db.poliklinikleri_getir():
                listbox.insert("end", p)

        def pol_ekle():
            ad = e_pol.get().strip()
            if not ad:
                messagebox.showwarning("Uyarı", "Bölüm adı boş olamaz!", parent=parent)
                return
            try:
                self.db.poliklinik_ekle(ad)
            except sqlite3.IntegrityError:
                messagebox.showwarning("Uyarı", "Bu bölüm zaten mevcut!", parent=parent)
                return
            e_pol.delete(0, "end")
            listeyi_doldur()

        def pol_sil():
            secim = listbox.curselection()
            if not secim:
                messagebox.showwarning("Uyarı", "Silinecek bölümü seçin.", parent=parent)
                return
            self.db.poliklinik_sil(listbox.get(secim[0]))
            listeyi_doldur()

        tk.Button(ekle_frame, text="Ekle", bg="#4CAF50", fg="white", command=pol_ekle).pack(side="left", padx=5)

        sag_btn = tk.Frame(alt_frame, bg="white")
        sag_btn.pack(side="left", anchor="n", pady=10)
        tk.Button(sag_btn, text="Seçileni Sil", bg="#f44336", fg="white", width=15, command=pol_sil).pack(pady=5)

        listeyi_doldur()

    def _doktorlar_sekmesi(self, parent):
        form = tk.LabelFrame(parent, text="Doktor Bilgileri", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        e_ad = self._etiketli_entry(form, "Adı Soyadı:", 0, 0)
        tk.Label(form, text="Uzmanlık / Poliklinik:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        cb_pol = ttk.Combobox(form, values=self.db.poliklinikleri_getir(), width=25, state="readonly")
        cb_pol.grid(row=0, column=3, sticky="w", padx=5, pady=4)
        tk.Button(form, text="🔄", bg="#607d8b", fg="white",
                  command=lambda: cb_pol.config(values=self.db.poliklinikleri_getir())).grid(row=0, column=4, padx=5)

        tk.Label(form, text="Uygunluk Durumu:", bg="#f0f0f0").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        cb_uygunluk = ttk.Combobox(form, values=["Müsait", "Meşgul", "İzinli"], width=25, state="readonly")
        cb_uygunluk.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        cb_uygunluk.set("Müsait")

        liste_frame = tk.LabelFrame(parent, text="Kayıtlı Doktorlar", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand=True, padx=10, pady=10)

        kolonlar = ("id", "ad", "uzmanlik", "poliklinik", "uygunluk")
        basliklar = {"id": "ID", "ad": "Adı Soyadı", "uzmanlik": "Uzmanlık", "poliklinik": "Poliklinik", "uygunluk": "Uygunluk"}
        genislikler = {"id": 50, "ad": 200, "uzmanlik": 180, "poliklinik": 180, "uygunluk": 100}
        tree = self._treeview_olustur(liste_frame, kolonlar, basliklar, genislikler)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for d in self.db.doktorlari_getir():
                tree.insert("", "end", iid=str(d["id"]), values=(d["id"], d["ad_soyad"], d["uzmanlik"], d["poliklinik"], d["uygunluk"]))

        def secileni_yukle(event=None):
            sec = tree.selection()
            if not sec:
                return
            d = next((x for x in self.db.doktorlari_getir() if x["id"] == int(sec[0])), None)
            if not d:
                return
            e_ad.delete(0, "end"); e_ad.insert(0, d["ad_soyad"])
            cb_pol.set(d["poliklinik"]); cb_uygunluk.set(d["uygunluk"])

        tree.bind("<<TreeviewSelect>>", secileni_yukle)

        def doktor_kaydet():
            if not e_ad.get().strip() or not cb_pol.get():
                messagebox.showwarning("Uyarı", "Ad Soyad ve Poliklinik zorunludur!", parent=parent)
                return
            v = {"ad_soyad": e_ad.get().strip(), "uzmanlik": cb_pol.get(), "poliklinik": cb_pol.get(),
                 "uygunluk": cb_uygunluk.get()}
            sec = tree.selection()
            if sec:
                self.db.doktor_guncelle(int(sec[0]), v)
            else:
                self.db.doktor_ekle(v)
            listeyi_doldur()
            e_ad.delete(0, "end"); cb_pol.set(""); cb_uygunluk.set("Müsait")

        def doktor_sil():
            sec = tree.selection()
            if not sec:
                messagebox.showwarning("Uyarı", "Silinecek doktoru seçin.", parent=parent)
                return
            self.db.doktor_sil(int(sec[0]))
            listeyi_doldur()

        btn_frame = tk.Frame(form, bg="#f0f0f0")
        btn_frame.grid(row=2, column=0, columnspan=4, pady=8)
        tk.Button(btn_frame, text="Kaydet / Güncelle", bg="#4CAF50", fg="white", width=18, command=doktor_kaydet).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Sil", bg="#f44336", fg="white", width=12, command=doktor_sil).pack(side="left", padx=5)

        listeyi_doldur()

    def _randevular_sekmesi(self, parent):
        form = tk.LabelFrame(parent, text="Yeni Randevu", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Hasta:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        cb_hasta = ttk.Combobox(form, width=28, state="readonly")
        cb_hasta.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        tk.Label(form, text="Doktor:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        cb_doktor = ttk.Combobox(form, width=28, state="readonly")
        cb_doktor.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        e_tarih = self._etiketli_entry(form, "Tarih (gg.aa.yyyy):", 1, 0)
        e_saat = self._etiketli_entry(form, "Saat (ss:dd):", 1, 2, width=10)

        def comboxlari_guncelle():
            cb_hasta["values"] = [f'{h["id"]} - {h["ad_soyad"]}' for h in self.db.hastalari_getir()]
            cb_doktor["values"] = [f'{d["id"]} - {d["ad_soyad"]} ({d["poliklinik"]})' for d in self.db.doktorlari_getir()]

        tk.Button(form, text="🔄 Hasta/Doktor Listesini Yenile", bg="#607d8b", fg="white",
                  command=comboxlari_guncelle).grid(row=1, column=4, padx=10)

        liste_frame = tk.LabelFrame(parent, text="Randevu Listesi", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand=True, padx=10, pady=10)

        kolonlar = ("id", "hasta", "doktor", "tarih", "saat", "durum")
        basliklar = {"id": "ID", "hasta": "Hasta", "doktor": "Doktor", "tarih": "Tarih", "saat": "Saat", "durum": "Durum"}
        genislikler = {"id": 50, "hasta": 220, "doktor": 220, "tarih": 100, "saat": 80, "durum": 110}
        tree = self._treeview_olustur(liste_frame, kolonlar, basliklar, genislikler)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for r in self.db.randevulari_getir():
                tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["hasta_ad"], r["doktor_ad"], r["tarih"], r["saat"], r["durum"]))

        def randevu_olustur():
            if not cb_hasta.get() or not cb_doktor.get() or not e_tarih.get().strip() or not e_saat.get().strip():
                messagebox.showwarning("Uyarı", "Tüm alanları doldurun!", parent=parent)
                return
            hasta_id = int(cb_hasta.get().split(" - ")[0])
            doktor_id = int(cb_doktor.get().split(" - ")[0])
            self.db.randevu_ekle(hasta_id, doktor_id, e_tarih.get().strip(), e_saat.get().strip())
            listeyi_doldur()
            e_tarih.delete(0, "end"); e_saat.delete(0, "end")

        def durum_guncelle(yeni_durum):
            sec = tree.selection()
            if not sec:
                messagebox.showwarning("Uyarı", "Bir randevu seçin.", parent=parent)
                return
            self.db.randevu_durum_guncelle(int(sec[0]), yeni_durum)
            listeyi_doldur()

        def randevu_sil():
            sec = tree.selection()
            if not sec:
                return
            self.db.randevu_sil(int(sec[0]))
            listeyi_doldur()

        btn_frame = tk.Frame(form, bg="#f0f0f0")
        btn_frame.grid(row=2, column=0, columnspan=4, pady=8)
        tk.Button(btn_frame, text="Randevu Oluştur", bg="#4CAF50", fg="white", width=16, command=randevu_olustur).pack(side="left", padx=5)

        alt_btn = tk.Frame(liste_frame, bg="#f0f0f0")
        alt_btn.pack(anchor="e", padx=5, pady=5)
        tk.Button(alt_btn, text="Tamamlandı Yap", bg="#2196F3", fg="white", command=lambda: durum_guncelle("Tamamlandı")).pack(side="left", padx=5)
        tk.Button(alt_btn, text="İptal Et", bg="#ff9800", fg="white", command=lambda: durum_guncelle("İptal Edildi")).pack(side="left", padx=5)
        tk.Button(alt_btn, text="Sil", bg="#f44336", fg="white", command=randevu_sil).pack(side="left", padx=5)

        comboxlari_guncelle()
        listeyi_doldur()

    def _muayene_sekmesi(self, parent):
        sol = tk.Frame(parent, bg="white")
        sol.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        sag = tk.Frame(parent, bg="white", width=460)
        sag.pack(side="right", fill="y", padx=10, pady=10)

        tk.Label(sol, text="Muayene Bekleyen Randevular", bg="white", font=("Arial", 9, "bold")).pack(anchor="w")
        kolonlar = ("id", "hasta", "doktor", "tarih", "saat")
        basliklar = {"id": "ID", "hasta": "Hasta", "doktor": "Doktor", "tarih": "Tarih", "saat": "Saat"}
        genislikler = {"id": 50, "hasta": 180, "doktor": 180, "tarih": 90, "saat": 70}
        tree = self._treeview_olustur(sol, kolonlar, basliklar, genislikler, height=18)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for r in self.db.bekleyen_randevulari_getir():
                tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["hasta_ad"], r["doktor_ad"], r["tarih"], r["saat"]))

        tk.Button(sol, text="🔄 Listeyi Yenile", bg="#607d8b", fg="white", command=listeyi_doldur).pack(anchor="w", pady=5)

        tk.Label(sag, text="Muayene Bilgileri", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 5))
        tk.Label(sag, text="Şikayet:", bg="white").pack(anchor="w")
        txt_sikayet = tk.Text(sag, width=52, height=2)
        txt_sikayet.pack(anchor="w", pady=2)
        tk.Label(sag, text="Tanı:", bg="white").pack(anchor="w")
        txt_tani = tk.Text(sag, width=52, height=2)
        txt_tani.pack(anchor="w", pady=2)
        tk.Label(sag, text="Doktor Notu:", bg="white").pack(anchor="w")
        txt_not = tk.Text(sag, width=52, height=3)
        txt_not.pack(anchor="w", pady=2)

        tk.Label(sag, text="Reçete - İlaç Ekle", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", pady=(10, 2))
        ilac_frame = tk.Frame(sag, bg="white")
        ilac_frame.pack(anchor="w")
        e_ilac = tk.Entry(ilac_frame, width=16); e_ilac.grid(row=0, column=0, padx=2)
        e_doz = tk.Entry(ilac_frame, width=9); e_doz.grid(row=0, column=1, padx=2)
        e_aciklama = tk.Entry(ilac_frame, width=18); e_aciklama.grid(row=0, column=2, padx=2)
        tk.Label(ilac_frame, text="İlaç", bg="white", font=("Arial", 7)).grid(row=1, column=0)
        tk.Label(ilac_frame, text="Dozaj", bg="white", font=("Arial", 7)).grid(row=1, column=1)
        tk.Label(ilac_frame, text="Kullanım", bg="white", font=("Arial", 7)).grid(row=1, column=2)

        recete_listbox = tk.Listbox(sag, width=58, height=6)
        recete_listbox.pack(pady=5)
        gecici_recete = []

        def ilac_ekle():
            if not e_ilac.get().strip():
                return
            gecici_recete.append({"ilac": e_ilac.get().strip(), "doz": e_doz.get().strip(), "aciklama": e_aciklama.get().strip()})
            recete_listbox.insert("end", f"{e_ilac.get()} - {e_doz.get()} - {e_aciklama.get()}")
            e_ilac.delete(0, "end"); e_doz.delete(0, "end"); e_aciklama.delete(0, "end")

        tk.Button(ilac_frame, text="Ekle", bg="#4CAF50", fg="white", command=ilac_ekle).grid(row=0, column=3, padx=5)

        def muayene_kaydet_ui():
            sec = tree.selection()
            if not sec:
                messagebox.showwarning("Uyarı", "Bir randevu seçin.", parent=parent)
                return
            rid = int(sec[0])
            r = self.db.randevu_getir_tek(rid)
            self.db.muayene_kaydet(rid, r["hasta_ad"], r["doktor_ad"], txt_sikayet.get("1.0", "end").strip(),
                                   txt_tani.get("1.0", "end").strip(), txt_not.get("1.0", "end").strip(), gecici_recete)
            gecici_recete.clear()
            messagebox.showinfo("Bilgi", "Muayene ve reçete kaydedildi.", parent=parent)
            txt_sikayet.delete("1.0", "end"); txt_tani.delete("1.0", "end"); txt_not.delete("1.0", "end")
            recete_listbox.delete(0, "end")
            listeyi_doldur()

        tk.Button(sag, text="Muayeneyi Kaydet", bg="#4CAF50", fg="white", font=("Arial", 9, "bold"),
                  width=20, command=muayene_kaydet_ui).pack(pady=10)

        listeyi_doldur()

    # =================================================================
    #  3) SERVİS MODÜLÜ
    # =================================================================
    def servis_modulunu_ac(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Servis - Yatış Yönetimi")
        pencere.geometry("1250x780")
        pencere.configure(bg="#f0f0f0")

        form = tk.LabelFrame(pencere, text="Yeni Yatış", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Hasta:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        cb_hasta = ttk.Combobox(form, width=28, state="readonly")
        cb_hasta.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        tk.Label(form, text="Servis:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        cb_servis = ttk.Combobox(form, values=["Dahiliye Servisi", "Genel Cerrahi Servisi", "Yoğun Bakım",
                                                "Pediatri Servisi", "Kardiyoloji Servisi", "Ortopedi Servisi"],
                                  width=26, state="readonly")
        cb_servis.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        def hasta_listesini_yukle():
            cb_hasta["values"] = [f'{h["id"]} - {h["ad_soyad"]}' for h in self.db.hastalari_getir()]

        tk.Button(form, text="🔄 Yenile", bg="#607d8b", fg="white", command=hasta_listesini_yukle).grid(row=0, column=4, padx=10)

        e_oda = self._etiketli_entry(form, "Oda No:", 1, 0, width=10)
        e_yatak = self._etiketli_entry(form, "Yatak No:", 1, 2, width=10)
        e_tarih = self._etiketli_entry(form, "Yatış Tarihi:", 2, 0)
        e_tani = self._etiketli_entry(form, "Ön Tanı:", 2, 2)

        liste_frame = tk.LabelFrame(pencere, text="Yatış Listesi", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand=True, padx=10, pady=10)

        kolonlar = ("id", "hasta", "servis", "oda", "yatak", "tarih", "tani", "durum")
        basliklar = {"id": "ID", "hasta": "Hasta", "servis": "Servis", "oda": "Oda", "yatak": "Yatak",
                    "tarih": "Yatış Tarihi", "tani": "Ön Tanı", "durum": "Durum"}
        genislikler = {"id": 40, "hasta": 180, "servis": 150, "oda": 50, "yatak": 50, "tarih": 100, "tani": 150, "durum": 100}
        tree = self._treeview_olustur(liste_frame, kolonlar, basliklar, genislikler)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for y in self.db.yatislari_getir():
                tree.insert("", "end", iid=str(y["id"]), values=(y["id"], y["hasta_ad"], y["servis"], y["oda"],
                                                                   y["yatak"], y["yatis_tarihi"], y["tani"], y["durum"]))

        def yatis_olustur():
            if not cb_hasta.get() or not cb_servis.get() or not e_oda.get().strip():
                messagebox.showwarning("Uyarı", "Hasta, servis ve oda bilgisi zorunludur!", parent=pencere)
                return
            hasta_id = int(cb_hasta.get().split(" - ")[0])
            self.db.yatis_ekle(hasta_id, cb_servis.get(), e_oda.get().strip(), e_yatak.get().strip(),
                               e_tarih.get().strip() or datetime.now().strftime("%d.%m.%Y"), e_tani.get().strip())
            listeyi_doldur()
            for e in (e_oda, e_yatak, e_tarih, e_tani):
                e.delete(0, "end")

        def taburcu_et():
            sec = tree.selection()
            if not sec:
                messagebox.showwarning("Uyarı", "Bir yatış seçin.", parent=pencere)
                return
            self.db.yatis_durum_guncelle(int(sec[0]), "Taburcu Oldu")
            listeyi_doldur()

        def yatis_sil():
            sec = tree.selection()
            if not sec:
                return
            self.db.yatis_sil(int(sec[0]))
            listeyi_doldur()

        btn_frame = tk.Frame(form, bg="#f0f0f0")
        btn_frame.grid(row=3, column=0, columnspan=4, pady=8)
        tk.Button(btn_frame, text="Yatış Oluştur", bg="#4CAF50", fg="white", width=16, command=yatis_olustur).pack(side="left", padx=5)

        alt_btn = tk.Frame(liste_frame, bg="#f0f0f0")
        alt_btn.pack(anchor="e", padx=5, pady=5)
        tk.Button(alt_btn, text="Taburcu Et", bg="#2196F3", fg="white", command=taburcu_et).pack(side="left", padx=5)
        tk.Button(alt_btn, text="Sil", bg="#f44336", fg="white", command=yatis_sil).pack(side="left", padx=5)

        if not self.db.hastalari_getir():
            messagebox.showinfo("Bilgi", "Yatış işlemi yapmadan önce Hasta Kayıt modülünden hasta ekleyin.", parent=pencere)

        hasta_listesini_yukle()
        listeyi_doldur()

    # =================================================================
    #  4) AMELİYAT MODÜLÜ
    # =================================================================
    def ameliyat_modulunu_ac(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Ameliyat Yönetimi")
        pencere.geometry("1250x780")
        pencere.configure(bg="#f0f0f0")

        form = tk.LabelFrame(pencere, text="Yeni Ameliyat Planlama", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Hasta:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        cb_hasta = ttk.Combobox(form, width=28, state="readonly")
        cb_hasta.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        tk.Label(form, text="Cerrah:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        cb_doktor = ttk.Combobox(form, width=28, state="readonly")
        cb_doktor.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        def listeleri_yukle():
            cb_hasta["values"] = [f'{h["id"]} - {h["ad_soyad"]}' for h in self.db.hastalari_getir()]
            cb_doktor["values"] = [f'{d["id"]} - {d["ad_soyad"]}' for d in self.db.doktorlari_getir()]

        tk.Button(form, text="🔄 Yenile", bg="#607d8b", fg="white", command=listeleri_yukle).grid(row=0, column=4, padx=10)

        e_ameliyat_adi = self._etiketli_entry(form, "Ameliyat Adı:", 1, 0)
        e_salon = self._etiketli_entry(form, "Ameliyathane No:", 1, 2, width=10)
        e_tarih = self._etiketli_entry(form, "Tarih:", 2, 0)
        e_saat = self._etiketli_entry(form, "Saat:", 2, 2, width=10)

        liste_frame = tk.LabelFrame(pencere, text="Ameliyat Listesi", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand=True, padx=10, pady=10)

        kolonlar = ("id", "hasta", "ameliyat", "cerrah", "tarih", "saat", "salon", "durum")
        basliklar = {"id": "ID", "hasta": "Hasta", "ameliyat": "Ameliyat", "cerrah": "Cerrah", "tarih": "Tarih",
                    "saat": "Saat", "salon": "Salon", "durum": "Durum"}
        genislikler = {"id": 40, "hasta": 160, "ameliyat": 180, "cerrah": 150, "tarih": 90, "saat": 60, "salon": 60, "durum": 110}
        tree = self._treeview_olustur(liste_frame, kolonlar, basliklar, genislikler)

        def listeyi_doldur():
            tree.delete(*tree.get_children())
            for a in self.db.ameliyatlari_getir():
                tree.insert("", "end", iid=str(a["id"]), values=(a["id"], a["hasta_ad"], a["ameliyat_adi"], a["cerrah_ad"],
                                                                   a["tarih"], a["saat"], a["salon"], a["durum"]))

        def ameliyat_planla():
            if not cb_hasta.get() or not cb_doktor.get() or not e_ameliyat_adi.get().strip():
                messagebox.showwarning("Uyarı", "Hasta, cerrah ve ameliyat adı zorunludur!", parent=pencere)
                return
            hasta_id = int(cb_hasta.get().split(" - ")[0])
            doktor_id = int(cb_doktor.get().split(" - ")[0])
            self.db.ameliyat_ekle(hasta_id, doktor_id, e_ameliyat_adi.get().strip(), e_tarih.get().strip(),
                                  e_saat.get().strip(), e_salon.get().strip())
            listeyi_doldur()
            for e in (e_ameliyat_adi, e_salon, e_tarih, e_saat):
                e.delete(0, "end")

        def durum_guncelle(yeni):
            sec = tree.selection()
            if not sec:
                messagebox.showwarning("Uyarı", "Bir ameliyat seçin.", parent=pencere)
                return
            self.db.ameliyat_durum_guncelle(int(sec[0]), yeni)
            listeyi_doldur()

        def ameliyat_sil():
            sec = tree.selection()
            if not sec:
                return
            self.db.ameliyat_sil(int(sec[0]))
            listeyi_doldur()

        btn_frame = tk.Frame(form, bg="#f0f0f0")
        btn_frame.grid(row=3, column=0, columnspan=4, pady=8)
        tk.Button(btn_frame, text="Ameliyat Planla", bg="#4CAF50", fg="white", width=16, command=ameliyat_planla).pack(side="left", padx=5)

        alt_btn = tk.Frame(liste_frame, bg="#f0f0f0")
        alt_btn.pack(anchor="e", padx=5, pady=5)
        tk.Button(alt_btn, text="Devam Ediyor", bg="#ff9800", fg="white", command=lambda: durum_guncelle("Devam Ediyor")).pack(side="left", padx=5)
        tk.Button(alt_btn, text="Tamamlandı", bg="#2196F3", fg="white", command=lambda: durum_guncelle("Tamamlandı")).pack(side="left", padx=5)
        tk.Button(alt_btn, text="İptal Et", bg="#9e9e9e", fg="white", command=lambda: durum_guncelle("İptal Edildi")).pack(side="left", padx=5)
        tk.Button(alt_btn, text="Sil", bg="#f44336", fg="white", command=ameliyat_sil).pack(side="left", padx=5)

        if not self.db.hastalari_getir() or not self.db.doktorlari_getir():
            messagebox.showinfo("Bilgi", "Ameliyat planlamadan önce hasta ve doktor kayıtlarının olduğundan emin olun.", parent=pencere)

        listeleri_yukle()
        listeyi_doldur()

    # =================================================================
    #  5) SİSTEM YÖNETİCİSİ MODÜLÜ
    # =================================================================
    def sistem_yoneticisi_modulunu_ac(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Sistem Yöneticisi - Personel Yönetimi")
        pencere.geometry("1250x800")
        pencere.configure(bg="#f0f0f0")

        form = tk.LabelFrame(pencere, text="Personel Bilgileri", bg="#f0f0f0", font=("Arial", 9, "bold"))
        form.pack(fill="x", padx=10, pady=10)

        e_ad = self._etiketli_entry(form, "Adı Soyadı:", 0, 0)
        tk.Label(form, text="Rol:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        cb_rol = ttk.Combobox(form, values=["Hemşire", "Sekreter", "Laborant", "Yönetici", "Teknisyen", "Doktor"],
                              width=25, state="readonly")
        cb_rol.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        tk.Label(form, text="Birim / Poliklinik:", bg="#f0f0f0").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        cb_birim = ttk.Combobox(form, values=self.db.poliklinikleri_getir() + ["Genel Yönetim", "Laboratuvar", "Acil Servis"],
                                 width=25, state="readonly")
        cb_birim.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        e_tel = self._etiketli_entry(form, "Telefon:", 1, 2)
        e_kadi = self._etiketli_entry(form, "Kullanıcı Adı:", 2, 0)
        e_sifre = self._etiketli_entry(form, "Şifre:", 2, 2)

        tk.Label(form, text="Durum:", bg="#f0f0f0").grid(row=3, column=0, sticky="e", padx=5, pady=4)
        cb_durum = ttk.Combobox(form, values=["Aktif", "Pasif"], width=25, state="readonly")
        cb_durum.grid(row=3, column=1, sticky="w", padx=5, pady=4)
        cb_durum.set("Aktif")

        liste_frame = tk.LabelFrame(pencere, text="Kayıtlı Personel", bg="#f0f0f0", font=("Arial", 9, "bold"))
        liste_frame.pack(fill="both", expand