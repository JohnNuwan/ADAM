
import re

def parse_mission_objectives(mission_text):
    objectives = re.findall(r'\bobjectif\s*\d*:\s*(.*)', mission_text, re.IGNORECASE)
    return objectives

def interpret_mission(mission_text):
    interpreted = {}
    interpreted['objectives'] = parse_mission_objectives(mission_text)
    return interpreted

if __name__ == '__main__':
    mission_text = "Mission Alpha : objectif 1: atteindre la base ennemie. objectif 2: récupérer le document secret."
    mission_interpreted = interpret_mission(mission_text)
    print(mission_interpreted)
