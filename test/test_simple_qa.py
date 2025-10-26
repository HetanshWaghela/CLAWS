import pytest
from app.qa_system import parse_question, get_policy_explanation, retrieve_clause

def test_parse_question_general():
    """Test parsing of general contract questions."""
    assert parse_question("What is this contract about?") == "GENERAL_CONTRACT"
    assert parse_question("What is the contract about?") == "GENERAL_CONTRACT"
    assert parse_question("contract summary") == "GENERAL_CONTRACT"
    assert parse_question("explain the contract") == "GENERAL_CONTRACT"

def test_parse_question_specific():
    """Test parsing of specific clause questions."""
    assert parse_question("Why is the assignment clause risky?") == "Anti-Assignment"
    assert parse_question("What about governing law?") == "Governing Law"
    assert parse_question("Tell me about termination") == "Termination"
    assert parse_question("confidentiality clause") == "Confidentiality"
    assert parse_question("indemnification risks") == "Indemnification"
    assert parse_question("force majeure") == "Force Majeure"

def test_parse_question_unknown():
    """Test parsing of unknown questions."""
    assert parse_question("What is the weather?") == "GENERAL_QUESTION"
    assert parse_question("random question") == "GENERAL_QUESTION"

def test_get_policy_explanation():
    """Test policy explanation retrieval."""
    # Test existing clause types
    policy = get_policy_explanation("Anti-Assignment")
    assert policy is not None
    assert "risk" in policy
    assert policy["severity"] == "High"
    
    policy = get_policy_explanation("Governing Law")
    assert policy is not None
    assert "jurisdiction" in policy["risk"]
    
    # Test non-existing clause type
    policy = get_policy_explanation("NonExistent")
    assert policy is None

def test_retrieve_clause():
    """Test clause retrieval from detected clauses."""
    detected_clauses = [
        {"type": "Anti-Assignment", "text": "No assignment without consent", "page": 1, "bbox": [0, 0, 0, 0], "score": 0.9},
        {"type": "Governing Law", "text": "Governed by California law", "page": 2, "bbox": [0, 0, 0, 0], "score": 0.8}
    ]
    
    # Test finding existing clause
    clause = retrieve_clause("Anti-Assignment", detected_clauses)
    assert clause is not None
    assert clause["type"] == "Anti-Assignment"
    assert "assignment" in clause["text"].lower()
    
    # Test finding non-existing clause
    clause = retrieve_clause("Termination", detected_clauses)
    assert clause is None
