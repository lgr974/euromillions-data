import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import locale

# 🗓️ Utiliser la locale française pour lire les dates en français
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    print("⚠️ Locale fr_FR.UTF-8 non disponible, tentative avec fr_FR")
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except locale.Error:
        print("❌ Locale française non disponible sur ce système.")
        exit(1)

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
    if "date_de_tirage" in df.columns:
        df["date_de_tirage"] = df["date_de_tirage"].astype(str).apply(corriger)
    return df

# 📥 Récupérer le dernier tirage depuis le site
def fetch_latest_draw():
    url = "https://tirage-gagnant.com/euromillions/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # 1. Date dans <span class="date_full">
    date_span = soup.find("span", class_="date_full")
    if not date_span:
        raise ValueError("❌ Impossible de trouver la date du tirage.")
    
    date_str = date_span.text.strip()

    try:
        draw_date = datetime.strptime(date_str, "%A %d %B %Y")
    except ValueError as e:
        raise ValueError(f"❌ Erreur de format de date : {date_str}") from e

    # 2. Numéros dans <p class="num_v2">
    numbers_tags = soup.find_all("p", class_="num_v2")
    if len(numbers_tags) < 5:
        raise ValueError("❌ Moins de 5 numéros trouvés.")
    
    numbers = [int(tag.text.strip()) for tag in numbers_tags[:5]]

    # 3. Étoiles dans <span class="etoile-num">
    stars_tags = soup.find_all("span", class_="etoile-num")
    if len(stars_tags) < 2:
        raise ValueError("❌ Moins de 2 étoiles trouvées.")
    
    stars = [int(tag.text.strip()) for tag in stars_tags[:2]]

    return {
        "date_de_tirage": draw_date.strftime("%Y-%m-%d"),
        "boule_1": numbers[0],
        "boule_2": numbers[1],
        "boule_3": numbers[2],
        "boule_4": numbers[3],
        "boule_5": numbers[4],
        "etoile_1": stars[0],
        "etoile_2": stars[1],
    }

# 🔄 Mettre à jour le fichier CSV
def update_csv(file_path="euromillions_merged.csv", force=False):
    draw = fetch_latest_draw()

    try:
        df_old = pd.read_csv(file_path, sep="\t")
        if "date_de_tirage" not in df_old.columns:
            print("⚠️ La colonne 'date_de_tirage' est absente. Recréation du fichier.")
            df_old = pd.DataFrame()
        else:
            df_old = corriger_dates_dataframe(df_old)
    except FileNotFoundError:
        df_old = pd.DataFrame()

    # Vérifie si le tirage est déjà présent
    if not force and not df_old.empty and draw["date_de_tirage"] in df_old["date_de_tirage"].values:
        print("✅ Tirage déjà présent :", draw["date_de_tirage"])
        return

    # Ajouter le nouveau tirage
    df_new = pd.DataFrame([draw])
    df_final = pd.concat([df_old, df_new], ignore_index=True)

    # Nettoyage et tri
    df_final = corriger_dates_dataframe(df_final)
    df_final["date_de_tirage"] = pd.to_datetime(df_final["date_de_tirage"])
    df_final = df_final.sort_values("date_de_tirage", ascending=True)
    df_final["date_de_tirage"] = df_final["date_de_tirage"].dt.strftime("%Y-%m-%d")

    # Sauvegarde du fichier CSV
    df_final.to_csv(file_path, index=False, sep="\t")
    print("✅ Fichier mis à jour :", file_path)

# ⬇️ Exécution principale
if __name__ == "__main__":
    update_csv("euromillions_merged.csv")


