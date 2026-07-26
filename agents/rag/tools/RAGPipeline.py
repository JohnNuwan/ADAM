
from haystack.document_stores import ElasticsearchDocumentStore
from haystack.nodes import DensePassageRetriever, EmbeddingRetriever
from haystack.pipelines import RetrieverQuestionAnsweringPipeline

def create_rag_pipeline(index_name, retriever_type='dpr'):
    document_store = ElasticsearchDocumentStore(host="localhost", port="9200", index=index_name)
    if retriever_type == 'dpr':
        retriever = DensePassageRetriever(document_store=document_store, query_embedding_model="facebook/dpr-question_encoder-single-nq-base",
                                          passage_embedding_model="facebook/dpr-ctx_encoder-single-nq-base")
    else:
        retriever = EmbeddingRetriever(document_store=document_store, embedding_model="sentence-transformers/all-MiniLM-L6-v2")

    rag_pipeline = RetrieverQuestionAnsweringPipeline(retriever=retriever)
    return rag_pipeline

if __name__ == '__main__':
    rag_pipeline = create_rag_pipeline(index_name="document_index", retriever_type='dpr')
    result = rag_pipeline.run(query="Quelle est la capitale de la France?")
    print(result)
