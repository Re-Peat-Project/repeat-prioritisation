"use strict";
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];

// ---------- language: English text is the key; Bahasa Indonesia in ID
let LANG="en";
const MISS=new Set();
const t=(s,v)=>{let r=s;if(LANG==="id"){if(ID[s]!==undefined)r=ID[s];else MISS.add(s)}if(v)r=r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m);return r};
const locEN=d3.formatLocale({decimal:".",thousands:",",grouping:[3],currency:["",""]}), locID=d3.formatLocale({decimal:",",thousands:".",grouping:[3],currency:["",""]});
const Lc=()=>LANG==="id"?locID:locEN;
const fmt=v=>Lc().format(",.0f")(v), f1=v=>Lc().format(".1f")(v), f2=v=>Lc().format(".2f")(v), fs2=v=>Lc().format("+.2f")(v);
const nf=v=>LANG==="id"?String(v).replace(".",","):String(v);
const tb=s=>LANG==="id"?s.replace(" to "," sampai "):s;                                  // band and class labels from the data
const tc=s=>LANG==="id"?s.replace(" to "," sampai ").replace(/ d$/," hr"):s;
const posName=p=>t(p==="all"?"All positions":p);

// static text of the page: remember the English once, translate on language change
const STATIC=[];
(function collect(){const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest("script,style")||!/[A-Za-z]{2}/.test(n.nodeValue)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
  let n;while(n=w.nextNode())STATIC.push({n,en:n.nodeValue.trim(),pre:n.nodeValue.match(/^\s*/)[0],post:n.nodeValue.match(/\s*$/)[0]});
  $$("[data-tip],[placeholder],[aria-label]").forEach(e=>["data-tip","placeholder","aria-label"].forEach(a=>{if(e.hasAttribute(a))STATIC.push({e,a,en:e.getAttribute(a)})}))})();
function applyStatic(){STATIC.forEach(o=>{if(o.n)o.n.nodeValue=o.pre+t(o.en)+o.post;else o.e.setAttribute(o.a,t(o.en))});document.documentElement.lang=LANG;document.title=t("Fire, wetness and the licence edge")}

const KH=DATA.khg, BY={}; KH.forEach(k=>BY[k.code]=k);
const withEc=KH.filter(k=>k.ec);
const state={code:(KH.find(k=>k.has_s1&&k.has_model)||KH[0]).code,conf:"all",dry:0,canal:"all",layer:"band",cov:1,pol:"VV"};
const POSCOL={foot:"var(--foot)",slope:"var(--slope)",crest:"var(--crest)",all:"var(--ink)"};
const READCOL={"outside higher":"var(--hi)","inside higher":"var(--lo)","no clear difference":"var(--none)"};
const DRY=new Set(DATA.dry_years);
const ecRows=k=>state.conf==="high"?k.ec_h:k.ec;
const ecOf=(k,pos)=>k.ec?ecRows(k).find(r=>r.position===pos&&r.canal===state.canal):null;

// ---------- tooltip and hover help
const tip=$("#tip");
function showTip(html,e){tip.innerHTML=html;tip.style.display="block";const w=tip.offsetWidth,h=tip.offsetHeight;let x=e.clientX+14,y=e.clientY+14;if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;tip.style.left=x+"px";tip.style.top=y+"px"}
const hideTip=()=>{tip.style.display="none"};
document.addEventListener("mouseover",e=>{const x=e.target.closest&&e.target.closest("[data-tip]");if(x)showTip(x.dataset.tip,e)});
document.addEventListener("mousemove",e=>{const x=e.target.closest&&e.target.closest("[data-tip]");if(x)showTip(x.dataset.tip,e)});
document.addEventListener("mouseout",e=>{const x=e.target.closest&&e.target.closest("[data-tip]");if(x&&!x.contains(e.relatedTarget))hideTip()});
function seg(sel,cb){$$(sel+" button").forEach(b=>b.onclick=()=>{if(b.disabled)return;$$(sel+" button").forEach(x=>x.classList.toggle("on",x===b));cb(b.dataset.v)})}
const setSeg=(sel,v)=>$$(sel+" button").forEach(x=>x.classList.toggle("on",x.dataset.v===String(v)));

// ---------- tables
function tableHTML(cols,rows){return "<table><thead><tr>"+cols.map(c=>`<th class="${c.l?"l":""}">${c.t}</th>`).join("")+"</tr></thead><tbody>"+rows.map(r=>"<tr>"+cols.map(c=>`<td class="${c.l?"l":""}">${c.f?c.f(r):r[c.k]}</td>`).join("")+"</tr>").join("")+"</tbody></table>"}
function sortable(host,cols,rows,opts={}){
  let k=opts.k??0,dir=opts.dir??1,q=host._q||"";
  const draw=()=>{let rs=rows.filter(r=>!q||cols.some(c=>String(c.s?c.s(r):(c.f?c.f(r):r[c.k])).toLowerCase().includes(q)));
    rs=rs.slice().sort((a,b)=>{const c=cols[k],x=c.s?c.s(a):a[c.k],y=c.s?c.s(b):b[c.k];return (x==null)-(y==null)||(x>y?1:x<y?-1:0)*dir});
    host.innerHTML="<thead><tr>"+cols.map((c,j)=>`<th data-j="${j}" class="${c.l?"l":""}"${c.h?` data-tip="${c.h}"`:""}>${c.t}<span class="arr">${j===k?(dir>0?"▲":"▼"):""}</span></th>`).join("")+"</tr></thead><tbody>"+
      rs.map(r=>`<tr data-code="${r.code||""}" class="${r.code===state.code?"sel":""}">`+cols.map(c=>`<td class="${c.l?"l":""}${c.w?" wrap2":""}">${c.f?c.f(r):r[c.k]}</td>`).join("")+"</tr>").join("")+"</tbody>";
    $$("th",host).forEach(th=>th.onclick=()=>{const j=+th.dataset.j;dir=(j===k)?-dir:1;k=j;draw()});
    if(opts.click)$$("tbody tr",host).forEach(tr=>tr.onclick=()=>opts.click(tr.dataset.code))};
  draw();host.search=v=>{q=host._q=v.toLowerCase();draw()};return host}

