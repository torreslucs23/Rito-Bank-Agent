import csv
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class CreditService:
    def __init__(self):
        self.rules_path = Path("app/src/data/score_limit.csv")
        self.log_path = Path("app/src/data/increase_limits_request.csv")
        self.clients_path = Path("app/src/data/clients.csv")

    def process_limit_request(self, cpf: str, current_limit: float, requested_limit: float, score: int) -> dict:
        """
        Orquestra o processo de validação, decisão e log do aumento de limite.
        """
        try:
            if not self.rules_path.exists():
                return {"status": "erro", "message": "Erro interno: Tabela de regras de crédito não encontrada."}

            max_allowed = self._get_max_allowed_limit(score)

            if requested_limit <= max_allowed:
                status = "aprovado"
                msg = f"Parabéns! Seu aumento para R$ {requested_limit:.2f} foi aprovado."
            else:
                status = "rejeitado"
                msg = f"No momento, não conseguimos aprovar R$ {requested_limit:.2f} com base no seu perfil atual (Máx permitido: {max_allowed})."

            self._log_transaction(cpf, current_limit, requested_limit, status)

            return {
                "status": status,
                "message": msg,
                "max_allowed": max_allowed
            }

        except Exception as e:
            logger.error(f"Erro no serviço de crédito: {str(e)}")
            return {"status": "erro", "message": f"Erro técnico ao processar solicitação: {str(e)}"}

    def update_client_limit(self, cpf: str, new_limit: float) -> bool:
        """
        Atualiza o limite de crédito do cliente no arquivo clients.csv (Persistência).
        """
        try:
            if not self.clients_path.exists():
                logger.error("Arquivo clients.csv não encontrado.")
                return False

            df = pd.read_csv(self.clients_path, dtype={'cpf': str})
            cpf_clean = str(cpf).strip()
            df['cpf'] = df['cpf'].str.strip()
            
            if cpf_clean not in df['cpf'].values:
                logger.error(f"Cliente {cpf_clean} não encontrado para atualização.")
                return False
            
            df.loc[df['cpf'] == cpf_clean, 'credit_limit'] = float(new_limit)
            df.to_csv(self.clients_path, index=False)
            logger.info(f"Limite atualizado com sucesso para CPF {cpf_clean}: R$ {new_limit}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar clients.csv: {e}")
            return False
        
    def get_client_data(self, cpf: str) -> dict:
        """
        Busca os dados completos do cliente (Score, Limite, Nome) no CSV.
        Retorna um dicionário ou None se não encontrar.
        """
        try:
            if not self.clients_path.exists():
                logger.error("Arquivo clients.csv não encontrado.")
                return None

            df = pd.read_csv(self.clients_path, dtype={'cpf': str})

            cpf_clean = str(cpf).strip()
            df['cpf'] = df['cpf'].str.strip()
            client_row = df[df['cpf'] == cpf_clean]
            
            print(client_row)
            
            if client_row.empty:
                return None
            
            return client_row.to_dict(orient='records')[0]

        except Exception as e:
            logger.error(f"Erro ao buscar dados do cliente: {e}")
            return None

    def _get_max_allowed_limit(self, score: int) -> float:
        """Lê o CSV de regras e retorna o limite máximo para o score dado."""
        try:
            df_rules = pd.read_csv(self.rules_path)
            for _, row in df_rules.iterrows():
                if row['min_score'] <= score <= row['max_score']:
                    return float(row['max_limit'])
            return 0.0
        except Exception as e:
            logger.error(f"Erro ao ler tabela de score: {e}")
            raise e

    def _log_transaction(self, cpf: str, current: float, requested: float, status: str):
        """Grava a solicitação no arquivo de log CSV."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            file_exists = self.log_path.exists()
            
            with open(self.log_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["cpf_cliente", "data_hora_solicitacao", "limite_atual", "novo_limite_solicitado", "status_pedido"])
                
                writer.writerow([
                    cpf,
                    datetime.now().isoformat(),
                    current,
                    requested,
                    status
                ])
        except Exception as e:
            logger.error(f"Erro ao salvar log de solicitação: {e}")