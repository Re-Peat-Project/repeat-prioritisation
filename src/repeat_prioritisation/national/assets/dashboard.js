(function(){
"use strict";
const K=DATA.khg, N=K.id.length, PR=DATA.params, M=PR.length, META=DATA.meta;
/*I18N*/
let LANG="en";
const t=(s,v)=>{let r=LANG==="id"&&ID[s]!==undefined?ID[s]:s;if(v)r=r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m);return r};
const loc=()=>LANG==="id"?"id-ID":"en-GB";
const dsep=s=>LANG==="id"?s.replace(".",","):s;
const fmt=(v,nd=2)=>{if(v==null||!isFinite(v))return t("n/a");if(Math.abs(v)>=1000)return Math.round(v).toLocaleString(LANG==="id"?"id-ID":"en");let s=(+v).toFixed(nd);if(s.indexOf(".")>=0)s=s.replace(/0+$/,"").replace(/\.$/,"");return dsep(s)};
const fx=(v,nd=2)=>dsep((+v).toFixed(nd));
const MONTHS_EN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],MONTHS_ID=["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"];
const MONTHF_EN=["January","February","March","April","May","June","July","August","September","October","November","December"],MONTHF_ID=["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
const mon=i=>(LANG==="id"?MONTHS_ID:MONTHS_EN)[i-1], monf=i=>(LANG==="id"?MONTHF_ID:MONTHF_EN)[i-1];
const nowDate=()=>META.period_now?new Date(META.period_now).toLocaleDateString(loc(),{day:"numeric",month:"short",year:"numeric"}):"";
const GROUPS={hist:{label:"Fire history",css:"--hist"},now:{label:"This year",css:"--now"},canal:{label:"Canals",css:"--canal"}};
const GK=["hist","now","canal"], GI=PR.map(p=>GK.indexOf(p.group));
const DEF=PR.map(p=>META.weights[p.id]);
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const clamp01=x=>x<0?0:x>1?1:x;
const state={w:DEF.slice(),minPeat:META.min_peat,islands:new Set(),missing:"skip",view:"top",sel:null,table:false,conf:"mh"};
const onlyHigh=()=>state.conf==="h"&&!!K.n1h;                                    // this year's hotspots: high confidence only
const val=(k,i)=>onlyHigh()&&PR[k].id==="n1"?K.n1h[i]:K.v[k][i];
const TOPN=30;
const PKEY={
  f1:["Burnt-area polygons, flagged by year, 2015 to 2025.","Area burned per year on peat, divided by the KHG's peat area, averaged over the years. A patch counts as peat if its centre point is on a peat cell."],
  f2:["Burnt-area polygons, flagged by year, 2015 to 2025.","Peat burned two or more times in 2015 to 2025, divided by peat area."],
  f3:["FIRMS VIIRS S-NPP hotspots, 2015 to 2025.","Vegetation-fire detections of nominal or high confidence that fall on peat, per km2 of peat per year."],
  n1:["KLH MODIS hotspots, 1 Jan to {date}.","Medium and high confidence detections on peat, per km2 of peat, year to date. MODIS differs from VIIRS, so this is a separate parameter."],
  n2:["Burnt-area polygons, flag for this year.","Share of the peat burned so far this year."],
  c1:["OSM-based canal layer, class from KODE_KANAL (primer).","Canal length per km2 of KHG. No value where no canal is mapped."],
  c2:["OSM-based canal layer, class from KODE_KANAL (sekunder).","Canal length per km2 of KHG. No value where no canal is mapped."],
  c3:["OSM-based canal layer, class from KODE_KANAL (tersier).","Canal length per km2 of KHG. No value where no canal is mapped."]};
function paramTip(p){const n=PKEY[p.id]||["",""];return `<b>${t(p.label)}</b><br><span>${t(p.unit)}</span><br>${t(n[0],{date:nowDate()})}<br><span>${t(n[1])}</span>`}
const tipAttr=h=>' data-tip="'+String(h).replace(/&/g,"&amp;").replace(/"/g,"&quot;")+'"';
{const find=e=>e.target.closest?e.target.closest("[data-tip]"):null;
  document.addEventListener("mouseover",e=>{const el=find(e);if(el)showTip(el.dataset.tip,e)});
  document.addEventListener("mousemove",e=>{const el=find(e);if(el)showTip(el.dataset.tip,e)});
  document.addEventListener("mouseout",e=>{const el=find(e);if(el&&!(e.relatedTarget&&el.contains(e.relatedTarget)))hideTip()});
  document.addEventListener("focusin",e=>{const el=find(e);if(el){const r=el.getBoundingClientRect();showTip(el.dataset.tip,{clientX:r.left,clientY:r.bottom})}});
  document.addEventListener("focusout",hideTip)}

// ---------------------------------------------------------------- tooltip
const tipEl=$("#tip");
function showTip(html,e){tipEl.innerHTML=html;tipEl.style.display="block";const w=tipEl.offsetWidth,h=tipEl.offsetHeight;let x=e.clientX+14,y=e.clientY+14;if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;tipEl.style.left=x+"px";tipEl.style.top=y+"px"}
function hideTip(){tipEl.style.display="none"}

// ---------------------------------------------------------------- scoring (same scaling as common.scoring)
function compute(w){
  const elig=new Uint8Array(N);let ne=0;
  for(let i=0;i<N;i++){const ok=K.area[i]>=META.min_area&&K.peat[i]!=null&&K.peat[i]>=state.minPeat&&(!state.islands.size||state.islands.has(K.island[i]));elig[i]=ok?1:0;if(ok)ne++}
  const minUnits=Math.min(20,Math.max(3,Math.floor(ne/2)));
  const Z=new Array(M).fill(null),ZR=new Array(M).fill(null),used=[];
  for(let k=0;k<M;k++){
    if(!(w[k]>0))continue;
    const vals=[];for(let i=0;i<N;i++){if(elig[i]){const v=val(k,i);if(v!=null&&isFinite(v))vals.push(v)}}
    if(vals.length<minUnits)continue;
    vals.sort(d3.ascending);const lo=d3.quantileSorted(vals,.05),hi=d3.quantileSorted(vals,.95);
    if(!(hi-lo>1e-12))continue;
    const z=new Float64Array(N).fill(NaN),zr=new Float64Array(N).fill(NaN),have=[];
    for(let i=0;i<N;i++){if(elig[i]){const v=val(k,i);if(v!=null&&isFinite(v)){z[i]=clamp01((v-lo)/(hi-lo));zr[i]=(v-lo)/(hi-lo);have.push(z[i])}}}
    ZR[k]=zr;
    if(state.missing==="median"){const med=d3.median(have);for(let i=0;i<N;i++)if(elig[i]&&!isFinite(z[i]))z[i]=med}
    Z[k]=z;used.push(k);
  }
  const score=new Float64Array(N).fill(NaN),tie=new Float64Array(N).fill(0),contrib=new Float64Array(N*3);
  for(let i=0;i<N;i++){if(!elig[i])continue;let num=0,den=0;
    for(const k of used){const z=Z[k][i];if(isFinite(z)){num+=w[k]*z;den+=w[k];contrib[i*3+GI[k]]+=w[k]*z}}
    if(den>0){score[i]=num/den;for(let g=0;g<3;g++)contrib[i*3+g]/=den;let tt=0;for(const k of used){const z=ZR[k][i];if(isFinite(z))tt+=w[k]*z}tie[i]=tt/den}
  }
  const order=[];for(let i=0;i<N;i++)if(elig[i]&&isFinite(score[i]))order.push(i);
  order.sort((a,b)=>score[b]-score[a]||tie[b]-tie[a]||a-b);     // ties at the 95th percentile cap are ordered by the unclipped values
  const rank=new Int32Array(N);for(let r=0;r<order.length;r++)rank[order[r]]=r+1;
  return {elig,score,contrib,order,rank,Z,used,ne};
}
let R=null,R0=null;   // R: current weights; R0: default weights under the same filters
function recompute(){R=compute(state.w);R0=compute(DEF)}

// ---------------------------------------------------------------- controls
function buildControls(){
  const host=$("#sliders");host.innerHTML="";
  for(const g of GK){
    const d=document.createElement("div");d.className=g;
    d.innerHTML=`<div class="gs"><span class="sw" style="background:var(${GROUPS[g].css})"></span>${t(GROUPS[g].label)}</div>`;
    PR.forEach((p,k)=>{if(p.group!==g)return;
      const row=document.createElement("div");row.className="sl";
      row.innerHTML=`<label for="w-${p.id}" class="hasTip"${tipAttr(paramTip(p))}>${t(p.label)}</label><input type="range" id="w-${p.id}" min="0" max="4" step="0.1" value="${state.w[k]}"><output id="o-${p.id}">${fmt(state.w[k],1)}</output>`;
      d.appendChild(row)});
    d.style.flex=String(d.querySelectorAll(".sl").length+.6);host.appendChild(d)}
  PR.forEach((p,k)=>{const el=$("#w-"+p.id);el.addEventListener("input",()=>{state.w[k]=+el.value;$("#o-"+p.id).textContent=fmt(state.w[k],1);schedule()})});
  const presets={"Default":DEF,"History":PR.map((p,k)=>p.group==="now"?0:DEF[k]),"This year":PR.map(p=>p.id==="n1"?1:0),"Canals":PR.map((p,k)=>p.group==="canal"?DEF[k]:0),"Equal":PR.map(()=>1)};
  const ps=$("#presets");ps.innerHTML="";
  for(const [name,w] of Object.entries(presets)){const b=document.createElement("button");b.type="button";b.textContent=t(name);b.onclick=()=>{state.w=w.slice();syncSliders();schedule()};b.dataset.p=name;ps.appendChild(b)}
  state.presets=presets;
  $("#reset").onclick=()=>{state.w=DEF.slice();state.minPeat=META.min_peat;state.islands.clear();state.missing="skip";syncSliders();syncFilters();schedule()};
  // filters
  const mp=$("#minpeat");mp.value=state.minPeat;mp.oninput=()=>{state.minPeat=+mp.value;$("#minpeat-o").textContent=state.minPeat+" km2";schedule()};
  const isl=$("#islands");isl.innerHTML="";
  [...new Set(K.island)].filter(Boolean).sort().forEach(n=>{const b=document.createElement("button");b.type="button";b.textContent=n;b.dataset.n=n;b.onclick=()=>{state.islands.has(n)?state.islands.delete(n):state.islands.add(n);syncFilters();schedule()};isl.appendChild(b)});
  const ms=$("#missing");ms.innerHTML="";[["skip","Ignore"],["median","Average"]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=t(tx);b.dataset.v=v;b.onclick=()=>{state.missing=v;syncFilters();schedule()};ms.appendChild(b)});
  const cf=$("#conf");cf.innerHTML="";if(K.n1h)[["mh","Medium + high"],["h","High only"]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=t(tx);b.dataset.v=v;b.onclick=()=>{state.conf=v;syncFilters();schedule();renderProfile()};cf.appendChild(b)});
  $("#conf").closest(".ctl").style.display=K.n1h?"":"none";
  const vs=$("#view");vs.innerHTML="";[["top",t("Top {n}",{n:TOPN})],["team",t("Team KHG")]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=tx;b.dataset.v=v;b.onclick=()=>{state.view=v;syncFilters();schedule()};vs.appendChild(b)});
  const rm=$("#rank-mode");rm.innerHTML="";[["list","Bars"],["table","Table"]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=t(tx);b.dataset.v=v;b.onclick=()=>{state.table=v==="table";syncFilters();render()};rm.appendChild(b)});
  const lg=$("#lang");lg.innerHTML="";[["en","EN"],["id","ID"]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=tx;b.dataset.v=v;b.onclick=()=>setLang(v);lg.appendChild(b)});
  syncFilters();
}
function syncSliders(){PR.forEach((p,k)=>{$("#w-"+p.id).value=state.w[k];$("#o-"+p.id).textContent=fmt(state.w[k],1)})}
function syncFilters(){
  $("#minpeat").value=state.minPeat;$("#minpeat-o").textContent=state.minPeat+" km2";
  $$("#islands button").forEach(b=>b.classList.toggle("on",state.islands.has(b.dataset.n)));
  $$("#missing button").forEach(b=>b.classList.toggle("on",b.dataset.v===state.missing));
  $$("#view button").forEach(b=>b.classList.toggle("on",b.dataset.v===state.view));
  $$("#conf button").forEach(b=>b.classList.toggle("on",b.dataset.v===state.conf));
  $$("#rank-mode button").forEach(b=>b.classList.toggle("on",(b.dataset.v==="table")===state.table));
  $$("#lang button").forEach(b=>b.classList.toggle("on",b.dataset.v===LANG));
}
function markPresets(){for(const b of $$("#presets button")){const w=state.presets[b.dataset.p];b.classList.toggle("on",w.every((x,k)=>Math.abs(x-state.w[k])<1e-9))}}

