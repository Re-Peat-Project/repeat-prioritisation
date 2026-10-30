"use strict";
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];

// ---------- language: English text is the key; Bahasa Indonesia in ID
let LANG="en";
const MISS=new Set();
const t=(s,v)=>{let r=s;if(LANG==="id"){if(ID[s]!==undefined)r=ID[s];else MISS.add(s)}if(v)r=r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m);return r};
const locEN=d3.formatLocale({decimal:".",thousands:",",grouping:[3],currency:["",""]}), locID=d3.formatLocale({decimal:",",thousands:".",grouping:[3],currency:["",""]});
const Lc=()=>LANG==="id"?locID:locEN;
const fmt=v=>v==null?"–":Lc().format(",.0f")(v), f1=v=>v==null||!isFinite(v)?"?":Lc().format(".1f")(v), f2=v=>v==null?"–":Lc().format(".2f")(v);
const nf=v=>LANG==="id"?String(v).replace(".",","):String(v);
const tb=s=>LANG==="id"?s.replace(" to "," sampai "):s;                                  // band labels from the data
const tc=s=>LANG==="id"?s.replace(" to "," sampai "):s;

// static text of the page: remember the English once, translate on language change
const STATIC=[];
(function collect(){const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest("script,style")||!/[A-Za-z]{2}/.test(n.nodeValue)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
  let n;while(n=w.nextNode())STATIC.push({n,en:n.nodeValue.trim(),pre:n.nodeValue.match(/^\s*/)[0],post:n.nodeValue.match(/\s*$/)[0]});
  $$("[data-tip],[placeholder],[aria-label]").forEach(e=>["data-tip","placeholder","aria-label"].forEach(a=>{if(e.hasAttribute(a))STATIC.push({e,a,en:e.getAttribute(a)})}))})();
function applyStatic(){STATIC.forEach(o=>{if(o.n)o.n.nodeValue=o.pre+t(o.en)+o.post;else o.e.setAttribute(o.a,t(o.en))});document.documentElement.lang=LANG;document.title=t("Do licence areas burn less?")}

const KH=DATA.khg, BY={}; KH.forEach(k=>BY[k.code]=k);
const withEc=KH.filter(k=>k.ec), Y=DATA.years.length;
const state={code:withEc[0].code,conf:"all",pos:"all",view:"band",scale:"own",filt:null,layer:"band"};
const IN="var(--lo)",OUT="var(--hi)";
const READ={"outside higher":{c:"var(--hi)",l:"Outside burns more"},"inside higher":{c:"var(--lo)",l:"Inside burns more"},"no clear difference":{c:"var(--none)",l:"No clear difference"}};
const PL={all:"Everywhere",foot:"Foot",slope:"Slope",crest:"Crest"};
const DRY=new Set(DATA.dry_years);

// one comparison row per KHG, for the chosen dome position and detection confidence
const ecR=(k,pos=state.pos)=>{if(!k.ec)return null;const a=k.ec.find(r=>r.position===pos&&r.canal==="all");if(!a)return null;if(state.conf==="all")return a;const h=k.ec_h.find(r=>r.position===pos&&r.canal==="all");return h?{...a,...h}:null};
const inRate=e=>100*e.hotspots_inside/(e.inside_km2*Y), outRate=e=>100*e.hotspots_outside/(e.outside_km2*Y);
const bandRate=r=>state.conf==="high"?100*r.high_hotspots/(r.peat_km2*Y):r.hs_per_100km2_yr;
function ratioText(e){const r=e.rate_ratio_out_over_in;if(r==null)return t("No hotspots inside");
  return r>=1?t("Outside {x}× inside",{x:f1(r)})+" · "+t("range {a}–{b}×",{a:f1(e.lo_block),b:f1(e.hi_block)}):t("Inside {x}× outside",{x:f1(1/r)})+" · "+t("range {a}–{b}×",{a:e.hi_block?f1(1/e.hi_block):"?",b:e.lo_block?f1(1/e.lo_block):"?"})}

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

