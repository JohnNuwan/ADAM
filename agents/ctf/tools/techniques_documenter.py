def techniques_documenter(lessons):
    with open('techniques_apprendues.txt', 'w') as file:
        for lesson in lessons:
            file.write('- ' + lesson + '\n')
    return 'Documentation des techniques terminée.'