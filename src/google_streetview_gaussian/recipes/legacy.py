"""Optional alignment of an earlier hybrid ground layer to a new visual gauge."""
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from plyfile import PlyData
from ..io import read,write
from .context import ROOT,classify,surface

def aligned_legacy_ground(folder,ctx,support,tree):
    if not folder:return np.empty((0,3),dtype=float)
    folder=Path(folder).resolve();meta=read(folder/'manifest.json');file=folder/meta.get('model_file',meta.get('hybrid',{}).get('final_filename','hybrid_final.ply'));vertices=PlyData.read(file)['vertex'].data;start=meta['hybrid']['new_ground_vertex_start'];count=meta['hybrid']['new_ground_splats'];points=np.stack([vertices[k][start:start+count] for k in ['x','y','z']],1).astype(float)
    new={f['pano_id']:np.array(f['transform_matrix'])[:3,3] for f in ctx[0]};shared=[s for s in meta['sources'] if s['id'] in new]
    if len(shared)<3:raise ValueError('Legacy alignment requires at least three shared visual cameras')
    A=np.array([s['camera_world'] for s in shared]);B=np.array([new[s['id']] for s in shared]);a=A-A.mean(0);b=B-B.mean(0)
    if np.linalg.matrix_rank(a)<2:raise ValueError('Legacy camera alignment is degenerate')
    U,S,V=np.linalg.svd(b.T@a/len(a));D=np.diag([1,1,np.linalg.det(U@V)]);R=U@D@V;scale=np.trace(np.diag(S)@D)/np.mean(np.sum(a*a,1));translation=B.mean(0)-scale*R@A.mean(0);points=points@(scale*R).T+translation;parts=[]
    for start in range(0,len(points),50000):
        p=points[start:start+50000];beta,valid=surface(p,support,tree);votes,_=classify(p,ctx);valid&=(votes>=2)&(np.abs(p[:,1]-beta[:,2])<1.5);p=p[valid];p[:,1]=beta[valid,2];parts.append(p)
    write(ROOT/'legacy_alignment.json',dict(shared_cameras=len(shared),scale=float(scale),camera_rmse_m=float(np.sqrt(np.mean(np.sum((A@(scale*R).T+translation-B)**2,axis=1)))),is_survey_accuracy=False))
    return np.concatenate(parts) if parts else np.empty((0,3))
