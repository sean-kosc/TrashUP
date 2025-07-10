from flask import Flask, request, render_template, redirect, url_for, session
from werkzeug.utils import secure_filename
import os
from extractor import traiter_et_enregistrer_image
import traceback
from datetime import datetime
import sqlite3
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = "change_this_secret_key"

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

last_uploaded_image = None
last_prediction = None

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    global last_uploaded_image, last_prediction

    if request.method == "POST":
        if "image" not in request.files:
            return render_template(get_template_name("upload_template.html"), erreur="Aucun fichier reçu.")

        file = request.files["image"]
        if file.filename == "":
            return render_template(get_template_name("upload_template.html"), erreur="Nom de fichier vide.")

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            chemin_image = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            file.save(chemin_image)

            localisation = request.form.get("localisation")
            latitude = request.form.get("latitude") or None
            longitude = request.form.get("longitude") or None

            latitude = float(latitude) if latitude else None
            longitude = float(longitude) if longitude else None

            try:
                prediction = traiter_et_enregistrer_image(
                    chemin_image, filename, localisation, latitude, longitude
                )
                last_uploaded_image = filename
                last_prediction = prediction
            except Exception as e:
                return f"<pre>Erreur : {e}\n\n{traceback.format_exc()}</pre>", 500

    return render_template(get_template_name("upload_template.html"),
                           uploaded_image=last_uploaded_image,
                           prediction=last_prediction)

@app.route("/corriger_prediction", methods=["POST"])
def corriger_prediction():
    filename = request.form["filename"]
    new_prediction = request.form["new_prediction"]

    db_path = os.path.abspath(os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db"))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("UPDATE images SET prediction = ?, correction = 1 WHERE nom_fichier = ?", (new_prediction, filename))
    conn.commit()
    conn.close()

    return redirect(url_for("upload_image"))


@app.route("/")
def index():
    return render_template(get_template_name("index.html"))

@app.route("/images")
def images():
    db_path = os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db")
    images = []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT nom_fichier, date_upload, prediction, localisation, 
                   taille_fichier_Ko, largeur, hauteur, 
                   moyenne_R, moyenne_V, moyenne_B,
                   luminosite, contraste, densite_contours
            FROM images
        """)
        rows = cursor.fetchall()

        for row in rows:
            (nom_fichier, date_upload, prediction, localisation,
             taille_ko, largeur, hauteur,
             moyenne_r, moyenne_v, moyenne_b,
             luminosite, contraste, densite_contours) = row

            if prediction == "dirty":
                pred_label = "pleine"
            elif prediction == "clean":
                pred_label = "vide"
            else:
                pred_label = "inconnue"

            try:
                date_obj = datetime.strptime(date_upload, "%Y-%m-%dT%H:%M:%S.%f")
            except Exception:
                date_obj = None

            images.append({
                "filename": nom_fichier,
                "date": date_obj,
                "prediction": pred_label,
                "localisation": localisation,
                "taille_fichier_Ko": round(float(taille_ko), 2) if taille_ko and isinstance(taille_ko, (int, float)) else 0,
                "largeur": int(largeur) if largeur else 0,
                "hauteur": int(hauteur) if hauteur else 0,
                "moyenne_R": int(moyenne_r) if moyenne_r else 0,
                "moyenne_V": int(moyenne_v) if moyenne_v else 0,
                "moyenne_B": int(moyenne_b) if moyenne_b else 0,
                "luminosite": round(float(luminosite), 1) if isinstance(luminosite, (int, float)) else 0,
                "contraste": round(float(contraste), 2) if isinstance(contraste, (int, float)) else 0,
                "densite_contours": round(float(densite_contours), 4) if isinstance(densite_contours, (int, float)) else 0
            })

        conn.close()
    except Exception as e:
        return f"<pre>Erreur de lecture de la base : {e}</pre>", 500

    return render_template(get_template_name("images.html"), images=images)

@app.route("/delete_image", methods=["POST"])
def delete_image():
    filename = request.form.get("filename")
    if not filename:
        return redirect("/images")

    try:
        # Supprimer l'entrée de la base
        db_path = os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images WHERE nom_fichier = ?", (filename,))
        conn.commit()
        conn.close()

        # Supprimer le fichier du dossier
        filepath = os.path.join(app.static_folder, "uploads", filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        return redirect("/images")

    except Exception as e:
        return f"<pre>Erreur lors de la suppression : {e}</pre>", 500
    

@app.route("/dashboard")
def dashboard():
    db_path = os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT prediction, date_upload, localisation, moyenne_R, moyenne_V, moyenne_B, luminosite, contraste, densite_contours, correction FROM images")
        rows = cursor.fetchall()

        total = len(rows)
        dirty = sum(1 for r in rows if r[0] == "dirty")
        clean = sum(1 for r in rows if r[0] == "clean")
        corrected = sum(1 for r in rows if r[-1] == 1)

        histogram_data = defaultdict(int)
        localisation_counter = Counter()

        for row in rows:
            pred, date_str, loc, *_ = row
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
            except:
                continue
            day_key = date_obj.strftime("%Y-%m-%d")
            histogram_data[day_key] += 1
            localisation_counter[loc] += 1

        # Dernières images avec infos complètes
        cursor.execute("""
        SELECT nom_fichier, date_upload, localisation, prediction
        FROM images
        ORDER BY date_upload DESC
        LIMIT 5
        """)
        latest = cursor.fetchall()
        latest_images = []
        for row in latest:
            try:
                formatted_date = datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%f").strftime("%d/%m/%Y - %H:%M")
            except:
                formatted_date = "-"
            latest_images.append({
                "filename": row[0],
                "date": formatted_date,
                "localisation": row[2] or "-",
                "prediction": row[3] or "unknown"
            })

        conn.close()

        return render_template(get_template_name("dashboard.html"),
                               total=total,
                               dirty=dirty,
                               clean=clean,
                               corrected=corrected,
                               histogram_data=dict(histogram_data),
                               latest_images=latest_images,
                               localisation_counter=dict(localisation_counter))

    except Exception as e:
        return f"<pre>Erreur : {e}</pre>", 500



@app.route("/map")
def map_view():
    return render_template(get_template_name("map.html"))

@app.route("/api/locations")
def get_locations():
    db_path = os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT nom_fichier, localisation, latitude, longitude, prediction FROM images WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        results = cursor.fetchall()
        conn.close()

        locations = []
        for filename, localisation, lat, lon, prediction in results:
            locations.append({
                "filename": filename,
                "localisation": localisation,
                "latitude": float(lat),
                "longitude": float(lon),
                "prediction": prediction
            })

        return {"status": "ok", "data": locations}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route("/about")
def about():
    return render_template(get_template_name("AboutUs.html"))

# Utilitaire pour choisir le template selon la langue
def get_template_name(base_name):
    lang = session.get('lang', 'fr')
    if lang == 'en':
        # Toujours utiliser le slash pour les templates Flask/Jinja
        en_path = f'en/{base_name}'
        if os.path.exists(os.path.join(app.template_folder, 'en', base_name)):
            return en_path
    return base_name

# Route pour changer la langue
@app.route("/switch_lang/<lang>")
def switch_lang(lang):
    session['lang'] = lang
    next_page = request.args.get("next") or "/"
    return redirect(next_page)

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    @app.errorhandler(500)
    def handle_500_error(e):
        return f"<pre>{traceback.format_exc()}</pre>", 500

    app.run(debug=True)