// ---------------------------------------------------------------- ranking list
const ROWH=26;
const confChar=["○","◐","●"], confName=["low","medium","high"];
function listItems(){
  if(state.view==="team"){
    const tm=[];for(let i=0;i<N;i++)if(K.team[i])tm.push(i);
    tm.sort((a,b)=>(R.rank[a]||1e9)-(R.rank[b]||1e9)||a-b);return tm}
  return R.order.slice(0,TOPN);
}
function renderList(){
  const items=listItems(),host=d3.select("#rank-list");
  host.style("height",items.length*ROWH+"px");
  const maxS=d3.max(items,i=>R.score[i])||1;
  const bw=Math.max(60,(($("#rank-list").clientWidth||520)-28-270-40-40-32));
  const x=d3.scaleLinear([0,Math.max(maxS,.01)],[0,bw]);
  const rows=host.selectAll("div.row").data(items,i=>K.id[i]);
  rows.exit().classed("exit",true).transition().duration(300).remove();
  const en=rows.enter().append("div").attr("class","row")
    .style("transform",(i,j)=>`translateY(${(items.length+1)*ROWH}px)`).style("opacity",0)
    .on("click",(e,i)=>select(K.id[i]))
    .on("mousemove",(e,i)=>showTip(tipFor(i),e)).on("mouseleave",hideTip);
  en.append("span").attr("class","rk");en.append("span").attr("class","nm");
  en.append("span").attr("class","bar-wrap").append("svg").attr("height",14);
  en.append("span").attr("class","sc");en.append("span").attr("class","dl");
  const all=en.merge(rows);
  all.classed("sel",i=>K.id[i]===state.sel);
  all.style("transform",(i,j)=>`translateY(${j*ROWH}px)`).style("opacity",1);
  all.select(".rk").text(i=>R.rank[i]||"-");
  all.select(".nm").html(i=>`<span title="${esc(t("Data confidence: {c}",{c:t(confName[K.conf[i]])}))}" style="color:var(--muted)">${confChar[K.conf[i]]}</span> ${esc(K.name[i])}${K.team[i]?` <span title="${esc(t("Team KHG"))}" style="color:var(--ink2)">◆</span>`:""}`);
  all.select(".sc").text(i=>isFinite(R.score[i])?fx(R.score[i],2):"");
  all.select(".dl").attr("data-tip",t("Change in rank against the default weights.")).text(i=>{if(!R.rank[i]||!R0.rank[i])return "";const d=R0.rank[i]-R.rank[i];return d>0?"▲"+d:d<0?"▼"+(-d):"·"});
  all.select("svg").each(function(i){
    const s=d3.select(this).attr("width",bw);const segs=[0,1,2].map(g=>({g,w:R.contrib[i*3+g]}));
    const rects=s.selectAll("rect").data(isFinite(R.score[i])?segs:[],d=>d.g);
    rects.exit().remove();
    rects.enter().append("rect").attr("y",1).attr("height",12).attr("rx",2).merge(rects)
      .attr("fill",d=>`var(${GROUPS[GK[d.g]].css})`)
      .attr("x",d=>{const v=segs.slice(0,d.g).reduce((a,b)=>a+b.w,0);return x(v)})
      .attr("width",d=>Math.max(0,x(d.w)-2));
  });
  $("#rank-title").textContent=state.view==="team"?t("Team KHG of {n} ranked",{n:R.order.length}):t("Top {k} of {n} ranked",{k:TOPN,n:R.order.length});
  const lg=$("#rank-legend");lg.innerHTML=GK.map(g=>`<span class="hasTip"${tipAttr(t("What the {g} parameters add to the score: the length of this segment.",{g:t(GROUPS[g].label).toLowerCase()}))}><span class="sw" style="background:var(${GROUPS[g].css})"></span>${t(GROUPS[g].label)}</span>`).join("")+`<span style="margin-left:auto;color:var(--muted)"${tipAttr(t("Data confidence: high when canals are mapped, there is enough fire signal and enough peat. Medium: two of the three. Low: fewer. A diamond marks the team KHG."))}>${t("● high ◐ medium ○ low confidence · ◆ team")}</span>`;
}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;")}
function tipFor(i){
  const r=R.rank[i];const parts=GK.map((g,j)=>`${t(GROUPS[g].label)} ${fx(R.contrib[i*3+j],2)}`);
  return `<b>${esc(K.name[i])}</b><br><span>${esc(K.prov[i])} · ${t("peat {x} km2",{x:fmt(K.peat[i],0)})}</span><br>${r?t("rank {r} · score {s}",{r,s:fx(R.score[i],2)}):t("not ranked (filters)")}<br><span>${r?parts.join(" · "):""}</span>${noCanals(i)?"<br><span>"+t("no canals mapped")+"</span>":""}`}
function noCanals(i){return [5,6,7].every(k=>K.v[k][i]==null)}

const tbl={q:"",all:false,k:0,dir:1,cols:[],rows:[]};
function tableCols(){
  return [
    {t:"#",tip:t("Rank at your weights."),get:i=>R.rank[i]||null,num:1,nd:0},
    {t:"KHG",tip:t("Peat hydrological unit. Click a row to open its profile."),get:i=>K.name[i]},
    {t:t("Province"),tip:t("Province in the official KHG table (SK.129/MENLHK/2017)."),get:i=>K.prov[i]},
    {t:t("Island"),tip:t("Island group."),get:i=>K.island[i]},
    {t:t("Peat km2"),tip:t("Peat area inside the KHG, from the GFW peat extent."),get:i=>K.peat[i],num:1,nd:0,unit:"km2"},
    {t:t("Score"),tip:t("Weighted mean of the parameters, scaled 0 to 1."),get:i=>isFinite(R.score[i])?R.score[i]:null,num:1,nd:3},
    ...PR.map((p,k)=>({t:t(p.label),tip:paramTip(p),get:i=>val(k,i),num:1,nd:3,unit:t(p.unit),param:1}))];
}
function fmtCell(c,v){return v==null||v===""?t("n/a"):c.num?fmt(v,c.nd):esc(v)}
function buildTable(){
  const host=$("#rank-table");
  host.innerHTML=`<div class="tbar"><input type="search" id="tq" placeholder="${esc(t("Search KHG, province or island"))}" aria-label="${esc(t("Search the table"))}" value="${esc(tbl.q)}"><label class="chk"><input type="checkbox" id="tall"${tbl.all?" checked":""}> ${t("Include not ranked")}</label><span id="tcount" class="hint"></span><button type="button" id="csv" class="ghost">${t("Download CSV")}</button></div><div class="tablewrap"><table><thead></thead><tbody></tbody></table></div>`;
  $("#tq").oninput=e=>{tbl.q=e.target.value.trim().toLowerCase();renderTable()};
  $("#tall").onchange=e=>{tbl.all=e.target.checked;renderTable()};
  host.querySelector("thead").addEventListener("click",e=>{const th=e.target.closest("th");if(!th)return;const k=+th.dataset.k;if(tbl.k===k)tbl.dir=-tbl.dir;else{tbl.k=k;tbl.dir=1}renderTable()});
  const tb=host.querySelector("tbody");
  tb.addEventListener("click",e=>{const tr=e.target.closest("tr");if(tr)select(K.id[+tr.dataset.i])});
  tb.addEventListener("mousemove",e=>{const td=e.target.closest("td");if(!td)return;const c=tbl.cols[td.cellIndex],i=+td.parentNode.dataset.i;
    showTip(`<b>${esc(K.name[i])}</b><br>${esc(c.t)}: ${fmtCell(c,c.get(i))}${c.unit&&c.get(i)!=null?" <span>"+esc(c.unit)+"</span>":""}`,e)});
  tb.addEventListener("mouseleave",hideTip);
  $("#csv").onclick=()=>{const cols=tbl.cols,csv=[cols.map(c=>c.t+(c.unit?" ("+c.unit+")":"")),...tbl.rows.map(i=>cols.map(c=>c.get(i)))]
      .map(r=>r.map(v=>`"${String(v==null?"":v).replace(/"/g,'""')}"`).join(",")).join("\n");
    const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="khg_ranking.csv";a.click()};
}
function renderTable(){
  const cols=tableCols();tbl.cols=cols;
  let rows=tbl.all?d3.range(N):R.order.slice();
  if(tbl.q)rows=rows.filter(i=>(K.name[i]+" "+K.prov[i]+" "+K.island[i]+" "+K.id[i]).toLowerCase().includes(tbl.q));
  const c=cols[tbl.k];
  rows.sort((a,b)=>{const x=c.get(a),y=c.get(b);if(x==null&&y==null)return a-b;if(x==null)return 1;if(y==null)return -1;return (c.num?x-y:String(x).localeCompare(String(y)))*tbl.dir||a-b});
  tbl.rows=rows;
  const host=$("#rank-table");
  host.querySelector("thead").innerHTML="<tr>"+cols.map((c,j)=>{
    const tip=c.param?c.tip:`<b>${esc(c.t)}</b>${c.unit?"<br><span>"+esc(c.unit)+"</span>":""}<br>${c.tip}`;
    return `<th data-k="${j}" class="sortable${j===tbl.k?" on":""}"${tipAttr(tip+"<br><span>"+t("Click to sort")+"</span>")}>${esc(c.t)}<span class="arr">${j===tbl.k?(tbl.dir>0?"▲":"▼"):""}</span></th>`}).join("")+"</tr>";
  host.querySelector("tbody").innerHTML=rows.map(i=>`<tr data-i="${i}"${K.id[i]===state.sel?' class="sel"':""}>${cols.map(c=>`<td>${fmtCell(c,c.get(i))}</td>`).join("")}</tr>`).join("");
  $("#tcount").textContent=t("{a} of {b}",{a:rows.length,b:tbl.all?N:R.order.length});
}

