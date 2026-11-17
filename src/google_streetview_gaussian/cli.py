import argparse,asyncio,json,os,runpy,subprocess,sys
from pathlib import Path

def parser():
    p=argparse.ArgumentParser(description='Google Street View Gaussian reconstruction and capture toolkit');sub=p.add_subparsers(dest='command',required=True)
    def workspace(name,help):
        s=sub.add_parser(name,help=help);s.add_argument('--run',type=Path,required=True);return s
    s=workspace('collect','Collect metadata with an exact month and radius');s.add_argument('--seed-pano',required=True);s.add_argument('--lat',type=float,required=True);s.add_argument('--lon',type=float,required=True);s.add_argument('--radius',type=float,default=100);s.add_argument('--month',required=True);s.add_argument('--max-inspected',type=int,default=300)
    s=workspace('download','Download accepted original panoramas');s.add_argument('--zoom',type=int,default=4)
    workspace('labels','Generate road/protection labels without masking training RGB')
    s=workspace('prepare','Make six calibrated 90-degree views per panorama');s.add_argument('--face-size',type=int,default=1280)
    for name in ['sfm','train']:
        s=workspace(name,'Run the pinned streetview-to-ply '+name+' backend');s.add_argument('--backend',type=Path,required=True);s.add_argument('--allow-unpinned-backend',action='store_true')
        if name=='sfm':s.add_argument('--minimum-coverage',type=float,default=1.);s.add_argument('--recovery-neighbors',type=int,default=16)
        else:s.add_argument('--brush',type=Path,required=True);s.add_argument('--max-splats',type=int,default=4000000)
    s=workspace('ground','Build a locally observed road surface');s.add_argument('--legacy',type=Path)
    workspace('hybrid','Fuse Brush and constrained photo-colored ground')
    workspace('repair','Fill bounded ground gaps and road-observed borders')
    s=workspace('export','Export registered cameras, source references and Gaussian PLY');s.add_argument('--model',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('viewer',help='Open local Gaussian/reference PNG capture tools');s.add_argument('--data-dir',type=Path,required=True);s.add_argument('--port',type=int,default=8870);s.add_argument('--no-browser',action='store_true')
    s=sub.add_parser('panorama',help='Reproject real cube/photo pixels into a cylindrical panorama');g=s.add_mutually_exclusive_group(required=True);g.add_argument('--image',type=Path);g.add_argument('--cube-manifest',type=Path);s.add_argument('--pano-id');s.add_argument('--output',type=Path,required=True);s.add_argument('--width',type=int,default=3840);s.add_argument('--aspect',type=float,default=2.5);s.add_argument('--hfov',type=float,default=225);s.add_argument('--yaw',type=float,default=180);s.add_argument('--bottom',type=float,default=30);s.add_argument('--cube-size',type=int,default=1280)
    s=sub.add_parser('crop',help='Crop to an exact aspect ratio without synthesis or pixel resizing');s.add_argument('--image',type=Path,required=True);s.add_argument('--output',type=Path,required=True);s.add_argument('--aspect',type=float,default=2.5)
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if hasattr(args,'run'):args.run=args.run.expanduser().resolve();os.environ['GSVG_RUN']=str(args.run)
        if args.command=='collect':
            from .collection import collect
            if not -90<=args.lat<=90 or not -180<=args.lon<=180:raise ValueError('Invalid geographic center')
            asyncio.run(collect(args.run,args.seed_pano,(args.lat,args.lon),args.radius,args.month,args.max_inspected))
        elif args.command=='download':
            from .collection import download
            asyncio.run(download(args.run,args.zoom))
        elif args.command=='labels':
            from .collection import labels
            labels(args.run)
        elif args.command=='prepare':
            from .backend import prepare
            print(prepare(args.run,args.face_size))
        elif args.command=='sfm':
            from .backend import sfm
            sfm(args.run,args.backend,args.minimum_coverage,args.recovery_neighbors,args.allow_unpinned_backend)
        elif args.command=='train':
            from .backend import train
            if args.max_splats<1:raise ValueError('--max-splats must be positive')
            train(args.run,args.backend,args.brush,args.max_splats,args.allow_unpinned_backend)
        elif args.command in ['ground','hybrid','repair']:
            if args.command=='ground':
                if args.legacy:os.environ['GSVG_LEGACY']=str(args.legacy.resolve())
                else:os.environ.pop('GSVG_LEGACY',None)
            if args.command=='repair':
                from .repair import audit
                print(json.dumps(audit(args.run)))
            runpy.run_module('google_streetview_gaussian.recipes.'+args.command,run_name='__main__')
        elif args.command=='export':
            from .export import export
            print(export(args.run,args.model,args.output))
        elif args.command=='viewer':
            server=Path(__file__).parent/'web/server.py';command=[sys.executable,str(server),'--data-dir',str(args.data_dir.resolve()),'--port',str(args.port)]
            if args.no_browser:command.append('--no-browser')
            raise SystemExit(subprocess.call(command))
        elif args.command=='panorama':
            from .panorama import project
            print(project(args.output,image=args.image,cube_manifest=args.cube_manifest,pano_id=args.pano_id,width=args.width,aspect=args.aspect,hfov=args.hfov,yaw=args.yaw,bottom=args.bottom,cube_size=args.cube_size))
        elif args.command=='crop':
            from .panorama import crop
            print(crop(args.image,args.output,args.aspect))
    except (ValueError,FileNotFoundError,FileExistsError,ModuleNotFoundError) as error:raise SystemExit(str(error)) from error

if __name__=='__main__':main()
