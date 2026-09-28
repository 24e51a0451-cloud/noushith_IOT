import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('D:/IEEE/REPORT/noushith_IOT_ppt.pptx'));
await fs.writeFile('D:/GALATICX/masterhub_iot_noushith/artifacts/ppt_build/template-inspect.txt',(await p.inspect({kind:'slide,textbox,shape,image,layout',maxChars:1000000})).ndjson);
console.log('slides',p.slides.items.length);
console.log('collection',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)));
console.log('slide api',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides.items[1])));
console.log('shape collection',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides.items[1].shapes)));
for(let i of [0,1,2,13]){let s=p.slides.items[i]; console.log('SLIDE',i, 'shapes',s.shapes.items.map(x=>({id:x.id,text:String(x.text),pos:x.position})), 'images',s.images.items.map(x=>({id:x.id,frame:x.frame})));}
