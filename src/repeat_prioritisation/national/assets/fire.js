(function(){
"use strict";
/*I18N*/
let LANG="en";
const t=(s,v)=>{let r=LANG==="id"&&ID[s]!==undefined?ID[s]:s;if(v)r=r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m);return r};
const loc=()=>LANG==="id"?"id-ID":"en-GB";
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
const tip=h=>' data-tip="'+esc(h)+'"';
const f0=v=>v==null||!isFinite(v)?"–":Math.round(v).toLocaleString(loc());
const f1=v=>v==null||!isFinite(v)?"–":v>=100?f0(v):(+v).toFixed(1).replace(".",LANG==="id"?",":".");
const pct=(a,b)=>b>0?Math.round(100*a/b)+"%":"–";
const MON_EN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],MON_ID=["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"];
const mon=i=>(LANG==="id"?MON_ID:MON_EN)[i-1];

const C=DATA.cls,AR=DATA.area,HT=DATA.hot,META=DATA.meta;
const NOW=2026,PAST=[2015,2025],Y0=META.years[0],YEARS=d3.range(META.years[0],META.years[1]+1);
const VY=[...new Set(HT.y.filter((y,j)=>HT.s[j]===1))].sort((a,b)=>a-b),V0=VY[0];
const CONC=1|2|4|8;                                    // licence bits that are concessions; PPHKM (16) is not
const NK=C.island.length;
const SPLITS={
  concession:{label:"Concession",help:"Inside a business licence of 2025 (oil palm, mining, plantation forest PPHTR, forest concession PBPH), or outside every one. Community forest permits (PPHKM) are not concessions.",
    classes:[["yes","Concession","--s2"],["no","No concession","--s1"]],of:k=>(C.lic_bits[k]&CONC)?"yes":"no"},
  forest:{label:"Forest area",help:"Forest area function 2023 (kawasan hutan, 1:250,000): forest area, other land use (APL), or water, undefined and not mapped.",
    classes:[["kawasan","Forest area (kawasan hutan)","--s6"],["apl","Other land use (APL)","--s4"],["other","Water, undefined or not mapped","--muted"]],of:k=>C.forest_group[k]},
  type:{label:"Concession type",help:"Licence type. Where licences overlap, the land takes the first type in this order: oil palm, mining, plantation forest, forest concession.",
    classes:[["sawit","Oil palm","--s2"],["pphtr","Plantation forest (PPHTR)","--s7"],["tambang","Mining","--s8"],["pbph","Forest concession (PBPH)","--s3"],["none","No concession","--s1"]],of:k=>C.concession[k]},
  function:{label:"Forest function",help:"Forest area function 2023. Where classes overlap, the first in this order is kept.",
    classes:[["cons","Conservation","--s6"],["hl","Protection forest","--s3"],["prod","Production forest (HP, HPT)","--s7"],["hpk","Convertible production (HPK)","--s5"],["apl","Other land use (APL)","--s4"],["other","Water, undefined","--s1"],["none","Not mapped","--muted"]],of:k=>C.kawasan[k]},
  dmpg:{label:"DMPG village",help:"Land inside a Desa Mandiri Peduli Gambut village (SiTMAT portal, 838 villages), or outside every one.",
    classes:[["yes","DMPG village","--s5"],["no","Outside DMPG villages","--s1"]],of:k=>C.dmpg[k]?"yes":"no"}};
