// Author the connected presentation only. This file never calls an experiment.
export async function appendSlides({presentation,input}) {
  const colors={bg:'#F6F7F9',ink:'#122E49',body:'#253D55',muted:'#526478',blue:'#275E8E',red:'#A34537'};
  function text(slide,t,x,y,w,h,size=28,color=colors.body,bold=false){
    const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
    s.text=t;s.text.style={fontFamily:'Arial',fontSize:size,color,bold};return s;
  }
  if(input.removeInitialBlank){
    const first=presentation.slides.getItem(0);
    if(first.shapes.items.length!==0 || first.tables.items.length!==0 || first.images.items.length!==0) throw new Error('Initial slide is not blank');
    presentation.slides.keep([1]);
    presentation.slides.getItem(0).speakerNotes.text=input.coverNotes;
  }
  const added=[];
  for(const spec of input.slides){
    const s=presentation.slides.add({width:1280,height:720});s.background.fill=colors.bg;
    text(s,spec.title,64,44,1150,92,40,colors.ink,true);
    if(spec.subtitle)text(s,spec.subtitle,68,139,1130,65,24,colors.muted);
    for(const b of spec.texts??[])text(s,b.text,b.x??68,b.y,b.w??1130,b.h??70,b.size??28,colors[b.color]??b.color??colors.body,b.bold??false);
    if(spec.table){
      const t=spec.table;
      const table=s.tables.add({rows:t.values.length,columns:t.values[0].length,left:t.x??68,top:t.y??220,width:t.w??1140,height:t.h??280,values:t.values,columnWidths:t.widths});
      table.borders.assign({fill:'#D9E1E8',width:1,style:'solid'});
      table.cells.block({row:0,column:0,rowCount:t.values.length,columnCount:t.values[0].length}).assign({textStyle:{fontFamily:'Arial',fontSize:t.size??24,color:colors.body},margins:{left:16,right:12,top:10,bottom:10},anchor:'center'});
      for(let r=0;r<t.values.length;r++)for(let c=0;c<t.values[0].length;c++){
        const cell=table.getCell(r,c);cell.fill=r===0?'#193E60':r%2===1?'#FFFFFF':'#EAF0F5';
        cell.text.style={fontFamily:'Arial',fontSize:t.size??24,color:r===0?'#FFFFFF':colors.body,bold:r===0};
      }
    }
    if(spec.source)text(s,spec.source,68,660,1130,35,17,colors.muted);
    s.speakerNotes.text=spec.notes;
    added.push({index:presentation.slides.items.length,title:spec.title});
  }
  return {added,slideCount:presentation.slides.items.length};
}
