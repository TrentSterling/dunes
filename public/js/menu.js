import {SCHEMA,saveSettings} from './settings.js';
import {ACTIONS,loadBindings,resetBindings,assign,keyName,padName,padPressed,RESERVED_KEYS,actionForKey} from './controls.js';
import {UI_COLORS as C,rgba} from './gpu-ui.js';
export {SCHEMA,DEFAULTS,GLOBAL_KEYS,loadSettings,saveSettings} from './settings.js';

export class Menu {
  constructor(ui,settings,onChange){
    this.ui=ui;ui.menu=this;this.s=settings;this.onChange=onChange;this.open=false;this.tab=0;
    this.tabs=['Driver',...SCHEMA.map(t=>t.tab)];this.scroll=0;this.maxScroll=0;this.bindings=loadBindings();
    this.capture=null;this.editor=null;this.notice='';this.focusIndex=-1;this.padPrev={};
  }
  toggle(force){this.open=force??!this.open;if(!this.open){this.capture=null;this.editor=null;this.ui.drag=null;}this.onToggle?.(this.open);}
  showTab(index){this.tab=Math.max(0,Math.min(this.tabs.length-1,index));this.scroll=0;this.capture=null;this.notice='';this.ui.focusId=null;}
  refresh(){}
  scrollBy(amount){this.scroll=Math.max(0,Math.min(this.maxScroll,this.scroll+amount));}
  set(item,value){if(this.s[item.key]===value)return;this.s[item.key]=value;saveSettings(this.s);this.onChange(item.key,value,item);}
  editName(){
    const value=this.ui.playerName;
    this.editor={value,caret:value.length,anchor:0,returnOpen:this.open,keyboard:false,error:''};
    this.open=true;this.capture=null;this.onToggle?.(true);this.ui.renderer.domElement.focus();
  }
  insert(text){
    const e=this.editor;if(!e)return;
    const lo=Math.min(e.caret,e.anchor),hi=Math.max(e.caret,e.anchor);
    const input=String(text).replace(/[\x00-\x1f\x7f]/g,'').slice(0,24-(e.value.length-(hi-lo)));
    e.value=e.value.slice(0,lo)+input+e.value.slice(hi);e.caret=e.anchor=lo+input.length;e.error='';
  }
  saveName(){
    const e=this.editor,value=e.value.trim().replace(/\s+/g,' ');
    if(!value){e.error='ENTER A DRIVER NAME';return;}
    this.onName?.(value);this.ui.playerName=value;this.editor=null;this.open=e.returnOpen;this.onToggle?.(this.open);this.ui.toast('Driver name updated');
  }
  cancelName(){const e=this.editor;this.editor=null;this.open=e.returnOpen;this.onToggle?.(this.open);}
  editKey(e){
    const f=this.editor,ctrl=e.ctrlKey||e.metaKey,lo=Math.min(f.caret,f.anchor),hi=Math.max(f.caret,f.anchor);
    if(e.key==='Escape'){this.cancelName();return true;}
    if(e.key==='Enter'){this.saveName();return true;}
    if(ctrl&&e.key.toLowerCase()==='a'){f.anchor=0;f.caret=f.value.length;return true;}
    if(ctrl&&['c','x'].includes(e.key.toLowerCase())){
      navigator.clipboard?.writeText(f.value.slice(lo,hi)).catch(()=>{});
      if(e.key.toLowerCase()==='x')this.insert('');return true;
    }
    if(ctrl&&e.key.toLowerCase()==='v'){navigator.clipboard?.readText().then(text=>{if(this.editor===f)this.insert(text);}).catch(()=>{f.error='CLIPBOARD UNAVAILABLE. TYPE YOUR NAME.';});return true;}
    if(e.key==='Backspace'||e.key==='Delete'){
      if(lo===hi){if(e.key==='Backspace')f.anchor=Math.max(0,f.caret-1);else f.anchor=Math.min(f.value.length,f.caret+1);}
      this.insert('');return true;
    }
    if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){
      f.caret=e.key==='Home'?0:e.key==='End'?f.value.length:Math.max(0,Math.min(f.value.length,f.caret+(e.key==='ArrowLeft'?-1:1)));
      if(!e.shiftKey)f.anchor=f.caret;return true;
    }
    if(!ctrl&&!e.altKey&&e.key.length===1){this.insert(e.key);return true;}
    return true;
  }
  handleKey(e){
    if(this.editor)return this.editKey(e);
    if(!this.open){if(e.code==='F3'){this.ui.debug=!this.ui.debug;return true;}return false;}
    if(this.capture){
      if(e.key==='Escape'){this.capture=null;this.notice='Binding cancelled';return true;}
      if(this.capture.kind==='keys'){
        if(RESERVED_KEYS.includes(e.code)){this.notice='M and Esc stay reserved for the menu';return true;}
        this.finishBinding(['Backspace','Delete'].includes(e.key)?null:e.code);
      }return true;
    }
    if(!e.ctrlKey&&!e.metaKey&&!e.altKey&&actionForKey(this.bindings,e.code)==='mute'){if(!e.repeat)this.ui.onMute?.();return true;}
    if(e.key==='Tab'){
      const hits=this.ui.hits,old=hits.findIndex(h=>h.id===this.ui.focusId),i=(old+(e.shiftKey?-1:1)+hits.length)%hits.length;
      this.ui.focusId=hits[i]?.id;return true;
    }
    const hit=this.ui.hits.find(h=>h.id===this.ui.focusId);
    if(['ArrowLeft','ArrowRight'].includes(e.key)&&hit?.adjust){hit.adjust(e.key==='ArrowRight'?1:-1);return true;}
    if((e.key==='Enter'||e.code==='Space')&&hit){hit.activate?.();return true;}
    if(e.key==='PageDown'||e.key==='PageUp'){this.scrollBy((e.key==='PageDown'?1:-1)*this.viewport.h*.8);return true;}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){this.scrollBy(e.key==='ArrowDown'?42:-42);return true;}
    return false;
  }
  startBinding(id,kind,slot){
    this.capture={id,kind,slot,armed:false,rest:{}};this.notice=kind==='keys'?'Press a key. Backspace clears; Esc cancels.':'Press a controller button or move a stick.';
    for(const gp of navigator.getGamepads?.()||[])if(gp)this.capture.rest[gp.index]=[...gp.axes];
  }
  finishBinding(code){const {id,kind,slot}=this.capture;const moved=assign(this.bindings,id,kind,slot,code);this.capture=null;
    this.notice=code?`${kind==='keys'?keyName(code):padName(code)} assigned${moved?' (previous binding cleared)':''}`:'Binding cleared';this.onBindings?.();}
  pollGamepads(){
    if(this.capture?.kind==='pad'){
      const code=padPressed([...(navigator.getGamepads?.()||[])],this.capture.rest);
      if(!code)this.capture.armed=true;else if(this.capture.armed)this.finishBinding(code);return;
    }
    if(!this.open||this.editor)return;
    for(const pad of navigator.getGamepads?.()||[]){if(!pad)continue;const prev=this.padPrev[pad.index]||{};
      for(const button of [0,1,4,5,12,13]){const pressed=pad.buttons[button]?.pressed;
        if(pressed&&!prev[button]){
          if(button===1)this.toggle(false);
          else if(button===4||button===5)this.showTab((this.tab+(button===5?1:-1)+this.tabs.length)%this.tabs.length);
          else if(button===12||button===13){const hits=this.ui.hits,i=hits.findIndex(h=>h.id===this.ui.focusId);this.ui.focusId=hits[(i+(button===13?1:-1)+hits.length)%hits.length]?.id;}
          else this.ui.hits.find(h=>h.id===this.ui.focusId)?.activate?.();
        }prev[button]=pressed;
      }this.padPrev[pad.index]=prev;
    }
  }
  draw(width,height){
    const u=this.ui;this.pollGamepads();u.rect(0,0,width,height,rgba('#080e0a',.7));
    if(this.editor){this.drawEditor(width,height);return;}
    const compact=width<760,pw=Math.min(1080,width-24),ph=Math.min(750,height-24),px=(width-pw)/2,py=(height-ph)/2;
    u.rect(px,py,pw,ph,'#152019',9);u.rect(px,py,4,ph,C.orange);
    u.text('DUNES',px+24,py+16,42,C.paper);
    if(!compact)u.text('MAKE YOURSELF AT HOME',px+150,py+34,15,C.muted,{maxWidth:pw-320});
    u.button('resume','RESUME',px+pw-124,py+24,100,38,()=>this.toggle(false),{selected:true});
    let cx,cy,cw,ch;
    if(compact){
      u.button('previous-tab','<',px+16,py+82,40,35,()=>this.showTab((this.tab+this.tabs.length-1)%this.tabs.length));
      u.text(this.tabs[this.tab].toUpperCase(),px+pw/2,py+86,21,C.orange,{align:'center'});
      u.button('next-tab','>',px+pw-56,py+82,40,35,()=>this.showTab((this.tab+1)%this.tabs.length));
      cx=px+20;cy=py+136;cw=pw-40;ch=ph-194;
    }else{
      const step=Math.min(53,(ph-180)/this.tabs.length);
      this.tabs.forEach((name,i)=>u.button(`tab-${i}`,name.toUpperCase(),px+20,py+98+i*step,160,Math.min(43,step-6),()=>this.showTab(i),{selected:this.tab===i,quiet:true,size:18}));
      u.text('F1  HELP',px+30,py+ph-66,15,C.muted);u.line(px+200,py+92,px+200,py+ph-66,1,'#36473b');
      cx=px+228;cy=py+99;cw=pw-256;ch=ph-164;
    }
    this.viewport={x:cx,y:cy,w:cw,h:ch};u.clip=[cx,cy,cx+cw,cy+ch];
    let y=cy-this.scroll;
    if(this.tab===0)y=this.drawDriver(cx,y,cw);
    else for(const item of SCHEMA[this.tab-1].items)y=this.drawItem(item,cx,y,cw);
    this.maxScroll=Math.max(0,y+this.scroll-cy-ch);this.scroll=Math.min(this.scroll,this.maxScroll);
    u.clip=[0,0,width,height];
    if(this.maxScroll>0){const track=ch,thumb=Math.max(28,ch*ch/(ch+this.maxScroll));u.rect(px+pw-12,cy,3,track,'#35463a');u.rect(px+pw-12,cy+(track-thumb)*this.scroll/this.maxScroll,3,thumb,C.orange);}
    u.line(px+20,py+ph-51,px+pw-20,py+ph-51,1,'#35463a');
    u.text(this.notice||'ESC  RESUME    /    TAB  FOCUS    /    ARROWS  ADJUST',px+24,py+ph-35,15,C.muted,{maxWidth:pw-48});
  }
  drawDriver(x,y,w){
    const u=this.ui;u.text('YOUR DRIVER',x,y,16,C.orange);y+=28;
    u.text(u.playerName,x,y,40,C.paper,{maxWidth:w-122});u.button('edit-name','EDIT NAME',x+w-112,y+7,112,36,()=>this.editName());y+=66;
    u.text(u.networkLabel,x,y,21,C.green);y+=32;
    y+=u.wrap('You join the global lobby automatically. Just drive; other players appear as they connect.',x,y,18,C.muted,w)+24;
    const car=SCHEMA.flatMap(t=>t.items).find(it=>it.key==='car');y=this.drawItem(car,x,y,w);
    u.text('DRIVERS HERE',x,y+8,16,C.orange);y+=40;
    for(const name of [u.playerName,...u.playerNames]){u.text(name,x+12,y,21,C.paper,{maxWidth:w-20});y+=34;}
    u.button('driver-help','SHOW DRIVING HELP',x,y+12,Math.min(230,w),38,()=>{this.s.showHelp=true;saveSettings(this.s);this.onChange('showHelp',true);this.toggle(false);});
    return y+72;
  }
  drawItem(item,x,y,w){
    const u=this.ui,top=y;
    if(item.type==='bindings')return this.drawBindings(x,y,w);
    if(item.type==='keys'){for(const [key,label] of item.rows){u.text(key.toUpperCase(),x,y,16,C.orange);y+=24;y+=u.wrap(label,x,y,18,C.muted,w)+16;}return y;}
    u.text(item.label,x,y,22,C.paper);y+=32;
    if(item.hint)y+=u.wrap(item.hint,x,y,16,C.muted,w)+11;
    if(item.type==='choice'||item.type==='actions'){
      let bx=x;
      for(const [value,label] of item.options||item.list){
        const bw=Math.min(w,Math.max(69,u.measure(label,18)+26));
        if(bx+bw>x+w+1){bx=x;y+=43;}
        u.button(`${item.key}-${String(value)}`,label,bx,y,bw,35,()=>item.type==='actions'?this.onAction?.(item.key,value):this.set(item,value),{selected:item.type==='choice'&&this.s[item.key]===value,size:18});bx+=bw+7;
      }y+=49;
    }else if(item.type==='range'){
      const value=this.preview?.key===item.key?this.preview.value:this.s[item.key],ratio=(value-item.min)/(item.max-item.min),sx=x+8,sw=Math.max(70,w-145);
      u.rect(sx,y+14,sw,5,'#465448',2);u.rect(sx,y+14,sw*Math.max(0,Math.min(1,ratio)),5,C.orange,2);u.rect(sx+sw*ratio-7,y+7,14,19,C.paper,4);
      u.text(item.fmt(value),x+w,y+2,19,C.paper,{align:'right',maxWidth:131});
      const quantize=v=>Math.max(item.min,Math.min(item.max,Math.round((v-item.min)/item.step)*item.step+item.min));
      const update=px=>{const v=quantize(item.min+(px-sx)/sw*(item.max-item.min));if(item.lazy)this.preview={key:item.key,value:v};else this.set(item,v);};
      const commit=()=>{if(this.preview?.key===item.key){this.set(item,this.preview.value);this.preview=null;}};
      u.hit(item.key,x,y,sw+16,35,{type:'slider',update,commit,adjust:step=>this.set(item,quantize(this.s[item.key]+step*item.step)),activate:()=>this.set(item,quantize(this.s[item.key]+item.step))});
      if(u.focusId===item.key)u.line(x,y+35,x+sw+16,y+35,2,C.paper);
      y+=45;
      if(item.presets){let bx=x;for(const [v,label]of item.presets){const bw=Math.max(60,u.measure(label,16)+25);u.button(`${item.key}-preset-${v}`,label,bx,y,bw,31,()=>this.set(item,v),{selected:Math.abs(this.s[item.key]-v)<.001,size:16});bx+=bw+6;}y+=42;}
    }
    u.line(x,y+3,x+w,y+3,1,'#35463a');return Math.max(top+55,y+23);
  }
  drawBindings(x,y,w){
    const u=this.ui;u.text('YOUR CONTROLS',x,y,27,C.paper);y+=42;
    y+=u.wrap('Choose a binding, then press a key or controller button. Backspace clears it; Esc cancels.',x,y,17,C.muted,w)+20;
    const compact=w<600;
    for(const a of ACTIONS){
      u.text(a.label,x,y+5,19,C.paper);const bx=compact?x:x+150,by=compact?y+34:y,bw=(w-(compact?0:150)-21)/4;
      for(const [i,[kind,slot]] of [['keys',0],['keys',1],['pad',0],['pad',1]].entries()){
        const active=this.capture?.id===a.id&&this.capture.kind===kind&&this.capture.slot===slot,code=this.bindings[a.id][kind][slot];
        const label=active?'PRESS...':kind==='keys'?keyName(code):padName(code);
        u.button(`bind-${a.id}-${kind}-${slot}`,label,bx+i*(bw+7),by,bw,32,()=>this.startBinding(a.id,kind,slot),{selected:active,size:compact?13:15});
      }y+=compact?80:45;
    }
    u.button('reset-bindings','RESET CONTROLS',x,y+8,180,38,()=>{this.capture=null;resetBindings(this.bindings);this.onBindings?.();this.notice='Default controls restored';});return y+65;
  }
  drawEditor(width,height){
    const u=this.ui,e=this.editor,w=Math.min(560,width-32),h=e.keyboard?458:284,x=(width-w)/2,y=Math.max(8,(height-h)/2);
    u.rect(x,y,w,h,C.panel,9);u.rect(x,y,4,h,C.orange);
    u.text('DRIVER NAME',x+24,y+19,32,C.paper);u.text('Updates here and for everyone in the lobby.',x+24,y+65,18,C.muted,{maxWidth:w-48});
    const fx=x+24,fy=y+108,fw=w-48;
    u.rect(fx,fy,fw,58,'#26362c',4);u.rect(fx,fy+56,fw,2,C.orange);
    const size=Math.min(29,(fw-24)/Math.max(1,u.measure(e.value,29))*29),lo=Math.min(e.caret,e.anchor),hi=Math.max(e.caret,e.anchor);
    const start=fx+12+u.measure(e.value.slice(0,lo),size),end=fx+12+u.measure(e.value.slice(0,hi),size);
    if(hi>lo)u.rect(start,fy+8,end-start,41,rgba(C.orange,.28),1);
    u.text(e.value,fx+12,fy+10,size,C.paper);
    if(Math.floor(performance.now()/500)%2===0){const caret=fx+12+u.measure(e.value.slice(0,e.caret),size);u.rect(caret,fy+12,2,34,C.paper);}
    u.hit('name-field',fx,fy,fw,58,{type:'button',activate:event=>{if(!event)return;let best=0,dist=Infinity;for(let i=0;i<=e.value.length;i++){const d=Math.abs(event.clientX-(fx+12+u.measure(e.value.slice(0,i),size)));if(d<dist){dist=d;best=i;}}e.caret=e.anchor=best;}});
    u.text(e.error||`${e.value.length}/24  /  ENTER TO SAVE  /  ESC TO CANCEL`,fx,fy+69,14,e.error?'#ff9b86':C.muted,{maxWidth:fw});
    const bw=(w-60)/3;
    u.button('name-cancel','CANCEL',x+24,y+221,bw,39,()=>this.cancelName(),{quiet:true,size:16});
    u.button('name-keyboard',w<400?'ABC':'KEYBOARD',x+30+bw,y+221,bw,39,()=>{e.keyboard=!e.keyboard;},{quiet:true,size:16});
    u.button('name-save','SAVE NAME',x+36+bw*2,y+221,bw,39,()=>this.saveName(),{selected:true,size:16});
    if(e.keyboard){
      const rows=['QWERTYUIOP','ASDFGHJKL','ZXCVBNM'];let ky=y+280;
      rows.forEach(row=>{const kw=Math.min(43,(w-48)/10),kx=x+(w-row.length*kw)/2;[...row].forEach((char,i)=>u.button('letter-'+char,char,kx+i*kw,ky,kw-3,35,()=>this.insert(char),{size:18}));ky+=42;});
      u.button('name-space','SPACE',x+w/2-65,ky,100,30,()=>this.insert(' '),{size:15});u.button('name-backspace','DEL',x+w/2+44,ky,57,30,()=>this.editKey({key:'Backspace'}),{size:15});
    }
  }
}
