#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde l'endpoint ODDS d'API-Football : liste les marches disponibles et
repere tout marche 'tirs / shots'. Resultat -> odds_probe.json."""
import os, json, datetime, requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
H = {"x-apisports-key": API_KEY}
out = {"genere": datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}

def get(path, params=None):
    r = requests.get(BASE + path, headers=H, params=params or {}, timeout=30)
    return r.json()

try:
    j = get("/odds/bets")
    bets = j.get("response", [])
    out["nb_types_de_paris"] = len(bets)
    out["paris_contenant_shot_ou_tir"] = [b for b in bets if "shot" in b["name"].lower() or "tir" in b["name"].lower()]
    out["tous_les_paris"] = [{"id": b["id"], "name": b["name"]} for b in bets]
except Exception as e:
    out["erreur_bets"] = str(e)

try:
    j = get("/odds/bookmakers")
    out["bookmakers"] = [b["name"] for b in j.get("response", [])]
except Exception as e:
    out["erreur_bookmakers"] = str(e)

try:
    j = get("/odds", {"league": 39, "season": 2023, "page": 1})
    resp = j.get("response", [])
    out["odds_dispo_PL2023_resultats"] = j.get("results")
    if resp:
        marches = set()
        for bk in resp[0].get("bookmakers", []):
            for bet in bk.get("bets", []):
                marches.add(bet["name"])
        out["exemple_marches_un_match"] = sorted(marches)
except Exception as e:
    out["erreur_odds"] = str(e)

json.dump(out, open("odds_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Types de paris:", out.get("nb_types_de_paris"))
print("Paris 'tirs/shots':", len(out.get("paris_contenant_shot_ou_tir", [])))
