import json,time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from plyfile import PlyData,PlyElement
from .context import ROOT,JOB,load,classify,surface

raw=JOB/'training/refined/final.ply'
if not (ROOT/'ground_ready.json').exists() or not raw.exists():raise FileNotFoundError('Run train and ground before hybrid fusion')
ctx=load();front,E,C,labels,ctree=ctx
g=np.load(ROOT/'ground_ready.npz');points=g['points'];colors=g['colors'];gtree=cKDTree(points[:,[0,2]])
support=np.load(ROOT/'ground_support.npy');stree=cKDTree(support[:,[0,2]])
data=PlyData.read(raw)['vertex'].data
keep=np.ones(len(data),bool);counts={'covered_road_layers_removed':0,'weak_large_nearby_splats_removed':0}
for start in range(0,len(data),100000):
 stop=min(start+100000,len(data));d=data[start:stop];p=np.stack([d[k] for k in ['x','y','z']],1);votes,protect=classify(p,ctx)
 distance,idx=gtree.query(p[:,[0,2]]);near=ctree.query(p[:,[0,2]])[0];opacity=1/(1+np.exp(-np.clip(d['opacity'],-60,60)));sigma=np.exp(np.stack([d[f'scale_{i}'] for i in range(3)],1)).max(1)
 road=(distance<.6)&(np.abs(p[:,1]-points[idx,1])<2)&(votes>=2)&~protect
 weak=(((near<25)&(sigma>1)&(opacity<.2))|((near<60)&(opacity<.015)))&~protect
 keep[start:stop]=~(road|weak);counts['covered_road_layers_removed']+=int(road.sum());counts['weak_large_nearby_splats_removed']+=int((weak&~road).sum())
 print('BODY',stop,len(data),flush=True)
new=np.zeros(len(points),dtype=data.dtype)
for i,k in enumerate(['x','y','z']):new[k]=points[:,i]
for i in range(3):new[f'f_dc_{i}']=colors[:,i]
for start in range(0,len(points),50000):
 stop=min(start+50000,len(points));beta,valid=surface(points[start:stop],support,stree);normal=np.stack([-beta[:,0],np.ones(stop-start),-beta[:,1]],1);normal/=np.linalg.norm(normal,axis=1,keepdims=True);x=np.stack([np.ones(stop-start),beta[:,0],np.zeros(stop-start)],1);x/=np.linalg.norm(x,axis=1,keepdims=True);z=np.cross(x,normal);quat=Rotation.from_matrix(np.stack([x,normal,z],2)).as_quat()[:,[3,0,1,2]]
 for i in range(4):new[f'rot_{i}'][start:stop]=quat[:,i]
new['scale_0']=np.log(.043);new['scale_1']=np.log(.004);new['scale_2']=np.log(.043);new['opacity']=np.log(.95/.05)
result=np.concatenate([data[keep],new]);assert all(np.isfinite(result[k]).all() for k in result.dtype.names)
out=ROOT/'output';out.mkdir(exist_ok=True);PlyData([PlyElement.describe(result,'vertex')],text=False).write(out/'model.ply')
survey=json.loads((ROOT/'area_survey.json').read_text());lookup=survey['accepted'];sources=[]
for f in front:
 s=lookup[f['pano_id']];sources.append({'id':s['id'],'date':s['date'],'lat':s['lat'],'lon':s['lon'],'camera_world':np.array(f['transform_matrix'])[:3,3].tolist()})
required=survey['required_date']
assert sources and all(str(s['date'])[:7]==required for s in sources)
excluded=sorted(set(lookup)-{s['id'] for s in sources})
meta={'center':[json.loads((JOB/'sfm/gps_report.json').read_text())['origin']['lat'],json.loads((JOB/'sfm/gps_report.json').read_text())['origin']['lng']],'collection_center':survey['center'],'collection_radius_m':survey['radius_m'],'collected_panorama_count':len(lookup),'used_panorama_count':len(sources),'excluded_sources':{'ids':excluded},'date':required,'sources':sources,'gaussians':len(result),'output_radius_crop':False,'method':'Unmasked Brush 40000 + gsplat 6000; optional legacy ground aligned to SfM plus observed road extension, local SfM height constraints, original panorama RGB reprojection','hybrid':{**json.loads((ROOT/'ground_ready.json').read_text()),**counts,'raw_brush_gaussians':len(data),'new_ground_vertex_start':int(keep.sum()),'new_ground_splats':len(new),'sampling_m':.05,'ground_sigma_m':[.043,.004,.043],'people_vehicle_sky_masking':False,'ground_surface_policy':'Local SfM-supported slopes only; coverage and original-photo evidence required. Semantic road classification selects floor replacement and protects people, vehicles, and sky.'},'validation':{'all_parameters_finite':True,'selected_month_sources':len(sources),'output_radius_crop':False}}
(out/'manifest.json').write_text(json.dumps(meta,indent=2));np.save(out/'ground_sfm_support.npy',support);print('COMPLETE',len(result),counts,flush=True)
