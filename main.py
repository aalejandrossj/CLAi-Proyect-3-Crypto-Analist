from crewai import Agent, Crew, Task, LLM, Process
from langchain.tools import tool
from crewai.tools import BaseTool
from dotenv import load_dotenv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import math
import openai
from typing import Tuple, Any, List
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
from twikit import Client
from textblob import TextBlob

load_dotenv()


fecha_actual = datetime.now()  
fecha_formateada = fecha_actual.strftime("%d-%m-%Y")

llm = LLM(model="gpt-4o-mini")

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


class GetActualDataInput(BaseModel):
    """Input schema for GetActualData tool."""
    moneda: str = Field(..., description="The cryptocurrency name to fetch data for.")

class GetActualData(BaseTool):
    name: str = "Get Crypto Actual Data Tool"
    description: str = "Scrape actual price data for a cryptocurrency."
    args_schema = GetActualDataInput  

    def _run(self, moneda: str) -> dict:
        """
        Fetch the current price of a cryptocurrency from CoinMarketCap.
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




class GetHistoricDataInput(BaseModel):
    """Input schema for GetHistoricData tool."""
    moneda: str = Field(..., description="The cryptocurrency name.")
    fecha: str = Field(..., description="Date in format <format>Month DD, YYYY</format> Exactly like the example <example>Jan 23, 2025</example>")

class GetHistoricData(BaseTool):
    name: str = "Crypto Historical Data Tool"
    description: str = "Scrape Historical Data of the crypto."
    args_schema = GetHistoricDataInput  

    def _run(self, moneda: str, fecha: str) -> dict:
        """
        Fetch historical cryptocurrency data for a specific date.
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



class IndicatorsToolInput(BaseModel):
    """Input schema for GetHistoricData tool."""
    moneda: str = Field(..., description="The cryptocurrency name.")
    fecha: str = Field(..., description="Date in format <format>Month DD, YYYY</format>. Exactly like the example <example>Jan 23, 2025</example>.")
    Apertura: str = Field(..., description="The opening price of the cryptocurrency on the given date.")
    Alza: str = Field(..., description="The highest price reached by the cryptocurrency on the given date.")
    Baja: str = Field(..., description="The lowest price reached by the cryptocurrency on the given date.")
    MarketCap: str = Field(..., description="The market capitalization of the cryptocurrency on the given date.")

class IndicatorsTool(BaseTool):
    name: str = "Calculate Indicators Tool"
    description: str = "Calculate economic indicators of the crypto"
    args_schema = IndicatorsToolInput  

    def _run(self, moneda: str, fecha: str, Apertura: str, Alza: str, Baja: str, MarketCap: str) -> dict:
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

        def limpiar_valor(valor_str):
            return float(valor_str.replace('$', '').replace(',', ''))
        
        apertura = limpiar_valor(Apertura)
        alza = limpiar_valor(Alza)
        baja = limpiar_valor(Baja)
        marketcap = limpiar_valor(MarketCap)
        
        volatilidad = ((alza - baja) / apertura) * 100
        potencial_ganancia = ((alza - apertura) / apertura) * 100
        potencial_perdida = ((apertura - baja) / apertura) * 100
        ratio_riesgo_beneficio = (potencial_ganancia / potencial_perdida) if potencial_perdida != 0 else None
        indice_riesgo_simple = volatilidad / math.log(marketcap) if marketcap > 0 else None
        
        return {
            'moneda': moneda,
            'fecha': fecha,
            'volatilidad': volatilidad,
            'potencial_ganancia': potencial_ganancia,
            'potencial_perdida': potencial_perdida,
            'ratio_riesgo_beneficio': ratio_riesgo_beneficio,
            'indice_riesgo_simple': indice_riesgo_simple
        }


class CryptoSentimentToolInput(BaseModel):
    """Input schema for CryptoSentimentTool tool."""
    moneda: str = Field(..., description="The cryptocurrency name to fetch data for.")

    
class CryptoSentimentTool(BaseTool):
    name: str = "Crypto Sentiment Scraper"
    description: str = "Scrape content from X related with the crypto and calculates sentiment"
    args_schema = CryptoSentimentToolInput  

    def _run(self, moneda: str = "bitcoin") -> list:
        """
        Busca tweets relacionados con un término específico y calcula el sentimiento de cada tweet.
        
        Parámetros:
        moneda (str): Término de búsqueda para los tweets.
        
        Retorna:
        list: Lista de diccionarios con el usuario, la fecha, el contenido del tweet y la puntuación de sentimiento.
        """

        async def get_tweets():
            client = Client(language='en-US')
            client.load_cookies('cookies.json')  # Carga las cookies
            tweet_list = []
            tweet_count = 0
            tweets = await client.search_tweet(moneda, product='Top')
            for tweet in tweets:
                if tweet_count >= 20:
                    break
                tweet_count += 1
                tweet_list.append(tweet)
            return tweet_list

        tweets = asyncio.run(get_tweets())
        
        results = []
        for tweet in tweets:
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
  tools=[GetActualData(), GetHistoricData()]
)

analista_indicadores_financieros = Agent(
  config=agents_config['analista_indicadores_financieros'],
  llm=llm,
  tools=[IndicatorsTool()]
)

crypto_sentiment_analist = Agent(
  config=agents_config['crypto_sentiment_analist'],
  tools=[CryptoSentimentTool()],
  llm=llm
)

agent_predictor = Agent(
  config=agents_config['agent_predictor'],
  llm=llm
)

get_actual_data = Task(
  config=tasks_config['get_actual_data'],
  agent=agente_valores
)

get_historic_data = Task(
  config=tasks_config['get_historic_data'],
  agent=agente_valores
  )

indicators_tool = Task(
  config=tasks_config['indicators_tool'],
  agent=analista_indicadores_financieros,
)

get_crypto_sentiment = Task(
  config=tasks_config['get_crypto_sentiment'],
  agent=crypto_sentiment_analist,
)

predict_market_trend = Task(
  config=tasks_config['predict_market_trend'],
  agent=agent_predictor,
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


result = crew.kickoff(inputs={'prompt': "Cual es el precio de xrp actual de ayer, de hace una semana y de hace un mes, y comparamelo con el precio de solana en las mismas fechas, dime cual parece mejor inversion si quiero invertir a largo plazo", 'actual_date': fecha_formateada})