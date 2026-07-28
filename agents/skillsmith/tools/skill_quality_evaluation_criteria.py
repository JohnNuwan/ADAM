
class SkillQualityEvaluationCriteria:
    def __init__(self):
        self.criteria = {
            "Accuracy": 0,
            "Coverage": 0,
            "Consistency": 0,
            "Performance": 0,
            "User满意度": 0
        }

    def evaluate_accuracy(self, skill_data, expected_outcomes):
        correct_count = 0
        for data_point in skill_data:
            if data_point["outcome"] == expected_outcomes[data_point["input"]]:
                correct_count += 1
        self.criteria["Accuracy"] = correct_count / len(skill_data)
        return self.criteria["Accuracy"]

    def evaluate_coverage(self, skill_data, all_possible_inputs):
        covered_inputs = set([data_point["input"] for data_point in skill_data])
        self.criteria["Coverage"] = len(covered_inputs) / len(all_possible_inputs)
        return self.criteria["Coverage"]

    def evaluate_consistency(self, skill_data):
        outcomes = [data_point["outcome"] for data_point in skill_data]
        unique_outcomes = set(outcomes)
        self.criteria["Consistency"] = 1 if len(unique_outcomes) == 1 else 0
        return self.criteria["Consistency"]

    def evaluate_performance(self, skill_data, performance_threshold):
        performance_scores = [data_point["performance_score"] for data_point in skill_data]
        self.criteria["Performance"] = sum([1 for score in performance_scores if score >= performance_threshold]) / len(performance_scores)
        return self.criteria["Performance"]

    def evaluate_user_satisfaction(self, user_feedback):
        positive_feedback = [feedback for feedback in user_feedback if feedback["rating"] > 3]
        self.criteria["User满意度"] = len(positive_feedback) / len(user_feedback)
        return self.criteria["User满意度"]

    def get_evaluation_report(self):
        report = "Skill Quality Evaluation Report:\n"
        for key, value in self.criteria.items():
            report += f"{key}: {value * 100:.2f}%\n"
        return report

# 示例数据
skill_data = [
    {"input": 1, "outcome": "A", "performance_score": 80},
    {"input": 2, "outcome": "B", "performance_score": 90},
    {"input": 3, "outcome": "A", "performance_score": 75}
]

expected_outcomes = {1: "A", 2: "B", 3: "C"}
all_possible_inputs = [1, 2, 3, 4, 5]
performance_threshold = 80
user_feedback = [
    {"rating": 4},
    {"rating": 2},
    {"rating": 5},
    {"rating": 3}
]

# 创建评估工具实例并进行评估
evaluation_tool = SkillQualityEvaluationCriteria()
evaluation_tool.evaluate_accuracy(skill_data, expected_outcomes)
evaluation_tool.evaluate_coverage(skill_data, all_possible_inputs)
evaluation_tool.evaluate_consistency(skill_data)
evaluation_tool.evaluate_performance(skill_data, performance_threshold)
evaluation_tool.evaluate_user_satisfaction(user_feedback)

print(evaluation_tool.get_evaluation_report())
