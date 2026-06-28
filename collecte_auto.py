#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR INCREMENTAL — toutes stats par match, fiches d'equipe (type Sofascore).
PRIORITE : selections encore en lice au Mondial 2026 + leur historique depuis 2020.
Puis backfill 5 grands championnats + coupes + Europe + amicaux.
Incremental (progress.json/matches.json), quota-aware. Cle = secret GitHub.
"""
import json, os, sys, time, math, datetime

API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
OUTPUT   = "donnees_cdm.js"; PROGRESS="progress.json"; MATCHES="matches.json"
SAFETY_MARGIN=60; MAX_RUN=7000; MAX_PER_TEAM=40; SLEEP=0.15
WC_LEAGUE=1; WC_SEASON=2026; PRIORITY_SEASONS=[2020,2021,2022,2023,2024,2025,2026]

COMPETITIONS=[
    (39,"Premier League","club",[2021,2022,2023,2024,2025]),
    (140,"LaLiga","club",[2021,2022,2023,2024,2025]),
    (135,"Serie A","club",[2021,2022,2023,2024,2025]),
    (78,"Bundesliga","club",[2021,2022,2023,2024,2025]),
    (61,"Ligue 1","club",[2021,2022,2023,2024,2025]),
    (45,"FA Cup","club",[2021,2022,2023,2024,2025]),
    (143,"Copa del Rey","club",[2021,2022,2023,2024,2025]),
    (137,"Coppa Italia","club",[2021,2022,2023,2024,2025]),
    (81,"DFB Pokal","club",[2021,2022,2023,2024,2025]),
    (66,"Coupe de France","club",[2021,2022,2023,2024,2025]),
    (2,"UEFA Champions League","club",[2021,2022,2023,2024,2025]),
    (3,"UEFA Europa League","club",[2021,2022,2023,2024,2025]),
    (848,"UEFA Conference League","club",[2021,2022,2023,2024,2025]),
    (1,"Coupe du Monde","nation",[2022,2026]),
    (4,"Euro","nation",[2020,2024]),
    (5,"Ligue des Nations","nation",[2022,2024,2025]),
    (9,"Copa America","nation",[2021,2024]),
    (10,"Amicaux","nation",[2022,2023,2024,2025]),
]

INT_STATS={"Total Shots":"ts","Shots on Goal":"sot","Shots insidebox":"sib","Shots outsidebox":"sob",
    "Blocked Shots":"blk","Corner Kicks":"cor","Fouls":"fouls","Offsides":"off","Yellow Cards":"yc",
    "Red Cards":"rc","Goalkeeper Saves":"sav","Total passes":"pas","Passes accurate":"pacc"}
PCT_STATS={"Ball Possession":"poss","Passes %":"ppct"}

def parse_side(d):
    out={}
    for api,k in INT_STATS.items():
        v=d.get(api,0); out[k]=int(v) if isinstance(v,(int,float)) else 0
    for api,k in PCT_STATS.items():
        v=d.get(api,0)
        try: out[k]=int(str(v).replace("%","").strip())
        except: out[k]=0
    try: out["xg"]=round(float(d.get("expected_goals")),2)
    except: out["xg"]=None
    return out

def mean(a):
    a=[x for x in a if x is not None]; return sum(a)/len(a) if a else 0.0
def std(a):
    a=[x for x in a if x is not None]
    if len(a)<2: return 1.7
    m=sum(a)/len(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))

class Stop(Exception): pass
_rem=[None]
def api_get(path,params,used):
    import requests
    if used[0]>=MAX_RUN: raise Stop()
    r=requests.get(BASE_URL+path,headers={"x-apisports-key":API_KEY},params=params,timeout=30)
    used[0]+=1
    rem=r.headers.get("x-ratelimit-requests-remaining")
    if rem is not None:
        try: _rem[0]=int(rem)
        except: pass
    if r.status_code==429: print("  429 -> quota."); raise Stop()
    r.raise_for_status(); data=r.json()
    if data.get("errors"): print("  ! API:",data["errors"])
    return data.get("response",[])
def can_continue(used):
    if used[0]>=MAX_RUN: return False
    if _rem[0] is not None and _rem[0]<=SAFETY_MARGIN: return False
    return True
def load_json(p,d):
    if os.path.exists(p):
        try: return json.load(open(p,encoding="utf-8"))
        except: return d
    return d

def add_fixtures(resp, matches, pending, upcoming_raw, league_id, prio):
    for fx in resp:
        st=fx["fixture"]["status"]["short"]; fid=str(fx["fixture"]["id"]); lg=fx.get("league",{})
        lid=league_id if league_id is not None else str(lg.get("id",""))
        h=fx["teams"]["home"]["name"]; a=fx["teams"]["away"]["name"]
        if st=="FT":
            if fid in matches: continue
            pending.append({"fid":fid,"date":fx["fixture"]["date"][:10],"h":h,"a":a,
                "league":str(lid),"lname":lg.get("name",""),"season":lg.get("season",""),
                "gh":fx.get("goals",{}).get("home") or 0,"ga":fx.get("goals",{}).get("away") or 0,"prio":prio})
        elif st in ("NS","TBD"):
            upcoming_raw[fid]={"date":fx["fixture"]["date"][:10],"h":h,"a":a,"lname":lg.get("name","")}

def run():
    if not API_KEY: print("ERREUR : secret API_FOOTBALL_KEY manquant."); sys.exit(1)
    progress=load_json(PROGRESS,{})
    progress.setdefault("priority_teams",{}); progress.setdefault("fixtures_done",{})
    progress.setdefault("pending_fixtures",[]); progress.setdefault("upcoming_raw",{})
    matches=load_json(MATCHES,{}); used=[0]
    print(datetime.datetime.now(datetime.timezone.utc).strftime("== Run %d/%m %H:%M UTC =="))
    if matches:
        sample=next(iter(matches.values()))
        if not isinstance(sample,dict) or "H" not in sample:
            print("  Ancien format detecte -> reinitialisation propre.")
            matches={}; progress={"priority_teams":{},"fixtures_done":{},"pending_fixtures":[],"upcoming_raw":{}}
    try:
        if not progress["priority_teams"]:
            if not can_continue(used): raise Stop()
            resp=api_get("/fixtures",{"league":WC_LEAGUE,"season":WC_SEASON},used)
            allt={}; alive={}; live={"NS","TBD","1H","HT","2H","ET","BT","P","SUSP","INT","LIVE"}
            for fx in resp:
                for side in ("home","away"):
                    t=fx["teams"][side]; allt[str(t["id"])]=t["name"]
                if fx["fixture"]["status"]["short"] in live:
                    for side in ("home","away"):
                        t=fx["teams"][side]; alive[str(t["id"])]=t["name"]
            progress["priority_teams"]=alive if alive else allt
            add_fixtures(resp,matches,progress["pending_fixtures"],progress["upcoming_raw"],str(WC_LEAGUE),True)
            print("  Selections prioritaires:",len(progress["priority_teams"]))
        for tid,name in list(progress["priority_teams"].items()):
            for s in PRIORITY_SEASONS:
                key=f"T{tid}_{s}"
                if progress["fixtures_done"].get(key): continue
                if not can_continue(used): raise Stop()
                resp=api_get("/fixtures",{"team":tid,"season":s},used)
                add_fixtures(resp,matches,progress["pending_fixtures"],progress["upcoming_raw"],None,True)
                progress["fixtures_done"][key]=True; time.sleep(SLEEP)
        for lid,label,cat,seasons in COMPETITIONS:
            for s in seasons:
                key=f"{lid}_{s}"
                if progress["fixtures_done"].get(key): continue
                if not can_continue(used): raise Stop()
                resp=api_get("/fixtures",{"league":lid,"season":s},used)
                add_fixtures(resp,matches,progress["pending_fixtures"],progress["upcoming_raw"],str(lid),False)
                progress["fixtures_done"][key]=True; time.sleep(SLEEP)
        seen=set(); pend=[]
        for it in progress["pending_fixtures"]:
            if it["fid"] in matches or it["fid"] in seen: continue
            seen.add(it["fid"]); pend.append(it)
        pend.sort(key=lambda x:x["date"],reverse=True); pend.sort(key=lambda x:0 if x.get("prio") else 1)
        for it in pend:
            if not can_continue(used): raise Stop()
            stats=api_get("/fixtures/statistics",{"fixture":it["fid"]},used)
            per={}
            for blk in stats:
                dd={}
                for s in blk["statistics"]: dd[s["type"]]=s["value"]
                per[blk["team"]["name"]]=dd
            matches[it["fid"]]={"date":it["date"],"lid":it["league"],"lname":it["lname"],"season":it["season"],
                "h":it["h"],"a":it["a"],"gh":it["gh"],"ga":it["ga"],
                "H":parse_side(per.get(it["h"],{})),"A":parse_side(per.get(it["a"],{}))}
            time.sleep(SLEEP)
    except Stop:
        print("  Pause (quota/plafond). Reprise au prochain run.")
    progress["pending_fixtures"]=[it for it in progress["pending_fixtures"] if it["fid"] not in matches]
    aggregate_and_write(matches, progress["upcoming_raw"])
    json.dump(progress,open(PROGRESS,"w",encoding="utf-8")); json.dump(matches,open(MATCHES,"w",encoding="utf-8"))
    print(f"  Requetes: {used[0]} | matchs: {len(matches)} | attente: {len(progress['pending_fixtures'])}")

def rec(opp,comp,season,home,gf,ga,me,opst):
    res="W" if gf>ga else ("D" if gf==ga else "L")
    d={"opp":opp,"comp":comp,"season":season,"home":home,"gf":gf,"ga":ga,"res":res,"a_ts":opst.get("ts",0),"a_sot":opst.get("sot",0),"a_xg":opst.get("xg")}
    for k in ("ts","sot","sib","sob","blk","poss","cor","fouls","off","yc","rc","sav","pas","pacc","ppct","xg"):
        d[k]=me.get(k,0)
    return d

def aggregate_and_write(matches, upcoming_raw):
    byteam={}; comps=set()
    for fid,m in matches.items():
        comps.add(m.get("lname",""))
        r1=rec(m["a"],m["lname"],m["season"],True,m["gh"],m["ga"],m["H"],m["A"]); r1["date"]=m["date"]
        r2=rec(m["h"],m["lname"],m["season"],False,m["ga"],m["gh"],m["A"],m["H"]); r2["date"]=m["date"]
        byteam.setdefault(m["h"],[]).append(r1)
        byteam.setdefault(m["a"],[]).append(r2)
    TEAMS={}
    for name,recs in byteam.items():
        recs.sort(key=lambda r:r["date"],reverse=True)
        up=[]
        for fid,u in upcoming_raw.items():
            if u["h"]==name: up.append({"date":u["date"],"opp":u["a"],"comp":u["lname"],"home":True})
            elif u["a"]==name: up.append({"date":u["date"],"opp":u["h"],"comp":u["lname"],"home":False})
        up.sort(key=lambda x:x["date"])
        TEAMS[name]={"matches":recs[:MAX_PER_TEAM],"upcoming":up[:8]}
    allts=[r["ts"] for t in TEAMS.values() for r in t["matches"]]
    la=round(mean(allts),1) if allts else 12.5
    comps=sorted([c for c in comps if c])
    payload=("// Genere automatiquement (GitHub Actions). Maj: "+datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M")+" UTC\n"
        "var LEAGUE_AVG = "+json.dumps(la)+";\n"
        "var COMPS = "+json.dumps(comps,ensure_ascii=False)+";\n"
        "var TEAMS = "+json.dumps(TEAMS,ensure_ascii=False)+";\n")
    open(OUTPUT,"w",encoding="utf-8").write(payload)
    print(f"  -> {OUTPUT}: {len(TEAMS)} equipes, {len(comps)} competitions.")

if __name__=="__main__":
    run()
