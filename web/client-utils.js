"use strict";
const get=id=>document.getElementById(id);
function make(tag, text, cls) {
  const e=document.createElement(tag);
  if(text!=null)e.textContent=text;
  if(cls)e.className=cls;
  return e;
}
function addOption(select,value,label){select.add(new Option(label,value));}
function readLocal(key,fallback){
  try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}
}
function writeLocal(key,value){
  try{localStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;}
}
function saveTable(name,rows,columns){
  const quote=value=>'"'+String(value??"").replaceAll('"','""')+'"';
  const content="\ufeff"+[columns,...rows.map(r=>columns.map(k=>r[k]))].map(row=>row.map(quote).join(",")).join("\r\n");
  if(window.CQLandAndroid){window.CQLandAndroid.saveCsv(name,content);return;}
  const url=URL.createObjectURL(new Blob([content],{type:"text/csv;charset=utf-8"}));
  const link=make("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function studyData(){
  const response=await fetch("/dashboard.json");
  if(!response.ok)throw new Error("数据读取失败");
  return enrichObservations(await response.json());
}
