#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde l'endpoint ODDS d'API-Football : catalogue + cotes tirs sur matchs proches,
ou dump complet d'un fixture precis (FIXTURE_ID env / argument)."""
import os, sys, json, datetime, requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
FIXTURE_ID = os.environ.get("FIXTURE_ID", "") or (sys.argv[1] if len(sys.argv) > 1 else "")
BASE = "https://v3.football.api-sports.io"
H = {"x-apisports-key": API_KEY}
out = {"genere": datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}

TEAM_SHOT_MARKETS = {
    "Shots. Home Total", "Shots. Away Total",
    "Home Total ShotOnGoal", "Away Total ShotOnGoal",
    "Home Shots On Target", "Away Shots On Target",
    "Total Shots", "Total ShotOnGoal",
}

def get(path, params=None):
    r = requests.get(BASE + path, headers=H, params=params or {}, timeout=30)
    return r.json()

# 1) marches tirs dans le catalogue
try:
    names = [(b.get("name") or "") for b in get("/odds/bets").get("response", [])]
    out["marches_tirs_catalogue"] = sorted([n for n in names if "shot" in n.lower()])
except Exception as e:
    out["erreur_bets"] = str(e)

# 2) fixture precis : dump TOUS les marches
if FIXTURE_ID:
    try:
        j = get("/odds", {"fixture": FIXTURE_ID})
        resp = j.get("response", [])
        fx = {"fixture_id": FIXTURE_ID, "nb_blocs": len(resp), "marches": {}, "marches_tirs": {}}
        for blk in resp:
            for bk in blk.get("bookmakers", []):
                for bet in bk.get("bets", []):
                    nm = bet.get("name") or ""
                    fx["marches"].setdefault(nm, []).append({
                        "book": bk.get("name"),
                        "values": bet.get("values"),
                    })
                    if nm in TEAM_SHOT_MARKETS or "shot" in nm.lower():
                        fx["marches_tirs"][nm] = {
                            "book": bk.get("name"),
                            "values": bet.get("values"),
                        }
        fx["liste_marches"] = sorted(fx["marches"].keys())
        fx["par_equipe_present"] = {
            k: k in fx["marches_tirs"]
            for k in ["Shots. Home Total", "Shots. Away Total",
                      "Home Total ShotOnGoal", "Away Total ShotOnGoal"]
        }
        out["fixture_precis"] = fx
    except Exception as e:
        out["erreur_fixture"] = str(e)

# 3) scan matchs proches (10 jours) pour cotes tirs remplies
def find_shots():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    scanned = 0
    exemples = []
    par_equipe = []
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
                fid = fx.get("fixture", {}).get("id")
                for bk in fx.get("bookmakers", []):
                    for bet in bk.get("bets", []):
                        nm = (bet.get("name") or "")
                        if "shot" not in nm.lower():
                            continue
                        item = {"date": day, "fixture": fid, "book": bk.get("name"),
                                "marche": nm, "valeurs": bet.get("values")}
                        exemples.append(item)
                        if nm in ("Shots. Home Total", "Shots. Away Total",
                                  "Home Total ShotOnGoal", "Away Total ShotOnGoal"):
                            par_equipe.append(item)
                if len(exemples) >= 8:
                    return {
                        "trouve": True,
                        "matchs_scannes": scanned,
                        "exemples": exemples[:6],
                        "cotes_par_equipe": par_equipe[:4],
                        "par_equipe_disponible": len(par_equipe) > 0,
                    }
            paging = j.get("paging", {})
            if page >= paging.get("total", 1):
                break
    return {
        "trouve": len(exemples) > 0,
        "matchs_scannes": scanned,
        "exemples": exemples[:6],
        "cotes_par_equipe": par_equipe[:4],
        "par_equipe_disponible": len(par_equipe) > 0,
    }

out["verif_cotes_tirs"] = find_shots()

json.dump(out, open("odds_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
v = out["verif_cotes_tirs"]
print("Verif tirs:", v.get("trouve"), "| par equipe:", v.get("par_equipe_disponible"),
      "| matchs scannes:", v.get("matchs_scannes"))
if FIXTURE_ID and "fixture_precis" in out:
    fp = out["fixture_precis"]
    print("Fixture", FIXTURE_ID, "->", len(fp.get("liste_marches", [])), "marches,",
          "tirs par equipe:", fp.get("par_equipe_present"))
