from crewai import LLM
from dotenv import load_dotenv
import openai
from selenium.webdriver.support import expected_conditions as EC
from crypto_analisis import crypto_analisis_crew
from portfolio import portfolio_crew
from datetime import datetime
import random

load_dotenv()

# Get formatted date
fecha_actual = datetime.now()  
fecha_formateada = fecha_actual.strftime("%b %d, %Y")

archivo_csv = "portfolio_historical.csv"

# Initialize LLM
llm = LLM(model="gpt-4o-mini")
cryptos = {
    1: "bitcoin",
    2: "ethereum",
    3: "crp",
    4: "bnb",
    5: "solana",
    6: "cardano",
    7: "dogecoin",
    8: "tron",
    9: "avalanche",
    10: "toncoin"
}
crypto = random.choice(list(cryptos.values()))

# Get instances of your crews
crypto_analisis_crew = crypto_analisis_crew
portfolio_crew = portfolio_crew
prompt = f"Cual es el precio de {crypto} de hoy, de hace dos días, de hace una semana, hace 2 y hace un mes"

# Check if the prompt is about crypto
client = openai.Client()
respuesta = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Detecta si el siguiente prompt trata sobre criptomonedas. Responde con 'sí' o 'no'."},
        {"role": "user", "content": prompt}
    ]
)

# Diccionario de criptomonedas listadas en CoinMarketCap

crypto = random.choice(list(cryptos.values()))

# Main workflow
if "sí" in respuesta.choices[0].message.content.lower():
    # Run the first crew and get results
    crypto_result = crypto_analisis_crew.kickoff(inputs={'prompt': prompt, 'actual_date': fecha_formateada})
    
    crypto_result_str = str(crypto_result)
    
    portfolio_result = portfolio_crew.kickoff(inputs={
        'archivo_csv': archivo_csv, 
        'crypto_analysis': crypto_result_str
    })

    print(portfolio_result)
else:
    print("The prompt is not about cryptocurrencies. No crews were executed.")