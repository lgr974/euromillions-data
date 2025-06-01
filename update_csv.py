import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://tirage-gagnant.com/euromillions/"
CSV_FILE = "euromillions_merged.csv"

def fetch_latest_draw():
    response = requests.get(URL)
    if response.status_code != 200:
        raise Exception(f"Erreur lors du chargement de la page ({response.status_code})")

    soup = BeautifulSoup(response.content, "html.parser")

    # Date
    date_str = soup.select_one("span.date_min").text.strip()
    draw_date = datetime.strptime(date_str, "%d/%m/%Y").date()

    # Numéros
    number_tags = soup.select("p.num_v2")
    numbers = [int(tag.text.strip()) for tag in number_tags[:5]]

    # Étoiles
    star_tags = soup.select("span.etoile-num")
    stars = [int(tag.text.strip()) for tag in star_tags[:2]]

    if len(numbers) != 5 or len(stars) != 2:
        raise ValueError("Le nombre de boules ou d'étoiles est incorrect.")

    print(f"Tirage récupéré : {draw_date} - Boules : {numbers} - Étoiles : {stars}")

    return {
        "date_de_tirage": draw_date,
        "boule_1": numbers[0],
        "boule_2": numbers[1],
        "boule_3": numbers[2],
        "boule_4": numbers[3],
        "boule_5": numbers[4],
        "etoile_1": stars[0],
        "etoile_2": stars[1],
    }

def update_csv(file_path):
    draw = fetch_latest_draw()

    # Chargement du fichier CSV
    try:
        df_old = pd.read_csv(file_path, sep=";")
    except FileNotFoundError:
        print("Fichier non trouvé, création d’un nouveau fichier.")
        df_old = pd.DataFrame(columns=[
            "date_de_tirage", "boule_1", "boule_2", "boule_3",
            "boule_4", "boule_5", "etoile_1", "etoile_2"
        ])

    # Vérification de l'existence
    draw_date_str = str(draw["date_de_tirage"])
    if draw_date_str in df_old["date_de_tirage"].astype(str).values:
        print("✅ Tirage déjà présent. Aucune mise à jour nécessaire.")
        return

    # Ajout du tirage
    new_row = pd.DataFrame([draw])
    df_new = pd.concat([df_old, new_row], ignore_index=True)

    # Sauvegarde
    df_new.to_csv(file_path, sep=";", index=False)
    print("✅ Fichier mis à jour avec le nouveau tirage.")

if __name__ == "__main__":
    update_csv(CSV_FILE)
