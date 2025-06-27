from typing import List, Dict, Tuple
import re

DOCUMENTOS_PADRAO = [
    {
        "nome": "Portaria da Sindicância Especial",
        "artigo": "NI 1.26 Art. 5º",
        "padroes_texto": [
            r"PORTARIA\s+N[º°]\s*\d+/SINDASV/\d{4}",
            r"INSTAURAÇÃO\s+DE\s+SINDICÂNCIA\s+ESPECIAL",
            r"DO\s+CMT\s+DO\s+\d+°\s+BPM.*?SINDICÂNCIA\s+ESPECIAL"
        ],
        "palavras_chave": ["portaria", "sindicância", "especial", "instauração"],
        "pagina_referencia": 3
    },
    # Adicione seus outros padrões aqui...
]

def identificar_documentos(textos_paginas: List[Tuple[int, str]]) -> Dict[str, List[int]]:
    """Sua função original de identificação de documentos"""
    resultados = {}
    
    for doc in DOCUMENTOS_PADRAO:
        paginas = []
        for pagina, texto in textos_paginas:
            for padrao in doc["padroes_texto"]:
                if re.search(padrao, texto):
                    paginas.append(pagina)
                    break
        
        if paginas:
            resultados[doc["nome"]] = paginas
    
    return resultados
