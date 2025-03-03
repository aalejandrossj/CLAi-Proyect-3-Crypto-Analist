import pandas as pd
from crewai import Agent, Crew, Task, LLM, Process
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
from datetime import datetime
import csv

archivo_csv = "portfolio_historical.csv"

load_dotenv()

llm = LLM(model="gpt-4o-mini")

files = {
    'agents_portfolio': 'config/agents_portfolio.yaml',
    'tasks_portfolio': 'config/tasks_portfolio.yaml'
}

# Load configurations from YAML files
configs = {}
for config_type, file_path in files.items():
    with open(file_path, 'r', encoding='utf-8') as file:
        configs[config_type] = yaml.safe_load(file)

agents_config = configs['agents_portfolio']
tasks_config = configs['tasks_portfolio']

class ObtenerUltimaTransaccionInput(BaseModel):
    """Input schema for GetActualData tool."""
    archivo_csv: str = Field(..., description="The portfolio historical.")

class ObtenerUltimaTransaccion(BaseTool):
    name: str = "Get Last Transaction"
    description: str = "Obtains the last transaction of the portfolio"
    args_schema = ObtenerUltimaTransaccionInput  

    def _run(self, archivo_csv: str) -> dict:
        try:
            # Leer el archivo CSV
            df = pd.read_csv(archivo_csv)
            
            # Obtener la última fila
            ultima_fila = df.iloc[-1]
            return ultima_fila
        except Exception as e:
            print(f"Error al leer el archivo: {e}")
            return None



class GetActualDataInput(BaseModel):
    """Input schema for GetActualData tool."""
    moneda: str = Field(..., description="The cryptocurrency name to fetch data for. This parameter must always be in lowercase and must not be abbreviated.")

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
                self.moneda = moneda.lower()
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


class UpdatePortfolioInput(BaseModel):
    """ Input schema for the tool that updates the static portfolio (CSV).
    inversion_inicial: Value of the initial investment (already previously declared).
    moneda: Name of the cryptocurrency to be updated.
    precio_actualizado: Current price of the cryptocurrency.
    cantidad_moneda: Total amount of the cryptocurrency that is owned.
    """
    inversion_inicial: float = Field(..., description="Value of the initial investment.") 
    moneda: str = Field(..., description="Name of the cryptocurrency to be updated. This parameter must always be in lowercase and must not be abbreviated.") 
    precio_actualizado: float = Field(..., description="Current price of the cryptocurrency.") 
    cantidad_moneda: float = Field(..., description="Total amount of the cryptocurrency that is owned.")
    operacion: str = Field(..., description="The operation, BUY SELL or UPDATE")

class UpdatePortfolio(BaseTool):
    name: str = "Update Portfolio"
    description: str = (
        "Updates the CSV (static portfolio) by adding a row with the 'UPDATE' operation, "
        "after calculating the current value and the profit/loss in relation to the initial investment."
    )
    args_schema = UpdatePortfolioInput

    def _run(
        self,
        inversion_inicial: float,
        moneda: str,
        precio_actualizado: float,
        cantidad_moneda: float,
        operacion: str,
    ) -> str:
        patrimonio = precio_actualizado * cantidad_moneda

        # Get current date and time for the 'fecha' column
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        # Prepare the row data
        data = {
            "fecha": fecha_actual,
            "moneda": moneda,
            "patrimonio": f"{patrimonio:.2f}",
            "precio": f"{precio_actualizado:.2f}",
            "cantidad": f"{cantidad_moneda:.4f}",
            "operacion": operacion,
        }

        csv_updater = CsvPortfolioUpdater()
        result = csv_updater.update(data)

        return result
    

class CsvPortfolioUpdater:
    """
    Clase encargada de actualizar el archivo CSV del portfolio.

    Se encarga de:
    - Verificar si el archivo CSV existe y, si no, crearlo y escribir la cabecera.
    - Agregar una nueva fila al CSV con los datos proporcionados.
    """
    def __init__(self, archivo_csv="portfolio_historical.csv"):
        self.archivo_csv = archivo_csv
        self.fieldnames = ["fecha", "moneda", "patrimonio", "precio", "cantidad", "operacion"]

    def update(self, data: dict) -> dict:
        # Verificar si el archivo existe; si no, crear y escribir la cabecera
        try:
            with open(self.archivo_csv, "r", newline="") as csvfile:
                # Si se abre correctamente, se asume que la cabecera ya está escrita
                pass
        except FileNotFoundError:
            with open(self.archivo_csv, "w", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()

        # Agregar la nueva fila al archivo CSV
        with open(self.archivo_csv, "a", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writerow(data)

        return data
    
class AddTransactionInput(BaseModel):
    """ Input schema for the tool that updates the static portfolio (CSV).
    inversion_inicial: Value of the initial investment (already previously declared).
    moneda: Name of the cryptocurrency to be updated.
    precio_actualizado: Current price of the cryptocurrency.
    cantidad_moneda: Total amount of the cryptocurrency that is owned.
    operacion: Buy, sell or HOLD
    """
    patrimonio_actualizado: float = Field(..., description="Current currency equity value") 
    moneda: str = Field(..., description="Name of the cryptocurrency to be updated. This parameter must always be in lowercase and must not be abbreviated.") 
    precio_actualizado: float = Field(..., description="Current price of the cryptocurrency.") 
    cantidad_moneda: float = Field(..., description="Total amount of the cryptocurrency that is owned.")
    operacion: str = Field(..., description="The operation, BUY SELL or UPDATE")

class AddTransaction(BaseTool):
    name: str = "Update Portfolio"
    description: str = (
        "Updates the CSV (static portfolio) by adding a row with the 'UPDATE' operation, "
        "after calculating the current value and the profit/loss in relation to the initial investment."
    )
    args_schema = AddTransactionInput

    def _run(
        self,
        moneda: str,
        precio_actualizado: float,
        patrimonio_actualizado: float,
        cantidad_moneda: float,
        operacion: str,
    ) -> str:

        # Get current date and time for the 'fecha' column
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        # Prepare the row data
        data = {
            "fecha": fecha_actual,
            "moneda": moneda,
            "patrimonio": f"{patrimonio_actualizado:.2f}",
            "precio": f"{precio_actualizado:.2f}",
            "cantidad": f"{cantidad_moneda:.4f}",
            "operacion": operacion,
        }

        csv_updater = CsvPortfolioUpdater()
        result = csv_updater.update(data)

        return result

agente_datos = Agent(
  config=agents_config['agente_datos'],
  llm=llm,
  tools=[GetActualData(), ObtenerUltimaTransaccion()]
)

agente_updater = Agent(
  config=agents_config['agente_updater'],
  llm=llm,
  tools=[UpdatePortfolio()]
)

agent_operator = Agent(
  config=agents_config['agent_operator'],
  llm=llm,
  tools=[AddTransaction()]
)


obtain_transaction_and_actual_value = Task(
  config=tasks_config['obtain_transaction_and_actual_value'],
  agent=agente_datos
)

update_portfolio = Task(
  config=tasks_config['update_portfolio'],
  agent=agente_updater
)

compare_and_operate = Task(
  config=tasks_config['compare_and_operate'],
  agent=agent_operator
)

portfolio_crew = Crew(
  agents=[
    agente_datos,
    agente_updater,
    agent_operator
  ],
  tasks=[
    obtain_transaction_and_actual_value,
    update_portfolio,
    compare_and_operate
  ],
  process=Process.sequential,  
  verbose=True
)