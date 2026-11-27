"use strict";
const $=id=>document.getElementById(id);
const map=$("map"), ctx=map.getContext("2d");
let records=[], shapes=[], page="overview", selected="", zoom=1, focused=null, datasetReady=false;
let playback=null;
let labRows=[], labYear=null, questionIssued=0, currentQuestion="", currentAnswer="";
const weights=[30,45,25];
const pages={overview:"空间总览",lab:"评价实验室",relations:"指标关系",library:"数据查询",assistant:"研究助手",report:"研究简报"};
const topics={
  "扩张与形态":["built_km2","expansion_km2","annual_expansion_intensity_pct","annual_growth_pct","added_km2","lost_km2","adjacent_km2","nonadjacent_km2","adjacency_unknown_km2","centroid_displacement_km","centroid_bearing_deg","expansion_cropland_share_pct"],
  "土地覆盖":[...landTypes,"valid_area_km2","nodata_area_km2","impervious_share_pct","coverage_gap_pct"],
  "人口与经济":["population","gdp_10k_cny","primary_10k_yuan","secondary_10k_cny","tertiary_10k_yuan","built_person_m2","nominal_gdp_person_yuan","secondary_share_pct",...indicators],
  "评价与质量":["intensive_score","rank","equal_weight_score","equal_weight_rank","quality_population","quality_gdp","quality_secondary","source_pop","source_gdp"]
};
const colors=["#bbab75","#4f8462","#de9667","#69aaba","#94aa67","#a8c779","#728eb0","#ada9a0","#d2e8ef"];
function node(tag,text,cls){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
function option(select,value,text){select.add(new Option(text,value));}
function scoped(){return records.filter(r=>!$("group").value||r.group===$("group").value);}
function yearRows(){return scoped().filter(r=>r.year===Number($("year").value));}
function sum(rows,k){const a=rows.map(r=>r[k]).filter(Number.isFinite);return a.length?a.reduce((x,y)=>x+y,0):null;}
function digits(k){return k.includes("score")||k==="annual_expansion_intensity_pct"?4:2;}
function value(r,k){return format(r[k],digits(k));}
function tab(key){
  page=key;
  if(key!=="overview"){stopPlayback();document.body.classList.remove("screen");$("platform-screen").textContent="大屏模式";}
  for(const view of document.querySelectorAll(".view"))view.hidden=view.id!==key;
  for(const btn of document.querySelectorAll("nav button"))btn.setAttribute("aria-current",btn.dataset.page===key?"page":"false");
  $("title").textContent=pages[key];
  if(datasetReady)render();
}
for(const btn of document.querySelectorAll("nav button"))btn.onclick=()=>tab(btn.dataset.page);
function buildPaths(features){
  const polys=features.map(f=>f.geometry.type==="Polygon"?[f.geometry.coordinates]:f.geometry.coordinates);
  const points=polys.flat(3);
  const [w,s,e,n]=points.reduce(([w,s,e,n],[x,y])=>[Math.min(w,x),Math.min(s,y),Math.max(e,x),Math.max(n,y)],[Infinity,Infinity,-Infinity,-Infinity]);
  const cos=Math.cos((n+s)*Math.PI/360);
  const scale=Math.min((map.width-100)/((e-w)*cos),(map.height-52)/(n-s));
  const project=([x,y])=>[map.width/2+(x-(w+e)/2)*cos*scale,map.height/2-(y-(s+n)/2)*scale];
  shapes=features.map((f,i)=>{
    const path=new Path2D();let bestArea=0,anchor;
    for(const polygon of polys[i]){
      for(const [j,ring] of polygon.entries()){
        const pts=ring.map(project);let area=0,cx=0,cy=0;
        pts.forEach(([x,y],k)=>{
          if(k===0)path.moveTo(x,y);else path.lineTo(x,y);
          const [xx,yy]=pts[(k+1)%pts.length],cross=x*yy-xx*y;
          area+=cross;cx+=(x+xx)*cross;cy+=(y+yy)*cross;
        });
        path.closePath();
        if(j===0&&Math.abs(area)>bestArea){bestArea=Math.abs(area);anchor=[cx/(3*area),cy/(3*area)];}
      }
    }
    return {code:String(f.properties.code),name:f.properties.district,path,anchor,size:bestArea};
  });
}
function transformMap(){
  const [x,y]=focused||[map.width/2,map.height/2];
  ctx.translate(map.width/2,map.height/2);ctx.scale(zoom,zoom);ctx.translate(-x,-y);
}
function paint(rows){
  const k=$("metric").value, available=scoped().map(r=>r[k]).filter(Number.isFinite);
  const lo=Math.min(...available),hi=Math.max(...available), by=new Map(rows.map(r=>[r.code,r]));
  ctx.clearRect(0,0,map.width,map.height);ctx.save();transformMap();
  for(const f of shapes){
    const v=by.get(f.code)?.[k], t=hi===lo?.5:(v-lo)/(hi-lo);
    ctx.fillStyle=Number.isFinite(v)?`rgb(${Math.round(36+t*165)},${Math.round(98+t*136)},${Math.round(91+t*25)})`:"#2b4945";
    ctx.fill(f.path,"evenodd");ctx.strokeStyle="#173e36";ctx.lineWidth=1.3/zoom;ctx.stroke(f.path);
  }
  const choice=shapes.find(f=>f.code===selected);
  if(choice){ctx.lineWidth=2.5/zoom;ctx.strokeStyle="#f6d880";ctx.stroke(choice.path);}
  ctx.textAlign="center";ctx.textBaseline="middle";ctx.font=`bold ${14/Math.sqrt(zoom)}px sans-serif`;
  for(const f of shapes){
    if(!by.has(f.code)||!f.anchor||(f.code!==selected&&f.size*zoom<2200))continue;
    ctx.strokeStyle="#274b3f";ctx.lineWidth=2.8/zoom;ctx.strokeText(f.name,...f.anchor);ctx.fillStyle="#fff";ctx.fillText(f.name,...f.anchor);
  }
  ctx.restore();
  $("legend").textContent=rows.some(r=>Number.isFinite(r[k]))?`${format(lo,digits(k))} — ${format(hi,digits(k))} ${fields[k][1]} · 跨期统一色阶`:"该年份没有此指标区间";
}
function hitTest(e){
  const rect=map.getBoundingClientRect(),[cx,cy]=focused||[map.width/2,map.height/2];
  const x=((e.clientX-rect.left)*map.width/rect.width-map.width/2)/zoom+cx;
  const y=((e.clientY-rect.top)*map.height/rect.height-map.height/2)/zoom+cy;
  return shapes.find(f=>ctx.isPointInPath(f.path,x,y,"evenodd"));
}
map.onpointermove=e=>{
  const hit=hitTest(e),k=$("metric").value,row=yearRows().find(r=>r.code===hit?.code);
  $("map-focus").textContent=row?`${row.district}　${fields[k][0]} ${value(row,k)} ${fields[k][1]}`:"";
};
map.onpointerleave=()=>{$("map-focus").textContent="";};
map.onclick=e=>{
  const hit=hitTest(e);
  if(hit&&yearRows().some(r=>r.code===hit.code)){selected=hit.code;render();}
};
$("zoom-in").onclick=()=>{zoom=Math.min(4,zoom*1.4);focused=shapes.find(f=>f.code===selected)?.anchor;render();};
$("zoom-out").onclick=()=>{zoom=Math.max(1,zoom/1.4);if(zoom===1)focused=null;render();};
$("reset-map").onclick=()=>{zoom=1;focused=null;render();};
function summary(rows){
  const previous=Math.max(...scoped().map(r=>r.year).filter(y=>y<Number($("year").value)));
  const cards=[["不透水面面积",sum(rows,"built_km2"),"km²"],["阶段净扩张",sum(rows,"expansion_km2"),Number.isFinite(previous)?`km² · ${previous}—${$("year").value}`:"基准期"],
    ["常住人口",sum(rows,"population")/10000,"万人"],["地区生产总值",sum(rows,"gdp_10k_cny")/10000,"亿元 · 当年现价"]];
  $("kpis").replaceChildren(...cards.map(([title,val,unit],index)=>{
    const box=node("div",null,"kpi");box.append(node("span",title),node("strong",format(val)),node("small",unit));
    const canvas=node("canvas",null,"spark");canvas.width=120;canvas.height=36;
    canvas.setAttribute("aria-hidden","true");
    const dataKey=["built_km2","expansion_km2","population","gdp_10k_cny"][index];
    const dates=[...new Set(scoped().map(r=>r.year))].sort();
    const series=dates.map(y=>sum(scoped().filter(r=>r.year===y),dataKey));
    const nums=series.filter(Number.isFinite),min=Math.min(...nums),max=Math.max(...nums);
    const pen=canvas.getContext("2d");
    pen.lineWidth=2.5;pen.strokeStyle=index?"#609c79":"#c7ed75";pen.fillStyle=pen.strokeStyle;
    pen.beginPath();let started=false;
    series.forEach((v,i)=>{if(v==null)return;
      const x=4+(dates[i]-dates[0])/(dates.at(-1)-dates[0]||1)*112,y=30-((v-min)/(max-min||1))*23;
      if(started)pen.lineTo(x,y);else pen.moveTo(x,y);started=true;
    });pen.stroke();
    const i=dates.indexOf(Number($("year").value));
    if(series[i]!=null){pen.beginPath();pen.arc(4+(dates[i]-dates[0])/(dates.at(-1)-dates[0]||1)*112,30-(series[i]-min)/(max-min||1)*23,3.5,0,2*Math.PI);pen.fill();}
    box.append(canvas);return box;
  }));
  const k=$("metric").value;
  const best=rows.filter(r=>Number.isFinite(r[k])).sort((a,b)=>b[k]-a[k]).slice(0,5);
  $("ranking").replaceChildren(...best.map(r=>{
    const btn=node("button",null,"rankrow"),bar=node("i");
    bar.style.width=Math.max(2,Math.abs(r[k])/(Math.max(...best.map(x=>Math.abs(x[k])))||1)*100)+"%";
    btn.append(node("span",r.district),bar,node("b",value(r,k)));btn.onclick=()=>{selected=r.code;render();};return btn;
  }));
  if(!best.length)$("ranking").textContent="基准期没有阶段变化值。";
  const cover=$("cover"),stack=node("div",null,"stack");cover.replaceChildren(stack);
  const hasCover=rows.every(r=>Number.isFinite(r.valid_area_km2));
  if(!hasCover)cover.textContent="当前面板未提供分类面积。";
  else{
    const total=sum(rows,"valid_area_km2");
    const keyList=node("div",null,"coverkeys"),ring=node("div",null,"coverring"),stops=[];let offset=0;
    stack.className="covergraph";stack.append(ring,keyList);
    landTypes.forEach((key,i)=>{
      const a=sum(rows,key)||0;if(!a)return;
      const pct=a/total*100,tag=node("span",null,"key"),swatch=node("i");
      swatch.style.background=colors[i];stops.push(colors[i]+" "+offset+"% "+(offset+pct)+"%");offset+=pct;
      tag.append(swatch,document.createTextNode(fields[key][0]+" "+format(pct)+"%"));keyList.append(tag);
    });
    ring.style.background="conic-gradient("+stops.join(",")+")";ring.append(node("span",$("year").value));
  }
  const dates=[...new Set(scoped().map(r=>r.year))].sort();
  const totals=dates.map(y=>sum(scoped().filter(r=>r.year===y),"built_km2"));
  $("trend").replaceChildren(...dates.map((y,i)=>{
    const line=node("div",null,"trendline"),bar=node("i",null,"bar");bar.style.width=totals[i]/Math.max(...totals)*100+"%";
    line.append(node("span",y),bar,node("b",format(totals[i])));return line;
  }));
  const selector=$("district");selector.replaceChildren();rows.forEach(r=>option(selector,r.code,r.district));selector.value=selected;
  const r=rows.find(item=>item.code===selected);
  $("detail").replaceChildren();
  if(r){
    $("detail").append(node("p",`${r.district} · ${r.code} · ${r.group}　｜　${r.year} 年集约排名 ${r.rank}`));
    const table=node("table");
    for(const h of scoped().filter(item=>item.code===selected).sort((a,b)=>a.year-b.year)){
      const tr=table.insertRow();for(const v of [h.year,format(h.built_km2)+" km²","得分 "+format(h.intensive_score,4)])tr.insertCell().textContent=v;
    }
    $("detail").append(table);
  }
  paint(rows);
  drawMatrix(rows);
}
function drawMatrix(rows){
  const districtOnly=$("matrix-scope").value==="district";
  const input=districtOnly?rows.filter(r=>r.code===selected):rows;
  const matrix=aggregateMatrix(input);
  $("matrix").replaceChildren();$("flow-detail").textContent="";$("export-flow").disabled=!matrix;
  if(!matrix){$("flow-note").textContent="该观测期没有地类转移矩阵。";return;}
  const period=input[0].interval_start+"—"+input[0].year;
  const scope=districtOnly?input[0].district:($("group").value||"全域");
  const changed=matrix.flatMap((row,i)=>row.map((v,j)=>i===j?0:v));
  const max=Math.max(...changed);
  $("flow-note").textContent=`${scope} · ${period} · 行为期初、列为期末。跨类转换合计 ${format(changed.reduce((a,b)=>a+b,0))} km²，点选数值查看。`;
  const head=node("tr");head.append(node("th","期初／期末"),...classNames.map(k=>node("th",k)));$("matrix").append(head);
  matrix.forEach((row,i)=>{
    const tr=node("tr");tr.append(node("th",classNames[i]));
    row.forEach((v,j)=>{
      const td=tr.insertCell(),btn=node("button",format(v));
      btn.title=classNames[i]+" → "+classNames[j];
      td.style.background=i===j?"#e5e8df":`rgba(88,161,118,${max?Math.sqrt(v/max)*.72:0})`;
      btn.onclick=()=>{$("flow-detail").textContent=`${period}　${scope}　${classNames[i]} → ${classNames[j]}　${v.toFixed(4)} km²`;};td.append(btn);
    });$("matrix").append(tr);
  });
  $("export-flow").onclick=()=>csv("地类转移-"+period+".csv",matrix.flatMap((row,i)=>row.map((v,j)=>({scope,period,from:classNames[i],to:classNames[j],area_km2:v}))),["scope","period","from","to","area_km2"]);
}
$("matrix-scope").onchange=render;
function csv(name,rows,columns){
  const encode=v=>'"'+String(v??"").replaceAll('"','""')+'"';
  const lines=[columns,...rows.map(r=>columns.map(k=>r[k]))].map(row=>row.map(encode).join(","));
  const content="\ufeff"+lines.join("\r\n");
  if(window.CQLandAndroid){window.CQLandAndroid.saveCsv(name,content);return;}
  const url=URL.createObjectURL(new Blob([content],{type:"text/csv;charset=utf-8"}));
  const link=node("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function library(){
  const q=$("search").value.trim(),cols=topics[$("topic").value];
  const rows=yearRows().filter(r=>r.district.includes(q)||r.code.includes(q));
  $("row-count").textContent=`${rows.length} 个区县 · ${$("year").value} 年`;
  const head=node("tr");head.append(node("th","区县"),...cols.map(k=>node("th",fields[k].join(" ").trim())));
  $("columns").replaceChildren(head);$("rows").replaceChildren(...rows.map(r=>{
    const tr=node("tr");tr.append(node("td",r.district),...cols.map(k=>node("td",value(r,k))));return tr;
  }));
  $("download").disabled=!rows.length;$("download").onclick=()=>csv("区县指标-"+$("year").value+".csv",rows,["code","district","group","year","data_kind","evaluation_basis","provisional",...cols]);
}
const scenarioKeys={built_km2:"不透水面面积",population:"常住人口",gdp_10k_cny:"GDP",secondary_10k_cny:"第二产业增加值"};
function scenarioSample(sample,year){
  const target=$("scenario-code").value;
  if(!target)return sample;
  return sample.map(row=>{
    if(row.code!==target||row.year!==year)return row;
    const r={...row};
    for(const k of Object.keys(scenarioKeys)){
      const input=$("delta-"+k);
      if(!input.value||!input.validity.valid)throw Error("请填写 −90 至 200 之间的变动百分比。");
      r[k]*=1+Number(input.value)/100;
    }
    if(r.built_km2>r.admin_km2||r.secondary_10k_cny>r.gdp_10k_cny)throw Error("情景超出可行范围：请核对建设用地面积和产业分项。");
    r.population_density=r.population/r.built_km2;r.gdp_density=r.gdp_10k_cny/r.built_km2;r.secondary_density=r.secondary_10k_cny/r.built_km2;
    return r;
  });
}
function lab(){
  const recent=$("basis").value==="recent",mode=$("scheme").value;
  const sample=records.filter(r=>!recent||[2020,2022].includes(r.year));
  const year=Number($("year").value);
  const refs=evaluateRows(sample);
  let calc;
  try{calc=evaluateRows(scenarioSample(sample,year),mode,weights);}
  catch(error){$("lab-note").textContent=error.message;$("scores").replaceChildren();$("comparison").replaceChildren();$("export-lab").disabled=true;return;}
  $("export-lab").disabled=false;
  const baseByCode=new Map(refs.rows.filter(r=>r.year===year).map(r=>[r.code,r.scenarioRank]));
  labRows=calc.rows.filter(r=>r.year===year&&(!$("group").value||r.group===$("group").value))
    .map(r=>({...r,baseline_rank:baseByCode.get(r.code)})).sort((a,b)=>a.scenarioRank-b.scenarioRank);
  labYear=year;
  indicators.forEach((k,i)=>{
    $("weight-"+i).disabled=mode!=="custom";
    $("weight-value-"+i).textContent=format(calc.weights[i]*100)+"%";
  });
  $("lab-note").textContent=`${sample.length} 条观测 · ${recent?"近期共同参照":"四期探索性参照"} · 现价产出 · ${$("scenario-code").value?"情景结果，改动只作用于当前年份":"原始观测"}。`;
  $("scores").replaceChildren(...labRows.map(r=>{
    const tr=node("tr");for(const v of [r.district,format(r.score,4),r.scenarioRank,r.baseline_rank,r.provisional?"待复核":r.quality_gdp||r.data_kind])tr.append(node("td",v));return tr;
  }));
  const controls=[$("compare-a"),$("compare-b")];
  controls.forEach((s,i)=>{
    const before=s.value;s.replaceChildren();labRows.forEach(r=>option(s,r.code,r.district));
    s.value=labRows.some(r=>r.code===before)?before:labRows[Math.min(i,labRows.length-1)]?.code||"";
  });
  const [a,b]=controls.map(s=>labRows.find(r=>r.code===s.value));
  if(!a||!b)return;
  const table=node("table"),head=node("tr");head.append(node("th","比较项"),node("th",a.district),node("th",b.district));table.append(head);
  for(const k of [...indicators,"score"]){
    const tr=table.insertRow();for(const v of [k==="score"?"试算得分":fields[k].join(" "),format(a[k],k==="score"?4:2),format(b[k],k==="score"?4:2)])tr.insertCell().textContent=v;
  }
  $("comparison").replaceChildren(table);
  $("export-lab").onclick=()=>csv("集约评价-"+labYear+".csv",labRows.map(r=>({...r,basis:$("basis").value,scheme:mode,weights:calc.weights.join("/"),scenario_code:$("scenario-code").value,changes_pct:Object.keys(scenarioKeys).map(k=>k+"="+$("delta-"+k).value).join("/")})),["code","district","year","score","scenarioRank","baseline_rank","basis","scheme","weights","scenario_code","changes_pct","data_kind","provisional"]);
}
function answer(q){
  currentQuestion=q;currentAnswer=researchAnswer(q,records,Number($("year").value),$("group").value,$("metric").value);
  if(/方案|试算|实验室/.test(q)){
    const year=Number($("year").value),recent=$("basis").value==="recent";
    const sample=records.filter(r=>!recent||[2020,2022].includes(r.year));
    if(!sample.some(r=>r.year===year))currentAnswer="当前年份超出近期试算范围，可在评价实验室切换为四期。";
    else try{
      const model=evaluateRows(scenarioSample(sample,year),$("scheme").value,weights);
      const sorted=model.rows.filter(r=>r.year===year&&(!$("group").value||r.group===$("group").value)).sort((a,b)=>a.scenarioRank-b.scenarioRank);
      currentAnswer=`${year} 年 · ${$("group").value||"全域"} · ${sample.length} 条样本
试算权重（人口／GDP／二产）为 ${model.weights.map(w=>format(w*100)+"%").join("、")}。
${sorted.slice(0,3).map(r=>r.district+" "+format(r.score,4)+"（年度第 "+r.scenarioRank+"）").join("、")}。
对应当前实验室设置，GDP 和二产采用现价。`;
    }catch(error){currentAnswer=error.message;}
  }
  $("answer").textContent=currentAnswer;$("generated").textContent="";questionIssued++;
}
function stopPlayback(){
  clearInterval(playback);playback=null;
  $("play-years").textContent="播放四期";$("play-years").setAttribute("aria-pressed","false");
}
$("play-years").onclick=()=>{
  if(playback){stopPlayback();return;}
  const values=[...$("year").options].map(o=>o.value).reverse();
  if(!values.length)return;
  let i=0;
  $("play-years").textContent="暂停播放";$("play-years").setAttribute("aria-pressed","true");
  $("year").value=values[i];render();
  playback=setInterval(()=>{i=(i+1)%values.length;$("year").value=values[i];render();},1600);
};
$("platform-screen").onclick=()=>{
  if(page!=="overview")tab("overview");
  const enabled=document.body.classList.toggle("screen");
  $("platform-screen").textContent=enabled?"退出大屏":"大屏模式";
};
const command=$("command");
function launchCommand(){
  if(!command.open)command.showModal();
  $("command-search").value="";fillCommand();$("command-search").focus();
}
function fillCommand(){
  const q=$("command-search").value.trim().toLowerCase();
  const actions=Object.entries(pages).map(([key,name])=>[name,"页面",()=>tab(key)]);
  const districtActions=Array.from(new Map(records.map(r=>[r.code,r.district]))).map(([code,name])=>[name,code,()=>{
    $("group").value="";selected=code;tab("overview");$("district").focus();
  }]);
  const metricActions=[...$("metric").options].map(o=>[o.text,"地图指标",()=>{$("metric").value=o.value;tab("overview");}]);
  const matches=[...actions,...districtActions,...metricActions].filter(([name,tag])=>(name+tag).toLowerCase().includes(q)).slice(0,9);
  $("command-results").replaceChildren(...matches.map(([name,tag,go])=>{
    const button=node("button");button.append(node("span",name),node("small",tag));
    button.onclick=()=>{command.close();go();};return button;
  }));
  if(!matches.length)$("command-results").textContent="未找到结果";
}
$("open-command").onclick=launchCommand;
$("command-search").oninput=fillCommand;
$("command-search").onkeydown=e=>{if(e.key==="Enter")$("command-results").querySelector("button")?.click();};
document.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();launchCommand();}});
function report(){
  const rows=yearRows(),year=$("year").value,group=$("group").value||"全域";
  const scope=group+" · "+year+" 年 · "+rows.length+" 区";
  const key="cq-web-report-"+group+"-"+year;
  $("report-scope").textContent=scope;
  const valid=sum(rows,"valid_area_km2"),built=sum(rows,"built_km2"),gap=sum(rows,"nodata_area_km2");
  const net=sum(rows,"expansion_km2"),matrix=aggregateMatrix(rows);
  const lead=rows.filter(r=>Number.isFinite(r.expansion_km2)).sort((a,b)=>b.expansion_km2-a.expansion_km2)[0];
  const result=[
    "不透水面 "+format(built)+" km²，占有效覆盖 "+format(valid>0?built/valid*100:null)+"%。",
    net==null?"本期为基准期，缺少阶段扩张指标。":"阶段净扩张 "+format(net)+" km²，"+lead.district+"净扩张量最高（"+format(lead.expansion_km2)+" km²）。",
    matrix?"耕地转入不透水面 "+format(matrix[0][7])+" km²。":"本期没有可用的地类转移矩阵。",
    "常住人口 "+format(sum(rows,"population"))+" 人，地区生产总值 "+format(sum(rows,"gdp_10k_cny"))+" 万元（现价）。",
    gap==null?"该面板缺少覆盖缺测数据。":"缺测面积 "+format(gap)+" km²，约占覆盖和缺测总面积的 "+format(valid+gap>0?gap/(valid+gap)*100:null)+"%。"
  ];
  $("report-findings").replaceChildren(...result.map(line=>node("p",line)));
  $("report-sources").textContent=[
    ...(rows.some(r=>r.data_kind==="demo")?["模拟观测，仅用于验证。"]:["数据口径为 CLCD 30 m 和固定区归属栅格。"]),
    ...new Set(rows.flatMap(r=>[r.source_pop,r.source_gdp]).filter(Boolean)),
    ...(rows.some(r=>r.provisional)?["同期部分经济数据待复核。"]:[])
  ].join("\n");
  const memo=$("report-note");
  try{memo.value=localStorage.getItem(key)||"";}catch{memo.value="";}
  $("report-note-print").textContent=memo.value;
  $("report-note-status").textContent="";
  memo.oninput=()=>{
    $("report-note-print").textContent=memo.value;
    try{localStorage.setItem(key,memo.value);$("report-note-status").textContent="已保存到本机。";}
    catch{$("report-note-status").textContent="本机存储不可用。";}
  };
}
$("print-report").onclick=()=>window.print();
const relationKeys=["annual_expansion_intensity_pct","intensive_score","built_km2","impervious_share_pct","population_density",
  "gdp_density","secondary_density","built_person_m2","nominal_gdp_person_yuan","secondary_share_pct","expansion_cropland_share_pct"];
