#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde l'endpoint ODDS d'API-Football pour savoir EXACTEMENT quels marches
'tirs / cadres PAR EQUIPE' existent et sont REELLEMENT proposes sur de vrais matchs.
Resultat -> odds_probe.json (a lire dans le depot)."""
import os, json, datetime, requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
H = {"x-apisports-key": API_KEY}
out = {"genere": datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}

def get(path, params=None):
    r = requests.get(BASE + path, headers=H, params=params or {}, timeout=30)
    return r.json()

def nm(b):
    return (b.get("name") or "")

# 1) catalogue : tous les types de paris lies aux tirs / cadres (par equipe inclus)
try:
    j = get("/odds/bets")
    bets = j.get("response", [])
    out["nb_types_de_paris"] = len(bets)
    out["types_de_paris_tirs"] = [{"id": b.get("id"), "name": nm(b)}
                                  for b in bets if ("shot" in nm(b).lower() or "tir" in nm(b).lower())]
except Exception as e:
    out["erreur_bets"] = str(e)

# 2) marches REELLEMENT proposes sur de vrais matchs (agrege sur les 10 premiers matchs)
def echantillon(league, season, label):
    try:
        j = get("/odds", {"league": league, "season": season, "page": 1})
        resp = j.get("response", []) or []
        marches = {}   # nom_marche -> set(bookmakers)
        for fx in resp[:10]:
            for bk in fx.get("bookmakers", []):
                for bet in bk.get("bets", []):
                    n = nm(bet)
                    marches.setdefault(n, set()).add(bk.get("name"))
        tirs = {n: sorted(b for b in bks if b) for n, bks in marches.items()
                if ("shot" in n.lower() or "tir" in n.lower())}
        out[label] = {
            "resultats_total": j.get("results"),
            "nb_matchs_page": len(resp),
            "marches_tirs_proposes": tirs,                 # <-- la reponse cle
            "tous_les_marches": sorted(marches.keys()),
        }
    except Exception as e:
        out["erreur_" + label] = str(e)

# matchs en cours / a venir => vraies cotes pre-match
echantillon(1,   2026, "CoupeDuMonde_2026")
echantillon(39,  2025, "PremierLeague_2025")
echantillon(140, 2025, "LaLiga_2025")
echantillon(135, 2025, "SerieA_2025")

# statut EXACT de fixtures precises (matchs signales : Pays-Bas-Maroc, Allemagne-Paraguay, etc.)
try:
    check = {}
    for fid in ["1562345", "1565176", "1561329", "1567311"]:
        j = get("/fixtures", {"id": fid})
        r = j.get("response") or []
        if r:
            fx = r[0]; stt = fx["fixture"]["status"]
            check[fid] = {"h": fx["teams"]["home"]["name"], "a": fx["teams"]["away"]["name"],
                          "date": fx["fixture"]["date"][:10], "status": stt.get("short"),
                          "detail": stt.get("long"), "score": str(fx.get("goals", {}).get("home")) + "-" + str(fx.get("goals", {}).get("away"))}
        else:
            check[fid] = "aucune reponse"
    out["fixtures_check"] = check
except Exception as e:
    out["erreur_fixtures_check"] = str(e)

json.dump(out, open("odds_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Types de paris 'tirs':", len(out.get("types_de_paris_tirs", [])))
for k in ("CoupeDuMonde_2026","PremierLeague_2025","LaLiga_2025","SerieA_2025"):
    if k in out:
        print(k, "-> marches tirs:", list(out[k]["marches_tirs_proposes"].keys()))
