"use strict";
const fields = {
  built_km2:["不透水面","km²"], expansion_km2:["净扩张面积","km²"], annual_expansion_intensity_pct:["年均扩张强度","%"],
  intensive_score:["集约利用得分",""], population:["常住人口","人"], gdp_10k_cny:["地区生产总值","万元"],
  secondary_10k_cny:["第二产业增加值","万元"], population_density:["人口承载密度","人/km²"],
  gdp_density:["单位用地 GDP","万元/km²"], secondary_density:["单位用地二产","万元/km²"],
  added_km2:["新增面积","km²"], lost_km2:["减少面积","km²"], adjacent_km2:["邻接新增","km²"],
  nonadjacent_km2:["非邻接新增","km²"], adjacency_unknown_km2:["邻接未知","km²"],
  annual_growth_pct:["年均增长率","%"], centroid_displacement_km:["重心位移","km"], centroid_bearing_deg:["位移方向","°"],
  valid_area_km2:["有效覆盖面积","km²"], nodata_area_km2:["缺测面积","km²"], admin_km2:["行政区面积","km²"],
  cropland_km2:["耕地","km²"], forest_km2:["林地","km²"], shrub_km2:["灌木","km²"], grassland_km2:["草地","km²"],
  water_km2:["水体","km²"], snow_km2:["冰雪","km²"], barren_km2:["裸地","km²"], wetland_km2:["湿地","km²"],
  primary_10k_yuan:["第一产业增加值","万元"], tertiary_10k_yuan:["第三产业增加值","万元"], rank:["集约排名","名"],
  equal_weight_rank:["等权排名","名"], equal_weight_score:["等权得分",""], source_pop:["人口来源",""],source_gdp:["经济来源",""],
  quality_population:["人口等级",""],quality_gdp:["GDP 等级",""],quality_secondary:["二产等级",""]
};
const indicators = ["population_density","gdp_density","secondary_density"];
const landTypes = ["cropland_km2","forest_km2","built_km2","water_km2","shrub_km2","grassland_km2","wetland_km2","barren_km2","snow_km2"];
const classNames=["耕地","林地","灌木","草地","水体","冰雪","裸地","不透水面","湿地"];
function aggregateMatrix(rows){
  const available=rows.filter(r=>Array.isArray(r.transition_km2));
  if(!available.length)return null;
  return classNames.map((_,i)=>classNames.map((_,j)=>available.reduce((a,r)=>a+r.transition_km2[i][j],0)));
}
const number = new Intl.NumberFormat("zh-CN",{maximumFractionDigits:2});
function format(value, digits=2) {
  if (value == null || (typeof value === "number" && !Number.isFinite(value))) return "—";
  if (typeof value !== "number") return String(value);
  return digits === 2 ? number.format(value) : value.toFixed(digits);
}
function evaluateRows(rows, mode="entropy", custom=[1,1,1]) {
  const columns = indicators.map(key => rows.map(row => row[key]));
  if (rows.length < 2 || columns.some(col => !col.every(Number.isFinite))) throw Error("样本缺少评价指标。");
  const normalized = columns.map(col => {
    const min=Math.min(...col), span=Math.max(...col)-min;
    return col.map(x=>span ? (x-min)/span : 0);
  });
  const weights=normalized.map((col,k)=>{
    const sum=col.reduce((a,b)=>a+b,0);
    if (!sum) return 0;
    if (mode==="custom") return custom[k];
    if (mode==="equal") return 1;
    const entropy = -col.reduce((acc,z)=>z ? acc + (z/sum)*Math.log(z/sum) : acc,0)/Math.log(rows.length);
    return Math.max(0,1-entropy);
  });
  const total=weights.reduce((a,b)=>a+b,0);
  if (!total) throw Error("请为至少一个有变化的指标设置正权重。");
  const share=weights.map(w=>w/total);
  const scored=rows.map((r,i)=>{
    const neg=Math.hypot(...normalized.map((col,k)=>col[i]*share[k]));
    const pos=Math.hypot(...normalized.map((col,k)=>(1-col[i])*share[k]));
    return {...r,score:neg/(neg+pos)};
  });
  for (const year of new Set(rows.map(r=>r.year))) {
    const sorted=scored.filter(r=>r.year===year).sort((a,b)=>b.score-a.score);
    sorted.forEach((r,i)=>{r.scenarioRank=i && r.score===sorted[i-1].score ? sorted[i-1].scenarioRank : i+1;});
  }
  return {rows:scored,weights:share};
}
function queryMetric(q, fallback) {
  const ordered=[...Object.keys(fields)].sort((a,b)=>fields[b][0].length-fields[a][0].length);
  const exact=ordered.find(k=>q.includes(fields[k][0]));
  if (exact) return exact;
  for(const [pattern,key] of [[/地均|单位.*GDP/i,"gdp_density"],[/GDP|经济总量/i,"gdp_10k_cny"],[/二产/,"secondary_10k_cny"],[/人口/,"population"],[/得分|集约|评分/,"intensive_score"],[/扩张|净增/,"expansion_km2"],[/建设用地|面积/,"built_km2"]]) if(pattern.test(q)) return key;
  return fallback;
}
// Retrieve the closest intent examples using character unigram/bigram TF-IDF cosine similarity.
const intents={
  rank:["排名最高的区县","哪些地区领先","前三名","排行榜"],
  trend:["历年变化趋势","四个年份分别多少","逐年走势","时间变化"],
  source:["数据来源和口径","哪些数据待复核","依据是什么","数据质量"],
  summary:["总结当前数据","评价所选区域","总体情况","概括研究数据"]
};
function grams(s){
  const tokens=new Map();
  const str=s.toLowerCase().replace(/\s/g,"");
  for(let i=0;i<str.length;i++) for(const n of [1,2]) if(i+n<=str.length){
    const t=str.slice(i,i+n);tokens.set(t,(tokens.get(t)||0)+1);
  }
  return tokens;
}
const examples=Object.entries(intents).flatMap(([intent,phrases])=>phrases.map(p=>({intent,terms:grams(p)})));
function retrieve(query){
  const terms=grams(query);
  let best=0, intent="summary";
  for(const example of examples){
    let dot=0,left=0,right=0;
    for(const t of new Set([...terms.keys(),...example.terms.keys()])){
      const idf=1+Math.log((examples.length+1)/(1+examples.filter(e=>e.terms.has(t)).length));
      const a=(terms.get(t)||0)*idf,b=(example.terms.get(t)||0)*idf;
      dot+=a*b;left+=a*a;right+=b*b;
    }
    const similarity=dot/(Math.sqrt(left*right)||1);
    if(similarity>best){best=similarity;intent=example.intent;}
  }
  return intent;
}
function researchAnswer(question,records,year,group,metric){
  const mentioned=question.match(/(?:19|20)\d{2}/g)?.map(Number)||[];
  const dates=[...new Set(records.map(r=>r.year))].sort();
  if(mentioned.some(y=>!dates.includes(y))) return "当前数据覆盖 "+dates.join("、")+" 年。";
  const named=[...new Set(records.map(r=>r.district))].filter(d=>question.includes(d.replace(/区$/,"")));
  const scope=question.includes("全域")||question.includes("全市")?"":(["中心城区","主城新区"].find(g=>question.includes(g))??group);
  const chosen=mentioned.at(-1)??year;
  const set=records.filter(r=>(!scope||r.group===scope)&&(!named.length||named.includes(r.district)));
  const sample=set.filter(r=>r.year===chosen);
  if(!sample.length) return "该筛选范围内没有匹配的区县。";
  const key=queryMetric(question,metric),[label,unit]=fields[key];
  const intent=retrieve(question);
  const usable=sample.filter(r=>Number.isFinite(r[key])).sort((a,b)=>b[key]-a[key]);
  const summable=["km²","万元","人"].includes(unit);
  const aggregate=rows=>{
    const nums=rows.map(r=>r[key]).filter(Number.isFinite);
    return nums.length ? nums.reduce((a,b)=>a+b,0)/(summable?1:nums.length) : null;
  };
  const lines=[`${chosen} 年 · ${scope||"全域"} · ${named.join("、")||sample.length+" 区"}`];
  if(/转移|转换|转入|来自哪些地类/.test(question)){
    const matrix=aggregateMatrix(sample);
    if(!matrix)lines.push("当前筛选没有阶段转移数据。");
    else{
      const added=matrix.map((r,i)=>({name:classNames[i],area:i===7?0:r[7]})).sort((a,b)=>b.area-a.area);
      lines.push("新增不透水面的期初地类："+added.filter(r=>r.area>0).slice(0,4).map(r=>r.name+" "+format(r.area)+" km²").join("、"));
    }
  } else if(intent==="source"||/来源|质量|口径/.test(question)){
    const refs=[...new Set(sample.flatMap(r=>[r.source_gdp,r.source_pop]).filter(Boolean))];
    lines.push(...(refs.length?refs:["数据来自当前加载的演示面板。"]));
  } else if(mentioned.length>1||/趋势|历年|四期|逐年|各年/.test(question)||(intent==="trend"&&!named.length&&!/多少|排名|最高|最低/.test(question))){
    for(const y of (mentioned.length>1?[...new Set(mentioned)]:dates)){
      lines.push(`${y} 年 · ${label}${summable?"合计":"均值"} ${format(aggregate(set.filter(r=>r.year===y)),key.includes("score")?4:2)} ${unit}`);
    }
  } else if(/总结|概括|总体/.test(question)){
    for(const k of ["built_km2","expansion_km2","population","gdp_10k_cny"]){
      const nums=sample.map(r=>r[k]).filter(Number.isFinite);
      if(nums.length)lines.push(`${fields[k][0]}合计 ${format(nums.reduce((a,b)=>a+b,0))} ${fields[k][1]}`);
    }
    const leader=[...sample].sort((a,b)=>b.intensive_score-a.intensive_score)[0];
    lines.push(`区内集约得分最高为${leader.district}（${format(leader.intensive_score,4)}）。`);
  } else if(!usable.length) lines.push("当前观测缺少该指标的可用数值。");
  else if(named.length>=2){
    for(const r of usable) lines.push(`${r.district} · ${label} ${format(r[key],key.includes("score")?4:2)} ${unit}`);
    if(usable.length===2) lines.push(`差额 ${format(usable[0][key]-usable[1][key],key.includes("score")?4:2)} ${unit}`);
  } else {
    lines.push(`${label}${summable?"合计":"均值"} ${format(aggregate(sample),key.includes("score")?4:2)} ${unit}。`);
    if(/最低|最少|最小|倒数/.test(question)) usable.reverse();
    const top=usable.slice(0,3);
    lines.push(top.map((r,i)=>`${i+1}. ${r.district}　${format(r[key],key.includes("score")?4:2)} ${unit}`).join("\n"));
  }
  if(sample[0].data_kind==="demo") lines.push("数据性质：模拟。");
  else lines.push("依据：CLCD 与区年统计面板；GDP 为当年现价。"+(sample.some(r=>r.provisional)?"本年经济分项含待复核记录。":""));
  return lines.join("\n");
}
