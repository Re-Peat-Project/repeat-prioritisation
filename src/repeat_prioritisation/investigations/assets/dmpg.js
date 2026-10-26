"use strict";
const $=s=>document.querySelector(s);
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const pc=v=>v==null?"n/a":Math.round(100*v)+"%";
const f2=v=>v==null||!isFinite(v)?"n/a":(+v).toFixed(2);
const tip=$("#tip");
const showTip=(h,e)=>{tip.innerHTML=h;tip.style.display="block";const r=tip.getBoundingClientRect();
  tip.style.left=Math.min(innerWidth-r.width-8,e.clientX+14)+"px";tip.style.top=Math.max(8,e.clientY-r.height-10)+"px"};
const hideTip=()=>{tip.style.display="none"};
const D=DATA;

// lines on one axis; o.series=[{name,col,data:[[x,y]]}], o.band={col,data:[[x,lo,hi]]}, o.ref={y,label},
// o.span={x0,x1,label}, o.log, o.ydom, o.yfmt, o.unit; end labels name each series, hover lists every value
function lines(host,o){
  const W=host.clientWidth||320,H=o.h||190,m={l:42,r:o.endLab?92:16,t:18,b:22};host.innerHTML="";
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${H}`).attr("height",H);
  const xs=[...new Set(o.series.flatMap(s=>s.data.map(d=>d[0])))].sort((a,b)=>a-b);
  const x=d3.scaleLinear(o.xdom||d3.extent(xs),[m.l,W-m.r]);
  let vals=o.series.flatMap(s=>s.data.map(d=>d[1])).concat(o.band?o.band.data.flatMap(d=>[d[1],d[2]]):[]).concat(o.ref?[o.ref.y]:[]).filter(v=>v!=null&&isFinite(v)&&(!o.log||v>0));
  const y=o.log?d3.scaleLog([d3.min(vals)/1.15,d3.max(vals)*1.15],[H-m.b,m.t]):d3.scaleLinear(o.ydom||[0,d3.max(vals)*1.05],[H-m.b,m.t]).nice(4);
  const ticks=o.log?[.25,.5,1,2,4,8].filter(v=>v>=y.domain()[0]&&v<=y.domain()[1]):y.ticks(4);
  const yf=o.yfmt||(v=>d3.format("~g")(v));
  if(o.span){const g=svg.append("g");g.append("rect").attr("x",x(o.span.x0)).attr("width",Math.max(1,x(o.span.x1)-x(o.span.x0))).attr("y",m.t).attr("height",H-m.t-m.b).attr("fill",css("--ink")).attr("opacity",.07);
    g.append("text").attr("x",(x(o.span.x0)+x(o.span.x1))/2).attr("y",m.t-5).attr("text-anchor","middle").attr("fill",css("--muted")).attr("font-size",10.5).text(o.span.label)}
  svg.append("g").attr("class","gridl").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickSize(-(W-m.l-m.r)).tickFormat(""));
  svg.append("g").attr("class","axis").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).tickValues(ticks).tickSize(0).tickPadding(6).tickFormat(yf)).select("path").remove();
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(Math.min(7,xs.length)).tickFormat(d3.format("d")).tickSize(3));
  if(o.band){const b=o.band.data.filter(d=>d[1]>0&&d[2]>0);svg.append("path").datum(b).attr("d",d3.area().x(d=>x(d[0])).y0(d=>y(d[1])).y1(d=>y(d[2]))).attr("fill",css(o.band.col)).attr("opacity",.18)}
  if(o.ref){svg.append("line").attr("x1",m.l).attr("x2",W-m.r).attr("y1",y(o.ref.y)).attr("y2",y(o.ref.y)).attr("stroke",css("--ink2")).attr("stroke-width",1).attr("stroke-dasharray","4 3");
    svg.append("text").attr("x",m.l+4).attr("y",y(o.ref.y)-5).attr("fill",css("--ink2")).attr("font-size",11).text(o.ref.label)}
  const line=d3.line().defined(d=>d[1]!=null&&isFinite(d[1])).x(d=>x(d[0])).y(d=>y(d[1]));
  o.series.forEach(s=>{svg.append("path").datum(s.data).attr("d",line).attr("fill","none").attr("stroke",css(s.col)).attr("stroke-width",2).attr("stroke-linejoin","round");
    const last=[...s.data].reverse().find(d=>d[1]!=null);
    if(last)svg.append("circle").attr("cx",x(last[0])).attr("cy",y(last[1])).attr("r",3.5).attr("fill",css(s.col)).attr("stroke",css("--surface")).attr("stroke-width",1.5);
    if(o.endLab&&last)svg.append("text").attr("x",x(last[0])+7).attr("y",y(last[1])+4).attr("fill",css("--ink2")).attr("font-size",11).text(s.name)});
  (o.points||[]).forEach(p=>svg.append("circle").attr("cx",x(p[0])).attr("cy",y(p[1])).attr("r",4.5).attr("fill",css(p[2])).attr("stroke",css("--surface")).attr("stroke-width",1.5));
  const step=(x.range()[1]-x.range()[0])/Math.max(1,xs.length-1);
  const vl=svg.append("line").attr("y1",m.t).attr("y2",H-m.b).attr("stroke",css("--muted")).attr("stroke-width",.8).style("display","none");
  svg.append("g").selectAll("rect").data(xs).join("rect").attr("x",d=>x(d)-step/2).attr("width",step).attr("y",m.t).attr("height",H-m.t-m.b).attr("fill","transparent")
    .on("mousemove",(e,yr)=>{vl.style("display",null).attr("x1",x(yr)).attr("x2",x(yr));showTip(`<b>${yr}</b>`+o.tip(yr),e)}).on("mouseleave",()=>{vl.style("display","none");hideTip()});
}

// post/pre ratio with interval per row, log x, 1 = no change
function forest(host,rows){
  const W=host.clientWidth||600,rh=30,m={l:Math.min(420,W*.42),r:130,t:26,b:26},H=m.t+m.b+rh*rows.length;host.innerHTML="";
  const svg=d3.select(host).append("svg").attr("viewBox",`0 0 ${W} ${H}`).attr("height",H);
  const ext=[d3.min(rows,r=>r.lo),d3.max(rows,r=>r.hi)],x=d3.scaleLog([Math.min(ext[0],.5)/1.1,Math.max(ext[1],2)*1.1],[m.l,W-m.r]);
  const ticks=[.25,.5,.75,1,1.5,2,4].filter(v=>v>=x.domain()[0]&&v<=x.domain()[1]);
  svg.append("g").attr("class","gridl").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(ticks).tickSize(-(H-m.t-m.b)).tickFormat(""));
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(ticks).tickFormat(d3.format("~g")).tickSize(3));
  svg.append("line").attr("x1",x(1)).attr("x2",x(1)).attr("y1",m.t-6).attr("y2",H-m.b).attr("stroke",css("--ink2")).attr("stroke-dasharray","4 3");
  svg.append("text").attr("x",x(1)-6).attr("y",m.t-10).attr("text-anchor","end").attr("fill",css("--muted")).attr("font-size",11).text("← gap shrank");
  svg.append("text").attr("x",x(1)+6).attr("y",m.t-10).attr("fill",css("--muted")).attr("font-size",11).text("gap grew →");
  rows.forEach((r,i)=>{const cy=m.t+rh*i+rh/2,g=svg.append("g");
    g.append("text").attr("x",8).attr("y",cy+4).attr("fill",css("--ink")).attr("font-size",12.5).text(r.label);
    g.append("text").attr("x",W-m.r+14).attr("y",cy+4).attr("fill",css("--ink2")).attr("font-size",12).text(`${f2(r.ratio)} (${f2(r.lo)}–${f2(r.hi)})`);
    g.append("line").attr("x1",x(r.lo)).attr("x2",x(r.hi)).attr("y1",cy).attr("y2",cy).attr("stroke",css("--dpg")).attr("stroke-width",2);
    g.append("circle").attr("cx",x(r.ratio)).attr("cy",cy).attr("r",5).attr("fill",css("--dpg")).attr("stroke",css("--surface")).attr("stroke-width",1.5);
    g.append("rect").attr("x",0).attr("y",cy-rh/2).attr("width",W).attr("height",rh).attr("fill","transparent")
      .on("mousemove",e=>showTip(`<b>${r.label}</b><br>${r.what}<br>${f2(r.ratio)} <span>(95% interval ${f2(r.lo)}–${f2(r.hi)})</span>`,e)).on("mouseleave",hideTip)});
}

function legend(host,items){host.innerHTML=items.map(([n,c])=>`<span><i style="border-color:${css(c)}"></i>${n}</span>`).join("")}
function card(host,title){const d=document.createElement("div");d.className="card";d.innerHTML=`<h3>${title}</h3><div></div>`;host.appendChild(d);return d.lastChild}

function render(){
  $("#sub").textContent=`Evidence for the World Bank question · ${D.n_dpg} DPG villages of the BRG atlas (mapped June 2018 to July 2019) against ${D.n_ctl} other Bluebook target villages · generated ${D.generated}`;
  $("#verdicts").innerHTML=D.verdicts.map(v=>`<div class="card verdict"><div class="t">${v.title}</div>${v.figure?`<div class="v">${v.figure}</div>`:""}<div class="x">${v.text}</div></div>`).join("");

  // 1. no fire
  $("#lead1").textContent=D.lead1;
  legend($("#leg1"),[["DPG villages","--dpg"],["Other target villages","--ctl"]]);
  const nf=$("#nofire");nf.innerHTML="";
  D.no_fire_panels.forEach(p=>{const h=card(nf,p.title);
    lines(h,{series:[{name:"DPG",col:"--dpg",data:p.dpg},{name:"other",col:"--ctl",data:p.ctl}],ydom:[0,100],yfmt:v=>v+"%",ref:{y:99,label:"KLH: 99%"},
      points:p.points,xdom:p.xdom,tip:yr=>{const a=p.dpg.find(d=>d[0]===yr),b=p.ctl.find(d=>d[0]===yr);return a?`<br>DPG villages: ${Math.round(a[1])}%<br>Other target villages: ${Math.round(b[1])}%`:""}})});

  // 2. rates
  legend($("#leg2"),[["DPG villages","--dpg"],["Other target villages","--ctl"]]);
  const rt=$("#rates");rt.innerHTML="";
  [["viirs","VIIRS hotspots per km2 of peat",v=>d3.format("~g")(v),v=>f2(v)],["burned","Peat burned, % of peat",v=>v+"%",v=>(+v).toFixed(1)+"%"]].forEach(([k,title,yf,vf])=>{const h=card(rt,title),r=D.rates[k];
    lines(h,{series:[{name:"DPG",col:"--dpg",data:r.map(d=>[d[0],d[1]])},{name:"other",col:"--ctl",data:r.map(d=>[d[0],d[2]])}],yfmt:yf,
      tip:yr=>{const d=r.find(q=>q[0]===yr);return d?`<br>DPG villages: ${vf(d[1])}<br>Other target villages: ${vf(d[2])}`:""}})});

  // 3. ratios
  $("#lead3").textContent=D.lead3;
  const ra=$("#ratios");ra.innerHTML="";
  [["viirs","VIIRS hotspots"],["burned","Burned peat"]].forEach(([k,title])=>{const h=card(ra,`${title}: DPG rate ÷ other villages' rate`),r=D.rr[k];
    lines(h,{series:[{name:"ratio",col:"--dpg",data:r.map(d=>[d[0],d[1]])}],band:{col:"--dpg",data:r.map(d=>[d[0],d[2],d[3]])},log:true,yfmt:v=>v+"×",
      ref:{y:1,label:"1× = same rate"},span:{x0:2018.45,x1:2019.55,label:"BRG mapping"},
      tip:yr=>{const d=r.find(q=>q[0]===yr);return d?`<br>${f2(d[1])}× <span>(95% interval ${f2(d[2])}–${f2(d[3])})</span>`:""}})});

  // 4. forest
  $("#lead4").textContent=D.lead4;
  forest($("#forest"),D.forest);

  // table
  const T=D.table,th=T.cols.map((c,i)=>`<th data-i="${i}">${c}</th>`).join("");
  const draw=(rows)=>{$("#table").innerHTML=`<table><thead><tr>${th}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    document.querySelectorAll("#table th").forEach(h=>h.onclick=()=>{const i=+h.dataset.i,dir=h.dataset.d==="a"?-1:1;draw([...rows].sort((a,b)=>dir*String(a[i]).localeCompare(String(b[i]),"en",{numeric:true})));})};
  draw(T.rows);
  ["method","limits","data"].forEach(k=>{$("#"+k).innerHTML=D[k].map(s=>`<li>${s}</li>`).join("")});
}
// ---------------------------------------------------------------- map
const COLOR_PROPS=["background-color","fill-color","fill-outline-color","line-color","text-color","text-halo-color"];
const DROP=/^(building|aeroway.*|railway.*|highway-shield.*|road_shield.*|airport|road_pier|road_area_pier|tunnel_.*|highway_path|highway-name-path|highway-name-minor)$/;
function mapColors(v,fn,prop){if(typeof v==="string"&&/^(#|rgb|hsl)/.test(v))return fn(v,prop);if(Array.isArray(v))return v.map(x=>mapColors(x,fn,prop));
  if(v&&typeof v==="object"){const o={};for(const k in v)o[k]=mapColors(v[k],fn,prop);return o}return v}
function darkColor(c,prop){const h=d3.hsl(c);if(!isFinite(h.h))h.h=0;const l=prop==="text-color"?1-h.l:.075+.27*(1-h.l);return d3.hsl(h.h,h.s*.45,Math.min(.95,l),h.opacity).formatRgb()}
const BASE_LIGHT=(()=>{const s=JSON.parse(JSON.stringify(D.style));s.layers=s.layers.filter(l=>!DROP.test(l.id));return s})();
const BASE_DARK=(()=>{const s=JSON.parse(JSON.stringify(BASE_LIGHT));for(const l of s.layers)for(const p of COLOR_PROPS)if(l.paint&&l.paint[p]!==undefined)l.paint[p]=mapColors(l.paint[p],darkColor,p);return s})();
const isDark=()=>{const th=document.documentElement.dataset.theme;return th?th==="dark":matchMedia("(prefers-color-scheme:dark)").matches};
function restyleBase(){const s=isDark()?BASE_DARK:BASE_LIGHT;for(const l of s.layers){if(!map.getLayer(l.id)||!l.paint)continue;for(const p of COLOR_PROPS)if(l.paint[p]!==undefined)try{map.setPaintProperty(l.id,p,l.paint[p])}catch(e){}}}
const MODES=[["group","DPG or other village"],["b","Hotspots 2019 and 2023"],["u","Peat burned 2019-2025"]];
const MUNIT={b:"VIIRS hotspots per km2 of peat per year, mean of the dry years 2019 and 2023",u:"% of the peat burned per year, mean 2019-2025"};
let map=null,mapReady=false,mode="group";
const V=D.map.villages;
const breaks=k=>{const v=V.map(x=>x[k]).filter(x=>x!=null&&x>0).sort((a,b)=>a-b);return [.2,.4,.6,.8].map(q=>d3.quantileSorted(v,q))};
const BR={b:breaks("b"),u:breaks("u")};
const fmtv=(v,k)=>v==null?"n/a":k==="u"?(+v).toFixed(1)+"%":(+v).toFixed(2);
function fillExpr(){
  if(mode==="group")return ["case",["==",["get","d"],1],css("--dpg"),css("--ctl")];
  const ramp=d3.interpolateRgb(css("--ramp0"),css("--ramp1")),b=BR[mode];
  return ["case",["==",["get",mode],null],css("--nodata"),["==",["get",mode],0],ramp(0),["step",["get",mode],ramp(.2),b[0],ramp(.4),b[1],ramp(.6),b[2],ramp(.8),b[3],ramp(1)]]}
function paintMap(){if(!mapReady)return;restyleBase();
  map.setPaintProperty("vil","fill-color",fillExpr());map.setPaintProperty("vil","fill-opacity",mode==="group"?["case",["==",["get","d"],1],.75,.35]:.85);
  map.setPaintProperty("dpg-line","line-color",css("--ink"));map.setLayoutProperty("dpg-line","visibility",mode==="group"?"none":"visible");
  map.setPaintProperty("khg-line","line-color",css("--ink"));map.setPaintProperty("vil-edge","line-color",css("--surface"));
  const k=$("#mapkeys");
  if(mode==="group")k.innerHTML=`<span><b style="background:${css("--dpg")}"></b>DPG village (BRG atlas)</span><span><b style="background:${css("--ctl")};opacity:.6"></b>Other target village</span><span><b style="border:2px dashed ${css("--ink")};background:none;height:8px"></b>KHG with DPG villages</span>`;
  else{const ramp=d3.interpolateRgb(css("--ramp0"),css("--ramp1")),b=BR[mode],lab=[`0`,`< ${fmtv(b[0],mode)}`,`${fmtv(b[0],mode)}–${fmtv(b[1],mode)}`,`${fmtv(b[1],mode)}–${fmtv(b[2],mode)}`,`${fmtv(b[2],mode)}–${fmtv(b[3],mode)}`,`> ${fmtv(b[3],mode)}`];
    k.innerHTML=`<span>${MUNIT[mode]}:</span>`+lab.map((l,i)=>`<span><b style="background:${ramp(i/5)}"></b>${l}</span>`).join("")+`<span><b style="background:${css("--nodata")}"></b>little or no peat</span><span><b style="border:2px solid ${css("--ink")};background:none;height:8px"></b>DPG village</span>`}}
function initMap(){
  const seg=$("#mapmode");seg.innerHTML="";MODES.forEach(([k,l])=>{const b=document.createElement("button");b.type="button";b.textContent=l;b.className=k===mode?"on":"";
    b.onclick=()=>{mode=k;[...seg.children].forEach(x=>x.classList.toggle("on",x===b));paintMap()};seg.appendChild(b)});
  const b=D.map.bounds;
  map=new maplibregl.Map({container:"map",style:BASE_LIGHT,bounds:[[b[0],b[1]],[b[2],b[3]]],fitBoundsOptions:{padding:20},attributionControl:{compact:true}});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
  map.addControl(new maplibregl.ScaleControl({unit:"metric"}),"bottom-left");
  map.on("load",()=>{
    const before=(map.getStyle().layers.find(l=>l.type==="symbol")||{}).id;
    const fc=(arr,props)=>({type:"FeatureCollection",features:arr.map((x,i)=>({type:"Feature",id:i,properties:props(x),geometry:{type:"MultiPolygon",coordinates:x.r}}))});
    map.addSource("vil",{type:"geojson",data:fc(V,x=>({n:x.n,d:x.d,k:x.k,p:x.p,a:x.a,b:x.b,u:x.u}))});
    map.addSource("khg",{type:"geojson",data:fc(D.map.khg,x=>({n:x.n}))});
    map.addLayer({id:"vil",type:"fill",source:"vil",paint:{"fill-color":"#888","fill-opacity":.6}},before);
    map.addLayer({id:"vil-edge",type:"line",source:"vil",paint:{"line-color":"#fff","line-width":.4,"line-opacity":.6}},before);
    map.addLayer({id:"dpg-line",type:"line",source:"vil",filter:["==",["get","d"],1],paint:{"line-width":2.2}},before);
    map.addLayer({id:"khg-line",type:"line",source:"khg",paint:{"line-width":1.4,"line-dasharray":[3,2]}},before);
    map.on("mousemove","vil",e=>{const p=e.features[0].properties;map.getCanvas().style.cursor="pointer";
      showTip(`<b>${p.n}</b><br><span>${p.d==1?"DPG village (BRG atlas)":"Other target village"}${p.k?" · "+p.k:""}</span><br>Peat: ${p.p==null||p.p==="null"?"n/a":(+p.p).toFixed(1)+" km2"}`+
        `<br>Hotspots per km2 of peat: ${fmtv(p.a==="null"?null:p.a,"b")} in 2014-15, ${fmtv(p.b==="null"?null:p.b,"b")} in 2019 and 2023<br>Peat burned per year 2019-2025: ${fmtv(p.u==="null"?null:p.u,"u")}`,e.originalEvent)});
    map.on("mouseleave","vil",()=>{map.getCanvas().style.cursor="";hideTip()});
    mapReady=true;paintMap()});
}
initMap();
$("#theme").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";render();paintMap()};
let rz;addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(render,150)});
render();
