import json,gc
from pathlib import Path
import numpy as np,cv2
from scipy.ndimage import binary_fill_holes,label
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from plyfile import PlyData,PlyElement
from .context import ROOT,load,classify,surface
out=ROOT/'holefix';out.mkdir(exist_ok=True)
ctx=load();front,E,C,labels,ctree=ctx;g=np.load(ROOT/'ground_ready.npz');ground=g['points'];ground_colors=g['colors'];tree=cKDTree(ground[:,[0,2]])
a=np.load(ROOT/'floor_hole_audit.npz');occ=a['occupancy'];closed=a['closed'];lo=a['lo'];lab,n=label(a['holes']);sizes=np.bincount(lab.ravel());accepted=(sizes<=3000)&(sizes>0);accepted[0]=False;inside=accepted[lab]
outer=cv2.dilate(occ,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(13,13)))
target=(outer.astype(bool)|closed.astype(bool)|inside)&~occ.astype(bool)
iy,ix=np.where(target);parts=[];flags=[]
for dx,dz in [(.025,.025),(.075,.025),(.025,.075),(.075,.075)]:
 p=np.stack([lo[0]+ix*.1+dx,np.zeros(len(ix)),lo[1]+iy*.1+dz],1);distance=tree.query(p[:,[0,2]])[0];valid=(distance>.03)&(distance<3)&(ctree.query(p[:,[0,2]])[0]<26);parts.append(p[valid]);flags.append(inside[iy,ix][valid])
points=np.concatenate(parts);is_inside=np.concatenate(flags);newparts=[];insideparts=[];betas=[]
for start in range(0,len(points),50000):
 p=points[start:start+50000];beta,valid=surface(p,ground,tree);p[:,1]=beta[:,2];votes,_=classify(p,ctx)
 ids=np.flatnonzero(is_inside[start:start+50000]&~valid)
 if len(ids):
  dd,nn=tree.query(p[ids][:,[0,2]],k=12);ww=1/(dd+.1)**2;yy=(ground[nn,1]*ww).sum(1)/ww.sum(1);stable=(np.ptp(ground[nn,1],axis=1)<.7)&(dd[:,0]<3);p[ids[stable],1]=yy[stable];beta[ids[stable],:2]=0;beta[ids[stable],2]=yy[stable];valid[ids[stable]]=True
 near=ctree.query(p[:,[0,2]])[1];height=p[:,1]-C[near,1];valid&=(is_inside[start:start+50000]|(votes>=1))&(height>.7)&(height<6.5)
 newparts.append(p[valid]);insideparts.append(is_inside[start:start+50000][valid]);betas.append(beta[valid]);print('PATCH_GEOMETRY',start,len(points),flush=True)
points=np.concatenate(newparts).astype(np.float32);interior=np.concatenate(insideparts);beta=np.concatenate(betas);print('PATCH_POINTS',len(points),flush=True)
if not len(points):
 import shutil
 shutil.copyfile(ROOT/'output/model.ply',out/'model.ply');meta=json.loads((ROOT/'output/manifest.json').read_text());meta['ground_hole_repair']={'added_gaussians':0};(out/'manifest.json').write_text(json.dumps(meta,indent=2));raise SystemExit(0)
# Observed road photo colors where available; adjacent road color interpolation elsewhere.
sums=np.zeros((len(points),3),np.float64);weights=np.zeros(len(points),np.float64);near=ctree.query(points[:,[0,2]],k=8)[1];paths=json.loads((ROOT/'photo_paths.json').read_text())
for i,f in enumerate(front):
 ids=np.flatnonzero(np.any(near==i,axis=1));p=points[ids]@E[i,:3,:3].T+E[i,:3,3];distance=np.linalg.norm(p,axis=1);horizontal=np.hypot(p[:,0],p[:,2]);u=np.arctan2(p[:,0],p[:,2])/(2*np.pi)+.5;v=np.arctan2(p[:,1],horizontal)/np.pi+.5;H,W=labels[i].shape;mu=(u*W).astype(int)%W;mv=np.clip((v*H).astype(int),0,H-1);valid=np.isin(labels[i][mv,mu],[0,1])&(horizontal>1.5)&(distance<40)&(p[:,1]>.3);local=np.flatnonzero(valid)
 if len(local):
  im=cv2.imread(paths[f['pano_id']]);H,W=im.shape[:2];x=(u[local]*W-.5)%W;y=np.clip(v[local]*H-.5,0,H-1.001);xx=np.floor(x).astype(int);yy=np.floor(y).astype(int);fx=(x-xx)[:,None];fy=(y-yy)[:,None];rgb=(im[yy,xx]*(1-fx)*(1-fy)+im[yy,(xx+1)%W]*fx*(1-fy)+im[yy+1,xx]*(1-fx)*fy+im[yy+1,(xx+1)%W]*fx*fy)[:,::-1];w=(p[local,1]/distance[local])**2/(distance[local]**2+1);sums[ids[local]]+=rgb*w[:,None];weights[ids[local]]+=w
 print('PATCH_COLOR',i+1,len(front),flush=True)
