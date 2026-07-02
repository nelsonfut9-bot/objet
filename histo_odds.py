#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill de cotes historiques REELLES (cloture) depuis football-data.co.uk.
5 grands championnats, saisons 2020/21 -> 2025/26. Cotes Bet365 (fallback Pinnacle) :
1X2 + Over/Under 2.5. Resultats (score final + mi-temps) inclus dans les CSV.
Produit donnees_histo.js (var HISTO=[...]) consomme par app_cdm.html (onglet Suivi reel).
"""
import csv, io, json, os, re, unicodedata, urllib.request

BASE="https://www.football-data.co.uk/mmz4281"
SEASONS=[("2021",2020),("2122",2021),("2223",2022),("2324",2023),("2425",2024),("2526",2025)]
LEAGUES=[("E0","Premier League","39"),("SP1","La Liga","140"),("I1","Serie A","135"),
         ("D1","Bundesliga","78"),("F1","Ligue 1","61")]

ALIASES={
 "man united":"Manchester United","man city":"Manchester City","spurs":"Tottenham",
 "tottenham":"Tottenham","newcastle":"Newcastle","wolves":"Wolves","west ham":"West Ham",
 "west brom":"West Brom","sheffield united":"Sheffield Utd","nott'm forest":"Nottingham Forest",
 "nottm forest":"Nottingham Forest","luton":"Luton","leicester":"Leicester","leeds":"Leeds",
 "brighton":"Brighton","bournemouth":"Bournemouth","ipswich":"Ipswich","sunderland":"Sunderland",
 "ath madrid":"Atletico Madrid","ath bilbao":"Athletic Club","espanol":"Espanyol",
 "sociedad":"Real Sociedad","betis":"Real Betis","celta":"Celta Vigo","cadiz":"Cadiz",
 "alaves":"Alaves","vallecano":"Rayo Vallecano","valladolid":"Real Valladolid",
 "la coruna":"Deportivo La Coruna","mallorca":"Mallorca","las palmas":"Las Palmas",
 "leganes":"Leganes","girona":"Girona","elche":"Elche","oviedo":"Real Oviedo",
 "inter":"Inter","milan":"AC Milan","roma":"AS Roma","lazio":"Lazio","napoli":"Napoli",
 "juventus":"Juventus","atalanta":"Atalanta","fiorentina":"Fiorentina","verona":"Verona",
 "parma":"Parma","como":"Como","spezia":"Spezia","salernitana":"Salernitana",
 "bayern munich":"Bayern München","dortmund":"Borussia Dortmund","m'gladbach":"Borussia Monchengladbach",
 "mgladbach":"Borussia Monchengladbach","leverkusen":"Bayer Leverkusen","ein frankfurt":"Eintracht Frankfurt",
 "rb leipzig":"RB Leipzig","hoffenheim":"1899 Hoffenheim","mainz":"FSV Mainz 05","fc koln":"1. FC Köln",
 "koln":"1. FC Köln","augsburg":"FC Augsburg","stuttgart":"VfB Stuttgart","wolfsburg":"VfL Wolfsburg",
 "freiburg":"SC Freiburg","union berlin":"Union Berlin","bochum":"VfL BOCHUM","heidenheim":"1. FC Heidenheim",
 "darmstadt":"Darmstadt 98","st pauli":"FC St. Pauli","holstein kiel":"Holstein Kiel",
 "hertha":"Hertha Berlin","schalke 04":"FC Schalke 04","werder bremen":"Werder Bremen",
 "greuther furth":"SpVgg Greuther Furth","bielefeld":"Arminia Bielefeld","hamburg":"Hamburger SV",
 "paris sg":"Paris Saint Germain","marseille":"Marseille","lyon":"Lyon","monaco":"Monaco",
 "lille":"Lille","nice":"Nice","rennes":"Rennes","lens":"Lens","st etienne":"Saint Etienne",
 "clermont":"Clermont Foot","brest":"Stade Brestois 29","le havre":"Le Havre","reims":"Stade de Reims",
 "troyes":"Troyes","ajaccio":"Ajaccio","auxerre":"Auxerre","metz":"Metz","lorient":"Lorient",
 "montpellier":"Montpellier","nantes":"Nantes","strasbourg":"Strasbourg","toulouse":"Toulouse",
 "angers":"Angers","paris fc":"Paris FC",
}

def norm(s):
    s=unicodedata.normalize("NFD",str(s)).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9 ]","",s.lower()).strip()

def load_known():
    known={}
    if os.path.exists("matches.json"):
        ms=json.load(open("matches.json",encoding="utf-8"))
        for m in ms.values():
            for n in (m.get("h"),m.get("a")):
                if n: known[norm(n)]=n
    return known

def map_name(name,known):
    n=norm(name)
    if n in ALIASES: return ALIASES[n]
    if n in known: return known[n]
    # inclusion simple (ex: "real madrid" dans "real madrid cf")
    for k,v in known.items():
        if n and (n in k or k in n) and abs(len(k)-len(n))<=6: return v
    return name  # nom brut : le front l'ignorera si inconnu de TEAMS

def f(v):
    try: return float(v)
    except: return None

def i(v):
    try: return int(v)
    except: return None

def run():
    known=load_known()
    out=[]; unmapped=set()
    for code,comp,lid in LEAGUES:
        for scode,syear in SEASONS:
            url=f"{BASE}/{scode}/{code}.csv"
            try:
                raw=urllib.request.urlopen(url,timeout=60).read().decode("utf-8","ignore")
            except Exception as e:
                print("skip",url,e); continue
            rd=csv.DictReader(io.StringIO(raw))
            n=0
            for r in rd:
                if not r.get("HomeTeam"): continue
                d=r.get("Date","")
                parts=d.split("/")
                if len(parts)==3:
                    dd,mm,yy=parts
                    if len(yy)==2: yy="20"+yy
                    d=f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
                h1=f(r.get("B365H")) or f(r.get("PSH")); x=f(r.get("B365D")) or f(r.get("PSD")); a2=f(r.get("B365A")) or f(r.get("PSA"))
                o25=f(r.get("B365>2.5")) or f(r.get("P>2.5")); u25=f(r.get("B365<2.5")) or f(r.get("P<2.5"))
                if not (h1 and x and a2): continue
                hm=map_name(r["HomeTeam"],known); am=map_name(r["AwayTeam"],known)
                if norm(hm)==norm(r["HomeTeam"]) and norm(hm) not in known and norm(hm) not in [norm(k) for k in ALIASES.values()]:
                    unmapped.add(r["HomeTeam"])
                out.append({"d":d,"h":hm,"a":am,"comp":comp,"season":syear,
                    "fthg":i(r.get("FTHG")),"ftag":i(r.get("FTAG")),
                    "hthg":i(r.get("HTHG")),"htag":i(r.get("HTAG")),
                    "h1":h1,"x":x,"a2":a2,"o25":o25,"u25":u25})
                n+=1
            print(f"{comp} {syear}: {n} matchs")
    open("donnees_histo.js","w",encoding="utf-8").write(
        "// Cotes historiques reelles (football-data.co.uk, cloture Bet365/Pinnacle). Genere par histo_odds.py\n"
        "var HISTO = "+json.dumps(out,ensure_ascii=False)+";\n")
    print("total:",len(out),"matchs | noms non mappes:",len(unmapped))
    for u in sorted(unmapped)[:40]: print("  ?",u)

if __name__=="__main__":
    run()
