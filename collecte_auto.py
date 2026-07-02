#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR INCREMENTAL — toutes stats par match, fiches d'equipe (type Sofascore).
PRIORITE : selections encore en lice au Mondial 2026 + leur historique depuis 2020.
Puis backfill 5 grands championnats + coupes + Europe + amicaux + championnats d'ete actifs.
Incremental (progress.json/matches.json), quota-aware. Cle = secret GitHub.
"""
import json, os, sys, time, math, datetime

API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
OUTPUT   = "donnees_cdm.js"; PROGRESS="progress.json"; MATCHES="matches.json"
SAFETY_MARGIN=60; MAX_RUN=2000; MAX_PER_TEAM=400; SLEEP=0.10  # MAX_RUN volontairement bas : on sauvegarde souvent (checkpoints)
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
    # championnats a saison calendaire, actifs en ete (ajout 07/2026)
    (253,"MLS","club",[2020,2021,2022,2023,2024,2025,2026]),
    (71,"Brasileirao Serie A","club",[2020,2021,2022,2023,2024,2025,2026]),
    (128,"Liga Profesional Argentina","club",[2020,2021,2022,2023,2024,2025,2026]),
    (103,"Eliteserien","club",[2020,2021,2022,2023,2024,2025,2026]),
    (113,"Allsvenskan","club",[2020,2021,2022,2023,2024,2025,2026]),
    (244,"Veikkausliiga","club",[2020,2021,2022,2023,2024,2025,2026]),
    (98,"J1 League","club",[2020,2021,2022,2023,2024,2025,2026]),
    (292,"K League 1","club",[2020,2021,2022,2023,2024,2025,2026]),
    (357,"Premier Division Irlande","club",[2020,2021,2022,2023,2024,2025,2026]),
    (164,"Besta deild Islande","club",[2020,2021,2022,2023,2024,2025,2026]),
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
    last=None
    for attempt in range(4):
        try:
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
        except Stop:
            raise
        except Exception as e:
            last=e; time.sleep(1.5*(attempt+1))  # erreur reseau transitoire -> on retente
    # apres plusieurs echecs reseau : on s'arrete proprement (les donnees deja collectees seront sauvegardees)
    print("  ! reseau (abandon apres retries):",last); raise Stop()
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
        if st in ("FT","AET","PEN"):  # FT + prolongation (AET) + tirs au but (PEN) = match termine
            if fid in matches: continue
            pending.append({"fid":fid,"date":fx["fixture"]["date"][:10],"dt":fx["fixture"]["date"],"h":h,"a":a,
                "league":str(lid),"lname":lg.get("name",""),"season":lg.get("season",""),
                "gh":fx.get("goals",{}).get("home") or 0,"ga":fx.get("goals",{}).get("away") or 0,"prio":prio})
        elif st in ("NS","TBD"):
            upcoming_raw[fid]={"date":fx["fixture"]["date"][:10],"time":fx["fixture"]["date"],"h":h,"a":a,"lname":lg.get("name","")}

ODDSFILE="odds.json"
ODDS_MARKETS={"total shots","shots. home total","shots. away total","total shotongoal",
    "home total shotongoal","away total shotongoal","home shots on target","away shots on target",
    "goals over/under","corners over under","total - corners","total corners",
    "cards over/under","total cards","total - cards"}
BTTS_MARKETS={"both teams score","both teams to score"}
def _parse_btts(values):
    d={}
    for v in (values or []):
        val=str(v.get("value","")).lower().strip(); od=v.get("odd")
        try: od=float(od)
        except: continue
        if val in ("yes","oui"): d["yes"]=od
        elif val in ("no","non"): d["no"]=od
    return d if ("yes" in d and "no" in d) else None
# marches "quelle equipe tire le plus" (3 issues : domicile / nul / exterieur)
WHICH_MARKETS={"shots.1x2":"shots","shotontarget 1x2":"sot","match winner":"mw"}
DC_MARKETS={"double chance"}
def _parse_dc(values):
    d={}
    for v in (values or []):
        val=str(v.get("value","")).lower().replace(" ",""); od=v.get("odd")
        try: od=float(od)
        except: continue
        if val in ("home/draw","1x"): d["1X"]=od
        elif val in ("draw/away","x2"): d["X2"]=od
        elif val in ("home/away","12"): d["12"]=od
    return d if d else None
def _parse_1x2(values):
    d={}
    for v in (values or []):
        val=str(v.get("value","")).lower().strip(); od=v.get("odd")
        try: od=float(od)
        except: continue
        if val in ("home","1"): d["home"]=od
        elif val in ("away","2"): d["away"]=od
        elif val in ("draw","x","égal","egal"): d["draw"]=od
    return d if ("home" in d and "away" in d) else None
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
    """Recupere les marches tirs/cadres (O/U) + 'quelle equipe tire le plus' (1x2). None si quota/stop."""
    try: resp=api_get("/odds",{"fixture":fid},used)
    except Stop: return None
    time.sleep(SLEEP)
    markets={}; which={}
    for blk in resp:
        for bk in blk.get("bookmakers",[]):
            bname=bk.get("name")
            for bet in bk.get("bets",[]):
                nm=(bet.get("name") or ""); low=nm.lower()
                if low in ODDS_MARKETS:
                    rows=_parse_ou(bet.get("values"))
                    if not rows: continue
                    if (nm not in markets) or (bname in ("Pinnacle","Bet365")):
                        markets[nm]={"book":bname,"rows":rows,"bl":_balanced(rows)}
                elif low in WHICH_MARKETS:
                    row=_parse_1x2(bet.get("values"))
                    if not row: continue
                    k=WHICH_MARKETS[low]
                    if (k not in which) or (bname in ("Pinnacle","Bet365")):
                        row["book"]=bname; which[k]=row
                elif low in DC_MARKETS:
                    dcr=_parse_dc(bet.get("values"))
                    if not dcr: continue
                    if ("dc" not in which) or (bname in ("Pinnacle","Bet365")):
                        dcr["book"]=bname; which["dc"]=dcr
                elif low in BTTS_MARKETS:
                    bt=_parse_btts(bet.get("values"))
                    if not bt: continue
                    if ("btts" not in which) or (bname in ("Pinnacle","Bet365")):
                        bt["book"]=bname; which["btts"]=bt
    return (markets, which)

def collect_odds(upcoming_raw, recent_ft, used, up_limit=40, rc_limit=120):
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
        res=_fetch_markets(fid, used)
        if res is None: break
        markets, which = res
        if markets or which:  # on n'ecrase jamais des cotes existantes par du vide (match deja joue)
            prev=odds.get(fid) or {}
            entry={"h":u.get("h"),"a":u.get("a"),"date":u.get("date"),"markets":markets,"which":which,"t1":now_iso}
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
    # one-time : re-tente les championnats de clubs (marques "faits" auparavant mais revenus vides)
    if not progress.get("clubs_retry_v4"):
        _club_ids=set(str(_l) for _l,_lab,_c,_s in COMPETITIONS if _c=="club")
        for _k in list(progress.get("fixtures_done",{}).keys()):
            if _k.split("_")[0] in _club_ids:
                progress["fixtures_done"].pop(_k,None)
        progress["clubs_retry_v4"]=True
        print("  Reset des championnats de clubs : re-collecte forcee.")
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
        # ===== PRIORITE 1 : RESULTATS RECENTS =====
        # matchs "a venir" dont la date est passee -> on recupere le resultat (calendriers en cache sinon)
        today_s=datetime.date.today().isoformat()
        due=[(fid,u) for fid,u in list(progress["upcoming_raw"].items()) if u.get("date","")<=today_s and fid not in matches]
        for fid,u in due[:60]:
            if not can_continue(used): raise Stop()
            resp=api_get("/fixtures",{"id":fid},used)
            add_fixtures(resp,matches,progress["pending_fixtures"],progress["upcoming_raw"],None,True)
            time.sleep(SLEEP)
        # ===== PRIORITE 2 : COTES (rafraichies a CHAQUE passage, AVANT le backfill) =====
        recent_ft={}
        try:
            cutoff=(datetime.date.today()-datetime.timedelta(days=14)).isoformat()
            cutoff_wc=(datetime.date.today()-datetime.timedelta(days=90)).isoformat()
        except:
            cutoff="0000-00-00"; cutoff_wc="0000-00-00"
        for fid,m in matches.items():
            d=m.get("date",""); ln=(m.get("lname") or "")
            iswc=(str(m.get("lid"))=="1") or ("World Cup" in ln) or ("Coupe du Monde" in ln)
            if (iswc and d>=cutoff_wc) or d>=cutoff:
                recent_ft[fid]={"h":m.get("h"),"a":m.get("a"),"date":m.get("date"),"wc":iswc}
        odds=collect_odds(progress["upcoming_raw"], recent_ft, used)
        # ===== PRIORITE 3 : STATS des matchs en attente (recents/selections d'abord) =====
        seen=set(); pend=[]
        for it in progress["pending_fixtures"]:
            if it["fid"] in matches or it["fid"] in seen: continue
            seen.add(it["fid"]); pend.append(it)
        pend.sort(key=lambda x:x["date"],reverse=True)
        _p=[it for it in pend if it.get("prio")]; _o=[it for it in pend if not it.get("prio")]
        pend=[]; pi=oi=0
        while pi<len(_p) or oi<len(_o):
            if pi<len(_p): pend.append(_p[pi]); pi+=1
            if oi<len(_o): pend.append(_o[oi]); oi+=1
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
        # ===== PRIORITE 4 : BACKFILL des calendriers (EN DERNIER) : selections + clubs en alternance =====
        nat_tasks=[]
        for tid,name in list(progress["priority_teams"].items()):
            for s in PRIORITY_SEASONS:
                nat_tasks.append(("T%s_%s"%(tid,s), {"team":tid,"season":s}, None, True))
        club_tasks=[]
        for lid,label,cat,seasons in COMPETITIONS:
            for s in seasons:
                club_tasks.append(("%s_%s"%(lid,s), {"league":lid,"season":s}, str(lid), False))
        fixture_tasks=[]; i=j=0
        while i<len(nat_tasks) or j<len(club_tasks):
            if j<len(club_tasks): fixture_tasks.append(club_tasks[j]); j+=1
            if i<len(nat_tasks): fixture_tasks.append(nat_tasks[i]); i+=1
        for key,params,lid,prio in fixture_tasks:
            if progress["fixtures_done"].get(key): continue
            if not can_continue(used): raise Stop()
            resp=api_get("/fixtures",params,used)
            add_fixtures(resp,matches,progress["pending_fixtures"],progress["upcoming_raw"],lid,prio)
            if resp: progress["fixtures_done"][key]=True
            time.sleep(SLEEP)
    except Stop:
        print("  Pause (quota/plafond/reseau). Reprise au prochain run.")
    except Exception as e:
        import traceback; print("  ! erreur inattendue, sauvegarde partielle:",e); traceback.print_exc()
    # on sauvegarde TOUJOURS ce qui a ete collecte (meme apres une erreur)
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
