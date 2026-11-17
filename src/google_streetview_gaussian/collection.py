"""Exact-month collection through the optional YellowO2 adapter."""
import asyncio,shutil
from pathlib import Path
from .io import distance_m,month,read,safe_id,selected_sources,write

async def collect(root,seed,center,radius,required,max_inspected=300):
    from streetview_to_3d.gather_panoramas.tools.fetch_pano_by_id import fetch_pano_by_id
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);month(required);safe_id(seed)
    if radius<=0 or max_inspected<1:raise ValueError("Positive radius and inspection limit required")
    queue=[seed];seen=set();accepted={};inspected={};failures={}
    while queue and len(seen)<max_inspected:
        batch=[p for p in dict.fromkeys(queue) if p not in seen][:min(8,max_inspected-len(seen))]
        queue=[p for p in queue if p not in batch]
        if not batch:break
        seen.update(batch);results=await asyncio.gather(*(fetch_pano_by_id(p) for p in batch),return_exceptions=True)
        for pid,meta in zip(batch,results):
            if isinstance(meta,Exception) or not meta:failures[pid]=str(meta);continue
            inspected[pid]=meta
            if distance_m(center,(meta["lat"],meta["lon"]))>radius:continue
            if str(meta.get("date",""))[:7]==required:accepted[meta["id"]]=meta
            for n in meta.get("neighbors",[]):
                if n["id"] not in seen and distance_m(center,(n["lat"],n["lon"]))<=radius:queue.append(safe_id(n["id"]))
            for h in meta.get("dates",[]):
                if str(h.get("label",""))[:7]==required and h["id"] not in seen:queue.append(safe_id(h["id"]))
        write(root/"area_survey.json",dict(center=list(center),radius_m=radius,required_date=required,accepted=accepted,inspected=inspected,failures=failures,inspection_limit=max_inspected,inspection_limit_reached=bool(queue and len(seen)>=max_inspected)))
        print(f"Accepted {len(accepted)} / inspected {len(seen)}",flush=True)
    return selected_sources(read(root/"area_survey.json"))

async def download(root,zoom=4):
    from streetview_to_3d.tools.streetview_fetch.download_pano_by_id import download_pano_by_id
    root=Path(root).resolve();sources=selected_sources(read(root/"area_survey.json"));folder=root/"photos";folder.mkdir(exist_ok=True);paths={};sem=asyncio.Semaphore(2)
    async def one(source):
        pid=source["id"];target=folder/f"{pid}.jpg"
        async with sem:
            if not target.exists():
                cached=await download_pano_by_id(pid,zoom=zoom)
                if not cached:raise RuntimeError("Download returned no panorama: "+pid)
                shutil.copyfile(cached,target)
            paths[pid]=str(target);print("Photo",len(paths),len(sources),pid,flush=True)
    await asyncio.gather(*(one(s) for s in sources));write(root/"photo_paths.json",paths)

def labels(root):
    from PIL import Image
    from streetview_to_3d.build_scene.models.Segmenter import Segmenter
    root=Path(root).resolve();sources=selected_sources(read(root/"area_survey.json"));paths=read(root/"photo_paths.json");out=root/"labels";out.mkdir(exist_ok=True);thumbs=root/"thumbnails";thumbs.mkdir(exist_ok=True);model=Segmenter()
    for i,source in enumerate(sources):
        pid=source["id"];target=out/f"{pid}.png"
        if not target.exists():
            photo=thumbs/f"{pid}.jpg"
            with Image.open(paths[pid]) as image:image.convert("RGB").resize((2048,1024),Image.Resampling.LANCZOS).save(photo,quality=95)
            model.pano_labels(str(photo),saved=str(target))
        print("Road labels",i+1,len(sources),flush=True)
    write(root/"labels_complete.json",dict(count=len(sources),purpose="Road selection/protection only; no people, vehicle or sky masks applied to training RGB"))
