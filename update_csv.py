import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import locale

# 🌍 Configurer la locale française
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except locale.Error:
        print("❌ Locale française non disponible.")
        exit(1)

# 🧠 Extraire le jour de la semaine en français
def jour_en_francais(date_str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%A").lower()  # "mardi", "vendredi", etc.

# 📥 Récupérer le dernier tirage
def fetch_latest_draw():
    url = "https://tirage-gagnant.com/euromillions/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # 📅 Date
    date_span = soup.find("span", class_="date_full")
    if not date_span:
        raise ValueError("❌ Date du tirage introuvable.")
    date_str = date_span.text.strip()

    try:
        draw_date = datetime.strptime(date_str, "%A %d %B %Y")
    except ValueError as e:
        raise ValueError(f"❌ Erreur de date : {date_str}") from e

    date_iso = draw_date.strftime("%Y-%m-%d")
    day_name = jour_en_francais(date_iso)

    # 🔢 Nombres
    numbers = [int(tag.text.strip()) for tag in soup.find_all("p", class_="num_v2")[:5]]
    stars = [int(tag.text.strip()) for tag in soup.find_all("span", class_="etoile-num")[:2]]

    # 🧼 Format propre
    tirage_str = "-".join(f"{n:02d}" for n in sorted(numbers))
    etoiles_str = "-".join(str(s) for s in sorted(stars))

    # ✅ Ordre des colonnes demandé
    return {
        "jour_de_tirage": day_name,
        "date_de_tirage": date_iso,
        "tirage": tirage_str,
        "etoiles": etoiles_str,
    }

# 🔁 Mise à jour du fichier CSV
def update_csv(file_path="euromillions_merged.csv", force=False):
    new_draw = fetch_latest_draw()

    try:
        df_old = pd.read_csv(file_path, sep=";", encoding="utf-8")
    except FileNotFoundError:
        df_old = pd.DataFrame()

    # 💡 Si la date existe déjà, on n’ajoute pas (sauf si force=True)
    if not force and not df_old.empty and new_draw["date_de_tirage"] in df_old["date_de_tirage"].values:
        print("✅ Tirage déjà présent :", new_draw["date_de_tirage"])
        return

    # ➕ Ajouter et trier
    df_new = pd.DataFrame([new_draw])
    df_final = pd.concat([df_old, df_new], ignore_index=True)
    df_final["date_de_tirage"] = pd.to_datetime(df_final["date_de_tirage"])
    df_final = df_final.sort_values("date_de_tirage", ascending=False)
    df_final["date_de_tirage"] = df_final["date_de_tirage"].dt.strftime("%Y-%m-%d")

    # 💾 Sauvegarde
    df_final.to_csv(file_path, sep=";", index=False, encoding="utf-8")
    print("✅ Fichier mis à jour :", file_path)

# ▶️ Lancer la mise à jour
if __name__ == "__main__":
    update_csv("euromillions_merged.csv")



