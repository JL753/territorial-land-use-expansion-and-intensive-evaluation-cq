"use strict";
(function(){
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const state={features:[],rows:[],landcoverRows:[],selected:params.get("code")||"",year:null,metric:"built_km2",map:null,source:null,osmSequence:0};
const metrics={built_km2:["不透水面面积","km²"],expansion_km2:["阶段净扩张","km²"],annual_expansion_intensity_pct:["年均扩张强度","%"],intensive_score:["集约利用得分","分"]};
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString("zh-CN",{maximumFractionDigits:d}):"—";
const code=f=>String(f.properties.code),name=f=>f.properties.district;
function bounds(geometry){const points=[];function walk(value){if(Array.isArray(value)&&typeof value[0]==="number"&&typeof value[1]==="number")points.push(value);else if(Array.isArray(value))value.forEach(walk);}walk(geometry.coordinates);return [[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1]))],[Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))]];}
function row(){const base=state.rows.find(r=>String(r.code)===state.selected&&Number(r.year)===Number(state.year));const lc=state.landcoverRows.find(r=>String(r.code)===state.selected&&Number(r.year)===Number(state.year));return base||lc?{...(base||{}),...(lc||{})}:null;}
function profile(){
 const f=state.features.find(x=>code(x)===state.selected),r=row();
 $("district-heading").textContent=f?name(f)+" · 三维空间":"重庆区县三维空间";
 $("district-subtitle").textContent=f?f.properties.group+" · "+state.selected+" · 独立区县地形与建设用地专题场景":"选择研究区县，查看地形起伏、行政边界和已发布研究数据。";
 $("profile-name").textContent=f?name(f):"请选择区县";$("profile-group").textContent=f?f.properties.group+" · "+state.selected:"—";
 $("stat-built").textContent=r?fmt(r.built_km2)+" km²":"—";$("stat-growth").textContent=r?fmt(r.expansion_km2)+" km²":"—";$("stat-intensity").textContent=r?fmt(r.annual_expansion_intensity_pct)+"%":"—";$("stat-score").textContent=r?fmt(r.intensive_score,3):"—";
 $("map-year-label").textContent=state.year+" 年";$("map-metric-label").textContent=metrics[state.metric][0];
 const history=$("year-history");history.replaceChildren();
 const historyMap=new Map();[...state.rows,...state.landcoverRows].filter(x=>String(x.code)===state.selected).forEach(x=>{const year=Number(x.year);historyMap.set(year,{...(historyMap.get(year)||{}),...x});});[...historyMap.values()].sort((a,b)=>a.year-b.year).forEach(x=>{const item=document.createElement("div");item.className="history-row";const left=document.createElement("span"),right=document.createElement("strong");left.textContent=x.year+" 年";right.textContent=fmt(x[state.metric])+" "+metrics[state.metric][1];item.append(left,right);history.append(item);});
}
function selectDistrict(value,fly=true){
 const f=state.features.find(x=>code(x)===String(value));if(!f)return;state.selected=String(value);$("district-select").value=state.selected;
 document.querySelectorAll("[data-code]").forEach(b=>b.classList.toggle("active",b.dataset.code===state.selected));
 if(state.map&&fly)state.map.fitBounds(bounds(f.geometry),{padding:65,duration:1000,maxZoom:11.5});
 if(state.source)state.source.setData({type:"FeatureCollection",features:state.features.map(x=>({...x,properties:{...x.properties,selected:code(x)===state.selected}}))});
 profile();
 if(state.map)loadOsmLayers(state.selected);
}

async function loadOsmLayers(code){
 const sequence=++state.osmSequence;
 const definitions=[
  ["buildings","district-buildings",{id:"district-buildings-3d",type:"fill-extrusion",source:"district-buildings",
   paint:{"fill-extrusion-color":["interpolate",["linear"],["to-number",["get","height_m"]],0,"#b8d0df",12,"#6f9bb8",40,"#3e6f94"],
    "fill-extrusion-height":["coalesce",["to-number",["get","height_m"]],6],"fill-extrusion-base":0,"fill-extrusion-opacity":0.84}}],
  ["roads","district-roads",{id:"district-roads-line",type:"line",source:"district-roads",
   paint:{"line-color":"#e6a95c","line-width":["interpolate",["linear"],["zoom"],8,0.5,14,2.2],"line-opacity":0.82}}],
  ["poi","district-poi",{id:"district-poi-points",type:"circle",source:"district-poi",
   paint:{"circle-radius":["interpolate",["linear"],["zoom"],8,2,15,5],"circle-color":"#bd6f54","circle-stroke-color":"#fff","circle-stroke-width":1}}]
 ];
 const empty={type:"FeatureCollection",features:[]};
 definitions.forEach(([,sourceId])=>{const source=state.map&&state.map.getSource(sourceId);if(source)source.setData(empty);});
 await Promise.all(definitions.map(async ([layer,sourceId])=>{
  try{
   const response=await fetch("/api/v1/osm-layers/"+layer+"/"+code+".geojson");
   if(!response.ok)throw new Error("OSM layer unavailable");
   const data=await response.json();
   if(sequence!==state.osmSequence||!state.map)return;
   if(state.map.getSource(sourceId))state.map.getSource(sourceId).setData(data);
   else state.map.addSource(sourceId,{type:"geojson",data});
   const layerId=layer==="buildings"?"district-buildings-3d":layer==="roads"?"district-roads-line":"district-poi-points";
   if(!state.map.getLayer(layerId))state.map.addLayer(definitions.find(x=>x[0]===layer)[2]);
  }catch(error){
   if(sequence===state.osmSequence&&layer==="buildings")console.info("该区县尚无已发布 OSM 建筑图层",code);
  }
 }));
}

