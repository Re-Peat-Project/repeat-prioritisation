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
const state={dy:2026,basis:"all",scope:"all",island:"",province:"",src:"viirs",year:NOW,high:false,stat:false,split:"concession",sk:"hs",sd:-1,q:""};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---------------------------------------------------------------- aggregation
const keepK=new Uint8Array(NK);
function filterKeys(){for(let k=0;k<NK;k++)keepK[k]=(state.basis==="all"||C.peat[k]===1)&&(state.scope==="all"||(state.scope==="in")===!!C.in_khg[k])&&(!state.island||C.island[k]===state.island)&&(!state.province||C.province[k]===state.province)?1:0}
const nb=YEARS.length,nv=NOW-V0+1;
const blank=()=>({area:0,ever:0,twice:0,x2:0,x3:0,x4:0,burned:new Float64Array(nb),sel:0,selM:new Float64Array(13),viirs:new Float64Array(nv),vytd:new Float64Array(nv)});
const yr=()=>state.src==="modis"?NOW:state.year;
function aggregate(key,extra){
  const out=new Map(),get=g=>{let a=out.get(g);if(!a){a=blank();out.set(g,a)}return a};
  for(let i=0;i<AR.k.length;i++){const k=AR.k[i];if(!keepK[k]||(extra&&!extra(k)))continue;const a=get(key(k));a.area+=AR.ha[i];a.ever+=AR.ever[i];a.twice+=AR.twice[i];a.x2+=AR.x2[i];a.x3+=AR.x3[i];a.x4+=AR.x4[i];for(let b=0;b<nb;b++)a.burned[b]+=AR.burned[b][i]}
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

function charts(T){
  const Y=yr(),src=state.src.toUpperCase();
  const lastM=+(state.src==="viirs"?META.viirs_last:META.modis_last).slice(5,7),ms=d3.range(1,lastM+1);
  const S=[{name:`${src} ${Y}`,color:"--s2",v:ms.map(i=>T.selM[i])}];
  if(state.src==="viirs"){const mm=new Float64Array(13),m15=new Float64Array(13);
    for(let j=0;j<HT.k.length;j++){const k=HT.k[j];if(!keepK[k]||HT.s[j]!==1||!HT.ytd[j]||(state.high&&!HT.hi[j])||(!state.stat&&HT.st[j]))continue;
      if(HT.y[j]>=PAST[0]&&HT.y[j]<=PAST[1])mm[HT.m[j]]+=HT.n[j]/(PAST[1]-PAST[0]+1);if(HT.y[j]===2015)m15[HT.m[j]]+=HT.n[j]}
    if(Y!==2015)S.push({name:"2015",color:"--s7",v:ms.map(i=>m15[i])});
    S.push({name:`${t("mean")} ${PAST[0]}–${PAST[1]}`,color:"--muted",dash:"4 3",v:ms.map(i=>mm[i])})}
  lineChart($("#c-month"),`${src} ${t("hotspots per month")}`,S,ms,mon,"")}

// ---------------------------------------------------------------- D3 views
const SEQ=["#f4a172","#ee7a45","#d9592a","#a8410f","#6e2a08"];          // validated ordinal orange ramp
const TIMES=["--q1","--q2","--q3","--q4"];
const scopeName=()=>state.province||(state.island?state.island.replace(/^Pulau /,""):t("Indonesia"));
function frame(host,title,hint,W,H){
  host.innerHTML=`<h2>${title}</h2>${hint?`<div class="hint">${hint}</div>`:""}`;
  return d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${H}`).attr("role","img").attr("aria-label",title)}
const T_=(g,x,y,s,o={})=>g.append("text").attr("x",x).attr("y",y).attr("font-size",o.size||12).attr("fill",o.fill||css("--ink")).attr("text-anchor",o.anchor||"start")
  .attr("dominant-baseline","middle").attr("font-weight",o.weight||400).text(s);
const tipOn=(sel,html)=>sel.on("mousemove",ev=>showTip(ev,html)).on("mouseleave",hideTip);
const ink=c=>["#f4a172","#ee7a45"].includes(c)?"#0b0b0b":"#fff";

// donuts: land, burned area and hotspots inside concessions, any year (slider)
let playing=null;
function donut(){
  const host=$("#v-donut"),cc=aggregate(SPLITS.concession.of),Y=state.dy,yi=Y-V0;
  const g=(k,f)=>{const a=cc.get(k);return a?f(a):0};
  const parts=[[t("Land"),g("yes",a=>a.area),g("no",a=>a.area),""],
    [`${t("Burned")} ${Y}`,Y>=Y0?g("yes",a=>a.burned[Y-Y0]):null,Y>=Y0?g("no",a=>a.burned[Y-Y0]):null,(Y===2024||Y===NOW)?"*":""],
    [`${t("Hotspots")} ${Y}`,g("yes",a=>a.vytd[yi]),g("no",a=>a.vytd[yi]),""]];
  const W=Math.max(360,host.clientWidth-28),H=340,svg=frame(host,`${t("Inside or outside concessions")} · ${esc(scopeName())}`,
    t("Share of the land, of the burned area of the year (KLHK) and of the VIIRS hotspots of the year (1 January to the last 2026 date) inside a 2025 business licence. Drag the year."),W,H);
  const r=Math.min(64,W/8),cw=W/3,cy=86,arc=d3.arc().innerRadius(r*0.62).outerRadius(r);
  parts.forEach(([lab,a,b,star],i)=>{
    const cx=cw*i+cw/2,gg=svg.append("g").attr("transform",`translate(${cx},${cy})`),tot=(a||0)+(b||0),p=tot>0?a/tot:null;
    gg.append("path").attr("d",arc({startAngle:0,endAngle:2*Math.PI})).attr("fill",css("--grid"));
    if(p!=null)tipOn(gg.append("path").attr("d",arc({startAngle:0,endAngle:2*Math.PI*p})).attr("fill",css("--s2")),`<b>${lab}</b><br>${t("Inside concessions")}: ${Math.round(100*p)}%`);
    T_(gg,0,0,p==null?"–":`${Math.round(100*p)}%${star}`,{anchor:"middle",size:20,weight:600});
    T_(svg,cx,cy+r+16,lab,{anchor:"middle",size:12.5,weight:600});
    T_(svg,cx,cy+r+32,p==null?t("no burned-area map"):(i===2?`${f0(a)} ${t("of")} ${f0(tot)}`:`${f0(a/100)} ${t("of")} ${f0(tot/100)} km²`),{anchor:"middle",size:11,fill:css("--ink2")})});
  // share inside concessions through the years: hotspots and burned area against the land share
  const x=d3.scaleLinear([V0,NOW],[44,W-60]),y=d3.scaleLinear([0,60],[H-14,250]);
  const land=parts[0][2]+parts[0][1]>0?100*parts[0][1]/(parts[0][1]+parts[0][2]):0;
  svg.append("line").attr("x1",x(V0)).attr("x2",x(NOW)).attr("y1",y(land)).attr("y2",y(land)).attr("stroke",css("--muted")).attr("stroke-dasharray","4 3");
  T_(svg,x(NOW)+6,y(land),`${t("land")} ${Math.round(land)}%`,{size:10.5,fill:css("--ink2")});
  const hs=VY.map(v=>{const a=g("yes",z=>z.vytd[v-V0]),b=g("no",z=>z.vytd[v-V0]);return [v,a+b>0?100*a/(a+b):null]});
  const bs=YEARS.map(v=>{const a=g("yes",z=>z.burned[v-Y0]),b=g("no",z=>z.burned[v-Y0]);return [v,a+b>0?100*a/(a+b):null]});
  const ln=d3.line().defined(d=>d[1]!=null).x(d=>x(d[0])).y(d=>y(d[1]));
  svg.append("path").attr("d",ln(bs)).attr("fill","none").attr("stroke",css("--s1")).attr("stroke-width",2);
  svg.append("path").attr("d",ln(hs)).attr("fill","none").attr("stroke",css("--s2")).attr("stroke-width",2);
  [[0,"0%"],[20,"20%"],[40,"40%"],[60,"60%"]].forEach(([v,l])=>T_(svg,40,y(v),l,{anchor:"end",size:10,fill:css("--muted")}));
  svg.append("line").attr("x1",x(Y)).attr("x2",x(Y)).attr("y1",y(60)).attr("y2",y(0)).attr("stroke",css("--ink2"));
  const hY=hs.find(d=>d[0]===Y);if(hY&&hY[1]!=null)svg.append("circle").attr("cx",x(Y)).attr("cy",y(hY[1])).attr("r",4.5).attr("fill",css("--s2")).attr("stroke",css("--surface")).attr("stroke-width",2);
  T_(svg,44,226,`${t("Share inside concessions per year")}:`,{size:11,fill:css("--ink2")});
  const lg=[[t("hotspots"),"--s2"],[t("burned area"),"--s1"]];let lx=44+212;
  lg.forEach(([l,c])=>{svg.append("rect").attr("x",lx).attr("y",221).attr("width",10).attr("height",10).attr("rx",2).attr("fill",css(c));lx+=14;const tt=T_(svg,lx,226,l,{size:11,fill:css("--ink2")});lx+=tt.node().getComputedTextLength()+12});
  host.insertAdjacentHTML("beforeend",`<div class="slider"><button type="button" id="dplay">${playing?"❚❚":"▶"}</button><input type="range" id="dyear" min="${V0}" max="${NOW}" value="${Y}" aria-label="${t("Year")}"><b>${Y}</b></div>`);
  $("#dyear").oninput=e=>{state.dy=+e.target.value;donut();hash()};
  $("#dplay").onclick=()=>{if(playing){clearInterval(playing);playing=null;donut();return}
    if(state.dy>=NOW)state.dy=V0;playing=setInterval(()=>{state.dy++;if(state.dy>=NOW){state.dy=NOW;clearInterval(playing);playing=null}donut()},700);donut()}}

// each class's share of land against its share of fire, and hotspot density inside against the rest
function fireLand(T){
  const host=$("#v-land"),Y=yr();
  const defs=[["Concessions",SPLITS.concession.of,"yes"],["Forest area",k=>C.forest_group[k],"kawasan"],["DMPG villages",SPLITS.dmpg.of,"yes"],["Peat",k=>C.peat[k]===1?"yes":"no","yes"]]
    .filter(d=>!(state.basis==="peat"&&d[0]==="Peat"));
  const rows=defs.map(([n,f,k])=>{const m=aggregate(f),a=m.get(k)||blank(),o=blank();for(const [kk,v] of m)if(kk!==k){o.area+=v.area;o.sel+=v.sel}
    return {n,land:T.area?100*a.area/T.area:0,burn:sumPast(T)?100*sumPast(a)/sumPast(T):0,hs:T.sel?100*a.sel/T.sel:0,din:rate(a.sel,a.area),dout:rate(o.sel,o.area),area:a.area}})
    .filter(r=>r.area>0).sort((a,b)=>(b.din/b.dout||0)-(a.din/a.dout||0));
  const W=Math.max(420,host.clientWidth-28),rh=52,top=58,H=top+rows.length*rh+20;
  const svg=frame(host,`${t("Fire against land")} · ${esc(scopeName())}`,t("Left: share of the area, of the burned area 2015 to 2025 and of the hotspots of the year. Right: hotspots per 100 km² inside the class and on the rest of the land."),W,H);
  const L=112,xa=d3.scaleLinear([0,Math.max(70,d3.max(rows,r=>Math.max(r.land,r.burn,r.hs))+8)],[L,L+(W-L)*0.5]);
  const xb=d3.scaleLinear([0,d3.max(rows,r=>Math.max(r.din||0,r.dout||0))*1.15||1],[xa.range()[1]+40,W-150]);
  [[css("--muted"),"open",t("area")],[css("--s1"),"fill",t("burned area")],[css("--s2"),"fill",`${t("hotspots")} ${Y}`]].forEach(([c,k,l],i)=>{
    const x0=L+i*110;svg.append("circle").attr("cx",x0+5).attr("cy",14).attr("r",5).attr("fill",k==="open"?css("--surface"):c).attr("stroke",c).attr("stroke-width",2);T_(svg,x0+14,14,l,{size:11,fill:css("--ink2")})});
  [[css("--s2"),t("inside")],[css("--axis"),t("rest of the land")]].forEach(([c,l],i)=>{const x0=xb(0)+i*70;svg.append("rect").attr("x",x0).attr("y",9).attr("width",10).attr("height",10).attr("rx",2).attr("fill",c);T_(svg,x0+14,14,l,{size:11,fill:css("--ink2")})});
  T_(svg,L,36,"%",{size:10.5,fill:css("--muted")});T_(svg,xb(0),36,t("per 100 km²"),{size:10.5,fill:css("--muted")});
  rows.forEach((r,i)=>{
    const y=top+i*rh+12;
    T_(svg,L-12,y-6,t(r.n),{anchor:"end",size:12.5,weight:600});T_(svg,L-12,y+9,`${f0(r.area/100)} km²`,{anchor:"end",size:10.5,fill:css("--muted")});
    const lo=Math.min(r.land,r.burn,r.hs),hi=Math.max(r.land,r.burn,r.hs);
    svg.append("line").attr("x1",xa(lo)).attr("x2",xa(hi)).attr("y1",y).attr("y2",y).attr("stroke",css("--axis")).attr("stroke-width",2);
    [[r.land,"open",css("--muted")],[r.burn,"fill",css("--s1")],[r.hs,"fill",css("--s2")]].forEach(([v,k,c])=>
      tipOn(svg.append("circle").attr("cx",xa(v)).attr("cy",y).attr("r",6.5).attr("fill",k==="open"?css("--surface"):c).attr("stroke",k==="open"?c:css("--surface")).attr("stroke-width",2),
        `<b>${t(r.n)}</b><br>${t("area")} ${f1(r.land)}% · ${t("burned area")} ${f1(r.burn)}% · ${t("hotspots")} ${f1(r.hs)}%`));
    T_(svg,xa(r.land),y+17,`${Math.round(r.land)}%`,{anchor:"middle",size:10.5,fill:css("--muted")});
    T_(svg,xa(hi)+11,y,`${Math.round(r.burn)}% · ${Math.round(r.hs)}%`,{size:11,fill:css("--ink2")});
    [[r.din,css("--s2"),-9],[r.dout,css("--axis"),1]].forEach(([v,c,dy])=>{svg.append("rect").attr("x",xb(0)).attr("y",y+dy).attr("width",Math.max(0,xb(v||0)-xb(0))).attr("height",8).attr("rx",2).attr("fill",c);
      T_(svg,xb(v||0)+4,y+dy+4,f0(v),{size:10.5,fill:css("--ink2")})});
    const q=r.din&&r.dout?r.din/r.dout:null;T_(svg,W-4,y,q?`${f1(q)}× ${t("the rest")}`:"–",{anchor:"end",size:12,weight:600,fill:q>=2?css("--ink"):css("--ink2")})})}

// forest area x concession as a Marimekko: width = land of the forest group, height = share in concessions, colour = density
function mosaic(){
  const host=$("#v-mosaic"),Y=yr(),m=aggregate(k=>C.forest_group[k]+"|"+((C.lic_bits[k]&CONC)?"c":"n"));
  const G=[["kawasan",t("Forest area (kawasan hutan)")],["apl",t("Other land use (APL)")]].map(([g,l])=>{const c=m.get(g+"|c")||blank(),n=m.get(g+"|n")||blank();return {g,l,c,n,area:c.area+n.area}}).filter(d=>d.area>0);
  const W=Math.max(380,host.clientWidth-28),H=300,svg=frame(host,`${t("Concession and forest area")} · ${esc(scopeName())}`,
    t("Column width: area of the forest group. Height: share inside and outside concessions. Colour: hotspots per 100 km² in the selected year."),W,H);
  const br=[10,20,40,80],col=d=>d==null?css("--grid"):SEQ[d3.bisectRight(br,d)];
  const x0=8,x1=W-8,y0=10,y1=H-50,tot=d3.sum(G,d=>d.area);let x=x0;
  G.forEach(d=>{const w=(x1-x0)*d.area/tot;let y=y0;
    [[d.c,t("Concession")],[d.n,t("No concession")]].forEach(([a,lab])=>{const h=(y1-y0)*a.area/d.area,den=rate(a.sel,a.area),c=col(den);
      if(h>0){tipOn(svg.append("rect").attr("x",x+1).attr("y",y+1).attr("width",Math.max(0,w-2)).attr("height",Math.max(0,h-2)).attr("rx",3).attr("fill",c),
        `<b>${lab} · ${d.l}</b><br>${f1(den)} ${t("per 100 km²")}<br>${f0(a.area/100)} km² · ${f0(a.sel)} ${t("hotspots")} ${Y}`);
        if(h>34&&w>90){T_(svg,x+8,y+14,lab,{size:12,weight:600,fill:ink(c)});T_(svg,x+8,y+30,`${f1(den)} ${t("per 100 km²")} · ${Math.round(100*a.area/d.area)}%`,{size:11,fill:ink(c)})}}
      y+=h});
    T_(svg,x+w/2,y1+14,d.l,{anchor:"middle",size:11.5,fill:css("--ink2")});T_(svg,x+w/2,y1+28,`${Math.round(100*d.area/tot)}% ${t("of the area")}`,{anchor:"middle",size:10.5,fill:css("--muted")});x+=w});
  let lx=8;const ly=H-8;T_(svg,lx,ly,`${t("per 100 km²")}:`,{size:10.5,fill:css("--ink2")});lx+=72;
  ["< 10","10–20","20–40","40–80","≥ 80"].forEach((l,i)=>{svg.append("rect").attr("x",lx).attr("y",ly-5).attr("width",10).attr("height",10).attr("rx",2).attr("fill",SEQ[i]);lx+=14;const tt=T_(svg,lx,ly,l,{size:10.5,fill:css("--ink2")});lx+=tt.node().getComputedTextLength()+10})}

// provinces x years: VIIRS hotspots per 100 km², 1 January to the last 2026 date
function heat(){
  const host=$("#v-heat"),P=aggregate(k=>C.province[k]),T=aggregate(()=>"all").get("all")||blank(),Ysel=state.src==="viirs"?state.year:NOW;
  const rows=[...P].filter(([p,a])=>!p.startsWith("Outside")&&a.area>0).map(([p,a])=>({p,a})).sort((u,v)=>(v.a.vytd[Ysel-V0]/v.a.area)-(u.a.vytd[Ysel-V0]/u.a.area));
  rows.unshift({p:scopeName(),a:T,all:true});
  const rh=15,L=150,top=40,W=Math.max(480,host.clientWidth-28),H=top+rows.length*rh+30,cw=(W-L-60)/VY.length;
  const svg=frame(host,`${t("Hotspots by province and year")}`,t("VIIRS hotspots per 100 km² of land, 1 January to the last 2026 date in every year. Rows sorted by the selected year; click a province to select it."),W,H);
  const br=[1,3,10,30,100],ramp=[css("--grid"),...SEQ],col=v=>ramp[d3.bisectRight(br,v)];
  VY.forEach((y,j)=>T_(svg,L+j*cw+cw/2,top-10,String(y).slice(2),{anchor:"middle",size:10.5,fill:y===Ysel?css("--ink"):css("--muted"),weight:y===Ysel?600:400}));
  rows.forEach((r,i)=>{const y=top+i*rh,sel=r.p===state.province;
    const lab=T_(svg,L-8,y+rh/2,r.p.length>24?r.p.slice(0,23)+"…":r.p,{anchor:"end",size:11,weight:r.all||sel?600:400,fill:sel?css("--s2"):css("--ink2")});
    if(!r.all)lab.style("cursor","pointer").on("click",()=>{state.province=state.province===r.p?"":r.p;state.island=state.province?(C.island[C.province.indexOf(r.p)]||state.island):state.island;update()});
    VY.forEach((yy,j)=>{const v=r.a.vytd[yy-V0]/r.a.area*1e4;
      tipOn(svg.append("rect").attr("x",L+j*cw+0.5).attr("y",y+0.5).attr("width",cw-1).attr("height",rh-1).attr("rx",2).attr("fill",col(v)),`<b>${esc(r.p)} · ${yy}</b><br>${f1(v)} ${t("per 100 km²")} · ${f0(r.a.vytd[yy-V0])} ${t("hotspots")}`)});
    if(r.all)svg.append("line").attr("x1",L).attr("x2",L+VY.length*cw).attr("y1",y+rh+1.5).attr("y2",y+rh+1.5).attr("stroke",css("--axis"))});
  const j=VY.indexOf(Ysel);if(j>=0)svg.append("rect").attr("x",L+j*cw).attr("y",top).attr("width",cw).attr("height",rows.length*rh).attr("fill","none").attr("stroke",css("--ink")).attr("stroke-width",1.5).attr("rx",2);
  let lx=L;const ly=H-12;["< 1","1–3","3–10","10–30","30–100","≥ 100"].forEach((l,i)=>{svg.append("rect").attr("x",lx).attr("y",ly-5).attr("width",10).attr("height",10).attr("rx",2).attr("fill",ramp[i]);lx+=14;const tt=T_(svg,lx,ly,l,{size:10.5,fill:css("--ink2")});lx+=tt.node().getComputedTextLength()+10})}

// times burned, per class of the chosen split: share of the class burned once, twice, three times, four or more
function timesBurned(){
  const host=$("#v-times");
  const pairs=[[SPLITS.concession.of,[["yes","Concession"],["no","No concession"]]],[k=>C.forest_group[k],[["kawasan","Forest area (kawasan hutan)"],["apl","Other land use (APL)"]]],
    [SPLITS.dmpg.of,[["yes","DMPG village"],["no","Outside DMPG villages"]]],[k=>C.peat[k]===1?"yes":"no",[["yes","Peat"],["no","Not peat"]]]].filter(p=>!(state.basis==="peat"&&p[1][0][1]==="Peat"));
  const rows=[];pairs.forEach(([f,cl],g)=>{const m=aggregate(f);cl.forEach(([k,l])=>{const a=m.get(k);if(a&&a.area>0)rows.push({l,a,g})})});
  const W=Math.max(320,host.clientWidth-28),rh=24,top=34,H=top+rows.length*rh+pairs.length*6+10;
  const svg=frame(host,`${t("Times burned")} · ${esc(scopeName())}`,t("Share of each class burned once, twice, three times or four or more times in the burn years 2015 to 2026 (KLHK). The 2024 and 2026 maps are incomplete, so these are lower bounds."),W,H);
  const L=170,mx=d3.max(rows,r=>r.a.area?100*r.a.ever/r.a.area:0)||1,x=d3.scaleLinear([0,mx*1.15],[L,W-50]),lab=[t("once"),t("twice"),t("3 times"),t("4 or more")];
  lab.forEach((l,i)=>{svg.append("rect").attr("x",L+i*72).attr("y",9).attr("width",10).attr("height",10).attr("rx",2).attr("fill",css(TIMES[i]));T_(svg,L+i*72+14,14,l,{size:10.5,fill:css("--ink2")})});
  rows.forEach((r,i)=>{const a=r.a,y=top+i*rh+r.g*6,v=[a.ever-a.twice,a.x2,a.x3,a.x4].map(z=>100*z/a.area);let x0=x(0);
    T_(svg,L-8,y+8,t(r.l).length>26?t(r.l).slice(0,25)+"…":t(r.l),{anchor:"end",size:11,fill:css("--ink2")});
    v.forEach((p,k)=>{const w=x(p)-x(0);if(w>0)tipOn(svg.append("rect").attr("x",x0).attr("y",y+1).attr("width",Math.max(0,w-1)).attr("height",14).attr("fill",css(TIMES[k])),`<b>${t(r.l)}</b><br>${lab[k]}: ${f1(p)}% ${t("of the area")}`);x0+=w});
    T_(svg,x0+5,y+8,`${f1(d3.sum(v))}%`,{size:10.5,fill:css("--ink2")})})}

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
  const h=`#l=${LANG}${th?"&t="+th:""}&b=${s.basis}&sc=${s.scope}&src=${s.src}&y=${s.year}${s.high?"&c=h":""}${s.stat?"&st=1":""}&sp=${s.split}&dy=${s.dy}${s.island?"&i="+encodeURIComponent(s.island):""}${s.province?"&p="+encodeURIComponent(s.province):""}`;
  history.replaceState(null,"",h);$("#nav-rank").href=`dashboard.html#l=${LANG}${th?"&t="+th:""}`}
function readHash(){const h=new URLSearchParams(location.hash.slice(1));
  LANG=h.get("l")==="id"||h.get("l")==="en"?h.get("l"):((navigator.language||"").toLowerCase().startsWith("id")?"id":"en");
  if(h.get("t")==="dark"||h.get("t")==="light")document.documentElement.dataset.theme=h.get("t");
  const s=state;if(h.get("b")==="peat")s.basis="peat";if(["in","out"].includes(h.get("sc")))s.scope=h.get("sc");if(h.get("src")==="modis")s.src="modis";
  if(VY.includes(+h.get("y")))s.year=+h.get("y");s.high=h.get("c")==="h";s.stat=h.get("st")==="1";if(SPLITS[h.get("sp")])s.split=h.get("sp");if(VY.includes(+h.get("dy")))s.dy=+h.get("dy");
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
  const sp=SPLITS[state.split],cls=aggregate(sp.of),shown=sp.classes.filter(c=>cls.has(c[0])&&(cls.get(c[0]).area>0||cls.get(c[0]).sel>0));
  donut();fireLand(T);mosaic();classTable(cls,shown);heat();charts(T);timesBurned();provinces();hash()}

readHash();applyStatic();
$("#psearch").oninput=e=>{state.q=e.target.value;provinces()};
$("#theme-btn").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";update()};
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(update,150)});
update();
document.body.dataset.ready="1";
})();
