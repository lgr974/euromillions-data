import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 🔄 Corriger les formats de date dans le DataFrame
def corriger_dates_dataframe(df):
    def corriger(date):
        try:
            return datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except:
            try:
                return datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                return date
    df["date_de_tirage"] = df["date_de_tirage"].astype(str).apply(corriger)
    return df

# 📥 Récupérer le dernier tirage depuis le site
def fetch_latest_draw():
    url = "https://tirage-gagnant.com/euromillions/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Recherche du bon bloc contenant la date
    date_text = None
    for h3 in soup.find_all("h3"):
        text = h3.get_text(strip=True).lower()
        if "tirage euromillions du" in text:
            date_text = text.replace("tirage euromillions du ", "")
            break

    if not date_text:
        raise ValueError("❌ Impossible de trouver la date du dernier tirage.")

    # Formatage de la date en français
    try:
        draw_date = datetime.strptime(date_text, "%A %d %B %Y")
    except ValueError:
        try:
            draw_date = datetime.strptime(date_text, "%d %B %Y")
        except ValueError:
            raise ValueError(f"❌ Format de date non reconnu : '{date_text}'")

    # Récupération des 5 numéros
    numbers = [p.text.strip() for p in soup.select("p.num_v2")]
    if len(numbers) != 5:
        raise ValueError(f"❌ 5 numéros attendus, trouvés : {len(numbers)}")

    # Récupération des 2 étoiles
    stars = [p.text.strip() for p in soup.select("p.num_etoile")]
    if len(stars) != 2:
        raise ValueError(f"❌ 2 étoiles attendues, trouvées : {len(stars)}")

    return {
        "date_de_tirage": draw_date.strftime("%Y-%m-%d"),
        "boule_1": int(numbers[0]),
        "boule_2": int(numbers[1]),
        "boule_3": int(numbers[2]),
        "boule_4": int(numbers[3]),
        "boule_5": int(numbers[4]),
        "etoile_1": int(stars[0]),
        "etoile_2": int(stars[1]),
    }


    # 🔢 Numéros
    numbers = [p.text.strip() for p in soup.select("p.num_v2")]
    if len(numbers) != 5:
        raise ValueError(f"❌ 5 numéros attendus, trouvés : {len(numbers)}")

    # ✨ Étoiles
    stars = [p.text.strip() for p in soup.select("p.etoile_v2")]
    if len(stars) != 2:
        raise ValueError(f"❌ 2 étoiles attendues, trouvées : {len(stars)}")

    return {
        "date_de_tirage": draw_date_str,
        "boule_1": int(numbers[0]),
        "boule_2": int(numbers[1]),
        "boule_3": int(numbers[2]),
        "boule_4": int(numbers[3]),
        "boule_5": int(numbers[4]),
        "etoile_1": int(stars[0]),
        "etoile_2": int(stars[1])
    }

# 🔄 Mettre à jour le fichier CSV
def update_csv(file_path="euromillions_merged.csv", force=False):
    draw = fetch_latest_draw()

    try:
        df_old = pd.read_csv(file_path)
        df_old = corriger_dates_dataframe(df_old)
    except FileNotFoundError:
        df_old = pd.DataFrame()

    # Si déjà présent (et non forcé), on ne fait rien
    if not force and not df_old.empty and draw["date_de_tirage"] in df_old["date_de_tirage"].values:
        print("✅ Tirage déjà présent :", draw["date_de_tirage"])
        return

    # Ajouter le tirage
    df_new = pd.DataFrame([draw])
    df_final = pd.concat([df_old, df_new], ignore_index=True)

    # Re-corriger les dates (par précaution)
    df_final = corriger_dates_dataframe(df_final)

    # Réordonner par date
    df_final["date_de_tirage"] = pd.to_datetime(df_final["date_de_tirage"])
    df_final = df_final.sort_values("date_de_tirage", ascending=True)
    df_final["date_de_tirage"] = df_final["date_de_tirage"].dt.strftime("%Y-%m-%d")

    # Sauvegarde
    df_final.to_csv(file_path, index=False)
    print("✅ Fichier mis à jour :", file_path)

# ⬇️ Exécution
if __name__ == "__main__":
    update_csv("euromillions_merged.csv")