// ---------- claims
function tiles(){
  const rd=withEc.map(k=>ecOf(k,"all")).filter(Boolean), n=rd.length;
  const out=rd.filter(r=>r.reading==="outside higher").length,inn=rd.filter(r=>r.reading==="inside higher").length;
  const foot=withEc.map(k=>ecOf(k,"foot")).filter(Boolean),fb=foot.filter(r=>r.rate_ratio_out_over_in<1).length;
  const s1=KH.filter(k=>k.s1c).flatMap(k=>k.s1c.filter(r=>r.pol==="VV"&&r.position==="all"));
  const less=s1.filter(r=>r.lo>0).length,more=s1.filter(r=>r.hi<0).length;
  const reach=[];KH.filter(k=>k.model).forEach(k=>{const r=k.model.filter(m=>m.position==="all"&&m.band_i>=4&&m.change_days>=0.1);reach.push(r.length?Math.max(...r.map(m=>[0.5,2,5,Infinity][m.band_i-4])):0)});
  const st=DATA.sitmat.stats,rm=isFinite(Math.max(...reach))?Math.max(...reach):5;
  const T=[
   {claim:t("Water levels in licence areas sit at the 0.4 m limit."),big:f1(+st.step_40_concession)+"×",what:t("more readings at −40 than at −41 cm at licence stations (community stations {c}×; {r} readings, {s} stations)",{c:f1(+st.step_40_community),r:fmt(+st.readings_concession),s:fmt(+st.stations_concession)}),chip:["✓",t("Consistent, not independent")],tt:t("The pile-up at the limit means readings follow the compliance level; they are not independent evidence of the managed water table.")},
   {claim:t("Land outside the licences dries more in the dry season."),big:t("{a} of {b}",{a:more,b:s1.length}),what:t("KHG × cover classes where Sentinel-1 backscatter fell more outside than inside; fell less outside in {l}, no difference in {n}",{l:less,n:s1.length-less-more}),chip:["✕",t("Not seen")],tt:t("Four KHG with a Sentinel-1 fetch, tree and open cover, all positions. The sensor is weak under dense canopy and for a deep water table.")},
   {claim:t("A 5 km buffer keeps the surroundings wet."),big:reach.length?"≤ "+nf(rm)+" km":"–",what:t("furthest band where the model moves open land when licence land is held at 0.4 m ({n} KHG)",{n:reach.length}),chip:["○",t("Open: not in the texts read")],tt:t("No distance buffer in PP 71/2014, PP 57/2016, Permen LHK P.15/2017 or P.16/2017 (see Rules and monitoring). The model reach is groundwater flow only; canal outflow control is not modelled.")},
   {claim:t("Fire sits on slopes and dome feet outside the core of the licence."),big:t("{a} of {b}",{a:out,b:n}),what:t("KHG with more fire per peat area just outside the edge; {i} higher inside, {n} no clear difference. At the dome foot the outside/inside ratio is below 1 in {f} of {g}.",{i:inn,n:n-out-inn,f:fb,g:foot.length}),chip:["◐",t("Mixed")],tt:t("Outside higher where the 5 km block interval of the ratio lies above 1.")}];
  $("#tiles").innerHTML=T.map(x=>`<div class="card tile"><div class="claim">${x.claim}</div><div class="big">${x.big}</div><div class="what">${x.what}</div><span class="chip" data-tip="${x.tt}"><span class="i">${x.chip[0]}</span>${x.chip[1]}</span></div>`).join("")}

// ---------- charts
const W=el=>Math.max(300,el.clientWidth||600);
function forestPanels(host,{rows,panels,xdom,log,ref,xlabel,rowLabel,valueOf,colorOf,hollowOf,onClick,selected,tipOf,rowH=24}){
  const w=W(host),lm=Math.min(210,w*.32),pw=(w-lm-8)/panels.length,top=34,bm=34,h=top+rows.length*rowH+bm;
  const svg=d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const x=(log?d3.scaleLog():d3.scaleLinear()).domain(xdom).range([0,pw-18]).clamp(true);
  const y=i=>top+i*rowH+rowH/2;
  panels.forEach((p,pi)=>{
    const g=svg.append("g").attr("transform",`translate(${lm+pi*pw+6},0)`);
    g.append("text").attr("class","ink").attr("x",0).attr("y",16).style("font-weight",600).text(p.label);
    const ticks=log?[0.1,0.25,0.5,1,2,4,10].filter(v=>v>=xdom[0]&&v<=xdom[1]):[xdom[0]/1.5,0,xdom[1]/1.5];
    ticks.forEach(v=>{g.append("line").attr("class","gridl").attr("x1",x(v)).attr("x2",x(v)).attr("y1",top-4).attr("y2",h-bm+2);g.append("text").attr("x",x(v)).attr("y",h-bm+16).attr("text-anchor","middle").text(log?nf(v):(v===0?"0":fs2(v)))});
    g.append("line").attr("class","ref").attr("x1",x(ref)).attr("x2",x(ref)).attr("y1",top-6).attr("y2",h-bm+2);
    rows.forEach((r,i)=>{const v=valueOf(r,p);if(!v)return;
      const c=colorOf(r,p,v),cy=y(i),hit=g.append("g").attr("class","row-hit").on("mousemove",e=>showTip(tipOf(r,p,v),e)).on("mouseleave",hideTip).on("click",()=>onClick&&onClick(r));
      hit.append("rect").attr("class","bg").attr("x",-6).attr("width",pw).attr("y",cy-rowH/2).attr("height",rowH).attr("fill","transparent");
      if(v.lo!=null&&v.hi!=null)hit.append("line").attr("x1",x(Math.max(v.lo,xdom[0]))).attr("x2",x(Math.min(v.hi,xdom[1]))).attr("y1",cy).attr("y2",cy).attr("stroke",c).attr("stroke-width",2);
      const hol=hollowOf(r,p,v),mk=r.marker==="diamond"?d3.symbol(d3.symbolDiamond,70):d3.symbol(d3.symbolCircle,50);
      hit.append("path").attr("d",mk()).attr("transform",`translate(${x(v.v)},${cy})`).attr("fill",hol?"var(--surface)":c).attr("stroke",c).attr("stroke-width",1.8);
      if(v.hi!=null&&v.hi>xdom[1])hit.append("text").attr("x",pw-14).attr("y",cy+4).text("▸");
    });
    g.append("text").attr("x",pw/2-9).attr("y",h-4).attr("text-anchor","middle").text(xlabel)});
  const lg=svg.append("g");
  rows.forEach((r,i)=>{lg.append("g").attr("class","row-hit"+(r.id===selected?" sel":"")).on("click",()=>onClick&&onClick(r)).append("text").attr("x",lm-8).attr("y",y(i)+4).attr("text-anchor","end").attr("class",r.id===selected?"ink":"").style("font-weight",r.id===selected?600:400).text(rowLabel(r))});
  return svg}

