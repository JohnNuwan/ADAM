
import numpy as np
from sklearn.model_selection import GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

class ParamètresOptimisation:
    def __init__(self, data):
        self.data = data
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer()),
            # Placeholder for the model that will be optimized
            ('model', None),
        ])
        self.param_grid = {
            'tfidf__ngram_range': [(1, 1), (1, 2), (1, 3)],
            'tfidf__max_df': [0.5, 0.75, 1.0],
            'tfidf__min_df': [1, 2, 3],
        }

    def optimize(self, model, scoring='accuracy'):
        self.pipeline.set_params(model=model)
        grid_search = GridSearchCV(self.pipeline, self.param_grid, cv=5, scoring=scoring)
        grid_search.fit(self.data['text'], self.data['labels'])
        return grid_search.best_params_, grid_search.best_score_

if __name__ == '__main__':
    from sklearn.datasets import fetch_20newsgroups
    from sklearn.linear_model import LogisticRegression

    categories = ['alt.atheism', 'soc.religion.christian', 'comp.graphics', 'sci.med']
    twenty_train = fetch_20newsgroups(subset='train', categories=categories, shuffle=True, random_state=42)

    data = {'text': twenty_train.data, 'labels': twenty_train.target}
    optimizer = ParamètresOptimisation(data)
    best_params, best_score = optimizer.optimize(LogisticRegression())
    print(f"Best parameters: {best_params}")
    print(f"Best score: {best_score}")