observed=weights>0;colors=np.zeros((len(points),3),np.float32);colors[observed]=(sums[observed]/weights[observed,None]/255-.5)/.28209479177387814
for start in range(0,len(points),50000):
 ids=np.arange(start,min(start+50000,len(points)));ids=ids[~observed[ids]]
 if len(ids):
  dist,idx=tree.query(points[ids][:,[0,2]],k=12);w=1/(dist+.1)**2;colors[ids]=(ground_colors[idx]*w[:,:,None]).sum(1)/w.sum(1)[:,None]
base=PlyData.read(ROOT/'output/model.ply')['vertex'].data;patch=np.zeros(len(points),dtype=base.dtype)
# Slightly lower backing layer avoids fighting with existing road splats at the seam.
points[:,1]+=.006
for i,k in enumerate(['x','y','z']):patch[k]=points[:,i]
for i in range(3):patch[f'f_dc_{i}']=colors[:,i]
normal=np.stack([-beta[:,0],np.ones(len(points)),-beta[:,1]],1);normal/=np.linalg.norm(normal,axis=1,keepdims=True);x=np.stack([np.ones(len(points)),beta[:,0],np.zeros(len(points))],1);x/=np.linalg.norm(x,axis=1,keepdims=True);quat=Rotation.from_matrix(np.stack([x,normal,np.cross(x,normal)],2)).as_quat()[:,[3,0,1,2]]
for i in range(4):patch[f'rot_{i}']=quat[:,i]
patch['scale_0']=np.log(.06);patch['scale_1']=np.log(.007);patch['scale_2']=np.log(.06);patch['opacity']=np.log(.985/.015)
assert all(np.isfinite(patch[k]).all() for k in patch.dtype.names)
PlyData([PlyElement.describe(patch,'vertex')],text=False).write(out/'floor_patch.ply');result=np.concatenate([base,patch]);PlyData([PlyElement.describe(result,'vertex')],text=False).write(out/'model.ply')
filled=occ.copy();ij=np.floor((points[:,[0,2]]-lo)/.1).astype(int);filled[ij[:,1],ij[:,0]]=1;before_hole=inside.sum();after_hole=(inside&~filled.astype(bool)).sum();before_area=float(before_hole*.01);after_area=float(after_hole*.01)
meta=json.loads((ROOT/'output/manifest.json').read_text());meta['previous_gaussians']=len(base);meta['gaussians']=len(result);meta['ground_hole_repair']={'added_gaussians':len(patch),'photo_colored_gaussians':int(observed.sum()),'interpolated_road_color_gaussians':int((~observed).sum()),'enclosed_hole_limit_m2':30,'maximum_gap_distance_to_existing_ground_m':3,'sampling_m':.05,'sigma_m':[.06,.007,.06],'existing_gaussians_deleted':0,'enclosed_gap_area_before_m2':before_area,'enclosed_gap_area_after_m2':after_area,'new_ground_area_on_10cm_grid_m2':float((filled.sum()-occ.sum())*.01),'method':'Fill bounded holes and road-observed boundary gaps using a local height field interpolated from existing ground. Photo reprojection when visible; adjacent ground RGB interpolation when occluded. Estimated surfaces, not new measurements. Original people, vehicles, and sky retained.'};meta['validation'].update(all_patch_parameters_finite=True,visual_check='pending hole-repair comparison; previous render validation refers to the earlier hybrid')
(out/'manifest.json').write_text(json.dumps(meta,indent=2));print('COMPLETE',meta['ground_hole_repair'],flush=True)
