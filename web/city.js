"use strict";
const ALL = [[105.26,28.42],[107.75,30.47]];
const CAMPUS = [106.298,29.598];
const POI_COLORS = {"教育":"#eaba6e","医疗":"#f1969b","公园与运动":"#aad67a","公共交通":"#8fd8ea","生活服务":"#c5b1ed"};
const USE_COLORS = {"居住":"#829cbd","商业":"#dc9170","教育":"#e0c17b","其他或未标注":"#9dada3"};
const BASIS_COLORS = {"源高度标签":"#9edfbd","按楼层估算":"#e5c57c","示意拉伸":"#899db0"};
const STORED = "cq-city-views-v1";
const empty = {type:"FeatureCollection",features:[]};
let panel=[], districts, atlas, poi, buildings, city, chart, buildingChart, markers=[], radiusCenter=null, picking=false;
let panelYears=[],year=2022, pane="overview", selected="500106", interval, mode3D=true, ready=false;
const saved = readLocal(STORED,[]);
const controls = {district:["district-fill","district-outline"],volume:["district-volume"],river:["rivers"],cover:["cover"],compare:["compare"],
  change:["change"],envelope:["coverage"],buildings:["buildings","footprints"],road:["roads"],poi:["poi"]};
const select=(id,value)=>get(id).value=String(value);
const checked=name=>get("layer-"+name).checked;
const safeText=(id,value)=>get(id).textContent=value;
const readCity=async url=>{const r=await fetch(url);if(!r.ok)throw Error("数据加载失败 "+url);return r.json();};
const areaUnit=" km²";
const modelLink=document.getElementById("city-scenario");

function cityPane(name){
  pane=name;
  for(const b of document.querySelectorAll("[data-pane]")){
    const active=b.dataset.pane===pane;
    b.setAttribute("aria-pressed",String(active));get("pane-"+b.dataset.pane).hidden=!active;
  }
  if(ready)renderReport();
}
document.querySelectorAll("[data-pane]").forEach(b=>b.onclick=()=>cityPane(b.dataset.pane));

function set3D(enabled){
  mode3D=enabled;
  get("city-3d").setAttribute("aria-pressed",String(enabled));
  safeText("city-3d",enabled?"三维":"二维");
  if(ready){city.easeTo({pitch:enabled?(city.getZoom()>12?58:38):0,bearing:enabled?city.getBearing():0,duration:440});showLayers();}
}

