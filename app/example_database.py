"""
Example PDF Database for CLAWS Demo
Contains sample contracts that users can directly upload for testing
"""

EXAMPLE_PDFS = {
    "Co-Branding Agreement": {
        "filename": "StampscomInc_20001114_10-Q_EX-10.47_2631630_EX-10.47_Co-Branding Agreement.pdf",
        "description": "Co-Branding Agreement between Stamps.com and partner company",
        "clause_types": ["Confidentiality", "Termination", "Governing Law", "Indemnification"],
        "key_topics": ["branding", "marketing", "partnership", "revenue sharing"],
        "complexity": "Medium",
        "pages": "~15 pages"
    },
    "Affiliate Agreement": {
        "filename": "UsioInc_20040428_SB-2_EX-10.11_1723988_EX-10.11_Affiliate Agreement 2.pdf", 
        "description": "Affiliate Agreement for marketing and referral programs",
        "clause_types": ["Anti-Assignment", "Confidentiality", "Termination", "Force Majeure"],
        "key_topics": ["affiliate marketing", "commissions", "referrals", "compliance"],
        "complexity": "Medium",
        "pages": "~12 pages"
    }
}

def get_example_pdfs():
    """Get list of available example PDFs"""
    return EXAMPLE_PDFS

def get_example_pdf_path(filename):
    """Get full path to example PDF"""
    import os
    return os.path.join("examples", filename)

def get_example_pdf_info(filename):
    """Get information about a specific example PDF"""
    for name, info in EXAMPLE_PDFS.items():
        if info["filename"] == filename:
            return info
    return None
