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
            # Use the question-answering pipeline
            # The model expects context and question separately
            result = self.pipeline(
                question=question,
                context=clause_text,
                max_answer_len=200,
                handle_impossible_answer=True
            )
            
            if result['answer'] and result['answer'] != "":
                # Add confidence score if available
                confidence = result.get('score', 0)
                answer = result['answer']
                
                # Format the response nicely
                if confidence > 0.5:
                    return f"Based on the contract analysis: {answer}"
                else:
                    return f"Answer (low confidence): {answer}"
            else:
                return "No specific answer found in the contract text."
                
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "No explanation available"

_llm_generator = None

def get_llm_generator():
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMGenerator()
    return _llm_generator
