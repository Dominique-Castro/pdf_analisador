import re
import pytesseract
from pdf2image import convert_from_bytes
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging
from collections import defaultdict

# Configuração básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

## ========== MODELOS DE DOCUMENTOS ========== ##

DOCUMENTOS_PADRAO = [
    {
        "nome": "Portaria da Sindicância Especial",
        "artigo": "NI 1.26 Art. 5º",
        "padroes_texto": [
            r"PORTARIA\s+N[º°]\s*\d+/SINDASV/\d{4}",
            r"INSTAURAÇÃO\s+DE\s+SINDICÂNCIA\s+ESPECIAL",
            r"DO\s+CMT\s+DO\s+\d+°\s+BPM.*?SINDICÂNCIA\s+ESPECIAL"
        ],
        "palavras_chave": ["portaria", "sindicância", "especial", "instauração", "acidente de serviço"],
        "pagina_referencia": 3  # Página típica onde aparece
    },
    {
        "nome": "Parte de acidente",
        "artigo": "Decreto 32.280 Art. 12",
        "padroes_texto": [
            r"PARTE\s+N[º°]\s*\d+/P1/\d{4}",
            r"ACIDENTE\s+DE\s+SERVIÇO.*?TESTEMUNHOU\s+O\s+FATO",
            r"RELAT[ÓO]RIO\s+DE\s+OCORR[ÊE]NCIA\s+DE\s+ACIDENTE"
        ],
        "palavras_chave": ["parte", "acidente", "ocorrência", "relatório", "testemunhas"],
        "pagina_referencia": 6
    },
    {
        "nome": "Termo de Oitiva do Acidentado",
        "artigo": "RDBM Art. 78",
        "padroes_texto": [
            r"TERMO\s+DE\s+OITIVA\s+DO\s+ACIDENTADO",
            r"DECLARAÇÃO\s+DO\s+MILITAR\s+ACIDENTADO",
            r"OITIVA\s+DO\s+SERVIR\s+ACIDENTADO.*?RESPONDIDO"
        ],
        "palavras_chave": ["oitiva", "acidentado", "declaração", "depoimento", "militar"],
        "pagina_referencia": 18
    },
    {
        "nome": "Termo de Oitiva de Testemunhas",
        "artigo": "Decreto 32.280 Art. 18",
        "padroes_texto": [
            r"TERMO\s+DE\s+OITIVA\s+DE\s+TESTEMUNHAS",
            r"DECLARAÇÃO\s+DA\s+TESTEMUNHA",
            r"TESTEMUNHA\s+N[º°]\s*\d+.*?RESPONDIDO"
        ],
        "palavras_chave": ["oitiva", "testemunha", "declaração", "depoimento"],
        "pagina_referencia": 17
    },
    {
        "nome": "Atestado de Origem",
        "artigo": "NI 1.26 Anexo III",
        "padroes_texto": [
            r"ATESTADO\s+DE\s+ORIGEM",
            r"LAUDO\s+MÉDICO.*?ACIDENTE\s+DE\s+SERVIÇO",
            r"FSR.*?NECESSIDADE\s+DE\s+AO"
        ],
        "palavras_chave": ["atestado", "origem", "médico", "laudo", "FSR"],
        "pagina_referencia": None
    }
]

## ========== FUNÇÕES AUXILIARES ========== ##

