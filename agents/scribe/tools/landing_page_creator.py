from jinja2 import Template

# Define the HTML template structure with placeholders for dynamic content
html_template = '''
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>EVA Products</title>
<style>
/* Add your styles here */
body {
  font-family: 'Inter', sans-serif;
  background-color: #050510;
}
.hero {
  /* Hero section with gradient */
}
.product-card {
  /* Product card design with glassmorphism */
}
.pricing {
  /* Pricing section styling */
}
.footer {
  /* Footer section styling */
}
</style>
</head>
<body>
<div class='hero'>
  <!-- Hero section content -->
</div>
<div class='product-cards'>
  <!-- 6 product cards -->
</div>
<div class='pricing'>
  <!-- Pricing section content -->
</div>
<footer class='footer'>
  <!-- Footer content -->
</footer>
</body>
</html>
'''

# Render the template and save it to a file
with open('landing_page.html', 'w') as f:
  f.write(Template(html_template).render())