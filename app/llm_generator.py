import torch
import logging

class LLMGenerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
    def load_model(self):
        try:
            print("Loading DialoGPT-medium for legal text analysis...")
            
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            self.tokenizer = AutoTokenizer.from_pretrained('microsoft/DialoGPT-medium')
            self.model = AutoModelForCausalLM.from_pretrained('microsoft/DialoGPT-medium')
            
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.model.to(self.device)
            self.model.eval()
            print("DialoGPT-medium loaded successfully")
            return True
        except Exception as e:
            print(f"Failed to load DialoGPT-medium: {e}")
            print("LLM functionality will be disabled - using rule-based responses only")
            return False
    
    def generate_explanation(self, clause_text, question):
        if not self.model or not self.tokenizer:
            if not self.model:
                self.load_model()
            if not self.model or not self.tokenizer:
                return "No explanation available"
        
        try:
            
            prompt = f"Legal Contract Analysis\n\nContext: {clause_text}\nQuestion: {question}\nAnswer:"
            
        
            inputs = self.tokenizer.encode(prompt, return_tensors='pt', max_length=512, truncation=True)
            inputs = inputs.to(self.device)
          
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 100,
                    num_return_sequences=1,
                    temperature=0.6,  
                    do_sample=True,
                    top_p=0.8,
                    top_k=40,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.2,
                    no_repeat_ngram_size=3  
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            if "Answer:" in response:
                answer = response.split("Answer:")[-1].strip()
            else:
                answer = response[len(prompt):].strip()
            
            if answer:
              
                sentences = answer.split('.')
                if len(sentences) > 1 and len(sentences[-1].strip()) < 5:
                    answer = '.'.join(sentences[:-1]) + '.'
                
                answer = answer.replace('Answer:', '').replace('answer:', '').strip()
              
                if len(answer) > 10:
                    return answer[:600]  
                else:
                    return "No explanation available"
            else:
                return "No explanation available"
                
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "No explanation available"

_llm_generator = None

def get_llm_generator():
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMGenerator()
    return _llm_generator