const state={basis:"all",scope:"all",island:"",province:"",src:"viirs",year:NOW,high:false,stat:false,split:"concession",sk:"hs",sd:-1,q:""};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---------------------------------------------------------------- aggregation
const keepK=new Uint8Array(NK);
function filterKeys(){for(let k=0;k<NK;k++)keepK[k]=(state.basis==="all"||C.peat[k]===1)&&(state.scope==="all"||(state.scope==="in")===!!C.in_khg[k])&&(!state.island||C.island[k]===state.island)&&(!state.province||C.province[k]===state.province)?1:0}
const nb=YEARS.length,nv=NOW-V0+1;
const blank=()=>({area:0,ever:0,twice:0,burned:new Float64Array(nb),sel:0,selM:new Float64Array(13),viirs:new Float64Array(nv),vytd:new Float64Array(nv)});
const yr=()=>state.src==="modis"?NOW:state.year;
function aggregate(key,extra){
  const out=new Map(),get=g=>{let a=out.get(g);if(!a){a=blank();out.set(g,a)}return a};
  for(let i=0;i<AR.k.length;i++){const k=AR.k[i];if(!keepK[k]||(extra&&!extra(k)))continue;const a=get(key(k));a.area+=AR.ha[i];a.ever+=AR.ever[i];a.twice+=AR.twice[i];for(let b=0;b<nb;b++)a.burned[b]+=AR.burned[b][i]}
  const srcV=state.src==="viirs"?1:0,Y=yr();
  for(let j=0;j<HT.k.length;j++){const k=HT.k[j];if(!keepK[k]||(extra&&!extra(k))||(state.high&&!HT.hi[j])||(!state.stat&&HT.st[j]))continue;
    const a=get(key(k)),n=HT.n[j],y=HT.y[j];
    if(HT.s[j]===srcV&&y===Y&&(srcV===0||HT.ytd[j])){a.sel+=n;a.selM[HT.m[j]]+=n}
    if(HT.s[j]===1){a.viirs[y-V0]+=n;if(HT.ytd[j])a.vytd[y-V0]+=n}}
  return out}
const bY=a=>a?(yr()>=Y0?a.burned[yr()-Y0]:null):0;
const sumPast=a=>{let s=0;if(a)for(let y=PAST[0];y<=PAST[1];y++)s+=a.burned[y-Y0];return s};
const meanPast=a=>sumPast(a)/(PAST[1]-PAST[0]+1);
const vMeanPast=a=>{let s=0;for(let y=PAST[0];y<=PAST[1];y++)s+=a.vytd[y-V0];return s/(PAST[1]-PAST[0]+1)};
const rate=(n,ha)=>ha>0?n/ha*1e4:null;            // per 100 km2 (10,000 ha)
const incomplete=()=>yr()===2024||yr()===NOW;

// ---------------------------------------------------------------- filters
function seg(label,id,opts,cur,on,help){
  return `<div class="ctl"${help?tip(help):""}><span class="lab">${t(label)}</span><span class="seg" id="${id}">`+opts.map(([v,l,h])=>`<button type="button" data-v="${v}" class="${String(v)===String(cur)?"on":""}"${h?tip(h):""}>${l}</button>`).join("")+`</span></div>`}
