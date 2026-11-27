"use strict";
const analysisCharts=new Map();
const modelLabels={median:"训练中位数基线",ridge:"岭回归",random_forest:"随机森林"};
const chartColors=["#286853","#a06b3d","#6b8799"];
let analysisSnapshot=null, loadingAnalysis=false;
function chart(id,options){
  const element=document.getElementById(id);
  if(!analysisCharts.has(id)){
    const instance=echarts.init(element,null,{renderer:"canvas"});
    const observer=new ResizeObserver(()=>{if(element.clientWidth)instance.resize();});
    observer.observe(element);
    analysisCharts.set(id,instance);
  }
  const instance=analysisCharts.get(id);
  instance.resize();
  instance.setOption({...options,color:chartColors,animationDuration:250,aria:{enabled:true}},true);
}
function drawAnalytics(report){
  const trend=report.yearly,model=report.model;
  chart("analysis-trend",{
    tooltip:{trigger:"axis"},grid:{left:66,right:22,top:20,bottom:38},
    xAxis:{type:"category",data:trend.map(r=>r.year)},
    yAxis:{type:"value",name:"km²"},
    series:[{name:"不透水面",type:"line",showSymbol:true,symbolSize:8,areaStyle:{opacity:.13},
      data:trend.map(r=>Number(r.built_km2.toFixed(3)))}]
  });
  const period=document.getElementById("analysis-period");
  if(period.dataset.fingerprint!==report.panel_fingerprint){
    period.replaceChildren();
    period.dataset.fingerprint=report.panel_fingerprint;
    for(const end of [...new Set(report.flows.map(row=>row.end))]){
      const row=report.flows.find(item=>item.end===end);
      period.add(new Option(row.start+"—"+end,end));
    }
    period.selectedIndex=period.options.length-1;
    period.onchange=()=>drawHeat(report);
    document.getElementById("analysis-changed").onchange=()=>drawHeat(report);
  }
  drawHeat(report);
  chart("analysis-metrics",{
    title:{text:"时间留出误差",textStyle:{fontSize:14}},tooltip:{trigger:"axis"},
    legend:{bottom:0},grid:{left:60,right:12,top:45,bottom:60},
    xAxis:{type:"category",data:Object.values(modelLabels),axisLabel:{fontSize:10}},
    yAxis:{type:"value",name:"km²/年"},
    series:["mae","rmse"].map(key=>({name:key.toUpperCase(),type:"bar",
      data:Object.keys(modelLabels).map(name=>model.scores[name][key])}))
  });
  const predictions=model.predictions;
  chart("analysis-predictions",{
    title:{text:"各区县年均净扩张回测",textStyle:{fontSize:14}},tooltip:{trigger:"axis"},
    legend:{bottom:0},grid:{left:58,right:22,top:46,bottom:80},
    xAxis:{type:"category",data:predictions.map(r=>r.district),axisLabel:{rotate:40,fontSize:10}},
    yAxis:{type:"value",name:"km²/年"},
    series:[{name:"实测",type:"line",data:predictions.map(r=>r.actual)},
      {name:"中位数基线",type:"line",lineStyle:{type:"dashed"},data:predictions.map(r=>r.median)},
      {name:"随机森林",type:"line",data:predictions.map(r=>r.random_forest)},
      {name:"岭回归",type:"line",data:predictions.map(r=>r.ridge)}]
  });
  document.getElementById("analysis-error-table").replaceChildren(...Object.entries(model.scores).map(([key,score])=>{
    const tr=document.createElement("tr");
    for(const value of [modelLabels[key],format(score.mae,3),format(score.rmse,3)])tr.insertCell().textContent=value;
    return tr;
  }));
  document.getElementById("analysis-design").textContent=
     `${model.train_years.map(years=>years.join("—")).join("、")} 训练，共 ${model.train_count} 条。${model.holdout_years.join("—")} 留出，共 ${model.holdout_count} 条。${model.validation}`;
  const best=Object.keys(model.scores).sort((a,b)=>model.scores[a].mae-model.scores[b].mae)[0];
  document.getElementById("analysis-model-note").textContent=
    `本次留出检验中，${modelLabels[best]}的 MAE 最低。模型得分用于历史回测与方法对照。`;
  const clusters=model.clusters;
  document.getElementById("analysis-cluster-note").textContent=
    `${clusters.year} 年期初特征 · K-means 分 ${clusters.k} 组 · 轮廓系数 ${format(clusters.silhouette,3)}。组号用于区分统计特征。`;
  chart("analysis-clusters",{
    tooltip:{renderMode:"richText",formatter:item=>{
      const [area,pop,name]=item.value;
      return `${name}\n不透水面 ${format(area)} km²\n常住人口 ${format(pop)} 万人`;
    }},
    legend:{bottom:0},grid:{left:72,right:42,top:35,bottom:54},
    xAxis:{type:"value",name:"km²"},yAxis:{type:"value",name:"万人"},
    series:Array.from({length:clusters.k},(_,i)=>({name:"组 "+(i+1),type:"scatter",symbolSize:12,
      data:clusters.rows.filter(r=>r.cluster===i+1).map(r=>[r.baseline_area_km2,r.baseline_population/10000,r.district])}))
  });
}
function drawHeat(report){
  const end=Number(document.getElementById("analysis-period").value);
  const changed=document.getElementById("analysis-changed").checked;
  const values=report.flows.filter(r=>r.end===end&&(!changed||r.from_class!==r.to_class))
    .map(r=>[r.to_class-1,r.from_class-1,Number(r.area_km2.toFixed(3))]);
  chart("analysis-heat",{
    tooltip:{formatter:item=>`${classNames[item.value[1]]} → ${classNames[item.value[0]]} · ${item.value[2]} km²`},
    grid:{left:63,right:20,top:14,bottom:86},
    xAxis:{type:"category",data:classNames,axisLabel:{rotate:33,fontSize:10}},
    yAxis:{type:"category",data:classNames},
    visualMap:{min:0,max:Math.max(1,...values.map(v=>v[2])),calculable:true,orient:"horizontal",left:"center",bottom:1,
      inRange:{color:["#f5f2dc","#9fba9b","#275d4e"]}},
    series:[{type:"heatmap",data:values}]
  });
}
function openAnalytics(){
  const info=document.getElementById("analytics-status"),content=document.getElementById("analytics-content");
  if(!window.echarts){info.textContent="ECharts 资源未加载。";return;}
  if(analysisSnapshot){drawAnalytics(analysisSnapshot);return;}
  if(loadingAnalysis)return;
  loadingAnalysis=true;
  fetch("/api/v1/analysis/").then(async response=>{
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"分析报告暂不可用。");
    analysisSnapshot=data;content.hidden=false;
    info.textContent=`${data.counts.cover} 条区年覆盖 · ${data.counts.change} 条区级阶段变化 · ${data.counts.flow.toLocaleString()} 条地类转移。此页呈现全研究区的固定分析口径。`;
    if(!document.getElementById("analytics").hidden)drawAnalytics(data);
  }).catch(error=>{info.textContent=error.message;}).finally(()=>{loadingAnalysis=false;});
}
