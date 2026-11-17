import * as THREE from 'three';

// Reproject original panorama pixels; do not synthesize another camera position.
export class ReferenceRenderer {
 constructor(canvas) {
  this.renderer=new THREE.WebGLRenderer({canvas,antialias:false,preserveDrawingBuffer:true});
  this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.setPixelRatio(1);
  this.cache=new Map();this.loader=new THREE.TextureLoader();
  this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-1,1,1,-1,0,2);this.camera.position.z=1;
  this.material=new THREE.ShaderMaterial({depthTest:false,depthWrite:false,uniforms:{panorama:{value:null},rayToPano:{value:new THREE.Matrix3()},tanVertical:{value:1},aspect:{value:1}},
   vertexShader:'varying vec2 screenUv; void main(){screenUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
   fragmentShader:`precision highp float;
    varying vec2 screenUv;uniform sampler2D panorama;uniform mat3 rayToPano;uniform float tanVertical;uniform float aspect;
    void main(){vec2 s=screenUv*2.-1.;vec3 q=rayToPano*vec3(s.x*tanVertical*aspect,s.y*tanVertical,-1.);
     float u=atan(q.x,q.z)/6.283185307179586+.5;
     float v=atan(q.y,length(q.xz))/3.141592653589793+.5;
     gl_FragColor=texture2D(panorama,vec2(u,1.-v));
     #include <colorspace_fragment>
    }`});
  this.scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.material));
 }
 async load(source) {
  if(this.cache.has(source.id)){const e=this.cache.get(source.id);e.used=performance.now();return e.promise;}
  const entry={used:performance.now(),texture:null};
  entry.promise=this.loader.loadAsync(source.file).then(texture=>{
   texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=THREE.RepeatWrapping;texture.wrapT=THREE.ClampToEdgeWrapping;
   texture.minFilter=THREE.LinearMipmapLinearFilter;texture.magFilter=THREE.LinearFilter;entry.texture=texture;
   const loaded=[...this.cache.entries()].filter(([id,e])=>e.texture&&id!==source.id).sort((a,b)=>a[1].used-b[1].used);
   while(loaded.length>1){const [id,e]=loaded.shift();e.texture.dispose();this.cache.delete(id);}
   return texture;
  }).catch(error=>{this.cache.delete(source.id);throw error;});
  this.cache.set(source.id,entry);return entry.promise;
 }
 draw(texture,source,pose,width,height) {
  const E=new THREE.Matrix3().set(...source.world_to_pano_cv.flat());
  const ednFromViewer=new THREE.Matrix3().set(1,0,0,0,-1,0,0,0,-1);
  const rotation=new THREE.Matrix3().setFromMatrix4(new THREE.Matrix4().fromArray(pose.matrix_world));
  this.material.uniforms.panorama.value=texture;
  this.material.uniforms.rayToPano.value.copy(E).multiply(ednFromViewer).multiply(rotation);
  this.material.uniforms.tanVertical.value=Math.tan(THREE.MathUtils.degToRad(pose.vertical_fov_degrees)/2);
  this.material.uniforms.aspect.value=width/height;this.renderer.setSize(width,height,false);this.renderer.render(this.scene,this.camera);
 }
 blob(){return new Promise((resolve,reject)=>this.renderer.domElement.toBlob(b=>b?resolve(b):reject(new Error('원본 이미지 저장에 실패했습니다.')),'image/png'));}
}
