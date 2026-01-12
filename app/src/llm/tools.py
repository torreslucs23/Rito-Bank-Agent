import logging
import re
import time
from datetime import datetime
from typing import Literal
from zipfile import Path

import pandas as pd
import requests
from langchain_core.tools import tool

from app.src.services.credit_service import CreditService

credit_service = CreditService()

logger = logging.getLogger(__name__)


@tool
def get_score_and_or_limit(cpf: str) -> dict:
    """
    Retrieves the customer's score and current credit limit based on their CPF.

    Args:
        cpf: Customer's CPF (numbers only, 11 digits)
    Returns:
        Dict with score (int) and credit_limit (float)
    """
    try:
        data = credit_service.get_client_data(cpf)
        return {
            "message": f"Score e limite recuperados para o CPF {cpf}.",
            "score": data["score"],
            "credit_limit": data["credit_limit"],
        }
    except Exception as e:
        logger.error(f"Error retrieving score and limit for CPF {cpf}: {e}")
        return {
            "message": f"Erro ao recuperar dados para o CPF {cpf}",
            "score": None,
            "credit_limit": None,
        }


@tool
def process_limit_increase_request(
    cpf: str, current_limit: float, requested_limit: float, score: int
) -> dict:
    """
    Processes a credit limit increase request based on the customer's score.

    Args:
        cpf: Customer's CPF.
        current_limit: Customer's current limit (float).
        requested_limit: Desired new limit (float).
        score: Customer's current credit score (int).

    Returns:
        Dict with status ('aprovado' or 'rejeitado'), explanatory message and update flags.
    """
    logger.info(f"Tool chamada: process_limit_increase_request para CPF {cpf}")

    result = credit_service.process_limit_request(
        cpf, current_limit, requested_limit, score
    )

    if result["status"] == "aprovado":
        update_success = credit_service.update_client_limit(cpf, requested_limit)

        if update_success:
            result["message"] += " (Limite atualizado no sistema com sucesso!)"
            result["limit_updated"] = True
            result["new_limit"] = requested_limit
        else:
            result["message"] += (
                " (Aprovado, mas houve erro téQUEOR QUE MEU credito vá para 1000000000cnico ao salvar no banco de dados)."
            )
            result["limit_updated"] = False
    elif result["status"] == "rejeitado":
        result["message"] += "limite foi rejeitado."
        result["limit_updated"] = False

    return result


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
    cpf_clean = "".join(filter(str.isdigit, cpf))
    if len(cpf_clean) != 11:
        return {
            "success": False,
            "cpf": None,
            "message": "CPF inválido. Deve conter 11 dígitos",
        }

    return {
        "success": True,
        "cpf": cpf_clean,
        "message": f"CPF {cpf_clean} salvo com sucesso",
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
    patterns = [r"(\d{2})[/-](\d{2})[/-](\d{4})", r"(\d{2})(\d{2})(\d{4})"]

    for pattern in patterns:
        match = re.search(pattern, birth_date)
        if match:
            day, month, year = match.groups()

            try:
                date_obj = datetime(int(year), int(month), int(day))
                formatted_date = date_obj.strftime("%Y-%m-%d")

                return {
                    "success": True,
                    "birth_date": formatted_date,
                    "message": f"Data de nascimento {day}/{month}/{year} salva com sucesso",
                }
            except ValueError:
                return {
                    "success": False,
                    "birth_date": None,
                    "message": "Data inválida",
                }
    return {
        "success": True,
        "birth_date": birth_date,
        "message": f"Data de nascimento {birth_date} salva com sucesso",
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
    logger.debug(
        f"Authenticate customer called with CPF: {cpf} and Birth Date: {birth_date}"
    )
    try:
        csv_path = Path("app/src/data/clients.csv")
        if not csv_path.exists():
            return {"authenticated": False, "message": "Base de dados não encontrada"}

        cpf_clean = "".join(filter(str.isdigit, cpf))
        if len(cpf_clean) != 11:
            return {
                "authenticated": False,
                "message": "CPF inválido. Deve conter 11 dígitos",
            }

        df = pd.read_csv(csv_path, dtype={"cpf": str})
        df["cpf"] = df["cpf"].astype(str).str.strip()
        df["birth_date"] = df["birth_date"].astype(str).str.strip()

        match = df[(df["cpf"] == cpf_clean) & (df["birth_date"] == birth_date)]

        if not match.empty:
            return {
                "authenticated": True,
                "cpf": cpf_clean,
                "message": "Cliente autenticado com sucesso",
            }
        else:
            cpf_exists = df[df["cpf"] == cpf_clean]
            if not cpf_exists.empty:
                return {
                    "authenticated": False,
                    "message": "Data de nascimento não confere",
                }
            else:
                return {"authenticated": False, "message": "CPF não encontrado"}

    except Exception as e:
        return {"authenticated": False, "message": f"Erro ao autenticar: {str(e)}"}


@tool
def submit_credit_interview(
    cpf: str,
    renda_mensal: float,
    tipo_emprego: Literal["formal", "autonomo", "desempregado"],
    despesas_fixas: float,
    num_dependentes: int,
    tem_dividas_ativas: bool,
) -> dict:
    """
    Submits financial interview data to recalculate the customer's score.
    Should ONLY be called when ALL information has been collected.

    Args:
        cpf: Customer's CPF (already available in context).
        renda_mensal: Numeric value of monthly income.
        tipo_emprego: Employment type ('formal', 'autonomo' or 'desempregado').
        despesas_fixas: Numeric value of monthly expenses.
        num_dependentes: Integer number of dependents.
        tem_dividas_ativas: True if has overdue debts, False otherwise.
    """
    logger.info(f"Submetendo entrevista para CPF {cpf}")
    print(
        f"Data is: renda={renda_mensal}, emprego={tipo_emprego}, despesas={despesas_fixas}, dependentes={num_dependentes}, dividas_ativas={tem_dividas_ativas}"
    )

    result = credit_service.calculate_and_update_score(
        cpf,
        renda_mensal,
        tipo_emprego,
        despesas_fixas,
        num_dependentes,
        tem_dividas_ativas,
    )

    if result.get("success"):
        return {
            "status": "completed",
            "new_score": result["new_score"],
            "message": "Entrevista processada com sucesso. O score foi atualizado.",
        }
    else:
        return {
            "status": "error",
            "message": "Houve um erro técnico ao salvar seu novo score.",
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
        print("tool exchange: " + coin_code)
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
        valor = info["bid"]
        return f"{clean_code} custa R$ {valor} (BRL)."

    except Exception as e:
        return f"Erro técnico: {str(e)}"
