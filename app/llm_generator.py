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
            
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                "Rakib/roberta-base-on-cuad",
                use_fast=True 
            )
            
            self.model = AutoModelForQuestionAnswering.from_pretrained(
                "Rakib/roberta-base-on-cuad",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32, 
                low_cpu_mem_usage=True  # 
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            
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
           
            contexts = self._create_multiple_contexts(clause_text, question)
            
            best_answer = None
            best_score = 0
            best_method = ""
         
            for context_name, context_text in contexts.items():
                if not context_text.strip():
                    continue
                    
                try:
                    result = self.pipeline(
                        question=question,
                        context=context_text,
                        max_answer_len=400,
                        handle_impossible_answer=True
                    )
                    
                    if result['answer'] and result['answer'].strip() != "":
                        score = result.get('score', 0)
                        
                       
                        if score > 0.01: 
                            if score > best_score:
                                best_answer = result['answer']
                                best_score = score
                                best_method = context_name
                                
                except Exception as e:
                    print(f"Error with {context_name}: {e}")
                    continue
            
         
            if best_answer:
               
                if best_score > 0.7:
                    response = f"**High Confidence Answer:** {best_answer}"
                elif best_score > 0.3:
                    response = f"**Answer:** {best_answer}"
                else:
                    response = f"**Answer (Low Confidence):** {best_answer}"
                
                response += f"\n\n*Source: {best_method} analysis (confidence: {best_score:.2f})*"
                return response
            
            # If no answer found, try to extract relevant information manually
            relevant_info = self._extract_relevant_info_manually(clause_text, question)
            if relevant_info:
                return f"**Answer:** {relevant_info}\n\n*Source: Manual extraction*"
            
            return "I couldn't find specific information about your question in this contract. The contract may not contain details about this topic, or the information might be worded differently than expected."
                
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "No explanation available"
    
    def _create_multiple_contexts(self, full_text, question):
        """Create multiple context strategies for better answer finding"""
        import re
        
        contexts = {}
        question_lower = question.lower()
        
    
        contexts['full_document'] = full_text[:4000] 
        
        
        relevant_clauses = self._find_relevant_clauses(full_text, question)
        if relevant_clauses:
            contexts['relevant_clauses'] = " ".join(relevant_clauses[:5])
        
 
        if 'payment' in question_lower:
            contexts['payment_focused'] = self._extract_payment_context(full_text)
        elif 'termination' in question_lower:
            contexts['termination_focused'] = self._extract_termination_context(full_text)
        elif 'liability' in question_lower or 'damage' in question_lower:
            contexts['liability_focused'] = self._extract_liability_context(full_text)
        elif 'confidential' in question_lower:
            contexts['confidentiality_focused'] = self._extract_confidentiality_context(full_text)
        elif 'what is' in question_lower or 'about' in question_lower:
            contexts['general_summary'] = self._create_summary_context(full_text)
        
       
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        contexts['document_start'] = " ".join(sentences[:10])
        

        question_words = [w for w in question_lower.split() if len(w) > 3]
        keyword_sentences = []
        for sentence in sentences:
            if any(word in sentence.lower() for word in question_words):
                keyword_sentences.append(sentence)
        if keyword_sentences:
            contexts['keyword_matches'] = " ".join(keyword_sentences[:8])
        
        return contexts
    
    def _extract_payment_context(self, full_text):
        """Extract payment-related information"""
        import re
        sentences = re.split(r'[.!?]+', full_text)
        payment_sentences = []
        
        payment_keywords = ['payment', 'pay', 'fee', 'cost', 'price', 'compensation', 'remuneration', 
                           'amount', 'dollar', 'currency', 'invoice', 'billing', 'charge']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in payment_keywords):
                payment_sentences.append(sentence)
        
        return " ".join(payment_sentences[:10])
    
    def _extract_termination_context(self, full_text):
        """Extract termination-related information"""
        import re
        sentences = re.split(r'[.!?]+', full_text)
        termination_sentences = []
        
        termination_keywords = ['termination', 'terminate', 'end', 'expire', 'cancel', 'duration', 
                               'period', 'term', 'validity']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in termination_keywords):
                termination_sentences.append(sentence)
        
        return " ".join(termination_sentences[:10])
    
    def _extract_liability_context(self, full_text):
        """Extract liability-related information"""
        import re
        sentences = re.split(r'[.!?]+', full_text)
        liability_sentences = []
        
        liability_keywords = ['liability', 'liable', 'responsible', 'damages', 'indemnify', 
                             'indemnification', 'hold harmless', 'defend', 'breach']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in liability_keywords):
                liability_sentences.append(sentence)
        
        return " ".join(liability_sentences[:10])
    
    def _extract_confidentiality_context(self, full_text):
        """Extract confidentiality-related information"""
        import re
        sentences = re.split(r'[.!?]+', full_text)
        confidentiality_sentences = []
        
        confidentiality_keywords = ['confidential', 'secret', 'proprietary', 'non-disclosure', 
                                   'privacy', 'information', 'data']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in confidentiality_keywords):
                confidentiality_sentences.append(sentence)
        
        return " ".join(confidentiality_sentences[:10])
    
    def _extract_relevant_info_manually(self, full_text, question):
        """Manually extract relevant information when AI fails"""
        import re
        question_lower = question.lower()
        

        sentences = re.split(r'[.!?]+', full_text)
        relevant_sentences = []
        
        question_words = [w for w in question_lower.split() if len(w) > 3]
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in question_words):
                relevant_sentences.append(sentence.strip())
        
        if relevant_sentences:
         
            return " ".join(relevant_sentences[:3])
        
        return None
    
    def _create_summary_context(self, full_text):
        """Create a summary context for general questions"""
        import re
        
      
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
    
        key_phrases = []
     
        for sentence in sentences[:10]:
            if any(word in sentence.lower() for word in ['agreement', 'contract', 'terms', 'conditions']):
                key_phrases.append(sentence)
                break
    
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['party', 'parties', 'between', 'company', 'corporation']):
                key_phrases.append(sentence)
                if len(key_phrases) >= 2:
                    break
 
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['purpose', 'scope', 'objectives', 'services', 'products']):
                key_phrases.append(sentence)
                break
  
        if key_phrases:
            return " ".join(key_phrases[:5])  
        else:
           
            return " ".join(sentences[:3])
    
    def _find_relevant_clauses(self, full_text, question):
        """Find the most relevant clauses for the question using keyword matching"""
        import re

        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

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
    
        for term, variations in legal_terms.items():
            if any(v in question_lower for v in variations):
                keywords.extend(variations)
  
        question_words = [w for w in question_lower.split() if len(w) > 2]  
        keywords.extend(question_words)
      
        if "what is" in question_lower or "about" in question_lower:
            keywords.extend(['agreement', 'contract', 'document', 'terms', 'conditions', 'purpose'])
    
        scored_sentences = []
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            for keyword in keywords:
                if keyword in sentence_lower:
                    score += 1
               
                    if keyword in sentence_lower.split():
                        score += 2
                   
                    if sentence_lower.startswith(keyword):
                        score += 1
            
       
            if any(word in sentence_lower for word in ['agreement', 'contract', 'terms', 'conditions']):
                score += 3
            
            if score > 0:
                scored_sentences.append((score, sentence))
        
    
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        return [sentence for score, sentence in scored_sentences[:8]]  

_llm_generator = None

def get_llm_generator():
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMGenerator()
    return _llm_generator