def limpar_texto(texto: str) -> str:
    """Normaliza o texto para análise removendo caracteres especiais e espaços excessivos"""
    texto = re.sub(r'[^\w\sáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇº°-]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.upper()

def pagina_vazia(img, threshold: float = 0.95) -> bool:
    """Verifica se a página é predominantemente vazia"""
    try:
        if img.mode != 'L':
            img = img.convert('L')
        img_array = np.array(img)
        white_pixels = np.sum(img_array > 200)
        total_pixels = img_array.size
        return (white_pixels / total_pixels) > threshold
    except Exception as e:
        logger.error(f"Erro ao verificar página vazia: {str(e)}")
        return False

## ========== FUNÇÕES PRINCIPAIS ========== ##

def extrair_metadados(texto: str) -> Dict[str, any]:
    """Extrai metadados importantes do texto com padrões específicos da BM/RS"""
    metadados = {
        'numero_processo': None,
        'data_acidente': None,
        'militar_acidentado': None,
        'unidade': None
    }
    
    # Padrões melhorados para processos da BM/RS
    padroes_processo = [
        r"Processo\s+Administrativo\s+Eletrônico\s*[\n:]\s*(\d{2}/\d{4}-\d{7}-\d)",
        r"PROA\s*n[º°]\s*(\d{2}/\d{4}-\d{7}-\d)",
        r"Processo:\s*(\d{2}/\d{4}-\d{7}-\d)"
    ]
    
    # Padrões para militar acidentado
    padroes_militar = [
        r"Militar\s+Estadual\s+Sindicado:\s*(.+?),\s*Id\s*Func",
        r"acidente\s+do\s+(Sd|Cb|3ºSgt|2ºSgt|1ºSgt|SubTen|Asp|2ºTen|1ºTen|Cap|Maj|TenCel|Cel)\s+(.+?),\s*Id",
        r"SD\s+([A-ZÀ-Ú\s]+)\s+ID\s+FUNC"
    ]
    
    # Padrões para unidade
    padroes_unidade = [
        r"\d+°\s*BPM.*?(NOVO\s+HAMBURGO|PORTO\s+ALEGRE|CANOAS)",
        r"CRPO/[A-Z]+\s+-\s+(\d+°\s*BPM)",
        r"LOTAÇÃO:\s*(CRPO/[A-Z]+/\d+°\s*BPM)"
    ]
    
    # Padrões para data do acidente
    padroes_data = [
        r"DATA\s+DO\s+ACIDENTE:\s*(\d{2}/\d{2}/\d{4})",
        r"ACIDENTE\s+OCORRIDO\s+EM:\s*(\d{2}/\d{2}/\d{4})",
        r"FATO\s+OCORRIDO\s+EM\s+(\d{2}/\d{2}/\d{4})"
    ]
    
    # Extração dos dados
    texto_limpo = limpar_texto(texto)
    
    for padrao in padroes_processo:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['numero_processo'] = match.group(1)
            break
            
    for padrao in padroes_militar:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['militar_acidentado'] = match.group(0).title()
            break
            
    for padrao in padroes_unidade:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['unidade'] = match.group(0).title()
            break
            
    for padrao in padroes_data:
        match = re.search(padrao, texto_limpo)
        if match:
            try:
                metadados['data_acidente'] = datetime.strptime(match.group(1), "%d/%m/%Y").date()
            except ValueError:
                continue
            break
    
    return metadados

def identificar_documento(texto: str) -> Optional[Dict[str, str]]:
    """
    Identifica o tipo de documento com base em padrões e palavras-chave
    Retorna o documento identificado ou None se não encontrar
    """
    texto_limpo = limpar_texto(texto)
    
    for documento in DOCUMENTOS_PADRAO:
        # Verifica padrões de texto primeiro
        for padrao in documento["padroes_texto"]:
            if re.search(padrao, texto_limpo, re.IGNORECASE):
                return documento
                
        # Fallback para palavras-chave se não encontrar padrão
        palavras_encontradas = sum(
            1 for palavra in documento["palavras_chave"] 
            if palavra.upper() in texto_limpo
        )
        
        if palavras_encontradas / len(documento["palavras_chave"]) > 0.7:
            return documento
            
    return None

def analisar_documento(pdf_path: str, modo_rapido: bool = False) -> Dict[str, any]:
    """
    Processa o PDF e analisa seu conteúdo buscando documentos padrão
    Retorna um dicionário com:
    - metadados
    - documentos encontrados
    - documentos faltantes
    - páginas processadas
    """
    resultados = {
        "metadados": {},
        "documentos_encontrados": defaultdict(list),
        "documentos_faltantes": [doc["nome"] for doc in DOCUMENTOS_PADRAO],
        "paginas_processadas": 0
    }
    
    try:
        # Converter PDF para imagens
        imagens = convert_from_bytes(pdf_path, dpi=200 if not modo_rapido else 150)
        resultados["total_paginas"] = len(imagens)
        
        # Processar cada página
        for num_pagina, img in enumerate(imagens, start=1):
            if pagina_vazia(img):
                continue
                
            # Extrair texto com OCR
            texto = pytesseract.image_to_string(img, lang='por')
            resultados["paginas_processadas"] += 1
            
            # Na primeira página, extrair metadados
            if num_pagina == 1:
                resultados["metadados"] = extrair_metadados(texto)
            
            # Identificar documentos na página
            documento = identificar_documento(texto)
            if documento:
                resultados["documentos_encontrados"][documento["nome"]].append({
                    "pagina": num_pagina,
                    "artigo": documento["artigo"]
                })
                
                # Remove da lista de faltantes se ainda estiver lá
                if documento["nome"] in resultados["documentos_faltantes"]:
                    resultados["documentos_faltantes"].remove(documento["nome"])
    
    except Exception as e:
        logger.error(f"Erro durante análise do documento: {str(e)}")
        raise
    
    return resultados

def gerar_relatorio(resultados: Dict[str, any]) -> str:
    """Gera um relatório textual com os resultados da análise"""
    relatorio = []
    
    # Cabeçalho
    relatorio.append("="*50)
    relatorio.append("RELATÓRIO DE ANÁLISE DOCUMENTAL - BM/RS")
    relatorio.append("="*50)
    relatorio.append(f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    relatorio.append(f"Número do processo: {resultados['metadados'].get('numero_processo', 'Não identificado')}")
    relatorio.append(f"Militar acidentado: {resultados['metadados'].get('militar_acidentado', 'Não identificado')}")
    relatorio.append(f"Data do acidente: {resultados['metadados'].get('data_acidente', 'Não identificada')}")
    relatorio.append(f"Unidade: {resultados['metadados'].get('unidade', 'Não identificada')}")
    relatorio.append(f"Páginas analisadas: {resultados['paginas_processadas']}/{resultados.get('total_paginas', '?')}")
    relatorio.append("")
    
    # Documentos encontrados
    relatorio.append("DOCUMENTOS ENCONTRADOS:")
    relatorio.append("-"*50)
    if resultados["documentos_encontrados"]:
        for doc, info in resultados["documentos_encontrados"].items():
            paginas = ", ".join(str(item["pagina"]) for item in info)
            relatorio.append(f"✓ {doc} (Art. {info[0]['artigo']}) - Páginas: {paginas}")
    else:
        relatorio.append("Nenhum documento padrão identificado")
    relatorio.append("")
    
    # Documentos faltantes
    relatorio.append("DOCUMENTOS FALTANTES:")
    relatorio.append("-"*50)
    if resultados["documentos_faltantes"]:
        for doc in resultados["documentos_faltantes"]:
            artigo = next(d["artigo"] for d in DOCUMENTOS_PADRAO if d["nome"] == doc)
            relatorio.append(f"✗ {doc} (Art. {artigo})")
    else:
        relatorio.append("Todos os documentos padrão foram identificados")
    
    return "\n".join(relatorio)

## ========== EXEMPLO DE USO ========== ##
if __name__ == "__main__":
    # Exemplo de uso (substitua pelo seu código de upload)
    with open("Processo_Administrativo.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    print("Processando documento...")
    resultados = analisar_documento(pdf_bytes)
    
    print("\nResultados da análise:")
    print(gerar_relatorio(resultados))