// ---------------------------------------------------------------- basemap (OpenFreeMap vector tiles, Positron style, muted; needs internet)
const DROP=/^(building|aeroway.*|railway.*|highway-shield.*|road_shield.*|airport|road_pier|road_area_pier|tunnel_.*|highway_path|highway-name-path|highway-name-minor)$/;
const COLOR_PROPS=["background-color","fill-color","fill-outline-color","line-color","text-color","text-halo-color"];
function mapColors(v,fn,prop){
  if(typeof v==="string"&&/^(#|rgb|hsl)/.test(v))return fn(v,prop);
  if(Array.isArray(v))return v.map(x=>mapColors(x,fn,prop));
  if(v&&typeof v==="object"){const o={};for(const k in v)o[k]=mapColors(v[k],fn,prop);return o}
  return v}
function darkColor(c,prop){const h=d3.hsl(c);if(!isFinite(h.h))h.h=0;const text=prop==="text-color";const l=text?1-h.l:.075+.27*(1-h.l);return d3.hsl(h.h,h.s*.45,Math.min(.95,l),h.opacity).formatRgb()}
const BASE_LIGHT=(()=>{const s=JSON.parse(JSON.stringify(DATA.style));s.layers=s.layers.filter(l=>!DROP.test(l.id));return s})();
const BASE_DARK=(()=>{const s=JSON.parse(JSON.stringify(BASE_LIGHT));for(const l of s.layers)for(const p of COLOR_PROPS)if(l.paint&&l.paint[p]!==undefined)l.paint[p]=mapColors(l.paint[p],darkColor,p);return s})();
const isDark=()=>{const th=document.documentElement.dataset.theme;return th?th==="dark":matchMedia("(prefers-color-scheme:dark)").matches};
const baseStyle=()=>isDark()?BASE_DARK:BASE_LIGHT;
function firstSymbol(map){const l=map.getStyle().layers.find(l=>l.type==="symbol");return l?l.id:undefined}   // our layers go under the labels
function restyleBase(map){const s=baseStyle();for(const l of s.layers){if(!map.getLayer(l.id)||!l.paint)continue;for(const p of COLOR_PROPS)if(l.paint[p]!==undefined)try{map.setPaintProperty(l.id,p,l.paint[p])}catch(e){}}}
function mapLabels(map){   // place names in the page language where OpenStreetMap has them, else the local name
  if(!map||!map.isStyleLoaded())return;
  const code=LANG==="id"?"id":"en";
  for(const l of map.getStyle().layers){if(l.type==="symbol"&&l.layout&&l.layout["text-field"]!==undefined&&!l.id.startsWith("p-"))try{map.setLayoutProperty(l.id,"text-field",["coalesce",["get","name:"+code],["get","name"]])}catch(e){}}}
function newMap(container,opts){
  const m=new maplibregl.Map({container,style:baseStyle(),attributionControl:false,cooperativeGestures:true,dragRotate:false,pitchWithRotate:false,renderWorldCopies:false,...opts});
  m.addControl(new maplibregl.AttributionControl({compact:true}));       // the style's tile source supplies the OpenFreeMap, OpenMapTiles and OpenStreetMap credits
  m.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-left");
  m.touchZoomRotate.disableRotation();m.on("error",()=>{});m.on("load",()=>mapLabels(m));return m}

// ---------------------------------------------------------------- national map
let nat=null,natReady=false;
const NAT_BOUNDS=[[94.5,-11.5],[141.8,6.5]];
function natGeo(){return {type:"FeatureCollection",features:DATA.geo.map((polys,i)=>({type:"Feature",id:i,properties:{team:K.team[i]?1:0},geometry:{type:"MultiPolygon",coordinates:polys}}))}}
const natLayers={fill:true,team:true,labels:true};
function applyNatLayers(){
  if(!nat||!natReady)return;
  const v=(id,on)=>{if(nat.getLayer(id))nat.setLayoutProperty(id,"visibility",on?"visible":"none")};
  v("khg-fill",natLayers.fill);v("khg-team",natLayers.team);
  for(const l of nat.getStyle().layers)if(l.type==="symbol")nat.setLayoutProperty(l.id,"visibility",natLayers.labels?"visible":"none");
}
function buildMapTools(){
  const host=$("#map-tools");host.innerHTML="";
  const lb=document.createElement("span");lb.className="lab";lb.textContent=t("Layers");host.appendChild(lb);
  [["fill","KHG score",`<i class="poly" style="background:var(--ramp1)"></i>`,"Colour of each KHG by score. Off leaves only the outlines."],["team","Team KHG outline",`<i style="background:var(--ink);height:2px"></i>`,"Dark outline around the KHG selected by the team."],["labels","Place names",`<i class="poly" style="background:var(--muted)"></i>`,"Basemap place names."]]
    .forEach(([k,tx,ic,tp])=>{const c=document.createElement("span");c.className="tg"+(natLayers[k]?"":" off");c.innerHTML=ic+t(tx);c.dataset.tip=t(tp);
      c.onclick=()=>{natLayers[k]=!natLayers[k];c.classList.toggle("off",!natLayers[k]);applyNatLayers()};host.appendChild(c)});
}
function buildZoomButtons(){
  buildMapTools();
  const isl=[["All",NAT_BOUNDS],["Sumatra",[[95,-6.5],[106.5,6]]],["Kalimantan",[[108,-4.5],[119.5,4.5]]],["Papua",[[130.5,-9.5],[141,0.5]]]];
  const zb=$("#zoom-btns");zb.innerHTML="";
  for(const [n,b] of isl){const btn=document.createElement("button");btn.type="button";btn.textContent=t(n);btn.onclick=()=>nat&&nat.fitBounds(b,{padding:16,duration:600});zb.appendChild(btn)}
}
function buildMap(){
  buildZoomButtons();
  if(nat)return;
  try{nat=newMap("map",{bounds:NAT_BOUNDS,fitBoundsOptions:{padding:14}})}catch(e){$("#map").innerHTML='<p class="hint" style="padding:12px">'+t("The map needs WebGL.")+'</p>';return}
  nat.on("load",()=>{
    nat.addSource("khg",{type:"geojson",data:natGeo()});const before=firstSymbol(nat);
    const none=["coalesce",["feature-state","c"],css("--none")];
    nat.addLayer({id:"khg-fill",type:"fill",source:"khg",paint:{"fill-color":none,"fill-opacity":.9}},before);
    nat.addLayer({id:"khg-line",type:"line",source:"khg",paint:{"line-color":none,"line-width":1}},before);
    nat.addLayer({id:"khg-team",type:"line",source:"khg",filter:["==",["get","team"],1],paint:{"line-color":css("--ink"),"line-width":1.6}},before);
    nat.addLayer({id:"khg-sel",type:"line",source:"khg",paint:{"line-color":css("--now"),"line-width":["case",["boolean",["feature-state","sel"],false],3,0]}},before);
    natReady=true;renderMap();applyNatLayers();
  });
  nat.on("mousemove","khg-fill",e=>{if(e.features.length){nat.getCanvas().style.cursor="pointer";showTip(tipFor(e.features[0].id),e.originalEvent)}});
  nat.on("mouseleave","khg-fill",()=>{nat.getCanvas().style.cursor="";hideTip()});
  nat.on("click","khg-fill",e=>{if(e.features.length)select(K.id[e.features[0].id])});
}
function renderMap(){
  const e=R.order.map(i=>R.score[i]);const lo=d3.min(e)??0,hi=d3.max(e)??1;
  const col=d3.interpolateRgb(css("--ramp0"),css("--ramp1"));
  $("#map-legend").innerHTML=`<span>${fx(lo,2)}</span><span class="ramp" style="background:linear-gradient(90deg,${css("--ramp0")},${css("--ramp1")})"></span><span>${fx(hi,2)}</span><span style="margin-left:auto;color:var(--muted)">${t("grey: not ranked · outlined: team")}</span>`;
  if(!nat||!natReady)return;
  for(let i=0;i<N;i++){const ok=R.elig[i]&&isFinite(R.score[i]);nat.setFeatureState({source:"khg",id:i},{c:ok?col((R.score[i]-lo)/Math.max(hi-lo,1e-9)):css("--none"),sel:K.id[i]===state.sel})}
  nat.setPaintProperty("khg-team","line-color",css("--ink"));nat.setPaintProperty("khg-sel","line-color",css("--now"));
}

// ---------------------------------------------------------------- rank shift (bump) chart
function renderBump(){
  const svg=d3.select("#bump");const w=$("#bump").clientWidth||520,h=Math.max(300,$("#bump").clientHeight||330);svg.attr("viewBox",`0 0 ${w} ${h}`);svg.selectAll("*").remove();
  const n=12,a=R0.order.slice(0,n),b=R.order.slice(0,n);const ids=[...new Set([...a,...b])];
  const moved=ids.some(i=>R.rank[i]!==R0.rank[i]);
  $("#bump-hint").textContent=moved?t("default → your weights"):t("same as default");
  const left=ids.slice().sort((p,q)=>R0.rank[p]-R0.rank[q]),right=ids.slice().sort((p,q)=>(R.rank[p]||1e9)-(R.rank[q]||1e9));
  const y=d3.scalePoint(d3.range(ids.length),[16,h-10]);
  const yl=new Map(left.map((i,j)=>[i,y(j)])),yr=new Map(right.map((i,j)=>[i,y(j)]));
  const x0=185,x1=w-185;
  const g=svg.append("g");
  g.selectAll("path").data(ids).join("path").attr("d",i=>`M${x0},${yl.get(i)}C${(x0+x1)/2},${yl.get(i)} ${(x0+x1)/2},${yr.get(i)} ${x1},${yr.get(i)}`)
    .attr("fill","none").attr("stroke",i=>K.id[i]===state.sel?css("--now"):Math.abs(yl.get(i)-yr.get(i))>y.step()*2.5?css("--ink2"):css("--axis"))
    .attr("stroke-width",i=>K.id[i]===state.sel?2.6:1.6).style("cursor","pointer")
    .on("mousemove",(e,i)=>showTip(tipFor(i)+`<br><span>${t("default {a} → now {b}",{a:R0.rank[i],b:R.rank[i]||"-"})}</span>`,e)).on("mouseleave",hideTip).on("click",(e,i)=>select(K.id[i]));
  const lab=(items,ym,anchor,x)=>svg.append("g").selectAll("text").data(items).join("text").attr("x",x).attr("y",i=>ym.get(i)+4).attr("text-anchor",anchor)
    .attr("fill",i=>K.id[i]===state.sel?css("--ink"):css("--ink2")).attr("font-size",11.5)
    .text(i=>{const r=anchor==="end"?R0.rank[i]:R.rank[i];const nm=K.name[i].length>26?K.name[i].slice(0,25)+"…":K.name[i];return anchor==="end"?`${nm}  ${r||"-"}`:`${r||"-"}  ${nm}`});
  lab(left,yl,"end",x0-8);lab(right,yr,"start",x1+8);
  svg.append("g").selectAll("circle").data(ids).join("circle").attr("cx",x0).attr("cy",i=>yl.get(i)).attr("r",3).attr("fill",css("--ink2"));
  svg.append("g").selectAll("circle").data(ids).join("circle").attr("cx",x1).attr("cy",i=>yr.get(i)).attr("r",3).attr("fill",css("--ink2"));
}

// ---------------------------------------------------------------- profile
const profCache={};
function profData(id){if(profCache[id]!==undefined)return profCache[id];const el=document.getElementById("prof-"+id);return profCache[id]=el?JSON.parse(el.textContent):null}
function fillPick(){
  const sel=$("#p-pick");sel.innerHTML='<option value="" disabled>'+esc(t("No profile for the selected KHG"))+'</option>';
  const grp=(label,ids)=>{if(!ids.length)return;const og=document.createElement("optgroup");og.label=label;ids.forEach(i=>{const o=document.createElement("option");o.value=K.id[i];o.textContent=K.name[i]+(K.team[i]?" ◆":"");og.appendChild(o)});sel.appendChild(og)};
  const withProf=[];for(let i=0;i<N;i++)if(K.has[i])withProf.push(i);
  const team=withProf.filter(i=>K.team[i]),rest=withProf.filter(i=>!K.team[i]).sort((a,b)=>(K.ref_rank[a]||1e9)-(K.ref_rank[b]||1e9));
  grp(t("Team KHG"),team.sort((a,b)=>(K.ref_rank[a]||1e9)-(K.ref_rank[b]||1e9)));grp(t("Top at default weights"),rest);
  sel.onchange=()=>select(sel.value);
  const i0=K.id.indexOf(state.sel);sel.value=i0>=0&&K.has[i0]?state.sel:"";
}
function select(id){state.sel=id;const i=K.id.indexOf(id);$("#p-pick").value=K.has[i]?id:"";render(true);renderProfile();history.replaceState(null,"",hashState())}
function hsTile(i,info){
  if(!info||info.hs_now==null)return [t("n/a"),t("Hotspots this year")];
  if(!onlyHigh())return [fmt(info.hs_now,0),info.rank_now?t("Hotspots this year · #{a} by density, #{b} by count",{a:info.rank_now,b:info.rank_now_n}):t("Hotspots this year")];
  const pool=[];for(let j=0;j<N;j++)if(K.ref_rank[j]!=null)pool.push(j);
  const rk=(arr)=>1+pool.filter(j=>arr[j]>arr[i]).length;
  return [fmt(K.n1hn[i],0),t("High-confidence hotspots this year · #{a} by density, #{b} by count",{a:rk(K.n1h),b:rk(K.n1hn)})];
}
function chip(tx){return `<span class="chip">${esc(tx)}</span>`}
function renderProfile(){
  const id=state.sel;if(!id)return;const i=K.id.indexOf(id),P=profData(id);
  $("#p-name").textContent=K.name[i];
  $("#p-chips").innerHTML=chip(K.prov[i])+chip(id)+(P?chip(P.info.kab):"")+(K.team[i]?chip(t("team "+K.team[i])):"")+(noCanals(i)?chip(t("no canals mapped")):"")+(P&&P.info.dmpg?chip(t("DPG villages: {n}",{n:P.info.dmpg})):"");
  const r=R.rank[i],r0=R0.rank[i],d=r&&r0?r0-r:null;
  const info=P?P.info:null;
  const tileTips=[t("Rank among the KHG that pass the filters, at your weights. The arrow is the change against the default weights."),
    t("Weighted mean of the parameters, scaled 0 to 1."),
    t("Peat area inside the KHG, from the GFW peat extent. Below it: the peat share of the KHG, and the share in the 1 km Global Peatland Map."),
    t("KLH MODIS hotspots on peat this year, medium and high confidence (high only when the filter is set). Ranks are by density (per km2 of peat) and by count."),
    t("SiTMAT loggers inside the KHG, 2026 season: share of days with the water table deeper than 0.4 m."),
    t("High: canals are mapped, there is enough fire signal and enough peat. Medium: two of the three. Low: fewer.")];
  const tiles=[
    [r?`${r}<small>${d?(d>0?"▲"+d:"▼"+(-d)):""}</small>`:t("n/a"),t("Rank of {n}",{n:R.order.length})+(r0?t(" · default {r}",{r:r0}):"")],
    [isFinite(R.score[i])?fx(R.score[i],2):t("n/a"),t("Score")],
    [`${fmt(K.peat[i],0)}<small>km2</small>`,info&&info.peat_gfw!=null?t("Peat: {a}% of KHG (1 km map {b})",{a:Math.round(info.peat_gfw*100),b:info.peat_gpm!=null?Math.round(info.peat_gpm*100)+"%":t("n/a")}):t("Peat area")],
    hsTile(i,info),
    [info&&info.tma_n?`${Math.round(info.tma_deep*100)}<small>${t("% of days")}</small>`:t("none"),info&&info.tma_n?t("Water table below 0.4 m ({n} stations)",{n:info.tma_n}):t("Water table stations")],
    [`${confChar[K.conf[i]]}<small>${t(confName[K.conf[i]])}</small>`,t("Data confidence")]];
  if(P&&P.ov){const fo=P.ov.s.forest||[],pt=d3.sum(fo,x=>x[2]),la=(P.ov.s.licence_any||[[0,0,0]])[0][2],ln=(P.ov.s.licence_any||[[0,0,0,0,0,0]])[0][5]||0;
    tiles.push([`${pt?Math.round(100*la/pt):0}<small>%</small>`,t("Peat under a licence")+(la?t(" · {n} km2 on protected function",{n:fmt(ln,0)}):"")]);
    tileTips.push(t("Share of the KHG's peat inside any business licence of the 2025 layer. Overlapping licences count once. Below it: licensed area that lies on protected peat function."))}
  $("#p-kpis").innerHTML=tiles.map((tl,j)=>`<div class="kpi"${tipAttr(tileTips[j])}><div class="v">${tl[0]}</div><div class="l">${tl[1]}</div></div>`).join("");
  renderStrips(i);
  $("#p-ov-panel").innerHTML="";
  const charts=$("#p-charts");charts.innerHTML="";
  if(!P){charts.innerHTML=`<p class="hint">${t("No detailed profile for this KHG. The profiles cover the top {n} at default weights and the team KHG.",{n:META.top_n})}</p>`;drawMap(null);$("#p-table").innerHTML="";return}
  const mk=(title,tip,wide)=>{const d=document.createElement("div");d.className="ch"+(wide?" wide":"");d.innerHTML=`<h3 class="hasTip"${tipAttr(t(tip))}>${t(title)}</h3><div></div>`;charts.appendChild(d);return d.lastChild};
  lineChart(mk("Burned, % of peat per year","Burnt-area polygons, 2015 to 2026: the share of the KHG's peat burned in each year. 2026 is a partial year, drawn dashed."),{data:P.burned,color:"--hist",partial:2026,unit:"%",nd:1,ticks:[2015,2020,2025]});
  lineChart(mk("Hotspots on peat per year, VIIRS","FIRMS VIIRS S-NPP vegetation-fire hotspots that fall on peat, nominal and high confidence, per year."),{data:P.hs,color:"--hist",unit:"",nd:0,ticks:[2012,2016,2020,2024]});
  lineChart(mk("Hotspots this year by month, KLH","KLH MODIS hotspots on peat in each month of this year, medium and high confidence (high only when the filter is set).",true),{data:onlyHigh()?P.now_m.map(m=>[m[0],P.lay.now.filter(p=>p[2]===m[0]&&p[3]&&p[4]).length]):P.now_m.map(m=>[m[0],m[1]]),color:"--now",unit:"",nd:0,ticks:[1,3,5,7,9],tickFmt:m=>mon(m),xdom:[1,9]});
  lineChart(mk("Dry-season water deficit, mm","TerraClimate climatic water deficit summed over the dry months (June to October), in mm. About 4 km resolution, 2015 to 2021. Shown for context, not scored."),{data:P.deficit,color:"--ink2",unit:" mm",nd:0,ticks:[2015,2018,2021]});
  lineChart(mk("Rain June to October, mm","TerraClimate rainfall in the dry months, in mm. About 4 km resolution, 2015 to 2021. Shown for context, not scored."),{data:P.rain,color:"--ink2",unit:" mm",nd:0,ticks:[2015,2018,2021]});
  landBar(mk("Land cover","ESA WorldCover classes sampled at 250 m. Open land is grass, shrub, crop, built and bare. Shown for context, not scored.",true),P.lc);
  renderOv(P);
  drawMap(P);
  renderDataTable(P);
  if(P.ov)$("#p-table").insertAdjacentHTML("beforeend",ovTable(P));
}
function renderDataTable(P){
  const yrs=[...new Set([...P.burned.map(d=>d[0]),...P.hs.map(d=>d[0]),...P.deficit.map(d=>d[0])])].sort();
  const get=(a,y)=>{const f=a.find(d=>d[0]===y);return f?f[1]:""};
  $("#p-table").innerHTML=`<table><thead><tr><th>${t("Year")}</th><th></th><th></th><th${tipAttr(t("Burnt-area polygons. Share of the KHG's peat burned in the year, in %."))}>${t("Burned % of peat")}</th><th${tipAttr(t("FIRMS VIIRS S-NPP hotspots on peat, count."))}>${t("Hotspots VIIRS")}</th><th${tipAttr(t("TerraClimate dry-season water deficit, mm."))}>${t("Deficit mm")}</th><th${tipAttr(t("TerraClimate rainfall June to October, mm."))}>${t("Rain Jun-Oct mm")}</th></tr></thead><tbody>${yrs.map(y=>`<tr><td>${y}</td><td></td><td></td><td>${get(P.burned,y)}</td><td>${get(P.hs,y)}</td><td>${get(P.deficit,y)}</td><td>${get(P.rain,y)}</td></tr>`).join("")}</tbody></table>
  <table style="margin-top:10px"><thead><tr><th>${t("Month 2026")}</th><th></th><th></th><th${tipAttr(t("KLH MODIS hotspots on peat, medium and high confidence, count."))}>${t("On peat")}</th><th${tipAttr(t("The same hotspots anywhere in the KHG, count."))}>${t("In KHG")}</th></tr></thead><tbody>${P.now_m.map(m=>`<tr><td>${mon(m[0])}</td><td></td><td></td><td>${m[1]}</td><td>${m[2]}</td></tr>`).join("")}</tbody></table>`;
}

// strip plots: where this KHG sits among the ranked KHG, per parameter
function renderStrips(i){
  const host=$("#p-strips");host.innerHTML="";
  PR.forEach((p,k)=>{
    const vals=[];for(let j=0;j<N;j++)if(R.elig[j]){const v=val(k,j);if(v!=null&&isFinite(v))vals.push(v)}
    vals.sort(d3.ascending);const v=val(k,i);
    const row=document.createElement("div");row.className="strip";
    const w0=state.w[k];
    row.innerHTML=`<span class="t hasTip"${tipAttr(paramTip(p))}>${t(p.label)}<b>w ${fmt(w0,1)}</b></span><svg${tipAttr(t("Grey bars: how the ranked KHG are spread on this parameter. The marker is this KHG."))}></svg><span class="n"></span>`;host.appendChild(row);
    const svg=d3.select(row.querySelector("svg"));const W=row.querySelector("svg").clientWidth||240;svg.attr("viewBox",`0 0 ${W} 22`);
    if(vals.length<2){row.querySelector(".n").textContent=t("n/a");return}
    const lo=d3.quantileSorted(vals,.02),hi=d3.quantileSorted(vals,.98),x=d3.scaleLinear([lo,Math.max(hi,lo+1e-9)],[4,W-4]).clamp(true);
    const bins=d3.bin().domain(x.domain()).thresholds(28)(vals.map(a=>Math.min(Math.max(a,lo),hi)));const mx=d3.max(bins,b=>b.length);
    svg.append("g").selectAll("rect").data(bins).join("rect").attr("x",b=>x(b.x0)).attr("width",b=>Math.max(1,x(b.x1)-x(b.x0)-1)).attr("y",b=>20-18*Math.sqrt(b.length/mx)).attr("height",b=>18*Math.sqrt(b.length/mx)).attr("fill",css("--axis")).attr("opacity",.7);
    svg.append("line").attr("x1",4).attr("x2",W-4).attr("y1",20.5).attr("y2",20.5).attr("stroke",css("--axis"));
    const n=row.querySelector(".n");
    if(v==null||!isFinite(v)){n.innerHTML=`<small>${t("not mapped")}</small>`;n.dataset.tip=t("No canal of this class is mapped in the layer for this KHG.");return}
    const pct=Math.round(100*d3.bisectLeft(vals,v)/vals.length);
    svg.append("line").attr("x1",x(v)).attr("x2",x(v)).attr("y1",2).attr("y2",20).attr("stroke",`var(${GROUPS[p.group].css})`).attr("stroke-width",2);
    svg.append("circle").attr("cx",x(v)).attr("cy",4).attr("r",4.5).attr("fill",`var(${GROUPS[p.group].css})`).attr("stroke",css("--surface")).attr("stroke-width",2);
    n.innerHTML=`${fmt(v,v<10?2:1)} <small>p${pct}</small>`;n.dataset.tip=`<b>${esc(t(p.label))}</b><br>${fmt(v,3)} <span>${esc(t(p.unit))}</span><br><span>${t("p{pct}: higher than {pct}% of the ranked KHG.",{pct})}</span>`;
  });
}

// line chart: thin line, hairline grid, end marker, hover crosshair
function lineChart(host,o){
  const W=host.clientWidth||300,H=128,m={l:34,r:14,t:8,b:20};host.innerHTML="";
  if(!o.data||!o.data.length){host.innerHTML=`<p class="hint">${t("No data")}</p>`;return}
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${H}`).attr("height",H);
  const xs=o.data.map(d=>d[0]),x=d3.scaleLinear(o.xdom||[d3.min(xs),d3.max(xs)],[m.l,W-m.r]);
  const ymax=d3.max(o.data,d=>d[1])||1,y=d3.scaleLinear([0,ymax*1.08],[H-m.b,m.t]).nice(3);
  const col=css(o.color);
  svg.append("g").attr("class","gridl").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickSize(-(W-m.l-m.r)).tickFormat(""));
  svg.append("g").attr("class","axis").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickSize(0).tickPadding(6).tickFormat(v=>fmt(v,v<10&&v%1?1:0)));
  svg.select(".axis path").remove();
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(o.ticks||x.ticks(4)).tickFormat(o.tickFmt||d3.format("d")).tickSize(3));
  const full=o.partial?o.data.filter(d=>d[0]<o.partial):o.data;
  const line=d3.line().x(d=>x(d[0])).y(d=>y(d[1]));
  svg.append("path").datum(full).attr("d",d3.area().x(d=>x(d[0])).y0(y(0)).y1(d=>y(d[1]))).attr("fill",col).attr("opacity",.1);
  svg.append("path").datum(full).attr("d",line).attr("fill","none").attr("stroke",col).attr("stroke-width",2).attr("stroke-linejoin","round").attr("stroke-linecap","round");
  if(o.partial){const pi=o.data.findIndex(d=>d[0]===o.partial);if(pi>0){svg.append("path").datum([o.data[pi-1],o.data[pi]]).attr("d",line).attr("fill","none").attr("stroke",col).attr("stroke-width",2).attr("stroke-dasharray","3 3")}
    const pd=o.data[pi];if(pd)svg.append("circle").attr("cx",x(pd[0])).attr("cy",y(pd[1])).attr("r",4).attr("fill",css("--surface")).attr("stroke",col).attr("stroke-width",2)}
  const last=full[full.length-1];
  svg.append("circle").attr("cx",x(last[0])).attr("cy",y(last[1])).attr("r",4).attr("fill",col).attr("stroke",css("--surface")).attr("stroke-width",2);
  const mx=d3.maxIndex(o.data,d=>d[1]),pk=o.data[mx];
  if(pk&&pk[1]>0)svg.append("text").attr("x",Math.min(W-m.r-2,Math.max(m.l+2,x(pk[0]))) ).attr("y",y(pk[1])-5).attr("text-anchor",x(pk[0])>W-60?"end":x(pk[0])<m.l+30?"start":"middle").attr("fill",css("--ink2")).attr("font-size",11).text(fmt(pk[1],o.nd)+o.unit);
  const dot=svg.append("circle").attr("r",4.5).attr("fill",col).attr("stroke",css("--surface")).attr("stroke-width",2).style("display","none");
  const step=(W-m.l-m.r)/Math.max(1,o.data.length-1);
  svg.append("g").selectAll("rect").data(o.data).join("rect").attr("x",d=>x(d[0])-step/2).attr("width",step).attr("y",m.t).attr("height",H-m.t-m.b).attr("fill","transparent")
    .on("mousemove",(e,d)=>{dot.style("display",null).attr("cx",x(d[0])).attr("cy",y(d[1]));showTip(`<b>${o.tickFmt?o.tickFmt(d[0]):d[0]}${o.partial&&d[0]===o.partial?" "+t("(partial year)"):""}</b><br>${fmt(d[1],o.nd)}${o.unit}`,e)})
    .on("mouseleave",()=>{dot.style("display","none");hideTip()});
}
function landBar(host,lc){
  const W=host.clientWidth||300,H=26;host.innerHTML="";if(!lc||!lc.length){host.innerHTML=`<p class="hint">${t("No data")}</p>`;return}
  const bucket={Tree:"Tree",Wetland:"Wetland, water",Water:"Wetland, water",Mangrove:"Wetland, water"};
  const cols={"Tree":"#008300","Open land":isDark()?"#c98500":"#eda100","Wetland, water":isDark()?"#9085e9":"#6250d6"};
  const agg={};lc.forEach(([n,v])=>{const b=bucket[n]||"Open land";agg[b]=(agg[b]||0)+v});
  const items=["Tree","Open land","Wetland, water"].map(n=>({n,v:agg[n]||0})).filter(d=>d.v>0);
  const tot=d3.sum(items,d=>d.v);let acc=0;const x=d3.scaleLinear([0,tot],[0,W]);items.forEach(d=>{d.x0=acc;acc+=d.v});
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${H}`).attr("height",H);
  svg.selectAll("rect").data(items).join("rect").attr("x",d=>x(d.x0)).attr("y",2).attr("height",22).attr("width",d=>Math.max(1,x(d.v)-2)).attr("rx",3).attr("fill",d=>cols[d.n])
    .on("mousemove",(e,d)=>showTip(`<b>${t(d.n)}</b><br>${t("{v}% of the KHG",{v:fmt(d.v,1)})}<br><span>${lc.filter(l=>(bucket[l[0]]||"Open land")===d.n).map(l=>t(l[0])+" "+fmt(l[1],0)+"%").join(", ")}</span>`,e)).on("mouseleave",hideTip);
  const lg=document.createElement("div");lg.className="legend-row";lg.style.marginTop="6px";
  lg.innerHTML=items.map(d=>`<span><span class="sw" style="background:${cols[d.n]}"></span>${t(d.n)} ${fmt(d.v,0)}%</span>`).join("");host.appendChild(lg);
}

// map of one KHG: burn counts, canals by class, this year's hotspot points, on the basemap
let pmap=null,pReady=false,pPending=undefined;
const pLayers={peat:true,burn:true,p:true,s:true,t:true,now:true};
const EMPTY={type:"FeatureCollection",features:[]};
const pOv={mode:"off",vil:false};
const OVCLS={
  forest:[["cons","Conservation"],["hl","Protection forest"],["prod","Production forest"],["hpk","Convertible production"],["apl","Other land use"],["other","Water, undefined"],["none","Not mapped"]],
  feg:[["lindung","Protected function"],["budidaya","Cultivation function"],["none","Not mapped"]],
  licence:[["sawit","Oil palm"],["pbph","Forest concession (PBPH)"],["pphkm","Community forest (PPHKM)"],["pphtr","Plantation forest (PPHTR)"],["tambang","Mining"],["none","No licence"]],
  village:[["in","Target village"],["out","Outside target villages"]],
  dmpg:[["in","DPG village (BRG atlas)"],["out","Outside DPG villages"]],
  ring:[["lic","In a licence"],["ring","Within 5 km of a licence"],["out","Farther from licences"]]};
function ovColor(layer,c){
  const d=isDark(),v=d?"#9085e9":"#6250d6",g="#008300",y=d?"#c98500":"#eda100",m=d?"#d55181":"#e87ba4",r=d?"#e66767":"#e34948",n=d?"#4a4a46":"#c9c8c0",b=d?"#5b7080":"#9fb3c1";
  const map={forest:{cons:v,hl:g,prod:y,hpk:m,apl:n,other:b,none:n},feg:{lindung:g,budidaya:y,none:n},licence:{sawit:y,pbph:g,pphkm:m,pphtr:v,tambang:r,none:n},village:{in:v,out:n},dmpg:{in:v,out:n},ring:{lic:y,ring:m,out:n}};
  return (map[layer]||{})[c]||n}
const ovMatch=layer=>["match",["get","c"],...OVCLS[layer].flatMap(([c])=>[c,ovColor(layer,c)]),ovColor(layer,"none")];
const ovTip={off:"Hide the land-status layers.",forest:"Forest area function 2023 (Kawasan Hutan, 1:250,000).",feg:"Peat ecosystem function 2017 (FEG): protected or cultivation.",licence:"Business licences, 2025 update. Hover for the holder.",ring:"Licences and the land within 5 km of one but inside none: the zone the Bluebook 2026 calls Buffer 5 Kilometer."};
function pTheme(){
  if(!pmap||!pReady)return;
  const ramp=d3.interpolateRgb(css("--ramp0"),css("--ramp1")),on=css("--now"),sf=css("--surface");
  pmap.setPaintProperty("p-burn","fill-color",["match",["get","n"],1,ramp(.25),2,ramp(.5),3,ramp(.75),ramp(1)]);
  for(const id of ["p-canal-p","p-canal-s","p-canal-t"])pmap.setPaintProperty(id,"line-color",css("--canal"));
  pmap.setPaintProperty("p-outline","line-color",css("--ink"));pmap.setPaintProperty("p-peat","fill-color",css("--peat"));
  pmap.setPaintProperty("p-ov-forest","fill-color",ovMatch("forest"));pmap.setPaintProperty("p-ov-feg","fill-color",ovMatch("feg"));
  pmap.setPaintProperty("p-ov-lic","fill-color",ovMatch("licence"));pmap.setPaintProperty("p-ov-ring","fill-color",ovMatch("ring"));pmap.setPaintProperty("p-ov-lic-line","line-color",ovMatch("licence"));
  pmap.setPaintProperty("p-ov-vil","line-color",ovColor("village","in"));pmap.setPaintProperty("p-ov-vil-f","fill-color",ovColor("dmpg","in"));
  for(const id of ["p-now-h","p-now-m"]){pmap.setPaintProperty(id,"circle-color",["case",["==",["get","p"],1],on,"rgba(0,0,0,0)"]);pmap.setPaintProperty(id,"circle-stroke-color",["case",["==",["get","p"],1],sf,on]);pmap.setPaintProperty(id,"circle-stroke-width",["case",["==",["get","p"],1],.8,1.4])}
}
function initProfileMap(){
  try{pmap=newMap("p-map",{center:[110,-1],zoom:5})}catch(e){$("#p-map").innerHTML='<p class="hint" style="padding:12px">'+t("The map needs WebGL.")+'</p>';return}
  pmap.on("load",()=>{
    const before=firstSymbol(pmap);
    for(const s of ["p-burn","p-outline","p-canal-t","p-canal-s","p-canal-p","p-now"])pmap.addSource(s,{type:"geojson",data:EMPTY});
    pmap.addSource("p-peat",{type:"geojson",data:EMPTY});
    pmap.addLayer({id:"p-peat",type:"fill",source:"p-peat",paint:{"fill-color":"#a58660","fill-opacity":.38}},before);
    for(const s of ["p-ov-forest","p-ov-feg","p-ov-lic","p-ov-vil","p-ov-ring"])pmap.addSource(s,{type:"geojson",data:EMPTY});
    const fillOv=(id,src,op)=>pmap.addLayer({id,type:"fill",source:src,layout:{visibility:"none"},paint:{"fill-color":"#888","fill-opacity":op}},before);
    fillOv("p-ov-forest","p-ov-forest",.55);fillOv("p-ov-feg","p-ov-feg",.55);fillOv("p-ov-lic","p-ov-lic",.38);fillOv("p-ov-ring","p-ov-ring",.45);
    pmap.addLayer({id:"p-ov-lic-line",type:"line",source:"p-ov-lic",layout:{visibility:"none"},paint:{"line-color":"#888","line-width":1.3}},before);
    fillOv("p-ov-vil-f","p-ov-vil",["case",["==",["get","d"],1],.3,.02]);
    pmap.addLayer({id:"p-ov-vil",type:"line",source:"p-ov-vil",filter:["!=",["get","x"],1],layout:{visibility:"none"},paint:{"line-color":"#6250d6","line-width":1.6,"line-dasharray":[3,2]}},before);
    pmap.addLayer({id:"p-burn",type:"fill",source:"p-burn",paint:{"fill-color":"#2a78d6","fill-opacity":.85}},before);
    const w=(a,b)=>["interpolate",["linear"],["zoom"],7,a,14,b];
    pmap.addLayer({id:"p-canal-t",type:"line",source:"p-canal-t",layout:{"line-join":"round"},paint:{"line-color":"#1baf7a","line-width":w(.3,1),"line-opacity":.55}},before);
    pmap.addLayer({id:"p-canal-s",type:"line",source:"p-canal-s",layout:{"line-join":"round"},paint:{"line-color":"#1baf7a","line-width":w(.6,1.8),"line-opacity":.85}},before);
    pmap.addLayer({id:"p-canal-p",type:"line",source:"p-canal-p",layout:{"line-join":"round"},paint:{"line-color":"#1baf7a","line-width":w(1,3)}},before);
    pmap.addLayer({id:"p-outline",type:"line",source:"p-outline",paint:{"line-color":"#000","line-width":1.6}},before);
    pmap.addLayer({id:"p-now-m",type:"circle",source:"p-now",filter:["==",["get","h"],0],paint:{"circle-radius":w(2,4.5),"circle-color":"#eb6834","circle-stroke-color":"#fff","circle-stroke-width":.8}});
    pmap.addLayer({id:"p-now-h",type:"circle",source:"p-now",filter:["==",["get","h"],1],paint:{"circle-radius":w(3,6.5),"circle-color":"#eb6834","circle-stroke-color":"#fff","circle-stroke-width":.8}});
    for(const id of ["p-now-m","p-now-h"]){
      pmap.on("mousemove",id,e=>{const f=e.features[0];if(f){pmap.getCanvas().style.cursor="pointer";showTip(`<b>${t("Hotspot, {m}",{m:monf(f.properties.m)})}</b><br><span>${t("{c} confidence · {p}",{c:t(f.properties.h?"high":"medium"),p:t(f.properties.p?"on peat":"off peat")})}</span>`,e.originalEvent)}});
      pmap.on("mouseleave",id,()=>{pmap.getCanvas().style.cursor="";hideTip()})}
    const ovHover=(id,f)=>{pmap.on("mousemove",id,e=>{if(pmap.queryRenderedFeatures(e.point,{layers:["p-now-m","p-now-h"]}).length)return;const x=e.features[0];if(x)showTip(f(x.properties),e.originalEvent)});pmap.on("mouseleave",id,hideTip)};
    const lab=(layer,c)=>t((OVCLS[layer].find(a=>a[0]===c)||[0,""])[1]);
    ovHover("p-ov-forest",p=>`<b>${lab("forest",p.c)}</b>`);ovHover("p-ov-feg",p=>`<b>${lab("feg",p.c)}</b>`);ovHover("p-ov-ring",p=>`<b>${lab("ring",p.c)}</b>`);
    ovHover("p-ov-lic",p=>`<b>${esc(p.n||lab("licence",p.c))}</b><br><span>${lab("licence",p.c)}</span>`);
    ovHover("p-ov-vil-f",p=>`<b>${esc(p.n)}</b><br><span>${t(p.x?"Not a target village":"Target village")}</span>`+(p.d?`<br><span>${t("DPG village, BRG atlas 2018-2019")}</span>`:""));
    pReady=true;pTheme();applyLayerToggles();
    if(pPending!==undefined)setProfileData(pPending);
  });
}
function applyLayerToggles(){
  if(!pmap||!pReady)return;
  const vis=(ids,on)=>ids.forEach(id=>pmap.setLayoutProperty(id,"visibility",on?"visible":"none"));
  vis(["p-peat"],pLayers.peat);vis(["p-burn"],pLayers.burn);vis(["p-canal-p"],pLayers.p);vis(["p-canal-s"],pLayers.s);vis(["p-canal-t"],pLayers.t);vis(["p-now-h"],pLayers.now);vis(["p-now-m"],pLayers.now&&!onlyHigh());
  vis(["p-ov-forest"],pOv.mode==="forest");vis(["p-ov-feg"],pOv.mode==="feg");vis(["p-ov-lic","p-ov-lic-line"],pOv.mode==="licence");vis(["p-ov-ring"],pOv.mode==="ring");vis(["p-ov-vil","p-ov-vil-f"],pOv.vil);
}
function setProfileData(P){
  const fc=f=>({type:"FeatureCollection",features:f});
  if(!P){for(const s of ["p-burn","p-outline","p-canal-t","p-canal-s","p-canal-p","p-now","p-peat","p-ov-forest","p-ov-feg","p-ov-lic","p-ov-vil","p-ov-ring"])pmap.getSource(s).setData(EMPTY);return}
  const L=P.lay,pairs=a=>{const c=[];for(let j=0;j<a.length;j+=2)c.push([a[j],a[j+1]]);return c};
  pmap.getSource("p-burn").setData(fc(L.burn.map(b=>({type:"Feature",properties:{n:b.n},geometry:{type:"MultiPolygon",coordinates:b.r}}))));
  pmap.getSource("p-outline").setData(fc([{type:"Feature",properties:{},geometry:{type:"MultiPolygon",coordinates:L.outline}}]));
  for(const [k,id] of [["t","p-canal-t"],["s","p-canal-s"],["p","p-canal-p"]])pmap.getSource(id).setData(fc(L.canals[k].map(a=>({type:"Feature",properties:{},geometry:{type:"LineString",coordinates:pairs(a)}}))));
  pmap.getSource("p-now").setData(fc(L.now.map(p=>({type:"Feature",properties:{m:p[2],h:p[3],p:p[4]},geometry:{type:"Point",coordinates:[p[0],p[1]]}}))));
  pmap.getSource("p-peat").setData(fc((L.peat&&L.peat.length)?[{type:"Feature",properties:{},geometry:{type:"MultiPolygon",coordinates:L.peat}}]:[]));
  const O=L.ov||{},poly=(arr,f)=>fc((arr||[]).map(x=>({type:"Feature",properties:f(x),geometry:{type:"MultiPolygon",coordinates:x.r}})));
  pmap.getSource("p-ov-forest").setData(poly(O.forest,x=>({c:x.c})));pmap.getSource("p-ov-feg").setData(poly(O.feg,x=>({c:x.c})));
  pmap.getSource("p-ov-lic").setData(poly(O.licence,x=>({c:x.c,n:x.n})));pmap.getSource("p-ov-ring").setData(poly(O.ring,x=>({c:x.c})));pmap.getSource("p-ov-vil").setData(poly(O.village,x=>({n:x.n,d:x.d||0,x:x.x||0})));
  const b=L.bounds;pmap.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:28,duration:0,maxZoom:14});
}
function drawMap(P){
  if(!pmap)initProfileMap();
  pPending=P;if(pmap&&pReady)setProfileData(P);
  const tools=$("#p-tools");tools.innerHTML="";
  if(P){const lb0=document.createElement("span");lb0.className="lab";lb0.textContent=t("Layers");tools.appendChild(lb0)}
  if(!P){$("#p-foot").textContent="";$("#p-ov-leg").innerHTML="";return}
  const T=[["peat","Peat extent",`<i class="poly" style="background:var(--peat)"></i>`,"Peat extent used for the rates (GFW composite, 76 m): the area that burned area and hotspots are divided by."],["burn","Burned, times",`<i class="poly" style="background:var(--hist)"></i>`,"Burnt-area polygons by number of burns, 2015 to 2025. Darker means burned more often."],["p","Primary canals",`<i style="background:var(--canal);height:4px"></i>`,"Primary canals (Kanal Primer) from the OSM-based layer."],["s","Secondary",`<i style="background:var(--canal);height:2px"></i>`,"Secondary canals (Kanal Sekunder)."],["t","Tertiary",`<i style="background:var(--canal);height:1px;opacity:.6"></i>`,"Tertiary canals (Kanal Tersier)."],["now","Hotspots this year ({n})",`<i class="dot" style="background:var(--now)"></i>`,"KLH MODIS hotspots this year. Filled: on peat. Hollow: off peat. Large: high confidence."]];
  T.forEach(([k,tx,ic,tp])=>{const s=document.createElement("span");s.className="tg"+(pLayers[k]?"":" off");s.innerHTML=ic+t(tx,{n:P.lay.now_total||P.lay.now.length});s.dataset.tip=t(tp);s.onclick=()=>{pLayers[k]=!pLayers[k];s.classList.toggle("off",!pLayers[k]);applyLayerToggles()};tools.appendChild(s)});
  if(P.lay.ov){
    const grp=document.createElement("span");grp.className="tgrp";tools.appendChild(grp);const lb=document.createElement("span");lb.className="lab";lb.textContent=t("Land status");grp.appendChild(lb);
    const seg=document.createElement("span");seg.className="seg";
    [["off","Off"],["forest","Forest area"],["feg","Peat function"],["licence","Licences"],["ring","5 km ring"]].forEach(([k,l])=>{const b=document.createElement("button");b.type="button";b.textContent=t(l);b.dataset.tip=t(ovTip[k]);b.className=pOv.mode===k?"on":"";
      b.onclick=()=>{pOv.mode=k;[...seg.children].forEach(x=>x.classList.toggle("on",x===b));applyLayerToggles();ovLegend(P)};seg.appendChild(b)});
    grp.appendChild(seg);
    const v=document.createElement("span");v.className="tg"+(pOv.vil?"":" off");v.innerHTML=`<i style="border-top:2px dashed ${ovColor("village","in")};height:0;background:none"></i>`+t("Target villages");v.dataset.tip=t("Target villages of the 2026 Bluebook for peat ecosystem restoration. Filled: DPG village in the BRG atlas, 2018-2019. Hover for the village.");
    v.onclick=()=>{pOv.vil=!pOv.vil;v.classList.toggle("off",!pOv.vil);applyLayerToggles()};grp.appendChild(v);
  }
  ovLegend(P);
  $("#p-foot").innerHTML=t("Filled dot: on peat. Hollow: off peat. Large: high confidence.")+(P.lay.now_total>P.lay.now.length?" "+t("Showing {a} of {b} points.",{a:P.lay.now.length,b:P.lay.now_total}):"")+" "+t("Basemap needs internet.");
}
function ovLegend(P){
  const host=$("#p-ov-leg");host.innerHTML="";if(!P||!P.lay.ov)return;
  const items=[];
  if(pOv.mode!=="off"){const layer=pOv.mode,present=new Set((P.lay.ov[layer]||[]).map(x=>x.c));OVCLS[layer].filter(([c])=>present.has(c)).forEach(([c,l])=>items.push(`<span><span class="sw" style="background:${ovColor(layer,c)}"></span>${t(l)}</span>`))}
  host.innerHTML=items.join("");
}
function ovSeg(layer,rows,tot){
  const mk=(k)=>{const v=rows.map(r=>r.v[k]),den=Math.max(tot[k],d3.sum(v))||1;
    return v.map((x,j)=>x>0?`<i style="width:${100*x/den}%;background:${ovColor(layer,rows[j].c)}"${tipAttr(`<b>${t(rows[j].l)}</b><br>${fmt(x,k===2?0:1)}${k===2?"":" km2"} <span>(${fmt(100*x/(tot[k]||1),0)}% ${t(["of the peat","of the burned peat","of the hotspots"][k])})</span>`)}></i>`:"").join("")};
  return [0,1,2].map(k=>mk(k))}