function buildFilters(){
  const isl=[...new Set(C.island)].filter(s=>!s.startsWith("Outside")).sort();
  const prov=[...new Set(C.province.filter((p,k)=>!state.island||C.island[k]===state.island))].filter(s=>!s.startsWith("Outside")).sort();
  const last=state.src==="viirs"?META.viirs_last:META.modis_last;
  $("#filters").innerHTML=
    seg("Area basis","f-basis",[["all",t("All land"),t("Every cell inside the village boundaries of 2023.")],["peat",t("Peat only"),t("Cells in KLH's peat land map (integrated thematic analysis for peat restoration, April 2026).")]],state.basis)+
    seg("KHG","f-scope",[["all",t("All")],["in",t("Inside KHG")],["out",t("Outside KHG")]],state.scope)+
    `<div class="ctl"><span class="lab">${t("Island")}</span><select id="f-island"><option value="">${t("Indonesia")}</option>${isl.map(s=>`<option value="${esc(s)}"${s===state.island?" selected":""}>${esc(s.replace(/^Pulau /,""))}</option>`).join("")}</select></div>`+
    `<div class="ctl"><span class="lab">${t("Province")}</span><select id="f-prov"><option value="">${t("All")}</option>${prov.map(s=>`<option value="${esc(s)}"${s===state.province?" selected":""}>${esc(s)}</option>`).join("")}</select></div>`+
    seg("Hotspots","f-src",[["viirs","VIIRS",t("VIIRS S-NPP, 375 m: one sensor since 2012, so every year is compared over the same window, 1 January to the last 2026 date.")],["modis","MODIS",t("MODIS, 1 km, 2026 only: the series KLH reports (KLH file, then NASA FIRMS near real time).")]],state.src)+
    `<div class="ctl"><span class="lab">${t("Year")}</span><select id="f-year"${state.src==="modis"?" disabled":""}>${VY.slice().reverse().map(y=>`<option${y===yr()?" selected":""}>${y}</option>`).join("")}</select></div>`+
    seg("Hotspot confidence","f-conf",[["mh",t("Medium + high")],["h",t("High confidence")]],state.high?"h":"mh")+
    `<label class="ctl"${tip(t("MODIS and VIIRS near-real-time hotspots carry no type. Those within 1 km (MODIS) or 375 m (VIIRS) of a VIIRS detection typed as volcano, static land source (such as a gas flare) or offshore are left out unless included here."))}><span class="lab">${t("Static sources")}</span><span><input type="checkbox" id="f-stat"${state.stat?" checked":""}> ${t("Include")}</span></label>`+
    `<span class="stamp">${state.src.toUpperCase()} ${yr()}: 1/1 ${t("to")} ${last.slice(8,10)}/${last.slice(5,7)} · ${t("Burned area")}: KLHK ${META.years[0]}–${META.years[1]}</span>`;
  const segOn=(id,f)=>$$(`#${id} button`).forEach(b=>b.onclick=()=>{f(b.dataset.v);update()});
  segOn("f-basis",v=>state.basis=v);segOn("f-scope",v=>state.scope=v);segOn("f-src",v=>state.src=v);segOn("f-conf",v=>state.high=v==="h");
  $("#f-island").onchange=e=>{state.island=e.target.value;state.province="";update()};
  $("#f-prov").onchange=e=>{state.province=e.target.value;update()};
  $("#f-year").onchange=e=>{state.year=+e.target.value;update()};
  $("#f-stat").onchange=e=>{state.stat=e.target.checked;update()};
}

// ---------------------------------------------------------------- panels
function kpis(T,conc,forest,dmpg){
  const src=state.src.toUpperCase(),Y=yr(),scope=state.province||(state.island?state.island.replace(/^Pulau /,""):t("Indonesia"));
  const share=(m,k)=>`${pct(sumPast(m.get(k)),sumPast(T))} ${t("of burned area")} ${PAST[0]}–${PAST[1]} · ${pct(m.get(k)?.area||0,T.area)} ${t("of the area")}`;
  const unit=state.basis==="peat"?t("of peat"):t("of land");
  const k=(l,v,s,h)=>`<div class="kpi"${tip(h)}><div class="lab">${l}</div><div class="v">${v}</div><div class="l">${s}</div></div>`;
  $("#kpis").innerHTML=
    k(state.basis==="peat"?t("Peat area"):t("Land area"),f0(T.area/100),`km² · ${esc(scope)}`,t("Area of the selection on the equal-area grid."))+
    k(`${t("Burned")} ${Y}${incomplete()?` (${t("incomplete")})`:""}`,f0(bY(T)),`ha · ${t("mean")} ${PAST[0]}–${PAST[1]}: ${f0(meanPast(T))} ha/${t("yr")}`,t("KLHK burnt-area polygons of the year, on the 30 m grid. The 2026 layer holds 0.2 ha per VIIRS hotspot against 2 to 6 ha in 2015 to 2023 and 2025: incomplete as delivered, so compare 2026 with earlier years through the hotspots. 2024 is also incomplete (0.6 ha per hotspot)."))+
    k(`${t("Hotspots")} ${Y}`,f0(T.sel),`${src}, ${state.high?t("high confidence"):t("medium + high")} · ${f1(rate(T.sel,T.area))} ${t("per 100 km²")} ${unit}`+(state.src==="viirs"?` · ×${f1(T.sel/Math.max(1,vMeanPast(T)))} ${t("mean")} ${PAST[0]}–${PAST[1]}`:""),
      state.src==="viirs"?t("VIIRS hotspots from 1 January to the last 2026 date, the same window in every year, and their ratio to the 2015 to 2025 mean."):t("MODIS hotspots of the year: KLH file, then NASA FIRMS MODIS near real time."))+
    k(t("In concessions"),pct(conc.get("yes")?.sel||0,T.sel),share(conc,"yes"),t("Share of the selected year's hotspots (large figure), of the burned area of 2015 to 2025 and of the area (line) inside a business licence. A hotspot inside a licence is a spatial overlap, not responsibility."))+
    k(t("In forest area"),pct(forest.get("kawasan")?.sel||0,T.sel),share(forest,"kawasan"),t("Share inside the forest area (kawasan hutan), with or without a licence."))+
    k(t("In DMPG villages"),pct(dmpg.get("yes")?.sel||0,T.sel),share(dmpg,"yes"),t("Share inside DMPG village land."))}

