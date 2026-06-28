#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR INCREMENTAL — PRIORITE Coupe du Monde, puis backfill large.
1) Identifie les selections ENCORE EN LICE au Mondial 2026 (presentes dans les
   matchs a venir / en cours), et recupere EN PRIORITE tous leurs matchs depuis 2020.
2) Ensuite seulement : 5 ans des 5 grands championnats + coupes + Europe + amicaux.
Incremental (reprend ou il s'arrete), quota-aware (plan Pro). Cle = secret GitHub.
"""
import json, os, sys, time, math, datetime

API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
OUTPUT   = "donnees_cdm.js"
PROGRESS = "progress.json"
MATCHES  = "matches.json"

SAFETY_MARGIN = 60
MAX_RUN       = 7000
MAX_PER_TEAM  = 18
SLEEP         = 0.15

WC_LEAGUE = 1
WC_SEASON = 2026
PRIORITY_SEASONS = [2020,2021,2022,2023,2024,2025,2026]

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

class Stop(Exception): pass
_state_remaining = [None]
def api_get(path, params, used):
    import requests
    if used[0] >= MAX_RUN: raise Stop()
    r = requests.get(BASE_URL+path, headers={"x-apisports-key":API_KEY}, params=params, timeout=30)
    used[0]+=1
    rem = r.headers.get("x-ratelimit-requests-remaining")
    if rem is not None:
        try: _state_remaining[0]=int(rem)
        except: pass
    if r.status_code==429:
        print("  429 -> quota atteint."); raise Stop()
    r.raise_for_status()
    data=r.json()
    if data.get("errors"): print("  ! API:", data["errors"])
    return data.get("response", [])

def can_continue(used):
    if used[0] >= MAX_RUN: return False
    if _state_remaining[0] is not None and _state_remaining[0] <= SAFETY_MARGIN: return False
    return True

def load_json(path, default):
    if os.path.exists(path):
        try: return json.load(open(path, encoding="utf-8"))
        except: return default
    return default

def add_fixtures(resp, matches, pending, league_id, prio):
    n=0
    for fx in resp:
        if fx["fixture"]["status"]["short"]!="FT": continue
        fid=str(fx["fixture"]["id"])
        if fid in matches: continue
        lid = league_id if league_id is not None else str(fx.get("league",{}).get("id",""))
        pending.append({"fid":fid,"date":fx["fixture"]["date"][:10],
            "h":fx["teams"]["home"]["name"],"a":fx["teams"]["away"]["name"],
            "league":str(lid),"prio":prio})
        n+=1
    return n

def run():
    if not API_KEY:
        print("ERREUR : secret API_FOOTBALL_KEY manquant."); sys.exit(1)
    progress = load_json(PROGRESS, {"fixtures_done":{}, "pending_fixtures":[], "priority_teams":{}})
    progress.setdefault("priority_teams", {})
    progress.setdefault("fixtures_done", {})
    progress.setdefault("pending_fixtures", [])
    matches = load_json(MATCHES, {})
    used=[0]
    print(datetime.datetime.now(datetime.timezone.utc).strftime("== Run %d/%m %H:%M UTC =="))
    try:
        # 0) equipes encore en lice
        if not progress["priority_teams"]:
            if not can_continue(used): raise Stop()
            resp=api_get("/fixtures", {"league":WC_LEAGUE,"season":WC_SEASON}, used)
            allt={}; alive={}
            live={"NS","TBD","1H","HT","2H","ET","BT","P","SUSP","INT","LIVE"}
            for fx in resp:
                for side in ("home","away"):
                    t=fx["teams"][side]; allt[str(t["id"])]=t["name"]
                if fx["fixture"]["status"]["short"] in live:
                    for side in ("home","away"):
                        t=fx["teams"][side]; alive[str(t["id"])]=t["name"]
            progress["priority_teams"] = alive if alive else allt
            print("  Selections prioritaires (en lice):", len(progress["priority_teams"]))
        # A) calendriers des selections prioritaires (tous matchs depuis 2020)
        for tid,name in list(progress["priority_teams"].items()):
            for s in PRIORITY_SEASONS:
                key=f"T{tid}_{s}"
                if progress["fixtures_done"].get(key): continue
                if not can_continue(used): raise Stop()
                resp=api_get("/fixtures", {"team":tid,"season":s}, used)
                add_fixtures(resp, matches, progress["pending_fixtures"], None, True)
                progress["fixtures_done"][key]=True
                time.sleep(SLEEP)
        # C) calendriers du backfill large (apres priorite)
        for lid,label,cat,seasons in COMPETITIONS:
            for s in seasons:
                key=f"{lid}_{s}"
                if progress["fixtures_done"].get(key): continue
                if not can_continue(used): raise Stop()
                resp=api_get("/fixtures", {"league":lid,"season":s}, used)
                add_fixtures(resp, matches, progress["pending_fixtures"], str(lid), False)
                progress["fixtures_done"][key]=True
                time.sleep(SLEEP)
        # B) statistiques : prioritaires d'abord, puis recents d'abord
        seen=set(); pend=[]
        for it in progress["pending_fixtures"]:
            if it["fid"] in matches or it["fid"] in seen: continue
            seen.add(it["fid"]); pend.append(it)
        pend.sort(key=lambda x:x["date"], reverse=True)
        pend.sort(key=lambda x:0 if x.get("prio") else 1)
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
        print("  Pause (quota/plafond). Reprise au prochain run.")
    progress["pending_fixtures"]=[it for it in progress["pending_fixtures"] if it["fid"] not in matches]
    aggregate_and_write(matches)
    json.dump(progress, open(PROGRESS,"w",encoding="utf-8"))
    json.dump(matches,  open(MATCHES,"w",encoding="utf-8"))
    print(f"  Requetes: {used[0]} | matchs en base: {len(matches)} | en attente: {len(progress['pending_fixtures'])}")

def aggregate_and_write(matches):
    by_team={}
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
    payload=("// Genere automatiquement (GitHub Actions) — priorite Mondial puis backfill.\n"
        "// Maj: "+datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M")+" UTC\n"
        "var LEAGUE_AVG = "+json.dumps(la)+";\n"
        "var TEAMS = "+json.dumps(TEAMS, ensure_ascii=False)+";\n"
        "var UPCOMING = [];\n"
        "var HISTORY = "+json.dumps(HISTORY, ensure_ascii=False)+";\n")
    open(OUTPUT,"w",encoding="utf-8").write(payload)
    print(f"  -> {OUTPUT}: {len(TEAMS)} equipes, {len(HISTORY)} matchs d'historique.")

if __name__=="__main__":
    run()
