import re
from collections import Counter
from typing import List, Dict, Any, Optional

def text_semantics_skill(components: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyse sémantique du texte basée sur les composants identifiés.
    
    Args:
        components: Liste de dictionnaires représentant les composants textuels.
                   Chaque composant doit avoir au moins une clé 'text' ou 'content'.
    
    Returns:
        Dictionnaire contenant les résultats de l'analyse sémantique :
        - 'word_frequencies': fréquence des mots
        - 'sentiment_score': score de sentiment (-1 à 1)
        - 'key_phrases': phrases clés extraites
        - 'language': langue détectée
        - 'summary': résumé du texte
    """
    # Extraire tout le texte des composants
    full_text = ""
    for comp in components:
        if isinstance(comp, dict):
            text = comp.get('text', comp.get('content', ''))
            if isinstance(text, str):
                full_text += text + " "
    
    full_text = full_text.strip()
    
    if not full_text:
        return {
            'word_frequencies': {},
            'sentiment_score': 0.0,
            'key_phrases': [],
            'language': 'unknown',
            'summary': ''
        }
    
    # Nettoyage et tokenisation
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', full_text.lower())
    
    # Fréquences des mots (exclure les stopwords courants)
    stopwords = {
        'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'est', 'sont',
        'dans', 'pour', 'sur', 'avec', 'par', 'que', 'qui', 'quoi', 'dont',
        'ou', 'mais', 'donc', 'car', 'ni', 'ne', 'pas', 'plus', 'très',
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'is',
        'it', 'as', 'by', 'with', 'from', 'that', 'this', 'these', 'those'
    }
    
    filtered_words = [w for w in words if w not in stopwords and len(w) > 2]
    word_freq = dict(Counter(filtered_words).most_common(20))
    
    # Analyse de sentiment basique (lexique français/anglais)
    positive_words = {
        'bon', 'bien', 'excellent', 'super', 'magnifique', 'beau', 'belle',
        'génial', 'parfait', 'merveilleux', 'formidable', 'agréable',
        'good', 'great', 'excellent', 'wonderful', 'amazing', 'beautiful',
        'perfect', 'fantastic', 'awesome', 'nice', 'happy', 'love'
    }
    negative_words = {
        'mauvais', 'mal', 'terrible', 'horrible', 'affreux', 'détestable',
        'triste', 'décevant', 'désagréable', 'pénible', 'ennuyeux',
        'bad', 'terrible', 'horrible', 'awful', 'ugly', 'sad', 'disappointing',
        'hate', 'angry', 'worst', 'poor', 'boring', 'annoying'
    }
    
    pos_count = sum(1 for w in filtered_words if w in positive_words)
    neg_count = sum(1 for w in filtered_words if w in negative_words)
    total_sentiment_words = pos_count + neg_count
    
    if total_sentiment_words > 0:
        sentiment_score = (pos_count - neg_count) / total_sentiment_words
    else:
        sentiment_score = 0.0
    
    # Extraction de phrases clés (bigrammes fréquents)
    bigrams = []
    for i in range(len(filtered_words) - 1):
        bigram = f"{filtered_words[i]} {filtered_words[i+1]}"
        bigrams.append(bigram)
    
    bigram_freq = Counter(bigrams)
    key_phrases = [phrase for phrase, count in bigram_freq.most_common(5) if count > 1]
    
    # Détection de langue basique
    french_chars = len(re.findall(r'[éèêëàâäùûüôöîïç]', full_text))
    english_chars = len(re.findall(r'[w]', full_text))
    
    if french_chars > english_chars:
        language = 'fr'
    elif english_chars > french_chars:
        language = 'en'
    else:
        # Vérifier les mots spécifiques
        french_words = {'le', 'la', 'les', 'des', 'dans', 'pour', 'avec', 'sur', 'que', 'qui'}
        english_words = {'the', 'and', 'with', 'from', 'that', 'this', 'these', 'those'}
        
        french_count = sum(1 for w in words if w in french_words)
        english_count = sum(1 for w in words if w in english_words)
        
        language = 'fr' if french_count > english_count else 'en' if english_count > french_count else 'unknown'
    
    # Génération d'un résumé simple (premières phrases significatives)
    sentences = re.split(r'[.!?]+', full_text)
    meaningful_sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]
    
    if meaningful_sentences:
        summary = ' '.join(meaningful_sentences[:2])
    else:
        summary = full_text[:200] if len(full_text) > 200 else full_text
    
    return {
        'word_frequencies': word_freq,
        'sentiment_score': round(sentiment_score, 3),
        'key_phrases': key_phrases,
        'language': language,
        'summary': summary
    }


if __name__ == '__main__':
    # Test simple
    test_components = [
        {'text': 'Ce site web est magnifique et très bien conçu. Le design est excellent.'},
        {'text': 'Les animations sont fluides et agréables. Vraiment un travail formidable.'}
    ]
    
    result = text_semantics_skill(test_components)
    print("Résultat de l'analyse sémantique :")
    print(f"Langue détectée : {result['language']}")
    print(f"Score de sentiment : {result['sentiment_score']}")
    print(f"Phrases clés : {result['key_phrases']}")
    print(f"Fréquences des mots : {result['word_frequencies']}")
    print(f"Résumé : {result['summary']}")