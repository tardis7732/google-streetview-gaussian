"""Build a portable local viewer data folder from registered visual cameras."""
from pathlib import Path
import shutil
import numpy as np
from plyfile import PlyData
from .io import read,write,safe_id,selected_sources

def export(root,model,output):
    root=Path(root).resolve();model=Path(model).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    survey=read(root/'area_survey.json');sources={s['id']:s for s in selected_sources(survey)};paths=read(root/'photo_paths.json');frames=read(root/'reconstruction/training/dataset/transforms_train.json')['frames'];front=[f for f in frames if f['face']=='front']
    if not front:raise ValueError('No registered front cameras')
    vertices=PlyData.read(model)['vertex']
    if not {'x','y','z','opacity','scale_0','rot_0','f_dc_0'}<=set(vertices.data.dtype.names):raise ValueError('Expected a Gaussian PLY, not an ordinary point cloud')
    collected=[];references=[]
    for f in front:
        pid=safe_id(f['pano_id']);s=sources[pid];pose=np.array(f['transform_matrix']);E=np.linalg.inv(pose@np.diag([1,-1,-1,1]));entry={k:s[k] for k in ['id','date','lat','lon']};entry['camera_world']=pose[:3,3].tolist();collected.append(entry);target=out/'panoramas'/f'{pid}.jpg';target.parent.mkdir(exist_ok=True)
        if Path(paths[pid]).resolve()!=target.resolve():shutil.copyfile(paths[pid],target)
        references.append(dict(**entry,file=target.relative_to(out).as_posix(),world_to_pano_cv=E[:3,:3].tolist()))
    destination=out/model.name
    if destination.resolve()!=model:shutil.copyfile(model,destination)
    gpsfile=root/'reconstruction/sfm/gps_report.json';gps=read(gpsfile).get('origin',{}) if gpsfile.exists() else {}
    excluded=sorted(set(sources)-{s['id'] for s in collected})
    metadata=dict(model_file=model.name,gaussians=vertices.count,date=survey['required_date'],center=[gps.get('lat',float(np.median([s['lat'] for s in collected]))),gps.get('lng',float(np.median([s['lon'] for s in collected])))],collection_center=survey['center'],collection_radius_m=survey['radius_m'],collected_panorama_count=len(sources),used_panorama_count=len(collected),sources=collected,excluded_sources={'ids':excluded},output_radius_crop=False,coordinate_frame='EDN',units='metres')
    write(out/'manifest.json',metadata);write(out/'panorama_index.json',dict(schema_version=1,date=survey['required_date'],coordinate_frame='EDN',image_projection='equirectangular; +Z forward, +X right, +Y down',sources=references))
    return out
