from RAGPipeline import create_rag_pipeline
pipeline = create_rag_pipeline()
pipeline.initialize(DocumentIndexer, SemanticSearchEngine)