function renderOv(P){
  const host=$("#p-ov-panel");host.innerHTML="";if(!P||!P.ov)return;
  const S=P.ov.s,fo=S.forest||[],tot=[d3.sum(fo,r=>r[2]),d3.sum(fo,r=>r[3]),d3.sum(fo,r=>r[4])];
  const val=(layer,c)=>{const r=(S[layer]||[]).find(x=>x[0]===c);return r?[r[2],r[3],r[4]]:[0,0,0]};
  const mkRows=(layer,codes)=>codes.map(c=>({c,l:(OVCLS[layer].find(a=>a[0]===c)||[0,c])[1],v:val(layer,c)}));
  const groups=[];
  groups.push({layer:"forest",title:"Forest area function",tip:"Forest area function 2023 (Kawasan Hutan, 1:250,000). Bars: the share of the KHG's peat, of the peat burned in 2015 to 2025, and of this year's hotspots on peat.",rows:mkRows("forest",OVCLS.forest.map(a=>a[0]))});
  groups.push({layer:"feg",title:"Peat function",tip:"Peat ecosystem function 2017, revised typology: indicative protected (Lindung) or cultivation (Budidaya). Same three measures.",rows:mkRows("feg",OVCLS.feg.map(a=>a[0]))});
  const lic=OVCLS.licence.slice(0,5).map(([c,l])=>({c,l,v:(S["licence_"+c]||[[0,0,0,0,0]])[0].slice(2,5)}));
  const any=(S.licence_any||[[0,0,0,0,0]])[0].slice(2,5);
  lic.push({c:"none",l:"No licence",v:tot.map((x,k)=>Math.max(0,x-any[k]))});
  groups.push({layer:"licence",title:"Licences",tip:"Business licences, 2025 update. Licences overlap, so the segments can add up to more than the peat; the grey segment is peat with no licence.",rows:lic});
  groups.push({layer:"ring",title:"5 km ring",tip:"Peat in a licence, within 5 km of one but inside none, or farther. The three classes add up. Licences outside the KHG count when their ring reaches into it.",rows:mkRows("ring",OVCLS.ring.map(a=>a[0]))});
  groups.push({layer:"village",title:"Target villages",tip:"Village areas targeted for peat restoration in the 2026 Bluebook.",rows:[{c:"in",l:"Target village",v:val("village","in")},{c:"out",l:"Outside target villages",v:tot.map((x,k)=>Math.max(0,x-val("village","in")[k]))}]});
  groups.push({layer:"dmpg",title:"DPG villages",tip:"Desa Peduli Gambut villages mapped in 2018-2019 in the BRG atlas and matched by name to village boundaries (KLH 2023, BIG 2026). Only part of all DPG and DMPG villages. Context, not scored.",rows:[{c:"in",l:"DPG village (BRG atlas)",v:val("dmpg","in")},{c:"out",l:"Outside DPG villages",v:tot.map((x,k)=>Math.max(0,x-val("dmpg","in")[k]))}]});
  const rowLab=[["Peat area","Peat area in each class, from the GFW peat extent."],["Burned peat","Peat that burned at least once in 2015 to 2025 (burnt-area polygons)."],["Hotspots this year","KLH MODIS hotspots on peat this year, medium and high confidence."]];
  const totTxt=[fmt(tot[0],0)+" km2",fmt(tot[1],0)+" km2",fmt(tot[2],0)];
  let html=`<div class="ovhead"><h3 class="hasTip"${tipAttr(t("Where the peat, the burned peat and this year's hotspots fall on each land-status layer. A segment wider in the lower bars than in the top bar means fire is over-represented in that class."))}>${t("Land status of the peat")}</h3></div><div class="ovgrid">`;
  groups.forEach(g=>{
    const rows=g.rows.filter(r=>(r.v[0]>=.002*tot[0]||r.v[1]>0||r.v[2]>0)&&r.v[0]+r.v[1]+r.v[2]>0);if(!rows.length)return;
    const bars=ovSeg(g.layer,rows,tot);
    html+=`<div class="ovg"><div class="ovt hasTip"${tipAttr(t(g.tip))}>${t(g.title)}</div><div class="ovleg">${rows.map(r=>`<span><span class="sw" style="background:${ovColor(g.layer,r.c)}"></span>${t(r.l)}${tot[0]?` <small>${fmt(100*r.v[0]/tot[0],0)}%</small>`:""}</span>`).join("")}</div>`+
      [0,1,2].map(k=>`<div class="ovrow"><span class="ovl hasTip"${tipAttr(t(rowLab[k][1]))}>${t(rowLab[k][0])}</span><div class="ovbar">${bars[k]}</div><span class="ovv">${totTxt[k]}</span></div>`).join("")+`</div>`});
  html+="</div>";
  const A=P.ov.a;
  html+=`<div class="ovact"><div class="ovt hasTip"${tipAttr(t("Licence holders with a licence or a 5 km ring in this KHG, sorted by hotspots this year in the licence and its ring. Overlapping licences of one holder count once."))}>${t("Licence holders")}</div>`;
  if(!A.length)html+=`<p class="hint">${t("No licence of the 2025 layer overlaps this KHG.")}</p>`;
  else{const mx=d3.max(A,a=>Math.max(a[4],a[7]||0))||1,bar=v=>`background:linear-gradient(90deg,var(--wash) ${100*v/mx}%,transparent ${100*v/mx}%)`;
    html+=`<div class="tablewrap" style="max-height:none"><table><thead><tr><th${tipAttr(t("Holder named in the licence layer."))}>${t("Holder")}</th><th${tipAttr(t("Licence type."))}>${t("Type")}</th><th${tipAttr(t("Licence area inside the KHG, km2."))}>${t("Area km2")}</th><th${tipAttr(t("Part of that area on protected peat function (FEG Lindung), km2."))}>${t("On protected km2")}</th><th${tipAttr(t("Peat inside the licence that burned at least once in 2015 to 2025, km2."))}>${t("Burned peat km2")}</th><th${tipAttr(t("KLH hotspots on peat this year inside the licence area."))}>${t("Hotspots")}</th><th${tipAttr(t("Peat within 5 km of the holder's licences but inside no licence that burned at least once in 2015 to 2025, km2. Only the part inside the KHG."))}>${t("Ring burned peat km2")}</th><th${tipAttr(t("KLH hotspots on peat this year within 5 km of the holder's licences but inside no licence. Rings of neighbouring holders overlap."))}>${t("Ring hotspots")}</th></tr></thead><tbody>`+
      A.map(a=>`<tr><td style="text-align:left;max-width:200px;overflow:hidden;text-overflow:ellipsis" title="${esc(a[0])}">${esc(a[0])}</td><td style="text-align:left">${esc(t(a[1]))}</td><td>${fmt(a[2],1)}</td><td>${fmt(a[5],1)}</td><td>${fmt(a[3],1)}</td><td style="${bar(a[4])}">${fmt(a[4],0)}</td><td>${a[6]==null?"":fmt(a[6],1)}</td><td style="${bar(a[7]||0)}">${fmt(a[7]||0,0)}</td></tr>`).join("")+`</tbody></table></div><p class="hint">${t("Hotspots inside each licence area and its 5 km ring, year to date. This shows where fires burn, not who started them.")}</p>`}
  html+="</div>";
  host.innerHTML=html;
}
function ovTable(P){
  const names={forest:"Forest area function",feg:"Peat function",village:"Target villages",dmpg:"DPG villages",ring:"5 km ring"};
  let rows="";
  for(const [layer,arr] of Object.entries(P.ov.s)){
    const base=layer.startsWith("licence_")?"licence":layer,lb=layer==="licence_any"?t("Any licence"):null;
    arr.forEach(r=>{const l=lb||t((OVCLS[base].find(a=>a[0]===r[0])||[0,r[0]])[1]);
      rows+=`<tr><td style="text-align:left">${t(names[layer]||"Licences")}</td><td style="text-align:left">${esc(l)}</td><td>${fmt(r[1],1)}</td><td>${fmt(r[2],1)}</td><td>${fmt(r[3],1)}</td><td>${fmt(r[4],0)}</td></tr>`})}
  return `<table style="margin-top:10px"><thead><tr><th style="text-align:left">${t("Layer")}</th><th style="text-align:left">${t("Class")}</th><th>${t("Area km2")}</th><th>${t("Peat km2")}</th><th>${t("Burned peat km2")}</th><th>${t("Hotspots")}</th></tr></thead><tbody>${rows}</tbody></table>`}
