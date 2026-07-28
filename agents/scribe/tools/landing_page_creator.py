
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def landing_page():
    product_name = "Premium Widget"
    product_description = "The best widget available on the market today!"
    call_to_action = "Buy Now"
    return render_template('landing_page.html', product_name=product_name, product_description=product_description, call_to_action=call_to_action)

if __name__ == '__main__':
    app.run(debug=True)
