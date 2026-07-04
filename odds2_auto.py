#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Source de cotes n°2 : odds-api.io (gratuit). Croise les cotes d'API-Football.
- Ne tourne que si le secret ODDSAPI_IO_KEY est defini (sinon sortie silencieuse).
- Associe les matchs a venir de notre base (progress.json/upcoming_raw) aux events odds-api.io
  par noms d'equipes normalises + date.
- Recupere 1X2, double chance, totaux buts, BTTS, buts 1re MT aupres de plusieurs bookmakers
  et stocke le MEILLEUR prix dans odds.json sous la cle "alt" de chaque match.
Budget : ~90 requetes/run (limite gratuite 100/h, marge de securite).
"""
import json, os, re, sys, time, unicodedata, datetime

KEY=os.environ.get("ODDSAPI_IO_KEY","")
BASE="https://api.odds-api.io/v3"
ODDSFILE="odds.json"; PROGRESS="progress.json"
BUDGET=90; SLEEP=0.15
BOOKIES="Bet365,Pinnacle,Unibet,Bwin,William Hill"

def norm(s):
    s=unicodedata.normalize("NFD",str(s)).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]","",s.lower())

def load(p,d):
    if os.path.exists(p):
        try: return json.load(open(p,encoding="utf-8"))
        except: return d
    return d

_used=[0]
def get(path,params):
    import requests
    if _used[0]>=BUDGET: return None
    params=dict(params or {}); params["apiKey"]=KEY
    for attempt in range(3):
        try:
            r=requests.get(BASE+path,params=params,timeout=30)
            _used[0]+=1
            if r.status_code==429:
                print("  429 odds-api.io -> stop"); return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            time.sleep(1.0*(attempt+1))
    return None

def best(cands):
    """cands = [(odd, book), ...] -> {'odd':max,'book':...} ou None"""
    cands=[(o,b) for o,b in cands if isinstance(o,(int,float)) and o>1.001]
    if not cands: return None
    o,b=max(cands,key=lambda x:x[0])
    return {"odd":round(float(o),3),"book":b}

def parse_markets(payload):
    """Extrait le meilleur prix par marche utile depuis la reponse /odds (defensif : structures variables)."""
    mw_h=[];mw_d=[];mw_a=[];dc_1x=[];dc_x2=[];btts_y=[];btts_n=[];ou={};fh={}
    def walk_bookmaker(bname,markets):
        for mkt in markets or []:
            name=str(mkt.get("name") or mkt.get("market") or "").lower()
            odds=mkt.get("odds") or mkt.get("outcomes") or mkt.get("values") or []
            def val(o):
                try: return float(o.get("price") or o.get("odd") or o.get("odds"))
                except: return None
            def lab(o): return str(o.get("name") or o.get("label") or o.get("value") or "").lower().strip()
            def hdp(o):
                for k in ("hdp","line","handicap","points","total"):
                    if o.get(k) is not None:
                        try: return float(o.get(k))
                        except: pass
                m=re.search(r"(\d+(?:\.\d+)?)",lab(o))
                return float(m.group(1)) if m else None
            is_fh=("1st half" in name or "first half" in name or "1e mi" in name)
            if name in ("ml","match winner","1x2","full time result","match result","moneyline"):
                for o in odds:
                    l=lab(o);v=val(o)
                    if v is None:continue
                    if l in("1","home"):mw_h.append((v,bname))
                    elif l in("x","draw"):mw_d.append((v,bname))
                    elif l in("2","away"):mw_a.append((v,bname))
            elif "double chance" in name:
                for o in odds:
                    l=lab(o).replace(" ","");v=val(o)
                    if v is None:continue
                    if l in("1x","home/draw","homeordraw"):dc_1x.append((v,bname))
                    elif l in("x2","draw/away","draworaway"):dc_x2.append((v,bname))
            elif "both teams" in name or name=="btts":
                for o in odds:
                    l=lab(o);v=val(o)
                    if v is None:continue
                    if l in("yes","oui"):btts_y.append((v,bname))
                    elif l in("no","non"):btts_n.append((v,bname))
            elif ("over/under" in name or "total" in name or "totals" in name) and "corner" not in name and "card" not in name and "team" not in name:
                tgt=fh if is_fh else ou
                for o in odds:
                    l=lab(o);v=val(o);ln=hdp(o)
                    if v is None or ln is None:continue
                    e=tgt.setdefault(ln,{})
                    if l.startswith("over") or l=="o":
                        if v>(e.get("over") or {}).get("odd",0): e["over"]={"odd":v,"book":bname}
                    elif l.startswith("under") or l=="u":
                        if v>(e.get("under") or {}).get("odd",0): e["under"]={"odd":v,"book":bname}
    # formats possibles : {bookmakers:[{name,markets:[...]}]} ou liste directe
    if isinstance(payload,dict):
        for bk in payload.get("bookmakers") or []:
            walk_bookmaker(bk.get("name","?"),bk.get("markets") or bk.get("odds"))
    elif isinstance(payload,list):
        for bk in payload:
            if isinstance(bk,dict):
                walk_bookmaker(bk.get("bookmaker") or bk.get("name","?"),bk.get("markets") or [bk])
    out={}
    if best(mw_h):out["mw"]={"home":best(mw_h),"draw":best(mw_d),"away":best(mw_a)}
    if best(dc_1x) or best(dc_x2):out["dc"]={"1X":best(dc_1x),"X2":best(dc_x2)}
    if best(btts_y):out["btts"]={"yes":best(btts_y),"no":best(btts_n)}
    if ou:out["ou"]={str(k):v for k,v in ou.items() if v}
    if fh:out["fh"]={str(k):v for k,v in fh.items() if v}
    return out or None

def run():
    if not KEY:
        print("ODDSAPI_IO_KEY absent : source n°2 desactivee (rien a faire)."); return
    progress=load(PROGRESS,{}); odds=load(ODDSFILE,{})
    upcoming=progress.get("upcoming_raw",{})
    today=datetime.date.today().isoformat()
    horizon=(datetime.date.today()+datetime.timedelta(days=3)).isoformat()
    # cible : matchs a venir sous 3 jours, sans cotes alt fraiches (<6h)
    now=time.time()
    targets=[]
    for fid,u in upcoming.items():
        if not (today<=u.get("date","")<=horizon): continue
        prev=(odds.get(fid) or {}).get("alt") or {}
        if prev.get("_ts") and now-prev["_ts"]<6*3600: continue
        targets.append((fid,u))
    targets.sort(key=lambda x:x[1].get("date",""))
    if not targets:
        print("Aucun match a croiser."); return
    # 1 requete : tous les events football a venir (14 jours)
    events=get("/events",{"sport":"football","limit":5000}) or []
    if isinstance(events,dict): events=events.get("events") or events.get("data") or []
    idx={}
    for ev in events:
        try:
            h=ev.get("home") or (ev.get("participants") or [{}])[0].get("name") or ev.get("homeTeam")
            a=ev.get("away") or (ev.get("participants") or [{},{}])[1].get("name") or ev.get("awayTeam")
            if isinstance(h,dict):h=h.get("name")
            if isinstance(a,dict):a=a.get("name")
            d=str(ev.get("date") or ev.get("startTime") or ev.get("starts") or "")[:10]
            if h and a and d: idx[(norm(h),norm(a),d)]=ev.get("id") or ev.get("eventId")
        except: continue
    print(f"events odds-api.io: {len(idx)} indexes | cibles: {len(targets)}")
    matched=0;fetched=0
    for fid,u in targets:
        if _used[0]>=BUDGET-2: break
        key=(norm(u["h"]),norm(u["a"]),u["date"])
        eid=idx.get(key)
        if not eid:
            # tolerance : meme date, noms partiels
            for (nh,na,dd),e in idx.items():
                if dd==u["date"] and (key[0] in nh or nh in key[0]) and (key[1] in na or na in key[1]):
                    eid=e;break
        if not eid: continue
        matched+=1
        payload=get("/odds",{"eventId":eid,"bookmakers":BOOKIES})
        time.sleep(SLEEP)
        if payload is None: break
        alt=parse_markets(payload)
        if not alt: continue
        alt["_ts"]=int(now)
        entry=odds.get(fid) or {"h":u["h"],"a":u["a"],"date":u["date"],"markets":{},"which":{}}
        entry["alt"]=alt
        odds[fid]=entry
        fetched+=1
    json.dump(odds,open(ODDSFILE,"w",encoding="utf-8"),ensure_ascii=False)
    print(f"croises: {matched} | cotes alt ecrites: {fetched} | requetes: {_used[0]}")

if __name__=="__main__":
    run()
