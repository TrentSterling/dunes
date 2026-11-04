// Cockpit text uses the same SDF glyph pipeline as the HUD, into GPU render targets.
import {UI_COLORS as C} from './gpu-ui.js';

export function drawDash(g,s,boost){
  g.begin(1024,512);g.rect(0,0,1024,512,'#090e0b');
  const rpm=Math.max(0,s.rpm||0),mph=Math.round(Math.abs(s.speed||0)*2.23694);
  for(let i=0;i<40;i++){const threshold=i/40*8000;g.rect(32+i*24,42,18,35,rpm>threshold?(threshold<4800?'#7ee39a':threshold<6600?'#f5cd6d':'#ff5d50'):'#27372d',2);}
  for(let i=0;i<=8;i++)g.text(String(i),32+i*120,86,22,C.muted,{align:'center'});
  g.line(28,125,996,125,2,'#344b3b');
  g.text('SPEED',42,146,26,C.muted);g.text(String(mph),42,179,145,C.paper);g.text('MPH',322,282,28,C.orange);
  g.rect(427,154,150,184,'#293b2e',10);g.text('GEAR',502,167,25,C.orange,{align:'center'});
  g.text(s.gear===-1?'R':s.gear===0?'N':String(s.gear),502,195,113,C.paper,{align:'center'});
  g.text('RPM',631,146,26,C.muted);g.text(String(Math.round(rpm/10)*10),982,183,113,C.paper,{align:'right'});
  g.text(`BOOST ${Math.max(0,boost).toFixed(1)} PSI`,982,319,26,C.orange,{align:'right'});
  const load=Math.min(1,rpm/7000),time=performance.now()/1000;
  const cells=[['WATER','F',188+14*load+Math.sin(time*.05)*2],['OIL P','PSI',22+52*load],['OIL T','F',214+16*load],['FUEL','%',74],['TRANS','F',176+10*load],['VOLTS','V',14.1-.2*load]];
  cells.forEach(([label,unit,value],i)=>{const x=26+i*163;g.rect(x,393,153,94,'#1a2b20',5);g.text(label,x+10,402,21,C.muted);g.text(unit,x+10,452,19,C.orange);g.text(label==='VOLTS'?value.toFixed(1):String(Math.round(value)),x+141,433,45,C.paper,{align:'right'});});
  g.render({clear:true,flipY:true});
}

export function drawNavigator(g,s,radar,trail,odometer){
  g.begin(1024,640);g.rect(0,0,1024,640,'#0e1912');
  const range=450,mw=640,mh=552,cx=320,cy=320,ppm=mw/(range*2);
  if(radar?.reliefTexture&&s.pos){const size=radar.terrain.fineSize;
    g.image(radar.reliefTexture,0,44,mw,mh,{uv:[(s.pos.x-range+size/2)/size,(s.pos.z-range*mh/mw+size/2)/size,2*range/size,2*range*mh/mw/size]});
  }
  g.clip=[0,44,640,596];
  if(s.pos)for(let i=1;i<trail.length;i++)g.line(cx+(trail[i-1][0]-s.pos.x)*ppm,cy+(trail[i-1][1]-s.pos.z)*ppm,cx+(trail[i][0]-s.pos.x)*ppm,cy+(trail[i][1]-s.pos.z)*ppm,5,'#ffb76e');
  const heading=s.fwd?Math.atan2(s.fwd.x,-s.fwd.z):0;
  const arrow=[[-13,16],[0,-23],[13,16]],rotate=([x,y])=>[cx+x*Math.cos(heading)-y*Math.sin(heading),cy+x*Math.sin(heading)+y*Math.cos(heading)];
  for(let i=0;i<2;i++){const a=rotate(arrow[i]),b=rotate(arrow[i+1]);g.line(...a,...b,6,C.paper);}
  g.text('N',606,61,26,C.paper,{align:'center'});g.line(24,565,144,565,5,C.paper);g.text('0.1 MI',24,530,23,C.paper);
  g.clip=[0,0,1024,640];g.rect(0,0,1024,44,'#0e1912');g.text('DUNENAV',18,7,27,C.orange);g.text('IMPERIAL SAND DUNES',510,9,23,C.paper,{align:'center'});
  const hour=Math.floor(s.tod??15),minute=Math.floor(((s.tod??15)-hour)*60);g.text(`${hour}:${String(minute).padStart(2,'0')}`,1002,7,27,C.paper,{align:'right'});
  const deg=Math.round((heading*180/Math.PI+360)%360),tiles=[['SPEED',(Math.abs(s.speed||0)*2.23694).toFixed(1),'MPH'],['HEADING',String(deg),'DEG'],['ODOMETER',(odometer/1609.34).toFixed(1),'MI'],['ELEVATION',String(Math.round((s.pos?.y||0)*3.281)),'FT']];
  tiles.forEach(([label,value,unit],i)=>{const y=54+i*128;g.rect(654,y,356,116,'#1d3023',5);g.text(label,668,y+8,23,C.muted);g.text(value,944,y+38,61,C.paper,{align:'right'});g.text(unit,996,y+73,20,C.orange,{align:'right'});});
  g.rect(0,596,1024,44,'#0e1912');g.text('DUNES / LIVE NAVIGATION',20,602,25,C.paper);g.text('GLOBAL CONVOY',1000,604,23,C.orange,{align:'right'});
  g.render({clear:true,flipY:true});
}