function forest(){
  const rows=withEc.map(k=>({id:k.code,k,v:ecOf(k,"all")})).filter(r=>r.v).sort((a,b)=>b.v.rate_ratio_out_over_in-a.v.rate_ratio_out_over_in);
  const val=(r,p)=>{const e=ecOf(r.k,p.pos);return e&&e.rate_ratio_out_over_in?{v:e.rate_ratio_out_over_in,lo:e.lo_block,hi:e.hi_block,e}:null};
  const PL={all:t("All positions"),foot:t("Dome foot"),slope:t("Slope"),crest:t("Crest")};
  forestPanels($("#forest"),{rows,panels:["all","foot","slope","crest"].map(p=>({pos:p,label:PL[p]})),xdom:[0.1,12],log:true,ref:1,
    xlabel:t("out ÷ in (log)"),rowLabel:r=>r.k.name,valueOf:val,colorOf:(r,p,v)=>READCOL[v.e.reading],hollowOf:(r,p,v)=>v.e.reading==="no clear difference",onClick:r=>selectKhg(r.id),selected:state.code,
    tipOf:(r,p,v)=>`<b>${r.k.name}</b> · ${p.label}<br>${t("ratio")} ${f2(v.v)} (${f2(v.lo)}–${f2(v.hi)})<br>${t("hotspots inside {a}, outside {b}",{a:fmt(v.e.hotspots_inside),b:fmt(v.e.hotspots_outside)})}<br>${t("peat inside {a} km², outside {b} km²",{a:fmt(v.e.inside_km2),b:fmt(v.e.outside_km2)})}<br><span class="m">${t(v.e.reading)} · ${t("{n} blocks of 5 km",{n:v.e.blocks})}</span>`});
  const cols=[{t:t("KHG"),l:1,k:"n"},{t:t("Position"),l:1,f:r=>posName(r.p)},{t:t("Ratio"),f:r=>f2(r.ratio)},{t:t("Low"),f:r=>f2(r.lo)},{t:t("High"),f:r=>f2(r.hi)},{t:t("Inside (hotspots)"),f:r=>fmt(r.hi_in)},{t:t("Outside (hotspots)"),f:r=>fmt(r.hi_out)},{t:t("Reading"),l:1,f:r=>t(r.rd)}];
  const tr=[];rows.forEach(r=>["all",...DATA.pos].forEach(p=>{const e=ecOf(r.k,p);if(e)tr.push({n:r.k.name,p,ratio:e.rate_ratio_out_over_in,lo:e.lo_block,hi:e.hi_block,hi_in:e.hotspots_inside,hi_out:e.hotspots_outside,rd:e.reading})}));
  $("#forest-tbl").innerHTML=tableHTML(cols,tr)}

const rate=(r)=>state.conf==="high"?100*r.high_hotspots/(r.peat_km2*DATA.years.length):(state.dry?r.hs_per_100km2_dry_yr:r.hs_per_100km2_yr);
function bandChart(k){
  const host=$("#bandchart"),w=W(host),h=250,m={l:44,r:56,t:12,b:58};
  const dryOk=state.conf==="all";$$("#c-dry button[data-v='1']").forEach(b=>b.disabled=!dryOk);if(!dryOk&&state.dry){state.dry=0;setSeg("#c-dry",0)}
  const rows=k.bp.filter(r=>r.peat_km2>=2);const svg=d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const x=d3.scalePoint().domain(d3.range(8)).range([m.l,w-m.r]).padding(.3),ymax=d3.max(rows,rate)||1,y=d3.scaleLinear().domain([0,ymax*1.08]).nice().range([h-m.b,m.t]);
  y.ticks(4).forEach(v=>{svg.append("line").attr("class","gridl").attr("x1",m.l).attr("x2",w-m.r).attr("y1",y(v)).attr("y2",y(v));svg.append("text").attr("x",m.l-6).attr("y",y(v)+4).attr("text-anchor","end").text(nf(v))});
  svg.append("rect").attr("x",(x(3)+x(4))/2).attr("y",m.t).attr("width",w-m.r-(x(3)+x(4))/2).attr("height",h-m.b-m.t).attr("fill","var(--wash)");
  svg.append("line").attr("class","ref").attr("x1",(x(3)+x(4))/2).attr("x2",(x(3)+x(4))/2).attr("y1",m.t).attr("y2",h-m.b);
  svg.append("text").attr("x",(x(3)+x(4))/2-6).attr("y",m.t+10).attr("text-anchor","end").text(t("inside ◂"));svg.append("text").attr("x",(x(3)+x(4))/2+6).attr("y",m.t+10).text(t("▸ outside"));
  DATA.bands.forEach((b,i)=>{svg.append("text").attr("transform",`translate(${x(i)},${h-m.b+14}) rotate(-35)`).attr("text-anchor","end").text(tb(b))});
  svg.append("text").attr("x",(m.l+w-m.r)/2).attr("y",h-4).attr("text-anchor","middle").text(t("distance to licence edge"));
  ["all",...DATA.pos].forEach(p=>{const pr=rows.filter(r=>r.position===p).sort((a,b)=>a.band_i-b.band_i);if(!pr.length)return;
    const ln=d3.line().x(r=>x(r.band_i)).y(r=>y(rate(r)));
    svg.append("path").attr("d",ln(pr)).attr("fill","none").attr("stroke",POSCOL[p]).attr("stroke-width",p==="all"?2.4:1.8).attr("stroke-dasharray",p==="all"?"5 3":null);
    svg.selectAll(null).data(pr).join("circle").attr("cx",r=>x(r.band_i)).attr("cy",r=>y(rate(r))).attr("r",3).attr("fill",POSCOL[p]).attr("stroke","var(--surface)").attr("stroke-width",1.5)
      .on("mousemove",(e,r)=>showTip(`<b>${posName(p)}</b> · ${tb(r.band)}<br>${t("{x} per 100 km² and year",{x:f2(rate(r))})}<br>${t("{n} hotspots on {a} km² peat",{n:fmt(state.conf==="high"?r.high_hotspots:r.hotspots),a:fmt(r.peat_km2)})}<br><span class="m">${t("burned share 2015–25: {p}%",{p:f1(100*r.burned_share_2015_25)})}</span>`,e)).on("mouseleave",hideTip);
    const last=pr[pr.length-1];svg.append("text").attr("x",x(last.band_i)+8).attr("y",y(rate(last))+(p==="all"?-6:4)).style("fill",POSCOL[p]).text(t(p))});
  const cols=[{t:t("Position"),l:1,f:r=>posName(r.position)},{t:t("Band"),l:1,f:r=>tb(r.band)},{t:t("Peat (km²)"),f:r=>fmt(r.peat_km2)},{t:t("Hotspots"),f:r=>fmt(state.conf==="high"?r.high_hotspots:r.hotspots)},{t:t("per 100 km² and year"),f:r=>f2(rate(r))}];
  const ord=["all",...DATA.pos];$("#band-tbl").innerHTML=tableHTML(cols,k.bp.slice().sort((a,b)=>ord.indexOf(a.position)-ord.indexOf(b.position)||a.band_i-b.band_i))}

