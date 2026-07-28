
class ProductServiceMarketingPlan:
    def __init__(self, product_name, target_audience, competition):
        self.product_name = product_name
        self.target_audience = target_audience
        self.competition = competition
        self.promotion_channels = []
        self.price_strategy = None
        self.sales_forecast = None

    def add_promotion_channel(self, channel):
        if channel not in self.promotion_channels:
            self.promotion_channels.append(channel)

    def set_price_strategy(self, strategy):
        self.price_strategy = strategy

    def set_sales_forecast(self, forecast):
        self.sales_forecast = forecast

    def generate_plan(self):
        plan = f"Marketing Plan for {self.product_name}\n"
        plan += f"Target Audience: {self.target_audience}\n"
        plan += "Promotion Channels:\n"
        for channel in self.promotion_channels:
            plan += f"- {channel}\n"
        plan += f"Price Strategy: {self.price_strategy}\n"
        plan += f"Sales Forecast: {self.sales_forecast}\n"
        return plan

# Example usage
if __name__ == "__main__":
    marketing_plan = ProductServiceMarketingPlan(
        product_name="Smart Watch",
        target_audience="Tech-savvy individuals aged 18-45",
        competition="Fitbit, Apple Watch"
    )
    marketing_plan.add_promotion_channel("Social Media Ads")
    marketing_plan.add_promotion_channel("Influencer Partnerships")
    marketing_plan.set_price_strategy("Competitive pricing with occasional discounts")
    marketing_plan.set_sales_forecast("First year: 10,000 units; Second year: 20,000 units")
    print(marketing_plan.generate_plan())
