#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR CLOUD (GitHub Actions) — Coupe du Monde.
La cle API est lue depuis un SECRET GitHub (variable d'environnement
API_FOOTBALL_KEY) : elle n'apparait JAMAIS dans le code.
Genere donnees_cdm.js. Voir GUIDE_github.md pour la mise en place.
"""
import json, os, sys, time, math, datetime

# --- la cle vient du secret GitHub, pas du code ---
API_KEY   = os.environ.get("API_FOOTBALL_KEY", "")
LEAGUE_ID = 1          # 1 = Coupe du Monde. (Plus tard : boucler sur plusieurs ligues.)
SEASON    = 2022       # gratuit = 2022-2024. Passe a 2026 quand tu es en plan Pro.
BASE_URL  = "https://v3.football.api-sports.io"
MAX_PAST  = 12
OUTPUT    = "donnees_cdm.js"
XG_REF    = 0.11

CONF = {
    "Mexico":"nation_concacaf","USA":"nation_concacaf","Canada":"nation_concacaf",
    "Brazil":"nation_conmebol","Argentina":"nation_conmebol","Uruguay":"nation_conmebol",
    "France":"nation_uefa","Spain":"nation_uefa","England":"nation_uefa",
    "Germany":"nation_uefa","Portugal":"nation_uefa","Netherlands":"nation_uefa",
    "Croatia":"nation_uefa","Belgium":"nation_uefa","Italy":"nation_uefa",
    "Morocco":"nation_caf","Senegal":"nation_caf","Egypt":"nation_caf",
    "South Africa":"nation_caf","Japan":"nation_afc","South Korea":"nation_afc",
}
LEAGUE_AVG = 12.8

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

def predict_shots(team, opp, is_home, comp_mult=1.02):
    sf=team["sf"]
    if not sf: return 0,1.7,{"line":0,"side":"over","prob":50}
    attack=0.6*mean(sf[:5])+0.4*mean(sf)
    opp_cd=mean(opp["cd"]) if opp["cd"] else LEAGUE_AVG
    exp=attack*(0.5+0.5*(opp_cd/LEAGUE_AVG))*(1.12 if is_home else 0.96)*comp_mult
    sd=max(std(sf),1.7)
    return round(exp,1),round(sd,1),reco(exp,sd)

class RateLimited(Exception): pass
def api_get(path, params):
    import requests
    r=requests.get(BASE_URL+path, headers={"x-apisports-key":API_KEY}, params=params, timeout=30)
    if r.status_code==429: raise RateLimited()
    r.raise_for_status(); data=r.json()
    if data.get("errors"): print("  ! API:", data["errors"])
    return data.get("response", [])

def collect_real():
    print("Connexion API-Football (saison", SEASON, ")...")
    try:
        fixtures=api_get("/fixtures", {"league":LEAGUE_ID,"season":SEASON})
    except RateLimited:
        print("  Quota atteint (429)."); return {}, [], []
    print(f"  {len(fixtures)} matchs.")
    teams={}; finished=[]; upcoming=[]
    def ensure(n):
        teams.setdefault(n, {"type":"nation","cat":CONF.get(n,"nation_uefa"),
            "sf":[],"sot":[],"cd":[],"xgf":[],"xga":[],"pos":50,
            "style":"-","press":"-","bloc":"-","top":False})
        return teams[n]
    fixtures.sort(key=lambda f: f["fixture"]["date"])
    for fx in fixtures:
        st=fx["fixture"]["status"]["short"]
        ensure(fx["teams"]["home"]["name"]); ensure(fx["teams"]["away"]["name"])
        if st=="FT": finished.append(fx)
        elif st in ("NS","TBD"): upcoming.append(fx)
    for fx in finished:
        fid=fx["fixture"]["id"]; h=fx["teams"]["home"]["name"]; a=fx["teams"]["away"]["name"]
        try:
            stats=api_get("/fixtures/statistics", {"fixture":fid})
        except RateLimited:
            print("  Quota atteint en cours — donnees partielles."); break
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
        hs,as_=iv(h,"Total Shots"),iv(a,"Total Shots")
        hsot,asot=iv(h,"Shots on Goal"),iv(a,"Shots on Goal")
        hxg,axg=fv(h,"expected_goals"),fv(a,"expected_goals")
        teams[h]["sf"].insert(0,hs); teams[h]["sot"].insert(0,hsot); teams[h]["cd"].insert(0,as_)
        teams[a]["sf"].insert(0,as_); teams[a]["sot"].insert(0,asot); teams[a]["cd"].insert(0,hs)
        teams[h]["xgf"].insert(0,hxg); teams[h]["xga"].insert(0,axg)
        teams[a]["xgf"].insert(0,axg); teams[a]["xga"].insert(0,hxg)
        fx["_shots"]={"home":hs,"away":as_}
        time.sleep(0.2)
    for t in teams.values():
        for k in ("sf","sot","cd","xgf","xga"): t[k]=t[k][:MAX_PAST]
    return teams, finished, upcoming

def build_upcoming(teams, upcoming):
    out=[]
    for fx in upcoming[:12]:
        h=fx["teams"]["home"]["name"]; a=fx["teams"]["away"]["name"]
        if not teams[h]["sf"] or not teams[a]["sf"]: continue
        out.append({"date":fx["fixture"]["date"][:10],"home":h,"away":a,"comp":"wc","market":"tirs",
            "ctx":{"meteo":"normal","repos":"normal","effectif":"complet"},
            "media":[{"src":"API-Football","v":True,"tag":"Info","txt":"Donnees live."}]})
    return out

def build_history(teams, finished):
    out=[]
    for fx in finished[-16:]:
        if "_shots" not in fx: continue
        h=fx["teams"]["home"]["name"]; a=fx["teams"]["away"]["name"]; real=fx["_shots"]["home"]
        sf=[x for x in teams[h]["sf"]]
        if real in sf: sf.remove(real)
        if len(sf)<3: continue
        exp,sd,rc=predict_shots({"sf":sf,"cd":teams[h]["cd"]}, teams[a], True)
        lbl=("OVER " if rc["side"]=="over" else "UNDER ")+str(rc["line"]).replace(".",",")
        out.append([fx["fixture"]["date"][:10], f"{h} - {a}", "tirs", lbl, exp,
                    [round(exp-0.85*sd),round(exp+0.85*sd)], real, rc["prob"]])
    return out

def write_data(teams, upcoming, history, league_avg):
    p=("// Genere automatiquement (GitHub Actions) — ne pas editer.\n"
       "// Source : API-Football. Mise a jour : "+datetime.datetime.now().strftime("%d/%m/%Y %H:%M")+" UTC\n"
       "var LEAGUE_AVG = "+json.dumps(round(league_avg,1))+";\n"
       "var TEAMS = "+json.dumps(teams, ensure_ascii=False, indent=1)+";\n"
       "var UPCOMING = "+json.dumps(upcoming, ensure_ascii=False, indent=1)+";\n"
       "var HISTORY = "+json.dumps(history, ensure_ascii=False, indent=1)+";\n")
    open(OUTPUT,"w",encoding="utf-8").write(p)
    print(f"OK -> {OUTPUT} ({len(teams)} equipes, {len(upcoming)} a venir, {len(history)} historique).")

def main():
    if not API_KEY:
        print("ERREUR : secret API_FOOTBALL_KEY manquant."); sys.exit(1)
    teams,finished,up=collect_real()
    allsf=[v for t in teams.values() for v in t["sf"]]
    la=mean(allsf) if allsf else LEAGUE_AVG
    write_data(teams, build_upcoming(teams,up), build_history(teams,finished), la)

if __name__=="__main__":
    main()
