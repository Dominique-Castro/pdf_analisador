import streamlit as st
import os
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
from datetime import datetime
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import json

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Configurações do Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    TESSERACT_CONFIG = "--oem 3 --psm 6 -l por+eng"
except Exception as e:
    st.warning(f"Configuração do Tesseract não encontrada: {str(e)}")
    TESSERACT_CONFIG = ""

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== MODELOS DE DOCUMENTOS ========== #
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
        "pagina_referencia": 3
    },
    # ... (outros modelos de documentos)
]

# ========== NOVAS FUNÇÕES PARA ANÁLISE DE ACIDENTES ========== #
class AcidenteAnalyzer:
    def __init__(self, textos_paginas: List[Tuple[int, str]]):
        self.textos_paginas = textos_paginas
        self.resultados = {
            'data_acidente': None,
            'numero_proa': None,
            'paginas_referencia': {
                'data_acidente': [],
                'numero_proa': []
            }
        }
    
    def find_data_acidente(self):
        """Encontra a data do acidente no texto do PDF"""
        date_patterns = [
            r'Data do fato:\s*(\d{2}/\d{2}/\d{4})',
            r'ocorrido em\s*(\d{2}/\d{2}/\d{4})',
            r'Data do acidente:\s*(\d{2}/\d{2}/\d{4})',
            r'(\d{2}/\d{2}/\d{4}).*acidente'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group(1)
                    try:
                        datetime.strptime(date_str, '%d/%m/%Y')
                        self.resultados['data_acidente'] = date_str
                        self.resultados['paginas_referencia']['data_acidente'].append(page_num)
                        return
                    except ValueError:
                        continue

    def find_numero_proa(self):
        """Encontra o número do PROA no texto do PDF"""
        proa_patterns = [
            r'PROA\s*n[º°o]*\s*([\d./-]+)',
            r'Processo\s*Administrativo\s*Eletrônico\s*([\d./-]+)',
            r'PROA\s*([\d./-]+)',
            r'24/1203-0022758-4'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in proa_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    proa_num = match.group(1) if match.lastindex else match.group(0)
                    self.resultados['numero_proa'] = proa_num
                    self.resultados['paginas_referencia']['numero_proa'].append(page_num)
                    return

    def analyze(self):
        """Executa toda a análise do PDF"""
        self.find_data_acidente()
        self.find_numero_proa()
        return self.resultados

# ========== FUNÇÕES AUXILIARES ========== #
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

# ... (continuam as outras funções com a indentação correta)

def main():
    # ... (código da função main com indentação correta)

if __name__ == "__main__":
    main()
