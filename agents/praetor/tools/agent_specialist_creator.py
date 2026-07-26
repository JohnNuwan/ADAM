
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

def load_data(filepath):
    return pd.read_csv(filepath)

def preprocess_data(data):
    X = data.drop('target', axis=1)
    y = data['target']
    return train_test_split(X, y, test_size=0.2, random_state=42)

def create_agent(X_train, y_train):
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model

if __name__ == '__main__':
    filepath = 'path_to_your_data.csv'
    data = load_data(filepath)
    X_train, X_test, y_train, y_test = preprocess_data(data)
    agent = create_agent(X_train, y_train)
    print("Agent créé avec succès.")
