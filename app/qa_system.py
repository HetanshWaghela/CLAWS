from app.knowledge_base import LEGAL_KNOWLEDGE_BASE
from app.llm_generator import get_llm_generator
import re

def parse_question(question):
    question_lower = question.lower()
    
   
    general_patterns = [
        'what is the contract about', 'what is this contract', 'contract about', 'contract summary',
        'explain the contract', 'what are the risks', 'contract risks', 'overall risks',
        'what does this contract', 'contract purpose', 'contract overview', 'contract details',
        'what is this agreement', 'agreement about', 'what does the agreement', 'agreement summary',
        'tell me about this contract', 'describe the contract', 'contract analysis'
    ]
    
    if any(phrase in question_lower for phrase in general_patterns):
        return 'GENERAL_CONTRACT'
    
    if any(word in question_lower for word in ['assignment', 'assign', 'transfer']):
        return 'Anti-Assignment'
    elif any(word in question_lower for word in ['governing', 'law', 'jurisdiction']):
        return 'Governing Law'
    elif any(word in question_lower for word in ['termination', 'terminate', 'end']):
        return 'Termination'
    elif any(word in question_lower for word in ['confidential', 'proprietary', 'secret']):
        return 'Confidentiality'
    elif any(word in question_lower for word in ['indemnify', 'indemnification', 'liability']):
        return 'Indemnification'
    elif any(word in question_lower for word in ['force majeure', 'act of god', 'disaster']):
        return 'Force Majeure'
    else:
        return 'GENERAL_QUESTION'  

def get_policy_explanation(clause_type):
    if clause_type in LEGAL_KNOWLEDGE_BASE:
        return LEGAL_KNOWLEDGE_BASE[clause_type]
    return None

def retrieve_clause(clause_type, detected_clauses):
    for clause in detected_clauses:
        if clause['type'] == clause_type:
            return clause
    return None

def generate_contract_summary(detected_clauses, question):
    """Generate a comprehensive contract summary using detected clauses and LLM."""
    if not detected_clauses:
        return "No contract clauses were detected. Please ensure the contract was properly analyzed."
    
    clause_groups = {}
    for clause in detected_clauses:
        clause_type = clause.get('type', 'Other')
        if clause_type not in clause_groups:
            clause_groups[clause_type] = []
        clause_groups[clause_type].append(clause)
    
    if question.lower().strip() in ['what is the contract about', 'what is this contract about', 'contract summary']:
        return _generate_rule_based_summary(clause_groups)
    
    context = "Contract Analysis Summary:\n\n"
    context += f"Total clauses detected: {len(detected_clauses)}\n\n"
    
    for clause_type, clauses in clause_groups.items():
        context += f"{clause_type} clauses ({len(clauses)} found):\n"
        for i, clause in enumerate(clauses[:3]):  
            text = clause.get('text', '')[:150]
            page = clause.get('page', 1)
            context += f"  - Page {page}: {text}...\n"
        context += "\n"
    
    llm_generator = get_llm_generator()
    prompt = f"{context}\n\nQuestion: {question}\n\nPlease provide a comprehensive answer based on the contract analysis above:"
    
    try:
        llm_answer = llm_generator.generate_explanation(prompt, question)
        if llm_answer and llm_answer != "No explanation available" and len(llm_answer.strip()) > 20:
            return llm_answer
    except Exception as e:
        print(f"LLM generation error: {e}")
    
    return _generate_fallback_summary(clause_groups, question)

def _generate_rule_based_summary(clause_groups):
    """Generate a simple, reliable summary using rule-based approach."""
    summary = "**Contract Summary**\n\n"
    
  
    if 'Document Name' in clause_groups:
        doc_text = clause_groups['Document Name'][0]['text'][:200]
        summary += f"**Document**: {doc_text}...\n\n"
    
    
    if 'Parties' in clause_groups:
        parties_text = clause_groups['Parties'][0]['text'][:200]
        summary += f"**Parties**: {parties_text}...\n\n"
    
   
    summary += "**Key Provisions**:\n"
    
    
    legal_clauses = ['Governing Law', 'Termination', 'Confidentiality', 'Anti-Assignment', 'Indemnification', 'Force Majeure']
    business_clauses = ['Effective Date', 'Insurance', 'Notices', 'Amendment', 'Waiver']
    procedural_clauses = ['Dispute Resolution', 'Severability', 'Entire Agreement']
    
    legal_found = [c for c in legal_clauses if c in clause_groups]
    business_found = [c for c in business_clauses if c in clause_groups]
    procedural_found = [c for c in procedural_clauses if c in clause_groups]
    
    if legal_found:
        summary += f"• **Legal Framework**: {', '.join(legal_found)}\n"
    if business_found:
        summary += f"• **Business Terms**: {', '.join(business_found)}\n"
    if procedural_found:
        summary += f"• **Procedures**: {', '.join(procedural_found)}\n"
    
   
    high_risk = [c for c in ['Anti-Assignment', 'Governing Law', 'Termination', 'Indemnification'] if c in clause_groups]
    if high_risk:
        summary += f"\nHigh-Risk Areas: {', '.join(high_risk)}\n"
    
   
    total = sum(len(clauses) for clauses in clause_groups.values())
    summary += f"\nTotal Provisions: {total} clauses across {len(clause_groups)} categories"
    
    return summary

