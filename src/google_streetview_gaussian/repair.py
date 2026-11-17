"""Prepare the same local ground occupancy audit used by the repair recipe."""
from pathlib import Path
import numpy as np,cv2
from scipy.ndimage import binary_fill_holes

def audit(root,max_cells=25000000):
    root=Path(root).resolve();points=np.load(root/'ground_ready.npz')['points']
    if len(points)<20:raise ValueError('At least 20 ground splats are required')
    lo=points[:,[0,2]].min(0)-1;hi=points[:,[0,2]].max(0)+1;shape=np.ceil((hi-lo)/.1).astype(int)[::-1]
    if np.prod(shape)>max_cells:raise ValueError('Ground extent is too large for the 10cm occupancy grid; split the workspace')
    occupied=np.zeros(shape,np.uint8);ij=np.floor((points[:,[0,2]]-lo)/.1).astype(int);occupied[ij[:,1],ij[:,0]]=1;closed=cv2.morphologyEx(occupied,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)));holes=binary_fill_holes(closed)&~closed.astype(bool)
    np.savez_compressed(root/'floor_hole_audit.npz',occupancy=occupied,closed=closed,holes=holes,lo=lo)
    return {'grid_shape':shape.tolist(),'occupied_area_m2':float(occupied.sum()*.01),'enclosed_hole_area_m2':float(holes.sum()*.01)}