function matrix(){
  const M=aggregate(k=>SPLITS.concession.of(k)+"|"+C.forest_group[k]),R=SPLITS.concession.classes,Cc=SPLITS.forest.classes,Y=yr(),src=state.src.toUpperCase();
  const scope=state.province||(state.island?state.island.replace(/^Pulau /,""):t("Indonesia"));
  $("#mx-title").textContent=`${t("Concession and forest area")} · ${scope}`;
  $("#mx-hint").innerHTML=`${t("Each cell")}: <b>${t("hotspots per 100 km²")}</b> · ${t("area")} km² · ${t("burned")} ${Y} ha · ${t("hotspots")} ${Y} (${src}). ${t("Shade: hotspot density.")}`;
  let mx=1e-9;R.forEach(r=>Cc.forEach(c=>{const a=M.get(r[0]+"|"+c[0]);if(a)mx=Math.max(mx,rate(a.sel,a.area)||0)}));
  let h=`<span></span>`+Cc.map(c=>`<span class="h"${tip(t(SPLITS.forest.help))}>${t(c[1])}</span>`).join("");
  R.forEach(r=>{h+=`<span${tip(t(SPLITS.concession.help))}><i class="sw" style="background:var(${r[2]})"></i>${t(r[1])}</span>`;
    Cc.forEach(c=>{const a=M.get(r[0]+"|"+c[0])||blank(),d=rate(a.sel,a.area),w=d?Math.round(60*d/mx):0;
      h+=`<div class="cell" style="background:color-mix(in srgb,var(--s2) ${w}%,transparent)"${tip(`<b>${t(r[1])} · ${t(c[1])}</b><br>${f1(d)} ${t("per 100 km²")}<br>${f0(a.area/100)} km² · ${f0(a.sel)} ${t("hotspots")}<br>${t("Burned")} ${Y}: ${f0(bY(a))} ha${incomplete()?"*":""} · ${t("mean")} ${PAST[0]}–${PAST[1]}: ${f0(meanPast(a))} ha/${t("yr")}`)}>
        <div class="d">${f1(d)}</div><div>${f0(a.area/100)} km²</div><div>${f0(bY(a))} ha${incomplete()?"*":""}</div><div>${f0(a.sel)} ${t("hotspots")}</div></div>`})});
  $("#mx").innerHTML=h}

