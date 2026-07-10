import os
import random
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash

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


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("rol") != "Yönetici":
            flash("Bu sayfa için yetkiniz bulunmuyor.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"simdi": datetime.now().strftime("%d.%m.%Y %H:%M")}


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
            flash(f"Hoş geldiniz, {kullanici['ad_soyad']}.", "success")
            return redirect(url_for("dashboard"))
        flash("Kullanıcı adı veya şifre hatalı!", "danger")
    return render_template("login.html")


@app.route("/cikis")
def logout():
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
    return render_template("dashboard.html", toplam_hasta=toplam_hasta, bugunku_randevu=bugunku_randevu,
                           yatan_hasta=yatan_hasta, bekleyen_randevu=bekleyen_randevu)


# ---------------------------------------------------------------------
#  HASTA KAYIT
# ---------------------------------------------------------------------
@app.route("/hastalar")
@login_required
def hastalar():
    q = request.args.get("q", "").strip()
    return render_template("hastalar.html", hastalar=db.hastalari_getir(q), q=q)


@app.route("/hastalar/form")
@app.route("/hastalar/form/<int:hid>")
@login_required
def hasta_form(hid=None):
    hasta = db.hasta_getir_tek(hid) if hid else None
    return render_template("hasta_form.html", hasta=hasta)


@app.route("/hastalar/kaydet", methods=["POST"])
@login_required
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
        flash("Hasta bilgileri güncellendi.", "success")
    else:
        v["kayit_tarihi"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        db.hasta_ekle(v)
        flash("Yeni hasta başarıyla kaydedildi.", "success")
    return redirect(url_for("hastalar"))


@app.route("/hastalar/<int:hid>/sil", methods=["POST"])
@login_required
def hasta_sil(hid):
    db.hasta_sil(hid)
    flash("Hasta kaydı silindi.", "info")
    return redirect(url_for("hastalar"))


# ---------------------------------------------------------------------
#  DOKTORLAR
# ---------------------------------------------------------------------
@app.route("/doktorlar")
@login_required
def doktorlar():
    return render_template("doktorlar.html", doktorlar=db.doktorlari_getir())


@app.route("/doktorlar/form")
@app.route("/doktorlar/form/<int:did>")
@login_required
def doktor_form(did=None):
    doktor = db.doktor_getir_tek(did) if did else None
    return render_template("doktor_form.html", doktor=doktor, poliklinikler=db.poliklinikleri_getir())


@app.route("/doktorlar/kaydet", methods=["POST"])
@login_required
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
        flash("Doktor bilgileri güncellendi.", "success")
    else:
        db.doktor_ekle(v)
        flash("Yeni doktor eklendi.", "success")
    return redirect(url_for("doktorlar"))


@app.route("/doktorlar/<int:did>/sil", methods=["POST"])
@login_required
def doktor_sil(did):
    db.doktor_sil(did)
    flash("Doktor kaydı silindi.", "info")
    return redirect(url_for("doktorlar"))


# ---------------------------------------------------------------------
#  POLİKLİNİKLER
# ---------------------------------------------------------------------
@app.route("/poliklinikler")
@login_required
def poliklinikler():
    return render_template("poliklinikler.html", poliklinikler=db.poliklinikleri_getir())


@app.route("/poliklinikler/ekle", methods=["POST"])
@login_required
def poliklinik_ekle():
    ad = request.form.get("ad", "").strip()
    if not ad:
        flash("Bölüm adı boş olamaz!", "warning")
    else:
        try:
            db.poliklinik_ekle(ad)
            flash("Poliklinik eklendi.", "success")
        except Exception:
            flash("Bu bölüm zaten mevcut!", "warning")
    return redirect(url_for("poliklinikler"))


@app.route("/poliklinikler/sil", methods=["POST"])
@login_required
def poliklinik_sil():
    db.poliklinik_sil(request.form.get("ad", ""))
    flash("Poliklinik silindi.", "info")
    return redirect(url_for("poliklinikler"))


# ---------------------------------------------------------------------
#  RANDEVULAR
# ---------------------------------------------------------------------
@app.route("/randevular")
@login_required
def randevular():
    return render_template("randevular.html", randevular=db.randevulari_getir())


@app.route("/randevular/form")
@login_required
def randevu_form():
    return render_template("randevu_form.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir())


@app.route("/randevular/kaydet", methods=["POST"])
@login_required
def randevu_kaydet():
    hasta_id = request.form.get("hasta_id")
    doktor_id = request.form.get("doktor_id")
    tarih = request.form.get("tarih", "").strip()
    saat = request.form.get("saat", "").strip()
    if not (hasta_id and doktor_id and tarih and saat):
        flash("Tüm alanları doldurun!", "warning")
        return redirect(url_for("randevu_form"))
    db.randevu_ekle(int(hasta_id), int(doktor_id), tarih, saat)
    flash("Randevu oluşturuldu.", "success")
    return redirect(url_for("randevular"))


@app.route("/randevular/<int:rid>/durum", methods=["POST"])
@login_required
def randevu_durum(rid):
    db.randevu_durum_guncelle(rid, request.form.get("durum", "Bekliyor"))
    return redirect(url_for("randevular"))


@app.route("/randevular/<int:rid>/sil", methods=["POST"])
@login_required
def randevu_sil(rid):
    db.randevu_sil(rid)
    flash("Randevu silindi.", "info")
    return redirect(url_for("randevular"))


# ---------------------------------------------------------------------
#  MUAYENE / REÇETE
# ---------------------------------------------------------------------
@app.route("/muayene")
@login_required
def muayene():
    return render_template("muayene.html", randevular=db.bekleyen_randevulari_getir())


@app.route("/muayene/<int:rid>")
@login_required
def muayene_form(rid):
    randevu = db.randevu_getir_tek(rid)
    if not randevu:
        flash("Randevu bulunamadı.", "danger")
        return redirect(url_for("muayene"))
    return render_template("muayene_form.html", randevu=randevu)


@app.route("/muayene/<int:rid>/kaydet", methods=["POST"])
@login_required
def muayene_kaydet(rid):
    randevu = db.randevu_getir_tek(rid)
    if not randevu:
        flash("Randevu bulunamadı.", "danger")
        return redirect(url_for("muayene"))

    ilaclar, dozlar, aciklamalar = (request.form.getlist("ilac[]"), request.form.getlist("doz[]"),
                                     request.form.getlist("aciklama[]"))
    recete_listesi = [{"ilac": i, "doz": d, "aciklama": a}
                       for i, d, a in zip(ilaclar, dozlar, aciklamalar) if i.strip()]

    db.muayene_kaydet(rid, randevu["hasta_ad"], randevu["doktor_ad"],
                      request.form.get("sikayet", "").strip(), request.form.get("tani", "").strip(),
                      request.form.get("not_", "").strip(), recete_listesi)
    flash("Muayene ve reçete kaydedildi.", "success")
    return redirect(url_for("muayene"))


# ---------------------------------------------------------------------
#  SERVİS / YATIŞ
# ---------------------------------------------------------------------
SERVIS_LISTESI = ["Dahiliye Servisi", "Genel Cerrahi Servisi", "Yoğun Bakım",
                   "Pediatri Servisi", "Kardiyoloji Servisi", "Ortopedi Servisi"]


@app.route("/servis")
@login_required
def servis():
    return render_template("servis.html", yatislar=db.yatislari_getir())


@app.route("/servis/form")
@login_required
def servis_form():
    return render_template("servis_form.html", hastalar=db.hastalari_getir(), servisler=SERVIS_LISTESI)


@app.route("/servis/kaydet", methods=["POST"])
@login_required
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
    flash("Yatış kaydı oluşturuldu.", "success")
    return redirect(url_for("servis"))


@app.route("/servis/<int:yid>/taburcu", methods=["POST"])
@login_required
def servis_taburcu(yid):
    db.yatis_durum_guncelle(yid, "Taburcu Oldu")
    flash("Hasta taburcu edildi.", "info")
    return redirect(url_for("servis"))


@app.route("/servis/<int:yid>/sil", methods=["POST"])
@login_required
def servis_sil(yid):
    db.yatis_sil(yid)
    flash("Yatış kaydı silindi.", "info")
    return redirect(url_for("servis"))


# ---------------------------------------------------------------------
#  AMELİYAT
# ---------------------------------------------------------------------
@app.route("/ameliyat")
@login_required
def ameliyat():
    return render_template("ameliyat.html", ameliyatlar=db.ameliyatlari_getir())


@app.route("/ameliyat/form")
@login_required
def ameliyat_form():
    return render_template("ameliyat_form.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir())


@app.route("/ameliyat/kaydet", methods=["POST"])
@login_required
def ameliyat_kaydet():
    hasta_id = request.form.get("hasta_id")
    doktor_id = request.form.get("doktor_id")
    ad = request.form.get("ameliyat_adi", "").strip()
    if not (hasta_id and doktor_id and ad):
        flash("Hasta, cerrah ve ameliyat adı zorunludur!", "warning")
        return redirect(url_for("ameliyat_form"))
    db.ameliyat_ekle(int(hasta_id), int(doktor_id), ad, request.form.get("tarih", "").strip(),
                     request.form.get("saat", "").strip(), request.form.get("salon", "").strip())
    flash("Ameliyat planlandı.", "success")
    return redirect(url_for("ameliyat"))


@app.route("/ameliyat/<int:aid>/durum", methods=["POST"])
@login_required
def ameliyat_durum(aid):
    db.ameliyat_durum_guncelle(aid, request.form.get("durum", "Planlandı"))
    return redirect(url_for("ameliyat"))


@app.route("/ameliyat/<int:aid>/sil", methods=["POST"])
@login_required
def ameliyat_sil(aid):
    db.ameliyat_sil(aid)
    flash("Ameliyat kaydı silindi.", "info")
    return redirect(url_for("ameliyat"))


# ---------------------------------------------------------------------
#  TETKİK İSTEM
# ---------------------------------------------------------------------
@app.route("/tetkik")
@login_required
def tetkik():
    if not db.hastalari_getir():
        flash("Tetkik istemi oluşturmadan önce bir hasta kaydedin.", "warning")
    return render_template("tetkik.html", hastalar=db.hastalari_getir(), doktorlar=db.doktorlari_getir(),
                           goruntuleme=GORUNTULEME_LISTESI, laboratuvar=LABORATUVAR_LISTESI,
                           mreket_no=random.randint(100000, 999999), bugun=datetime.now().strftime("%d.%m.%Y"))


@app.route("/tetkik/kaydet", methods=["POST"])
@login_required
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
    flash(f"{len(secilenler)} adet tetkik başarıyla kaydedildi.", "success")
    return redirect(url_for("tetkik"))


@app.route("/tetkik/gecmis")
@login_required
def tetkik_gecmis():
    return render_template("tetkik_gecmis.html", tetkikler=db.tetkikleri_getir())


# ---------------------------------------------------------------------
#  PERSONEL (SİSTEM YÖNETİCİSİ)
# ---------------------------------------------------------------------
@app.route("/personel")
@login_required
@admin_required
def personel():
    return render_template("personel.html", personeller=db.personelleri_getir())


@app.route("/personel/form")
@app.route("/personel/form/<int:pid>")
@login_required
@admin_required
def personel_form(pid=None):
    kisi = db.personel_getir_tek(pid) if pid else None
    return render_template("personel_form.html", kisi=kisi, poliklinikler=db.poliklinikleri_getir())


@app.route("/personel/kaydet", methods=["POST"])
@login_required
@admin_required
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
            flash("Personel bilgileri güncellendi.", "success")
        else:
            v["sifre"] = yeni_sifre or "1234"
            db.personel_ekle(v)
            flash("Yeni personel başarıyla kaydedildi.", "success")
    except Exception:
        flash("Bu kullanıcı adı zaten kullanılıyor!", "danger")
        return redirect(url_for("personel_form", pid=pid) if pid else url_for("personel_form"))
    return redirect(url_for("personel"))


@app.route("/personel/<int:pid>/sil", methods=["POST"])
@login_required
@admin_required
def personel_sil(pid):
    db.personel_sil(pid)
    flash("Personel kaydı silindi.", "info")
    return redirect(url_for("personel"))


if __name__ == "__main__":
    app.run(debug=True)