const GROUPS=[["inside, more than 0.5 km from the edge","inside > 0.5 km","#184f95"],["inside, within 0.5 km of the edge","inside ≤ 0.5 km","#6da7ec"],["outside, within 0.5 km","outside ≤ 0.5 km","#f0a383"],["outside, 0.5 to 2 km","outside 0.5–2 km","#eb6834"],["outside, 2 to 5 km","outside 2–5 km","#a8391a"]];
function yearChart(k){
  const host=$("#yearchart"),w=W(host),h=250,m={l:44,r:12,t:12,b:46};
  const svg=d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const rows=k.by.filter(r=>r.position==="all"),val=r=>100*(state.conf==="high"?r.high_hotspots:r.hotspots)/r.peat_km2;
  const x=d3.scaleLinear().domain([DATA.years[0],DATA.years.at(-1)]).range([m.l,w-m.r]),y=d3.scaleLinear().domain([0,d3.max(rows,val)||1]).nice().range([h-m.b,m.t]);
  DATA.dry_years.forEach(d=>svg.append("rect").attr("x",x(d)-(x(1)-x(0))/2).attr("width",x(1)-x(0)).attr("y",m.t).attr("height",h-m.b-m.t).attr("fill","var(--wash)"));
  y.ticks(4).forEach(v=>{svg.append("line").attr("class","gridl").attr("x1",m.l).attr("x2",w-m.r).attr("y1",y(v)).attr("y2",y(v));svg.append("text").attr("x",m.l-6).attr("y",y(v)+4).attr("text-anchor","end").text(nf(v))});
  DATA.years.filter((d,i)=>i%2===0).forEach(d=>svg.append("text").attr("x",x(d)).attr("y",h-m.b+14).attr("text-anchor","middle").text(d));
  GROUPS.forEach(([g,lab,c])=>{const pr=rows.filter(r=>r.group===g).sort((a,b)=>a.year-b.year);if(!pr.length)return;
    svg.append("path").attr("d",d3.line().x(r=>x(r.year)).y(r=>y(val(r)))(pr)).attr("fill","none").attr("stroke",c).attr("stroke-width",2);
    svg.selectAll(null).data(pr).join("circle").attr("cx",r=>x(r.year)).attr("cy",r=>y(val(r))).attr("r",2.6).attr("fill",c).attr("stroke","var(--surface)").attr("stroke-width",1)
      .on("mousemove",(e,r)=>showTip(`<b>${t(lab)}</b> · ${r.year}${DRY.has(r.year)?" ("+t("dry year")+")":""}<br>${t("{v} hotspots per 100 km²",{v:f2(val(r))})}<br>${t("{n} on {a} km² peat",{n:fmt(state.conf==="high"?r.high_hotspots:r.hotspots),a:fmt(r.peat_km2)})}`,e)).on("mouseleave",hideTip)});
  GROUPS.forEach(([g,lab,c],i)=>{const gx=m.l+i*((w-m.l-m.r-60)/5);svg.append("rect").attr("x",gx).attr("y",h-6).attr("width",10).attr("height",3).attr("fill",c);svg.append("text").attr("x",gx+14).attr("y",h-2).text(t(lab))});
  const cols=[{t:t("Zone"),l:1,f:r=>t((GROUPS.find(g=>g[0]===r.group)||[0,r.group])[1])},{t:t("Year"),f:r=>r.year},{t:t("Peat (km²)"),f:r=>fmt(r.peat_km2)},{t:t("Hotspots"),f:r=>fmt(state.conf==="high"?r.high_hotspots:r.hotspots)},{t:t("per 100 km²"),f:r=>f2(val(r))}];
  $("#year-tbl").innerHTML=tableHTML(cols,k.by.filter(r=>r.position==="all"))}

