import post_generator
import content_advisor
import editorial_calendar_generator
import post_template_updater
import trend_analyzer
import weekly_trend_report
import monetization_opportunities
import sponsorship_affiliate_content_generator

class AdvancedContentGenerator:
    def __init__(self):
        self.post_generator = post_generator.PostGenerator()
        self.content_advisor = content_advisor.ContentAdvisor()
        self.editorial_calendar_generator = editorial_calendar_generator.EditorialCalendarGenerator()
        self.post_template_updater = post_template_updater.PostTemplateUpdater()
        self.trend_analyzer = trend_analyzer.TrendAnalyzer()
        self.weekly_trend_report = weekly_trend_report.WeeklyTrendReport()
        self.monetization_opportunities = monetization_opportunities.MonetizationOpportunities()
        self.sponsorship_affiliate_content_generator = sponsorship_affiliate_content_generator.SponsorshipAffiliateContentGenerator()

    def generate_content(self):
        trends = self.trend_analyzer.analyze_trends()
        report = self.weekly_trend_report.generate_report(trends)
        opportunities = self.monetization_opportunities.identify_opportunities(report)
        sponsored_posts = self.sponsorship_affiliate_content_generator.generate_sponsored_content(opportunities)
        advice = self.content_advisor.generate_advice(report)
        templates = self.post_template_updater.update_templates(advice)
        calendar = self.editorial_calendar_generator.generate_calendar(templates)
        posts = self.post_generator.generate_posts(calendar)
        return posts