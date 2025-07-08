import os
import cv2
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from tqdm import tqdm
from classifier import classer

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, '../database/TrashUP_images.db')


def extraire_caracteristiques(chemin_image):
    image = cv2.imread(chemin_image)
    image_redimensionnee = cv2.resize(image, (256, 256))
    gris = cv2.cvtColor(image_redimensionnee, cv2.COLOR_BGR2GRAY)

    taille_ko = os.path.getsize(chemin_image) / 1024
    hauteur, largeur = image.shape[:2]
    moyenne_couleur = cv2.mean(image)[:3]
    histo_gris = cv2.calcHist([gris], [0], None, [256], [0, 256]).flatten()
    histo_gris = histo_gris / np.sum(histo_gris)
    ecart_type_histogramme = np.std(histo_gris)
    contraste = np.max(gris) - np.min(gris)
    contours_detectes = cv2.Canny(gris, 100, 200)
    densite_contours = np.sum(contours_detectes > 0) / contours_detectes.size
    contours, _ = cv2.findContours(contours_detectes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    aires = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 0]
    taille_moyenne_par_contour = np.mean(aires) / contours_detectes.size if aires else 0

    return {
        "taille_fichier_Ko": taille_ko,
        "largeur": largeur,
        "hauteur": hauteur,
        "moyenne_R": moyenne_couleur[2],
        "moyenne_V": moyenne_couleur[1],
        "moyenne_B": moyenne_couleur[0],
        "luminosite": np.mean(gris),
        "ecart_type_gris": np.std(gris),
        "contraste": contraste,
        "ecart_type_histogramme": ecart_type_histogramme,
        "densite_contours": densite_contours,
        "taille_par_contours": taille_moyenne_par_contour
    }


def enregistrer_dans_bdd(nom_fichier, chemin, localisation, latitude, longitude, features, prediction):
    import sqlite3
    from datetime import datetime

    print("Connexion à la base :", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO images (
            nom_fichier, chemin, date_upload, localisation, latitude, longitude,
            taille_fichier_Ko, largeur, hauteur, moyenne_R, moyenne_V, moyenne_B,
            luminosite, ecart_type_gris, contraste, ecart_type_histogramme,
            densite_contours, taille_par_contours, prediction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nom_fichier, chemin, datetime.now().isoformat(), localisation, latitude, longitude,
        features["taille_fichier_Ko"],
        features["largeur"],
        features["hauteur"],
        features["moyenne_R"],
        features["moyenne_V"],
        features["moyenne_B"],
        features["luminosite"],
        features["ecart_type_gris"],
        features["contraste"],
        features["ecart_type_histogramme"],
        features["densite_contours"],
        features["taille_par_contours"],
        prediction
    ))
    conn.commit()
    conn.close()



def traiter_et_enregistrer_image(chemin_image, nom_fichier, localisation, latitude, longitude):
    features = extraire_caracteristiques(chemin_image)
    prediction = classer(features)
    enregistrer_dans_bdd(nom_fichier, chemin_image, localisation, latitude, longitude, features, prediction)
    return prediction
