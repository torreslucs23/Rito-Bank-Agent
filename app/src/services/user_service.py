from pathlib import Path
from app.src.core.app_state import app_state
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def authenticate_user(cpf: str, birth_date: str) -> dict:
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