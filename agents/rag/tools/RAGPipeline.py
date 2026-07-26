def create_RAG_pipeline(semantic_search_engine):
    # Initialisation du pipeline RAG
    rag_pipeline = RAGPipeline()
    rag_pipeline.set_semantic_search_engine(semantic_search_engine)
    return rag_pipeline