function classTable(cls,shown){
  const sp=SPLITS[state.split],Y=yr(),scope=state.province||(state.island?state.island.replace(/^Pulau /,""):t("Indonesia"));
  $("#cls-title").textContent=`${t("By")} ${t(sp.label).toLowerCase()} · ${scope}`;
  $("#splits").innerHTML=Object.keys(SPLITS).map(k=>`<button type="button" data-v="${k}" class="${k===state.split?"on":""}"${tip(t(SPLITS[k].help))}>${t(SPLITS[k].label)}</button>`).join("");
  $$("#splits button").forEach(b=>b.onclick=()=>{state.split=b.dataset.v;update()});
  const mx=Math.max(1e-9,...shown.map(c=>rate(cls.get(c[0]).sel,cls.get(c[0]).area)||0));
  let h=`<table class="ct"><thead><tr><th></th><th${tip(t("Area of the class on the equal-area grid."))}>${state.basis==="peat"?t("Peat"):t("Land")}<br>km²</th>
    <th${tip(t("KLHK burnt-area polygons of the year. The 2026 layer is incomplete as delivered."))}>${t("Burned")} ${Y}${incomplete()?"*":""}<br>ha</th>
    <th${tip(t("Mean yearly burned area over the earlier years."))}>${t("Mean")} ${PAST[0]}–${PAST[1]}<br>ha/${t("yr")}</th>
    <th${tip(t("Share of the class burned at least once in 2015 to 2026."))}>${t("Ever burned")}<br>%</th>
    <th${tip(t("Share of the class burned in two or more years of 2015 to 2026."))}>${t("Burned 2+ times")}<br>%</th>
    <th${tip(t("Hotspots of the selected sensor and year."))}>${t("Hotspots")} ${Y}</th>
    <th style="text-align:left"${tip(t("Hotspots of the selected sensor and year per 100 km² of the class."))}>${t("per 100 km²")}</th></tr></thead><tbody>`;
  shown.forEach(c=>{const a=cls.get(c[0]),d=rate(a.sel,a.area);
    h+=`<tr><td><i class="sw" style="background:var(${c[2]})"></i>${t(c[1])}</td><td>${f0(a.area/100)}</td><td>${f0(bY(a))}</td><td>${f0(meanPast(a))}</td>
      <td>${a.area>0?f1(100*a.ever/a.area):"–"}</td><td>${a.area>0?f1(100*a.twice/a.area):"–"}</td><td>${f0(a.sel)}</td>
      <td><div class="bar0"><i style="width:${(60*(d||0)/mx).toFixed(1)}%;background:var(${c[2]})"></i><span>${f1(d)}</span></div></td></tr>`});
  // shares: one 100% bar each for area, burned area 2015-2025 and hotspots, segmented by class
  const rows=[[state.basis==="peat"?t("Peat"):t("Land"),c=>cls.get(c[0]).area,t("Area of the class on the equal-area grid.")],
    [`${t("Burned")} ${PAST[0]}–${PAST[1]}`,c=>sumPast(cls.get(c[0])),t("Burned area of 2015 to 2025, summed over the years.")],
    [`${t("Hotspots")} ${Y}`,c=>cls.get(c[0]).sel,t("Hotspots of the selected sensor and year.")]];
  h+=`</tbody></table><div class="shares"><div class="lab">${t("Share of each total")}</div>`;
  rows.forEach(([lab,f,hl])=>{const tot=shown.reduce((s,c)=>s+f(c),0);
    h+=`<div class="srow"><span class="sl"${tip(hl)}>${lab}</span><div class="sbar">`+shown.map(c=>{const v=f(c),p=tot>0?100*v/tot:0;
      return p>0?`<i style="width:${p}%;background:var(${c[2]});color:${["--s3","--s4","--s5","--muted"].includes(c[2])?"#0b0b0b":"#fff"}"${tip(`<b>${t(c[1])}</b><br>${lab}: ${Math.round(p)}%`)}>${p>=7?Math.round(p)+"%":""}</i>`:""}).join("")+`</div></div>`});
  $("#cls").innerHTML=h+"</div>";
  $("#cls-note").textContent=(incomplete()?"* "+t("Burned area of 2026 (and 2024) is incomplete as delivered: it holds far less burned area per hotspot than the other years.")+" ":"")+(state.split==="type"?t("Overlapping licences: the land counts once, under the first type in the list."):"")}

