from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
import os
from extractor import traiter_et_enregistrer_image
import traceback
from datetime import datetime
import sqlite3


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates'))

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
            return render_template("upload_template.html", erreur="Aucun fichier reçu.")

        file = request.files["image"]
        if file.filename == "":
            return render_template("upload_template.html", erreur="Nom de fichier vide.")

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

    return render_template("upload_template.html",
                           uploaded_image=last_uploaded_image,
                           prediction=last_prediction)

@app.route("/corriger_prediction", methods=["POST"])
def corriger_prediction():
    filename = request.form["filename"]
    new_prediction = request.form["new_prediction"]

    db_path = os.path.abspath(os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db"))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("UPDATE images SET prediction = ? WHERE nom_fichier = ?", (new_prediction, filename))
    conn.commit()
    conn.close()

    return redirect(url_for("upload_image"))


@app.route("/")
def index():
    return render_template("index.html")

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

    return render_template("images.html", images=images)


@app.route("/dashboard")
def dashboard():
    db_path = os.path.join(BASE_DIR, "..", "database", "TrashUP_images.db")
    total = dirty = clean = 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT prediction FROM images")
        all_predictions = cursor.fetchall()

        for (pred,) in all_predictions:
            if pred == "dirty":
                dirty += 1
            elif pred == "clean":
                clean += 1
        total = len(all_predictions)
        conn.close()
    except Exception as e:
        return f"<pre>Erreur : {e}</pre>", 500

    return render_template("dashboard.html", total=total, dirty=dirty, clean=clean)

@app.route("/map")
def map_view():
    return render_template("map.html")

@app.route("/about")
def about():
    return render_template("AboutUs.html")

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    @app.errorhandler(500)
    def handle_500_error(e):
        return f"<pre>{traceback.format_exc()}</pre>", 500

    app.run(debug=True)

