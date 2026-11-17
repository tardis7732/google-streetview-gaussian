import importlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
from plyfile import PlyData,PlyElement
from google_streetview_gaussian.backend import prepare
from google_streetview_gaussian.io import write,read
from google_streetview_gaussian.cli import main

def test_prepare_creates_fixed_rigs_and_preserves_all_training_pixels(tmp_path):
    source=tmp_path/'panorama.png';Image.new('RGB',(128,64),(60,100,150)).save(source);sources={}
    for i in range(2):sources[f'p{i}']=dict(id=f'p{i}',date='2025-09',lat=0,lon=i*.00001,heading=0.,elevation=None,neighbors=[])
    write(tmp_path/'area_survey.json',dict(center=[0,0],radius_m=100,required_date='2025-09',accepted=sources));write(tmp_path/'photo_paths.json',{pid:str(source) for pid in sources});job=prepare(tmp_path,32);manifest=read(job/'prepared/manifest.json');assert len(manifest['frames'])==12;assert manifest['processing_options']=={'remove_sky':False,'mask_dynamic':False}
    for f in manifest['frames']:
        assert np.array(Image.open(job/f['mask_path'])).min()==255;assert np.array(Image.open(job/f['sfm_mask_path'])).min()==255;assert np.array(Image.open(job/f['sky_mask_path'])).max()==0

def make_ground_run(root):
    job=root/'reconstruction';frames=[];sources={};paths={}
    for i,center in enumerate([[0.,0,0],[1.,0,0],[0.,0,1.]]):
        pid=f'p{i}';pose=np.diag([1.,-1,-1,1]);pose[:3,3]=center;frames.append(dict(face='front',pano_id=pid,transform_matrix=pose.tolist()));sources[pid]=dict(id=pid,date='2025-09',lat=0.,lon=i*.00001,heading=0.,elevation=None,neighbors=[]);photo=root/f'{pid}.jpg';Image.new('RGB',(256,128),(100,110,120)).save(photo);paths[pid]=str(photo);(root/'labels').mkdir(exist_ok=True);Image.new('L',(256,128),0).save(root/'labels'/f'{pid}.png')
    write(root/'area_survey.json',dict(center=[0,0],radius_m=100,required_date='2025-09',accepted=sources));write(root/'photo_paths.json',paths);write(root/'labels_complete.json',dict(count=3));write(job/'training/prepared_receipt.json',{});write(job/'training/dataset/transforms_train.json',dict(frames=frames));write(job/'sfm/gps_report.json',dict(origin=dict(lat=0.,lng=0.)))
    (job/'sfm/dataset').mkdir(parents=True,exist_ok=True);x,z=np.meshgrid(np.linspace(-.8,.8,9),np.linspace(-.8,.8,9));points=np.stack([x.ravel(),np.full(x.size,2.),z.ravel()],1);np.savez(job/'sfm/dataset/init_points.npz',xyz=points)
    dtype=[(k,'<f4') for k in ['x','y','z','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3']];v=np.zeros(4,dtype=dtype);v['y']=2;v['opacity']=2;v['rot_0']=1
    for k in ['scale_0','scale_1','scale_2']:v[k]=np.log(.05)
    folder=job/'training/refined';folder.mkdir(parents=True);PlyData([PlyElement.describe(v,'vertex')],text=False).write(folder/'final.ply')

def test_ground_hybrid_and_repair_preserve_existing_gaussians(tmp_path,monkeypatch):
    make_ground_run(tmp_path);monkeypatch.setenv('GSVG_RUN',str(tmp_path));sys.modules.pop('google_streetview_gaussian.recipes.context',None);sys.modules.pop('google_streetview_gaussian.recipes.legacy',None)
    main(['ground','--run',str(tmp_path)]);main(['hybrid','--run',str(tmp_path)]);before=PlyData.read(tmp_path/'output/model.ply')['vertex'].data.copy();main(['repair','--run',str(tmp_path)]);after=PlyData.read(tmp_path/'holefix/model.ply')['vertex'].data;report=read(tmp_path/'holefix/manifest.json')
    assert len(after)>=len(before);np.testing.assert_array_equal(after[:len(before)],before);assert report['ground_hole_repair']['existing_gaussians_deleted']==0;assert report['ground_hole_repair']['added_gaussians']>0;assert all(np.isfinite(after[k]).all() for k in after.dtype.names)
    main(['export','--run',str(tmp_path),'--model',str(tmp_path/'holefix/model.ply'),'--output',str(tmp_path/'viewer')]);index=read(tmp_path/'viewer/panorama_index.json');assert len(index['sources'])==3;assert all(s['date']=='2025-09' for s in index['sources'])

def test_local_plane_fit_supports_numpy_two_batch_rhs(tmp_path,monkeypatch):
    monkeypatch.setenv('GSVG_RUN',str(tmp_path));module=importlib.import_module('google_streetview_gaussian.recipes.context');x,z=np.meshgrid(np.linspace(-2,2,11),np.linspace(-2,2,11));support=np.stack([x.ravel(),2+.03*x.ravel()-.02*z.ravel(),z.ravel()],1)
    from scipy.spatial import cKDTree
    query=np.array([[0.,0,0],[.5,0,-.4]]);beta,valid=module.surface(query,support,cKDTree(support[:,[0,2]]));assert valid.all();np.testing.assert_allclose(beta[:,:2],np.tile([.03,-.02],(2,1)),atol=1e-3);np.testing.assert_allclose(beta[:,2],2+.03*query[:,0]-.02*query[:,2],atol=1e-3)
