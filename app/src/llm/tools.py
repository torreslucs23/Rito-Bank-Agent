from zipfile import Path
import requests
from langchain_core.tools import tool
import re
from datetime import datetime
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)


@tool
def save_cpf(cpf: str) -> dict:
    """
    Saves the CPF provided by the customer.
    
    Args:
        cpf: Customer's CPF (numbers only, 11 digits)
    
    Returns:
        Confirmation of the save operation
    """
    logger.debug(f"Save CPF called with CPF: {cpf}")
    cpf_clean = ''.join(filter(str.isdigit, cpf))
    if len(cpf_clean) != 11:
        return {
            "success": False,
            "cpf": None,
            "message": "CPF inválido. Deve conter 11 dígitos"
        }
    
    return {
        "success": True,
        "cpf": cpf_clean,
        "message": f"CPF {cpf_clean} salvo com sucesso"
    }
  
@tool  
def save_birth_date(birth_date: str) -> dict:
    """
    Saves the birth date provided by the customer.
    
    Args:
        birth_date: Customer's birth date (format DD/MM/YYYY)
    
    Returns:
        Confirmation of the save operation
    """
    logger.debug(f"Save Birth Date called with Birth Date: {birth_date}")
    patterns = [
        r'(\d{2})[/-](\d{2})[/-](\d{4})', 
        r'(\d{2})(\d{2})(\d{4})'           
    ]
    
    for pattern in patterns:
        match = re.search(pattern, birth_date)
        if match:
            day, month, year = match.groups()
            
            try:
                date_obj = datetime(int(year), int(month), int(day))
                formatted_date = date_obj.strftime('%Y-%m-%d')
                
                return {
                    "success": True,
                    "birth_date": formatted_date,
                    "message": f"Data de nascimento {day}/{month}/{year} salva com sucesso"
                }
            except ValueError:
                return {
                    "success": False,
                    "birth_date": None,
                    "message": "Data inválida"
                }
    return {
        "success": True,
        "birth_date": birth_date,
        "message": f"Data de nascimento {birth_date} salva com sucesso"
    }
    

@tool
def authenticate_customer(cpf: str, birth_date: str) -> dict:
    """
    Authenticates the customer by validating CPF and birth date against the clients CSV.
    
    Args:
        cpf: Customer's CPF (11 digits, numbers only)
        birth_date: Birth date in YYYY-MM-DD format
    
    Returns:
        Dict with authentication status (True/False)
    """
    logger.debug(f"Authenticate customer called with CPF: {cpf} and Birth Date: {birth_date}")
    try:
        csv_path = Path("app/src/data/clients.csv")
        if not csv_path.exists():
            return {
                "authenticated": False,
                "message": "Base de dados não encontrada"
            }
        
        cpf_clean = ''.join(filter(str.isdigit, cpf))
        if len(cpf_clean) != 11:
            return {
                "authenticated": False,
                "message": "CPF inválido. Deve conter 11 dígitos"
            }
        
        df = pd.read_csv(csv_path, dtype={'cpf': str})
        df['cpf'] = df['cpf'].astype(str).str.strip()
        df['birth_date'] = df['birth_date'].astype(str).str.strip()
        
        match = df[(df['cpf'] == cpf_clean) & (df['birth_date'] == birth_date)]
        
        if not match.empty:
            return {
                "authenticated": True,
                "cpf": cpf_clean,
                "message": "Cliente autenticado com sucesso"
            }
        else:
            cpf_exists = df[df['cpf'] == cpf_clean]
            if not cpf_exists.empty:
                return {
                    "authenticated": False,
                    "message": "Data de nascimento não confere"
                }
            else:
                return {
                    "authenticated": False,
                    "message": "CPF não encontrado"
                }
        
    except Exception as e:
        return {
            "authenticated": False,
            "message": f"Erro ao autenticar: {str(e)}"
        }
        
@tool
def get_exchange_rate_tool(coin_code: str) -> str:
    """
    Queries the exchange rate of a currency against the Brazilian Real (BRL).
    Use this tool to fetch currency values like USD, EUR, BTC, etc.
    
    Args:
        coin_code: Currency code (e.g., 'USD', 'EUR', 'BTC'). 
                   Does NOT accept pairs like 'USDEUR'. Only the source currency code.
    Returns:
        String containing the purchase value (bid) and quote date.
    """
    try:
        print('tool exchange: ' + coin_code)
        time.sleep(3)
        clean_code = coin_code.replace("-BRL", "").strip().upper()
        
        url = f"https://economia.awesomeapi.com.br/last/{clean_code}-BRL"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return f"Erro: Não consegui cotação para {clean_code}."
        
        data = response.json()
        key = f"{clean_code}BRL"
        
        if key not in data:
            return f"Erro: Moeda {clean_code} não encontrada na API."
            
        info = data[key]
        valor = info['bid']
        return f"{clean_code} custa R$ {valor} (BRL)."

    except Exception as e:
        return f"Erro técnico: {str(e)}"