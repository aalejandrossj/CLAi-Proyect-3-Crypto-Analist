from crewai import Agent, Crew, Task, LLM, Process
from langchain.tools import tool
from crewai.tools import tool
from dotenv import load_dotenv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import math
import asyncio
from datetime import datetime
from twikit import Client
from textblob import TextBlob
from textblob import TextBlob

load_dotenv()


llm = LLM(model="gpt-4o-mini")

fecha_actual = datetime.now()  
fecha_formateada = fecha_actual.strftime("%d-%m-%Y")

files = {
    'agents': 'config/agents.yaml',
    'tasks': 'config/tasks.yaml'
}

# Load configurations from YAML files
configs = {}
for config_type, file_path in files.items():
    with open(file_path, 'r', encoding='utf-8') as file:
        configs[config_type] = yaml.safe_load(file)

# Assign loaded configurations to specific variables
agents_config = configs['agents']
tasks_config = configs['tasks']


@tool
def get_actual_data(moneda: str) -> dict:
    """
    Obtiene el precio actual de una criptomoneda desde CoinMarketCap.
    
    Parámetros:
    moneda (str): El nombre de la criptomoneda en la URL de CoinMarketCap.

    Retorna:
    dict: Un diccionario con el precio o un mensaje de error.
    """
    class Scraper:
        def __init__(self, moneda: str):
            self.moneda = moneda
            self.url = f"https://coinmarketcap.com/es/currencies/{self.moneda}/"
            self.options = webdriver.ChromeOptions()
            self.options.add_argument("--headless")
        
        def run(self) -> str:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.options
            )
            driver.get(self.url)
            try:
                # Se busca el elemento que contiene el precio
                span = driver.find_element(By.CLASS_NAME, "sc-65e7f566-0.WXGwg.base-text")
                resultado = span.text
            except Exception as e:
                resultado = f"Error: {e}"
            driver.quit()
            return resultado

    resultado = Scraper(moneda).run()
    if resultado.startswith("Error:"):
        return {"error": resultado}
    return {"Precio": resultado}


@tool
def get_historic_data(moneda: str, fecha: str) -> dict:
    """
    Obtiene los datos históricos de una criptomoneda en una fecha específica desde CoinMarketCap.

    Parámetros:
    moneda (str): El nombre de la criptomoneda en la URL de CoinMarketCap.
    fecha (str): La fecha en formato MM DD, YYYY, <example>Jan 23, 2025</example> para obtener los datos históricos.

    Retorna:
    {resultado}: Un diccionario con los datos de apertura, alza, baja y capitalización de mercado, 
          o un mensaje de error si la fecha no está disponible.
    """
    class Scraper:
        def __init__(self, moneda: str, fecha: str):
            self.moneda = moneda
            self.fecha = fecha
            self.url = f"https://coinmarketcap.com/es/currencies/{self.moneda}/historical-data/"
            self.options = webdriver.ChromeOptions()
            self.options.add_argument("--headless")
        
        def run(self) -> dict:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.options
            )
            driver.get(self.url)
            wait = WebDriverWait(driver, 10)
            try:
                # Se localiza la fila que contiene la fecha indicada
                fila = wait.until(
                    EC.visibility_of_element_located(
                        (By.XPATH, f"//tbody/tr[td[normalize-space(text())='{self.fecha}']]")
                    )
                )
                columnas = fila.find_elements(By.TAG_NAME, "td")
                resultado = {
                    "Apertura": columnas[1].text,
                    "Alza": columnas[2].text,
                    "Baja": columnas[3].text,
                    "MarketCap": columnas[6].text
                }
            except Exception as e:
                resultado = {"error": str(e)}
            driver.quit()
            return resultado

    return Scraper(moneda, fecha).run()


