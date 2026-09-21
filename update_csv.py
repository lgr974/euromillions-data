#!/usr/bin/env python3
"""Met à jour euromillions_merged.csv et comble les tirages manquants.

Sources, dans l'ordre :
  1. le dernier tirage affiché sur tirage-gagnant.com ;
  2. l'API communautaire de Pedro Mealha (euromillions.api.pedromealha.dev)
     pour tous les tirages entre le dernier du fichier et aujourd'hui.

Chaque source peut tomber en panne sans empêcher la mise à jour : si l'une
échoue, l'autre prend le relais. Le script échoue (code 1, erreur rouge dans
GitHub Actions) seulement si les DEUX sources échouent. Quand les deux
répondent et ne sont pas d'accord sur un tirage, c'est tirage-gagnant.com qui
est retenu et un avertissement est affiché.

Le fichier existant n'est jamais réécrit en entier : les nouvelles lignes sont
insérées à leur place (fichier trié du plus récent au plus ancien).

Dépendances : requests, beautifulsoup4.
"""
import re
import sys
import time
import unicodedata
from collections import namedtuple
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

URL_SITE = "https://tirage-gagnant.com/euromillions/"
URL_API = "https://euromillions.api.pedromealha.dev/v1/draws"
FICHIER = "euromillions_merged.csv"
ENTETE = "jour_de_tirage;date_de_tirage;tirage;etoiles"
PREMIER_TIRAGE = date(2004, 2, 13)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

Tirage = namedtuple("Tirage", "date numeros etoiles")


# ----------------------------------------------------------------- validation

def valider_tirage(jour, numeros, etoiles):
    numeros, etoiles = sorted(numeros), sorted(etoiles)
    if len(numeros) != 5 or len(set(numeros)) != 5 or not all(1 <= n <= 50 for n in numeros):
        raise ValueError(f"Numéros invalides : {numeros}")
    if len(etoiles) != 2 or len(set(etoiles)) != 2 or not all(1 <= e <= 12 for e in etoiles):
        raise ValueError(f"Étoiles invalides : {etoiles}")
    if jour.weekday() not in (1, 4):
        raise ValueError(f"{jour} n'est ni un mardi ni un vendredi")
    return Tirage(jour, numeros, etoiles)


def formater_ligne(tirage):
    numeros = "-".join(f"{n:02d}" for n in tirage.numeros)
    etoiles = "-".join(str(e) for e in tirage.etoiles)
    return f"{JOURS[tirage.date.weekday()]};{tirage.date.isoformat()};{numeros};{etoiles}"


# ------------------------------------------------------- source 1 : le site

def sans_accent(texte):
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower()


def analyser_date(texte):
    """« Mardi 1er Septembre 2026 » ou « Vendredi 28 Août 2026 » -> date."""
    m = re.search(r"(\d{1,2})(?:er|re|e)?\s+([^\W\d_]+)\s+(\d{4})", texte.strip())
    if not m:
        raise ValueError(f"Date illisible : {texte!r}")
    jour, nom_mois, annee = int(m.group(1)), sans_accent(m.group(2)), int(m.group(3))
    if nom_mois not in MOIS:
        raise ValueError(f"Mois inconnu dans la date : {texte!r}")
    return date(annee, MOIS[nom_mois], jour)


def _entier(balise):
    try:
        return int(balise.get_text(strip=True))
    except ValueError as erreur:
        raise ValueError(f"Nombre illisible : {balise.get_text(strip=True)!r}") from erreur


def extraire_dernier_tirage(contenu):
    soup = BeautifulSoup(contenu, "html.parser")
    balise_date = soup.find("span", class_="date_full")
    if balise_date is None:
        raise ValueError(
            "Balise span.date_full introuvable : le site a changé de structure "
            "ou a renvoyé une page de blocage."
        )
    jour = analyser_date(balise_date.get_text(" ", strip=True))
    numeros = [_entier(t) for t in soup.find_all("p", class_="num_v2")[:5]]
    etoiles = [_entier(t) for t in soup.find_all("span", class_="etoile-num")[:2]]
    return valider_tirage(jour, numeros, etoiles)


def telecharger_site(essais=3):
    derniere = None
    for i in range(essais):
        try:
            r = requests.get(URL_SITE, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return extraire_dernier_tirage(r.content)
        except requests.RequestException as erreur:
            derniere = erreur
            print(f"Site : essai {i + 1}/{essais} échoué : {erreur}")
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"Site injoignable : {derniere}")


# -------------------------------------------------------- source 2 : l'API

def tirages_depuis_json(donnees):
    """Réponse de GET /v1/draws -> (liste de Tirage, nombre d'entrées rejetées)."""
    if not isinstance(donnees, list):
        raise ValueError("Réponse de l'API inattendue (une liste était attendue)")
    tirages, rejetes = [], 0
    for item in donnees:
        try:
            jour = date.fromisoformat(str(item["date"])[:10])
            tirages.append(
                valider_tirage(
                    jour,
                    [int(n) for n in item["numbers"]],
                    [int(e) for e in item["stars"]],
                )
            )
        except (KeyError, ValueError, TypeError):
            rejetes += 1
    return tirages, rejetes


