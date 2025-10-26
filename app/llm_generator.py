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
            import torch
            
            # Load with optimizations for faster loading
            self.tokenizer = AutoTokenizer.from_pretrained(
                "Rakib/roberta-base-on-cuad",
                use_fast=True  # Use fast tokenizer
            )
            
            self.model = AutoModelForQuestionAnswering.from_pretrained(
                "Rakib/roberta-base-on-cuad",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,  # Use half precision on GPU
                low_cpu_mem_usage=True  # Reduce memory usage
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            # Create pipeline after model is loaded
            self.pipeline = pipeline(
                "question-answering", 
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1
            )
            
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
            
            # Try multiple approaches for better answers
            answers = []
            
            # Approach 1: Use the most relevant clause
            best_context = relevant_clauses[0]
            result1 = self.pipeline(
                question=question,
                context=best_context,
                max_answer_len=200,
                handle_impossible_answer=True
            )
            
            if result1['answer'] and result1['answer'] != "" and result1['score'] > 0.1:
                answers.append((result1['answer'], result1['score'], "Primary"))
            
            # Approach 2: Use multiple relevant clauses combined
            if len(relevant_clauses) > 1:
                combined_context = " ".join(relevant_clauses[:3])  # Use top 3
                result2 = self.pipeline(
                    question=question,
                    context=combined_context,
                    max_answer_len=300,
                    handle_impossible_answer=True
                )
                
                if result2['answer'] and result2['answer'] != "" and result2['score'] > 0.1:
                    answers.append((result2['answer'], result2['score'], "Combined"))
            
            # Approach 3: For general questions, try with document summary
            if "what is" in question.lower() or "about" in question.lower():
                # Create a summary context
                summary_context = self._create_summary_context(clause_text)
                result3 = self.pipeline(
                    question=question,
                    context=summary_context,
                    max_answer_len=400,
                    handle_impossible_answer=True
                )
                
                if result3['answer'] and result3['answer'] != "" and result3['score'] > 0.05:
                    answers.append((result3['answer'], result3['score'], "Summary"))
            
            # Choose the best answer
            if answers:
                # Sort by confidence score
                answers.sort(key=lambda x: x[1], reverse=True)
                best_answer, best_score, method = answers[0]
                
                # Format response
                if best_score > 0.7:
                    response = f"**High Confidence Answer:** {best_answer}"
                elif best_score > 0.4:
                    response = f"**Answer:** {best_answer}"
                else:
                    response = f"**Answer (Low Confidence):** {best_answer}"
                
                # Add method info for debugging
                response += f"\n\n*Source: {method} analysis*"
                
                # Add additional relevant clauses if available
                if len(relevant_clauses) > 1:
                    response += f"\n\n**Additional Relevant Information:**"
                    for i, clause in enumerate(relevant_clauses[1:3], 1):
                        response += f"\n- {clause[:150]}..."
                
                return response
            else:
                return "No specific answer found in the contract text."
                
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "No explanation available"
    
    def _create_summary_context(self, full_text):
        """Create a summary context for general questions"""
        import re
        
        # Extract key sentences
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Look for key contract elements
        key_phrases = []
        
        # Find document name/title
        for sentence in sentences[:10]:
            if any(word in sentence.lower() for word in ['agreement', 'contract', 'terms', 'conditions']):
                key_phrases.append(sentence)
                break
        
        # Find parties
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['party', 'parties', 'between', 'company', 'corporation']):
                key_phrases.append(sentence)
                if len(key_phrases) >= 2:
                    break
        
        # Find purpose/scope
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['purpose', 'scope', 'objectives', 'services', 'products']):
                key_phrases.append(sentence)
                break
        
        # Combine key phrases
        if key_phrases:
            return " ".join(key_phrases[:5])  # Use top 5 key phrases
        else:
            # Fallback: use first few sentences
            return " ".join(sentences[:3])
    
    def _find_relevant_clauses(self, full_text, question):
        """Find the most relevant clauses for the question using keyword matching"""
        import re
        
        # Split text into sentences/paragraphs
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Extract keywords from question
        question_lower = question.lower()
        keywords = []
        
        # Enhanced legal term mappings
        legal_terms = {
            'contract_about': ['agreement', 'contract', 'terms', 'conditions', 'purpose', 'scope', 'objectives'],
            'parties': ['party', 'parties', 'between', 'company', 'corporation', 'entity', 'person'],
            'termination': ['terminate', 'end', 'expire', 'cancel', 'termination', 'duration'],
            'liability': ['liability', 'liable', 'responsible', 'damages', 'indemnify', 'indemnification'],
            'payment': ['payment', 'pay', 'fee', 'cost', 'price', 'compensation', 'remuneration'],
            'confidentiality': ['confidential', 'secret', 'proprietary', 'non-disclosure', 'privacy'],
            'assignment': ['assign', 'transfer', 'delegate', 'assignment', 'novation'],
            'governing_law': ['governing law', 'jurisdiction', 'legal', 'court', 'venue'],
            'force_majeure': ['force majeure', 'act of god', 'unforeseeable', 'circumstances'],
            'warranty': ['warranty', 'warrant', 'guarantee', 'represent', 'representation'],
            'breach': ['breach', 'violate', 'default', 'non-compliance', 'failure'],
            'remedy': ['remedy', 'damages', 'injunction', 'specific performance', 'relief']
        }
        
        # Find relevant terms based on question type
        for term, variations in legal_terms.items():
            if any(v in question_lower for v in variations):
                keywords.extend(variations)
        
        # Add general keywords from question (more aggressive)
        question_words = [w for w in question_lower.split() if len(w) > 2]  # Lower threshold
        keywords.extend(question_words)
        
        # For "what is" questions, add general contract terms
        if "what is" in question_lower or "about" in question_lower:
            keywords.extend(['agreement', 'contract', 'document', 'terms', 'conditions', 'purpose'])
        
        # Score sentences based on keyword matches
        scored_sentences = []
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            for keyword in keywords:
                if keyword in sentence_lower:
                    score += 1
                    # Bonus for exact word matches
                    if keyword in sentence_lower.split():
                        score += 2
                    # Bonus for beginning of sentence
                    if sentence_lower.startswith(keyword):
                        score += 1
            
            # Special scoring for contract identification
            if any(word in sentence_lower for word in ['agreement', 'contract', 'terms', 'conditions']):
                score += 3
            
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # Sort by relevance and return top matches
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        return [sentence for score, sentence in scored_sentences[:8]]  # Return more clauses

_llm_generator = None

def get_llm_generator():
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMGenerator()
    return _llm_generator
