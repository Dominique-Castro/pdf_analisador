class LegislacaoBMRS:
    """Classe que encapsula os normativos da BM/RS"""
    
    @staticmethod
    def documentos_obrigatorios(tipo_processo: str = "acidente"):
        """Retorna documentos por tipo de processo conforme NI 1.26 EMBM 23"""
        base = {
            "acidente": [
                ("Portaria da Sindicância Especial", "NI 1.26 Art. 5º"),
                ("Primeiro Boletim Médico", "Decreto 32.280 Art. 12"),
                # ... outros 15 itens
            ],
            "disciplinar": [
                ("Auto de Prisão em Flagrante", "RDBM Art. 89"),
                # ... outros itens
            ]
        }
        return base.get(tipo_processo, [])

    @staticmethod
    def prazos():
        return {
            "protocolo": 30,  # dias
            "recurso": 10,
            "prescricao": 365 * 2  # RDBM Art. 123
        }