function modelChart(){
  const host=$("#modelchart"),ks=KH.filter(k=>k.model);host.innerHTML="";
  if(!ks.length){host.textContent=t("No model runs.");return}
  const w=W(host),h=240,m={l:44,r:8,t:26,b:58},pw=(w-m.l-m.r-24)/2;
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const cols=["var(--open)","#e87ba4","#c98500"];
  [["change_days",t("Change (days deeper than 40 cm)")],["base_days_deeper_40",t("Baseline, no managed target (days)")]].forEach(([f,ti],pi)=>{
    const g=svg.append("g").attr("transform",`translate(${m.l+pi*(pw+24)},0)`),x=d3.scalePoint().domain(d3.range(8)).range([0,pw-6]).padding(.3);
    const all=ks.flatMap(k=>k.model.filter(r=>r.position==="all")),y=d3.scaleLinear().domain([Math.min(0,d3.min(all,r=>r[f])||0),Math.max(f==="change_days"?3:60,d3.max(all,r=>r[f])||1)]).nice().range([h-m.b,m.t]);
    g.append("text").attr("class","ink").attr("y",14).style("font-weight",600).text(ti);
    y.ticks(4).forEach(v=>{g.append("line").attr("class","gridl").attr("x1",0).attr("x2",pw).attr("y1",y(v)).attr("y2",y(v));g.append("text").attr("x",-6).attr("y",y(v)+4).attr("text-anchor","end").text(nf(v))});
    g.append("line").attr("class","ref").attr("x1",(x(3)+x(4))/2).attr("x2",(x(3)+x(4))/2).attr("y1",m.t).attr("y2",h-m.b);
    DATA.bands.forEach((b,i)=>g.append("text").attr("transform",`translate(${x(i)},${h-m.b+14}) rotate(-35)`).attr("text-anchor","end").text(tb(b)));
    ks.forEach((k,ki)=>{const pr=k.model.filter(r=>r.position==="all").sort((a,b)=>a.band_i-b.band_i);
      g.append("path").attr("d",d3.line().x(r=>x(r.band_i)).y(r=>y(r[f]))(pr)).attr("fill","none").attr("stroke",cols[ki]).attr("stroke-width",2);
      g.selectAll(null).data(pr).join("circle").attr("cx",r=>x(r.band_i)).attr("cy",r=>y(r[f])).attr("r",3).attr("fill",cols[ki]).attr("stroke","var(--surface)").attr("stroke-width",1.2)
        .on("mousemove",(e,r)=>showTip(`<b>${k.name}</b> · ${tb(r.band)}<br>${f==="change_days"?t("change"):t("baseline")} ${t("{x} days",{x:f2(r[f])})}<br><span class="m">${t("{n} open cells",{n:fmt(r.cells)})}</span>`,e)).on("mouseleave",hideTip);
      if(pi===1){const l=pr.at(-1);g.append("text").attr("x",x(l.band_i)-4).attr("y",y(l[f])-6).attr("text-anchor","end").style("fill","var(--ink2)").text(k.name.split(" - ")[0])}})});
  $("#model-note").textContent=t("Open land only; cells held at the target are left out. Held licence land moves open land within about 0.5 km of the edge and not beyond; the managed target (0.4 m) is an assumption.")}

function s1Chart(){
  const host=$("#s1chart"),ks=KH.filter(k=>k.s1c);if(!ks.length){host.textContent=t("No Sentinel-1 fetch.");return}
  const rows=[];ks.forEach(k=>["tree","open"].forEach(c=>rows.push({id:k.code+c,k,cover:c,marker:c==="open"?"diamond":"circle"})));
  const val=(r,p)=>{const e=r.k.s1c.find(x=>x.cover===r.cover&&x.position===p.pos&&x.pol===state.pol);return e?{v:e.outside_minus_inside_dB,lo:e.lo,hi:e.hi,e}:null};
  forestPanels(host,{rows,panels:[{pos:"all",label:t("All")},{pos:"foot",label:t("Foot")},{pos:"slope",label:t("Slope")},{pos:"crest",label:t("Crest")}],xdom:[-1.5,1.5],log:false,ref:0,xlabel:"dB",
    rowLabel:r=>r.k.name.split(" - ")[0]+" · "+t(r.cover),valueOf:val,colorOf:r=>r.cover==="tree"?"var(--tree)":"var(--open)",hollowOf:(r,p,v)=>!(v.lo>0||v.hi<0),selected:null,
    tipOf:(r,p,v)=>`<b>${r.k.name}</b> · ${t(r.cover)} · ${p.label}<br>${fs2(v.v)} dB (${fs2(v.lo)} ${t("to")} ${fs2(v.hi)})<br>${t("{a} cells inside, {b} outside",{a:fmt(v.e.cells_inside),b:fmt(v.e.cells_outside)})}<br><span class="m">${t("positive: backscatter fell less outside")}</span>`,onClick:r=>selectKhg(r.k.code),rowH:22})}

function sitChart(){
  const host=$("#sitchart"),w=W(host),h=210,m={l:44,r:110,t:10,b:30},b=DATA.sitmat.bins,st=DATA.sitmat.stats;
  const svg=d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const x=d3.scaleLinear().domain([-60,-20]).range([m.l,w-m.r]),y=d3.scaleLinear().domain([0,d3.max(b,r=>r.concession_permille)]).nice().range([h-m.b,m.t]);
  y.ticks(4).forEach(v=>{svg.append("line").attr("class","gridl").attr("x1",m.l).attr("x2",w-m.r).attr("y1",y(v)).attr("y2",y(v));svg.append("text").attr("x",m.l-6).attr("y",y(v)+4).attr("text-anchor","end").text(nf(v))});
  x.ticks(8).forEach(v=>svg.append("text").attr("x",x(v)).attr("y",h-12).attr("text-anchor","middle").text(v));svg.append("text").attr("x",(m.l+w-m.r)/2).attr("y",h-0).attr("text-anchor","middle").text(t("water level (cm, negative below the surface)"));
  svg.append("line").attr("class","ref").attr("x1",x(-40)).attr("x2",x(-40)).attr("y1",m.t).attr("y2",h-m.b);svg.append("text").attr("x",x(-40)+5).attr("y",m.t+10).text(t("0.4 m limit"));
  [["concession_permille",t("Licence stations"),"var(--slope)"],["community_permille",t("Community stations"),"var(--foot)"]].forEach(([f,ti,c])=>{
    svg.append("path").attr("d",d3.line().x(r=>x(r.level_cm)).y(r=>y(r[f]))(b)).attr("fill","none").attr("stroke",c).attr("stroke-width",2);
    svg.selectAll(null).data(b).join("circle").attr("cx",r=>x(r.level_cm)).attr("cy",r=>y(r[f])).attr("r",6).attr("fill","transparent").on("mousemove",(e,r)=>showTip(`<b>${ti}</b><br>${t("{l} cm: {v} per mille",{l:r.level_cm,v:f1(r[f])})}`,e)).on("mouseleave",hideTip);
    const l=b.at(-1);svg.append("text").attr("x",x(-20)+6).attr("y",y(l[f])+4).style("fill","var(--ink2)").text(ti)});
  $("#sit-note").textContent=t("{a} readings from {b} licence stations and {c} from {d} community stations, {f} to {g}. Licence readings pile up just inside the limit and drop below it; community readings do not. Whether operators hold water at the limit or report it there, these readings are not independent evidence of the managed water table.",{a:fmt(+st.readings_concession),b:fmt(+st.stations_concession),c:fmt(+st.readings_community),d:fmt(+st.stations_community),f:st.first_date,g:st.last_date})}