function initMap(){
 if(!window.maplibregl)throw new Error("MapLibre 未加载，请检查网络。");
 state.map=new maplibregl.Map({container:"district-map",center:[106.55,29.6],zoom:8.2,pitch:62,bearing:-15,maxPitch:82,style:{version:8,sources:{osm:{type:"raster",tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],tileSize:256,attribution:"© OpenStreetMap contributors",maxzoom:19},dem:{type:"raster-dem",tiles:["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],encoding:"terrarium",tileSize:256,maxzoom:15}},layers:[{id:"background",type:"background",paint:{"background-color":"#dceaf3"}},{id:"terrain-hillshade",type:"hillshade",source:"dem",paint:{"hillshade-exaggeration":0.35}},{id:"osm",type:"raster",source:"osm",paint:{"raster-opacity":0.68}}]},canvasContextAttributes:{antialias:true}});
 state.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"top-right");
 state.map.on("load",()=>{state.map.setTerrain({source:"dem",exaggeration:1.35});state.map.addSource("districts",{type:"geojson",data:{type:"FeatureCollection",features:state.features}});state.source=state.map.getSource("districts");state.map.addLayer({id:"district-fill",type:"fill",source:"districts",paint:{"fill-color":["case",["boolean",["get","selected"],false],"#e4a34e","#4d91bd"],"fill-opacity":["case",["boolean",["get","selected"],false],0.42,0.12]}});state.map.addLayer({id:"district-outline",type:"line",source:"districts",paint:{"line-color":["case",["boolean",["get","selected"],false],"#e18c35","#397aa8"],"line-width":["case",["boolean",["get","selected"],false],3,1.1]}});selectDistrict(state.selected||code(state.features[0]));});
 state.map.on("click","district-fill",event=>{const f=event.features&&event.features[0];if(f)selectDistrict(f.properties.code);});
}
function selectors(){
 $("district-select").replaceChildren();$("district-list").replaceChildren();
 state.features.forEach(f=>{const option=document.createElement("option");option.value=code(f);option.textContent=name(f);$("district-select").append(option);const button=document.createElement("button");button.type="button";button.dataset.code=code(f);button.textContent=name(f);button.addEventListener("click",()=>selectDistrict(code(f)));$("district-list").append(button);});
 const years=[...new Set([...state.rows,...state.landcoverRows].map(r=>Number(r.year)))].sort((a,b)=>a-b);state.year=years.includes(2022)?2022:years.at(-1);$("year-select").replaceChildren();years.forEach(y=>{const option=document.createElement("option");option.value=y;option.textContent=y;$("year-select").append(option);});$("year-select").value=String(state.year);
}
async function start(){
 try{
  const [geo,panel,landcover]=await Promise.all([fetch("/districts.geojson").then(r=>{if(!r.ok)throw Error("区县边界读取失败");return r.json();}),fetch("/api/v1/research/panel/").then(r=>{if(!r.ok)throw Error("研究面板读取失败");return r.json();}),fetch("/api/v1/landcover-series/").then(r=>r.ok?r.json():{rows:[]}).catch(()=>({rows:[]}))]);
  state.features=geo.features;state.rows=panel.observations;state.landcoverRows=landcover.rows||[];selectors();initMap();profile();
  $("district-select").addEventListener("change",e=>selectDistrict(e.target.value));
  $("year-select").addEventListener("change",e=>{state.year=Number(e.target.value);profile();});
  $("metric-select").addEventListener("change",e=>{state.metric=e.target.value;profile();});
  $("terrain-toggle").addEventListener("change",e=>state.map&&state.map.setTerrain(e.target.checked?{source:"dem",exaggeration:1.35}:null));
  $("boundary-toggle").addEventListener("change",e=>state.map&&state.map.setLayoutProperty("district-outline","visibility",e.target.checked?"visible":"none"));
  $("hillshade-toggle").addEventListener("change",e=>state.map&&state.map.setLayoutProperty("terrain-hillshade","visibility",e.target.checked?"visible":"none"));
  $("district-fullscreen").addEventListener("click",()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen?.());
 }catch(error){$("district-subtitle").textContent="场景加载失败："+error.message;}
}
start();
})();
