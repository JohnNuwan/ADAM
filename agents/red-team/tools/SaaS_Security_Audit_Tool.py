
import requests
from bs4 import BeautifulSoup

class SaaSSecurityAuditTool:
    def __init__(self):
        self.vulnerabilities = []

    def scan_system(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            self.check_xss(soup)
            self.check_sql_injection(url)
            self.check_csrf(soup)

    def check_xss(self, soup):
        forms = soup.find_all('form')
        for form in forms:
            action = form.get('action')
            method = form.get('method', 'GET').lower()
            if method == 'get':
                self.vulnerabilities.append("Potential XSS vulnerability in form with GET method at URL: " + action)
            else:
                inputs = form.find_all('input')
                for input_tag in inputs:
                    if input_tag.get('type') == 'text':
                        self.vulnerabilities.append("Potential XSS vulnerability due to text input field at URL: " + action)
                        break

    def check_sql_injection(self, url):
        test_payloads = ["'", '"', ' OR 1=1']
        for payload in test_payloads:
            response = requests.get(url + "?" + payload)
            if response.status_code == 200 and ("SQL syntax" in response.text or "mysql_fetch" in response.text):
                self.vulnerabilities.append("Potential SQL Injection vulnerability detected at URL: " + url)

    def check_csrf(self, soup):
        forms = soup.find_all('form')
        for form in forms:
            if not form.find('input', {'name': 'csrf_token'}):
                self.vulnerabilities.append("Potential CSRF vulnerability due to lack of CSRF token in form at URL: " + form.get('action'))

    def generate_report(self):
        report = "Security Audit Report:\n\n"
        if self.vulnerabilities:
            report += "Vulnerabilities found:\n"
            for vulnerability in self.vulnerabilities:
                report += "- " + vulnerability + "\n"
        else:
            report += "No vulnerabilities found.\n"
        return report

    def provide_recommendations(self):
        recommendations = "Recommendations:\n\n"
        for vulnerability in self.vulnerabilities:
            if "XSS" in vulnerability:
                recommendations += "- Implement proper input validation and sanitization for all user inputs.\n"
            elif "SQL Injection" in vulnerability:
                recommendations += "- Use parameterized queries or prepared statements for database interactions.\n"
            elif "CSRF" in vulnerability:
                recommendations += "- Include a unique CSRF token in each form and validate it on the server side.\n"
        return recommendations

if __name__ == "__main__":
    tool = SaaSSecurityAuditTool()
    tool.scan_system("http://example.com")
    print(tool.generate_report())
    print(tool.provide_recommendations())
