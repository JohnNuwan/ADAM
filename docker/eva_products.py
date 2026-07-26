from flask import Flask
app = Flask(__name__)
HTML = r""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVA - Premium Landing Page</title>
    <style>
        body {
            background-color: #050510;
            color: white;
            font-family: 'Inter', sans-serif;
        }
        .hero {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #00ffcb, #00bfff);
            text-align: center;
        }
        .stats {
            margin-top: 2rem;
        }
        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 2rem;
            padding: 2rem;
        }
        .product-card {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(5px);
            transition: transform 0.3s ease-in-out;
        }
        .product-card:hover {
            transform: scale(1.05);
        }
        .product-title {
            font-size: 1.5em;
        }
        .product-price {
            font-weight: bold;
        }
    </style>
</head>
<body>
    <header class="hero">
        <div>
            <h1>EVA</h1>
            <p>Your Ultimate AI Companion</p>
            <div class="stats">
                <span>1M+</span>
                <span>Satisfied Users</span>
            </div>
        </div>
    </header>
    
    <main>
        <section class="product-grid">
            <article class="product-card">
                <h2 class="product-title">Security Scanner</h2>
                <p class="product-price">€299</p>
            </article>
            <article class="product-card">
                <h2 class="product-title">Trading Bot</h2>
                <p class="product-price">€199</p>
            </article>
            <article class="product-card">
                <h2 class="product-title">Maeve Content</h2>
                <p class="product-price">€149</p>
            </article>
            <article class="product-card">
                <h2 class="product-title">OSINT</h2>
                <p class="product-price">€499</p>
            </article>
            <article class="product-card">
                <h2 class="product-title">Code Audit</h2>
                <p class="product-price">€399</p>
            </article>
            <article class="product-card">
                <h2 class="product-title">Skills Pack</h2>
                <p class="product-price">€299</p>
            </article>
        </section>
    </main>
</body>
</html>
"""
@app.route("/")
def index():
    return HTML
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8093)
