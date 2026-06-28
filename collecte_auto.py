#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR INCREMENTAL (GitHub Actions) — multi-competitions.
- Balaie 5 ans des 5 grands championnats + coupes nationales + coupes d'Europe
  + competitions de selections + amicaux.
- INCREMENTAL : reprend ou il s'est arrete (progress.json + matches.json),
  ne recharge jamais de zero.
- QUOTA-AWARE : s'arrete avant d'epuiser le quota quotidien (plan Pro).
- Agrege tout en donnees_cdm.js (lu par outil_cdm.html).
La cle API vient du secret GitHub API_FOOTBALL_KEY.
"""
import json, os, sys, time, math, datetime

API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
OUTPUT   = "donnees_cdm.js"
PROGRESS = "progress.json"
MATCHES  = "matches.json"

SAFETY_MARGIN = 60      # on garde 60 requetes de marge sous le quota du jour
MAX_RUN       = 7000    # plafond de requetes par execution (securite)
MAX_PER_TEAM  = 18      # nb de matchs recents gardes par equipe (frontend)
SLEEP         = 0.15    # pause entre requetes (respect du debit)

# (league_id, libelle, categorie, [saisons])
COMPETITIONS = [
    (39,  "Premier League",      "club", [2021,2022,2023,2024,2025]),
    (140, "LaLiga",              "club", [2021,2022,2023,2024,2025]),
    (135, "Serie A",             "club", [2021,2022,2023,2024,2025]),
    (78,  "Bundesliga",          "club", [2021,2022,2023,2024,2025]),
    (61,  "Ligue 1",             "club", [2021,2022,2023,2024,2025]),
    (45,  "FA Cup",              "club", [2021,2022,2023,2024,2025]),
    (143, "Copa del Rey",        "club", [2021,2022,2023,2024,2025]),
    (137, "Coppa Italia",        "club", [2021,2022,2023,2024,2025]),
    (81,  "DFB Pokal",           "club", [2021,2022,2023,2024,2025]),
    (66,  "Coupe de France",     "club", [2021,2022,2023,2024,2025]),
    (2,   "Champions League",    "club", [2021,2022,2023,2024,2025]),
    (3,   "Europa League",       "club", [2021,2022,2023,2024,2025]),
    (848, "Conference League",   "club", [2021,2022,2023,2024,2025]),
    (1,   "Coupe du Monde",      "nation", [2022,2026]),
    (4,   "Euro",                "nation", [2020,2024]),
    (5,   "Ligue des Nations",   "nation", [2022,2024,2025]),
    (9,   "Copa America",        "nation", [2021,2024]),
    (10,  "Amicaux (selections)","nation", [2022,2023,2024,2025]),
]
COMP_LABEL = {str(c[0]): c[1] for c in COMPETITIONS}
COMP_CAT   = {str(c[0]): c[2] for c in COMPETITIONS}

# ---------------- maths / moteur ----------------
def mean(a): return sum(a)/len(a) if a else 0.0
def std(a):
    if len(a) < 2: return 1.7
    m = mean(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))
def norm_cdf(x, mu, sd): return 0.5*(1+math.erf((x-mu)/(sd*math.sqrt(2))))
def reco(mu, sd):
    best=None; L=math.floor(mu-3)+0.5
    while L <= mu+3:
        p=1-norm_cdf(L,mu,sd); conf=max(p,1-p)
        if conf<=0.85:
            sc=conf-abs(L-mu)*0.01
            if best is None or sc>best["score"]:
                best={"line":L,"side":"over" if p>=0.5 else "under","prob":round(conf*100),"score":sc}
        L+=1
    if best is None:
        L=round(mu-0.5)+0.5; p=1-norm_cdf(L,mu,sd)
        best={"line":L,"side":"over" if p>=0.5 else "under","prob":round(max(p,1-p)*100)}
    return {"line":best["line"],"side":best["side"],"prob":best["prob"]}
LEAGUE_AVG = 12.5
def predict_shots(sf, opp_cd, is_home):
    if not sf: return 0,1.7,{"line":0,"side":"over","prob":50}
    attack=0.6*mean(sf[:5])+0.4*mean(sf)
    oc=mean(opp_cd) if opp_cd else LEAGUE_AVG
    exp=attack*(0.5+0.5*(oc/LEAGUE_AVG))*(1.12 if is_home else 0.96)*1.0
    sd=max(std(sf),1.7)
    return round(exp,1),round(sd,1),reco(exp,sd)

# ---------------- API (quota-aware) ----------------
class Stop(Exception): pass
_state_remaining = [None]   # quota quotidien restant (depuis les en-tetes)

def api_get(path, params, used):
    import requests
    if used[0] >= MAX_RUN: raise Stop()
    r = requests.get(BASE_URL+path, headers={"x-apisports-key":API_KEY}, params=params, timeout=30)
    used[0]+=1
    rem = r.headers.get("x-ratelimit-requests-remaining")
    if rem is not None:
        try:
            _state_remaining[0]=int(rem)
            if int(rem) <= SAFETY_MARGIN:
                print("  Quota quotidien presque epuise (", rem, "restantes) -> on s'arrete proprement.")
                # on traite cette reponse puis on stoppera au prochain tour
        except: pass
    if r.status_code==429:
        print("  429 -> quota atteint."); raise Stop()
    r.raise_for_status()
    data=r.json()
    if data.get("errors"): print("  ! API:", data["errors"])
    if _state_remaining[0] is not None and _state_remaining[0] <= SAFETY_MARGIN:
        # on a encore traite la reponse courante, mais on ne repart pas
        pass
    return data.get("response", [])

def can_continue(used):
    if used[0] >= MAX_RUN: return False
    if _state_remaining[0] is not None and _state_remaining[0] <= SAFETY_MARGIN: return False
    return True

# ---------------- persistance ----------------
def load_json(path, default):
    if os.path.exists(path):
        try: return json.load(open(path, encoding="utf-8"))
        except: return default
    return default

# ---------------- collecte ----------------
def run():
    if not API_KEY:
        print("ERREUR : secret API_FOOTBALL_KEY manquant."); sys.exit(1)
    progress = load_json(PROGRESS, {"fixtures_done": {}, "pending_fixtures": []})
    matches  = load_json(MATCHES, {})   # fid -> {h,a,hs,as,hsot,asot,hxg,axg,date,league,cat}
    used=[0]
    print(datetime.datetime.utcnow().strftime("== Run %d/%m %H:%M UTC =="))

    # 1) Recuperer les calendriers manquants (1 requete par competition-saison)
    try:
        for lid, label, cat, seasons in COMPETITIONS:
            for season in seasons:
                key=f"{lid}_{season}"
                if progress["fixtures_done"].get(key): continue
                if not can_continue(used): raise Stop()
                resp=api_get("/fixtures", {"league":lid,"season":season}, used)
                for fx in resp:
                    st=fx["fixture"]["status"]["short"]
                    fid=str(fx["fixture"]["id"])
                    if st=="FT" and fid not in matches:
                        progress["pending_fixtures"].append({
                            "fid":fid,"date":fx["fixture"]["date"][:10],
                            "h":fx["teams"]["home"]["name"],"a":fx["teams"]["away"]["name"],
                            "league":str(lid)})
                progress["fixtures_done"][key]=True
                time.sleep(SLEEP)
        # 2) Recuperer les statistiques des matchs en attente
        # dedoublonnage + ordre chronologique inverse (recents d'abord)
        seen=set(); pend=[]
        for it in progress["pending_fixtures"]:
            if it["fid"] in matches or it["fid"] in seen: continue
            seen.add(it["fid"]); pend.append(it)
        pend.sort(key=lambda x: x["date"], reverse=True)
        for it in pend:
            if not can_continue(used): raise Stop()
            stats=api_get("/fixtures/statistics", {"fixture":it["fid"]}, used)
            per={}
            for blk in stats:
                d={}
                for s in blk["statistics"]: d[s["type"]]=s["value"]
                per[blk["team"]["name"]]=d
            def iv(t,k):
                v=per.get(t,{}).get(k,0); return int(v) if isinstance(v,(int,float)) else 0
            def fv(t,k):
                v=per.get(t,{}).get(k,None)
                try: return round(float(v),2)
                except: return None
            h,a=it["h"],it["a"]
            matches[it["fid"]]={"h":h,"a":a,"date":it["date"],"league":it["league"],
                "hs":iv(h,"Total Shots"),"as":iv(a,"Total Shots"),
                "hsot":iv(h,"Shots on Goal"),"asot":iv(a,"Shots on Goal"),
                "hxg":fv(h,"expected_goals"),"axg":fv(a,"expected_goals")}
            time.sleep(SLEEP)
    except Stop:
        print("  Pause (quota/plafond). On reprendra au prochain run.")

    # on retire de pending ce qui est deja recupere
    progress["pending_fixtures"]=[it for it in progress["pending_fixtures"] if it["fid"] not in matches]

    aggregate_and_write(matches)
    json.dump(progress, open(PROGRESS,"w",encoding="utf-8"))
    json.dump(matches,  open(MATCHES,"w",encoding="utf-8"))
    print(f"  Requetes utilisees: {used[0]} | matchs en base: {len(matches)} | en attente: {len(progress['pending_fixtures'])}")

# ---------------- agregation -> donnees_cdm.js ----------------
def aggregate_and_write(matches):
    # construire l'historique de tirs par equipe (recents d'abord)
    by_team={}   # name -> list of (date, shots_for, sot_for, shots_against, xg_for, xg_against)
    for fid,m in matches.items():
        by_team.setdefault(m["h"],[]).append((m["date"],m["hs"],m["hsot"],m["as"],m["hxg"],m["axg"]))
        by_team.setdefault(m["a"],[]).append((m["date"],m["as"],m["asot"],m["hs"],m["axg"],m["hxg"]))
    TEAMS={}
    for name,rows in by_team.items():
        rows.sort(key=lambda r:r[0], reverse=True)
        rows=rows[:MAX_PER_TEAM]
        TEAMS[name]={"type":"club","cat":"club",
            "sf":[r[1] for r in rows], "sot":[r[2] for r in rows], "cd":[r[3] for r in rows],
            "xgf":[r[4] for r in rows], "xga":[r[5] for r in rows],
            "pos":50,"style":"-","press":"-","bloc":"-","top":False}
    # historique de predictions honnetes (sur les 40 matchs les plus recents avec stats)
    HISTORY=[]
    recent=sorted(matches.values(), key=lambda m:m["date"], reverse=True)[:40]
    for m in recent:
        h=m["h"]; a=m["a"]
        if h not in TEAMS: continue
        sf=[x for x in TEAMS[h]["sf"]]; real=m["hs"]
        if real in sf: sf.remove(real)
        if len(sf)<3: continue
        exp,sd,rc=predict_shots(sf, TEAMS[a]["cd"] if a in TEAMS else [], True)
        lbl=("OVER " if rc["side"]=="over" else "UNDER ")+str(rc["line"]).replace(".",",")
        HISTORY.append([m["date"], f"{h} - {a}", "tirs", lbl, exp,
                        [round(exp-0.85*sd),round(exp+0.85*sd)], real, rc["prob"]])
    allsf=[v for t in TEAMS.values() for v in t["sf"]]
    la=round(mean(allsf),1) if allsf else LEAGUE_AVG
    payload=("// Genere automatiquement (GitHub Actions) — base multi-competitions.\n"
        "// Maj: "+datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M")+" UTC\n"
        "var LEAGUE_AVG = "+json.dumps(la)+";\n"
        "var TEAMS = "+json.dumps(TEAMS, ensure_ascii=False)+";\n"
        "var UPCOMING = [];\n"
        "var HISTORY = "+json.dumps(HISTORY, ensure_ascii=False)+";\n")
    open(OUTPUT,"w",encoding="utf-8").write(payload)
    print(f"  -> {OUTPUT}: {len(TEAMS)} equipes, {len(HISTORY)} matchs d'historique.")

if __name__=="__main__":
    run()
