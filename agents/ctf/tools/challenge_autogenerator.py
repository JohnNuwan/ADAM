
import random

class ChallengeAutogenerator:
    def __init__(self, lesson_plan):
        self.lesson_plan = lesson_plan

    def generate_challenge(self, lesson_name):
        lesson_details = self.lesson_plan.get(lesson_name, {})
        challenge_type = random.choice(list(lesson_details.keys()))
        challenge_content = random.choice(lesson_details[challenge_type])
        return f"Challenge for {lesson_name}: {challenge_type} - {challenge_content}"

def main():
    lesson_plan = {
        "Python Basics": {
            "Quiz": ["What is the syntax to print something in Python?", "How do you define a function?"],
            "Exercise": ["Write a program that prints 'Hello, World!'", "Create a function that adds two numbers."]
        },
        "Data Structures": {
            "Quiz": ["What is a list in Python?", "How do you create a dictionary?"],
            "Exercise": ["Write a program that creates a list of 5 elements.", "Create a dictionary with keys as integers and values as strings."]
        }
    }

    generator = ChallengeAutogenerator(lesson_plan)
    print(generator.generate_challenge("Python Basics"))
    print(generator.generate_challenge("Data Structures"))

if __name__ == '__main__':
    main()
