
class Agent:
    def __init__(self, name):
        self.name = name
        self.tasks = []

    def assign_task(self, task):
        self.tasks.append(task)

    def perform_tasks(self):
        for task in self.tasks:
            print(f"{self.name} is performing task: {task}")
            # Here you can add logic to actually perform the task
        self.tasks.clear()

class MultiAgentArchitecturePlanner:
    def __init__(self):
        self.agents = {}

    def add_agent(self, agent_name):
        if agent_name not in self.agents:
            self.agents[agent_name] = Agent(agent_name)
        else:
            print(f"Agent {agent_name} already exists.")

    def remove_agent(self, agent_name):
        if agent_name in self.agents:
            del self.agents[agent_name]
        else:
            print(f"Agent {agent_name} does not exist.")

    def assign_task_to_agent(self, agent_name, task):
        if agent_name in self.agents:
            self.agents[agent_name].assign_task(task)
        else:
            print(f"Agent {agent_name} does not exist.")

    def execute_all_agents(self):
        for agent_name in self.agents:
            self.agents[agent_name].perform_tasks()

# Example usage
planner = MultiAgentArchitecturePlanner()
planner.add_agent("Agent1")
planner.add_agent("Agent2")

planner.assign_task_to_agent("Agent1", "Task1")
planner.assign_task_to_agent("Agent1", "Task2")
planner.assign_task_to_agent("Agent2", "Task3")

planner.execute_all_agents()
