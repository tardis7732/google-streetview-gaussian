from pathlib import Path
import hashlib,json,math,re

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")

def sha(path):
    with Path(path).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def month(value):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",value):raise ValueError("Month must be YYYY-MM")
    return value

def safe_id(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_-]+",value):raise ValueError("Invalid panorama ID")
    return value

def distance_m(center,point):
    a,b=map(math.radians,center);c,d=map(math.radians,point)
    q=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(max(0,q))))

def selected_sources(survey):
    required=month(survey["required_date"]);sources=list(survey["accepted"].values())
    if not sources:raise ValueError("No panoramas matched the requested month and radius")
    for s in sources:
        safe_id(s["id"])
        if str(s.get("date",""))[:7]!=required:raise ValueError("Unexpected capture month: "+s["id"])
        if distance_m(survey["center"],(s["lat"],s["lon"]))>survey["radius_m"]+.01:raise ValueError("Panorama outside collection radius")
    return sources
