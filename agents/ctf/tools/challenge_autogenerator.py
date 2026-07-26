
import random
import string

class ChallengeAutogenerator:
    def __init__(self, technique):
        self.technique = technique
        self.challenges = []

    def generate_challenge(self):
        challenge_title = f"Challenge based on {self.technique}"
        challenge_description = self._generate_description()
        challenge_flag = self._generate_flag()
        
        challenge = {
            "title": challenge_title,
            "description": challenge_description,
            "flag": challenge_flag
        }
        self.challenges.append(challenge)
        return challenge

    def _generate_description(self):
        techniques = ["reverse engineering", "cryptoanalysis", "network security"]
        description = f"Use your skills in {self.technique} to uncover the hidden message."
        if self.technique == "reverse engineering":
            description += " Analyze the binary and find the secret algorithm."
        elif self.technique == "cryptoanalysis":
            description += " Decrypt the ciphertext using known techniques."
        elif self.technique == "network security":
            description += " Capture and analyze network packets to extract the flag."
        return description

    def _generate_flag(self):
        return f"FLAG{{{self._random_string(16)}}}"

    @staticmethod
    def _random_string(length):
        letters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(letters) for i in range(length))

# Example usage:
autogenerator = ChallengeAutogenerator("reverse engineering")
challenge = autogenerator.generate_challenge()
print(challenge)
