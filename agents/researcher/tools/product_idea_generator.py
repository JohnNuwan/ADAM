
import random

class ProductIdeaGenerator:
    def __init__(self):
        self.needs = [
            "automatisation des tâches répétitives",
            "amélioration de la productivité",
            "réduction des coûts opérationnels",
            "amélioration de la qualité du service client",
            "analyse avancée des données",
            "optimisation des ressources",
            "amélioration de la sécurité informatique",
            "amélioration de la collaboration interne"
        ]
        self.products = [
            "plateforme d'automatisation des workflows",
            "outil d'analyse prédictive",
            "solution de gestion des ressources",
            "robot conversationnel pour le service client",
            "système de recommandation d'actions",
            "outil de visualisation de données en temps réel",
            "solution de cybersécurité avancée",
            "plateforme de collaboration en ligne"
        ]

    def generate_idea(self):
        need = random.choice(self.needs)
        product = random.choice(self.products)
        return f"Un {product} pour {need}."

def main():
    generator = ProductIdeaGenerator()
    for _ in range(5):
        print(generator.generate_idea())

if __name__ == "__main__":
    main()
