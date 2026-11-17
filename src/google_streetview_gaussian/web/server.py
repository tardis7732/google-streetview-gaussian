"""Local Gaussian viewer and paired PNG saver. No external image service."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote
import argparse, base64, json, os, re, socket, struct, threading, webbrowser

WEB_ROOT=Path(__file__).resolve().parent
ROOT=WEB_ROOT
DOWNLOADS=Path.home()/'Downloads'
PORT=8870
SAVED={}
SAVE_LOCK=threading.Lock()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def translate_path(self,path):
        name=urlsplit(path).path.lstrip('/')
        if name in {'viewer.html','viewer.css','viewer-app.mjs','reference-renderer.mjs'}:return str(WEB_ROOT/name)
        return super().translate_path(path)
    def json_response(self,status,payload):
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8');self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/capture-capabilities':return self.json_response(200,{'paired_png_save':True,'folder':str(DOWNLOADS)})
        if path.startswith('/api/capture-file/'):
            name=unquote(path.removeprefix('/api/capture-file/'));file=SAVED.get(name)
            if file is None or not file.is_file():return self.send_error(404)
            data=file.read_bytes();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Disposition',f'inline; filename="{name}"');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        return super().do_GET()
    def do_POST(self):
        if urlsplit(self.path).path!='/api/save-pair':return self.send_error(404)
        if self.headers.get('Origin') not in {f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'}:return self.json_response(403,{'error':'뷰어에서만 저장할 수 있습니다.'})
        if self.headers.get_content_type()!='application/json':return self.json_response(415,{'error':'JSON 요청이 필요합니다.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=128*1024*1024:raise ValueError('이미지 요청이 너무 크거나 비어 있습니다.')
            body=json.loads(self.rfile.read(length));prefix=body.get('prefix','')
            if not re.fullmatch(r'capture_\d{8}T\d{6}Z',prefix):raise ValueError('저장 이름이 올바르지 않습니다.')
            images={}
            for kind in ['gaussian','streetview']:
                data=base64.b64decode(body[kind],validate=True)
                if data[:8]!=b'\x89PNG\r\n\x1a\n' or len(data)<33:raise ValueError('PNG 이미지가 아닙니다.')
                width,height=struct.unpack('>II',data[16:24])
                if not (0<width<=8192 and 0<height<=8192 and width*height<=32000000):raise ValueError('지원하지 않는 이미지 크기입니다.')
                images[kind]=data
            if images['gaussian'][16:24]!=images['streetview'][16:24]:raise ValueError('두 이미지의 해상도가 다릅니다.')
            DOWNLOADS.mkdir(exist_ok=True)
            with SAVE_LOCK:
                suffix=0
                while True:
                    stem=prefix+(f'_{suffix}' if suffix else '')
                    paths={kind:DOWNLOADS/f'{stem}_{kind}.png' for kind in images}
                    if all(not p.exists() and not p.with_suffix('.png.tmp').exists() for p in paths.values()):break
                    suffix+=1
                temporary=[]
                try:
                    for kind,file in paths.items():
                        temp=file.with_suffix('.png.tmp');temporary.append(temp)
                        with temp.open('xb') as stream:stream.write(images[kind])
                    for file in paths.values():os.replace(file.with_suffix('.png.tmp'),file);SAVED[file.name]=file
                finally:
                    for temp in temporary:
                        if temp.exists():temp.unlink()
            return self.json_response(200,{'saved':[{'name':p.name,'path':str(p),'url':'/api/capture-file/'+p.name} for p in paths.values()],'folder':str(DOWNLOADS),'width':width,'height':height})
        except (ValueError,KeyError,TypeError) as error:return self.json_response(400,{'error':str(error)})
        except OSError as error:return self.json_response(500,{'error':f'파일 저장에 실패했습니다: {error}'})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--data-dir',type=Path,required=True);parser.add_argument('--port',type=int,default=8870);args=parser.parse_args();ROOT=args.data_dir.expanduser().resolve();PORT=args.port;url=f'http://127.0.0.1:{PORT}/viewer.html'
    if not (ROOT/'manifest.json').is_file():raise SystemExit('Data folder needs manifest.json; run export first')
    with socket.socket() as sock:running=sock.connect_ex(('127.0.0.1',PORT))==0
    if running:
        raise SystemExit(f'Port {PORT} is already in use. Choose another --port so the correct dataset is served.')
    else:
        server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
        if not args.no_browser:webbrowser.open(url)
        print(url+'\nPNG pairs: '+str(DOWNLOADS),flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:server.server_close()