// ---------- verdict
function verdict(){
  const rs=withEc.map(k=>ecR(k)).filter(Boolean),n=rs.length,cnt={};
  Object.keys(READ).forEach(r=>cnt[r]=rs.filter(e=>e.reading===r).length);
  const o=cnt["outside higher"],i=cnt["inside higher"],z=cnt["no clear difference"];
  let h,p;
  if(o>=2*n/3){h=t("Land outside licence areas burns more.");p=t("In {a} of {n} peat areas there is clearly more fire just outside the licence edge than just inside.",{a:o,n})}
  else if(i>=2*n/3){h=t("Licence areas burn more than the land beside them.");p=t("In {a} of {n} peat areas there is clearly more fire just inside the licence edge than just outside.",{a:i,n})}
  else{h=t("No consistent difference: licence areas do not clearly burn less.");p=t("Just outside the licence edge there is clearly more fire in {o} of {n} peat areas, clearly less in {i}, and no clear difference in the other {z}.",{o,i,z,n})}
  $("#verdict").innerHTML=`<h2>${h}</h2><p>${p}</p><div class="cnt">`+
    Object.keys(READ).map(r=>`<button data-r="${r}" class="${state.filt===r?"on":""}" style="--c:${READ[r].c}"><span class="n">${cnt[r]}</span><span class="l">${t(READ[r].l)}</span></button>`).join("")+
    `</div><div class="key"><span><i style="background:${IN}"></i>${t("Inside a licence area")}</span><span><i style="background:${OUT}"></i>${t("Outside")}</span><span>${t("Click a number to show only those peat areas.")}</span></div>`;
  $$("#verdict .cnt button").forEach(b=>b.onclick=()=>{state.filt=state.filt===b.dataset.r?null:b.dataset.r;verdict();panels()})}

// ---------- small multiples
const GROUPS=[["inside, more than 0.5 km from the edge",0],["inside, within 0.5 km of the edge",0],["outside, within 0.5 km",1],["outside, 0.5 to 2 km",1]];
function bandPts(k){return k.bp.filter(r=>r.position===state.pos&&r.peat_km2>=2).sort((a,b)=>a.band_i-b.band_i).map(r=>({i:r.band_i,v:bandRate(r),r}))}
function yearPts(k){const rows=k.by.filter(r=>r.position===state.pos),out=[[],[]];
  DATA.years.forEach(y=>[0,1].forEach(z=>{const rs=rows.filter(r=>r.year===y&&(GROUPS.find(g=>g[0]===r.group)||[0,-1])[1]===z),a=d3.sum(rs,r=>r.peat_km2),h=d3.sum(rs,r=>state.conf==="high"?r.high_hotspots:r.hotspots);if(a>=2)out[z].push({y,v:100*h/a,h,a})}));return out}
