import os
import csv
import random
from functools import wraps
from datetime import datetime
from io import BytesIO, StringIO

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from xhtml2pdf import pisa

from database import Database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "web_hastane.db")

app = Flask(__name__)
app.secret_key = "novahbys-gelistirme-anahtari-degistir"
db = Database(DB_PATH)

GORUNTULEME_LISTESI = [
    "MRG, Beyin, kontrastlı", "MRG, Servikal vertebra", "MRG, Lomber vertebra, kontrastlı",
    "MRG, Diz - sağ, kontrastlı", "MRG, Omuz - sağ, kontrastlı", "BT, Toraks, kontrastlı",
    "BT, Abdomen, kontrastsız", "Röntgen, Akciğer PA", "Röntgen, El bileği", "Ultrason, Batın",
    "Doppler USG, Alt Ekstremite", "Mamografi, Bilateral",
]
LABORATUVAR_LISTESI = [
    "Glukoz (Açlık)", "Üre", "Kreatinin", "AST (SGOT)", "ALT (SGPT)", "Kolesterol, Total",
    "Trigliserid", "HDL Kolesterol", "LDL Kolesterol", "Sodyum (Na)", "Potasyum (K)",
    "Hemogram (Tam Kan Sayımı)", "TSH", "Serbest T4", "CRP", "Vitamin B12", "Ferritin",
]

# ---------------------------------------------------------------------
#  ROL BAZLI MODÜL YETKİLENDİRMESİ
# ---------------------------------------------------------------------
ROL_MODUL_YETKILERI = {
    "Yönetici": {"hasta", "doktor", "poliklinik", "randevu", "muayene", "servis",
                 "ameliyat", "tetkik", "personel", "log"},
    "Doktor": {"hasta", "doktor", "poliklinik", "randevu", "muayene", "servis", "ameliyat", "tetkik"},
    "Hemşire": {"hasta", "randevu", "servis", "tetkik"},
    "Sekreter": {"hasta", "doktor", "poliklinik", "randevu"},
    "Laborant": {"tetkik"},
    "Teknisyen": {"tetkik", "ameliyat"},
}


# ---------------------------------------------------------------------
#  YETKİLENDİRME
# ---------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Lütfen giriş yapın.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def modul_gerekli(modul):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            rol = session.get("rol")
            izinli = ROL_MODUL_YETKILERI.get(rol, set())
            if modul not in izinli:
                db.log_ekle(session.get("ad"), rol, "YETKİ", "ERİŞİM_RED",
                            f"'{modul}' modülüne yetkisiz erişim denemesi ({request.path}).", "Başarısız")
                flash("Bu sayfa için yetkiniz bulunmuyor.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_globals():
    def modul_yetkili(modul):
        return modul in ROL_MODUL_YETKILERI.get(session.get("rol"), set())
    return {"simdi": datetime.now().strftime("%d.%m.%Y %H:%M"), "modul_yetkili": modul_yetkili}


def pdf_olustur(html_icerik, dosya_adi):
    buffer = BytesIO()
    pisa.CreatePDF(src=html_icerik, dest=buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=dosya_adi)


def csv_indir(satirlar, basliklar, dosya_adi):
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(basliklar)
    for s in satirlar:
        writer.writerow(s)
    mem = BytesIO()
    mem.write("\ufeff".encode("utf-8"))
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=dosya_adi)


