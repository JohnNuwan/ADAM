class DocumentIndexer:
    def __init__(self):
        self.index = {}

    def add_document(self, document_id, document_content):
        # Ici, nous pourrions utiliser diverses méthodes d'indexation,
        # mais pour simplifier, nous allons juste stocker le contenu du document.
        self.index[document_id] = document_content

    def get_index(self):
        return self.index