def _generate_fallback_summary(clause_groups, question):
    """Generate a structured summary when LLM fails."""
    summary = "Based on the contract analysis, here's what I found:\n\n"
    
   
    if 'Document Name' in clause_groups:
        doc_clauses = clause_groups['Document Name']
        summary += f"Document Type: {doc_clauses[0]['text'][:100]}...\n\n"
    
   
    if 'Parties' in clause_groups:
        parties_clauses = clause_groups['Parties']
        summary += f"Parties: {parties_clauses[0]['text'][:100]}...\n\n"
    
   
    if 'Effective Date' in clause_groups:
        date_clauses = clause_groups['Effective Date']
        summary += f"Effective Date: {date_clauses[0]['text'][:100]}...\n\n"
    
   
    summary += "Key Clauses Detected:\n"
    clause_descriptions = {
        'Governing Law': 'Determines which jurisdiction\'s laws apply',
        'Termination': 'Defines how the contract can be ended',
        'Confidentiality': 'Protects sensitive information',
        'Anti-Assignment': 'Restricts transfer of contract rights',
        'Indemnification': 'Defines liability and responsibility',
        'Force Majeure': 'Covers unexpected events and disruptions',
        'Dispute Resolution': 'Specifies how conflicts will be resolved',
        'Insurance': 'Defines insurance requirements',
        'Severability': 'Ensures contract remains valid if parts are invalid',
        'Entire Agreement': 'States this is the complete agreement',
        'Amendment': 'Defines how changes can be made',
        'Waiver': 'Defines rights that can be waived',
        'Notices': 'Specifies how communications should be sent'
    }
    
    for clause_type, clauses in clause_groups.items():
        if clause_type not in ['Document Name', 'Parties', 'Effective Date']:
            description = clause_descriptions.get(clause_type, 'Legal provision')
            summary += f"  • {clause_type}: {len(clauses)} clause(s) - {description}\n"
    
   
    high_risk_clauses = []
    medium_risk_clauses = []
    
    for clause_type in ['Anti-Assignment', 'Governing Law', 'Termination', 'Indemnification']:
        if clause_type in clause_groups:
            high_risk_clauses.append(clause_type)
    
    for clause_type in ['Confidentiality', 'Force Majeure', 'Dispute Resolution']:
        if clause_type in clause_groups:
            medium_risk_clauses.append(clause_type)
    
    if high_risk_clauses:
        summary += f"\nHigh-Risk Clauses: {', '.join(high_risk_clauses)}\n"
        summary += "These clauses may require careful review for potential legal risks.\n"
    
    if medium_risk_clauses:
        summary += f"\nMedium-Risk Clauses: {', '.join(medium_risk_clauses)}\n"
        summary += "These clauses should be reviewed for completeness and fairness.\n"
    
  
    total_clauses = sum(len(clauses) for clauses in clause_groups.values())
    summary += f"\nContract Overview:\n"
    summary += f"  • Total clauses detected: {total_clauses}\n"
    summary += f"  • Clause types: {len(clause_groups)}\n"
    
    if question.lower() in ['what is the contract about', 'what is this contract about']:
        summary += f"\nSummary: This appears to be a legal contract with {total_clauses} key provisions covering various aspects of the agreement between the parties. "
        if high_risk_clauses:
            summary += f"Pay special attention to the {len(high_risk_clauses)} high-risk clause(s) identified above."
        summary += " Review each clause carefully to understand your rights and obligations."
    
    return summary

def generate_answer(clause_text, policy, question):
    if not policy:
       
        if clause_text:
            llm_generator = get_llm_generator()
            llm_answer = llm_generator.generate_explanation(clause_text, question)
            if llm_answer != "No explanation available":
                return f"LLM Analysis: {llm_answer}"
        return "No risk information available for this clause type."
    
   
    answer = f"The {policy['severity'].lower()} risk with this clause is: {policy['risk']}"
    
    if clause_text:
        answer += f" In your contract, the clause states: '{clause_text[:100]}...'"
    
    answer += f" [Source: {policy['source']}]"
    
    return answer