// ---------- map
const DROP=/^(building|aeroway.*|railway.*|highway-shield.*|road_shield.*|airport|road_pier|road_area_pier|tunnel_.*|highway_path|highway-name-path|highway-name-minor)$/;
const CP=["background-color","fill-color","fill-outline-color","line-color","text-color","text-halo-color"];
const mapColors=(v,fn,p)=>{if(typeof v==="string"&&/^(#|rgb|hsl)/.test(v))return fn(v,p);if(Array.isArray(v))return v.map(x=>mapColors(x,fn,p));if(v&&typeof v==="object"){const o={};for(const k in v)o[k]=mapColors(v[k],fn,p);return o}return v};
const darkColor=(c,p)=>{const h=d3.hsl(c);if(!isFinite(h.h))h.h=0;const l=p==="text-color"?1-h.l:.075+.27*(1-h.l);return d3.hsl(h.h,h.s*.45,Math.min(.95,l),h.opacity).formatRgb()};
const BASE_L=(()=>{const s=JSON.parse(JSON.stringify(DATA.style));s.layers=s.layers.filter(l=>!DROP.test(l.id));return s})();
const BASE_D=(()=>{const s=JSON.parse(JSON.stringify(BASE_L));for(const l of s.layers)for(const p of CP)if(l.paint&&l.paint[p]!==undefined)l.paint[p]=mapColors(l.paint[p],darkColor,p);return s})();
const isDark=()=>{const x=document.documentElement.dataset.theme;return x?x==="dark":matchMedia("(prefers-color-scheme:dark)").matches};
const BAND_COL=["#184f95","#2a78d6","#6da7ec","#b7d3f6","#f6c2ad","#eb6834","#b8431b","#6e2410"];
const RAMP=["#ece9e0","#fbd9c9","#f5b394","#eb6834","#c24a1b","#8c3010","#5a1d08"];
const LAYERS={
  band:{t:"Distance to edge",c:BAND_COL},
  pos:{t:"Dome position",c:["#2a78d6","#eb6834","#1baf7a"]},
  fire:{t:"Fire 2012–25",c:RAMP,u:"hotspots per 100 km² and year, 1 km blocks"},
  s1:{t:"Sentinel-1",c:["#a8391a","#eb6834","#f5b394","#d9d8d2","#9ec5f4","#2a78d6"],u:"VV, dry minus wet; negative: backscatter fell"},
  mchg:{t:"Model: change",c:RAMP.slice(1,6),u:"days deeper than 40 cm, licence land held at 0.4 m"},
  mbase:{t:"Model: baseline",c:RAMP.slice(1,7),u:"days deeper than 40 cm of 122, no managed target"}};
const layerLabels=n=>n==="band"?DATA.bands.map(tb):n==="pos"?DATA.pos.map(p=>t(p)):n==="fire"?DATA.classes.fire.map(tc):n==="s1"?DATA.classes.s1.map(tc):n==="mchg"?DATA.classes.mchg.map(tc):DATA.classes.mbase.map(tc);
const hexRGB=h=>{const c=d3.rgb(h);return[c.r,c.g,c.b]};
let map=null,mapReady=false,cache={};
async function gunzip(b64){const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));const s=new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));return new Uint8Array(await new Response(s).arrayBuffer())}
async function layersOf(k){if(cache[k.code])return cache[k.code];const o={};for(const n in k.map.layers)o[n]=await gunzip(k.map.layers[n]);cache[k.code]=o;return o}
const layerKey=()=>state.layer==="fire"&&state.conf==="high"?"fire_h":state.layer;
function mapLabels(){if(!map||!mapReady)return;const code=LANG==="id"?"id":"en";for(const l of map.getStyle().layers){if(l.type==="symbol"&&l.layout&&l.layout["text-field"]!==undefined)try{map.setLayoutProperty(l.id,"text-field",["coalesce",["get","name:"+code],["get","name"]])}catch(e){}}}
function legend(){const def=LAYERS[state.layer],lab=layerLabels(state.layer);
  $("#legend").innerHTML=lab.map((l,i)=>`<span><span class="sw" style="background:${def.c[i]}"></span>${l}</span>`).join("")+(def.u?`<span style="color:var(--muted)">${t(def.u)}</span>`:"");
  $("#c-cov").style.display=state.layer==="s1"?"inline-flex":"none"}
async function paint(){
  const k=BY[state.code],L=await layersOf(k),M=k.map,key=layerKey(),a=L[key],def=LAYERS[state.layer],cov=L.cov;
  const cv=document.createElement("canvas");cv.width=M.w;cv.height=M.h;const ctx=cv.getContext("2d"),im=ctx.createImageData(M.w,M.h),rgb=def.c.map(hexRGB);
  for(let i=0;i<a.length;i++){const c=a[i];if(!c)continue;if(state.layer==="s1"&&cov[i]!==state.cov)continue;const col=rgb[c-1];if(!col)continue;im.data[4*i]=col[0];im.data[4*i+1]=col[1];im.data[4*i+2]=col[2];im.data[4*i+3]=225}
  ctx.putImageData(im,0,0);
  if(mapReady){map.getSource("img").updateImage({url:cv.toDataURL(),coordinates:M.corners})}else window._pending=cv.toDataURL();
  legend()}
