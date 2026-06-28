#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifie si des COTES TIRS reelles sont remplies pour des matchs a venir."""
import os, json, datetime, requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
H = {"x-apisports-key": API_KEY}
out = {"genere": datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}

def get(path, params=None):
    return requests.get(BASE + path, headers=H, params=params or {}, timeout=30).json()

# rappel : marches tirs presents dans le catalogue (deja confirme)
try:
    names = [(b.get("name") or "") for b in get("/odds/bets").get("response", [])]
    out["marches_tirs_catalogue"] = sorted([n for n in names if "shot" in n.lower()])
except Exception as e:
    out["erreur_bets"] = str(e)

# VERIF : cherche de vrais matchs a venir avec des cotes tirs remplies
def find_shots():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    scanned = 0
    exemples = []
    for d in range(0, 10):
        day = (today + datetime.timedelta(days=d)).isoformat()
        for page in range(1, 4):
            try:
                j = get("/odds", {"date": day, "page": page})
            except Exception as e:
                return {"erreur": str(e)}
            resp = j.get("response", [])
            if not resp:
                break
            scanned += len(resp)
            for fx in resp:
                for bk in fx.get("bookmakers", []):
                    for bet in bk.get("bets", []):
                        nm = (bet.get("name") or "")
                        if "shot" in nm.lower():
                            exemples.append({"date": day, "fixture": fx.get("fixture", {}).get("id"),
                                             "book": bk.get("name"), "marche": nm,
                                             "valeurs": bet.get("values")})
                            if len(exemples) >= 6:
                                return {"trouve": True, "matchs_scannes": scanned, "exemples": exemples}
            paging = j.get("paging", {})
            if page >= paging.get("total", 1):
                break
    return {"trouve": len(exemples) > 0, "matchs_scannes": scanned, "exemples": exemples}

out["verif_cotes_tirs"] = find_shots()

json.dump(out, open("odds_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Verif tirs:", out["verif_cotes_tirs"].get("trouve"), "| matchs scannes:", out["verif_cotes_tirs"].get("matchs_scannes"))
