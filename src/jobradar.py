#!/usr/bin/env python3
"""VagaRadar: vagas remotas, filtro transparente, deduplicação e aviso SMTP."""
import datetime as dt
import hashlib
import html
import json
import logging
import os
from pathlib import Path
import re
import smtplib
import ssl
import unicodedata
from email.message import EmailMessage
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = logging.getLogger("vagaradar")
UTC = dt.timezone.utc
TERMS = {
    "Dados e BI": ["analista de dados", "assistente de dados", "data analyst", "data assistant", "bi analyst", "business intelligence analyst", "analista de bi", "analista de indicadores", "reporting analyst"],
    "TI e Suporte": ["analista de suporte", "suporte de ti", "assistente de ti", "help desk", "service desk", "it support", "technical support", "support analyst", "analista de sistemas"],
    "Operações e Administração": ["assistente administrativo", "analista administrativo", "administrative assistant", "operations analyst", "operations assistant", "back office", "analista de processos"],
    "Trainee": ["trainee", "graduate program", "internship", "estagio"]
}
SKILLS = {"SQL": ["sql"], "Power BI": ["power bi", "dax", "business intelligence"], "Python": ["python", "pandas"], "Excel": ["excel", "spreadsheets", "planilhas"], "Suporte": ["support", "suporte", "help desk"], "Processos": ["processos", "operations", "workflow"], "Dashboards": ["dashboard", "kpi", "indicadores"]}
SENIOR = re.compile(r"\b(senior|sr|pleno|lead|staff|principal|head|director|manager|gerente|coordenador|especialista|architect|arquiteto)\b", re.I)
UNRELATED = re.compile(r"\b(software engineer|desenvolvedor|account executive|sales representative|recruiter|product manager)\b", re.I)
def norm(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", str(t or "")))
    return unicodedata.normalize("NFKD",t).encode("ascii","ignore").decode().lower().strip()
def api(url, params=None):
    if params: url += ("&" if "?" in url else "?") + urlencode(params)
    req = Request(url,headers={"User-Agent":"VagaRadar/1.0","Accept":"application/json"})
    with urlopen(req, timeout=24) as resp: return json.load(resp)
def job(source, identifier, title, company, location, desc, link, published, eligible, reason, salary=""):
    if urlparse(str(link)).scheme not in ("http","https"): return None
    return {"id":hashlib.sha256(f"{source}:{identifier}".encode()).hexdigest()[:18], "source":source,"title":str(title),"company":str(company),"location":str(location),"description":norm(desc)[:4500], "url":str(link),"published":str(published or ""),"salary":str(salary or ""),"remote":True,"location_allowed":bool(eligible),"location_reason":reason}
def himalayas_allowed(items):
    if not items: return True, "Sem restrição geográfica informada; conferir anúncio"
    s = " ".join(str(x.get("alpha2",""))+" "+str(x.get("name","")) if isinstance(x,dict) else str(x) for x in items)
    return bool(re.search(r"\bBR\b|brazil|brasil",s,re.I)), "Brasil explicitamente incluído" if re.search(r"\bBR\b|brazil|brasil",s,re.I) else "Outro país"
def fetch_himalayas(queries):
    out=[]
    for query in queries:
        try:
            payload=api("https://himalayas.app/jobs/api/search",{"q":query,"sort":"recent","page":1})
            for v in payload.get("jobs",[]):
                allow,reason=himalayas_allowed(v.get("locationRestrictions"))
                pub=v.get("pubDate")
                if isinstance(pub,(int,float)): pub=dt.datetime.fromtimestamp(pub,UTC).isoformat()
                j=job("Himalayas",v.get("guid") or v.get("applicationLink"),v.get("title"),v.get("companyName"),"Global / remoto"," ".join([v.get("excerpt") or "",v.get("description") or ""]),v.get("applicationLink"),pub,allow,reason)
                if j: out.append(j)
        except Exception as ex: LOG.warning("Himalayas %s: %s",query,ex)
    return out
def fetch_remotive():
    out=[]
    try:
        payload=api("https://remotive.com/api/remote-jobs",{"limit":1000})
        for v in payload.get("jobs",[]):
            loc=str(v.get("candidate_required_location") or "")
            n=norm(loc)
            allow=any(s in n for s in ("brazil","brasil","worldwide","anywhere","global","latam","latin america","south america"))
            j=job("Remotive",v.get("id") or v.get("url"),v.get("title"),v.get("company_name"),loc or "Não informado",v.get("description"),v.get("url"),v.get("publication_date"),allow,"Brasil ou localidade elegível" if allow else "Elegibilidade não confirmada",v.get("salary"))
            if j: out.append(j)
    except Exception as ex: LOG.warning("Remotive: %s",ex)
    return out
def score(v, cfg):
    if not v["remote"] or (cfg.get("require_brazil_eligibility",True) and not v["location_allowed"]): return None
    title=norm(v["title"])
    if SENIOR.search(title) or UNRELATED.search(title): return None
    category=next((name for name,aliases in TERMS.items() if any(t in title for t in aliases)),None)
    if not category: return None
    pub=None
    try: pub=dt.datetime.fromisoformat(v["published"].replace("Z","+00:00")).astimezone(UTC)
    except (ValueError,TypeError): pass
    age=(dt.datetime.now(UTC)-pub).days if pub else None
    if age is not None and age>int(cfg.get("days_old_max",45)):return None
    points=50
    positive=["Cargo relacionado a "+category, v["location_reason"]]
    negative=[]
    if re.search(r"\b(junior|jr|trainee|intern|estagio|assistente|auxiliar|entry level)\b",title):
        points+=17;positive.append("Nível inicial/júnior")
    else: negative.append("Senioridade não confirmada")
    matches=[name for name,aliases in SKILLS.items() if any(re.search(r"\b"+re.escape(a)+r"\b",v["description"]) for a in aliases)]
    points+=min(24,len(matches)*4)
    if matches: positive.append("Competências: "+", ".join(matches))
    else: negative.append("Poucas competências localizadas no anúncio")
    if re.search(r"\b(fluent english|advanced english|c1 english|ingles fluente|ingles avancado)\b",v["description"]):
        points-=15;negative.append("Pode exigir inglês avançado")
    if category=="Trainee":points-=5
    if age is not None and age<=7:points+=5;positive.append("Anúncio recente")
    points=max(0,min(100,points))
    if points<int(cfg.get("minimum_score",55)):return None
    result={k:value for k,value in v.items() if k!="description"}
    result.update(score=points, category=category,positives=positive,negatives=negative)
    return result
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
def email_alert(jobs):
    keys=["SMTP_HOST","SMTP_USER","SMTP_PASSWORD","ALERT_EMAIL"]
    host,user,password,recipient=[os.getenv(k) for k in keys]
    if not all((host,user,password,recipient)):return False
    msg=EmailMessage()
    msg["From"]=user;msg["To"]=recipient
    msg["Subject"]=f"VagaRadar — {len(jobs)} novas vagas remotas"
    lines=["Novas oportunidades que combinam com seu currículo",""]
    for v in jobs:
        lines.extend([f"{v['score']}% | {v['title']} — {v['company']}","Local: "+v["location"],"Fonte: "+v["source"],"Por que combina: "+"; ".join(v["positives"]),"Conferir: "+"; ".join(v["negatives"]),"Candidatura: "+v["url"],""])
    msg.set_content("\n".join(lines))
    try:
        port=int(os.getenv("SMTP_PORT") or 465)
        if port==465:
            with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context(),timeout=25) as s:
                s.login(user,password);s.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=25) as s:
                s.starttls(context=ssl.create_default_context());s.login(user,password);s.send_message(msg)
        return True
    except (OSError,smtplib.SMTPException) as ex:
        LOG.error("Não enviou e-mail: %s",ex);return False
