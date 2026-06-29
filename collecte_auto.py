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
SAFETY_MARGIN=60; MAX_RUN=40000; MAX_PER_TEAM=80; SLEEP=0.10
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

INT_STATS={"Total Shots":"ts","Shots on Goal":"sot","Shots off Goal":"sog","Shots insidebox":"sib","Shots outsidebox":"sob",
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
            pending.append({"fid":fid,"date":fx["fixture"]["date"][:10],"dt":fx["fixture"]["date"],"h":h,"a":a,
                "league":str(lid),"lname":lg.get("name",""),"season":lg.get("season",""),
                "gh":fx.get("goals",{}).get("home") or 0,"ga":fx.get("goals",{}).get("away") or 0,"prio":prio})
        elif st in ("NS","TBD"):
            upcoming_raw[fid]={"date":fx["fixture"]["date"][:10],"time":fx["fixture"]["date"],"h":h,"a":a,"lname":lg.get("name","")}

ODDSFILE="odds.json"
ODDS_MARKETS={"total shots","shots. home total","shots. away total","total shotongoal",
    "home total shotongoal","away total shotongoal","home shots on target","away shots on target",
    "goals over/under","corners over under","total corners","total - corners",
    "cards over/under","total cards","total - cards"}
def _parse_ou(values):
    over={}; under={}
    for v in (values or []):
        val=str(v.get("value","")); od=v.get("odd")
        try: od=float(od)
        except: continue
        parts=val.replace(":"," ").split()
        if len(parts)<2: continue
        side=parts[0].lower()
        try: ln=float(parts[-1].replace(",","."))
        except: continue
        if side.startswith("o"): over[ln]=od
        elif side.startswith("u"): under[ln]=od
    rows=[]
    for ln in sorted(set(list(over.keys())+list(under.keys()))):
        if ln in over and ln in under: rows.append([ln,over[ln],under[ln]])
    return rows
def _balanced(rows):
    pts=[]
    for ln,oo,uu in rows:
        io=1.0/oo; iu=1.0/uu; pts.append((ln, io/(io+iu)))
    pts.sort()
    for i in range(len(pts)-1):
        a=pts[i]; b=pts[i+1]
        if a[1]>=0.5>=b[1]:
            t=(a[1]-0.5)/(a[1]-b[1]) if a[1]!=b[1] else 0.0
            return round(a[0]+t*(b[0]-a[0]),1)
    return None
def _fetch_markets(fid, used):
    """Recupere les marches tirs/tirs cadres pour une fixture. None si quota/stop."""
    try: resp=api_get("/odds",{"fixture":fid},used)
    except Stop: return None
    time.sleep(SLEEP)
    markets={}
    for blk in resp:
        for bk in blk.get("bookmakers",[]):
            bname=bk.get("name")
            for bet in bk.get("bets",[]):
                nm=(bet.get("name") or "")
                if nm.lower() in ODDS_MARKETS:
                    rows=_parse_ou(bet.get("values"))
                    if not rows: continue
                    if (nm not in markets) or (bname in ("Pinnacle","Bet365")):
                        markets[nm]={"book":bname,"rows":rows,"bl":_balanced(rows)}
    return markets

def collect_odds(upcoming_raw, recent_ft, used, up_limit=40, rc_limit=40):
    """Cotes des matchs a venir (rafraichies a chaque run pour approcher les cotes de cloture)
    + cotes des matchs recents joues, captees une seule fois (seed historique de la bankroll).
    Les matchs de Coupe du Monde sont traites en priorite."""
    odds=load_json(ODDSFILE,{})
    up_items=sorted(upcoming_raw.items(), key=lambda kv: kv[1].get("date",""))[:up_limit]
    # matchs recents joues sans cotes : Coupe du Monde d'abord, puis du plus recent au plus ancien
    cand=[(fid,u) for fid,u in recent_ft.items() if fid not in odds]
    cand.sort(key=lambda x: x[1].get("date",""), reverse=True)
    cand.sort(key=lambda x: 0 if x[1].get("wc") else 1)
    rc_items=cand[:rc_limit]
    now_iso=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for fid,u in up_items+rc_items:
        if not can_continue(used): break
        markets=_fetch_markets(fid, used)
        if markets is None: break
        if markets:  # on n'ecrase jamais des cotes existantes par du vide (match deja joue)
            prev=odds.get(fid) or {}
            entry={"h":u.get("h"),"a":u.get("a"),"date":u.get("date"),"markets":markets,"t1":now_iso}
            # CLV : on conserve le tout premier releve de cotes (ouverture)
            if prev.get("open"):
                entry["open"]=prev["open"]; entry["t0"]=prev.get("t0",now_iso)
            else:
                entry["open"]=markets; entry["t0"]=now_iso
            odds[fid]=entry
    json.dump(odds,open(ODDSFILE,"w",encoding="utf-8"))
    return odds

def run():
    if not API_KEY: print("ERREUR : secret API_FOOTBALL_KEY manquant."); sys.exit(1)
    progress=load_json(PROGRESS,{})
    progress.setdefault("priority_teams",{}); progress.setdefault("fixtures_done",{})
    progress.setdefault("pending_fixtures",[]); progress.setdefault("upcoming_raw",{})
    matches=load_json(MATCHES,{}); used=[0]; odds=load_json(ODDSFILE,{})
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
            matches[it["fid"]]={"date":it["date"],"dt":it.get("dt"),"lid":it["league"],"lname":it["lname"],"season":it["season"],
                "h":it["h"],"a":it["a"],"gh":it["gh"],"ga":it["ga"],
                "H":parse_side(per.get(it["h"],{})),"A":parse_side(per.get(it["a"],{}))}
            time.sleep(SLEEP)
        # nettoie les matchs deja joues de la liste "a venir"
        for fid in [k for k in progress["upcoming_raw"] if k in matches]:
            progress["upcoming_raw"].pop(fid, None)
        # matchs recents joues -> tentative de captation des cotes pour la bankroll
        # fenetre large pour la Coupe du Monde (en cours), plus courte pour le reste
        recent_ft={}
        try:
            cutoff=(datetime.date.today()-datetime.timedelta(days=12)).isoformat()
            cutoff_wc=(datetime.date.today()-datetime.timedelta(days=90)).isoformat()
        except:
            cutoff="0000-00-00"; cutoff_wc="0000-00-00"
        for fid,m in matches.items():
            d=m.get("date",""); ln=(m.get("lname") or "")
            iswc=(str(m.get("lid"))=="1") or ("World Cup" in ln) or ("Coupe du Monde" in ln)
            if (iswc and d>=cutoff_wc) or d>=cutoff:
                recent_ft[fid]={"h":m.get("h"),"a":m.get("a"),"date":m.get("date"),"wc":iswc}
        odds=collect_odds(progress["upcoming_raw"], recent_ft, used)
    except Stop:
        print("  Pause (quota/plafond). Reprise au prochain run.")
    progress["pending_fixtures"]=[it for it in progress["pending_fixtures"] if it["fid"] not in matches]
    aggregate_and_write(matches, progress["upcoming_raw"], odds)
    json.dump(progress,open(PROGRESS,"w",encoding="utf-8")); json.dump(matches,open(MATCHES,"w",encoding="utf-8"))
    print(f"  Requetes: {used[0]} | matchs: {len(matches)} | attente: {len(progress['pending_fixtures'])}")

def rec(opp,comp,season,home,gf,ga,me,opst):
    res="W" if gf>ga else ("D" if gf==ga else "L")
    d={"opp":opp,"comp":comp,"season":season,"home":home,"gf":gf,"ga":ga,"res":res,"a_ts":opst.get("ts",0),"a_sot":opst.get("sot",0),"a_xg":opst.get("xg")}
    STK=("ts","sot","sog","sib","sob","blk","poss","cor","fouls","off","yc","rc","sav","pas","pacc","ppct","xg")
    for k in STK:
        d[k]=me.get(k,0)
    d["o"]={k:opst.get(k,0) for k in STK}
    return d

def aggregate_and_write(matches, upcoming_raw, odds=None):
    byteam={}; comps=set()
    for fid,m in matches.items():
        comps.add(m.get("lname",""))
        r1=rec(m["a"],m["lname"],m["season"],True,m["gh"],m["ga"],m["H"],m["A"]); r1["date"]=m["date"]; r1["dt"]=m.get("dt")
        r2=rec(m["h"],m["lname"],m["season"],False,m["ga"],m["gh"],m["A"],m["H"]); r2["date"]=m["date"]; r2["dt"]=m.get("dt")
        byteam.setdefault(m["h"],[]).append(r1)
        byteam.setdefault(m["a"],[]).append(r2)
    TEAMS={}
    for name,recs in byteam.items():
        recs.sort(key=lambda r:r["date"],reverse=True)
        up=[]
        for fid,u in upcoming_raw.items():
            if u["h"]==name: up.append({"date":u["date"],"time":u.get("time"),"opp":u["a"],"comp":u["lname"],"home":True})
            elif u["a"]==name: up.append({"date":u["date"],"time":u.get("time"),"opp":u["h"],"comp":u["lname"],"home":False})
        up.sort(key=lambda x:x["date"])
        TEAMS[name]={"matches":recs[:MAX_PER_TEAM],"upcoming":up[:8]}
    allts=[r["ts"] for t in TEAMS.values() for r in t["matches"]]
    la=round(mean(allts),1) if allts else 12.5
    comps=sorted([c for c in comps if c])
    # categorie par competition (nation / club) pour le filtre en cascade du site
    club_lids={str(_lid) for _lid,_label,_cat,_seasons in COMPETITIONS if _cat=="club"}
    comp_cat={}
    for fid,m in matches.items():
        ln=m.get("lname","")
        if ln: comp_cat[ln]="club" if str(m.get("lid")) in club_lids else "nation"
    payload=("// Genere automatiquement (GitHub Actions). Maj: "+datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M")+" UTC\n"
        "var GENERATED = "+json.dumps(datetime.datetime.now(datetime.timezone.utc).isoformat())+";\n"
        "var LEAGUE_AVG = "+json.dumps(la)+";\n"
        "var COMPS = "+json.dumps(comps,ensure_ascii=False)+";\n"
        "var COMP_CAT = "+json.dumps(comp_cat,ensure_ascii=False)+";\n"
        "var TEAMS = "+json.dumps(TEAMS,ensure_ascii=False)+";\n"
        "var ODDS = "+json.dumps(odds or {},ensure_ascii=False)+";\n")
    open(OUTPUT,"w",encoding="utf-8").write(payload)
    print(f"  -> {OUTPUT}: {len(TEAMS)} equipes, {len(comps)} competitions.")

if __name__=="__main__":
    run()
