
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split

# Sample data generation for demonstration purposes
def generate_sample_data():
    data = {
        'views': [1000, 2000, 3000, 4000, 5000],
        'engagement_rate': [0.05, 0.07, 0.08, 0.10, 0.12],
        'sponsorship_income': [100, 200, 300, 400, 500],
        'affiliate_income': [50, 100, 150, 200, 250]
    }
    return pd.DataFrame(data)

class MonetizationOpportunities:
    def __init__(self):
        self.data = generate_sample_data()
        self.sponsorship_model = LinearRegression()
        self.affiliate_model = LinearRegression()

    def train_models(self):
        X = self.data[['views', 'engagement_rate']]
        y_sponsorship = self.data['sponsorship_income']
        y_affiliate = self.data['affiliate_income']

        X_train, X_test, y_sponsorship_train, y_sponsorship_test = train_test_split(X, y_sponsorship, test_size=0.2, random_state=42)
        X_train, X_test, y_affiliate_train, y_affiliate_test = train_test_split(X, y_affiliate, test_size=0.2, random_state=42)

        self.sponsorship_model.fit(X_train, y_sponsorship_train)
        self.affiliate_model.fit(X_train, y_affiliate_train)

    def predict_monetization(self, views, engagement_rate):
        sponsorship_prediction = self.sponsorship_model.predict([[views, engagement_rate]])
        affiliate_prediction = self.affiliate_model.predict([[views, engagement_rate]])
        return {'sponsorship_income': sponsorship_prediction[0], 'affiliate_income': affiliate_prediction[0]}

if __name__ == "__main__":
    monetization_tool = MonetizationOpportunities()
    monetization_tool.train_models()
    prediction = monetization_tool.predict_monetization(6000, 0.15)
    print(prediction)
