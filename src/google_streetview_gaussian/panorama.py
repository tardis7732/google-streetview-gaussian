"""Photo-only cylindrical panorama projection and lossless aspect crops."""
from pathlib import Path
from fractions import Fraction
import math
import numpy as np,cv2
from PIL import Image
from .backend import ROTATIONS
from .cubemap import CubeSampler
from .io import read,write,sha

def cube_from_image(path,size=1280):
    if size<32:raise ValueError('Cube face size must be >= 32')
    image=cv2.imread(str(path))
    if image is None:raise ValueError('Cannot read panorama')
    h,w=image.shape[:2];q=(np.arange(size,dtype=np.float32)+.5-size/2)/(size/2);x,y=np.meshgrid(q,q);rays=np.stack([x,y,np.ones_like(x)],-1);images=[];cameras=[]
    for face,rotation in ROTATIONS.items():
        R=np.array(rotation,dtype=float);d=rays@R.T;mx=((np.arctan2(d[:,:,0],d[:,:,2])/(2*np.pi)+.5)*w).astype(np.float32);my=((np.arctan2(d[:,:,1],np.hypot(d[:,:,0],d[:,:,2]))/np.pi+.5)*h).astype(np.float32)
        images.append(cv2.cvtColor(cv2.remap(image,mx,my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_WRAP),cv2.COLOR_BGR2RGB));T=np.eye(4);T[:3,:3]=R;cameras.append(dict(face=face,w=size,h=size,fl_x=size/2,fl_y=size/2,cx=size/2,cy=size/2,camera_to_station_cv=T.tolist()))
    return CubeSampler(images,[np.ones(i.shape[:2],bool) for i in images],cameras),dict(source=str(Path(path).resolve()),source_sha256=sha(path),cube_source='Reprojected from preserved original equirectangular photograph',cube_size=size)

def cube_from_manifest(path,pano_id=None):
    path=Path(path).resolve();data=read(path);frames=data['frames'];ids={f['pano_id'] for f in frames}
    if pano_id is None:
        if len(ids)!=1:raise ValueError('Multiple panoramas: supply --pano-id')
        pano_id=next(iter(ids))
    rows=[f for f in frames if f['pano_id']==pano_id]
    if len(rows)!=6:raise ValueError('Six cube views are required')
    root=path.parent.parent if path.parent.name=='prepared' else path.parent;images=[];records=[]
    for f in rows:
        file=(root/f['file_path']).resolve()
        with Image.open(file) as im:images.append(np.asarray(im.convert('RGB')))
        records.append(dict(face=f['face'],file=f['file_path'],sha256=sha(file)))
    return CubeSampler(images,[np.ones(i.shape[:2],bool) for i in images],rows),dict(pano_id=pano_id,cube_manifest=str(path),cube_source='Existing native calibrated cube views',cube_files=records)

def project(output,*,image=None,cube_manifest=None,pano_id=None,width=3840,aspect=2.5,hfov=225.,yaw=180.,bottom=30.,cube_size=1280):
    if bool(image)==bool(cube_manifest):raise ValueError('Choose exactly one of image or cube manifest')
    if width<32 or not .2<=aspect<=10 or not 0<hfov<360 or not 0<=bottom<89:raise ValueError('Invalid projection settings')
    height=round(width/aspect)
    if height<16 or width*height>64000000:raise ValueError('Output image is too small or too large')
    sampler,info=cube_from_image(image,cube_size) if image else cube_from_manifest(cube_manifest,pano_id)
    focal=width/math.radians(hfov);top=height/focal-math.tan(math.radians(bottom))
    if top<=0:raise ValueError('Requested crop has no area above the horizon; reduce --bottom')
    theta=math.radians(yaw-hfov/2)+(np.arange(width)+.5)/focal;result=np.empty((height,width,3),np.uint8)
    for start in range(0,height,32):
        stop=min(height,start+32);vertical=(np.arange(start,stop)+.5)/focal-top;angle,y=np.meshgrid(theta,vertical);rays=np.stack([np.sin(angle),y,np.cos(angle)],-1);rgb,valid,_=sampler.sample(rays)
        if not valid.all():raise ValueError('Some rays have no valid original cube observation')
        result[start:stop]=rgb
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(result).save(output)
    write(output.with_suffix('.json'),dict(**info,width=width,height=height,aspect=width/height,projection='cylindrical square pixels',horizontal_fov_degrees=hfov,center_yaw_pano_degrees=yaw,top_elevation_degrees=math.degrees(math.atan(top)),bottom_elevation_degrees=-bottom,generative_ai_used=False,inpainting_used=False))
    return output

def crop(image,output,aspect=2.5):
    if not .2<=aspect<=10:raise ValueError('Aspect must be between .2 and 10')
    ratio=Fraction(str(aspect)).limit_denominator(1000)
    with Image.open(image) as im:
        scale=min(im.width//ratio.numerator,im.height//ratio.denominator)
        if scale<1:raise ValueError('Source image is too small for this exact pixel ratio')
        w,h=scale*ratio.numerator,scale*ratio.denominator;x=(im.width-w)//2;y=(im.height-h)//2;output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);im.crop((x,y,x+w,y+h)).save(output)
    return output
