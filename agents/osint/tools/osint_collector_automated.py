import osint_collector
from legal_checker import check_legality

def create_osint_tool(target):
    if not check_legality(target):
        raise Exception('Operation not legal')
    return osint_collector.collect_osint(target, ['LinkedIn', 'Twitter'])

# Create the tool with the target 'EVA'
tool = create_osint_tool('EVA')