const BLANK="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
function overlays(){const M=BY[state.code].map,first=map.getStyle().layers.find(l=>l.type==="symbol"),before=first&&first.id;
  map.addSource("img",{type:"image",url:window._pending||BLANK,coordinates:M.corners});
  map.addLayer({id:"img",type:"raster",source:"img",paint:{"raster-resampling":"nearest","raster-opacity":.95,"raster-fade-duration":0}},before);
  map.addSource("khg",{type:"geojson",data:{type:"Feature",geometry:M.khg}});map.addSource("lic",{type:"geojson",data:{type:"Feature",geometry:M.lic||{type:"GeometryCollection",geometries:[]}}});
  map.addLayer({id:"khg-l",type:"line",source:"khg",paint:{"line-color":"#767570","line-width":1.2,"line-dasharray":[3,2]}},before);
  map.addLayer({id:"lic-l",type:"line",source:"lic",paint:{"line-color":isDark()?"#f0efec":"#0b0b0b","line-width":1.6}},before)}
function initMap(){
  map=new maplibregl.Map({container:"map",style:isDark()?BASE_D:BASE_L,attributionControl:false,cooperativeGestures:true,dragRotate:false,pitchWithRotate:false,renderWorldCopies:false,bounds:BY[state.code].map.bounds,fitBoundsOptions:{padding:30}});
  map.addControl(new maplibregl.AttributionControl({compact:true}));map.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-left");map.on("error",()=>{});
  map.on("load",async()=>{overlays();mapReady=true;mapLabels();await paint()});
  map.on("mousemove",e=>{if(!mapReady)return;const k=BY[state.code],M=k.map,R=6378137,x=R*e.lngLat.lng*Math.PI/180,y=R*Math.log(Math.tan(Math.PI/4+e.lngLat.lat*Math.PI/360)),c=Math.floor((x-M.x0)/M.res),r=Math.floor((M.ytop-y)/M.res);
    const L=cache[k.code],ci=$("#cellinfo");if(!L||c<0||r<0||c>=M.w||r>=M.h){ci.innerHTML=t("Outside the peat cells");return}const i=r*M.w+c,b=L.band[i];
    if(!b){ci.innerHTML=t("No peat cell");return}
    const fc=(state.conf==="high"?L.fire_h:L.fire)[i];let h=`<b>${tb(DATA.bands[b-1])}</b> ${b<=4?t("inside the edge"):t("outside the edge")}<br>${t("position")}: ${["–",t("foot"),t("slope"),t("crest")][L.pos[i]]}<br>${t("fire")}: ${fc?tc(DATA.classes.fire[fc-1]):"–"} ${t("per 100 km²·yr (1 km block)")}`;
    if(L.s1&&L.s1[i])h+=`<br>S1 ${L.cov[i]===1?t("tree"):t("open")}: ${tc(DATA.classes.s1[L.s1[i]-1])}`;if(L.mchg&&L.mchg[i])h+=`<br>${t("model")}: +${tc(DATA.classes.mchg[L.mchg[i]-1])}, ${t("baseline")} ${tc(DATA.classes.mbase[L.mbase[i]-1])}`;
    ci.innerHTML=h})}
function layerButtons(k){const avail=Object.keys(LAYERS).filter(n=>n==="s1"?k.has_s1:n.startsWith("m")?k.has_model:true);if(!avail.includes(state.layer))state.layer="band";
  $("#c-layer").innerHTML=avail.map(n=>`<button data-v="${n}" class="${n===state.layer?"on":""}">${t(LAYERS[n].t)}</button>`).join("");seg("#c-layer",v=>{state.layer=v;paint();mapNote()})}
function mapNote(){const M=BY[state.code].map;$("#map-note").textContent=t("Peat cells of 200 m.")+(state.layer==="fire"?" "+t("Fire is shown as 1 km blocks for readability; the charts use the 200 m counts."):"")+" "+t("Solid outline: dissolved 2025 licence layer")+(M.lic?"":" ("+t("none on peat in this KHG")+")")+"; "+t("dashed: KHG boundary. Basemap needs internet.")}
function mapTo(k){layerButtons(k);const M=k.map;if(!map){initMap()}else if(mapReady){map.getSource("khg").setData({type:"Feature",geometry:M.khg});map.getSource("lic").setData({type:"Feature",geometry:M.lic||{type:"GeometryCollection",geometries:[]}});map.fitBounds(M.bounds,{padding:30,duration:600});paint()}
  mapNote();legend()}

// ---------- selection and render
function selectKhg(code){state.code=code;$("#c-khg").value=code;renderDetail();forest();$$("#ktbl tbody tr").forEach(tr=>tr.classList.toggle("sel",tr.dataset.code===code))}
function renderDetail(){const k=BY[state.code];
  $("#d-title").textContent=k.name;$("#d-sub").textContent=t("{p} · peat {a} km² · peat under licence {b} km² ({n} licence polygons) · DTM {d}",{p:k.province,a:fmt(k.peat_km2),b:fmt(k.licence_peat_km2),n:k.licences,d:k.dem});
  if(k.ec){bandChart(k);yearChart(k)}else{$("#bandchart").innerHTML="<p class='note'>"+t("No licence on peat in this KHG: no contrast.")+"</p>";$("#yearchart").innerHTML="";$("#band-tbl").innerHTML="";$("#year-tbl").innerHTML=""}
  mapTo(k)}
function rules(){
  const col=LANG==="id"?"_id":"_en",tx=(r,k)=>r[k+col]||r[k+"_en"];
  $("#rules").innerHTML="<thead><tr><th class='l'>"+t("Question")+"</th><th class='l'>"+t("Status")+"</th><th class='l'>"+t("What the texts say")+"</th><th class='l'>"+t("Article")+"</th><th class='l'>"+t("What this page's data can show")+"</th></tr></thead><tbody>"+
   DATA.rules.map(r=>`<tr><td class="l wrap2">${tx(r,"question")}</td><td class="l wrap2"><span class="chip"><span class="i">${r.status==="open"?"○":"✓"}</span>${t(r.status==="open"?"Unresolved":"Found")}</span></td>`+
   `<td class="l wrap2">${tx(r,"finding")}${r.quote_id?`<details><summary>${t("Original wording")}</summary><i>${r.quote_id}</i></details>`:""}</td><td class="l wrap2"><a href="${r.url}" target="_blank" rel="noopener" style="color:var(--foot)">${r.instrument}</a><br>${r.article}</td><td class="l wrap2">${tx(r,"data")}</td></tr>`).join("")+"</tbody>"}
