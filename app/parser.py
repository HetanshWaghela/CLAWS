##this is for testing-- currently im not using PyMuPDF or any ML
##this is a simple parser that just looks for the text "Clause" and "Contract" in the pdf
##it will return the text and the page number

def parse_pdf(pdf_path: str) -> list[dict]:
    return [ 
        {
            "type": "Governance",
            "text": "This is governed by the laws of the Seven Kingdoms",
            "page": 1,
            "bbox": [72.0, 144.0, 468.0, 180.0],
            "score":0.92,
        }
    ]

