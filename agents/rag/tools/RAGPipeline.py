
from haystack.nodes import DensePassageRetriever, EmbeddingRetriever
from haystack.document_stores import InMemoryDocumentStore
from haystack.pipelines import ExtractiveQAPipeline
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

class RAGPipeline:
    def __init__(self):
        self.document_store = InMemoryDocumentStore(embedding_dim=768)
        self.retriever = DensePassageRetriever(document_store=self.document_store,
                                               query_embedding_model="facebook/dpr-question_encoder-single-nq-base",
                                               passage_embedding_model="facebook/dpr-ctx_encoder-single-nq-base")
        self.tokenizer = AutoTokenizer.from_pretrained("facebook/dpr-question_encoder-single-nq-base")
        self.model = AutoModelForSeq2SeqLM.from_pretrained("facebook/rag-token-nq")

    def generate_response(self, question):
        preprocessed_question = self.tokenizer(question, return_tensors="pt")
        response = self.model.generate(**preprocessed_question)
        return self.tokenizer.decode(response[0], skip_special_tokens=True)

    def add_documents(self, documents):
        self.document_store.write_documents(documents)
        self.document_store.update_embeddings(self.retriever)

    def retrieve_answers(self, query):
        retriever = EmbeddingRetriever(document_store=self.document_store, embedding_model="sentence-transformers/all-MiniLM-L6-v2")
        pipeline = ExtractiveQAPipeline(retriever=retriever)
        prediction = pipeline.run(query=query)
        return prediction['answers']

# Example usage
if __name__ == "__main__":
    rag_pipeline = RAGPipeline()
    documents = [
        {"content": "EVA's financial autonomy is promoted through advanced AI systems.", "meta": {"source": "ADAM Knowledge Base"}},
        {"content": "The development towards AGI is a strategic goal for EVA.", "meta": {"source": "ADAM Knowledge Base"}}
    ]
    rag_pipeline.add_documents(documents)
    query = "What is the strategic goal for EVA in terms of AI?"
    answers = rag_pipeline.retrieve_answers(query)
    for answer in answers:
        print(answer.answer)
