import json
import numpy as np
from PIL import Image,ImageChops
from google_streetview_gaussian.backend import ROTATIONS
from google_streetview_gaussian.cubemap import CubeSampler
from google_streetview_gaussian.panorama import crop,project

def test_cube_axes_and_seam_use_actual_neighbor_pixels():
    colors=np.array([[255,0,0],[0,255,0],[0,0,255],[255,255,0],[255,0,255],[0,255,255]],np.uint8);images=[];cameras=[]
    for (name,R),color in zip(ROTATIONS.items(),colors):
        image=np.tile(color,(32,32,1));images.append(image);T=np.eye(4);T[:3,:3]=R;cameras.append(dict(face=name,w=32,h=32,fl_x=16,fl_y=16,cx=16,cy=16,camera_to_station_cv=T.tolist()))
    sampler=CubeSampler(images,[np.ones((32,32),bool)]*6,cameras)
    rays=np.array([[0,0,1],[1,0,0],[0,0,-1],[-1,0,0],[0,-1,0],[0,1,0]],float);rgb,valid,_=sampler.sample(rays)
    assert valid.all();np.testing.assert_array_equal(rgb,colors)
    rgb,valid,stats=sampler.sample(np.array([[1.,0,1.]]));assert valid.all();assert stats['pixels_with_cross_face_taps']==1;np.testing.assert_allclose(rgb[0],[188,188,0],atol=1)

def test_aspect_crop_does_not_resample_or_generate_pixels(tmp_path):
    pixels=np.arange(300*100*3,dtype=np.uint32).reshape(100,300,3).astype(np.uint8);source=tmp_path/'input.png';target=tmp_path/'crop.png';Image.fromarray(pixels).save(source);crop(source,target,2.5)
    output=Image.open(target);assert output.size==(250,100);assert ImageChops.difference(output,Image.open(source).crop((25,0,275,100))).getbbox() is None

def test_panorama_reports_source_provenance(tmp_path):
    source=tmp_path/'source.png';Image.new('RGB',(256,128),(75,110,155)).save(source);target=tmp_path/'projected.png';project(target,image=source,width=160,aspect=2.5,hfov=225,cube_size=32)
    output=Image.open(target);assert output.size==(160,64);np.testing.assert_allclose(np.array(output),np.tile([75,110,155],(64,160,1)),atol=1)
    report=json.loads(target.with_suffix('.json').read_text());assert report['generative_ai_used'] is False;assert report['inpainting_used'] is False;assert len(report['source_sha256'])==64
