import json,os
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
ROOT=Path(os.environ['GSVG_RUN']).expanduser().resolve()
JOB=ROOT/'reconstruction'
def load():
 frames=json.loads((JOB/'training/dataset/transforms_train.json').read_text())['frames'];front=[f for f in frames if f['face']=='front'];E=np.array([np.linalg.inv(np.array(f['transform_matrix'])@np.diag([1,-1,-1,1])) for f in front]);C=np.array([np.array(f['transform_matrix'])[:3,3] for f in front]);labels=[np.asarray(Image.open(ROOT/f"labels/{f['pano_id']}.png")) for f in front];return front,E,C,labels,cKDTree(C[:,[0,2]])
def classify(points,context):
 front,E,C,labels,tree=context;near=tree.query(points[:,[0,2]],k=3)[1];votes=np.zeros(len(points),np.uint8);protect=np.zeros(len(points),bool)
 for i in range(len(front)):
  ids=np.flatnonzero(np.any(near==i,axis=1))
  if not len(ids):continue
  q=points[ids]@E[i,:3,:3].T+E[i,:3,3];H,W=labels[i].shape;u=((np.arctan2(q[:,0],q[:,2])/(2*np.pi)+.5)*W).astype(int)%W;v=np.clip(((np.arctan2(q[:,1],np.hypot(q[:,0],q[:,2]))/np.pi+.5)*H).astype(int),0,H-1);lab=labels[i][v,u];votes[ids]+=np.isin(lab,[0,1]);protect[ids]|=np.isin(lab,[10,11,12,13,14,15,16,17,18])
 return votes,protect
def surface(points,support,tree):
 distances,indices=tree.query(points[:,[0,2]],k=min(20,len(support)));q=support[indices];dx=q[:,:,0]-points[:,None,0];dz=q[:,:,2]-points[:,None,2];X=np.stack([dx,dz,np.ones_like(dx)],2);weights=1/(distances+.3)**2;beta=np.zeros((len(points),3))
 for _ in range(3):
  lhs=np.einsum('nki,nk,nkj->nij',X,weights,X)+np.eye(3)[None]*1e-6;rhs=np.einsum('nki,nk,nk->ni',X,weights,q[:,:,1]);beta=np.linalg.solve(lhs,rhs[...,None])[...,0];residual=np.abs(np.einsum('nki,ni->nk',X,beta)-q[:,:,1]);weights=1/(distances+.3)**2*np.minimum(1,.2/np.maximum(residual,1e-6))
 spread=np.median(np.abs(q[:,:,1]-np.einsum('nki,ni->nk',X,beta)),axis=1);valid=(distances[:,0]<5)&(np.linalg.norm(beta[:,:2],axis=1)<.35)&(spread<.25)
 return beta,valid
