#!/usr/bin/env python3
from flask import Flask
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVA - Premium Products</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #00b4db, #0083a6);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            width: 100%;
            padding: 20px;
        }
        h1 {
            text-align: center;
            font-size: 4em;
            margin-bottom: 30px;
        }
        .product-card {
            background-color: rgba(5, 5, 16, 0.7);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(5px);
            transition: transform 0.2s ease-in-out;
            margin: 15px 0;
        }
        .product-card:hover {
            transform: scale(1.05);
        }
        .product-card img {
            width: 100%;
            height: auto;
        }
        .product-info {
            padding: 15px;
        }
        .product-title {
            font-size: 1.5em;
            margin: 0;
        }
        .product-price {
            font-size: 1.2em;
            margin-top: 5px;
        }
        .stats {
            text-align: center;
            margin-top: 30px;
        }
        @media (min-width: 768px) {
            .product-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>EVA Premium Products</h1>
        <div class="product-grid">
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=Security+Scanner" alt="Security Scanner">
                <div class="product-info">
                    <h2 class="product-title">Security Scanner</h2>
                    <p class="product-price">299€</p>
                </div>
            </div>
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=Trading+Bot" alt="Trading Bot">
                <div class="product-info">
                    <h2 class="product-title">Trading Bot</h2>
                    <p class="product-price">199€</p>
                </div>
            </div>
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=Maeve+Content" alt="Maeve Content">
                <div class="product-info">
                    <h2 class="product-title">Maeve Content</h2>
                    <p class="product-price">149€</p>
                </div>
            </div>
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=OSINT" alt="OSINT">
                <div class="product-info">
                    <h2 class="product-title">OSINT</h2>
                    <p class="product-price">499€</p>
                </div>
            </div>
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=Code+Audit" alt="Code Audit">
                <div class="product-info">
                    <h2 class="product-title">Code Audit</h2>
                    <p class="product-price">399€</p>
                </div>
            </div>
            <div class="product-card">
                <img src="https://via.placeholder.com/500x300?text=Skills+Pack" alt="Skills Pack">
                <div class="product-info">
                    <h2 class="product-title">Skills Pack</h2>
                    <p class="product-price">299€</p>
                </div>
            </div>
        </div>
        <div class="stats">
            <p>19 agents | 1127 skills | 120+ tools</p>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8093)
