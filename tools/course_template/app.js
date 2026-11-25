(function(){
"use strict";
var D=JSON.parse(document.getElementById("data").textContent), KEY="course."+D.id;
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var S={done:{},last:"",cards:{},tasks:{},theme:""};
try{var raw=localStorage.getItem(KEY);if(raw)S=Object.assign(S,JSON.parse(raw))}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}}
var esc=function(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})};
var steps=D.steps,idx={};steps.forEach(function(s,i){idx[s.id]=i});
/* тема */
function theme(t){if(t)document.documentElement.setAttribute("data-theme",t)}
theme(S.theme);
$("#theme").onclick=function(){var dark=document.documentElement.getAttribute("data-theme")==="dark"||(!S.theme&&matchMedia("(prefers-color-scheme:dark)").matches);S.theme=dark?"light":"dark";theme(S.theme);save()};
/* источник */
var STX={ok:"проверено: цитата найдена на странице",noquote:"у утверждения автора нет цитаты: не проверено",notfound:"цитата не найдена на странице: не проверено",numbers:"цитата найдена, но числа не сошлись: не проверено",model:"написано моделью: цитаты книги нет"};
function showEv(k){
 var e=D.ev[k];if(!e)return;var h='<div class="in"><button type="button" id="evx" style="float:right">Закрыть</button>';
 h+='<p><span class="badge b-'+e.a+'">'+e.a+'</span><span class="meta">'+esc(e.k)+(e.st==="ok"?' · <b style="color:var(--a)">✓ проверено</b>':'')+'</span></p>';
 if(e.t)h+='<p>'+esc(e.t)+'</p>';
 if(e.a==="автор"){
  h+='<p class="meta">стр. '+e.p+' PDF · '+STX[e.st]+'</p>';
  if(e.q)h+='<p class="meta">Дословная цитата автора:</p><blockquote>'+(e.x&&e.x[1]?esc(e.x[0])+'<mark>'+esc(e.x[1])+'</mark>'+esc(e.x[2]):esc(e.q))+'</blockquote>';
  if(e.o)h+='<p class="ocr"><b>Правка OCR:</b> '+esc(e.o)+'</p>';
 }else{
  h+='<p class="meta">'+(e.a==="гипотеза"?'Гипотеза модели: в книге этого нет.':'Это слова модели, а не автора: цитаты нет.')+' '+STX.model+'.</p>';
  if(e.o)h+='<p class="meta">Основа: '+esc(e.o)+'.</p>';
  if(e.pp)h+='<p class="meta">Страницы утверждений шага: '+e.pp.join(", ")+' PDF.</p>';
  if(e.basis)h+='<p class="meta">Утверждения шага: '+e.basis.map(function(b){return '<a href="#" data-ev="'+esc(b)+'">'+esc(b.split("#")[1])+'</a>'}).join(", ")+'</p>';
 }
 h+='<p class="meta">Узел: <code>'+esc(e.n)+(e.c?'#'+e.c:'')+'</code></p></div>';
 var p=$("#ev");p.innerHTML=h;p.hidden=false;$("#evx").onclick=function(){p.hidden=true};
}
document.addEventListener("click",function(ev){
 var t=ev.target.closest&&ev.target.closest(".cl,[data-ev]");
 if(t){ev.preventDefault();showEv(t.getAttribute("data-k")||t.getAttribute("data-ev"));return}
 var j=ev.target.closest&&ev.target.closest("[data-jump]");
 if(j){ev.preventDefault();var el=document.getElementById(j.getAttribute("data-jump"));if(el){el.scrollIntoView();el.querySelector("h3").setAttribute("tabindex","-1");el.querySelector("h3").focus()}}
});
document.addEventListener("keydown",function(ev){
 if((ev.key==="Enter"||ev.key===" ")&&ev.target.classList&&ev.target.classList.contains("cl")){ev.preventDefault();showEv(ev.target.getAttribute("data-k"))}
 if(ev.key==="Escape")$("#ev").hidden=true;
});
/* прогресс */
function prog(){var n=Object.keys(S.done).length,t=steps.length,p=Math.round(100*n/t);$("#progbar").style.width=p+"%";$(".prog").setAttribute("aria-valuenow",p);$("#proglbl").textContent="Пройдено шагов: "+n+" из "+t}
/* путь */
function path(){
 var h="",cur="",mins=steps.reduce(function(a,s){return a+s.min},0);
 h+='<p class="meta">Шагов: '+steps.length+', около '+mins+' мин (оценка по объёму текста и числу заданий).</p>';
 if(S.last&&idx[S.last]!==undefined)h+='<p><a href="#/step/'+S.last+'"><b>Продолжить с места, где остановились: шаг '+(idx[S.last]+1)+'</b></a></p>';
 steps.forEach(function(s){if(s.part!==cur){if(cur)h+='</div>';cur=s.part;h+='<div class="part"><h3>'+esc(cur)+'</h3>'}
  h+='<div class="stp"><span class="ck" aria-label="'+(S.done[s.id]?"пройден":"не пройден")+'">'+(S.done[s.id]?"✓":"○")+'</span><a href="#/step/'+s.id+'">'+s.num+'. '+esc(s.short)+'</a><span class="meta">≈'+s.min+' мин</span></div>'});
 $("#pathbox").innerHTML=h+'</div>';
}
/* маршрутизатор */
function route(){
 var hs=location.hash||"#/path",m=hs.match(/^#\/step\/(.+)$/),view;
 $$(".view").forEach(function(v){v.hidden=true;v.classList.remove("printing")});
 if(m&&idx[m[1]]!==undefined){view=document.getElementById("v-"+m[1]);S.last=m[1];save();initStep(m[1])}
 else if(hs==="#/cards"){view=$("#v-cards");cards()}
 else if(hs==="#/summary")view=$("#v-summary");
 else if(hs==="#/map")view=$("#v-map");
 else{view=$("#v-path");path()}
 view.hidden=false;view.classList.add("printing");$("#ev").hidden=true;window.scrollTo(0,0);prog();
 var h=$("h2",view);if(h)h.focus({preventScroll:true});
}
window.addEventListener("hashchange",route);
$("#print").onclick=function(){window.print()};
/* страница шага */
function initStep(id){
 var v=document.getElementById("v-"+id),i=idx[id];if(v.dataset.ready)return;v.dataset.ready=1;
 $$(".tasks",v).forEach(function(box){D.tasks.filter(function(t){return t.node===box.dataset.node}).forEach(function(t){box.appendChild(taskEl(t))});if(!box.children.length)box.innerHTML='<p class="meta">Заданий к этому шагу нет.</p>'});
 $$(".wid",v).forEach(widget);
 var pv=$("[data-prev]",v),nx=$("[data-next]",v),dn=$("[data-done]",v);
 pv.disabled=i===0;nx.disabled=i===steps.length-1;
 pv.onclick=function(){location.hash="#/step/"+steps[i-1].id};nx.onclick=function(){S.done[id]=1;save();location.hash="#/step/"+steps[i+1].id};
 function lab(){dn.textContent=S.done[id]?"Пройден ✓ (снять отметку)":"Отметить пройденным"}lab();
 dn.onclick=function(){if(S.done[id])delete S.done[id];else S.done[id]=1;save();lab();prog()};
}
/* задания */
var shuf=function(a,seed){var r=a.slice(),x=0;for(var i=0;i<seed.length;i++)x=(x*31+seed.charCodeAt(i))>>>0;
 for(var n=0;n<5;n++){for(var i=r.length-1;i>0;i--){x=(x*1103515245+12345)>>>0;var j=x%(i+1);var t=r[i];r[i]=r[j];r[j]=t}}
 if(r.join()===a.join())r.push(r.shift());return r};
var SUBS={"₀":"0","₁":"1","₂":"2","₃":"3","₄":"4","₅":"5","₆":"6","₇":"7","₈":"8","₉":"9","ₐ":"a","ₑ":"e","ₒ":"o","ₓ":"x","ₕ":"h","ₖ":"k","ₗ":"l","ₘ":"m","ₙ":"n","ₚ":"p","ₛ":"s","ₜ":"t"};
var LOOK={"а":"a","е":"e","о":"o","р":"p","с":"c","х":"x","к":"k","м":"m","т":"t","π":"п","ρ":"p"};
var nz=function(s){var t=String(s).toLowerCase().replace(/[₀-₉ₐₑₒₓₕₖₗₘₙₚₛₜ]/g,function(c){return SUBS[c]}).replace(/\s+/g,"").replace(/[−–—]/g,"-").replace(/,/g,".").replace(/[_{}]/g,"").replace(/[·⋅×*]/g,"*").replace(/[арескомтхπ]/g,function(c){return LOOK[c]});
 if(t.indexOf("*")>=0)t=t.split("*").sort().join("*");return t};
var TN={single:"один ответ",multi:"несколько ответов",order:"порядок",blank:"пропуск",calc:"расчёт"};
function taskEl(t){
 var d=document.createElement("div");d.className="task";var h='<p><b>'+esc(t.q)+'</b> <span class="meta">('+TN[t.type]+')</span></p><div class="in"></div><button type="button" class="chk">Проверить</button><div class="fb" hidden aria-live="polite"></div>';d.innerHTML=h;
 var inn=$(".in",d),getv,show;
 if(t.type==="single"||t.type==="multi"){
  var ty=t.type==="single"?"radio":"checkbox";inn.innerHTML=t.options.map(function(o,i){return '<label><input type="'+ty+'" name="'+t.id+'" value="'+i+'"> '+esc(o)+'</label>'}).join("");
  getv=function(){return $$("input:checked",inn).map(function(x){return t.options[+x.value]})};
  var ans=t.type==="single"?[t.answer]:t.answers;
  var ok=function(v){return v.length===ans.length&&ans.every(function(a){return v.indexOf(a)>=0})};
  d._ev=function(){var v=getv();return{ok:ok(v),right:ans.join("; ")}};
 }else if(t.type==="blank"){
  var parts=t.text.split(/\[\[.+?\]\]/);inn.innerHTML='<p>'+esc(parts[0])+'<input type="text" aria-label="пропуск" autocomplete="off" size="8">'+esc(parts[1]||"")+'</p>';
  d._ev=function(){var v=nz($("input",inn).value);return{ok:[t.answer].concat(t.alt||[]).some(function(a){return nz(a)===v}),right:t.answer}};
 }else if(t.type==="calc"){
  inn.innerHTML='<input type="text" inputmode="decimal" aria-label="ответ" autocomplete="off">';
  d._ev=function(){var v=parseFloat($("input",inn).value.replace(",","."));return{ok:isFinite(v)&&Math.abs(v-t.answer)<=t.tol,right:String(t.answer).replace(".",",")}};
 }else{
  var items=shuf(t.items,t.id);inn.innerHTML='<ol class="ord" aria-label="Перетащите или используйте кнопки"></ol>';var ol=$("ol",inn);
  items.forEach(function(x){var li=document.createElement("li");li.dataset.v=x;li.innerHTML='<span class="hd" aria-hidden="true">⠿</span><span class="tx">'+esc(x)+'</span><button type="button" data-d="-1" aria-label="Выше">↑</button><button type="button" data-d="1" aria-label="Ниже">↓</button>';ol.appendChild(li)});
  ol.addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;var li=b.parentNode,dd=+b.dataset.d;if(dd<0&&li.previousElementSibling)ol.insertBefore(li,li.previousElementSibling);if(dd>0&&li.nextElementSibling)ol.insertBefore(li.nextElementSibling,li)});
  var cur=null;
  ol.addEventListener("pointerdown",function(e){var hd=e.target.closest(".hd");if(!hd)return;cur=hd.parentNode;cur.classList.add("drag");hd.setPointerCapture(e.pointerId);e.preventDefault()});
  ol.addEventListener("pointermove",function(e){if(!cur)return;var el=document.elementFromPoint(e.clientX,e.clientY),li=el&&el.closest&&el.closest("li");if(!li||li===cur||li.parentNode!==ol)return;var r=li.getBoundingClientRect();if(e.clientY<r.top+r.height/2)ol.insertBefore(cur,li);else ol.insertBefore(cur,li.nextSibling)});
  var end=function(){if(cur)cur.classList.remove("drag");cur=null};ol.addEventListener("pointerup",end);ol.addEventListener("pointercancel",end);
  d._ev=function(){var v=$$("li",ol).map(function(l){return l.dataset.v});return{ok:v.join("\u0001")===t.items.join("\u0001"),right:t.items.map(function(x,i){return(i+1)+") "+x}).join(" ")}};
 }
 $(".chk",d).onclick=function(){var r=d._ev(),f=$(".fb",d);S.tasks[t.id]=r.ok;save();
  f.hidden=false;f.className="fb "+(r.ok?"ok":"no");
  var e=D.ev[t.claim];
  f.innerHTML='<b>'+(r.ok?"Верно.":"Не совсем.")+'</b> Верный ответ: '+esc(r.right)+'. '+esc(t.expl)+'<br><span class="meta">В тексте шага: «<span class="cl ca" tabindex="0" role="button" data-k="'+esc(t.claim)+'">'+esc(e.t)+'</span>» (утверждение '+esc(t.claim)+')</span>'};
 return d;
}
/* виджеты */
function widget(w){
 var k=w.dataset.widget;
 if(k==="linmodel"){
  var dj=w.dataset.dj==="1";
  w.innerHTML='<label>C (чувствительность, усл.): <output id="oC"></output><input type="range" min="1" max="5" step="0.5" value="2" aria-label="C"></label><label>I_ф (фон, усл.): <output id="oF"></output><input type="range" min="0" max="10" step="1" value="3" aria-label="I_ф"></label><label>q пласта (усл.): <output id="oQ"></output><input type="range" min="0" max="10" step="1" value="5" aria-label="q"></label><svg viewBox="0 0 360 200" role="img" aria-label="Линия I = C q + I_ф с тремя точками"></svg><p class="meta" aria-live="polite"></p>';
  var r=$$("input",w),svg=$("svg",w),msg=$(".meta",w);
  var draw=function(){var C=+r[0].value,F=+r[1].value,q=+r[2].value,I=function(x){return C*x+F},X=function(x){return 30+x*30},Y=function(v){return 180-v*3};
   var s='<line x1="30" x2="330" y1="180" y2="180" class="ax"/><line x1="30" x2="30" y1="10" y2="180" class="ax"/><path class="cv" d="M'+X(0)+' '+Y(I(0))+' L'+X(10)+' '+Y(I(10))+'"/><text x="334" y="196" text-anchor="end" class="t">q</text><text x="34" y="16" class="t">I</text>';
   [[2,"оп1"],[8,"оп2"],[q,"пласт"]].forEach(function(p){s+='<circle cx="'+X(p[0])+'" cy="'+Y(I(p[0]))+'" r="5" class="bar"/><text x="'+(X(p[0])+6)+'" y="'+(Y(I(p[0]))-6)+'" class="t">'+p[1]+'</text>'});
   svg.innerHTML=s;$("#oC",w).textContent=C;$("#oF",w).textContent=F;$("#oQ",w).textContent=q;
   var t="I = C·q + I_ф = "+I(q);
   if(dj){var v=(I(q)-I(2))/(I(8)-I(2));t+="; ΔJ = (I − I_оп1)/(I_оп2 − I_оп1) = "+v.toFixed(2).replace(".",",")+": меняйте C и I_ф, ΔJ остаётся прежним"}
   msg.textContent=t};
  r.forEach(function(x){x.oninput=draw});draw();
 }else if(k==="dcalc"){
  var c=D.dstep,h='<p class="meta">Числа по умолчанию взяты из книги; меняйте их и смотрите на результат.</p>';
  c.inputs.forEach(function(x){h+='<p><label>'+esc(x.label)+': <input type="text" inputmode="decimal" data-k="'+x.k+'" value="'+esc(x.v)+'"></label> <a href="#" data-ev="'+esc(x.claim)+'" class="chip">источник</a></p>'});
  h+='<div id="dout"></div>';w.innerHTML=h;
  var run=function(){var vals={};$$("input",w).forEach(function(i){vals[i.dataset.k]=parseFloat(i.value.replace(",","."))});
   var o="";c.outputs.forEach(function(q){var v;try{v=new Function(Object.keys(vals).join(","),"return "+q.expr).apply(null,Object.keys(vals).map(function(k){return vals[k]}))}catch(e){v=NaN}
    var s=isFinite(v)?v.toFixed(q.digits).replace(".",","):"—";var diff=isFinite(v)&&s!==q.book;var def=c.inputs.every(function(x){return vals[x.k]===parseFloat(String(x.v).replace(",","."))});var lab=q.label.replace(/\{(\w+)\}/g,function(_,k){return isFinite(vals[k])?String(vals[k]).replace(".",","):"?"});var st=!isFinite(v)?". Введите числа во все поля.":!def?". Числа изменены, поэтому сравнение с книгой не проводится.":diff?". Расхождение с книгой: считайте это спорным местом (причина — в источнике утверждения).":". Совпадает.";
    o+='<p><b>'+esc(lab)+' = '+s+'</b><br><span class="meta">В книге: '+esc(q.book)+st+' <a href="#" data-ev="'+esc(q.claim)+'">источник</a></span></p>'});
   $("#dout",w).innerHTML=o};
  $$("input",w).forEach(function(i){i.oninput=run});run();
 }
}
/* карточки */
var order=[],ci=0,flipped=false;
function cards(){
 var only=$("#conlyrep").checked,all=$$("#cardbox .card");
 order=all.filter(function(c){return !only||S.cards[c.dataset.id]==="rep"});ci=Math.min(ci,Math.max(0,order.length-1));
 var know=Object.keys(S.cards).filter(function(k){return S.cards[k]==="know"}).length;
 $("#cardinfo").textContent="Карточек: "+all.length+" · знаю: "+know+" · повторить: "+(Object.keys(S.cards).length-know);
 flipped=false;paint();
}
function paint(){
 $$("#cardbox .card").forEach(function(c){c.hidden=true;c.querySelector(".back").hidden=true});
 var c=order[ci];$("#cflip").disabled=!c;$("#cknow").disabled=$("#crep").disabled=true;if(!c)return;
 c.hidden=false;c.querySelector(".back").hidden=!flipped;$("#cflip").textContent=flipped?"Скрыть ответ":"Показать ответ";
 $("#cknow").disabled=$("#crep").disabled=!flipped;$("#cardinfo").dataset.pos=(ci+1)+"/"+order.length;
}
$("#cflip").onclick=function(){flipped=!flipped;paint()};
function mark(v){var c=order[ci];if(!c)return;S.cards[c.dataset.id]=v;save();if(order.length>1)ci=(ci+1)%order.length;cards()}
$("#cknow").onclick=function(){mark("know")};$("#crep").onclick=function(){mark("rep")};$("#conlyrep").onchange=function(){ci=0;cards()};
route();
})();