function themeMaps(){
  for(const m of [nat,pmap])if(m&&m.isStyleLoaded()){restyleBase(m)}
  pTheme();
  if(state.sel){const P=profData(state.sel);if(P&&P.ov){renderOv(P);ovLegend(P)}}
}

function staticTips(){
  const T=(el,html)=>{if(el)el.dataset.tip=t(html)};
  const presetTips={"Default":"The provisional default weights.","History":"Default weights with this year's parameters set to 0.","This year":"Only hotspots this year, weight 1. Everything else 0.","Canals":"Only the three canal parameters, at their default weights.","Equal":"Every parameter at weight 1."};
  $$("#presets button").forEach(b=>T(b,presetTips[b.dataset.p]));
  T($("#minpeat").closest(".ctl"),"Peat area of a KHG, from the GFW peat extent. KHG with less peat than this are not ranked.");
  T($("#islands"),"Rank only the KHG on the chosen islands. Each parameter is scaled using only these KHG.");
  T($("#missing"),"How a KHG with no mapped canals is scored. Ignore: its canal parameters are left out. Average: it gets the average KHG value.");
  T($("#conf"),"Confidence levels of this year's KLH hotspots that count. High only keeps the detections KLH rates Tinggi; the ranking and the profile numbers follow.");
  T($("#view"),"The top 30 at your weights, or the team's selected KHG with their rank.");
  T($("#rank-mode"),"Bars show what each group adds to the score. Table lists every parameter and can be searched and sorted.");
  T($("#map-legend"),"Score from 0 to 1. Grey: not ranked because of the filters.");
  T($("#bumpcard h2"),"Rank at the default weights on the left, at your weights on the right. Dark lines moved 3 places or more. Orange: the selected KHG.");
  T($("#zoom-btns"),"Zoom to an island.");
  T($("#reset"),"Back to the default weights and filters.");
  T($("#theme-btn"),"Switch between light and dark.");
  T($("#lang"),"Language: English or Bahasa Indonesia.");
}
// ---------------------------------------------------------------- notes, theme, language, hash
function buildNotes(){
  const pi=META.peat_by_island,v=META.validation&&META.validation.v_hotspot;
  const isl=Object.entries(pi).filter(e=>e[1][2]>=10).map(([n,a])=>t("{n} {a}% against {b}%",{n,a:Math.round(a[0]*100),b:Math.round(a[1]*100)})).join(", ");
  const items=[
    t("Each parameter is scaled from 0 to 1 between the 5th and 95th percentile of the KHG that pass the filters. The score is the weighted mean of the parameters a KHG has."),
    t("Fire is counted on peat and divided by peat area. Peat comes from the GFW extent. In the median KHG it is lower than the 1 km Global Peatland Map: {isl}.",{isl}),
    t("Hotspots 2015 to 2025 are VIIRS. Hotspots this year are KLH MODIS, 1 Jan to {date}, medium and high confidence. The sensors differ, so they are separate parameters.",{date:nowDate()}),
    t("Canals come from an OSM-based layer. A KHG with no mapped canals is scored on its other parameters, or on the average value with the switch set to Average."),
    t("KHG under {a} km2, or under the minimum peat area, are not ranked.",{a:META.min_area}),
    t("The default weights are provisional. Canal weights (0.5, 0.3, 0.2) split the single canal weight used before."),
    v?t("Scored on 2015 to 2022 without this year's hotspots, the default weights give AUC {a} against hotspots in 2023 to 2025. Fire history alone gives {b}.",{a:fx(v.auc,3),b:fx(v.auc_hist,3)}):"",
    t("Profiles cover the top {n} at default weights and the team KHG. Generated {d}.",{n:META.top_n,d:META.generated})
  ].filter(Boolean);
  $("#notes-list").innerHTML=items.map(tx=>`<li>${esc(tx)}</li>`).join("");
  $("#notes-btn").onclick=()=>$("#notes").showModal();$("#notes-close").onclick=()=>$("#notes").close();
}
function applyStatic(){
  document.documentElement.lang=LANG;
  document.title=t("Peat KHG priority");
  $$("[data-i18n]").forEach(el=>{el.textContent=t(el.dataset.i18n)});
  $$("[data-i18n-aria]").forEach(el=>{el.setAttribute("aria-label",t(el.dataset.i18nAria))});
  $("#sub").textContent=t("{n} KHG, hotspots to {date}. Move a slider and the ranking updates.",{n:META.n_khg,date:nowDate()});
}
function setLang(l){
  LANG=l==="id"?"id":"en";
  applyStatic();buildControls();fillPick();buildNotes();buildZoomButtons();buildTable();staticTips();
  mapLabels(nat);mapLabels(pmap);
  render();history.replaceState(null,"",hashState());
}
function hashState(){const w=state.w.map(x=>+x.toFixed(2)).join(",");const th=document.documentElement.dataset.theme;return `#w=${w}&p=${state.minPeat}&m=${state.missing}&v=${state.view}${th?"&t="+th:""}${LANG==="id"?"&l=id":""}${state.conf==="h"?"&c=h":""}${state.islands.size?"&i="+encodeURIComponent([...state.islands].join(",")):""}${state.sel?"&k="+encodeURIComponent(state.sel):""}`}
function readHash(){
  const h=new URLSearchParams(location.hash.slice(1));
  if(h.get("l")==="id"||h.get("l")==="en")LANG=h.get("l");else LANG=(navigator.language||"").toLowerCase().startsWith("id")?"id":"en";
  if(h.get("w")){const a=h.get("w").split(",").map(Number);if(a.length===M&&a.every(isFinite))state.w=a}
  if(h.get("p")!=null&&isFinite(+h.get("p")))state.minPeat=+h.get("p");
  if(h.get("m"))state.missing=h.get("m");
  if(h.get("v")==="team"||h.get("v")==="top")state.view=h.get("v");
  if(h.get("t")==="dark"||h.get("t")==="light")document.documentElement.dataset.theme=h.get("t");
  if(h.get("i"))h.get("i").split(",").forEach(n=>state.islands.add(n));
  if(h.get("c")==="h")state.conf="h";
  if(h.get("k"))state.sel=h.get("k");
}

