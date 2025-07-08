
import pandas as pd
from sklearn.metrics import accuracy_score

# Règles enrichies précédemment testées
def regle_1(ligne):
    return (
        ligne["luminosite"] > 115
        and ligne["densite_contours"] < 0.12
        and ligne["taille_par_contours"] > 0.0015
        and ligne["ecart_type_gris"] < 65
    )

def regle_2(ligne):
    return (
        ligne["moyenne_R"] > 120
        and ligne["contraste"] < 160
        and ligne["ecart_type_histogramme"] < 0.005
    )

def regle_3(ligne):
    return (
        ligne["moyenne_B"] > 100
        and ligne["moyenne_V"] > 100
        and ligne["luminosite"] > 100
        and ligne["taille_fichier_Ko"] < 150
    )

def regle_4(ligne):
    return (
        ligne["largeur"] >= 200
        and ligne["hauteur"] >= 200
        and ligne["contraste"] > 30
        and ligne["ecart_type_histogramme"] < 0.01
    )

def classer(ligne):
    votes = sum([
        regle_1(ligne),
        regle_2(ligne),
        regle_3(ligne),
        regle_4(ligne)
    ])
    return "clean" if votes >= 2 else "dirty"

if __name__ == "__main__":
    df = pd.read_csv("resultats.csv")
    df["prediction"] = df.apply(classer, axis=1)

    print("✅ Prédictions effectuées avec succès sur", len(df), "images.")

    if "etiquette_reelle" in df.columns:
        df["correct"] = df["prediction"] == df["etiquette_reelle"]
        precision = accuracy_score(df["etiquette_reelle"], df["prediction"]) * 100
        print(f"🎯 Précision (avec évaluation) : {precision:.2f} %")

        erreurs = df[~df["correct"]]
        if not erreurs.empty:
            print("\n❌ Images mal classées :")
            for _, ligne in erreurs.iterrows():
                print(f" - {ligne['nom_fichier']} | Réelle : {ligne['etiquette_reelle']} | Prédit : {ligne['prediction']}")
        else:
            print("✅ Aucune erreur de classification")

    df.to_csv("resultats_avec_predictions_final.csv", index=False)
    print("💾 Fichier sauvegardé : resultats_avec_predictions_final.csv")
