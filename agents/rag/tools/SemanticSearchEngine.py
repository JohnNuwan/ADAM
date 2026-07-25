from semantic_search import create_engine
engine = create_engine(database='PostgreSQL', vector_field='embedding_vector')