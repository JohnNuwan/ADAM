
import json

class SkillFeedbackIntegration:
    def __init__(self):
        self.skill_name = "finance-skills"
        self.feedback_data = []

    def load_feedback(self, feedback_file):
        with open(feedback_file, 'r') as file:
            self.feedback_data = json.load(file)
    
    def analyze_feedback(self):
        improvement_points = {}
        for entry in self.feedback_data:
            if entry['skill'] == self.skill_name:
                for issue, details in entry['issues'].items():
                    if issue not in improvement_points:
                        improvement_points[issue] = []
                    improvement_points[issue].append(details)
        return improvement_points
    
    def generate_report(self, improvement_points, report_file):
        report = {
            "skill": self.skill_name,
            "improvement_points": improvement_points
        }
        with open(report_file, 'w') as file:
            json.dump(report, file, indent=4)

    def integrate_feedback(self, feedback_file, report_file):
        self.load_feedback(feedback_file)
        improvement_points = self.analyze_feedback()
        self.generate_report(improvement_points, report_file)


# Example usage
if __name__ == "__main__":
    tool = SkillFeedbackIntegration()
    tool.integrate_feedback('feedback.json', 'report.json')
