
import json
from datetime import datetime

class SystemStatusChecker:
    def get_latest_tools(self):
        # Simulate fetching data from a system status checker.
        tools = [
            {"name": "Tool A", "created_at": "2023-04-01T10:00:00Z"},
            {"name": "Tool B", "created_at": "2023-04-02T11:00:00Z"},
            {"name": "Tool C", "created_at": "2023-04-03T12:00:00Z"}
        ]
        return tools

class LatestToolsDocumentor:
    def __init__(self, system_status_checker):
        self.system_status_checker = system_status_checker

    def document_latest_tools(self):
        latest_tools = self.system_status_checker.get_latest_tools()
        documented_tools = []
        for tool in latest_tools:
            tool_name = tool['name']
            creation_date = datetime.fromisoformat(tool['created_at'])
            documented_tool = f"Tool Name: {tool_name}, Created At: {creation_date.strftime('%Y-%m-%d %H:%M:%S')}"
            documented_tools.append(documented_tool)
        return documented_tools

    def save_documentation(self, filename):
        documented_tools = self.document_latest_tools()
        with open(filename, 'w') as file:
            for tool in documented_tools:
                file.write(tool + '\n')

def main():
    system_status_checker = SystemStatusChecker()
    latest_tools_documentor = LatestToolsDocumentor(system_status_checker)
    latest_tools_documentor.save_documentation('latest_tools_documentation.txt')

if __name__ == "__main__":
    main()