// ---------------------------------------------------------------- line chart (D3): 2 px lines, recessive axes, crosshair and tooltip
function lineChart(host,title,series,xs,xfmt,yunit){
  host.innerHTML=`<div class="ttl">${title}</div><div class="lg">${series.length>1?series.map(s=>`<span><i class="sw" style="background:${s.dash?"transparent;border:1.5px dashed "+css(s.color):css(s.color)}"></i>${esc(s.name)}</span>`).join(""):""}</div>`;
  const W=Math.max(260,host.clientWidth-28),Hh=220,m={l:52,r:12,t:8,b:24};
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${Hh}`).attr("role","img").attr("aria-label",title);
  const x=d3.scaleLinear().domain(d3.extent(xs)).range([m.l,W-m.r]);
  const ymax=d3.max(series,s=>d3.max(s.v))||1,y=d3.scaleLinear().domain([0,ymax]).nice(4).range([Hh-m.b,m.t]);
  svg.append("g").attr("transform",`translate(0,${Hh-m.b})`).call(d3.axisBottom(x).tickValues(xs.length>8?xs.filter((v,i)=>i%Math.ceil(xs.length/8)===0):xs).tickFormat(xfmt).tickSizeOuter(0))
    .call(g=>{g.selectAll("text").attr("fill",css("--ink2")).style("font-size","11px");g.selectAll("line,path").attr("stroke",css("--axis"))});
  svg.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(v=>f0(v)).tickSize(-(W-m.l-m.r)))
    .call(g=>{g.select(".domain").remove();g.selectAll("line").attr("stroke",css("--grid"));g.selectAll("text").attr("fill",css("--ink2")).style("font-size","11px")});
  if(yunit)svg.append("text").attr("x",m.l).attr("y",m.t+2).attr("dx",4).attr("dy","0.7em").attr("fill",css("--muted")).style("font-size","11px").text(yunit);
  const line=d3.line().x((d,i)=>x(xs[i])).y(d=>y(d));
  series.forEach(s=>svg.append("path").attr("d",line(s.v)).attr("fill","none").attr("stroke",css(s.color)).attr("stroke-width",2).attr("stroke-dasharray",s.dash||null).attr("stroke-linejoin","round"));
  const cross=svg.append("line").attr("y1",m.t).attr("y2",Hh-m.b).attr("stroke",css("--axis")).style("display","none");
  const dots=series.map(s=>svg.append("circle").attr("r",4).attr("fill",css(s.color)).attr("stroke",css("--surface")).attr("stroke-width",2).style("display","none"));
  svg.append("rect").attr("x",m.l).attr("y",m.t).attr("width",W-m.l-m.r).attr("height",Hh-m.t-m.b).attr("fill","transparent")
    .on("mousemove",ev=>{const [px]=d3.pointer(ev),i=d3.minIndex(xs,v=>Math.abs(x(v)-px));cross.attr("x1",x(xs[i])).attr("x2",x(xs[i])).style("display",null);
      dots.forEach((d,k)=>d.attr("cx",x(xs[i])).attr("cy",y(series[k].v[i])).style("display",null));
      const tipEl=$("#tip");tipEl.innerHTML=`<b>${xfmt(xs[i])}</b>`+series.map(s=>`<br><i class="sw" style="background:${css(s.color)}"></i>${esc(s.name)}: ${f0(s.v[i])}`).join("");showTip(ev)})
    .on("mouseleave",()=>{cross.style("display","none");dots.forEach(d=>d.style("display","none"));hideTip()})}

function charts(cls,shown,T){
  const sp=SPLITS[state.split],Y=yr(),src=state.src.toUpperCase(),last=META.viirs_last;
  lineChart($("#c-burn"),`${t("Burned area per year")} · ${t(sp.label)}`,shown.map(c=>({name:t(c[1]),color:c[2],v:YEARS.map(y=>cls.get(c[0]).burned[y-Y0]/100)})),YEARS,String,"km²");
  lineChart($("#c-years"),`${t("VIIRS hotspots per year")}, 1/1–${last.slice(8,10)}/${last.slice(5,7)}`,shown.map(c=>({name:t(c[1]),color:c[2],v:VY.map(y=>cls.get(c[0]).vytd[y-V0])})),VY,String,"");
  const lastM=+(state.src==="viirs"?META.viirs_last:META.modis_last).slice(5,7),ms=d3.range(1,lastM+1);
  const S=[{name:`${src} ${Y}`,color:"--s2",v:ms.map(i=>T.selM[i])}];
  if(state.src==="viirs"){const mm=new Float64Array(13);
    for(let j=0;j<HT.k.length;j++){const k=HT.k[j];if(!keepK[k]||HT.s[j]!==1||!HT.ytd[j]||HT.y[j]<PAST[0]||HT.y[j]>PAST[1]||(state.high&&!HT.hi[j])||(!state.stat&&HT.st[j]))continue;mm[HT.m[j]]+=HT.n[j]/(PAST[1]-PAST[0]+1)}
    S.push({name:`${t("mean")} ${PAST[0]}–${PAST[1]}`,color:"--muted",dash:"4 3",v:ms.map(i=>mm[i])})}
  lineChart($("#c-month"),`${src} ${t("hotspots per month")}, ${Y}`,S,ms,mon,"")}

// ---------------------------------------------------------------- province table
function provinces(){
  const P=k=>C.province[k],all=aggregate(P),c=aggregate(P,k=>C.lic_bits[k]&CONC),kw=aggregate(P,k=>C.forest_group[k]==="kawasan"),d=aggregate(P,k=>C.dmpg[k]);
  const isl=new Map(C.province.map((p,k)=>[p,C.island[k]])),Y=yr();
  let rows=[...all].filter(([p])=>!p.startsWith("Outside")).map(([p,a])=>{const b=sumPast(a);return {p,i:(isl.get(p)||"").replace(/^Pulau /,""),isl:isl.get(p),area:a.area/100,bn:bY(a),bm:meanPast(a),
    bc:b>0?100*sumPast(c.get(p))/b:null,bk:b>0?100*sumPast(kw.get(p))/b:null,hs:a.sel,hd:rate(a.sel,a.area),
    hc:a.sel>0?100*(c.get(p)?.sel||0)/a.sel:null,hk:a.sel>0?100*(kw.get(p)?.sel||0)/a.sel:null,hm:a.sel>0?100*(d.get(p)?.sel||0)/a.sel:null}});
  if(state.q){const q=state.q.toLowerCase();rows=rows.filter(r=>r.p.toLowerCase().includes(q)||r.i.toLowerCase().includes(q))}
  rows.sort((a,b)=>{const x=a[state.sk],y=b[state.sk];return (typeof x==="string"?x.localeCompare(y):((x??-1)-(y??-1)))*state.sd});
  const pc=v=>v==null?"–":Math.round(v);
  const cols=[["p",t("Province"),""],["i",t("Island"),""],["area",state.basis==="peat"?t("Peat"):t("Land"),"km²"],["bn",`${t("Burned")} ${Y}${incomplete()?"*":""}`,"ha"],["bm",`${t("Mean")} ${PAST[0]}–${PAST[1]}`,"ha/"+t("yr")],
    ["bc",t("Concession"),"% "+t("burned")],["bk",t("Forest area"),"% "+t("burned")],["hs",`${t("Hotspots")} ${Y}`,""],["hd",t("per 100 km²"),""],["hc",t("Concession"),"% "+t("hotspots")],["hk",t("Forest area"),"% "+t("hotspots")],["hm","DMPG","% "+t("hotspots")]];
  const fm={p:v=>esc(v),i:v=>esc(v),area:f0,bn:f0,bm:f0,bc:pc,bk:pc,hs:f0,hd:f1,hc:pc,hk:pc,hm:pc};
  $("#ptab").innerHTML=`<table><thead><tr>${cols.map(([k,l,u])=>`<th data-k="${k}">${l}${state.sk===k?(state.sd<0?" ▾":" ▴"):""}${u?`<br><span class="hint">${u}</span>`:""}</th>`).join("")}</tr></thead><tbody>`+
    rows.map(r=>`<tr data-p="${esc(r.p)}" data-i="${esc(r.isl)}" class="${r.p===state.province?"sel":""}">${cols.map(([k])=>`<td>${fm[k](r[k])}</td>`).join("")}</tr>`).join("")+"</tbody></table>";
  $$("#ptab th").forEach(th=>th.onclick=()=>{const k=th.dataset.k;state.sd=state.sk===k?-state.sd:(k==="p"||k==="i"?1:-1);state.sk=k;provinces()});
  $$("#ptab tbody tr").forEach(tr=>tr.onclick=()=>{const p=tr.dataset.p;state.province=state.province===p?"":p;state.island=state.province?tr.dataset.i:state.island;update()});
  $("#p-hint").textContent=t("Shares in %: burned area 2015 to 2025 (first pair) and hotspots of the selected year (last three) inside concessions, forest area and DMPG villages. Burned area of 2024 and 2026 is incomplete as delivered. Click a row to select the province.")}

// ---------------------------------------------------------------- tooltip, language, theme, hash
const tipEl=$("#tip");let tipHtml="";
function showTip(e,html){if(html!==undefined)tipEl.innerHTML=html;tipEl.style.display="block";const w=tipEl.offsetWidth,h=tipEl.offsetHeight;let x=e.clientX+14,y=e.clientY+14;if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;tipEl.style.left=x+"px";tipEl.style.top=y+"px"}
function hideTip(){tipEl.style.display="none"}
{const find=e=>e.target.closest?e.target.closest("[data-tip]"):null;
  document.addEventListener("mouseover",e=>{const el=find(e);if(el)showTip(e,el.dataset.tip)});
  document.addEventListener("mousemove",e=>{const el=find(e);if(el)showTip(e,el.dataset.tip)});
  document.addEventListener("mouseout",e=>{const el=find(e);if(el&&!(e.relatedTarget&&el.contains(e.relatedTarget)))hideTip()})}
function hash(){const th=document.documentElement.dataset.theme,s=state;
  const h=`#l=${LANG}${th?"&t="+th:""}&b=${s.basis}&sc=${s.scope}&src=${s.src}&y=${s.year}${s.high?"&c=h":""}${s.stat?"&st=1":""}&sp=${s.split}${s.island?"&i="+encodeURIComponent(s.island):""}${s.province?"&p="+encodeURIComponent(s.province):""}`;
  history.replaceState(null,"",h);$("#nav-rank").href=`dashboard.html#l=${LANG}${th?"&t="+th:""}`}
