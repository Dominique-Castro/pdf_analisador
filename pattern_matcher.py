cat > processors/pattern_matcher.py << 'EOF'
"""
Módulo para identificação de padrões em documentos militares
"""

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
    }
    # Adicione outros padrões conforme necessário
]

def identificar_documentos(textos_paginas: list) -> dict:
    """
    Identifica documentos com base nos padrões definidos.
    
    Args:
        textos_paginas: Lista de tuplas (número_página, texto)
    
    Returns:
        Dicionário {tipo_documento: [páginas_encontradas]}
    """
    resultados = {}
    
    for doc in DOCUMENTOS_PADRAO:
        paginas = []
        for pagina, texto in textos_paginas:
            for padrao in doc["padroes_texto"]:
                if re.search(padrao, texto, re.IGNORECASE):
                    paginas.append(pagina)
                    break
        
        if paginas:
            resultados[doc["nome"]] = paginas
    
    return resultados

if __name__ == "__main__":
    # Teste local do módulo
    print("Módulo pattern_matcher criado com sucesso!")
EOF
