"""Adapter to the pinned streetview-to-ply SfM / Brush / gsplat backend."""
from pathlib import Path
import hashlib,json,math,os,subprocess,sys
import numpy as np,cv2
from PIL import Image
from .io import read,write,sha,selected_sources

BACKEND_COMMIT="3211651201467682ebdd92e3c81504234be5c468"
ROTATIONS={"front":[[1,0,0],[0,1,0],[0,0,1]],"right":[[0,0,1],[0,1,0],[-1,0,0]],"back":[[-1,0,0],[0,1,0],[0,0,-1]],"left":[[0,0,-1],[0,1,0],[1,0,0]],"up":[[1,0,0],[0,0,-1],[0,1,0]],"down":[[1,0,0],[0,0,1],[0,-1,0]]}

def prepare(root,size=1280):
    root=Path(root).resolve();survey=read(root/"area_survey.json");sources=selected_sources(survey);paths=read(root/"photo_paths.json");job=root/"reconstruction";folder=job/"prepared";folder.mkdir(parents=True,exist_ok=True)
    if size<32 or size%2:raise ValueError("Face size must be an even integer >= 32")
    if (folder/"manifest.json").exists():raise FileExistsError("Prepared input already exists; use a new run or skip prepare")
    config=dict(panorama_ids=[s["id"] for s in sources],processing_options=dict(remove_sky=False,mask_dynamic=False));write(job/"selection.json",config);write(job/"collection/manifest.json",survey)
    Image.new("L",(size,size),255).save(folder/"all_valid.png");Image.new("L",(size,size),0).save(folder/"empty.png")
    t=(np.arange(size,dtype=np.float32)+.5-size/2)/(size/2);x,y=np.meshgrid(t,t);rays=np.stack([x,y,np.ones_like(x)],-1);frames=[];stations=[]
    for source in sources:
        pid=source["id"];image=cv2.imread(paths[pid])
        if image is None:raise ValueError("Cannot read panorama: "+pid)
        h,w=image.shape[:2];stations.append(dict(pano_id=pid,station_id=pid,lat=source["lat"],lon=source["lon"],heading=math.degrees(source["heading"]),date=source["date"],altitude_m=source.get("elevation"),links=source.get("neighbors",[])))
        for face,rotation in ROTATIONS.items():
            R=np.array(rotation,dtype=float);d=rays@R.T;mx=((np.arctan2(d[:,:,0],d[:,:,2])/(2*np.pi)+.5)*w).astype(np.float32);my=((np.arctan2(d[:,:,1],np.hypot(d[:,:,0],d[:,:,2]))/np.pi+.5)*h).astype(np.float32);target=folder/f"{pid}_{face}.jpg"
            if not cv2.imwrite(str(target),cv2.remap(image,mx,my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_WRAP),[cv2.IMWRITE_JPEG_QUALITY,97]):raise OSError(str(target))
            T=np.eye(4);T[:3,:3]=R;frame=dict(pano_id=pid,station_id=pid,face=face,file_path=target.relative_to(job).as_posix(),source_sha256=sha(target),w=size,h=size,fl_x=size/2,fl_y=size/2,cx=size/2,cy=size/2,camera_to_station_cv=T.tolist())
            for key in ["mask","sfm_mask","sky_mask","ground_mask"]:
                mask=folder/("empty.png" if key in ["sky_mask","ground_mask"] else "all_valid.png");frame[key+"_path"]=mask.relative_to(job).as_posix();frame[key+"_sha256"]=sha(mask)
            frames.append(frame)
    write(folder/"manifest.json",dict(status="complete",processing_options=config["processing_options"],stations=stations,frames=frames,collection_manifest_path="collection/manifest.json",collection_sha256=sha(job/"collection/manifest.json")))
    return job

def attach_backend(path,allow_unpinned=False):
    path=Path(path).resolve()
    if not (path/"tools/streetview_engine/sfm.py").is_file():raise ValueError("Expected a streetview-to-ply checkout")
    revision=subprocess.check_output(["git","-C",str(path),"rev-parse","HEAD"],text=True).strip()
    if revision!=BACKEND_COMMIT and not allow_unpinned:raise ValueError(f"Backend differs from tested commit {BACKEND_COMMIT}; use --allow-unpinned-backend explicitly")
    sys.path.insert(0,str(path));os.environ['PYTHONPATH']=str(path)+(os.pathsep+os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '');return path

def sfm(root,backend,minimum_coverage=1.,recovery_neighbors=16,allow_unpinned=False):
    attach_backend(backend,allow_unpinned);from tools.streetview_engine import sfm as engine
    from tools.streetview_engine.brush_refine import prepare_dataset
    root=Path(root).resolve();job=root/"reconstruction";config=read(job/"selection.json")
    settings={"sfm":{"device":"cpu","threads":12,"holdout_fraction":0,"mapper_seconds":3600,"recovery_rounds":4,"recovery_seconds":600,"recovery_match_neighbors":recovery_neighbors,"minimum_registered_fraction":minimum_coverage},"quality":{"enabled":False}}
    write(job/"settings.json",settings)
    if not (job/"sfm/manifest.json").exists():engine.run(config,job,settings)
    if not (job/"training/dataset").exists():prepare_dataset(job/"sfm/dataset",job/"training/dataset",job/"training/depth")

def train(root,backend,brush,max_splats=4000000,allow_unpinned=False):
    attach_backend(backend,allow_unpinned)
    from tools.streetview_engine.brush_refine import build_commands,_execute
    from gsplat.cuda._backend import _C
    root=Path(root).resolve();out=root/"reconstruction/training";library=Path(_C.__file__);brush=Path(brush).resolve()
    if not brush.is_file():raise FileNotFoundError(brush)
    commands=build_commands(dict(brush_binary=str(brush),renderer_library=str(library),renderer_library_sha256=sha(library)),out/"dataset",out,out/"depth")
    for command in commands:command[command.index("--max-splats")+1]=str(max_splats)
    write(out/"commands.json",dict(brush=commands[0],refine=commands[1]));(root/"train.log").write_text("RUNNING\n",encoding="utf8")
    if not (out/"brush/brush_40000.ply").exists():_execute(commands[0],out/"brush.log",terminal=True)
    _execute(commands[1],out/"refine.log");(root/"train.log").write_text("COMPLETE\n",encoding="utf8")
