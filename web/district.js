"use strict";
(function(){
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const state={features:[],rows:[],selected:params.get("code")||"",year:null,metric:"built_km2",map:null,source:null};
const metrics={built_km2:["不透水面面积","km²"],expansion_km2:["阶段净扩张","km²"],annual_expansion_intensity_pct:["年均扩张强度","%"],intensive_score:["集约利用得分","分"]};
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString("zh-CN",{maximumFractionDigits:d}):"—";
const featureCode=f=>String(f.properties.code);
const featureName=f=>f.properties.district;
function bounds(geometry){
 const points=[];function walk(value){if(Array.isArray(value)&&typeof value[0]==="number"&&typeof value[1]==="number")points.push(value);else if(Array.isArray(value))value.forEach(walk);}
 walk(geometry.coordinates);return [[Math.min(...points.map(p=>p[0]),106),Math.min(...points.map(p=>p[1]),29)],[Math.max(...points.map(p=>p[0]),107),Math.max(...points.map(p=>p[1]),30)]];
}
function currentRow(){return state.rows.find(r=>String(r.code)===state.selected&&Number(r.year)===Number(state.year));}
function renderProfile(){
 const f=state.features.find(x=>featureCode(x)===state.selected),row=currentRow();
 $("district-heading").textContent=f?featureName(f)+" · 三维空间":"重庆区县三维空间";
 $("district-subtitle").textContent=f?"独立区县地形、边界和建设用地专题场景":"选择研究区县，查看地形起伏、行政边界和建设用地专题数据。";
 $("profile-name").textContent=f?featureName(f):"请选择区县";$("profile-group").textContent=f?f.properties.group+" · "+state.selected:"—";
 $("stat-built").textContent=row?fmt(row.built_km2)+" km²":"—";$("stat-growth").textContent=row?fmt(row.expansion_km2)+" km²":"—";$("stat-intensity").textContent=row?fmt(row.annual_expansion_intensity_pct)+"%":"—";$("stat-score").textContent=row?fmt(row.intensive_score,3):"—";
 $("map-year-label").textContent=state.year+" 年";$("map-metric-label").textContent=metrics[state.metric][0];
 const history=$("year-history");history.replaceChildren();
 state.rows.filter(r=>String(r.code)===state.selected).sort((a,b)=>a.year-b.year).forEach(r=>{const item=document.createElement("div");item.className="history-row";const left=document.createElement("span"),right=document.createElement("strong");left.textContent=r.year+" 年";right.textContent=fmt(r[state.metric])+" "+metrics[state.metric][1];item.append(left,right);history.append(item);});
}
function selectDistrict(code,fly=true){
 const f=state.features.find(x=>featureCode(x)===String(code));if(!f)return;state.selected=String(code);$("district-select").value=state.selected;
 document.querySelectorAll("[data-code]").forEach(b=>b.classList.toggle("active",b.dataset.code===state.selected));
 if(state.map&&fly)state.map.fitBounds(bounds(f.geometry),{padding:65,duration:1100,maxZoom:11.5});
 if(state.source)state.source.setData({type:"FeatureCollection",features:state.features.map(x=>({...x,properties:{...x.properties,selected:featureCode(x)===state.selected}}))});
 renderProfile();
}
function initMap(){
 if(!window.maplibregl)throw new Error("MapLibre 未加载，请检查网络。");
 state.map=new maplibregl.Map({container:"district-map",center:[106.55,29.6],zoom:8.2,pitch:62,bearing:-15,maxPitch:82,antialias:true,style:{version:8,sources:{osm:{type:"raster",tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],tileSize:256,attribution:"© OpenStreetMap contributors",maxzoom:19},dem:{type:"raster-dem",tiles:["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],encoding:"terrarium",tileSize:256,maxzoom:15}},layers:[{id:"background",type:"background",paint:{"background-color":"#dceaf3"}},{id:"terrain-hillshade",type:"hillshade",source:"dem",paint:{"hillshade-exaggeration":0.35}},{id:"osm",type:"raster",source:"osm",paint:{"raster-opacity":0.68}}]},canvasContextAttributes:{antialias:true}});
 state.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"top-right");
 state.map.on("load",()=>{
  state.map.setTerrain({source:"dem",exaggeration:1.35});
  state.map.addSource("districts",{type:"geojson",data:{type:"FeatureCollection",features:state.features}});
  state.source=state.map.getSource("districts");
  state.map.addLayer({id:"district-fill",type:"fill",source:"districts",paint:{"fill-color":["case",["boolean",["get","selected"],false],"#e4a34e","#4d91bd"],"fill-opacity":["case",["boolean",["get","selected"],false],0.45,0.12]}});
  state.map.addLayer({id:"district-outline",type:"line",source:"districts",paint:{"line-color":["case",["boolean",["get","selected"],false],"#e18c35","#397aa8"],"line-width":["case",["boolean",["get","selected"],false],3,1.1]}});
  state.map.addLayer({id:"district-extrusion",type:"fill-extrusion",source:"districts",paint:{"fill-extrusion-color":["case",["boolean",["get","selected"],false],"#e3a14b","#4b91b7"],"fill-extrusion-height":["case",["boolean",["get","selected"],false],1200,0],"fill-extrusion-base":0,"fill-extrusion-opacity":0.28}});
  selectDistrict(state.selected||featureCode(state.features[0]));
 });
 state.map.on("click","district-fill",event=>{const f=event.features&&event.features[0];if(f)selectDistrict(f.properties.code);});
}
function renderSelectors(){
 const options=state.features.map(f=>({code:featureCode(f),name:featureName(f),group:f.properties.group}));
 $("district-select").replaceChildren();$("district-list").replaceChildren();
 options.forEach(f=>{const option=document.createElement("option");option.value=f.code;option.textContent=f.name;$("district-select").append(option);const button=document.createElement("button");button.type="button";button.dataset.code=f.code;button.textContent=f.name;button.addEventListener("click",()=>selectDistrict(f.code));$("district-list").append(button);});
 const years=[...new Set(state.rows.map(r=>Number(r.year)))].sort((a,b)=>a-b);state.year=years.includes(2022)?2022:years.at(-1);$("year-select").replaceChildren();years.forEach(y=>{const option=document.createElement("option");option.value=y;option.textContent=y;$("year-select").append(option);});$("year-select").value=String(state.year);
}
async function start(){
 try{
  const [geo,rows]=await Promise.all([fetch("/districts.geojson").then(r=>{if(!r.ok)throw Error("区县边界读取失败");return r.json();}),fetch("/dashboard.json").then(r=>{if(!r.ok)throw Error("研究观测读取失败");return r.json();})]);
  state.features=geo.features;state.rows=rows;renderSelectors();initMap();renderProfile();
  $("district-select").addEventListener("change",e=>selectDistrict(e.target.value));
  $("year-select").addEventListener("change",e=>{state.year=Number(e.target.value);renderProfile();});
  $("metric-select").addEventListener("change",e=>{state.metric=e.target.value;renderProfile();});
  $("terrain-toggle").addEventListener("change",e=>state.map&&state.map.setTerrain(e.target.checked?{source:"dem",exaggeration:1.35}:null));
  $("boundary-toggle").addEventListener("change",e=>{if(state.map&&state.map.getLayer("district-outline"))state.map.setLayoutProperty("district-outline","visibility",e.target.checked?"visible":"none");});
  $("hillshade-toggle").addEventListener("change",e=>{if(state.map&&state.map.getLayer("terrain-hillshade"))state.map.setLayoutProperty("terrain-hillshade","visibility",e.target.checked?"visible":"none");});
  $("district-fullscreen").addEventListener("click",()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen?.());
 }catch(error){$("district-subtitle").textContent="场景加载失败："+error.message;}
}
start();
})();