@tool
def indicators_tool(moneda: str, fecha: str, Apertura: str, Alza: str, Baja: str, MarketCap: str):
    """
    Recibe los parámetros {{moneda}}, {{fecha}}, {{Apertura}}, {{Alza}}, {{Baja}}, {{MarketCap}} y calcula sus indicadores.
    
    Calcula y retorna un diccionario con:
      - volatilidad: ((Alza - Baja) / Apertura) * 100
      - potencial_ganancia: ((Alza - Apertura) / Apertura) * 100
      - potencial_perdida: ((Apertura - Baja) / Apertura) * 100
      - ratio_riesgo_beneficio: potencial_ganancia / potencial_perdida
      - indice_riesgo_simple: volatilidad / ln(MarketCap)

    Además, se incluyen los parámetros 'moneda' y 'fecha' en el resultado.
    """
    ...

    # Función auxiliar para limpiar el valor y convertirlo a float
    def limpiar_valor(valor_str):
        return float(valor_str.replace('$', '').replace(',', ''))
    
    # Convertir los valores recibidos a números
    apertura = limpiar_valor(Apertura)
    alza = limpiar_valor(Alza)
    baja = limpiar_valor(Baja)
    marketcap = limpiar_valor(MarketCap)
    
    # Calcular indicadores
    volatilidad = ((alza - baja) / apertura) * 100
    potencial_ganancia = ((alza - apertura) / apertura) * 100
    potencial_perdida = ((apertura - baja) / apertura) * 100
    ratio_riesgo_beneficio = (potencial_ganancia / potencial_perdida) if potencial_perdida != 0 else None
    indice_riesgo_simple = volatilidad / math.log(marketcap) if marketcap > 0 else None
    
    # Retornar los resultados junto con la moneda y la fecha
    return {
        'moneda': moneda,
        'fecha': fecha,
        'volatilidad': volatilidad,
        'potencial_ganancia': potencial_ganancia,
        'potencial_perdida': potencial_perdida,
        'ratio_riesgo_beneficio': ratio_riesgo_beneficio,
        'indice_riesgo_simple': indice_riesgo_simple
    }

@tool
def get_crypto_sentiment(query: str = "bitcoin", max_tweets: int = 20) -> list:
    """
    Busca tweets relacionados con un término específico y calcula el sentimiento de cada tweet.
    
    Parámetros:
    query (str): Término de búsqueda para los tweets.
    max_tweets (int): Número máximo de tweets a analizar.
    
    Retorna:
    list: Lista de diccionarios con el usuario, la fecha, el contenido del tweet y la puntuación de sentimiento.
    """

    async def get_tweets():
        client = Client(language='en-US')
        client.load_cookies('cookies.json')  # Carga las cookies
        tweet_list = []
        tweet_count = 0
        tweets = await client.search_tweet(query, product='Top')
        for tweet in tweets:
            if tweet_count >= max_tweets:
                break
            tweet_count += 1
            tweet_list.append(tweet)
        return tweet_list

    # Ejecutar la función asíncrona para obtener los tweets
    tweets = asyncio.run(get_tweets())
    
    results = []
    for tweet in tweets:
        # Usamos tweet.full_text si existe, de lo contrario tweet.text
        tweet_text = getattr(tweet, 'full_text', tweet.text)
        analysis = TextBlob(tweet_text)
        sentiment_score = analysis.sentiment.polarity

        results.append({
            "user": tweet.user.name,
            "tweet": tweet_text,
            "sentiment_score": sentiment_score
        })

    return results


agente_valores = Agent(
  config=agents_config['agente_valores'],
  llm=llm,
  tools=[get_actual_data, get_historic_data]
)

analista_indicadores_financieros = Agent(
  config=agents_config['analista_indicadores_financieros'],
  llm=llm,
  tools=[indicators_tool]
)

crypto_sentiment_analist = Agent(
  config=agents_config['crypto_sentiment_analist'],
  tools=[get_crypto_sentiment],
  llm=llm
)

agent_predictor = Agent(
  config=agents_config['agent_predictor'],
  llm=llm
)

get_actual_data = Task(
  config=tasks_config['get_actual_data'],
  agent=agente_valores,
)

get_historic_data = Task(
  config=tasks_config['get_historic_data'],
  agent=agente_valores,
)

indicators_tool = Task(
  config=tasks_config['indicators_tool'],
  agent=analista_indicadores_financieros,
  inputs={"actual_data": get_actual_data, "historic_data": get_historic_data},  
)

get_crypto_sentiment = Task(
  config=tasks_config['get_crypto_sentiment'],
  agent=crypto_sentiment_analist,
  inputs={"actual_data": get_actual_data},  
)

predict_market_trend = Task(
  config=tasks_config['predict_market_trend'],
  agent=agent_predictor,
  expected_output="Market trend prediction based on financial indicators and crypto sentiment"
)

crew = Crew(
  agents=[
    agente_valores,
    analista_indicadores_financieros,
    crypto_sentiment_analist,
    agent_predictor
  ],
  tasks=[
    get_actual_data,
    get_historic_data,
    indicators_tool,
    get_crypto_sentiment,
    predict_market_trend  
  ],
  process=Process.sequential,  
  verbose=True
)


result = crew.kickoff(inputs={'prompt': "datos de avalanche de ayer y anteayer", 'actual_date': fecha_formateada})