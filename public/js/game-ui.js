import {GlyphSurface,UI_COLORS as C,rgba} from './gpu-ui.js';

export class GameUI extends GlyphSurface {
  constructor(renderer,atlas){
    super(renderer,atlas);this.hits=[];this.pointer={x:-1,y:-1};this.focusId=null;this.hudHidden=false;this.labels=new Set();
    this.playerName='Driver';this.networkLabel='Joining global lobby';this.playerNames=[];this.toastText='';this.toastUntil=0;this.fps=0;
    const canvas=renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','Dunes driving game. WASD drives. M opens settings. P edits your driver name.');
    canvas.addEventListener('pointermove',e=>{this.pointer={x:e.clientX,y:e.clientY};if(this.drag){this.drag.update(e.clientX);e.preventDefault();e.stopImmediatePropagation();}else if(this.menu?.open)e.stopImmediatePropagation();},true);
    canvas.addEventListener('pointerdown',e=>{
      const hit=this.hitAt(e.clientX,e.clientY);
      if(!hit&&!this.menu?.open)return;
      e.preventDefault();e.stopImmediatePropagation();canvas.focus();this.focusId=hit?.id||null;
      if(hit?.type==='slider'){this.drag=hit;canvas.setPointerCapture(e.pointerId);hit.update(e.clientX);}else hit?.activate?.(e);
    },true);
    canvas.addEventListener('pointerup',e=>{if(this.drag){this.drag.commit?.();this.drag=null;e.preventDefault();e.stopImmediatePropagation();}else if(this.menu?.open)e.stopImmediatePropagation();},true);
    canvas.addEventListener('pointercancel',()=>{this.drag?.commit?.();this.drag=null;});
    canvas.addEventListener('wheel',e=>{if(this.menu?.open){this.menu.scrollBy(e.deltaY);e.preventDefault();e.stopImmediatePropagation();}},{capture:true,passive:false});
    addEventListener('keydown',e=>{if(this.menu?.handleKey(e)){e.preventDefault();e.stopImmediatePropagation();}},true);
    addEventListener('paste',e=>{if(this.menu?.editor){const text=e.clipboardData?.getData('text/plain');if(text)this.menu.insert(text);e.preventDefault();}},true);
    addEventListener('blur',()=>{this.drag?.commit?.();this.drag=null;});
  }
  hitAt(x,y){return [...this.hits].reverse().find(h=>x>=h.x&&y>=h.y&&x<=h.x+h.w&&y<=h.y+h.h);}
  hit(id,x,y,w,h,options){const c=this.clip,x0=Math.max(x,c[0]),y0=Math.max(y,c[1]),x1=Math.min(x+w,c[2]),y1=Math.min(y+h,c[3]);if(x1>x0&&y1>y0)this.hits.push({id,x:x0,y:y0,w:x1-x0,h:y1-y0,...options});}
  button(id,label,x,y,w,h,activate,{selected=false,quiet=false,size=18}={}){
    const hover=this.pointer.x>=x&&this.pointer.y>=y&&this.pointer.x<=x+w&&this.pointer.y<=y+h;
    const focused=this.focusId===id;
    this.rect(x,y,w,h,selected?C.orange:hover?'#354339':quiet?rgba(C.panel,.4):'#27342c',5);
    if(focused){this.rect(x,y,w,2,C.paper);this.rect(x,y+h-2,w,2,C.paper);}
    this.text(label,x+w/2,y+(h-size)/2-2,size,selected?C.ink:C.paper,{align:'center',maxWidth:w-12});
    this.hit(id,x,y,w,h,{type:'button',activate});
  }
  label(){const l={visible:false,x:0,y:0,text:''};this.labels.add(l);return l;}
  removeLabel(label){this.labels.delete(label);}
  toast(text){this.toastText=text;this.toastUntil=performance.now()+2700;}
  loading(message,progress=.15){
    this.begin(innerWidth,innerHeight);this.rect(0,0,this.width,this.height,'#17201a');
    const x=this.width*.5,y=this.height*.43;
    this.text('DUNES',x,y,Math.min(104,this.width*.2),C.paper,{align:'center'});
    this.text('IMPERIAL SAND DUNES  /  CALIFORNIA',x,y+116,16,C.orange,{align:'center',maxWidth:this.width-30});
    this.text(message,x,y+156,19,C.muted,{align:'center',maxWidth:this.width-40});
    const w=Math.min(360,this.width-60);this.rect(x-w/2,y+202,w,3,'#354339');this.rect(x-w/2,y+202,w*progress,3,C.orange);
    this.render({clear:true});
  }
  draw(state){
    const w=innerWidth,h=innerHeight,m=w<600?16:28;this.begin(w,h);this.hits=[];
    const menu=this.menu,small=w<650;
    for(const label of this.labels)if(label.visible&&!this.hudHidden){const tw=this.measure(label.text,17);this.rect(label.x-tw/2-9,label.y-3,tw+18,28,rgba('#101712',.77),4);this.text(label.text,label.x,label.y,17,C.paper,{align:'center'});}
    if(!this.hudHidden){
      this.rect(m-10,m-8,small?220:285,86,rgba(C.ink,.78),7);
      this.text('DUNES',m,m-4,34,C.paper);this.rect(m+91,m+7,4,25,C.orange);
      this.text(this.networkLabel,m,m+38,15,C.green,{maxWidth:small?200:260});
      if(!small&&this.playerNames.length)this.text(this.playerNames.join('  /  '),m,m+60,14,C.muted,{maxWidth:260});
      const speedW=small?158:228,sx=w-m-speedW,sy=h-(small?158:196);
      this.rect(sx-12,sy-8,speedW+24,small?130:160,rgba(C.ink,.84),8);
      this.text(String(Math.round(state.mph)),sx,sy-11,small?72:98,C.paper);
      this.text('MPH',sx+(small?94:140),sy+(small?45:64),18,C.muted);
      this.rect(sx+speedW-42,sy+3,42,40,C.orange,5);this.text(String(state.gear),sx+speedW-21,sy+3,29,C.ink,{align:'center'});
      const barY=sy+(small?79:108),rpm=state.rpm||0;
      for(let i=0;i<28;i++)this.rect(sx+i*speedW/28,barY,speedW/28-2,7,i/28<rpm/8000?(rpm>7000?'#ff6954':C.orange):'#465047',1);
      this.text(`${Math.round(rpm/10)*10} RPM`,sx,barY+13,16,C.muted);
      if(state.radarVisible&&state.radar?.texture){
        const d=Math.min(small?132:214,h-190),rx=m,ry=h-d-(small?51:69),radar=state.radar;
        this.radarBounds={x:rx,y:ry,w:d,h:d};
        this.rect(rx-10,ry-36,d+20,d+78,rgba(C.ink,.88),8);
        this.text('RADAR',rx,ry-29,17,C.paper);
        this.text(radar.range>=1000?`${radar.range/1000} KM`:`${radar.range} M`,rx+d-28,ry-27,15,C.orange,{align:'right'});
        this.button('radar-out','+',rx+d-22,ry-29,24,24,()=>this.onRadarRange?.(1),{quiet:true,size:18});
        this.button('radar-in','-',rx+d-51-(small?38:47),ry-29,24,24,()=>this.onRadarRange?.(-1),{quiet:true,size:18});
        this.image(radar.texture,rx,ry,d,d);
        this.rect(rx+2,ry+d+9,6,6,'#ffb05c',3);
        this.text(`${radar.counts?.bots||0} BOTS`,rx+13,ry+d+3,small?12:14,C.muted);
        this.quad(rx+(small?72:110),ry+d+9,6,6,'#73e5f5',0,undefined,0,Math.PI/4);
        this.text(`${radar.counts?.players||0} DRIVERS`,rx+(small?83:121),ry+d+3,small?12:14,C.muted);
      }else{
        this.radarBounds=null;this.button('show-radar','SHOW RADAR',m,h-80,132,36,()=>this.onRadarShow?.(),{size:16});
      }
      if(!small)this.text(this.shortcuts||'WASD  DRIVE',w/2,h-34,16,C.paper,{align:'center',maxWidth:w-440});
      if(state.showHelp&&!menu?.open){
        const x=m,y=m+96,bw=Math.min(334,w-2*m);this.rect(x-10,y-8,bw,Math.min(h-330,352),rgba(C.ink,.86),7);
        this.text('DRIVE THE DUNES',x,y,21,C.orange);let lineY=y+35;
        for(const [keys,label] of (this.helpRows||[]).slice(0,small?5:10)){this.text(keys,x,lineY,16,C.orange,{maxWidth:98});this.text(label,x+105,lineY,16,C.paper,{maxWidth:bw-126});lineY+=25;}
        this.text('F1  CLOSE HELP',x,lineY+8,14,C.muted);
      }
      if(this.debug)this.text(`${this.fps} FPS  /  ${state.quality.toUpperCase()}  /  GPU GLYPHS ${this.glyphCount}`,m,h-21,13,C.muted);
    }
    if(!menu?.open)this.button('open-menu','M  /  MENU',w-m-112,m,112,38,()=>menu?.toggle(true),{size:17});
    if(performance.now()<this.toastUntil){const tw=Math.min(w-40,this.measure(this.toastText,23)+40);this.rect((w-tw)/2,h*.2,tw,48,rgba(C.ink,.94),5);this.text(this.toastText,w/2,h*.2+8,23,C.paper,{align:'center',maxWidth:tw-24});}
    if(menu?.open){this.hits=[];menu.draw(w,h);}
    this.render();
  }
}
