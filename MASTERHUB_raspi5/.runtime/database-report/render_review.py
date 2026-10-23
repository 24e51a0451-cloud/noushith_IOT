import pypdfium2 as pdfium
from pypdf import PdfReader
from pathlib import Path
p=Path('.runtime/database-report/review.pdf')
r=PdfReader(p)
print('Pages:',len(r.pages))
for n,page in enumerate(r.pages):
 t=page.extract_text()
 print(n+1,len(t),t[:75].replace('\n',' '))
doc=pdfium.PdfDocument(str(p))
for n,page in enumerate(doc):
 page.render(scale=1.25).to_pil().save(f'.runtime/database-report/page-{n+1}.png')