const relationChart=$("relation-chart"), relationPen=relationChart.getContext("2d");
let chartPoints=[];
function relationView(){
  const xKey=$("relation-x").value,yKey=$("relation-y").value;
  const list=yearRows().filter(r=>Number.isFinite(r[xKey])&&Number.isFinite(r[yKey]));
  const width=relationChart.width,height=relationChart.height;
  const x0=105,y0=height-85,x1=width-42,y1=37;
  const pen=relationPen;
  pen.clearRect(0,0,width,height);
  chartPoints=[];
  if(!list.length){
    pen.font="21px sans-serif";pen.fillStyle="#4d695d";pen.textAlign="center";pen.fillText("本期缺少两项指标的共同观测",width/2,height/2);
  }else{
    const xs=list.map(r=>r[xKey]),ys=list.map(r=>r[yKey]);
    const range=values=>{
      const lo=Math.min(...values),hi=Math.max(...values),padding=(hi-lo||Math.abs(hi)||1)*.08;
      return [lo-padding,hi+padding];
    };
    const [xl,xh]=range(xs),[yl,yh]=range(ys);
    const px=v=>x0+(v-xl)/(xh-xl)*(x1-x0),py=v=>y0-(v-yl)/(yh-yl)*(y0-y1);
    pen.font="17px sans-serif";pen.lineWidth=1;pen.strokeStyle="#d9ddd0";pen.fillStyle="#466457";
    for(let i=0;i<=4;i++){
      const x=x0+(x1-x0)*i/4,y=y0-(y0-y1)*i/4;
      pen.beginPath();pen.moveTo(x,y1);pen.lineTo(x,y0);pen.moveTo(x0,y);pen.lineTo(x1,y);pen.stroke();
      pen.textAlign="center";pen.fillText(format(xl+(xh-xl)*i/4,2),x,y0+27);
      pen.textAlign="right";pen.fillText(format(yl+(yh-yl)*i/4,2),x0-13,y+5);
    }
    pen.setLineDash([6,4]);pen.strokeStyle="#8b927d";
    pen.beginPath();pen.moveTo(px(median(xs)),y0);pen.lineTo(px(median(xs)),y1);pen.moveTo(x0,py(median(ys)));pen.lineTo(x1,py(median(ys)));pen.stroke();pen.setLineDash([]);
    pen.textAlign="center";pen.fillText(fields[xKey].join(" "), (x0+x1)/2,height-18);pen.textAlign="left";pen.fillText(fields[yKey].join(" "),x0,24);
    chartPoints=list.map(r=>({r,x:px(r[xKey]),y:py(r[yKey])}));
    for(const {r,x,y} of chartPoints){
      const radius=r.code===selected?9:6;
      pen.beginPath();
      if(r.group==="中心城区")pen.arc(x,y,radius,0,Math.PI*2);
      else{pen.moveTo(x,y-radius);pen.lineTo(x+radius,y);pen.lineTo(x,y+radius);pen.lineTo(x-radius,y);pen.closePath();}
      pen.fillStyle=r.group==="中心城区"?"#246354":"#a56437";pen.fill();
      if(r.code===selected){pen.strokeStyle="#9d3a2f";pen.lineWidth=3;pen.stroke();}
    }
  }
  const picker=$("relation-district");picker.replaceChildren(new Option("选择区县",""));
  list.forEach(r=>option(picker,r.code,r.district));picker.value=list.some(r=>r.code===selected)?selected:"";
  const r=list.find(r=>r.code===selected);
  $("relation-detail").textContent=r?`${r.district} · ${format(r[xKey],4)} ${fields[xKey][1]} / ${format(r[yKey],4)} ${fields[yKey][1]}`:"请选择散点或区县。";
  $("relation-map").disabled=!r;$("relation-export").disabled=!list.length;
  const rho=spearman(list.map(r=>r[xKey]),list.map(r=>r[yKey]));
  $("relation-stats").replaceChildren(...[["共同观测",list.length+" 区"],["Spearman ρ",format(rho,3)],
    ["横轴中位数",format(median(list.map(r=>r[xKey])),4)],["纵轴中位数",format(median(list.map(r=>r[yKey])),4)]]
    .flatMap(([name,val])=>[node("dt",name),node("dd",val)]));
  $("relation-legend").textContent="● 中心城区　◆ 主城新区 · 朱砂描边为所选区县";
  $("relation-export").onclick=()=>csv("指标关系-"+$("year").value+".csv",list.map(r=>({...r,rho})),
    [...new Set(["code","district","group","year",xKey,yKey,"rho","provisional"])]);
}
relationChart.onclick=event=>{
  const box=relationChart.getBoundingClientRect(),x=(event.clientX-box.left)/box.width*relationChart.width,
    y=(event.clientY-box.top)/box.height*relationChart.height;
  const hit=chartPoints.map(p=>({p,d:Math.hypot(p.x-x,p.y-y)})).sort((a,b)=>a.d-b.d)[0];
  if(hit&&hit.d<22){selected=hit.p.r.code;relationView();}
};
$("relation-district").onchange=()=>{selected=$("relation-district").value;relationView();};
$("relation-map").onclick=()=>tab("overview");
for(const id of ["relation-x","relation-y"])$(id).onchange=relationView;
for(const k of relationKeys)for(const id of ["relation-x","relation-y"])option($(id),k,fields[k][0]);
$("relation-x").value="annual_expansion_intensity_pct";$("relation-y").value="intensive_score";
function render(){
  if(!datasetReady)return;
  $("map-focus").textContent="";
  const restrict=page==="lab"&&$("basis").value==="recent";
  for(const o of $("year").options)o.disabled=restrict&&Number(o.value)<2020;
  if($("year").selectedOptions[0]?.disabled)$("year").value="2020";
  if(!yearRows().some(r=>r.code===selected))selected=yearRows()[0]?.code||"";
  $("matrix-section").hidden=page!=="overview";
  if(page==="overview")summary(yearRows());
  if(page==="lab")lab();
  if(page==="library")library();
  if(page==="relations")relationView();
  if(page==="report")report();
  if(page==="assistant"&&currentQuestion)answer(currentQuestion);
}
for(const id of ["year","group","metric","basis","scheme","topic"])$(id).onchange=()=>{zoom=1;focused=null;render();};
$("search").oninput=render;$("district").onchange=()=>{selected=$("district").value;render();};
$("ask").onsubmit=e=>{e.preventDefault();const q=$("question").value.trim();if(q&&datasetReady)answer(q);};
$("fullscreen").onclick=async()=>{try{if(window.CQLandAndroid){window.CQLandAndroid.fullscreen();return;}if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{$("status").textContent="当前设备使用系统全屏模式。";}};
$("enhance").onclick=async()=>{
  if(!currentAnswer)return;
  const id=questionIssued;$("generated").textContent="正在调用本机模型…";
  try{
    const resp=await fetch("/api/interpret",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:currentQuestion,evidence:currentAnswer})});
    const data=await resp.json();if(!resp.ok)throw Error(data.error||"请求失败");
    if(id===questionIssued)$("generated").textContent="模型解读 · "+data.answer;
  }catch(e){if(id===questionIssued)$("generated").textContent="本机模型暂不可用："+e.message;}
};
for(const prompt of ["总结当前数据","解读评价实验室方案","新增不透水面来自哪些地类？","当前区域净扩张多少？","哪些区县集约得分最高？","不透水面历年变化趋势","数据来源和质量"]){
  const b=node("button",prompt);b.onclick=()=>{$("question").value=prompt;answer(prompt);};$("suggestions").append(b);
}
for(const [key,label] of Object.entries(scenarioKeys)){
  const l=node("label",label+"变动 %"),input=node("input");input.type="number";input.id="delta-"+key;
  input.min="-90";input.max="200";input.step="0.1";input.value="0";input.oninput=lab;l.append(input);$("inputs-scenario").append(l);
}
$("scenario-code").onchange=lab;
$("clear-scenario").onclick=()=>{$("scenario-code").value="";for(const k of Object.keys(scenarioKeys))$("delta-"+k).value=0;lab();};
for(const [i,k] of indicators.entries()){
  const label=node("label",fields[k][0]),input=node("input"),v=node("span");input.type="range";input.min=0;input.max=100;input.value=weights[i];input.id="weight-"+i;v.id="weight-value-"+i;
  input.oninput=()=>{weights[i]=Number(input.value);lab();};label.append(input,v);$("weights").append(label);
}
for(const [id,title] of [["compare-a","对照区 A"],["compare-b","对照区 B"]]){
  const l=node("label",title),s=node("select");s.id=id;s.onchange=lab;l.append(s);$("compare-controls").append(l);
}
for(const k of Object.keys(topics))option($("topic"),k,k);
async function read(url){const r=await fetch(url);if(!r.ok)throw Error(String(r.status));return r.json();}
Promise.all([read("/dashboard.json"),read("/districts.geojson")]).then(([data,boundaries])=>{
  records=enrichObservations(data);buildPaths(boundaries.features);
  [...new Set(records.map(r=>r.year))].sort((a,b)=>b-a).forEach(y=>option($("year"),y,y));
  for(const [key,[name,unit]] of Object.entries(fields))if(records.some(r=>Number.isFinite(r[key])))option($("metric"),key,name+(unit?" · "+unit:""));
  $("status").textContent=records.some(r=>r.data_kind==="demo")?"模拟数据与虚构几何，仅用于系统验证":
    `${new Set(records.map(r=>r.code)).size} 个区县 · ${records.length} 条区年观测 · CLCD 30 m ｜ 经济指标为现价，四期评价含早期待复核记录`;
  for(const [code,name] of new Map(records.map(r=>[r.code,r.district])))option($("scenario-code"),code,name);
  datasetReady=true;render();
  read("/api/config").then(config=>{$("enhance").hidden=!config.model;}).catch(()=>{});
  if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js").catch(()=>{});
}).catch(e=>{$("status").textContent="数据加载失败："+e.message;});
