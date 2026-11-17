import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {SparkRenderer,SplatMesh} from '@sparkjsdev/spark';
import {ReferenceRenderer} from './reference-renderer.mjs';

const $=id=>document.getElementById(id);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,.05,1000);
const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true});renderer.domElement.id='gaussian-canvas';renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);document.body.prepend(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=.1;controls.maxDistance=350;
scene.add(new SparkRenderer({renderer}));
const metadata=await fetch('manifest.json').then(r=>{if(!r.ok)throw new Error('모델 정보를 읽지 못했습니다.');return r.json();});
const splat=new SplatMesh({url:metadata.model_file||'scene.ply'});splat.rotation.x=Math.PI;scene.add(splat);
$('dataset-meta').textContent=`${metadata.date||'촬영월 미지정'} · ${metadata.collection_radius_m??'?'}m`;
$('source-count').textContent=`정렬된 촬영본 ${metadata.sources.length}개 사용`;
let references=[],referenceRenderer,modelReady=false,referenceReady=false,captureBusy=false,previewTimer,previewGeneration=0;
const locations=metadata.sources.map(p=>({id:p.id,p:[p.camera_world[0],-p.camera_world[1],-p.camera_world[2]]}));
locations.forEach((p,i)=>$('location').add(new Option(`지점 ${i+1} · ${p.id.slice(0,7)}`,String(i))));
function street(){const p=locations[Number($('location').value)].p;camera.position.set(...p);controls.target.set(p[0]-7,p[1],p[2]);controls.update();}
function overhead(){camera.position.set(130,150,130);controls.target.set(0,0,0);controls.update();}
function floor(){const p=locations[Number($('location').value)].p;camera.position.set(p[0],p[1]+1,p[2]);controls.target.set(p[0]-2,p[1]-2,p[2]);controls.update();}
$('street').onclick=street;$('location').onchange=street;$('overhead').onclick=overhead;$('floor').onclick=floor;street();
const storageKey='gsvg-camera-v1:'+location.pathname;
try{const saved=JSON.parse(localStorage.getItem(storageKey));if(saved&&[...saved.position,...saved.target].every(Number.isFinite)){camera.position.fromArray(saved.position);controls.target.fromArray(saved.target);if(Number.isInteger(saved.location_index))$('location').value=String(saved.location_index);controls.update();}}catch{}
let savePoseTimer;
function rememberPose(){try{localStorage.setItem(storageKey,JSON.stringify({position:camera.position.toArray(),target:controls.target.toArray(),location_index:Number($('location').value)}));}catch{}}
controls.addEventListener('end',rememberPose);controls.addEventListener('change',()=>{clearTimeout(savePoseTimer);savePoseTimer=setTimeout(rememberPose,300);});
function toggleUI(){const hidden=$('panel').classList.toggle('hidden');$('show-ui').hidden=!hidden;}
$('hide-ui').onclick=toggleUI;$('show-ui').onclick=toggleUI;
addEventListener('keydown',e=>{if(e.key.toLowerCase()==='h'&&!/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))toggleUI();});
function pose(width,height){camera.updateMatrixWorld(true);const d=camera.getWorldDirection(new THREE.Vector3());return {position_viewer:camera.position.toArray(),position_edn:[camera.position.x,-camera.position.y,-camera.position.z],quaternion_xyzw_viewer:camera.quaternion.toArray(),matrix_world:camera.matrixWorld.toArray(),matrix_order:'column-major',coordinate_frame:'viewer: east/up/south; source geometry: east/down/north, metres',width,height,aspect:width/height,vertical_fov_degrees:camera.fov,horizontal_fov_degrees:THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov)/2)*width/height)),heading_degrees:(THREE.MathUtils.radToDeg(Math.atan2(d.x,-d.z))+360)%360,pitch_degrees:THREE.MathUtils.radToDeg(Math.atan2(d.y,Math.hypot(d.x,d.z)))};}
function nearest(position){let best=null;for(const s of references){const p=s.camera_world,dx=position[0]-p[0],dy=position[1]-p[1],dz=position[2]-p[2],distance=Math.hypot(dx,dy,dz);if(!best||distance<best.distance_m)best={source:s,distance_m:distance,horizontal_distance_m:Math.hypot(dx,dz)};}return best;}
function closest(){return nearest([camera.position.x,-camera.position.y,-camera.position.z]);}
function updateButtons(){$('save-gaussian').disabled=captureBusy||!modelReady;$('save-streetview').disabled=captureBusy||!referenceReady;$('save-both').disabled=captureBusy||!modelReady||!referenceReady;$('snap-source').disabled=captureBusy||!referenceReady;}
function updateInfo(){if(!referenceReady)return;const n=closest();$('reference-info').textContent=`${n.source.date} · ${n.source.id.slice(0,10)}… · 촬영 위치까지 ${n.distance_m.toFixed(1)}m`;}
async function updatePreview(){
 if(!referenceReady||captureBusy)return;const seq=++previewGeneration,n=closest();updateInfo();
 try{const texture=await referenceRenderer.load(n.source);if(seq!==previewGeneration||captureBusy)return;const a=camera.aspect,w=Math.max(32,Math.round(Math.min(310,150*a))),h=Math.max(32,Math.round(w/a));referenceRenderer.draw(texture,n.source,pose(w,h),w,h);$('reference-loading').hidden=true;}
 catch(error){if(seq===previewGeneration){$('reference-loading').textContent='원본을 읽지 못했습니다. 다시 저장을 눌러 재시도하세요.';$('reference-loading').hidden=false;console.error(error);}}
}
controls.addEventListener('change',()=>{updateInfo();clearTimeout(previewTimer);previewTimer=setTimeout(updatePreview,180);});
$('snap-source').onclick=()=>{const n=closest(),p=n.source.camera_world,dir=camera.getWorldDirection(new THREE.Vector3()),distance=Math.max(2,camera.position.distanceTo(controls.target));camera.position.set(p[0],-p[1],-p[2]);controls.target.copy(camera.position).addScaledVector(dir,distance);$('location').value=String(locations.findIndex(s=>s.id===n.source.id));controls.update();updatePreview();};
async function initReferences(){try{const response=await fetch('panorama_index.json');if(!response.ok)throw new Error('파노라마 인덱스가 없습니다.');const index=await response.json();references=index.sources;if(!references.length||references.some(s=>String(s.date).slice(0,7)!==metadata.date||!s.world_to_pano_cv))throw new Error('원본 촬영 정보가 맞지 않습니다.');referenceRenderer=new ReferenceRenderer($('reference-canvas'));referenceReady=true;updateButtons();updatePreview();}catch(error){$('reference-info').textContent='원본 파노라마를 사용할 수 없습니다. panorama_index.json과 panoramas 폴더를 확인하세요.';$('reference-loading').hidden=true;console.error(error);}}
initReferences();
function dimensions(){const b=renderer.getDrawingBufferSize(new THREE.Vector2());if($('resolution').value==='screen')return [b.x,b.y];const edge=Number($('resolution').value),a=camera.aspect;return a>=1?[edge,Math.round(edge/a)]:[Math.round(edge*a),edge];}
function nextFrames(n=3){return new Promise(resolve=>{function tick(){if(--n<=0)resolve();else requestAnimationFrame(tick);}requestAnimationFrame(tick);});}
function png(canvas){return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('PNG를 만들지 못했습니다.')),'image/png'));}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function message(text,error=false){$('export-status').textContent=text;$('export-status').classList.toggle('error',error);}
function base64(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('이미지를 읽지 못했습니다.'));reader.readAsDataURL(blob);});}
async function savePair(gaussian,streetview,prefix){
 const [g,s]=await Promise.all([base64(gaussian),base64(streetview)]);
 const response=await fetch('/api/save-pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefix,gaussian:g,streetview:s})});
 let result;try{result=await response.json();}catch{throw new Error('open_viewer.cmd로 뷰어를 다시 열어 주세요.');}
 if(!response.ok)throw new Error(result.error||'두 장을 저장하지 못했습니다.');
 const container=$('saved-files');container.replaceChildren();
 for(const [i,file] of result.saved.entries()){const link=document.createElement('a');link.href=file.url;link.target='_blank';link.textContent=i===0?'저장된 가우시안 열기':'저장된 스트리트뷰 열기';container.append(link);}
 container.hidden=false;container.title=result.folder;
}
async function capture(mode){
 if(captureBusy)return;captureBusy=true;previewGeneration++;clearTimeout(previewTimer);controls.enabled=false;updateButtons();
 const oldSize=renderer.getSize(new THREE.Vector2()),oldRatio=renderer.getPixelRatio(),oldAspect=camera.aspect;
 try{
  const [width,height]=dimensions(),shot=pose(width,height),match=referenceReady?nearest(shot.position_edn):null;
  const stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d+Z$/,'Z'),prefix=`capture_${stamp}`;
  let gaussianBlob,streetBlob;
  if(mode!=='gaussian'){message('같은 방향의 원본 스트리트뷰를 준비하는 중…');const texture=await referenceRenderer.load(match.source);referenceRenderer.draw(texture,match.source,shot,width,height);streetBlob=await referenceRenderer.blob();}
  if(mode!=='streetview'){message('UI 없는 가우시안 이미지를 저장하는 중…');renderer.setPixelRatio(1);renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();await nextFrames(4);renderer.render(scene,camera);gaussianBlob=await png(renderer.domElement);}
  if(mode==='both'){message('다운로드 폴더에 두 PNG를 저장하는 중…');await savePair(gaussianBlob,streetBlob,prefix);}
  else download(mode==='gaussian'?gaussianBlob:streetBlob,`${prefix}_${mode}.png`);
  message(`${mode==='both'?'다운로드 폴더에 두 장 저장 완료':'저장 완료'} · ${width} × ${height}px${match?' · 원본 촬영 위치까지 '+match.distance_m.toFixed(1)+'m':''}`);
 }catch(error){message(`저장 실패: ${error.message}`,true);console.error(error);}
 finally{renderer.setPixelRatio(oldRatio);renderer.setSize(oldSize.x,oldSize.y,false);camera.aspect=oldAspect;camera.updateProjectionMatrix();captureBusy=false;controls.enabled=true;updateButtons();updatePreview();}
}
$('save-gaussian').onclick=()=>capture('gaussian');$('save-streetview').onclick=()=>capture('streetview');$('save-both').onclick=()=>capture('both');
renderer.setAnimationLoop(()=>{if(!captureBusy)controls.update();renderer.render(scene,camera);});
addEventListener('resize',()=>{if(captureBusy)return;camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);updatePreview();});
try{await splat.initialized;modelReady=true;$('status').textContent=`${metadata.sources.length}개 촬영 지점 · ${metadata.gaussians.toLocaleString()} 가우시안`;updateButtons();}catch(error){$('status').textContent='가우시안을 불러오지 못했습니다. 새로고침해 다시 시도하세요.';console.error(error);}
window.viewer={scene,camera,renderer,controls,overhead,street};