function addImage(name,url){
  city.addSource(name,{type:"image",url,coordinates:atlas.land.corners});
  city.addLayer({id:name,source:name,type:"raster",paint:{"raster-opacity":0.85,"raster-resampling":"nearest","raster-fade-duration":0}});
}
function matchColor(field,dictionary,fallback){
  return ["match",["get",field],...Object.entries(dictionary).flat(),fallback];
}
function loadLayers(rivers,roads){
  // District fills sit under land-cover previews. Outlines and site geometry are above them.
  city.addSource("districts",{type:"geojson",data:districts,promoteId:"code"});
  city.addLayer({id:"district-fill",source:"districts",type:"fill",paint:{
    "fill-color":"#315c50","fill-opacity":0.86
  }});
  addImage("cover","/city/cover-2022.png");
  addImage("compare","/city/cover-2010.png");
  addImage("change","/city/change-2022.png");
  city.addLayer({id:"district-outline",source:"districts",type:"line",paint:{
    "line-color":["case",["boolean",["feature-state","selected"],false],"#fad699","#80a595"],
    "line-width":["case",["boolean",["feature-state","selected"],false],2.4,1.25]
  }});
  city.addLayer({id:"district-volume",source:"districts",type:"fill-extrusion",maxzoom:11,
    paint:{"fill-extrusion-height":0,"fill-extrusion-color":"#315c50","fill-extrusion-opacity":0.78}});
  city.addSource("rivers",{type:"geojson",data:rivers});
  city.addLayer({id:"rivers",source:"rivers",type:"line",paint:{"line-color":"#8ccdd9","line-width":2.2}});
  const [west,south,east,north]=atlas.osm.bbox;
  city.addSource("coverage",{type:"geojson",data:{type:"Feature",properties:{},
    geometry:{type:"LineString",coordinates:[[west,south],[east,south],[east,north],[west,north],[west,south]]}}});
  city.addLayer({id:"coverage",source:"coverage",type:"line",minzoom:10.5,
    paint:{"line-color":"#ffe398","line-width":1.5,"line-dasharray":[3,3]}});
  city.addSource("roads",{type:"geojson",data:roads});
  city.addLayer({id:"roads",source:"roads",type:"line",minzoom:12,paint:{"line-color":"#a5b8a9","line-width":1.8}});
  city.addSource("radius",{type:"geojson",data:empty});
  city.addLayer({id:"radius-fill",source:"radius",type:"fill",paint:{"fill-color":"#f7df83","fill-opacity":0.18}});
  city.addLayer({id:"radius-line",source:"radius",type:"line",paint:{"line-color":"#f1dc83","line-width":2}});
  city.addSource("buildings",{type:"geojson",data:buildings});
  city.addLayer({id:"footprints",type:"fill",source:"buildings",minzoom:12,paint:{"fill-color":matchColor("type",USE_COLORS,"#859c90"),"fill-opacity":0.87}});
  city.addLayer({id:"buildings",type:"fill-extrusion",source:"buildings",minzoom:12,paint:{
    "fill-extrusion-color":matchColor("type",USE_COLORS,"#859c90"),
    "fill-extrusion-height":["get","height"],"fill-extrusion-opacity":0.95,
  }});
  city.addSource("poi",{type:"geojson",data:poi});
  city.addLayer({id:"poi",type:"circle",source:"poi",minzoom:12,paint:{
    "circle-radius":["interpolate",["linear"],["zoom"],12,3,16,5.5],
    "circle-color":matchColor("type",POI_COLORS,"#dbe7db"),"circle-stroke-color":"#142d29","circle-stroke-width":1.3
  }});
}
function showLayers(){
  for(const [name,ids] of Object.entries(controls)){
    for(const id of ids){
      const rasterYear=atlas.land.years.includes(year);
      const enabled=checked(name)&&(id!=="cover"||rasterYear)&&(id!=="change"||(rasterYear&&year!==atlas.land.years[0]))
        &&(id!=="district-volume"||(mode3D&&checked("district")&&!checked("cover")&&!checked("compare")&&!checked("change")))
        &&(id!=="buildings"||mode3D)&&(id!=="footprints"||!mode3D);
      city.setLayoutProperty(id,"visibility",enabled?"visible":"none");
    }
  }
  get("layer-cover").disabled=!atlas.land.years.includes(year);
  get("layer-change").disabled=!atlas.land.years.includes(year)||year===atlas.land.years[0];
  const multiplier=Number(get("height-scale").value);
  safeText("height-value",multiplier+"× · 仅影响显示");
  city.setPaintProperty("buildings","fill-extrusion-height",["*",["get","height"],multiplier]);
  city.setPaintProperty("compare","raster-opacity",Number(get("compare-opacity").value)/100);
  const basis=get("building-color").value;
  const scheme=matchColor(basis,basis==="basis"?BASIS_COLORS:USE_COLORS,"#859c90");
  city.setPaintProperty("footprints","fill-color",scheme);
  city.setPaintProperty("buildings","fill-extrusion-color",scheme);
  const category=get("poi-type").value;
  city.setFilter("poi",category?["==",["get","type"],category]:null);
  updateMarkers();
  legend();
}
function updateMarkers(){
  const visible=checked("district")&&city.getZoom()<11;
  for(const marker of markers)marker.getElement().hidden=!visible;
}
function legend(){
  const active=[];
  if((checked("cover")&&!get("layer-cover").disabled)||checked("compare"))active.push(...classNames.map((n,i)=>[n,atlas.land.colors[i]]));
  if(checked("change")&&!get("layer-change").disabled)active.push(["新增不透水面","#ef873e"],["转出不透水面","#79c9da"]);
  if(city.getZoom()>=11&&checked("envelope"))active.push(["虎溪快照覆盖框","#ffe398"]);
  if(city.getZoom()>=12&&checked("buildings"))active.push(...Object.entries(get("building-color").value==="basis"?BASIS_COLORS:USE_COLORS));
  if(city.getZoom()>=12&&checked("poi"))active.push(...Object.entries(POI_COLORS));
  if(checked("volume")&&mode3D&&city.getZoom()<11&&!checked("cover")&&!checked("compare")&&!checked("change"))
    active.push(["柱高表示本专题值","#aed18d"]);
  if(!active.length&&checked("district"))active.push(["较低","#274b43"],["较高","#bfd18d"],["当前区县","#fad699"]);
  get("city-legend").replaceChildren(...active.map(([label,color])=>{
    const item=make("span",null,"legend-item"),swatch=make("i");
    swatch.style.background=color;item.append(swatch,document.createTextNode(label));return item;
  }));
  get("city-legend").hidden=!active.length;
  get("building-key").textContent=get("building-color").value==="basis"
    ?"源高度标签、楼层估算与示意拉伸分别着色。"
    :"用途按 OSM 标签分组。多数轮廓缺少真实高度。";
}
function setYear(value){
  year=Number(value);if(!ready)return;
  for(const b of get("city-years").children)b.setAttribute("aria-pressed",String(Number(b.textContent)===year));
  const previous=panelYears[panelYears.indexOf(year)-1];
  safeText("period-note",previous?`${previous}—${year} 阶段${atlas.land.years.includes(year)?"":" · 暂无对应栅格预览"}`:"基准期 · 无阶段变化");
  if(atlas.land.years.includes(year))city.getSource("cover").updateImage({url:`/city/cover-${year}.png`,coordinates:atlas.land.corners});
  if(atlas.land.years.indexOf(year)>0)city.getSource("change").updateImage({url:`/city/change-${year}.png`,coordinates:atlas.land.corners});
  showLayers();updateDistrictColors();renderReport();
}
function updateDistrictColors(){
  const key=get("district-metric").value,rows=panel.filter(row=>row.year===year&&Number.isFinite(row[key]));
  const sameScope=panel.filter(row=>Number.isFinite(row[key])).map(row=>row[key]);
  const lo=Math.min(...sameScope),hi=Math.max(...sameScope);
  const rules=["match",["get","code"]],heights=["match",["get","code"]];
  for(const row of rows){
    const t=hi>lo?(row[key]-lo)/(hi-lo):0.5;
    heights.push(row.code,1200+t*22000);
    rules.push(row.code,`rgb(${Math.round(39+t*151)},${Math.round(75+t*134)},${Math.round(67+t*74)})`);
  }
  const fill=rules.length>2?[...rules,"#2c423c"]:"#2c423c";
  city.setPaintProperty("district-fill","fill-color",fill);
  city.setPaintProperty("district-volume","fill-extrusion-color",fill);
  city.setPaintProperty("district-volume","fill-extrusion-height",heights.length>2?[...heights,0]:0);
}
function bounds(feature){
  const b=new maplibregl.LngLatBounds();
  const polygons=feature.geometry.type==="Polygon"?[feature.geometry.coordinates]:feature.geometry.coordinates;
  for(const ring of polygons.flat())for(const xy of ring)b.extend(xy);
  return b;
}
function pickDistrict(code,fly=false){
  if(selected)city.setFeatureState({source:"districts",id:selected},{selected:false});
  selected=code;select("city-district",code);
  city.setFeatureState({source:"districts",id:code},{selected:true});
  if(fly){
    const f=districts.features.find(f=>f.properties.code===code);
    if(f)city.fitBounds(bounds(f),{padding:65,maxZoom:12,pitch:mode3D?30:0,duration:750});
  }
  renderReport();
}
function preview(feature,position,title){
  const properties=feature.properties,body=make("div");
  body.append(make("strong",properties.name),make("p",title+" · "+properties.type));
  if(title==="建筑")body.append(make("p",`${format(properties.height)} m · ${properties.basis}`),
    make("p",properties.levels?"源楼层 "+properties.levels:"源数据未记录楼层"));
  body.append(make("p","OpenStreetMap · "+properties.id));
  const button=make("button","分析周边");
  button.onclick=()=>{setCenter(position);cityPane("nearby");};body.append(button);
  new maplibregl.Popup({offset:10,maxWidth:"240px"}).setLngLat(position).setDOMContent(body).addTo(city);
}
function mapClick(event){
  if(picking){setCenter([event.lngLat.lng,event.lngLat.lat]);cityPane("nearby");return;}
  const layers=["poi","buildings","footprints","district-volume","district-fill"].filter(id=>city.getLayoutProperty(id,"visibility")!=="none");
  const hit=city.queryRenderedFeatures(event.point,{layers});
  const chosen=["poi","buildings","footprints","district-volume","district-fill"].map(id=>hit.find(f=>f.layer.id===id)).find(Boolean);
  if(!chosen)return;
  if(chosen.layer.id==="district-fill"||chosen.layer.id==="district-volume"){pickDistrict(chosen.properties.code);cityPane("overview");return;}
  const kind=chosen.layer.id==="poi"?"设施":"建筑";
  const point=kind==="设施"?chosen.geometry.coordinates:[chosen.properties.lon,chosen.properties.lat];
  preview(chosen,point,kind);
}
const rad=Math.PI/180,earth=6371008.8;
function distance(a,b){
  const u=Math.sin((b[1]-a[1])*rad/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin((b[0]-a[0])*rad/2)**2;
  return 2*earth*Math.asin(Math.min(1,Math.sqrt(u)));
}
function circlePoint(center,meter,bearing){
  const [lon,lat]=center.map(v=>v*rad),arc=meter/earth;
  const y=Math.asin(Math.sin(lat)*Math.cos(arc)+Math.cos(lat)*Math.sin(arc)*Math.cos(bearing));
  const x=lon+Math.atan2(Math.sin(bearing)*Math.sin(arc)*Math.cos(lat),Math.cos(arc)-Math.sin(lat)*Math.sin(y));
  return [x/rad,y/rad];
}
function setCenter(point){
  radiusCenter=point;picking=false;get("pick-radius").setAttribute("aria-pressed","false");
  city.getCanvas().style.cursor="";
  if(point){
    const r=Number(get("city-radius").value);
    const ring=Array.from({length:65},(_,i)=>circlePoint(point,r,i*Math.PI/32));ring[64]=ring[0];
    city.getSource("radius").setData({type:"Feature",properties:{},geometry:{type:"Polygon",coordinates:[ring]}});
  }else city.getSource("radius").setData(empty);
  renderReport();
}
function covered(point,r){
  const [w,s,e,n]=atlas.osm.bbox;
  return point[0]>=w&&point[0]<=e&&point[1]>=s&&point[1]<=n&&
    [[w,point[1]],[e,point[1]],[point[0],s],[point[0],n]].every(edge=>distance(point,edge)>=r);
}
function tally(){
  if(!radiusCenter)return [];
  const bins=[500,1000];
  const count=(collection,filter,coordinates,r)=>collection.features.filter(f=>filter(f)&&distance(radiusCenter,coordinates(f))<=r).length;
  const rows=Object.keys(POI_COLORS).map(type=>{
    const [m500,m1000]=bins.map(r=>count(poi,f=>f.properties.type===type,f=>f.geometry.coordinates,r));
    return {type,m500,m1000};
  });
  const [m500,m1000]=bins.map(r=>count(buildings,()=>true,f=>[f.properties.lon,f.properties.lat],r));
  return [...rows,{type:"建筑轮廓代表点",m500,m1000}];
}
function renderBuildingStock(){
  const radius=Number(get("city-radius").value);
  const local=radiusCenter?buildings.features.filter(f=>
    distance(radiusCenter,[f.properties.lon,f.properties.lat])<=radius):buildings.features;
  const counts=Object.keys(USE_COLORS).map(type=>({
    name:type,value:local.filter(f=>f.properties.type===type).length,itemStyle:{color:USE_COLORS[type]}
  }));
  const tagged=local.filter(f=>f.properties.levels>0);
  safeText("building-scope",`${radiusCenter?radius+" 米范围":"虎溪快照范围"} · ${local.length} 个轮廓 · ${tagged.length} 个有源楼层标签`);
  const table=make("table"),head=table.createTHead().insertRow(),body=table.createTBody();
  ["楼层档位","标签数量"].forEach(v=>head.append(make("th",v)));
  const bins=[["1—3 层",tagged.filter(f=>f.properties.levels<4).length],
    ["4—8 层",tagged.filter(f=>f.properties.levels>=4&&f.properties.levels<9).length],
    ["9 层及以上",tagged.filter(f=>f.properties.levels>=9).length],["无楼层标签",local.length-tagged.length]];
  for(const row of bins){const tr=body.insertRow();row.forEach(v=>tr.insertCell().textContent=v);}
  get("floor-table").replaceChildren(table);
  if(window.echarts){
    buildingChart??=echarts.init(get("building-chart"));buildingChart.resize();
    buildingChart.setOption({tooltip:{trigger:"item",renderMode:"richText"},
      legend:{bottom:0,textStyle:{color:"#c7ded1",fontSize:10}},
      series:[{type:"pie",radius:["35%","62%"],center:["50%","43%"],data:counts,label:{show:false}}],
      graphic:local.length?[]:[{type:"text",left:"center",top:"middle",style:{text:"范围内无建筑记录",fill:"#ccd8d0"}}]
    },true);
  }
}
function renderNearby(){
  const button=get("city-tally-export"),table=get("city-nearby-table");
  table.replaceChildren();button.disabled=!radiusCenter;renderBuildingStock();
  if(!radiusCenter){safeText("poi-coverage","请先选择周边中心。");return;}
  const c500=covered(radiusCenter,500),c1000=covered(radiusCenter,1000);
  safeText("poi-coverage",`中心 ${radiusCenter.map(v=>v.toFixed(5)).join(", ")} · 500 米${c500?"位于快照框内":"越出快照框"} · 1 公里${c1000?"位于快照框内":"越出快照框"}。数量只反映已收录要素。`);
  const rows=tally(),grid=make("table"),head=grid.createTHead().insertRow();
  ["分类","500 米","1 公里"].forEach(label=>head.append(make("th",label)));
  const body=grid.createTBody();
  for(const row of rows){const tr=body.insertRow();[row.type,row.m500,row.m1000].forEach(v=>tr.insertCell().textContent=v);}
  table.append(grid);
  button.onclick=()=>saveTable("周边统计.csv",rows.map(r=>({...r,lon:radiusCenter[0],lat:radiusCenter[1],full500:c500,full1000:c1000,source_date:atlas.osm.date})),
    ["type","m500","m1000","lon","lat","full500","full1000","source_date"]);
}
function renderReport(){
  const history=panel.filter(r=>r.code===selected).sort((a,b)=>a.year-b.year);
  const r=history.find(r=>r.year===year);
  if(!r)return;
  const k=get("district-metric").value;
  safeText("city-scope",`${r.group} · ${year} 年 · ${r.code}`);
  safeText("city-name",r.district);
  get("city-kpi").replaceChildren(...["built_km2","expansion_km2","intensive_score","population"].map(key=>{
    const tile=make("div");tile.append(make("small",fields[key][0]),make("strong",format(r[key],key.endsWith("score")?4:2)),
      document.createTextNode(" "+fields[key][1]));return tile;
  }));
  const crops=r.transition_km2?.map((row,index)=>({name:classNames[index],area:index===7?0:row[7]}))
    .filter(item=>item.area>0).sort((a,b)=>b.area-a.area).slice(0,4);
  get("city-sources").replaceChildren(...(crops?.length?crops.map(item=>make("p",item.name+" · "+format(item.area)+areaUnit)):[make("p","本期无可用阶段转移记录。")]));
  get("city-provenance").replaceChildren(make("p",`常住人口 ${format(r.population)} 人 · GDP ${format(r.gdp_10k_cny)} 万元（现价）`),
    make("p",r.provisional?"部分经济资料待复核，评价为探索性口径。":"使用四期探索性评价口径。"),make("p",r.source_pop),make("p",r.source_gdp));
  modelLink.href=`/?view=lab&year=${r.year}&district=${r.code}`;
  if(pane==="overview"&&window.echarts){
    chart??=echarts.init(get("city-chart"));
    chart.resize();
    chart.setOption({grid:{left:48,right:6,top:13,bottom:23},
      tooltip:{trigger:"axis",valueFormatter:v=>format(v)+areaUnit},xAxis:{data:history.map(x=>x.year),axisLabel:{color:"#acc3b8"}},
      yAxis:{type:"value",axisLabel:{color:"#acc3b8"},splitLine:{lineStyle:{color:"#36534b"}}},
      series:[{type:"line",data:history.map(x=>x.built_km2),itemStyle:{color:"#f1d791"},areaStyle:{color:"#487f65",opacity:.4}}]});
  }
  if(pane==="nearby")renderNearby();
  const summary=get("city-summary");
  summary.replaceChildren(make("h3",r.district+" · "+year+" 年"),
    make("p",fields[k][0]+" "+format(r[k],k.endsWith("score")?4:2)+" "+fields[k][1]),
    make("p","不透水面 "+format(r.built_km2)+areaUnit+" · 净扩张 "+format(r.expansion_km2)+areaUnit),
    make("p",r.source_pop),make("p",r.source_gdp));
  if(radiusCenter){
    const rows=tally(),grid=make("table"),head=grid.createTHead().insertRow();
    ["已收录设施","500 米","1 公里"].forEach(label=>head.append(make("th",label)));
    for(const row of rows){const tr=grid.insertRow();[row.type,row.m500,row.m1000].forEach(v=>tr.insertCell().textContent=v);}
    summary.append(make("p","设施统计为直线距离，范围可能超出虎溪快照。"),grid);
  }
  get("city-district-export").onclick=()=>saveTable(r.district+"-历期区年数据.csv",history,
    ["code","district","group","year","built_km2","expansion_km2","population","gdp_10k_cny","secondary_10k_cny","intensive_score","provisional","source_pop","source_gdp"]);
}

function displayViews(){
  const box=get("city-tasks");
  box.replaceChildren(...saved.map((view,index)=>{
    const row=make("div",null,"task-row"),open=make("button",view.name),remove=make("button","移除");
    open.onclick=()=>{
      for(const name of Object.keys(controls))get("layer-"+name).checked=!!view.layers[name];
      mode3D=!!view.is3D;
      get("city-3d").setAttribute("aria-pressed",String(mode3D));safeText("city-3d",mode3D?"三维":"二维");
      select("compare-year",view.compareYear);select("compare-opacity",view.opacity);select("height-scale",view.multiplier??2.5);
      select("city-radius",view.radius);select("poi-type",view.poiType);
      select("building-color",view.buildingColor);select("district-metric",view.metric);
      city.getSource("compare").updateImage({url:`/city/cover-${view.compareYear}.png`,coordinates:atlas.land.corners});
      city.jumpTo(view.camera);pickDistrict(view.district);setYear(panelYears.includes(view.year)?view.year:panelYears.at(-1));setCenter(view.point);
      safeText("city-task-status","已恢复 "+view.name);
    };
    remove.onclick=()=>{
      const updated=saved.filter((_,i)=>i!==index);
      if(!writeLocal(STORED,updated)){safeText("city-task-status","本机存储不可用。");return;}
      saved.splice(index,1);displayViews();
    };
    row.append(open,remove);return row;
  }));
  if(!saved.length)box.append(make("p","尚无已保存视图。"));
}
get("save-city-task").onclick=()=>{
  if(!ready)return;
  const name=get("city-task-name").value.trim();
  if(!name){safeText("city-task-status","请输入视图名称。");return;}
  const view={name,district:selected,year,is3D:mode3D,
    layers:Object.fromEntries(Object.keys(controls).map(k=>[k,checked(k)])),
    camera:{center:city.getCenter().toArray(),zoom:city.getZoom(),pitch:city.getPitch(),bearing:city.getBearing()},
    compareYear:get("compare-year").value,opacity:get("compare-opacity").value,radius:get("city-radius").value,multiplier:get("height-scale").value,
    poiType:get("poi-type").value,buildingColor:get("building-color").value,metric:get("district-metric").value,point:radiusCenter};
  const list=[...saved,view];
  if(!writeLocal(STORED,list)){safeText("city-task-status","本机存储不可用。");return;}
  saved.push(view);displayViews();safeText("city-task-status","已保存 "+name);
};
get("city-map-export").onclick=()=>{
  if(!ready)return;
  const source=city.getCanvas(),out=document.createElement("canvas");
  const scale=Math.max(1,source.width/900),stripe=36*scale;
  out.width=source.width;out.height=source.height+stripe;
  const context=out.getContext("2d");
  context.drawImage(source,0,0);context.fillStyle="#12302a";context.fillRect(0,source.height,out.width,stripe);
  context.fillStyle="#f5f1df";context.font=`${12*scale}px sans-serif`;
  const lines=[`重庆主城都市区 · ${year} 年土地观测`,"© OpenStreetMap contributors · CLCD · Natural Earth"];
  lines.forEach((line,index)=>context.fillText(line,8*scale,source.height+(14+14*index)*scale));
  out.toBlob(blob=>{
    if(!blob){safeText("city-task-status","未能导出当前地图。");return;}
    const url=URL.createObjectURL(blob),link=make("a");
    link.href=url;link.download=`重庆三维专题图-${year}.png`;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  },"image/png");
};
get("city-print").onclick=()=>{if(ready)window.print();};
get("city-fullscreen").onclick=async()=>{
  try{
    if(document.fullscreenElement)await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  }catch{safeText("city-status","当前浏览器未开放全屏模式。");}
};
get("city-play").onclick=()=>{
  if(!ready)return;
  if(interval){clearInterval(interval);interval=null;safeText("city-play","播放");return;}
  interval=setInterval(()=>{const yrs=panelYears;setYear(yrs[(yrs.indexOf(year)+1)%yrs.length]);},1700);
  safeText("city-play","暂停");
};
get("city-district").onchange=()=>{if(ready)pickDistrict(get("city-district").value,true);};
get("compare-year").onchange=()=>{
  if(ready)city.getSource("compare").updateImage({url:`/city/cover-${get("compare-year").value}.png`,coordinates:atlas.land.corners});
};
for(const id of ["compare-opacity","height-scale"])get(id).oninput=()=>{if(ready)showLayers();};
get("district-metric").onchange=()=>{if(ready){updateDistrictColors();renderReport();}};
get("city-radius").onchange=()=>{if(ready)setCenter(radiusCenter);};
for(const name of Object.keys(controls))get("layer-"+name).onchange=()=>{if(ready)showLayers();};
for(const id of ["building-color","poi-type"])get(id).onchange=()=>{if(ready)showLayers();};
get("pick-radius").onclick=()=>{
  if(!ready)return;
  picking=!picking;get("pick-radius").setAttribute("aria-pressed",String(picking));
  city.getCanvas().style.cursor=picking?"crosshair":"";
  if(picking)cityPane("nearby");
};
get("clear-radius").onclick=()=>{if(ready)setCenter(null);};
get("city-3d").onclick=()=>set3D(!mode3D);
get("all-view").onclick=()=>{if(ready)city.fitBounds(ALL,{padding:45,pitch:mode3D?36:0,bearing:0,duration:750});};
get("campus-view").onclick=()=>{
  if(!ready)return;
  get("layer-buildings").checked=true;get("layer-poi").checked=true;get("layer-road").checked=true;
  showLayers();pickDistrict("500106");city.flyTo({center:CAMPUS,zoom:15.4,pitch:mode3D?62:0,bearing:mode3D?-24:0,speed:1.2});
};
function initSearch(){
  const index=[...poi.features.map(f=>({f,title:"设施",xy:f.geometry.coordinates})),
    ...buildings.features.map(f=>({f,title:"建筑",xy:[f.properties.lon,f.properties.lat]}))];
  const picker=get("site-matches");
  get("site-search").oninput=()=>{
    const q=get("site-search").value.trim(),list=q?index.filter(x=>x.f.properties.name.includes(q)||x.f.properties.id===q).slice(0,24):[];
    picker.replaceChildren(new Option(q?(list.length?"选择匹配结果":"无匹配设施或建筑"):"输入名称以检索",""));
    for(const [i,item] of list.entries())picker.add(new Option(item.f.properties.name+" · "+item.f.properties.type,i));
    picker.onchange=()=>{
      if(picker.value===""||!ready)return;
      const item=list[Number(picker.value)];
      city.flyTo({center:item.xy,zoom:16,pitch:mode3D?55:0,duration:1000});
      preview(item.f,item.xy,item.title);
    };
  };
}

if("serviceWorker" in navigator){
  navigator.serviceWorker.register("/sw.js").then(()=>navigator.serviceWorker.ready)
    .then(registration=>registration.active?.postMessage("cache-city")).catch(()=>{});
}
Promise.all([studyData(),readCity("/districts.geojson"),readCity("/city/manifest.json"),
  readCity("/api/v1/research/map/").catch(async()=>{
    const [buildings,poi,roads]=await Promise.all(["buildings","poi","roads"].map(name=>readCity("/city/"+name+".geojson")));
    return {buildings,poi,roads};
  }),readCity("/rivers.geojson")])
.then(([rows,boundary,metadata,site,rivers])=>{
  panel=rows;districts=boundary;atlas={...metadata,osm:site.osm??metadata.osm};
  buildings=site.buildings;poi=site.poi;const roads=site.roads;
  panelYears=[...new Set(rows.map(r=>r.year))].sort((a,b)=>a-b);
  if(!window.maplibregl)throw Error("地图组件未加载。");
  city=new maplibregl.Map({
    container:"city-map",style:{version:8,sources:{},layers:[{id:"background",type:"background",paint:{"background-color":"#1a3531"}}]},
    canvasContextAttributes:{preserveDrawingBuffer:true},
    bounds:ALL,fitBoundsOptions:{padding:70},maxPitch:75,minZoom:5,maxZoom:19.5,
    attributionControl:false,
  });
  city.addControl(new maplibregl.AttributionControl({compact:true,customAttribution:
    '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · CLCD · Natural Earth'}),"bottom-right");
  city.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"top-right");
  city.addControl(new maplibregl.ScaleControl({unit:"metric"}),"bottom-right");
  city.on("error",e=>{
    if(!ready)safeText("city-status","三维视图加载受限。可返回研究台查看二维地图。");
    else if(e.sourceId)safeText("city-status","一个地图图层加载失败，请尝试重新打开页面。");
  });
  city.once("load",()=>{
    loadLayers(rivers,roads);initSearch();
    for(const y of panelYears){
      const b=make("button",y);b.onclick=()=>setYear(y);
      get("city-years").append(b);
    }
    atlas.land.years.forEach(y=>get("compare-year").add(new Option(y,y)));
    for(const type of Object.keys(POI_COLORS))get("poi-type").add(new Option(type,type));
    for(const f of districts.features){
      const {code,district}=f.properties;
      get("city-district").add(new Option(district,code));
      const label=make("button",district,"scene-marker");
      label.onclick=e=>{e.stopPropagation();pickDistrict(code,true);cityPane("overview");};
      // Bounding-box center serves as a label anchor. District selection uses the polygon itself.
      const marker=new maplibregl.Marker({element:label}).setLngLat(bounds(f).getCenter()).addTo(city);markers.push(marker);
    }
    ready=true;
    pickDistrict(districts.features.some(f=>f.properties.code===selected)?selected:districts.features[0].properties.code);
    setYear(Math.max(...panel.map(r=>r.year)));set3D(true);displayViews();
    city.on("click",mapClick);
    city.on("zoomend",()=>{legend();updateMarkers();});
    new ResizeObserver(()=>{city.resize();if(pane==="overview")chart?.resize();if(pane==="nearby")buildingChart?.resize();}).observe(get("city-body"));
    safeText("city-status",`${districts.features.length} 区 · ${panelYears.length} 期观测 · 虎溪快照 ${atlas.osm.buildings} 个建筑轮廓、${atlas.osm.poi} 个设施点 · ${atlas.osm.date}`);
  });
}).catch(error=>{safeText("city-status",error.message+" 可返回研究台使用二维地图。");});
