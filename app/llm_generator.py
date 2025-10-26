import torch
import logging

class LLMGenerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
    def load_model(self):
        try:
            print("Loading RoBERTa legal Q&A model...")
            
            from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering
            
            # Use pipeline for easier question-answering
            self.pipeline = pipeline(
                "question-answering", 
                model="Rakib/roberta-base-on-cuad",
                device=0 if self.device == "cuda" else -1
            )
            
            # Also load model directly for more control if needed
            self.tokenizer = AutoTokenizer.from_pretrained("Rakib/roberta-base-on-cuad")
            self.model = AutoModelForQuestionAnswering.from_pretrained("Rakib/roberta-base-on-cuad")
            
            self.model.to(self.device)
            self.model.eval()
            print("RoBERTa legal Q&A model loaded successfully")
            return True
        except Exception as e:
            print(f"Failed to load RoBERTa legal model: {e}")
            print("LLM functionality will be disabled - using rule-based responses only")
            return False
    
    def generate_explanation(self, clause_text, question):
        if not self.pipeline:
            if not self.model:
                self.load_model()
            if not self.pipeline:
                return "No explanation available"
        
        try:
            # RAG-based approach: Find most relevant clauses first
            relevant_clauses = self._find_relevant_clauses(clause_text, question)
            
            if not relevant_clauses:
                return "No relevant information found in the contract for this question."
            
            # Use the most relevant clause as context
            best_context = relevant_clauses[0]
            
            # Get answer from the legal Q&A model
            result = self.pipeline(
                question=question,
                context=best_context,
                max_answer_len=300,
                handle_impossible_answer=True
            )
            
            if result['answer'] and result['answer'] != "":
                confidence = result.get('score', 0)
                answer = result['answer']
                
                # Format with confidence and additional context
                if confidence > 0.7:
                    response = f"**High Confidence Answer:** {answer}"
                elif confidence > 0.4:
                    response = f"**Answer:** {answer}"
                else:
                    response = f"**Answer (Low Confidence):** {answer}"
                
                # Add additional relevant clauses if available
                if len(relevant_clauses) > 1:
                    response += f"\n\n**Additional Relevant Information:**"
                    for i, clause in enumerate(relevant_clauses[1:3], 1):  # Show up to 2 more
                        response += f"\n- {clause[:150]}..."
                
                return response
            else:
                return "No specific answer found in the contract text."
                
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "No explanation available"
    
    def _find_relevant_clauses(self, full_text, question):
        """Find the most relevant clauses for the question using keyword matching"""
        # Split text into sentences/paragraphs
        import re
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Extract keywords from question
        question_lower = question.lower()
        keywords = []
        
        # Legal term mappings
        legal_terms = {
            'termination': ['terminate', 'end', 'expire', 'cancel', 'termination'],
            'liability': ['liability', 'liable', 'responsible', 'damages', 'indemnify'],
            'payment': ['payment', 'pay', 'fee', 'cost', 'price', 'compensation'],
            'confidentiality': ['confidential', 'secret', 'proprietary', 'non-disclosure'],
            'assignment': ['assign', 'transfer', 'delegate', 'assignment'],
            'governing law': ['governing law', 'jurisdiction', 'legal', 'court'],
            'force majeure': ['force majeure', 'act of god', 'unforeseeable'],
            'warranty': ['warranty', 'warrant', 'guarantee', 'represent'],
            'breach': ['breach', 'violate', 'default', 'non-compliance'],
            'remedy': ['remedy', 'damages', 'injunction', 'specific performance']
        }
        
        # Find relevant terms
        for term, variations in legal_terms.items():
            if any(v in question_lower for v in variations):
                keywords.extend(variations)
        
        # Add general keywords from question
        question_words = [w for w in question_lower.split() if len(w) > 3]
        keywords.extend(question_words)
        
        # Score sentences based on keyword matches
        scored_sentences = []
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            for keyword in keywords:
                if keyword in sentence_lower:
                    score += 1
                    # Bonus for exact matches
                    if keyword in sentence_lower.split():
                        score += 2
            
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # Sort by relevance and return top matches
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        return [sentence for score, sentence in scored_sentences[:5]]

_llm_generator = None

def get_llm_generator():
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMGenerator()
    return _llm_generator
