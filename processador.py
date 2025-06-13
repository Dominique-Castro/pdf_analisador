from datetime import timedelta
from core.legislacao import LegislacaoBMRS

class ProcessadorDocumentos:
    def __init__(self):
        self.legislacao = LegislacaoBMRS()
    
    def validar_prazos(self, data_acidente):
        prazo = self.legislacao.prazos()["protocolo"]
        if data_acidente < (datetime.now() - timedelta(days=prazo)).date():
            return False, f"Prazo excedido em {(datetime.now().date() - data_acidente).days - prazo} dias"
        return True, "Dentro do prazo"

    def verificar_conformidade(self, texto):
        # Implementação detalhada com regex para cada documento
        pass
