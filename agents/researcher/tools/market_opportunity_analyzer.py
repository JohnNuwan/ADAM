
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

class MarketOpportunityAnalyzer:
    def __init__(self, data_path):
        self.data = pd.read_csv(data_path)
        self.model = None

    def preprocess_data(self):
        # Assuming the dataset has columns: 'revenue', 'ia_investment', 'saas_adam_options'
        self.data.dropna(inplace=True)
        features = ['ia_investment', 'saas_adam_options']
        target = 'revenue'
        self.X = self.data[features]
        self.y = self.data[target]

    def train_model(self):
        X_train, X_test, y_train, y_test = train_test_split(self.X, self.y, test_size=0.2, random_state=42)
        self.model = LinearRegression()
        self.model.fit(X_train, y_train)
        predictions = self.model.predict(X_test)
        mse = mean_squared_error(y_test, predictions)
        print(f"Mean Squared Error: {mse}")

    def predict_revenue(self, ia_investment, saas_adam_options):
        if self.model:
            return self.model.predict([[ia_investment, saas_adam_options]])[0]
        else:
            raise Exception("Model not trained yet.")

# Example usage
if __name__ == "__main__":
    analyzer = MarketOpportunityAnalyzer('path_to_your_data.csv')
    analyzer.preprocess_data()
    analyzer.train_model()
    predicted_revenue = analyzer.predict_revenue(1000000, 5)
    print(f"Predicted Revenue: {predicted_revenue}")
