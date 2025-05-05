import stanza
from typing import List, Dict, Any

class NERProcessor:
    def __init__(self):
        # Download the English model if not already downloaded
        try:
            stanza.download('en')
        except Exception as e:
            print(f"Error downloading Stanza model: {e}")
        
        # Initialize the pipeline
        self.nlp = stanza.Pipeline(lang='en', processors='tokenize,ner')

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract named entities from the given text.
        
        Args:
            text (str): The text to process
            
        Returns:
            List[Dict[str, Any]]: List of entities with their text and type
        """
        try:
            doc = self.nlp(text)
            entities = []
            print(text)
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "type": ent.type
                })
            print(entities)
            return entities
        except Exception as e:
            print(f"Error processing text with NER: {e}")
            return []

# Example usage
if __name__ == "__main__":
    # Initialize the NER processor
    ner_processor = NERProcessor()
    
    # Example text
    text = "Call me at (555) 123-4567 or email me at john@example.com."
    
    # Extract entities
    entities = ner_processor.extract_entities(text)
    
    # Print results
    print("Extracted entities:")
    for entity in entities:
        print(f"Text: {entity['text']}, Type: {entity['type']}") 