import asyncio,sys,types
import pytest
from google_streetview_gaussian.collection import collect
from google_streetview_gaussian.io import selected_sources,read

def metadata(pid,date,lat=0.,lon=0.,neighbors=None,dates=None):
    return dict(id=pid,date=date,lat=lat,lon=lon,heading=0.,elevation=None,neighbors=neighbors or [],dates=dates or [])

def test_collection_follows_historical_date_but_never_substitutes_month(tmp_path,monkeypatch):
    table={'seed':metadata('seed','2025-08',neighbors=[dict(id='outside',lat=.01,lon=0)],dates=[dict(id='september',label='2025-09')]),'september':metadata('september','2025-09-12',lat=.00001)}
    async def fetch(pid):return table[pid]
    names=['streetview_to_3d','streetview_to_3d.gather_panoramas','streetview_to_3d.gather_panoramas.tools','streetview_to_3d.gather_panoramas.tools.fetch_pano_by_id']
    for name in names:
        module=types.ModuleType(name);module.__path__=[];monkeypatch.setitem(sys.modules,name,module)
    sys.modules[names[-1]].fetch_pano_by_id=fetch
    result=asyncio.run(collect(tmp_path,'seed',(0,0),100,'2025-09',20));assert [s['id'] for s in result]==['september'];survey=read(tmp_path/'area_survey.json');assert 'outside' not in survey['inspected'];assert survey['inspection_limit_reached'] is False

@pytest.mark.parametrize('entry',[metadata('bad','2025-08'),metadata('bad','2025-09',lat=1.)])
def test_prepared_selection_rejects_wrong_month_or_outside_radius(entry):
    with pytest.raises(ValueError):selected_sources(dict(center=[0,0],radius_m=100,required_date='2025-09',accepted={'bad':entry}))
