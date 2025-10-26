##PDF parser using pattern-based legal clause detection
import fitz
from typing import List
import re

def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Parse PDF using pattern-based legal clause detection.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of detected clauses with type, text, page, bbox, and score
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []

    full_text = ""
    page_data = []
    
    for page_index, page in enumerate(doc, start=1):
        try:
            page_text = page.get_text()
            full_text += page_text + "\n"
            page_data.append((page_index, page, page_text))
        except Exception:
            continue
    
    if not full_text.strip():
        doc.close()
        return []
    
    # Use pattern-based detection
    print("Using pattern-based clause detection...")
    detected_clauses = _detect_legal_clauses_fallback(full_text, page_data)
    
    # Add highlights to PDF
    for clause in detected_clauses:
        try:
            _highlight_clause_in_pdf(doc, clause['page'], clause['text'], clause['type'])
        except Exception as e:
            print(f"Could not highlight {clause['type']}: {e}")
    
    try:
        highlighted_pdf_path = pdf_path.replace('.pdf', '_highlighted.pdf')
        doc.save(highlighted_pdf_path)
        print(f"Highlighted PDF saved to: {highlighted_pdf_path}")
    except Exception as e:
        print(f"Failed to save highlighted PDF: {e}")
    
    doc.close()
    return detected_clauses

def _get_text_bbox(doc, page_num, text):
    """Get bounding box for text on a specific page."""
    try:
        page = doc[page_num - 1]
        rects = page.search_for(text)
        if rects:
            return [rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1]
        else:
            page_rect = page.rect
            return [page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1]
    except Exception as e:
        print(f"Error in coordinate mapping: {e}")
        return [0, 0, 0, 0]

def _highlight_clause_in_pdf(doc, page_num, text, clause_type):
    """Add highlight annotation to PDF for a specific clause."""
    try:
        page = doc[page_num - 1]
        rects = page.search_for(text)
        
        for rect in rects:
            try:
                highlight = page.add_highlight_annot(rect)
                highlight.set_colors(stroke=(1, 1, 0))  # Yellow highlight
                highlight.set_info(title=f"CLAWS: {clause_type}")
                highlight.update()
                print(f"Added highlight for {clause_type} at {rect}")
            except Exception as e:
                print(f"Could not add highlight: {e}")
    except Exception as e:
        print(f"Could not highlight {clause_type} on page {page_num}: {e}")

def _detect_legal_clauses_fallback(full_text, page_data):
    """Fallback legal clause detection using patterns."""
    clauses = []
    
    legal_patterns = {
        "Document Name": [r"(?i)(agreement|contract|license|terms)"],
        "Parties": [r"(?i)(party|parties|company|corporation)"],
        "Effective Date": [r"(?i)(effective\s+date|commencement)"],
        "Governing Law": [r"(?i)(governing\s+law|jurisdiction)"],
        "Termination": [r"(?i)(termination|expiration)"],
        "Confidentiality": [r"(?i)(confidential|proprietary)"],
        "Anti-Assignment": [r"(?i)(assignment|transfer)"],
        "Indemnification": [r"(?i)(indemnify|hold\s+harmless)"],
        "Force Majeure": [r"(?i)(force\s+majeure|act\s+of\s+god)"],
        "Dispute Resolution": [r"(?i)(dispute|arbitration)"],
        "Severability": [r"(?i)(severability|invalid)"],
        "Entire Agreement": [r"(?i)(entire\s+agreement)"],
        "Amendment": [r"(?i)(amendment|modification)"],
        "Waiver": [r"(?i)(waiver|waive)"],
        "Notices": [r"(?i)(notice|notification)"],
        "Assignment": [r"(?i)(assign|assignment)"],
        "Insurance": [r"(?i)(insurance|coverage)"]
    }
    
    for page_index, page_obj, page_text in page_data:
        print(f"Fallback analyzing page {page_index} for legal clauses...")
        
        for clause_type, patterns in legal_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(page_text), match.end() + 50)
                    context = page_text[start:end].strip()
                    context = re.sub(r'\s+', ' ', context)
                    
                    if len(context) > 20:
                        clauses.append({
                            "type": clause_type,
                            "text": context,
                            "page": page_index,
                            "bbox": [0, 0, 0, 0],
                            "score": 0.8
                        })
                        print(f"Fallback Found {clause_type}: {context[:50]}...")
                        break
    
    return clauses[:30]
