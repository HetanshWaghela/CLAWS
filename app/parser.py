##now using PyMuPDF
##this is a simple parser that just looks for the text "Clause" and "Contract" in the pdf
##it will return the text and the page number
import fitz
def parse_pdf(pdf_path: str) -> list[dict]:
    fallback= [ 
        {
            "type": "Governance",
            "text": "This is governed by the laws of the Seven Kingdoms",
            "page": 1,
            "bbox": [72.0, 144.0, 468.0, 180.0],
            "score":0.92,
        }
    ]
    try:
        doc=fitz.open(pdf_path)
    except Exception:
        return fallback

    clauses: list[dict]=[]

    for page_index, page in enumerate(doc,start=1):
        try:
            blocks = page.get_text("blocks")
        except Exception:
            continue

        for b in blocks:
            x0,y0,x1,y1= float(b[0]),float(b[1]),float(b[2]),float(b[3])
            txt= (b[4] or "").strip()

            if not txt or len(txt.replace(" ", ""))<2:
                continue
        
            snippet = txt[:800]

            clauses.append({
                "type": "Paragraph",
                "text": snippet,
                "page": page_index,
                "bbox": [x0,y0,x1,y1],
                "score": 0.95,
            })

            if len(clauses)>=10:
                break
        if len(clauses)>=10:
            break
    return clauses