function ktable(){
  const rows=KH.map(k=>{const e=k.ec?ecRows(k).find(r=>r.position==="all"&&r.canal==="all"):null;return{code:k.code,n:k.name,pv:k.province,peat:k.peat_km2,lic:k.licence_peat_km2,e,ratio:e&&e.rate_ratio_out_over_in,rd:e?e.reading:"no licence on peat",dem:k.dem,m:k.has_model?"yes":"–",s:k.has_s1?"yes":"–"}});
  const cols=[{t:t("KHG"),l:1,k:"n"},{t:t("Province"),l:1,k:"pv"},{t:t("Peat (km²)"),f:r=>fmt(r.peat),s:r=>r.peat,h:t("Peat area of the KHG (GFW composite extent), km²")},{t:t("Peat under licence (km²)"),f:r=>fmt(r.lic),s:r=>r.lic},
   {t:t("Ratio out ÷ in"),f:r=>r.ratio==null?"–":f2(r.ratio),s:r=>r.ratio,h:t("Hotspots per km² of peat 0–2 km outside the licence edge over 0–2 km inside")},{t:t("Low"),f:r=>r.e?f2(r.e.lo_block):"–",s:r=>r.e?r.e.lo_block:null},{t:t("High"),f:r=>r.e?f2(r.e.hi_block):"–",s:r=>r.e?r.e.hi_block:null},
   {t:t("Reading"),l:1,f:r=>t(r.rd),s:r=>r.rd},{t:t("DTM"),l:1,k:"dem"},{t:t("Model"),f:r=>t(r.m)},{t:t("Sentinel-1"),f:r=>t(r.s)}];
  const tb_=sortable($("#ktbl"),cols,rows,{k:4,dir:-1,click:selectKhg});$("#q").oninput=e=>tb_.search(e.target.value);return tb_}
function sources(){
  const pass=[...new Set(KH.filter(k=>k.s1_pass).map(k=>k.s1_pass.toLowerCase()))].join("/");
  const S=[[t("Licence areas"),t("KLH business licences, 2025 layer (landstatus)"),t("vector"),t("2025 map applied to all years"),t("Dissolved; no holder names shown")],
   [t("Peat extent"),t("GFW composite peat extent"),t("raster, sampled at each hotspot"),"—",t("Fire is counted on peat and divided by peat area")],
   [t("Hotspots"),t("VIIRS SNPP active fire (FIRMS)"),t("points; per 100 km² of peat and year"),"2012–2025",t("Nominal and high confidence kept, low dropped; high-only shown on request")],
   [t("Dome position"),t("Height above nearest river from the best DTM covering the KHG"),t("200 m cells; thirds of the KHG's peat"),t("per KHG (see table)"),t("Foot, slope, crest")],
   [t("Canal distance"),t("KHG canal layer"),t("m to nearest canal"),"—",t("Strata < 1 km and ≥ 1 km")],
   [t("Groundwater model"),t("repeat-neraca-model, LiDAR DTM; baseline against licence land held at 0.4 m"),t("200 m (100 m at Mendahara)"),t("1 June–30 Sept 2026 (122 days)"),t("In development; the 0.4 m target is an assumption")],
   [t("Sentinel-1"),t("COPERNICUS/S1_GRD IW VV and VH, {o} orbit; ESA WorldCover v200 classes",{o:pass}),t("10 m averaged onto the 200 m grid in Earth Engine"),t("wet {w}; dry {d} 2026",{w:DATA.s1_wet.join(", "),d:DATA.s1_dry.join(", ")}),t("Moisture signal, not a water table")],
   [t("Water-level stations"),t("SiTMAT TMAT, unflagged daily values −300 to +50 cm"),t("station-day"),t("from {a} to {b}",{a:DATA.sitmat.stats.first_date,b:DATA.sitmat.stats.last_date}),t("Licence readings follow the 0.4 m limit")],
   [t("Rules"),t("PP 71/2014, PP 57/2016, Permen LHK P.15/2017 and P.16/2017 (peraturan.go.id)"),t("text"),t("as published"),t("Read in full for the terms in Rules and monitoring; other instruments not searched")]];
  $("#src").innerHTML="<thead><tr><th class='l'>"+t("Layer")+"</th><th class='l'>"+t("Source")+"</th><th class='l'>"+t("Grid and unit")+"</th><th class='l'>"+t("Period")+"</th><th class='l'>"+t("Note")+"</th></tr></thead><tbody>"+S.map(r=>"<tr>"+r.map(c=>`<td class="l wrap2">${c}</td>`).join("")+"</tr>").join("")+"</tbody>";
  $("#foot").textContent=t("Built {d} from the per-KHG outputs of the licence-edge investigation. Associations by position on the dome, not statements about responsibility. Dataset records: re-peat/sites/data_catalog.csv.",{d:DATA.built})}

function renderAll(){tiles();forest();renderDetail();modelChart();s1Chart();sitChart();ktable();rules();sources()}
function setLang(l){LANG=l;setSeg("#lang",l);applyStatic();renderAll();mapLabels();location.hash=l==="id"?"l=id":""}
$("#c-khg").innerHTML=KH.map(k=>`<option value="${k.code}">${k.name}</option>`).join("");$("#c-khg").value=state.code;$("#c-khg").onchange=e=>selectKhg(e.target.value);
seg("#lang",setLang);
seg("#c-conf",v=>{state.conf=v;if(map&&mapReady)paint();tiles();forest();renderDetail();ktable()});
seg("#c-canal",v=>{state.canal=v;tiles();forest()});
seg("#c-dry",v=>{state.dry=+v;bandChart(BY[state.code])});
seg("#c-cov",v=>{state.cov=+v;paint()});
seg("#c-pol",v=>{state.pol=v;s1Chart()});
$("#theme").onclick=()=>{document.documentElement.dataset.theme=isDark()?"light":"dark";if(map&&mapReady){map.setStyle(isDark()?BASE_D:BASE_L,{diff:false});map.once("style.load",()=>{overlays();mapLabels();paint()})}};
LANG=(location.hash.includes("l=id")||(!location.hash&&(navigator.language||"").toLowerCase().startsWith("id")))?"id":"en";
setSeg("#lang",LANG);if(LANG==="id")applyStatic();
renderAll();
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(()=>{forest();bandChart(BY[state.code]);yearChart(BY[state.code]);modelChart();s1Chart();sitChart()},150)});