// ---------------------------------------------------------------- render loop
let pending=false;
function schedule(){if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;recompute();render();history.replaceState(null,"",hashState())})}
function render(selOnly){
  if(!R)recompute();
  markPresets();
  const g=document.querySelector(".grid");if(g.classList.contains("tablemode")!==state.table){g.classList.toggle("tablemode",state.table);setTimeout(()=>{nat&&nat.resize()},60)}
  state.table?($("#rank-list").hidden=true,$("#rank-legend").hidden=true,$("#rank-table").hidden=false,renderTable()):($("#rank-list").hidden=false,$("#rank-legend").hidden=false,$("#rank-table").hidden=true,renderList());
  renderMap();renderBump();
  if(!selOnly)renderProfile();
}
function init(){
  readHash();applyStatic();
  buildControls();fillPick();buildNotes();buildMap();buildTable();staticTips();recompute();
  // parity with the Python ranking at default weights and filters
  let bad=0,cmp=0;const def=compute(DEF);if(state.minPeat===META.min_peat&&!state.islands.size){for(const i of def.order.slice(0,150)){cmp++;if(def.rank[i]!==K.ref_rank[i])bad++}}
  document.body.dataset.parity=cmp+":"+bad;
  if(!state.sel||K.id.indexOf(state.sel)<0){const first=R.order.find(i=>K.has[i]);state.sel=K.id[first!==undefined?first:0]}
  const i0=K.id.indexOf(state.sel);$("#p-pick").value=K.has[i0]?state.sel:"";
  render();
  $("#theme-btn").onclick=()=>{const r=document.documentElement;const dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";themeMaps();render();history.replaceState(null,"",hashState())};
  if(window.ResizeObserver){let ro;new ResizeObserver(()=>{clearTimeout(ro);ro=setTimeout(()=>{nat&&nat.resize()},80)}).observe($("#map"))}
  if(window.ResizeObserver){let ro2;new ResizeObserver(()=>{clearTimeout(ro2);ro2=setTimeout(()=>{pmap&&pmap.resize()},80)}).observe($("#p-map"))}
  let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(()=>{nat&&nat.resize();pmap&&pmap.resize();render()},150)});
  document.body.dataset.ready="1";
}
init();
})();