def telecharger_api(debut, fin, essais=4):
    """Tirages entre `debut` et `fin` inclus (une seule requête)."""
    params = {"dates": f"{debut.isoformat()},{fin.isoformat()}"}
    derniere = None
    for i in range(essais):
        attente = 10 * (i + 1)
        try:
            r = requests.get(URL_API, params=params, headers=HEADERS, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504):
                derniere = f"code {r.status_code}"
                try:
                    attente = max(attente, int(r.headers.get("Retry-After", "0")))
                except ValueError:
                    pass
            else:
                r.raise_for_status()
                tirages, rejetes = tirages_depuis_json(r.json())
                if rejetes:
                    print(f"API : {rejetes} entrée(s) invalide(s) ignorée(s)")
                return tirages
        except (requests.RequestException, ValueError) as erreur:
            derniere = erreur
        print(f"API : essai {i + 1}/{essais} échoué ({derniere})")
        if i < essais - 1:
            time.sleep(attente)
    raise RuntimeError(f"API injoignable : {derniere}")


# ------------------------------------------------------------------ fichier

def date_de_ligne(ligne):
    parts = ligne.split(";")
    if len(parts) >= 2 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[1].strip()):
        try:
            return date.fromisoformat(parts[1].strip())
        except ValueError:
            return None
    return None


def lire_lignes(chemin):
    try:
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            lignes = [l for l in f.read().splitlines() if l.strip()]
    except FileNotFoundError:
        return [ENTETE]
    return lignes or [ENTETE]


def inserer(lignes, nouvelle, jour):
    """Insère avant la première ligne plus ancienne. Lignes illisibles intactes."""
    position = len(lignes)
    for i in range(1, len(lignes)):
        d = date_de_ligne(lignes[i])
        if d is not None and d < jour:
            position = i
            break
    lignes.insert(position, nouvelle)


def tirages_manquants(dates_existantes, apres, jusqua):
    """Mardis et vendredis strictement entre `apres` et `jusqua`, absents."""
    manquants = []
    jour = apres + timedelta(days=1)
    while jour < jusqua:
        if jour.weekday() in (1, 4) and jour not in dates_existantes:
            manquants.append(jour)
        jour += timedelta(days=1)
    return manquants


# ------------------------------------------------------------- orchestration

def mettre_a_jour(chemin, recuperer_site, recuperer_api, aujourdhui):
    """Retourne le code de sortie (0 = succès, 1 = les deux sources ont échoué)."""
    lignes = lire_lignes(chemin)
    dates = {d for d in (date_de_ligne(l) for l in lignes[1:]) if d is not None}
    derniere = max(dates) if dates else None

    candidats = {}  # date -> Tirage ; le site est prioritaire
    echecs = []

    # 1) le site : dernier tirage publié
    try:
        t = recuperer_site()
        if t.date <= aujourdhui:
            candidats[t.date] = t
    except Exception as erreur:  # noqa: BLE001 - on veut tout signaler
        echecs.append("site")
        print(f"::warning::tirage-gagnant.com indisponible : {erreur}")

    # 2) l'API : tous les tirages depuis le dernier du fichier
    debut = (derniere + timedelta(days=1)) if derniere else PREMIER_TIRAGE
    if debut <= aujourdhui:
        try:
            for t in recuperer_api(debut, aujourdhui):
                if t.date > aujourdhui:
                    continue
                autre = candidats.get(t.date)
                if autre is None:
                    candidats[t.date] = t
                elif (autre.numeros, autre.etoiles) != (t.numeros, t.etoiles):
                    print(
                        f"::warning::Désaccord des sources pour {t.date} : site "
                        f"{formater_ligne(autre)} / API {formater_ligne(t)} (site retenu)"
                    )
        except Exception as erreur:  # noqa: BLE001
            echecs.append("api")
            print(f"::warning::API Euromillions indisponible : {erreur}")

    if len(echecs) == 2:
        print("::error::Aucune source disponible : mise à jour impossible.")
        return 1

    nouveaux = sorted((t for d, t in candidats.items() if d not in dates), key=lambda t: t.date)
    if not nouveaux:
        print("Fichier déjà à jour.")
        return 0

    for t in reversed(nouveaux):
        inserer(lignes, formater_ligne(t), t.date)
        print(f"Ajouté : {formater_ligne(t)}")

    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lignes) + "\n")

    if derniere:
        toutes = dates | {t.date for t in nouveaux}
        trous = tirages_manquants(toutes, derniere, max(toutes))
        if trous:
            liste = ", ".join(d.isoformat() for d in trous)
            print(f"::warning::Tirages toujours manquants (à ajouter à la main) : {liste}")
    return 0


def main():
    aujourdhui = datetime.now(timezone.utc).date()
    return mettre_a_jour(FICHIER, telecharger_site, telecharger_api, aujourdhui)


if __name__ == "__main__":
    sys.exit(main())
