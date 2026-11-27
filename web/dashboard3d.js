"use strict";
(function(){
const $=id=>document.getElementById(id), years=[2010,2015,2020,2022];
const state={rows:[],recent:[],features:null,viewer:null,source:null,rivers:null,selected:"",year:2022,group:"",metric:"built_km2",playing:false,timer:null,charts:{}};
const metrics={built_km2:["不透水面面积","km²"],expansion_km2:["阶段净扩张面积","km²"],annual_expansion_intensity_pct:["年均扩张强度","%"],intensive_score:["集约利用得分","分"],population_density:["人口承载密度","人/km²"],gdp_density:["单位用地 GDP","万元/km²"],secondary_density:["单位用地二产增加值","万元/km²"]};
const numeric=["year","admin_km2","valid_area_km2","nodata_area_km2","built_km2","population","gdp_10k_cny","secondary_10k_cny","added_km2","lost_km2","expansion_km2","annual_growth_pct","annual_expansion_intensity_pct","population_density","gdp_density","secondary_density","intensive_score","rank","equal_weight_score","equal_weight_rank","cropland_km2","forest_km2","water_km2","grassland_km2","shrub_km2","barren_km2","wetland_km2","snow_km2"];
function num(v){if(v===null||v===undefined||v==="")return null;const n=Number(v);return Number.isFinite(n)?n:null}
function normalize(row){const out={...row};numeric.forEach(k=>out[k]=num(out[k]));return out}
function fmt(v,d=2){return Number.isFinite(v)?v.toLocaleString("zh-CN",{maximumFractionDigits:d,minimumFractionDigits:d}):"—"}
function rowsFor(year){let base=state.rows.filter(r=>r.year===year);if(state.group)base=base.filter(r=>r.group===state.group);
 if(state.metric==="intensive_score"&&(year===2020||year===2022)){const primary=new Map(state.recent.filter(r=>r.year===year).map(r=>[String(r.code),r]));base=base.map(r=>{const p=primary.get(String(r.code));return p?{...r,intensive_score:p.intensive_score,rank:p.rank,equal_weight_score:p.equal_weight_score,equal_weight_rank:p.equal_weight_rank}:r;});}
 return base}
function values(rows,key){return rows.map(r=>r[key]).filter(Number.isFinite)}
function sum(rows,key){const a=values(rows,key);return a.length?a.reduce((x,y)=>x+y,0):null}
function currentRows(){return rowsFor(state.year)}
function mean(rows,key){const a=values(rows,key);return a.length?a.reduce((x,y)=>x+y,0)/a.length:null}
function setStatus(text){$("engine-status").textContent=text}
function initCharts(){
 if(!window.echarts)return;
 state.charts.trend=echarts.init($("trend-chart"));state.charts.cover=echarts.init($("cover-chart"));state.charts.rank=echarts.init($("ranking-chart"));
 window.addEventListener("resize",()=>Object.values(state.charts).forEach(c=>c.resize()));
}
function renderTrend(){
 if(!state.charts.trend)return;const totals=years.map(y=>sum(state.rows.filter(r=>r.year===y),"built_km2"));
 state.charts.trend.setOption({grid:{left:42,right:12,top:18,bottom:24},tooltip:{trigger:"axis"},xAxis:{type:"category",data:years,axisLabel:{color:"#91adbd"},axisLine:{lineStyle:{color:"#31536a"}}},yAxis:{type:"value",axisLabel:{color:"#7899aa"},splitLine:{lineStyle:{color:"#244157"}}},series:[{type:"line",smooth:true,data:totals,showSymbol:true,symbolSize:7,lineStyle:{width:3,color:"#5de0e7"},itemStyle:{color:"#f1c875"},areaStyle:{color:"rgba(50,176,190,.18)"}}]});
}
function renderCover(rows){
 if(!state.charts.cover)return;const items=[["耕地","cropland_km2"],["林地","forest_km2"],["水域","water_km2"],["不透水面","built_km2"],["草地","grassland_km2"],["灌木","shrub_km2"],["湿地","wetland_km2"],["裸地","barren_km2"]];
 state.charts.cover.setOption({tooltip:{trigger:"item",formatter:p=>p.name+"："+fmt(p.value)+" km²"},legend:{bottom:0,textStyle:{color:"#9bb5c3",fontSize:9},itemWidth:8,itemHeight:8},series:[{type:"pie",radius:["38%","66%"],center:["50%","43%"],label:{show:false},data:items.map(x=>({name:x[0],value:sum(rows,x[1])||0})),color:["#bca36b","#3f8d69","#3f91bb","#e2a36b","#a2b66f","#b2a17d","#63aab0","#8c9496"]}]});
}
function renderRanking(rows){
 if(!state.charts.rank)return;const data=rows.filter(r=>Number.isFinite(r[state.metric])).sort((a,b)=>b[state.metric]-a[state.metric]).slice(0,8).reverse();
 state.charts.rank.setOption({grid:{left:72,right:28,top:8,bottom:16},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br>"+fmt(p[0].value)+" "+metrics[state.metric][1]},xAxis:{type:"value",axisLabel:{color:"#7899aa",fontSize:8},splitLine:{lineStyle:{color:"#244157"}}},yAxis:{type:"category",data:data.map(r=>r.district),axisLabel:{color:"#b8d0dc",fontSize:9},axisLine:{lineStyle:{color:"#31536a"}}},series:[{type:"bar",data:data.map(r=>({value:r[state.metric],itemStyle:{color:r.code===state.selected?"#f0c879":"#32a9bc"}})),barWidth:10,label:{show:true,position:"right",color:"#b8d0dc",fontSize:8,formatter:p=>fmt(p.value,1)}}]});
}
function renderKpis(rows){
 $("kpi-built").textContent=fmt(sum(rows,"built_km2"));
 $("kpi-growth").textContent=state.year===2010?"基期":fmt(sum(rows,"expansion_km2"));
 const score=mean(rows,"intensive_score");$("kpi-score").textContent=fmt(score,3);
 const hasPrimary=state.recent.some(r=>r.year===state.year);$("kpi-score-note").textContent=(state.year>=2020&&hasPrimary?"主要比较 · A 级样本":"四期探索 · 含早期待核验数据");
 $("kpi-records").textContent=String(rows.length);
}
function renderDetail(){
 const row=currentRows().find(r=>String(r.code)===state.selected);
 $("district-empty").hidden=!!row;$("district-detail").hidden=!row;
 if(!row)return;
 const metricsToShow=[["不透水面面积",row.built_km2,"km²"],["阶段净扩张",row.expansion_km2,"km²"],["年均扩张强度",row.annual_expansion_intensity_pct,"%"],["人口密度",row.population_density,"人/km²"],["单位用地 GDP",row.gdp_density,"万元/km²"],["单位用地二产",row.secondary_density,"万元/km²"],["集约利用得分",row.intensive_score,"分"],["评价排名",row.rank,"名"]];
 $("district-detail").innerHTML='<div class="district-name"></div><div class="district-meta"></div><div class="detail-grid"></div><p class="detail-note"></p>';
 $("district-detail").querySelector(".district-name").textContent=row.district;
 $("district-detail").querySelector(".district-meta").textContent=row.group+" · "+row.code+" · "+state.year;
 const grid=$("district-detail").querySelector(".detail-grid");
 metricsToShow.forEach(([label,v,unit])=>{const cell=document.createElement("div");cell.className="detail-cell";const a=document.createElement("span"),b=document.createElement("strong");a.textContent=label;b.textContent=fmt(v,v===row.intensive_score?3:2)+(Number.isFinite(v)?" "+unit:"");cell.append(a,b);grid.append(cell)});
 const hasPrimary=state.recent.some(r=>r.year===state.year);const note=state.year<2020?"本期经济指标包含 B/C 级待复核记录，四期得分仅作探索性分析。":((state.year===2020||state.year===2022)&&hasPrimary?"集约利用得分采用 2020、2022 年 42 条 A 级样本的主要比较口径。":((state.year===2020||state.year===2022)?"主要比较样本当前不可用，本页回退显示四期探索性评价值。":"该字段按当前发布数据口径展示。"));
 $("district-detail").querySelector(".detail-note").textContent=note;
}
function applyMap(){
 if(!state.source||!window.Cesium)return;
 const rows=currentRows(),byCode=new Map(rows.map(r=>[String(r.code),r])),vals=values(rows,state.metric);
 const lo=vals.length?Math.min(...vals):0,hi=vals.length?Math.max(...vals):1;
 state.source.entities.values.forEach(entity=>{
  const code=String(entity.properties.code.getValue()),row=byCode.get(code),poly=entity.polygon;
  const baselineOnly=state.year===2010&&(state.metric==="expansion_km2"||state.metric==="annual_expansion_intensity_pct");const hasValue=!!row&&Number.isFinite(row[state.metric]);const show=!!row&&(hasValue||baselineOnly);entity.show=show;if(!show||!poly)return;
  const v=hasValue?row[state.metric]:0,t=hi===lo?.5:(v-lo)/(hi-lo);
  const low=Cesium.Color.fromCssColorString("#176a87"),high=Cesium.Color.fromCssColorString("#f1c66f");
  const color=Cesium.Color.lerp(low,high,t,new Cesium.Color());
  poly.height=0;poly.extrudedHeight=2200+t*23000;poly.material=color.withAlpha(code===state.selected ? .96 : .78);
  poly.outline=true;poly.outlineColor=code===state.selected?Cesium.Color.WHITE:Cesium.Color.fromCssColorString("#78d7e7");
 });
 $("legend-range").textContent=vals.length?fmt(lo,2)+" — "+fmt(hi,2)+" "+metrics[state.metric][1]:(state.year===2010&&(state.metric==="expansion_km2"||state.metric==="annual_expansion_intensity_pct")?"基期无阶段扩张值":"当前年份无可用值");
 $("map-title").textContent=state.year+" · "+metrics[state.metric][0];
}
function render(){
 const rows=currentRows();renderKpis(rows);renderCover(rows);renderRanking(rows);renderDetail();applyMap();
 document.querySelectorAll("[data-year]").forEach(b=>b.classList.toggle("selected",Number(b.dataset.year)===state.year));
 $("year").value=String(state.year);$("group").value=state.group;$("metric").value=state.metric;
 $("timeline-caption").textContent=state.year===2010?"基期观测 · 不计算阶段扩张":state.year===2015?"2010—2015 年阶段变化":state.year===2020?"2015—2020 年阶段变化":"2020—2022 年阶段变化";
}
async function initMap(){
 if(!window.Cesium){throw new Error("CesiumJS 引擎未能加载。请检查网络连接后刷新页面；二维研究总览仍可正常使用。")}
 const C=window.Cesium;
 state.viewer=new C.Viewer("cesiumContainer",{animation:false,timeline:false,geocoder:false,homeButton:false,sceneModePicker:false,baseLayerPicker:false,baseLayer:new C.ImageryLayer(new C.OpenStreetMapImageryProvider({url:"https://tile.openstreetmap.org/",credit:"© OpenStreetMap contributors"})),terrainProvider:new C.EllipsoidTerrainProvider(),navigationHelpButton:false,fullscreenButton:false,infoBox:false,selectionIndicator:false,scene3DOnly:true,shouldAnimate:false,shadows:false,requestRenderMode:false});
 const baseLayer=state.viewer.imageryLayers.get(0);if(baseLayer){baseLayer.brightness=.48;baseLayer.saturation=.28;baseLayer.contrast=1.12;}
 state.viewer.scene.backgroundColor=C.Color.fromCssColorString("#061321");state.viewer.scene.globe.baseColor=C.Color.fromCssColorString("#10283a");state.viewer.scene.globe.showGroundAtmosphere=true;state.viewer.scene.globe.enableLighting=false;state.viewer.scene.globe.depthTestAgainstTerrain=false;
 state.viewer.scene.screenSpaceCameraController.minimumZoomDistance=15000;state.viewer.scene.screenSpaceCameraController.maximumZoomDistance=2500000;
 state.source=await C.GeoJsonDataSource.load(state.features,{stroke:C.Color.fromCssColorString("#72d9eb"),strokeWidth:2,fill:C.Color.fromCssColorString("#268da0").withAlpha(.65),clampToGround:false});
 state.viewer.dataSources.add(state.source);
 state.source.entities.values.forEach(entity=>{if(entity.polygon){entity.polygon.height=0;entity.polygon.extrudedHeight=3000;entity.polygon.outline=true;entity.polygon.outlineColor=C.Color.fromCssColorString("#82dbea");}});
 if($("river-toggle").checked){try{state.rivers=await C.GeoJsonDataSource.load("/rivers.geojson",{stroke:C.Color.fromCssColorString("#45c8e6"),strokeWidth:3,clampToGround:false});state.viewer.dataSources.add(state.rivers);}catch(e){console.warn("水系图层不可用",e)}}
 state.viewer.camera.flyTo({destination:C.Cartesian3.fromDegrees(106.7,29.55,430000),orientation:{heading:C.Math.toRadians(0),pitch:C.Math.toRadians(-48),roll:0},duration:2.5});
 state.viewer.screenSpaceEventHandler.setInputAction(function(movement){
  const picked=state.viewer.scene.pick(movement.position);const entity=picked&&(picked.id||picked.primitive&&picked.primitive.id);
  if(entity&&entity.properties&&entity.properties.code){state.selected=String(entity.properties.code.getValue());render();}
 },C.ScreenSpaceEventType.LEFT_CLICK);
 setStatus("三维场景已就绪 · 点击区县查看数据");
}
function stopPlay(){state.playing=false;if(state.timer)clearInterval(state.timer);state.timer=null;$("play-years").textContent="▶ 播放四期"}
function play(){if(state.playing){stopPlay();return}state.playing=true;$("play-years").textContent="Ⅱ 暂停";let i=years.indexOf(state.year);state.timer=setInterval(()=>{i=(i+1)%years.length;state.year=years[i];render()},2600)}
function bind(){
 $("year").addEventListener("change",e=>{state.year=Number(e.target.value);render()});
 $("group").addEventListener("change",e=>{state.group=e.target.value;render()});
 $("metric").addEventListener("change",e=>{state.metric=e.target.value;render()});
 $("play-years").addEventListener("click",play);
 $("reset-camera").addEventListener("click",()=>{if(state.viewer)state.viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(106.7,29.55,430000),orientation:{heading:0,pitch:Cesium.Math.toRadians(-48),roll:0},duration:1.5})});
 $("river-toggle").addEventListener("change",async e=>{if(!state.viewer)return;if(e.target.checked&&!state.rivers){try{state.rivers=await Cesium.GeoJsonDataSource.load("/rivers.geojson",{stroke:Cesium.Color.fromCssColorString("#45c8e6"),strokeWidth:3,clampToGround:false});state.viewer.dataSources.add(state.rivers)}catch(err){setStatus("水系图层加载失败")}}else if(state.rivers)state.rivers.show=e.target.checked});
 $("fullscreen").addEventListener("click",()=>{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen()});
 document.querySelectorAll("[data-year]").forEach(b=>b.addEventListener("click",()=>{state.year=Number(b.dataset.year);stopPlay();render()}));
}
async function start(){
 initCharts();bind();
 try{
  const results=await Promise.all([fetch("/dashboard.json").then(r=>{if(!r.ok)throw new Error("研究面板读取失败");return r.json()}),fetch("/districts.geojson").then(r=>{if(!r.ok)throw new Error("区县边界读取失败");return r.json()}),fetch("/api/v1/recent-observations/").then(r=>r.ok?r.json():{results:[]}).catch(()=>({results:[]}))]);
  state.rows=results[0].map(normalize);state.features=results[1];state.recent=(results[2].results||[]).map(normalize);
  $("kpi-districts").textContent=String(state.features.features.length);$("kpi-records").textContent=String(state.rows.length);
  renderTrend();await initMap();render();
 }catch(error){
  setStatus("三维场景暂不可用");
  const box=$("map-error");box.hidden=false;box.replaceChildren();
  const message=document.createElement("p");message.textContent=error.message+" 请检查数据服务或网络。";
  const link=document.createElement("a");link.href="/";link.textContent="返回二维研究总览";
  box.append(message,link);console.error(error)
 }
}
document.addEventListener("DOMContentLoaded",start);
})();