# ---------------------------------------------------------------------
#  GİRİŞ / ÇIKIŞ
# ---------------------------------------------------------------------
@app.route("/giris", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        kadi = request.form.get("kullanici_adi", "").strip()
        sifre = request.form.get("sifre", "").strip()
        kullanici = db.giris_kontrol(kadi, sifre)
        if kullanici:
            session["user_id"] = kullanici["id"]
            session["ad"] = kullanici["ad_soyad"]
            session["rol"] = kullanici["rol"]
            db.log_ekle(kullanici["ad_soyad"], kullanici["rol"], "GİRİŞ", "GİRİŞ",
                        "Sisteme başarıyla giriş yapıldı.", "Başarılı")
            flash(f"Hoş geldiniz, {kullanici['ad_soyad']}.", "success")
            return redirect(url_for("dashboard"))
        db.log_ekle(kadi, "-", "GİRİŞ", "GİRİŞ",
                    f"Hatalı giriş denemesi (kullanıcı adı: '{kadi}').", "Başarısız")
        flash("Kullanıcı adı veya şifre hatalı!", "danger")
    return render_template("login.html")


@app.route("/cikis")
def logout():
    if "ad" in session:
        db.log_ekle(session.get("ad"), session.get("rol"), "GİRİŞ", "ÇIKIŞ", "Oturum kapatıldı.", "Başarılı")
    session.clear()
    flash("Oturum kapatıldı.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------
#  ANA PANEL
# ---------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    toplam_hasta, bugunku_randevu, yatan_hasta, bekleyen_randevu = db.istatistikleri_getir()
    bekleyen_tetkik = db.bekleyen_tetkik_sayisi()
    bugunku_ameliyat = db.bugunku_ameliyat_sayisi()
    son_hastalar = db.son_hastalar_getir(5)
    bugunun_randevulari = db.bugunun_randevulari_getir()
    gunler, hasta_trend, randevu_trend = db.son_7_gun_trend()
    return render_template("dashboard.html", toplam_hasta=toplam_hasta, bugunku_randevu=bugunku_randevu,
                           yatan_hasta=yatan_hasta, bekleyen_randevu=bekleyen_randevu,
                           bekleyen_tetkik=bekleyen_tetkik, bugunku_ameliyat=bugunku_ameliyat,
                           son_hastalar=son_hastalar, bugunun_randevulari=bugunun_randevulari,
                           gunler=gunler, hasta_trend=hasta_trend, randevu_trend=randevu_trend)


# ---------------------------------------------------------------------
#  HASTA KAYIT
# ---------------------------------------------------------------------
@app.route("/hastalar")
@login_required
@modul_gerekli("hasta")
def hastalar():
    q = request.args.get("q", "").strip()
    return render_template("hastalar.html", hastalar=db.hastalari_getir(q), q=q)


@app.route("/hastalar/form")
@app.route("/hastalar/form/<int:hid>")
@login_required
@modul_gerekli("hasta")
def hasta_form(hid=None):
    hasta = db.hasta_getir_tek(hid) if hid else None
    return render_template("hasta_form.html", hasta=hasta)


@app.route("/hastalar/kaydet", methods=["POST"])
@login_required
@modul_gerekli("hasta")
def hasta_kaydet():
    hid = request.form.get("id")
    tc = request.form.get("tc", "").strip()
    ad = request.form.get("ad_soyad", "").strip()
    if not ad or not tc:
        flash("Adı Soyadı ve TC Kimlik No zorunludur!", "warning")
        return redirect(url_for("hasta_form", hid=hid) if hid else url_for("hasta_form"))
    if not (tc.isdigit() and len(tc) == 11):
        flash("TC Kimlik No 11 haneli sayı olmalıdır!", "warning")
        return redirect(url_for("hasta_form", hid=hid) if hid else url_for("hasta_form"))

    v = {
        "ad_soyad": ad, "tc": tc, "dogum_tarihi": request.form.get("dogum_tarihi", "").strip(),
        "cinsiyet": request.form.get("cinsiyet", ""), "kan_grubu": request.form.get("kan_grubu", ""),
        "telefon": request.form.get("telefon", "").strip(), "adres": request.form.get("adres", "").strip(),
        "acil_ad": request.form.get("acil_ad", "").strip(), "acil_tel": request.form.get("acil_tel", "").strip(),
        "gecmis": request.form.get("gecmis", "").strip(),
    }
    if hid:
        db.hasta_guncelle(int(hid), v)
        db.log_ekle(session.get("ad"), session.get("rol"), "HASTA", "GÜNCELLE",
                    f"'{ad}' adlı hastanın bilgileri güncellendi.")
        flash("Hasta bilgileri güncellendi.", "success")
    else:
        v["kayit_tarihi"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        db.hasta_ekle(v)
        db.log_ekle(session.get("ad"), session.get("rol"), "HASTA", "EKLE",
                    f"'{ad}' adlı yeni hasta kaydedildi.")
        flash("Yeni hasta başarıyla kaydedildi.", "success")
    return redirect(url_for("hastalar"))


@app.route("/hastalar/<int:hid>/sil", methods=["POST"])
@login_required
@modul_gerekli("hasta")
def hasta_sil(hid):
    hasta = db.hasta_getir_tek(hid)
    db.hasta_sil(hid)
    db.log_ekle(session.get("ad"), session.get("rol"), "HASTA", "SİL",
                f"'{hasta['ad_soyad'] if hasta else hid}' adlı hasta kaydı silindi.")
    flash("Hasta kaydı silindi.", "info")
    return redirect(url_for("hastalar"))


@app.route("/hastalar/<int:hid>/detay")
@login_required
@modul_gerekli("hasta")
def hasta_detay(hid):
    hasta = db.hasta_getir_tek(hid)
    if not hasta:
        flash("Hasta bulunamadı.", "danger")
        return redirect(url_for("hastalar"))
    return render_template("hasta_detay.html", hasta=hasta,
                           randevular=db.hasta_randevulari_getir(hid),
                           muayeneler=db.hasta_muayeneleri_getir(hid),
                           tetkikler=db.hasta_tetkikleri_getir(hid),
                           yatislar=db.hasta_yatislari_getir(hid),
                           ameliyatlar=db.hasta_ameliyatlari_getir(hid))


@app.route("/hastalar/disa-aktar")
@login_required
@modul_gerekli("hasta")
def hastalar_disa_aktar():
    satirlar = [[h["id"], h["ad_soyad"], h["tc"], h["dogum_tarihi"], h["cinsiyet"], h["kan_grubu"],
                 h["telefon"], h["kayit_tarihi"]] for h in db.hastalari_getir()]
    db.log_ekle(session.get("ad"), session.get("rol"), "HASTA", "DIŞA_AKTAR",
                "Hasta listesi CSV olarak dışa aktarıldı.")
    return csv_indir(satirlar, ["ID", "Ad Soyad", "TC", "Doğum Tarihi", "Cinsiyet", "Kan Grubu", "Telefon", "Kayıt Tarihi"],
                     "hastalar.csv")


# ---------------------------------------------------------------------
#  DOKTORLAR
# ---------------------------------------------------------------------
@app.route("/doktorlar")
@login_required
@modul_gerekli("doktor")
def doktorlar():
    return render_template("doktorlar.html", doktorlar=db.doktorlari_getir())


@app.route("/doktorlar/form")
@app.route("/doktorlar/form/<int:did>")
@login_required
@modul_gerekli("doktor")
def doktor_form(did=None):
    doktor = db.doktor_getir_tek(did) if did else None
    return render_template("doktor_form.html", doktor=doktor, poliklinikler=db.poliklinikleri_getir())


@app.route("/doktorlar/kaydet", methods=["POST"])
@login_required
@modul_gerekli("doktor")
def doktor_kaydet():
    did = request.form.get("id")
    ad = request.form.get("ad_soyad", "").strip()
    pol = request.form.get("poliklinik", "")
    if not ad or not pol:
        flash("Ad Soyad ve Poliklinik zorunludur!", "warning")
        return redirect(url_for("doktor_form"))
    v = {"ad_soyad": ad, "uzmanlik": pol, "poliklinik": pol, "uygunluk": request.form.get("uygunluk", "Müsait")}
    if did:
        db.doktor_guncelle(int(did), v)
        db.log_ekle(session.get("ad"), session.get("rol"), "DOKTOR", "GÜNCELLE",
                    f"'{ad}' adlı doktorun bilgileri güncellendi.")
        flash("Doktor bilgileri güncellendi.", "success")
    else:
        db.doktor_ekle(v)
        db.log_ekle(session.get("ad"), session.get("rol"), "DOKTOR", "EKLE", f"'{ad}' adlı yeni doktor eklendi.")
        flash("Yeni doktor eklendi.", "success")
    return redirect(url_for("doktorlar"))


@app.route("/doktorlar/<int:did>/sil", methods=["POST"])
@login_required
@modul_gerekli("doktor")
def doktor_sil(did):
    doktor = db.doktor_getir_tek(did)
    db.doktor_sil(did)
    db.log_ekle(session.get("ad"), session.get("rol"), "DOKTOR", "SİL",
                f"'{doktor['ad_soyad'] if doktor else did}' adlı doktor kaydı silindi.")
    flash("Doktor kaydı silindi.", "info")
    return redirect(url_for("doktorlar"))


# ---------------------------------------------------------------------
#  POLİKLİNİKLER
# ---------------------------------------------------------------------
@app.route("/poliklinikler")
@login_required
@modul_gerekli("poliklinik")
def poliklinikler():
    return render_template("poliklinikler.html", poliklinikler=db.poliklinikleri_getir())


@app.route("/poliklinikler/ekle", methods=["POST"])
@login_required
@modul_gerekli("poliklinik")
def poliklinik_ekle():
    ad = request.form.get("ad", "").strip()
    if not ad:
        flash("Bölüm adı boş olamaz!", "warning")
    else:
        try:
            db.poliklinik_ekle(ad)
            db.log_ekle(session.get("ad"), session.get("rol"), "POLİKLİNİK", "EKLE",
                        f"'{ad}' adlı poliklinik eklendi.")
            flash("Poliklinik eklendi.", "success")
        except Exception:
            db.log_ekle(session.get("ad"), session.get("rol"), "POLİKLİNİK", "EKLE",
                        f"'{ad}' adlı poliklinik zaten mevcut olduğu için eklenemedi.", "Başarısız")
            flash("Bu bölüm zaten mevcut!", "warning")
    return redirect(url_for("poliklinikler"))


@app.route("/poliklinikler/sil", methods=["POST"])
@login_required
@modul_gerekli("poliklinik")
def poliklinik_sil():
    ad = request.form.get("ad", "")
    db.poliklinik_sil(ad)
    db.log_ekle(session.get("ad"), session.get("rol"), "POLİKLİNİK", "SİL", f"'{ad}' adlı poliklinik silindi.")
    flash("Poliklinik silindi.", "info")
    return redirect(url_for("poliklinikler"))


# ---------------------------------------------------------------------
#  RANDEVULAR
# ---------------------------------------------------------------------
@app.route("/randevular")
@login_required
@modul_gerekli("randevu")
def randevular():
    return render_template("randevular.html", randevular=db.randevulari_getir())


@app.route("/randevular/form")
@login_required
@modul_gerekli("randevu")
def randevu_form():
    return render_template("randevu_form.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir())


@app.route("/randevular/kaydet", methods=["POST"])
@login_required
@modul_gerekli("randevu")
def randevu_kaydet():
    hasta_id = request.form.get("hasta_id")
    doktor_id = request.form.get("doktor_id")
    tarih = request.form.get("tarih", "").strip()
    saat = request.form.get("saat", "").strip()
    if not (hasta_id and doktor_id and tarih and saat):
        flash("Tüm alanları doldurun!", "warning")
        return redirect(url_for("randevu_form"))
    if db.randevu_cakisma_var_mi(int(doktor_id), tarih, saat):
        db.log_ekle(session.get("ad"), session.get("rol"), "RANDEVU", "EKLE",
                    f"{tarih} {saat} için çakışma nedeniyle randevu oluşturulamadı.", "Başarısız")
        flash("Seçilen doktorun bu tarih ve saatte zaten bir randevusu var!", "danger")
        return redirect(url_for("randevu_form"))
    db.randevu_ekle(int(hasta_id), int(doktor_id), tarih, saat)
    db.log_ekle(session.get("ad"), session.get("rol"), "RANDEVU", "EKLE",
                f"{tarih} {saat} tarihine randevu oluşturuldu.")
    flash("Randevu oluşturuldu.", "success")
    return redirect(url_for("randevular"))


@app.route("/randevular/<int:rid>/durum", methods=["POST"])
@login_required
@modul_gerekli("randevu")
def randevu_durum(rid):
    durum = request.form.get("durum", "Bekliyor")
    db.randevu_durum_guncelle(rid, durum)
    db.log_ekle(session.get("ad"), session.get("rol"), "RANDEVU", "DURUM_GÜNCELLE",
                f"#{rid} numaralı randevunun durumu '{durum}' olarak güncellendi.")
    return redirect(url_for("randevular"))


@app.route("/randevular/<int:rid>/sil", methods=["POST"])
@login_required
@modul_gerekli("randevu")
def randevu_sil(rid):
    db.randevu_sil(rid)
    db.log_ekle(session.get("ad"), session.get("rol"), "RANDEVU", "SİL", f"#{rid} numaralı randevu silindi.")
    flash("Randevu silindi.", "info")
    return redirect(url_for("randevular"))


# ---------------------------------------------------------------------
#  MUAYENE / REÇETE
# ---------------------------------------------------------------------
@app.route("/muayene")
@login_required
@modul_gerekli("muayene")
def muayene():
    return render_template("muayene.html", randevular=db.bekleyen_randevulari_getir())


@app.route("/muayene/<int:rid>")
@login_required
@modul_gerekli("muayene")
def muayene_form(rid):
    randevu = db.randevu_getir_tek(rid)
    if not randevu:
        flash("Randevu bulunamadı.", "danger")
        return redirect(url_for("muayene"))
    return render_template("muayene_form.html", randevu=randevu)


@app.route("/muayene/<int:rid>/kaydet", methods=["POST"])
@login_required
@modul_gerekli("muayene")
def muayene_kaydet(rid):
    randevu = db.randevu_getir_tek(rid)
    if not randevu:
        flash("Randevu bulunamadı.", "danger")
        return redirect(url_for("muayene"))

    ilaclar, dozlar, aciklamalar = (request.form.getlist("ilac[]"), request.form.getlist("doz[]"),
                                     request.form.getlist("aciklama[]"))
    recete_listesi = [{"ilac": i, "doz": d, "aciklama": a}
                       for i, d, a in zip(ilaclar, dozlar, aciklamalar) if i.strip()]

    muayene_id = db.muayene_kaydet(rid, randevu["hasta_ad"], randevu["doktor_ad"],
                                    request.form.get("sikayet", "").strip(), request.form.get("tani", "").strip(),
                                    request.form.get("not_", "").strip(), recete_listesi)
    db.log_ekle(session.get("ad"), session.get("rol"), "MUAYENE", "EKLE",
                f"'{randevu['hasta_ad']}' hastasının muayenesi kaydedildi ({len(recete_listesi)} ilaç reçete edildi).")
    flash("Muayene ve reçete kaydedildi.", "success")
    return redirect(url_for("recete_yazdir", muayene_id=muayene_id))


@app.route("/muayene/gecmis")
@login_required
@modul_gerekli("muayene")
def muayene_gecmis():
    return render_template("muayene_gecmis.html", muayeneler=db.muayeneleri_getir())


@app.route("/recete/<int:muayene_id>/yazdir")
@login_required
@modul_gerekli("muayene")
def recete_yazdir(muayene_id):
    muayene = db.muayene_getir_tek(muayene_id)
    if not muayene:
        flash("Muayene kaydı bulunamadı.", "danger")
        return redirect(url_for("muayene"))
    receteler = db.recete_getir(muayene_id)
    return render_template("recete_yazdir.html", muayene=muayene, receteler=receteler)


@app.route("/recete/<int:muayene_id>/pdf")
@login_required
@modul_gerekli("muayene")
def recete_pdf(muayene_id):
    muayene = db.muayene_getir_tek(muayene_id)
    if not muayene:
        flash("Muayene kaydı bulunamadı.", "danger")
        return redirect(url_for("muayene"))
    receteler = db.recete_getir(muayene_id)
    html = render_template("recete_pdf.html", muayene=muayene, receteler=receteler)
    return pdf_olustur(html, f"recete_{muayene_id}.pdf")


# ---------------------------------------------------------------------
#  SERVİS / YATIŞ
# ---------------------------------------------------------------------
SERVIS_LISTESI = ["Dahiliye Servisi", "Genel Cerrahi Servisi", "Yoğun Bakım",
                   "Pediatri Servisi", "Kardiyoloji Servisi", "Ortopedi Servisi"]


@app.route("/servis")
@login_required
@modul_gerekli("servis")
def servis():
    return render_template("servis.html", yatislar=db.yatislari_getir())


@app.route("/servis/form")
@login_required
@modul_gerekli("servis")
def servis_form():
    return render_template("servis_form.html", hastalar=db.hastalari_getir(), servisler=SERVIS_LISTESI)


@app.route("/servis/kaydet", methods=["POST"])
@login_required
@modul_gerekli("servis")
def servis_kaydet():
    hasta_id = request.form.get("hasta_id")
    servis_adi = request.form.get("servis", "")
    oda = request.form.get("oda", "").strip()
    if not (hasta_id and servis_adi and oda):
        flash("Hasta, servis ve oda bilgisi zorunludur!", "warning")
        return redirect(url_for("servis_form"))
    tarih = request.form.get("yatis_tarihi", "").strip() or datetime.now().strftime("%d.%m.%Y")
    db.yatis_ekle(int(hasta_id), servis_adi, oda, request.form.get("yatak", "").strip(),
                  tarih, request.form.get("tani", "").strip())
    db.log_ekle(session.get("ad"), session.get("rol"), "SERVİS", "EKLE",
                f"Hasta '{servis_adi}' servisine yatırıldı (Oda: {oda}).")
    flash("Yatış kaydı oluşturuldu.", "success")
    return redirect(url_for("servis"))


@app.route("/servis/<int:yid>/taburcu", methods=["POST"])
@login_required
@modul_gerekli("servis")
def servis_taburcu(yid):
    db.yatis_durum_guncelle(yid, "Taburcu Oldu")
    db.log_ekle(session.get("ad"), session.get("rol"), "SERVİS", "TABURCU", f"#{yid} numaralı hasta taburcu edildi.")
    flash("Hasta taburcu edildi.", "info")
    return redirect(url_for("servis"))


@app.route("/servis/<int:yid>/sil", methods=["POST"])
@login_required
@modul_gerekli("servis")
def servis_sil(yid):
    db.yatis_sil(yid)
    db.log_ekle(session.get("ad"), session.get("rol"), "SERVİS", "SİL", f"#{yid} numaralı yatış kaydı silindi.")
    flash("Yatış kaydı silindi.", "info")
    return redirect(url_for("servis"))


@app.route("/servis/<int:yid>/ozet")
@login_required
@modul_gerekli("servis")
def servis_ozet(yid):
    yatis = db.yatis_getir_tek(yid)
    if not yatis:
        flash("Yatış kaydı bulunamadı.", "danger")
        return redirect(url_for("servis"))
    return render_template("servis_ozet.html", yatis=yatis)


@app.route("/servis/<int:yid>/ozet/pdf")
@login_required
@modul_gerekli("servis")
def servis_ozet_pdf(yid):
    yatis = db.yatis_getir_tek(yid)
    if not yatis:
        flash("Yatış kaydı bulunamadı.", "danger")
        return redirect(url_for("servis"))
    html = render_template("servis_ozet_pdf.html", yatis=yatis)
    return pdf_olustur(html, f"taburcu_ozeti_{yid}.pdf")


# ---------------------------------------------------------------------
#  AMELİYAT
# ---------------------------------------------------------------------
@app.route("/ameliyat")
@login_required
@modul_gerekli("ameliyat")
def ameliyat():
    return render_template("ameliyat.html", ameliyatlar=db.ameliyatlari_getir())


@app.route("/ameliyat/form")
@login_required
@modul_gerekli("ameliyat")
def ameliyat_form():
    return render_template("ameliyat_form.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir())


@app.route("/ameliyat/kaydet", methods=["POST"])
@login_required
@modul_gerekli("ameliyat")
def ameliyat_kaydet():
    hasta_id = request.form.get("hasta_id")
    doktor_id = request.form.get("doktor_id")
    ad = request.form.get("ameliyat_adi", "").strip()
    if not (hasta_id and doktor_id and ad):
        flash("Hasta, cerrah ve ameliyat adı zorunludur!", "warning")
        return redirect(url_for("ameliyat_form"))
    db.ameliyat_ekle(int(hasta_id), int(doktor_id), ad, request.form.get("tarih", "").strip(),
                     request.form.get("saat", "").strip(), request.form.get("salon", "").strip())
    db.log_ekle(session.get("ad"), session.get("rol"), "AMELİYAT", "EKLE", f"'{ad}' ameliyatı planlandı.")
    flash("Ameliyat planlandı.", "success")
    return redirect(url_for("ameliyat"))


@app.route("/ameliyat/<int:aid>/durum", methods=["POST"])
@login_required
@modul_gerekli("ameliyat")
def ameliyat_durum(aid):
    durum = request.form.get("durum", "Planlandı")
    db.ameliyat_durum_guncelle(aid, durum)
    db.log_ekle(session.get("ad"), session.get("rol"), "AMELİYAT", "DURUM_GÜNCELLE",
                f"#{aid} numaralı ameliyatın durumu '{durum}' olarak güncellendi.")
    return redirect(url_for("ameliyat"))


@app.route("/ameliyat/<int:aid>/sil", methods=["POST"])
@login_required
@modul_gerekli("ameliyat")
def ameliyat_sil(aid):
    db.ameliyat_sil(aid)
    db.log_ekle(session.get("ad"), session.get("rol"), "AMELİYAT", "SİL", f"#{aid} numaralı ameliyat kaydı silindi.")
    flash("Ameliyat kaydı silindi.", "info")
    return redirect(url_for("ameliyat"))


@app.route("/ameliyat/<int:aid>/rapor")
@login_required
@modul_gerekli("ameliyat")
def ameliyat_rapor(aid):
    ameliyat_kaydi = db.ameliyat_getir_tek(aid)
    if not ameliyat_kaydi:
        flash("Ameliyat kaydı bulunamadı.", "danger")
        return redirect(url_for("ameliyat"))
    return render_template("ameliyat_rapor.html", ameliyat=ameliyat_kaydi)


@app.route("/ameliyat/<int:aid>/rapor/pdf")
@login_required
@modul_gerekli("ameliyat")
def ameliyat_rapor_pdf(aid):
    ameliyat_kaydi = db.ameliyat_getir_tek(aid)
    if not ameliyat_kaydi:
        flash("Ameliyat kaydı bulunamadı.", "danger")
        return redirect(url_for("ameliyat"))
    html = render_template("ameliyat_rapor_pdf.html", ameliyat=ameliyat_kaydi)
    return pdf_olustur(html, f"ameliyat_rapor_{aid}.pdf")


# ---------------------------------------------------------------------
#  TETKİK İSTEM
# ---------------------------------------------------------------------
@app.route("/tetkik")
@login_required
@modul_gerekli("tetkik")
def tetkik():
    if not db.hastalari_getir():
        flash("Tetkik istemi oluşturmadan önce bir hasta kaydedin.", "warning")
    return render_template("tetkik.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir(),
                           goruntuleme=GORUNTULEME_LISTESI, laboratuvar=LABORATUVAR_LISTESI,
                           mreket_no=random.randint(100000, 999999), bugun=datetime.now().strftime("%d.%m.%Y"))


@app.route("/tetkik/kaydet", methods=["POST"])
@login_required
@modul_gerekli("tetkik")
def tetkik_kaydet():
    hasta_id = request.form.get("hasta_id")
    doktor_ad = request.form.get("doktor_ad", "-")
    secilenler = request.form.getlist("tetkik[]")
    if not hasta_id or not secilenler:
        flash("Lütfen hasta ve en az bir tetkik seçin!", "warning")
        return redirect(url_for("tetkik"))
    for secim in secilenler:
        kodu, ad = secim.split("::", 1)
        db.tetkik_ekle(int(hasta_id), kodu, ad, 1, "İstem Bekliyor", doktor_ad)
    db.log_ekle(session.get("ad"), session.get("rol"), "TETKİK", "EKLE",
                f"{len(secilenler)} adet tetkik istemi oluşturuldu.")
    flash(f"{len(secilenler)} adet tetkik başarıyla kaydedildi.", "success")
    return redirect(url_for("tetkik"))


@app.route("/tetkik/gecmis")
@login_required
@modul_gerekli("tetkik")
def tetkik_gecmis():
    return render_template("tetkik_gecmis.html", tetkikler=db.tetkikleri_getir())


@app.route("/tetkik/<int:tid>/sonuc", methods=["GET", "POST"])
@login_required
@modul_gerekli("tetkik")
def tetkik_sonuc(tid):
    tetkik_kaydi = db.tetkik_getir_tek(tid)
    if not tetkik_kaydi:
        flash("Tetkik kaydı bulunamadı.", "danger")
        return redirect(url_for("tetkik_gecmis"))
    if request.method == "POST":
        sonuc = request.form.get("sonuc", "").strip()
        if not sonuc:
            flash("Sonuç metni boş olamaz!", "warning")
            return redirect(url_for("tetkik_sonuc", tid=tid))
        db.tetkik_sonuc_kaydet(tid, sonuc)
        db.log_ekle(session.get("ad"), session.get("rol"), "TETKİK", "SONUÇ_GİR",
                    f"'{tetkik_kaydi['tetkik_adi']}' tetkikinin sonucu girildi.")
        flash("Tetkik sonucu kaydedildi.", "success")
        return redirect(url_for("tetkik_gecmis"))
    return render_template("tetkik_sonuc_form.html", tetkik=tetkik_kaydi)


@app.route("/tetkik/<int:tid>/rapor")
@login_required
@modul_gerekli("tetkik")
def tetkik_rapor(tid):
    tetkik_kaydi = db.tetkik_getir_tek(tid)
    if not tetkik_kaydi:
        flash("Tetkik kaydı bulunamadı.", "danger")
        return redirect(url_for("tetkik_gecmis"))
    return render_template("tetkik_rapor.html", tetkik=tetkik_kaydi)


@app.route("/tetkik/<int:tid>/rapor/pdf")
@login_required
@modul_gerekli("tetkik")
def tetkik_rapor_pdf(tid):
    tetkik_kaydi = db.tetkik_getir_tek(tid)
    if not tetkik_kaydi:
        flash("Tetkik kaydı bulunamadı.", "danger")
        return redirect(url_for("tetkik_gecmis"))
    html = render_template("tetkik_rapor_pdf.html", tetkik=tetkik_kaydi)
    return pdf_olustur(html, f"tetkik_rapor_{tid}.pdf")


# ---------------------------------------------------------------------
#  PERSONEL (SİSTEM YÖNETİCİSİ)
# ---------------------------------------------------------------------
@app.route("/personel")
@login_required
@modul_gerekli("personel")
def personel():
    return render_template("personel.html", personeller=db.personelleri_getir())


@app.route("/personel/form")
@app.route("/personel/form/<int:pid>")
@login_required
@modul_gerekli("personel")
def personel_form(pid=None):
    kisi = db.personel_getir_tek(pid) if pid else None
    return render_template("personel_form.html", kisi=kisi, poliklinikler=db.poliklinikleri_getir())


@app.route("/personel/kaydet", methods=["POST"])
@login_required
@modul_gerekli("personel")
def personel_kaydet():
    from werkzeug.security import generate_password_hash

    pid = request.form.get("id")
    ad = request.form.get("ad_soyad", "").strip()
    kadi = request.form.get("kullanici_adi", "").strip()
    if not ad or not request.form.get("rol") or not kadi:
        flash("Adı Soyadı, Rol ve Kullanıcı Adı zorunludur!", "warning")
        return redirect(url_for("personel_form", pid=pid) if pid else url_for("personel_form"))

    v = {
        "ad_soyad": ad, "rol": request.form.get("rol"), "birim": request.form.get("birim", ""),
        "telefon": request.form.get("telefon", "").strip(), "kullanici_adi": kadi,
        "durum": request.form.get("durum", "Aktif"),
    }
    yeni_sifre = request.form.get("sifre", "").strip()

    try:
        if pid:
            mevcut = db.personel_getir_tek(int(pid))
            v["sifre"] = generate_password_hash(yeni_sifre) if yeni_sifre else mevcut["sifre"]
            db.personel_guncelle(int(pid), v)
            db.log_ekle(session.get("ad"), session.get("rol"), "PERSONEL", "GÜNCELLE",
                        f"'{ad}' ({kadi}) personel bilgileri güncellendi.")
            flash("Personel bilgileri güncellendi.", "success")
        else:
            v["sifre"] = yeni_sifre or "1234"
            db.personel_ekle(v)
            db.log_ekle(session.get("ad"), session.get("rol"), "PERSONEL", "EKLE",
                        f"'{ad}' ({kadi}) rolü '{v['rol']}' olarak eklendi.")
            flash("Yeni personel başarıyla kaydedildi.", "success")
    except Exception:
        db.log_ekle(session.get("ad"), session.get("rol"), "PERSONEL", "EKLE",
                    f"'{kadi}' kullanıcı adı zaten mevcut olduğu için işlem başarısız oldu.", "Başarısız")
        flash("Bu kullanıcı adı zaten kullanılıyor!", "danger")
        return redirect(url_for("personel_form", pid=pid) if pid else url_for("personel_form"))
    return redirect(url_for("personel"))


@app.route("/personel/<int:pid>/sil", methods=["POST"])
@login_required
@modul_gerekli("personel")
def personel_sil(pid):
    kisi = db.personel_getir_tek(pid)
    db.personel_sil(pid)
    db.log_ekle(session.get("ad"), session.get("rol"), "PERSONEL", "SİL",
                f"'{kisi['ad_soyad'] if kisi else pid}' personel kaydı silindi.")
    flash("Personel kaydı silindi.", "info")
    return redirect(url_for("personel"))


# ---------------------------------------------------------------------
#  LOG PANELİ (SADECE YÖNETİCİ)
# ---------------------------------------------------------------------
@app.route("/loglar")
@login_required
@modul_gerekli("log")
def loglar():
    kategori = request.args.get("kategori", "").strip()
    kullanici = request.args.get("kullanici", "").strip()
    sonuc = request.args.get("sonuc", "").strip()
    return render_template("loglar.html",
                           loglar=db.loglari_getir(kategori or None, kullanici or None, sonuc or None),
                           kategoriler=db.log_kategorileri_getir(),
                           kategori=kategori, kullanici=kullanici, sonuc=sonuc)


@app.route("/loglar/disa-aktar")
@login_required
@modul_gerekli("log")
def loglar_disa_aktar():
    kategori = request.args.get("kategori", "").strip()
    kullanici = request.args.get("kullanici", "").strip()
    sonuc = request.args.get("sonuc", "").strip()
    kayitlar = db.loglari_getir(kategori or None, kullanici or None, sonuc or None)
    satirlar = [[l["tarih"], l["kullanici_adi"], l["rol"], l["kategori"], l["islem"], l["aciklama"], l["sonuc"]]
                for l in kayitlar]
    return csv_indir(satirlar, ["Tarih", "Kullanıcı", "Rol", "Kategori", "İşlem", "Açıklama", "Sonuç"], "loglar.csv")


if __name__ == "__main__":
    app.run(debug=True)