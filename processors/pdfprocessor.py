from pdf2image import convert_from_bytes
import pytesseract
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple
import re

# Configuração do Tesseract (ajuste conforme seu ambiente)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
TESSERACT_CONFIG = r'--oem 3 --psm 6 -l por+eng'

def process_page(img) -> str:
    """Processa uma página com OCR"""
    try:
        return pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
    except Exception as e:
        print(f"Erro OCR: {str(e)}")
        return ""

def limpar_texto(texto: str) -> str:
    """Sua função original de limpeza"""
    texto = re.sub(r'[^\w\sáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇº°-]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip().upper()

def process_pdf(pdf_bytes: bytes) -> Dict:
    """Processa o PDF e retorna resultados estruturados"""
    images = convert_from_bytes(pdf_bytes, dpi=300, thread_count=4)
    
    # Processamento paralelo das páginas
    with ThreadPoolExecutor() as executor:
        textos = list(executor.map(process_page, images))
    
    textos_limpos = [limpar_texto(t) for t in textos]
    textos_paginas = list(zip(range(1, len(textos_limpos)+1), textos_limpos))
    
    # Análise de Acidente (seu código original)
    data_acidente = None
    numero_proa = None
    paginas_referencia = []
    
    for pagina, texto in textos_paginas:
        # Padrões de data (seus regex originais)
        date_match = re.search(r'Data do (?:fato|acidente):?\s*(\d{2}/\d{2}/\d{4})', texto)
        if date_match:
            data_acidente = date_match.group(1)
            paginas_referencia.append(pagina)
        
        # Padrões PROA (seus regex originais)
        proa_match = re.search(r'PROA\s*[nº°]*\s*([\d./-]+)', texto)
        if proa_match:
            numero_proa = proa_match.group(1)
            paginas_referencia.append(pagina)
    
    # Identificação de documentos (sua lógica original)
    documentos = identificar_documentos(textos_paginas)
    
    return {
        'texto': "\n".join(textos_limpos),
        'data_acidente': data_acidente,
        'numero_proa': numero_proa,
        'paginas_referencia': list(set(paginas_referencia)),
        'documentos': [{'tipo': k, 'paginas': ", ".join(map(str, v))} for k, v in documentos.items()]
    }