function readHash(){const h=new URLSearchParams(location.hash.slice(1));
  LANG=h.get("l")==="id"||h.get("l")==="en"?h.get("l"):((navigator.language||"").toLowerCase().startsWith("id")?"id":"en");
  if(h.get("t")==="dark"||h.get("t")==="light")document.documentElement.dataset.theme=h.get("t");
  const s=state;if(h.get("b")==="peat")s.basis="peat";if(["in","out"].includes(h.get("sc")))s.scope=h.get("sc");if(h.get("src")==="modis")s.src="modis";
  if(VY.includes(+h.get("y")))s.year=+h.get("y");s.high=h.get("c")==="h";s.stat=h.get("st")==="1";if(SPLITS[h.get("sp")])s.split=h.get("sp");
  if(h.get("i"))s.island=h.get("i");if(h.get("p"))s.province=h.get("p")}
function applyStatic(){document.documentElement.lang=LANG;$$("[data-i18n]").forEach(el=>{el.textContent=t(el.dataset.i18n)});document.title=t("Fire by land status");
  $("#psearch").placeholder=t("Search province");
  $("#sub").textContent=t("Burned area (KLHK, 2015 to 2026) and hotspots (VIIRS 2012 to 2026, MODIS 2026) by concession, forest area, DMPG village and peat, all of Indonesia");
  $("#foot").textContent=t("Every layer is laid on one equal-area grid of 30 m cells; a cell takes the class of the polygon its centre falls in, and a hotspot the class of the cell it falls in. Licences 2025 and forest area 2023 are matched to every year, so land may have had another status in earlier years. Hotspots and burns inside a licence are a spatial overlap; they do not show the cause of a fire or who is responsible.");
  const lg=$("#lang");lg.innerHTML=[["en","EN"],["id","ID"]].map(([v,x])=>`<button type="button" data-v="${v}" class="${v===LANG?"on":""}">${x}</button>`).join("");
  $$("#lang button").forEach(b=>b.onclick=()=>{LANG=b.dataset.v;applyStatic();update()})}

function update(){
  filterKeys();buildFilters();
  const T=aggregate(()=>"all").get("all")||blank();
  kpis(T,aggregate(SPLITS.concession.of),aggregate(SPLITS.forest.of),aggregate(SPLITS.dmpg.of));
  matrix();
  const sp=SPLITS[state.split],cls=aggregate(sp.of),shown=sp.classes.filter(c=>cls.has(c[0])&&(cls.get(c[0]).area>0||cls.get(c[0]).sel>0));
  classTable(cls,shown);charts(cls,shown,T);provinces();hash()}

readHash();applyStatic();
$("#psearch").oninput=e=>{state.q=e.target.value;provinces()};
$("#theme-btn").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";update()};
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(update,150)});
update();
document.body.dataset.ready="1";
})();