def main():
    logging.basicConfig(level=logging.INFO,format="%(levelname)s: %(message)s")
    cfg=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
    state_path=DATA/"state.json"
    old=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"seen":[]}
    seen=set(old.get("seen",[]))
    raw=fetch_himalayas(cfg["queries"])+fetch_remotive()
    if not raw:raise SystemExit("Nenhuma fonte respondeu; histórico preservado")
    unique={}
    for v in raw:
        classified=score(v,cfg["profile"])
        if classified:unique[classified["id"]]=classified
    matches=sorted(unique.values(),key=lambda x:(x["score"],x["published"]),reverse=True)
    fresh=[j for j in matches if j["id"] not in seen]
    chosen=fresh[:int(cfg["profile"].get("max_alerts_per_run",8))]
    if chosen and email_alert(chosen):seen.update(j["id"] for j in chosen)
    now=dt.datetime.now(UTC).isoformat()
    save(DATA/"jobs.json",{"updated_at":now,"total":len(matches),"new_count":len(fresh),"sources":sorted({j["source"] for j in raw}),"jobs":matches[:400]})
    save(state_path,{"seen":sorted(seen),"last_run":now})
    LOG.info("Recebidas: %d; compatíveis: %d; novas: %d",len(raw),len(matches),len(fresh))
if __name__=="__main__":main()
