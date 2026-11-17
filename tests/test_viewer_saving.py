import base64,importlib.util,io,json,threading,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
import pytest
import google_streetview_gaussian

@pytest.fixture
def server(tmp_path):
    path=Path(google_streetview_gaussian.__file__).parent/'web/server.py';spec=importlib.util.spec_from_file_location('capture_server_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=tmp_path;module.DOWNLOADS=tmp_path/'downloads';http=ThreadingHTTPServer(('127.0.0.1',0),module.Handler);module.PORT=http.server_port;thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield module,f'http://127.0.0.1:{http.server_port}'
    http.shutdown();http.server_close();thread.join(timeout=5)

def png(size=(8,8)):
    stream=io.BytesIO();Image.new('RGB',size,(30,80,120)).save(stream,format='PNG');return base64.b64encode(stream.getvalue()).decode()

def post(url,data,origin=None):
    return urllib.request.urlopen(urllib.request.Request(url+'/api/save-pair',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':origin or url}),timeout=5)

def test_both_pngs_saved_without_browser_multiple_download_permission(server):
    module,url=server;data=dict(prefix='capture_20250101T010203Z',gaussian=png(),streetview=png())
    with post(url,data) as response:result=json.load(response)
    assert len(result['saved'])==2
    for item in result['saved']:
        file=module.DOWNLOADS/item['name'];assert file.exists();assert Image.open(file).size==(8,8)
        with urllib.request.urlopen(url+item['url'],timeout=5) as response:assert response.read()==file.read_bytes()
    with post(url,data) as response:again=json.load(response)
    assert {x['name'] for x in result['saved']}.isdisjoint(x['name'] for x in again['saved'])

@pytest.mark.parametrize('patch,origin',[({'prefix':'../escape'},None),({'streetview':png((9,8))},None),({},'https://unrelated.example')])
def test_invalid_capture_requests_do_not_write_files(server,patch,origin):
    module,url=server;data=dict(prefix='capture_20250101T010203Z',gaussian=png(),streetview=png());data.update(patch)
    with pytest.raises(urllib.error.HTTPError) as error:post(url,data,origin)
    assert error.value.code in [400,403];assert not module.DOWNLOADS.exists()
