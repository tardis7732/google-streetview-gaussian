import json,time,gc,os
from pathlib import Path
import numpy as np,cv2
from scipy.spatial import cKDTree
from plyfile import PlyData
from .context import ROOT,JOB,load,classify,surface
if not (JOB/'training/prepared_receipt.json').exists() or not (ROOT/'labels_complete.json').exists():raise FileNotFoundError('Run sfm and labels before ground fusion')
ctx=load();front,E,C,labels,ctree=ctx
seed=np.load(JOB/'sfm/dataset/init_points.npz')['xyz'];votes,_=classify(seed,ctx);nearest=ctree.query(seed[:,[0,2]])[1];support=seed[(votes>=2)&(seed[:,1]>C[nearest,1]+.7)]
if len(support)<50:raise RuntimeError('Insufficient observed ground support; at least 50 road tracks are needed')
stree=cKDTree(support[:,[0,2]]);nb=stree.query(support[:,[0,2]],k=min(12,len(support)))[1];support=support[np.abs(support[:,1]-np.median(support[nb,1],1))<.7];stree=cKDTree(support[:,[0,2]])
print('SUPPORT',len(support),flush=True)
if len(support)<50:raise RuntimeError('Insufficient observed ground support')
np.save(ROOT/'ground_support.npy',support)
from .legacy import aligned_legacy_ground
legacy=aligned_legacy_ground(os.environ.get('GSVG_LEGACY'),ctx,support,stree)
legacy_tree=cKDTree(legacy[:,[0,2]]) if len(legacy) else None
parts=[legacy] if len(legacy) else []
xs=np.arange(support[:,0].min()-4,support[:,0].max()+4,.05);zs=np.arange(support[:,2].min()-4,support[:,2].max()+4,.05)
for start in range(0,len(zs),64):
 x,z=np.meshgrid(xs,zs[start:start+64]);p=np.stack([x.ravel(),np.zeros(x.size),z.ravel()],1);valid=(stree.query(p[:,[0,2]])[0]<5)&(ctree.query(p[:,[0,2]])[0]<25)&((legacy_tree.query(p[:,[0,2]])[0]>.045) if legacy_tree is not None else np.ones(len(p),bool));p=p[valid]
 if len(p):
  beta,valid=surface(p,support,stree);p[:,1]=beta[:,2];votes,_=classify(p,ctx);p=p[valid&(votes>=2)];parts.append(p)
 print('GROUND_GRID',min(start+64,len(zs)),len(zs),flush=True)
if not parts or not any(len(p) for p in parts):raise RuntimeError('No locally supported road surface was found')
pts=np.concatenate(parts).astype(np.float32);_,ids=np.unique(np.floor(pts[:,[0,2]]/.04).astype(np.int32),axis=0,return_index=True);pts=pts[ids];print('GROUND_TOTAL',len(pts),flush=True)
np.save(ROOT/'ground_points.npy',pts);paths=json.loads((ROOT/'photo_paths.json').read_text());sums=np.zeros((len(pts),3),np.float64);weights=np.zeros(len(pts),np.float64);near=ctree.query(pts[:,[0,2]],k=min(6,len(front)))[1]
for i,f in enumerate(front):
 ids=np.flatnonzero(np.any(near==i,axis=1));p=pts[ids]@E[i,:3,:3].T+E[i,:3,3];distance=np.linalg.norm(p,axis=1);horizontal=np.hypot(p[:,0],p[:,2]);u=np.arctan2(p[:,0],p[:,2])/(2*np.pi)+.5;v=np.arctan2(p[:,1],horizontal)/np.pi+.5;H,W=labels[i].shape;mu=(u*W).astype(int)%W;mv=np.clip((v*H).astype(int),0,H-1);valid=np.isin(labels[i][mv,mu],[0,1])&(horizontal>3)&(distance<40)&(p[:,1]>.3);local=np.flatnonzero(valid)
 if len(local):
  im=cv2.imread(paths[f['pano_id']]);H,W=im.shape[:2];x=(u[local]*W-.5)%W;y=np.clip(v[local]*H-.5,0,H-1.001);xx=np.floor(x).astype(int);yy=np.floor(y).astype(int);fx=(x-xx)[:,None];fy=(y-yy)[:,None];rgb=(im[yy,xx]*(1-fx)*(1-fy)+im[yy,(xx+1)%W]*fx*(1-fy)+im[yy+1,xx]*(1-fx)*fy+im[yy+1,(xx+1)%W]*fx*fy)[:,::-1];w=(p[local,1]/distance[local])**2/(distance[local]**2+1);sums[ids[local]]+=rgb*w[:,None];weights[ids[local]]+=w
 print('GROUND_COLOR',i+1,len(front),flush=True)
valid=weights>0;pts=pts[valid];colors=(np.clip(sums[valid]/weights[valid,None]/255,0,1)-.5)/.28209479177387814;np.savez_compressed(ROOT/'ground_ready.npz',points=pts,colors=colors);(ROOT/'ground_ready.json').write_text(json.dumps({'ground_splats':len(pts),'sfm_support':len(support),'legacy_points_before_resampling':len(legacy),'method':'Optional aligned legacy ground plus local SfM-supported road/sidewalk coverage; original selected-month panorama RGB reprojection. No output-radius crop.'}));print('GROUND COMPLETE',len(pts),flush=True)
