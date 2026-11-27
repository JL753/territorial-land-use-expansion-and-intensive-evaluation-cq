"use strict";
let data=[],years=[],plans=readLocal("cq-desk-plans",[]),sortKey="year",descending=true;
const columns=["year","district","group","built_km2","impervious_share_pct","expansion_km2","built_person_m2",
  "nominal_gdp_person_yuan","secondary_share_pct","coverage_gap_pct","intensive_score","rank","provisional"];
const labels={year:"年份",district:"区县",group:"区组",provisional:"经济资料"};
const title=k=>labels[k]??fields[k]?.[0]??k;
const modes={entropy:"熵权",equal:"等权",custom:"自定义"};
let lastRank=[];
const val=(row,k)=>k==="provisional"?(row[k]?"待复核":"见来源"):format(row[k],k==="intensive_score"?4:2);
function table(headers,rows){
  const t=make("table"),head=t.createTHead().insertRow(),body=t.createTBody();
  for(const s of headers)head.append(make("th",s));
  for(const row of rows){const tr=body.insertRow();for(const c of row)tr.insertCell().textContent=c;}
  return t;
}
function showPage(view){
  const names={data:"区年数据",work:"评价方案",sensitivity:"敏感性扫描",pairing:"区县对照"};
  for(const key of Object.keys(names))get(key).hidden=view!==key;
  for(const b of document.querySelectorAll("nav button"))b.setAttribute("aria-current",b.dataset.view===view?"page":"false");
  get("desktop-title").textContent=names[view];
  if(view==="work"&&data.length)rank();
  if(view==="sensitivity"&&data.length&&!get("s-year").options.length)scanYears();
  if(view==="pairing"&&data.length)pair();
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>showPage(b.dataset.view));
function selectedData(){
  const y=get("d-year").value,g=get("d-group").value,q=get("d-search").value.trim(),only=get("d-quality").checked;
  return data.filter(r=>(!y||r.year===Number(y))&&(!g||r.group===g)&&(!only||!r.provisional)
    &&(r.district.includes(q)||r.code.includes(q)));
}
function renderData(){
  const rows=selectedData().sort((a,b)=>{
    const x=a[sortKey],y=b[sortKey],direction=descending?-1:1;
    if(x==null||y==null)return x==null?(y==null?0:1):-1;
    return direction*(typeof x==="string"?x.localeCompare(y,"zh-CN"):Number(x)-Number(y));
  });
  get("d-count").textContent=rows.length+" 条区年记录 · 点列名排序";
  get("d-columns").replaceChildren();
  const head=get("d-columns").insertRow();
  for(const k of columns){
    const th=make("th");
    const button=make("button",title(k)+(sortKey===k?(descending?" ↓":" ↑"):""));
    if(k===sortKey)th.setAttribute("aria-sort",descending?"descending":"ascending");
    button.onclick=()=>{descending=sortKey===k?!descending:false;sortKey=k;renderData();};th.append(button);head.append(th);
  }
  get("d-rows").replaceChildren(...rows.map(r=>{
    const tr=make("tr");for(const k of columns)tr.insertCell().textContent=val(r,k);return tr;
  }));
  get("d-export").disabled=!rows.length;
  get("d-export").onclick=()=>saveTable("区年筛选.csv",rows,["code",...columns,"source_pop","source_gdp"]);
}
for(const id of ["d-year","d-group","d-search","d-quality"])get(id).oninput=renderData;
function currentPlan(){
  return {basis:get("d-basis").value,mode:get("d-mode").value,
    weights:indicators.map((_,i)=>get("w"+i).valueAsNumber)};
}
function calculate(plan){
  const sample=data.filter(r=>plan.basis==="full"||[2020,2022].includes(r.year));
  return evaluateRows(sample,plan.mode,plan.weights);
}
function renderPlans(){
  for(const id of ["d-a","d-b"]){
    const picker=get(id),value=picker.value;
    picker.replaceChildren(new Option("选择方案",""));
    for(const plan of plans)addOption(picker,plan.id,plan.name+" · "+modes[plan.mode]);
    if(plans.some(p=>p.id===value))picker.value=value;
  }
  delta();
}
function delta(){
  const a=plans.find(p=>p.id===get("d-a").value),b=plans.find(p=>p.id===get("d-b").value);
  get("d-delete").disabled=!b;
  get("d-compare-export").disabled=true;
  get("d-change-summary").textContent="";
  if(!a||!b){get("d-delta").textContent="保存方案后选择 A 和 B。";return;}
  const y=Number(get("d-rank-year").value);
  const left=calculate(a).rows.filter(r=>r.year===y);
  const right=new Map(calculate(b).rows.filter(r=>r.year===y).map(r=>[r.code,r.scenarioRank]));
  if(!left.length||!right.size){get("d-delta").textContent="所选方案缺少该年份，切换到共同年份。";return;}
  const rows=left.sort((x,z)=>x.scenarioRank-z.scenarioRank).filter(r=>right.has(r.code)).map(r=>({
    code:r.code,district:r.district,year:y,scheme_a:a.name,scheme_b:b.name,
    rank_a:r.scenarioRank,rank_b:right.get(r.code),improvement:r.scenarioRank-right.get(r.code)
  }));
  const improved=rows.filter(r=>r.improvement>0).length;
  const declined=rows.filter(r=>r.improvement<0).length;
  get("d-change-summary").textContent=`${y} 年 · 提升 ${improved} 区 · 下降 ${declined} 区 · 持平 ${rows.length-improved-declined} 区`;
  const grid=table(["区县","方案 A","方案 B","排名变动"],rows.map(r=>[r.district,r.rank_a,r.rank_b,
    r.improvement>0?"↑ "+r.improvement:r.improvement<0?"↓ "+Math.abs(r.improvement):"—"]));
  [...grid.tBodies[0].rows].forEach((tr,i)=>{
    if(rows[i].improvement)tr.cells[3].className=rows[i].improvement>0?"delta-up":"delta-down";
  });
  get("d-delta").replaceChildren(grid);
  get("d-compare-export").disabled=!rows.length;
  get("d-compare-export").onclick=()=>saveTable("评价方案差异-"+y+".csv",rows,Object.keys(rows[0]));

}
function rank(){
  const plan=currentPlan(),picker=get("d-rank-year"),prior=picker.value;
  const available=years.filter(y=>plan.basis==="full"||[2020,2022].includes(y));
  picker.replaceChildren(...available.map(y=>new Option(y,y)));
  picker.value=available.includes(Number(prior))?prior:available.at(-1);
  get("d-weights").hidden=plan.mode!=="custom";
  lastRank=[];
  try{
    if(plan.mode==="custom"&&plan.weights.some(x=>!Number.isFinite(x)||x<0||x>100))throw Error("权重须在 0—100 内。");
    const computed=calculate(plan);
    lastRank=computed.rows.filter(r=>r.year===Number(picker.value))
      .sort((a,b)=>a.scenarioRank-b.scenarioRank).map(r=>({...r,basis:plan.basis,mode:plan.mode,weights:computed.weights.join("/")}));
    get("d-message").textContent="实际权重 "+computed.weights.map(w=>format(w*100)+"%").join(" / ");
    get("d-scores").replaceChildren(table(["区县","得分","名次","经济资料"],lastRank.map(r=>[r.district,format(r.score,4),r.scenarioRank,val(r,"provisional")])));
  }catch(e){get("d-message").textContent=e.message;get("d-scores").replaceChildren();}
  get("d-save").disabled=get("d-export-rank").disabled=!lastRank.length;
  delta();
}
get("d-save").onclick=()=>{
  const name=get("d-name").value.trim();
  if(!name){get("d-message").textContent="请输入方案名称。";return;}
  const plan={...currentPlan(),name,id:String(Date.now())};
  const next=[...plans,plan];
  if(!writeLocal("cq-desk-plans",next)){get("d-message").textContent="本机存储不可用。";return;}
  plans=next;renderPlans();if(!get("d-a").value)get("d-a").value=plan.id;else get("d-b").value=plan.id;
  delta();get("d-message").textContent="已保存 "+name;
};
get("d-delete").onclick=()=>{
  const id=get("d-b").value;
  const plan=plans.find(p=>p.id===id);
  if(!plan||!window.confirm("移除本机方案「"+plan.name+"」？"))return;
  const next=plans.filter(p=>p.id!==id);
  if(!writeLocal("cq-desk-plans",next)){get("d-message").textContent="本机存储不可用。";return;}
  plans=next;renderPlans();get("d-message").textContent="已移除 "+plan.name;
};
get("d-export-rank").onclick=()=>saveTable("年度评价.csv",lastRank,["code","district","year","score","scenarioRank","basis","mode","weights","provisional"]);
for(const id of ["d-basis","d-mode","d-rank-year"])get(id).onchange=rank;
for(const id of ["d-a","d-b"])get(id).onchange=delta;
indicators.forEach((k,i)=>{
  const label=make("label",title(k)),input=make("input");
  input.id="w"+i;input.type="number";input.min=0;input.max=100;input.value=[30,45,25][i];input.oninput=rank;
  label.append(input);get("d-weights").append(label);
});
function pair(){
  const a=get("district-a").value,b=get("district-b").value,key=get("pair-metric").value;
  const left=data.filter(r=>r.code===a),right=data.filter(r=>r.code===b);
  if(!left.length||!right.length)return;
  const rows=years.map(year=>{
    const x=left.find(r=>r.year===year)?.[key],y=right.find(r=>r.year===year)?.[key];
    return {year,district_a:left[0].district,district_b:right[0].district,metric:key,value_a:x,value_b:y,
      difference:Number.isFinite(x)&&Number.isFinite(y)?x-y:null};
  });
  get("pair-title").textContent=fields[key].join(" ");
  get("pair-table").replaceChildren(table(["年份",left[0].district,right[0].district,"差额 A−B"],rows.map(r=>
    [r.year,format(r.value_a,4),format(r.value_b,4),format(r.difference,4)])));
  get("d-export-pair").onclick=()=>saveTable("区县历期对照.csv",rows,Object.keys(rows[0]));
}
for(const id of ["district-a","district-b","pair-metric"])get(id).onchange=pair;
function scanYears(){
  const picker=get("s-year"),prior=Number(picker.value),range=years.filter(y=>get("s-basis").value==="full"||[2020,2022].includes(y));
  picker.replaceChildren(...range.map(y=>new Option(y,y)));picker.value=range.includes(prior)?prior:range.at(-1);
  clearScan();
}
function clearScan(){
  get("s-result").textContent="请选择年份并运行。";get("s-table").replaceChildren();get("s-export").disabled=true;
}
get("s-basis").onchange=scanYears;
get("s-year").onchange=clearScan;
get("s-run").onclick=()=>{
  const year=Number(get("s-year").value),basis=get("s-basis").value;
  try{
    const scan=weightSensitivity(data.filter(r=>basis==="full"||[2020,2022].includes(r.year)),year);
    const rows=scan.rows.sort((a,b)=>b.span-a.span||a.scenarioRank-b.scenarioRank);
    if(!rows.length)throw Error("该年份没有可扫描的观测。");
    get("s-result").textContent=`${year} 年 · ${scan.scenarios} 套权重 · ${rows.length} 区 · 最大名次跨度 ${rows[0].span} 位`;
    const result=table(["区县","熵权名次","最好","最差","跨度","进入前五"],rows.map(r=>
      [r.district,r.scenarioRank,r.best,r.worst,r.span,format(r.topFivePct)+"%"]));
    [...result.tBodies[0].rows].forEach((tr,i)=>{
      const bar=make("span",null,"s-bar");bar.style.width=(rows[i].span/Math.max(rows.length-1,1)*64)+"px";
      tr.cells[4].prepend(bar);
    });
    get("s-table").replaceChildren(result);get("s-export").disabled=false;
    get("s-export").onclick=()=>saveTable("权重扫描-"+year+".csv",rows.map(r=>({...r,basis,scenarios:scan.scenarios})),
      ["code","district","year","basis","scenarios","scenarioRank","best","worst","span","topFivePct","provisional"]);
  }catch(e){clearScan();get("s-result").textContent=e.message;}
};
studyData().then(rows=>{
  data=rows;years=[...new Set(rows.map(r=>r.year))].sort();
  years.forEach(y=>addOption(get("d-year"),y,y));
  const districts=new Map(rows.map(r=>[r.code,r.district]));
  for(const [code,name] of districts){addOption(get("district-a"),code,name);addOption(get("district-b"),code,name);}
  get("district-b").selectedIndex=1;
  for(const k of columns.filter(k=>fields[k]))addOption(get("pair-metric"),k,fields[k].join(" "));
  get("desktop-status").textContent=rows.length+" 条观测 · "+districts.size+" 个区县";
  renderData();renderPlans();rank();pair();
}).catch(e=>{get("desktop-status").textContent=e.message;});
