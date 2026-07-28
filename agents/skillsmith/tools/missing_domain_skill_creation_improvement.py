
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

class MissingDomainSkillCreationImprovement:
    def __init__(self, data_path):
        self.data_path = data_path
        self.data = None
        self.model = None

    def load_data(self):
        self.data = pd.read_csv(self.data_path)
        return self.data

    def preprocess_data(self):
        # Assuming the last column is the target variable and all others are features
        X = self.data.iloc[:, :-1]
        y = self.data.iloc[:, -1]
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        return self.X_train, self.X_test, self.y_train, self.y_test

    def train_model(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(self.X_train, self.y_train)
        return self.model

    def evaluate_model(self):
        predictions = self.model.predict(self.X_test)
        report = classification_report(self.y_test, predictions)
        print(report)
        return report

    def run(self):
        self.load_data()
        self.preprocess_data()
        self.train_model()
        return self.evaluate_model()

# Example usage
if __name__ == "__main__":
    tool = MissingDomainSkillCreationImprovement(data_path="path/to/your/data.csv")
    evaluation_report = tool.run()
