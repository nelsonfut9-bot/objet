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

def _f(x):
    try: return float(x)
    except: return None

def parse_markets(ev):
    """ev = reponse /odds pour UN event : {'bookmakers': {book: [ {name, odds:[{...}]} ]}}"""
    mw_h=[];mw_d=[];mw_a=[];dc_1x=[];dc_x2=[];btts_y=[];btts_n=[];ou={};fh={}
    bks=ev.get("bookmakers") or {}
    if isinstance(bks,list):  # tolerance si liste
        bks={ (b.get("name") or "?"): (b.get("markets") or []) for b in bks if isinstance(b,dict)}
    for bname,markets in bks.items():
        for mkt in markets or []:
            name=str(mkt.get("name") or "").lower()
            rows=mkt.get("odds") or []
            is_fh=("1st" in name or "first half" in name)
            if name in ("ml","match winner","1x2","full time result","match result") and not is_fh:
                for o in rows:
                    if _f(o.get("home")):mw_h.append((_f(o.get("home")),bname))
                    if _f(o.get("draw")):mw_d.append((_f(o.get("draw")),bname))
                    if _f(o.get("away")):mw_a.append((_f(o.get("away")),bname))
            elif "double chance" in name:
                for o in rows:
                    for k,v in o.items():
                        kk=str(k).lower().replace("_","").replace("-","").replace(" ","")
                        vv=_f(v)
                        if vv is None:continue
                        if kk in ("1x","homedraw","homeordraw"):dc_1x.append((vv,bname))
                        elif kk in ("x2","drawaway","draworaway"):dc_x2.append((vv,bname))
            elif "both teams" in name or name=="btts":
                for o in rows:
                    if _f(o.get("yes")):btts_y.append((_f(o.get("yes")),bname))
                    if _f(o.get("no")):btts_n.append((_f(o.get("no")),bname))
            elif "over/under" in name or name=="totals":
                tgt=fh if is_fh else ou
                for o in rows:
                    ln=_f(o.get("max") if o.get("max") is not None else o.get("hdp") if o.get("hdp") is not None else o.get("line"))
                    ov=_f(o.get("over")); un=_f(o.get("under"))
                    if ln is None:continue
                    e=tgt.setdefault(ln,{})
                    if ov and ov>((e.get("over") or {}).get("odd") or 0):e["over"]={"odd":ov,"book":bname}
                    if un and un>((e.get("under") or {}).get("odd") or 0):e["under"]={"odd":un,"book":bname}
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
    events=get("/events",{"sport":"football","limit":5000}) or []
    if isinstance(events,dict): events=events.get("events") or events.get("data") or []
    idx={}   # (normH, normA) -> liste de (date, id)
    for ev in events:
        try:
            h=ev.get("home"); a=ev.get("away")
            if isinstance(h,dict):h=h.get("name")
            if isinstance(a,dict):a=a.get("name")
            d=str(ev.get("date") or ev.get("startTime") or "")[:10]
            eid=ev.get("id") or ev.get("eventId")
            if h and a and d and eid: idx.setdefault((norm(h),norm(a)),[]).append((d,eid))
        except: continue
    def close_date(d1,d2):
        try:
            a=datetime.date.fromisoformat(d1);b=datetime.date.fromisoformat(d2)
            return abs((a-b).days)<=1
        except: return d1==d2
    def find_eid(u):
        kh,ka=norm(u["h"]),norm(u["a"])
        for cand in (idx.get((kh,ka)) or []):
            if close_date(cand[0],u["date"]): return cand[1]
        # tolerance : inclusion partielle des noms
        for (nh,na),lst in idx.items():
            if ((kh in nh or nh in kh) and (ka in na or na in ka)) and len(kh)>=5 and len(ka)>=5:
                for cand in lst:
                    if close_date(cand[0],u["date"]): return cand[1]
        return None
    pairs=[]
    for fid,u in targets:
        eid=find_eid(u)
        if eid: pairs.append((fid,u,str(eid)))
    print(f"events odds-api.io: {len(events)} | cibles: {len(targets)} | associes: {len(pairs)}")
    fetched=0
    for k in range(0,len(pairs),10):
        if _used[0]>=BUDGET-2: break
        chunk=pairs[k:k+10]
        payload=get("/odds/multi",{"eventIds":",".join(p[2] for p in chunk),"bookmakers":BOOKIES})
        time.sleep(SLEEP)
        if payload is None: break
        evs=payload if isinstance(payload,list) else (payload.get("events") or payload.get("data") or [])
        if k==0:  # debug structure (1er lot seulement)
            try:
                import json as _j
                print("  DEBUG type payload:",type(payload).__name__,"| nb evs:",len(evs) if isinstance(evs,list) else "?")
                if isinstance(evs,list) and evs:
                    e0=evs[0]
                    print("  DEBUG keys ev:",list(e0.keys())[:12])
                    bk=e0.get("bookmakers")
                    print("  DEBUG type bookmakers:",type(bk).__name__)
                    if isinstance(bk,dict):
                        for bn,ms in list(bk.items())[:1]:
                            print("  DEBUG book:",bn,"| marches:",[m.get("name") for m in (ms or [])][:15])
                    elif isinstance(bk,list) and bk:
                        print("  DEBUG book[0]:",_j.dumps(bk[0])[:400])
                elif isinstance(payload,dict):
                    print("  DEBUG keys payload:",list(payload.keys())[:12])
            except Exception as _e: print("  DEBUG err:",_e)
        by_id={str(e.get("id") or e.get("eventId")):e for e in evs if isinstance(e,dict)}
        for fid,u,eid in chunk:
            ev=by_id.get(eid)
            if not ev: continue
            alt=parse_markets(ev)
            if not alt: continue
            alt["_ts"]=int(now)
            entry=odds.get(fid) or {"h":u["h"],"a":u["a"],"date":u["date"],"markets":{},"which":{}}
            entry["alt"]=alt
            odds[fid]=entry
            fetched+=1
    json.dump(odds,open(ODDSFILE,"w",encoding="utf-8"),ensure_ascii=False)
    print(f"cotes alt ecrites: {fetched} | requetes: {_used[0]}")

if __name__=="__main__":
    run()
