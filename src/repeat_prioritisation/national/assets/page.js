// Shared helpers of the stand-alone pages (KHG table, method): language, theme, numbers, tooltips, navigation.
/*I18N*/
let LANG="en";
const t=(s,v)=>{let r=LANG==="id"&&ID[s]!==undefined?ID[s]:s;if(v)r=r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m);return r};
const loc=()=>LANG==="id"?"id-ID":"en-GB";
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
const tipAttr=h=>h?' data-tip="'+String(h).replace(/&/g,"&amp;").replace(/"/g,"&quot;")+'"':"";
const dsep=s=>LANG==="id"?s.replace(/\./g,"#").replace(/,/g,".").replace(/#/g,","):s;
const fmt=(v,nd=2)=>{if(v==null||!isFinite(v))return t("n/a");if(Math.abs(v)>=1000)return Math.round(v).toLocaleString(LANG==="id"?"id-ID":"en");
  let s=(+v).toFixed(nd);if(s.indexOf(".")>=0)s=s.replace(/0+$/,"").replace(/\.$/,"");return dsep(s)};
const fx=(v,nd=2)=>v==null||!isFinite(v)?t("n/a"):dsep((+v).toFixed(nd));
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PAGES=[["dashboard.html","KHG priority"],["khg_table.html","KHG table"],["fire.html","Fire by land status"],["method.html","Method"]];
function navHtml(cur){return PAGES.map(([h,l])=>`<a href="${h}" data-p="${h}" class="${h===cur?"on":""}">${esc(t(l))}</a>`).join("")}
function navHrefs(){const th=document.documentElement.dataset.theme;$$("nav.nav a[data-p]").forEach(a=>a.href=`${a.dataset.p}#l=${LANG}${th?"&t="+th:""}`)}
const tipEl=()=>document.getElementById("tip");
function showTip(e,html){const el=tipEl();if(html!==undefined)el.innerHTML=html;el.style.display="block";const w=el.offsetWidth,h=el.offsetHeight;
  let x=e.clientX+14,y=e.clientY+14;if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;el.style.left=Math.max(4,x)+"px";el.style.top=Math.max(4,y)+"px"}
function hideTip(){tipEl().style.display="none"}
{const find=e=>e.target.closest?e.target.closest("[data-tip]"):null;
  document.addEventListener("mouseover",e=>{const el=find(e);if(el)showTip(e,el.dataset.tip)});
  document.addEventListener("mousemove",e=>{const el=find(e);if(el)showTip(e,el.dataset.tip)});
  document.addEventListener("mouseout",e=>{const el=find(e);if(el&&!(e.relatedTarget&&el.contains(e.relatedTarget)))hideTip()})}
function readLangTheme(h){LANG=h.get("l")==="id"||h.get("l")==="en"?h.get("l"):((navigator.language||"").toLowerCase().startsWith("id")?"id":"en");
  if(h.get("t")==="dark"||h.get("t")==="light")document.documentElement.dataset.theme=h.get("t")}
function topBar(cur,onChange){
  const lg=$("#lang");lg.innerHTML=[["en","EN"],["id","ID"]].map(([v,x])=>`<button type="button" data-v="${v}" class="${v===LANG?"on":""}">${x}</button>`).join("");
  $$("#lang button").forEach(b=>b.onclick=()=>{LANG=b.dataset.v;onChange()});
  $("#theme-btn").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";onChange()};
  $("nav.nav").innerHTML=navHtml(cur);navHrefs();
  document.documentElement.lang=LANG;$$("[data-i18n]").forEach(el=>{el.textContent=t(el.dataset.i18n)})}
