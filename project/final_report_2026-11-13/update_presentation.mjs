// Update the existing Spaces deck in place. Never starts experiments.
export async function updatePresentation({presentation,input}) {
  const colors={bg:'#F6F7F9',ink:'#122E49',body:'#253D55',muted:'#526478',blue:'#275E8E',red:'#A34537'};
  if(presentation.slides.items.length !== input.expectedSlides) throw new Error('Deck changed since inspection');
  const beforeIds=presentation.slides.items.map(s=>s.toSnapshot().aid);
  while(presentation.slides.items.length<input.slides.length) presentation.slides.add({width:1280,height:720});
  if(presentation.slides.items.length!==input.slides.length) throw new Error('Unexpected excess slides');
  for(let index=0;index<input.slides.length;index++) {
    const slide=presentation.slides.getItem(index), spec=input.slides[index];
    slide.background.fill=colors.bg;
    const strings=[{text:spec.title,x:64,y:44,w:1150,h:92,size:40,color:'ink',bold:true}];
    if(spec.subtitle) strings.push({text:spec.subtitle,x:68,y:139,w:1130,h:65,size:24,color:'muted'});
    strings.push(...(spec.texts??[]));
    strings.push({text:spec.source,x:68,y:660,w:1130,h:35,size:17,color:'muted'});
    const oldShapes=[...slide.shapes.items];
    for(let i=0;i<strings.length;i++) {
      const b=strings[i];
      const shape=oldShapes[i]??slide.shapes.add({geometry:'textbox',fill:'none',line:{fill:'none',width:0}});
      shape.position={left:b.x??68,top:b.y,width:b.w??1130,height:b.h??70};
      shape.text=b.text;
      shape.text.style={fontFamily:'Arial',fontSize:b.size??28,color:colors[b.color]??b.color??colors.body,bold:b.bold??false};
    }
    const elements=await presentation.inspect({select:`$.slides[${index}].elements[*]`,include:['id','kind']});
    const excessShapeIds=oldShapes.slice(strings.length).map(x=>x.toSnapshot().aid);
    const oldTableIds=elements.records.filter(x=>x.kind==='table').map(x=>x.id);
    if(excessShapeIds.length||oldTableIds.length) presentation.delete([...excessShapeIds,...oldTableIds]);
    if(spec.table) {
      const t=spec.table, nr=t.values.length,nc=t.values[0].length;
      const table=slide.tables.add({rows:nr,columns:nc,left:t.x??68,top:t.y??220,width:t.w??1140,height:t.h??280,values:t.values,columnWidths:t.widths});
      table.borders.assign({fill:'#D9E1E8',width:1,style:'solid'});
      table.cells.block({row:0,column:0,rowCount:nr,columnCount:nc}).assign({textStyle:{fontFamily:'Arial',fontSize:t.size??24,color:colors.body},margins:{left:16,right:12,top:10,bottom:10},anchor:'center'});
      for(let r=0;r<nr;r++)for(let c=0;c<nc;c++) {
        const cell=table.getCell(r,c);cell.fill=r===0?'#193E60':r%2===1?'#FFFFFF':'#EAF0F5';
        cell.text.style={fontFamily:'Arial',fontSize:t.size??24,color:r===0?'#FFFFFF':colors.body,bold:r===0};
      }
    }
    slide.speakerNotes.text=spec.notes;
  }
  const afterIds=presentation.slides.items.map(s=>s.toSnapshot().aid);
  for(let i=0;i<beforeIds.length;i++) if(beforeIds[i]!==afterIds[i]) throw new Error('Original slide identity changed');
  return {slideCount:afterIds.length,preservedOriginalSlides:beforeIds.length,slideIds:afterIds};
}
