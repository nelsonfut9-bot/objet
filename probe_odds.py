#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde ODDS d'API-Football : catalogue complet des marches + repere 'tirs/shots'
+ exemple reel de cotes sur un match. Resultat -> odds_probe.json."""
import os, json, datetime, requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
H = {"x-apisports-key": API_KEY}
out = {"genere": datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}

def get(path, params=None):
    return requests.get(BASE + path, headers=H, params=params or {}, timeout=30).json()

# 1) catalogue complet des types de paris (en gerant les noms vides)
try:
    bets = get("/odds/bets").get("response", [])
    names = [(b.get("name") or "") for b in bets]
    out["nb_types_de_paris"] = len(bets)
    out["paris_tirs"] = sorted([n for n in names if "shot" in n.lower() or "tir" in n.lower()])
    out["tous_les_paris"] = sorted([n for n in names if n])
except Exception as e:
    out["erreur_bets"] = str(e)

# 2) cherche un vrai match avec des cotes, liste ses marches et toute cote 'tirs'
def sample_markets():
    for lg, ss in [(39, 2024), (140, 2024), (135, 2024), (61, 2024), (2, 2024), (39, 2025), (61, 2025)]:
        try:
            resp = get("/odds", {"league": lg, "season": ss, "page": 1}).get("response", [])
        except Exception as e:
            return {"erreur": str(e)}
        if not resp:
            continue
        fx = resp[0]
        allm, shots = set(), []
        for bk in fx.get("bookmakers", []):
            for bet in bk.get("bets", []):
                nm = bet.get("name", "") or ""
                allm.add(nm)
                if "shot" in nm.lower() or "tir" in nm.lower():
                    shots.append({"book": bk.get("name"), "marche": nm, "valeurs": bet.get("values")})
        return {"league": lg, "season": ss, "fixture": fx.get("fixture", {}).get("id"),
                "nb_marches": len(allm), "marches": sorted(allm), "marches_tirs": shots}
    return {"info": "aucune cote trouvee sur les ligues testees (les cotes API ne couvrent souvent que les matchs proches)"}
out["exemple_match"] = sample_markets()

json.dump(out, open("odds_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OK", out.get("nb_types_de_paris"), "paris ; tirs:", out.get("paris_tirs"))