function svgBase(host,w,h){return d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`)}
function yAxis(svg,y,m,w,ymax){[0,ymax].forEach(v=>{svg.append("line").attr("class","gridl").attr("x1",m.l).attr("x2",w-m.r).attr("y1",y(v)).attr("y2",y(v));svg.append("text").attr("x",m.l-5).attr("y",y(v)+4).attr("text-anchor","end").text(nf(+v.toPrecision(2)))})}
function drawBand(host,k,ymax){
  const w=280,h=150,m={l:34,r:6,t:8,b:22},pts=bandPts(k),svg=svgBase(host,w,h);
  const x=d3.scalePoint().domain(d3.range(8)).range([m.l,w-m.r]).padding(.35),y=d3.scaleLinear().domain([0,ymax*1.05]).range([h-m.b,m.t]),mid=(x(3)+x(4))/2;
  svg.append("rect").attr("x",m.l).attr("width",mid-m.l).attr("y",m.t).attr("height",h-m.b-m.t).attr("fill",IN).attr("opacity",.07);
  svg.append("rect").attr("x",mid).attr("width",w-m.r-mid).attr("y",m.t).attr("height",h-m.b-m.t).attr("fill",OUT).attr("opacity",.07);
  yAxis(svg,y,m,w,ymax);
  svg.append("line").attr("class","ref").attr("x1",mid).attr("x2",mid).attr("y1",m.t).attr("y2",h-m.b);
  svg.append("text").attr("x",m.l).attr("y",h-6).text(t("inside"));svg.append("text").attr("x",mid).attr("y",h-6).attr("text-anchor","middle").text(t("edge"));svg.append("text").attr("x",w-m.r).attr("y",h-6).attr("text-anchor","end").text(t("outside"));
  const seg_=(a,c)=>{if(a.length>1)svg.append("path").attr("d",d3.line().x(p=>x(p.i)).y(p=>y(p.v))(a)).attr("fill","none").attr("stroke",c).attr("stroke-width",2)};
  const pi=pts.filter(p=>p.i<=3),po=pts.filter(p=>p.i>=4);seg_(pi,IN);seg_(po,OUT);
  if(pi.length&&po.length)svg.append("path").attr("d",d3.line().x(p=>x(p.i)).y(p=>y(p.v))([pi.at(-1),po[0]])).attr("fill","none").attr("stroke","var(--muted)").attr("stroke-dasharray","3 3");
  pts.forEach(p=>{const c=p.i<=3?IN:OUT,core=p.i>=2&&p.i<=5;
    svg.append("circle").attr("cx",x(p.i)).attr("cy",y(p.v)).attr("r",core?3.2:2.4).attr("fill",core?c:"var(--surface)").attr("stroke",c).attr("stroke-width",1.6)
     .on("mousemove",e=>showTip(`<b>${k.name}</b><br>${tb(p.r.band)} ${p.i<=3?t("inside"):t("outside")}<br>${t("{x} per 100 km² of peat and year",{x:f2(p.v)})}<br>${t("{n} hotspots on {a} km² of peat",{n:fmt(state.conf==="high"?p.r.high_hotspots:p.r.hotspots),a:fmt(p.r.peat_km2)})}`,e)).on("mouseleave",hideTip)})}
function drawYear(host,k,ymax){
  const w=280,h=150,m={l:34,r:6,t:8,b:22},[a,b]=yearPts(k),svg=svgBase(host,w,h);
  const x=d3.scaleLinear().domain([DATA.years[0],DATA.years.at(-1)]).range([m.l+4,w-m.r-4]),y=d3.scaleLinear().domain([0,ymax*1.05]).range([h-m.b,m.t]),sp=x(DATA.years[0]+1)-x(DATA.years[0]);
  DATA.dry_years.forEach(d=>svg.append("rect").attr("x",x(d)-sp/2).attr("width",sp).attr("y",m.t).attr("height",h-m.b-m.t).attr("fill","var(--wash)"));
  yAxis(svg,y,m,w,ymax);
  [DATA.years[0],2015,2019,2023].forEach(d=>svg.append("text").attr("x",x(d)).attr("y",h-6).attr("text-anchor","middle").text(d));
  [[a,IN,t("inside the licence")],[b,OUT,t("outside, within 2 km")]].forEach(([s,c,lab])=>{if(!s.length)return;
    svg.append("path").attr("d",d3.line().x(p=>x(p.y)).y(p=>y(p.v))(s)).attr("fill","none").attr("stroke",c).attr("stroke-width",2);
    s.forEach(p=>svg.append("circle").attr("cx",x(p.y)).attr("cy",y(p.v)).attr("r",5).attr("fill","transparent")
      .on("mousemove",e=>showTip(`<b>${k.name}</b> · ${p.y}${DRY.has(p.y)?" ("+t("dry year")+")":""}<br>${lab}<br>${t("{x} per 100 km² of peat",{x:f2(p.v)})}<br>${t("{n} hotspots on {a} km² of peat",{n:fmt(p.h),a:fmt(p.a)})}`,e)).on("mouseleave",hideTip))})}
function panels(){
  const host=$("#sm");
  let items=withEc.map(k=>({k,e:ecR(k)})).sort((p,q)=>((q.e&&q.e.rate_ratio_out_over_in)??-1)-((p.e&&p.e.rate_ratio_out_over_in)??-1));
  const total=items.length;if(state.filt)items=items.filter(p=>p.e&&p.e.reading===state.filt);
  const val=state.view==="band"?k=>d3.max(bandPts(k),p=>p.v)||0:k=>{const[a,b]=yearPts(k);return d3.max([...a,...b],p=>p.v)||0};
  const shared=d3.max(items,p=>val(p.k))||1;
  $("#sm-sub").textContent=state.view==="band"?t("Fire per area, by distance from the licence edge ({n} of {m} shown)",{n:items.length,m:total}):t("Fire per area each year, just inside and just outside the licence edge ({n} of {m} shown)",{n:items.length,m:total});
  host.innerHTML=items.map((p,i)=>{const e=p.e,rd=e?READ[e.reading]:null;
    return `<div class="card pn${p.k.code===state.code?" sel":""}" data-code="${p.k.code}"><div class="pn-h"><b>${p.k.name}</b>${rd?`<span class="pill" style="--c:${rd.c}">${t(rd.l)}</span>`:""}</div><div class="pn-sub">${e?ratioText(e):t("Too little peat for a comparison")}</div><div id="pn${i}"></div></div>`}).join("")||`<p class="note">${t("No peat area matches.")}</p>`;
  items.forEach((p,i)=>{const el=$("#pn"+i);if(!p.e){el.innerHTML=`<div class="empty">${t("no data")}</div>`;return}
    const ym=state.scale==="same"?shared:Math.max(val(p.k),1e-6);(state.view==="band"?drawBand:drawYear)(el,p.k,ym)});
  $$("#sm .pn").forEach(c=>c.onclick=()=>{selectKhg(c.dataset.code);$("#s-detail").scrollIntoView({behavior:"smooth"})});
  const no=KH.filter(k=>!k.ec).map(k=>k.name);
  $("#sm-note").textContent=t("Range: where the true difference most likely lies (95%). If the range includes 1× (equal), the difference is not clear. Filled points are the 0–2 km either side that the comparison uses. Click a panel for the map.")+(no.length?" "+t("No licence on peat, so not compared: {n}.",{n:no.join(", ")}):"")}

// ---------- one KHG: lines by dome position, numbers
const POSCOL={foot:"var(--foot)",slope:"var(--slope)",crest:"var(--crest)",all:"var(--ink)"};
function bandChart(k){
  const host=$("#bandchart"),w=Math.max(300,host.clientWidth||600),h=250,m={l:44,r:70,t:12,b:58};
  const rows=k.bp.filter(r=>r.peat_km2>=2),svg=d3.select(host).html("").append("svg").attr("viewBox",`0 0 ${w} ${h}`).attr("height",h);
  const x=d3.scalePoint().domain(d3.range(8)).range([m.l,w-m.r]).padding(.3),y=d3.scaleLinear().domain([0,(d3.max(rows,bandRate)||1)*1.08]).nice().range([h-m.b,m.t]),mid=(x(3)+x(4))/2;
  y.ticks(4).forEach(v=>{svg.append("line").attr("class","gridl").attr("x1",m.l).attr("x2",w-m.r).attr("y1",y(v)).attr("y2",y(v));svg.append("text").attr("x",m.l-6).attr("y",y(v)+4).attr("text-anchor","end").text(nf(v))});
  svg.append("rect").attr("x",m.l).attr("y",m.t).attr("width",mid-m.l).attr("height",h-m.b-m.t).attr("fill",IN).attr("opacity",.07);
  svg.append("rect").attr("x",mid).attr("y",m.t).attr("width",w-m.r-mid).attr("height",h-m.b-m.t).attr("fill",OUT).attr("opacity",.07);
  svg.append("line").attr("class","ref").attr("x1",mid).attr("x2",mid).attr("y1",m.t).attr("y2",h-m.b);
  svg.append("text").attr("x",mid-6).attr("y",m.t+10).attr("text-anchor","end").text(t("inside ◂"));svg.append("text").attr("x",mid+6).attr("y",m.t+10).text(t("▸ outside"));
  DATA.bands.forEach((b,i)=>svg.append("text").attr("transform",`translate(${x(i)},${h-m.b+14}) rotate(-35)`).attr("text-anchor","end").text(tb(b)));
  svg.append("text").attr("x",(m.l+w-m.r)/2).attr("y",h-4).attr("text-anchor","middle").text(t("distance to the licence edge"));
  svg.append("text").attr("x",m.l).attr("y",m.t-2).text(t("hotspots per 100 km² and year"));
  const ends=[];["all",...DATA.pos].forEach(p=>{const pr=rows.filter(r=>r.position===p).sort((a,b)=>a.band_i-b.band_i);if(!pr.length)return;
    svg.append("path").attr("d",d3.line().x(r=>x(r.band_i)).y(r=>y(bandRate(r)))(pr)).attr("fill","none").attr("stroke",POSCOL[p]).attr("stroke-width",p==="all"?2.4:1.8).attr("stroke-dasharray",p==="all"?"5 3":null);
    svg.selectAll(null).data(pr).join("circle").attr("cx",r=>x(r.band_i)).attr("cy",r=>y(bandRate(r))).attr("r",3).attr("fill",POSCOL[p]).attr("stroke","var(--surface)").attr("stroke-width",1.5)
      .on("mousemove",(e,r)=>showTip(`<b>${t(PL[p])}</b> · ${tb(r.band)}<br>${t("{x} per 100 km² of peat and year",{x:f2(bandRate(r))})}<br>${t("{n} hotspots on {a} km² of peat",{n:fmt(state.conf==="high"?r.high_hotspots:r.hotspots),a:fmt(r.peat_km2)})}`,e)).on("mouseleave",hideTip);
    ends.push({p,y:y(bandRate(pr.at(-1))),x:x(pr.at(-1).band_i)+8})});
  ends.sort((a,b)=>a.y-b.y);ends.forEach((e,i)=>{if(i&&e.y<ends[i-1].y+12)e.y=ends[i-1].y+12;svg.append("text").attr("x",e.x).attr("y",e.y+4).style("fill",POSCOL[e.p]).text(t(PL[e.p]))})}
function nums(k){
  const e=ecR(k);if(!e){$("#nums").innerHTML=`<p class="note">${t("No licence on peat in this KHG: no comparison.")}</p>`;return}
  const rows=[{z:t("Inside, 0–2 km"),a:e.inside_km2,h:e.hotspots_inside,v:inRate(e),c:IN},{z:t("Outside, 0–2 km"),a:e.outside_km2,h:e.hotspots_outside,v:outRate(e),c:OUT}];
  $("#nums").innerHTML=tableHTML([{t:t("Zone"),l:1,f:r=>`<span style="color:${r.c}">■</span> ${r.z}`},{t:t("Peat (km²)"),f:r=>fmt(r.a)},{t:t("Hotspots 2012–2025"),f:r=>fmt(r.h)},{t:t("per 100 km² and year"),f:r=>f2(r.v)}],rows)+`<p class="note">${t(PL[state.pos])}: ${ratioText(e)} · ${t(READ[e.reading].l)}</p>`}

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
  band:{t:"Distance to the edge",c:BAND_COL},
  pos:{t:"Dome position",c:["#2a78d6","#eb6834","#1baf7a"]},
  fire:{t:"Fire 2012–25",c:RAMP,u:"hotspots per 100 km² and year, 1 km blocks"}};
const layerLabels=n=>n==="band"?DATA.bands.map(tb):n==="pos"?DATA.pos.map(p=>t(PL[p])):DATA.classes.fire.map(tc);
const hexRGB=h=>{const c=d3.rgb(h);return[c.r,c.g,c.b]};
let map=null,mapReady=false,cache={};
async function gunzip(b64){const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));const s=new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));return new Uint8Array(await new Response(s).arrayBuffer())}
async function layersOf(k){if(cache[k.code])return cache[k.code];const o={};for(const n in k.map.layers)o[n]=await gunzip(k.map.layers[n]);cache[k.code]=o;return o}
const layerKey=()=>state.layer==="fire"&&state.conf==="high"?"fire_h":state.layer;
function mapLabels(){if(!map||!mapReady)return;const code=LANG==="id"?"id":"en";for(const l of map.getStyle().layers){if(l.type==="symbol"&&l.layout&&l.layout["text-field"]!==undefined)try{map.setLayoutProperty(l.id,"text-field",["coalesce",["get","name:"+code],["get","name"]])}catch(e){}}}
function legend(){const def=LAYERS[state.layer],lab=layerLabels(state.layer);
  $("#legend").innerHTML=lab.map((l,i)=>`<span><span class="sw" style="background:${def.c[i]}"></span>${l}</span>`).join("")+(def.u?`<span style="color:var(--muted)">${t(def.u)}</span>`:"")}
async function paint(){
  const k=BY[state.code],L=await layersOf(k),M=k.map,a=L[layerKey()],def=LAYERS[state.layer];
  const cv=document.createElement("canvas");cv.width=M.w;cv.height=M.h;const ctx=cv.getContext("2d"),im=ctx.createImageData(M.w,M.h),rgb=def.c.map(hexRGB);
  for(let i=0;i<a.length;i++){const c=a[i];if(!c)continue;const col=rgb[c-1];if(!col)continue;im.data[4*i]=col[0];im.data[4*i+1]=col[1];im.data[4*i+2]=col[2];im.data[4*i+3]=225}
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
    const fc=(state.conf==="high"?L.fire_h:L.fire)[i];
    ci.innerHTML=`<b>${tb(DATA.bands[b-1])}</b> ${b<=4?t("inside the edge"):t("outside the edge")}<br>${t("dome position")}: ${L.pos[i]?t(PL[DATA.pos[L.pos[i]-1]]):"–"}<br>${t("fire")}: ${fc?tc(DATA.classes.fire[fc-1]):"–"} ${t("per 100 km² and year (1 km block)")}`})}
function layerButtons(){$("#c-layer").innerHTML=Object.keys(LAYERS).map(n=>`<button data-v="${n}" class="${n===state.layer?"on":""}">${t(LAYERS[n].t)}</button>`).join("");seg("#c-layer",v=>{state.layer=v;paint();mapNote()})}
function mapNote(){const M=BY[state.code].map;$("#map-note").textContent=t("Peat cells of 200 m.")+(state.layer==="fire"?" "+t("Fire is shown as 1 km blocks so it can be read; the charts use the 200 m counts."):"")+" "+t("Solid outline: licence areas (2025)")+(M.lic?"":" ("+t("none on peat in this KHG")+")")+"; "+t("dashed: KHG boundary.")}
function mapTo(k){layerButtons();const M=k.map;if(!map){initMap()}else if(mapReady){map.getSource("khg").setData({type:"Feature",geometry:M.khg});map.getSource("lic").setData({type:"Feature",geometry:M.lic||{type:"GeometryCollection",geometries:[]}});map.fitBounds(M.bounds,{padding:30,duration:600});paint()}
  mapNote();legend()}

// ---------- selection and render
function selectKhg(code){state.code=code;renderDetail();panels();$$("#ktbl tbody tr").forEach(tr=>tr.classList.toggle("sel",tr.dataset.code===code))}
function renderDetail(){const k=BY[state.code];
  $("#d-title").textContent=k.name;$("#d-sub").textContent=t("{p} · peat {a} km² · peat under licence {b} km²",{p:k.province,a:fmt(k.peat_km2),b:fmt(k.licence_peat_km2)});
  if(k.ec){bandChart(k);nums(k)}else{$("#bandchart").innerHTML="<p class='note'>"+t("No licence on peat in this KHG: no comparison.")+"</p>";$("#nums").innerHTML=""}
  mapTo(k)}
function tableRows(){return KH.map(k=>{const e=ecR(k);return{code:k.code,n:k.name,pv:k.province,peat:k.peat_km2,lic:k.licence_peat_km2,e,ri:e&&inRate(e),ro:e&&outRate(e),ratio:e&&e.rate_ratio_out_over_in,rd:e?e.reading:"no licence on peat"}})}
function ktable(){
  const rows=tableRows(),rl=r=>r.e?t(READ[r.rd].l):t("No licence on peat");
  const cols=[{t:t("KHG"),l:1,k:"n"},{t:t("Province"),l:1,k:"pv"},{t:t("Peat (km²)"),f:r=>fmt(r.peat),s:r=>r.peat},{t:t("Peat under licence (km²)"),f:r=>fmt(r.lic),s:r=>r.lic},
   {t:t("Inside"),f:r=>r.e?f2(r.ri):"–",s:r=>r.ri,h:t("Hotspots per 100 km² of peat and year, 0–2 km inside the licence edge")},{t:t("Outside"),f:r=>r.e?f2(r.ro):"–",s:r=>r.ro,h:t("Hotspots per 100 km² of peat and year, 0–2 km outside the licence edge")},
   {t:t("Outside ÷ inside"),f:r=>r.ratio==null?"–":f2(r.ratio),s:r=>r.ratio,h:t("Above 1: more fire outside. Below 1: more fire inside.")},{t:t("Range low"),f:r=>r.e?f2(r.e.lo_block):"–",s:r=>r.e?r.e.lo_block:null},{t:t("Range high"),f:r=>r.e?f2(r.e.hi_block):"–",s:r=>r.e?r.e.hi_block:null},
   {t:t("Result"),l:1,f:rl,s:rl}];
  window._tbl=sortable($("#ktbl"),cols,rows,{k:6,dir:-1,click:selectKhg});$("#q").oninput=e=>_tbl.search(e.target.value)}
function csv(){
  const H=["khg","province","dome_position","detections","peat_km2","peat_under_licence_km2","inside_km2","outside_km2","hotspots_inside","hotspots_outside","per_100km2_yr_inside","per_100km2_yr_outside","outside_over_inside","range_low","range_high","result"];
  const L=[H.join(",")];tableRows().forEach(r=>{const e=r.e||{};L.push([`"${r.n}"`,`"${r.pv}"`,state.pos,state.conf==="high"?"high":"nominal+high",r.peat,r.lic,e.inside_km2??"",e.outside_km2??"",e.hotspots_inside??"",e.hotspots_outside??"",r.ri??"",r.ro??"",r.ratio??"",e.lo_block??"",e.hi_block??"",r.rd].join(","))});
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([L.join("\n")],{type:"text/csv"}));a.download="licence_edge_by_khg.csv";a.click()}
function sources(){
  const S=[[t("Licence areas"),t("KLH business licences, 2025 layer"),t("polygons, merged into one outline"),t("2025 layer applied to all years")],
   [t("Peat"),t("GFW composite peat extent"),t("200 m cells"),"—"],
   [t("Fire"),t("VIIRS satellite hotspots (FIRMS)"),t("points; nominal and high confidence, low dropped"),"2012–2025"],
   [t("Dome position"),t("Height above the nearest river, from the best terrain model for the KHG"),t("thirds of the KHG's peat: foot, slope, crest"),"—"]];
  $("#src").innerHTML="<thead><tr><th class='l'>"+t("Layer")+"</th><th class='l'>"+t("Source")+"</th><th class='l'>"+t("Unit")+"</th><th class='l'>"+t("Period")+"</th></tr></thead><tbody>"+S.map(r=>"<tr>"+r.map(c=>`<td class="l wrap2">${c}</td>`).join("")+"</tr>").join("")+"</tbody>";
  $("#check").textContent=t("To check a result: hover any point for its hotspot count and peat area, or download the table as CSV and recompute the ratio. Hotspots are satellite detections, not measured burned area.");
  $("#foot").textContent=t("Built {d}. The page compares position relative to licence areas; it says nothing about who is responsible for a fire.",{d:DATA.built})}

function renderAll(){verdict();panels();renderDetail();ktable();sources()}
function setLang(l){LANG=l;setSeg("#lang",l);applyStatic();renderAll();mapLabels();location.hash=l==="id"?"l=id":""}
seg("#lang",setLang);
seg("#c-conf",v=>{state.conf=v;if(map&&mapReady)paint();verdict();panels();renderDetail();ktable()});
seg("#c-pos",v=>{state.pos=v;verdict();panels();nums(BY[state.code]);ktable()});
seg("#c-view",v=>{state.view=v;panels()});
seg("#c-scale",v=>{state.scale=v;panels()});
$("#csv").onclick=csv;
$("#theme").onclick=()=>{document.documentElement.dataset.theme=isDark()?"light":"dark";if(map&&mapReady){map.setStyle(isDark()?BASE_D:BASE_L,{diff:false});map.once("style.load",()=>{overlays();mapLabels();paint()})}};
LANG=(location.hash.includes("l=id")||(!location.hash&&(navigator.language||"").toLowerCase().startsWith("id")))?"id":"en";
setSeg("#lang",LANG);if(LANG==="id")applyStatic();
renderAll();
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(()=>{const k=BY[state.code];if(k.ec)bandChart(k)},150)});
