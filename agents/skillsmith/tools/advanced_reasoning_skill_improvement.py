
class AdvancedReasoningSkillImprovement:
    def __init__(self, analysis_results):
        self.analysis_results = analysis_results

    def identify_common_errors(self):
        common_errors = {}
        for result in self.analysis_results:
            error_type = result.get('error_type')
            if error_type not in common_errors:
                common_errors[error_type] = 0
            common_errors[error_type] += 1
        return common_errors

    def generate_exercises(self, common_errors):
        exercises = []
        for error_type, frequency in common_errors.items():
            for _ in range(frequency):
                exercise = {
                    "type": error_type,
                    "description": f"Exercice pour corriger l'erreur {error_type}",
                    "solution": f"Solution pour {error_type}"
                }
                exercises.append(exercise)
        return exercises

    def provide_feedback(self, exercise, user_response):
        feedback = ""
        if user_response == exercise["solution"]:
            feedback = "Correct! Vous avez bien compris."
        else:
            feedback = f"Incorrect. La bonne réponse est: {exercise['solution']}"
        return feedback

    def run_improvement_program(self):
        common_errors = self.identify_common_errors()
        exercises = self.generate_exercises(common_errors)
        for exercise in exercises:
            print(exercise["description"])
            user_response = input("Votre réponse: ")
            feedback = self.provide_feedback(exercise, user_response)
            print(feedback)

# Example usage:
analysis_results = [
    {"error_type": "logical_fallacy"},
    {"error_type": "oversimplification"},
    {"error_type": "logical_fallacy"}
]

improvement_tool = AdvancedReasoningSkillImprovement(analysis_results)
improvement_tool.run_improvement_program()
