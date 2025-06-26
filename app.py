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
    # ... (mantido igual ao original)
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
            r'24/1203-0022758-4'  # Padrão específico para documentos BM/RS
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

# ========== FUNÇÕES AUXILIARES (MANTIDAS) ========== #
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

def preprocess_image(img):
    """Melhora a qualidade da imagem para OCR"""
    try:
        img_np = np.array(img)
        
        if len(img_np.shape) == 3:
            img_np = np.dot(img_np[...,:3], [0.2989, 0.5870, 0.1140])
        
        img_np = (img_np > 128).astype(np.uint8) * 255
        
        return Image.fromarray(img_np)
    except Exception as e:
        logger.error(f"Erro no pré-processamento: {str(e)}")
        return img

# ========== FUNÇÕES PRINCIPAIS (ATUALIZADAS) ========== #
@st.cache_data(show_spinner=False)
def processar_pdf(uploaded_file, modo_rapido: bool = False) -> Dict[str, any]:
    """Processa o PDF e extrai texto de cada página"""
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        dpi = 150 if modo_rapido else 200
        max_paginas = 5 if modo_rapido else None
        
        with st.spinner("Convertendo PDF para imagens..."):
            imagens = convert_from_bytes(
                file_bytes,
                dpi=dpi,
                fmt='jpeg',
                first_page=1,
                last_page=max_paginas,
                thread_count=2
            )
        
        resultados = {
            "textos_paginas": [],
            "imagens_paginas": [],
            "metadados": {},
            "total_paginas": len(imagens),
            "analise_acidente": None  # Novo campo para análise específica
        }
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, img in enumerate(imagens):
            progresso = int((i + 1) / len(imagens) * 100)
            progress_bar.progress(progresso)
            status_text.text(f"Processando página {i+1}/{len(imagens)}...")
            
            if not pagina_vazia(img):
                img_processed = preprocess_image(img)
                texto = pytesseract.image_to_string(
                    img_processed,
                    lang='por',
                    config=TESSERACT_CONFIG
                )
                
                resultados["textos_paginas"].append((i+1, texto))
                resultados["imagens_paginas"].append(img)
                
                if i == 0:
                    resultados["metadados"] = extrair_metadados(texto)
        
        # Realiza análise específica para acidentes
        analyzer = AcidenteAnalyzer(resultados["textos_paginas"])
        resultados["analise_acidente"] = analyzer.analyze()
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro durante a análise: {str(e)}")
        return None

def gerar_relatorio(resultados: Dict[str, any]) -> str:
    """Gera um relatório textual com os resultados da análise (ATUALIZADO)"""
    relatorio = []
    
    # Cabeçalho (mantido)
    relatorio.append("="*60)
    relatorio.append("BRIGADA MILITAR DO RIO GRANDE DO SUL")
    relatorio.append("SISTEMA DE ANÁLISE DOCUMENTAL - SEÇÃO DE AFASTAMENTOS E ACIDENTES")
    relatorio.append("="*60)
    
    # Metadados (com adição da análise de acidente)
    relatorio.append(f"\n📋 INFORMAÇÕES DO PROCESSO")
    relatorio.append("-"*60)
    relatorio.append(f"▪ Número do processo: {resultados['metadados'].get('numero_processo', 'Não identificado')}")
    relatorio.append(f"▪ Número do PROA: {resultados['analise_acidente'].get('numero_proa', 'Não identificado')}")
    relatorio.append(f"▪ Militar acidentado: {resultados['metadados'].get('militar_acidentado', 'Não identificado')}")
    relatorio.append(f"▪ Unidade: {resultados['metadados'].get('unidade', 'Não identificada')}")
    relatorio.append(f"▪ Data do acidente: {resultados['analise_acidente'].get('data_acidente', resultados['metadados'].get('data_acidente', 'Não identificada'))}")
    relatorio.append(f"▪ Data da abertura: {resultados['metadados'].get('data_abertura', 'Não identificada')}")
    relatorio.append(f"▪ Páginas analisadas: {resultados['paginas_processadas']}/{resultados['total_paginas']}")
    
    # Seção específica para análise de acidente
    if resultados['analise_acidente']:
        relatorio.append(f"\n🔍 ANÁLISE DE ACIDENTE")
        relatorio.append("-"*60)
        relatorio.append(f"▪ Data do acidente encontrada nas páginas: {', '.join(map(str, resultados['analise_acidente']['paginas_referencia']['data_acidente'])) or 'Não encontrada'}")
        relatorio.append(f"▪ Número do PROA encontrado nas páginas: {', '.join(map(str, resultados['analise_acidente']['paginas_referencia']['numero_proa'])) or 'Não encontrado'}")
    
    # ... (restante do relatório mantido igual)
    
    return "\n".join(relatorio)

# ========== INTERFACE STREAMLIT (ATUALIZADA) ========== #
def main():
    # CSS Personalizado (mantido igual)
    
    # Header institucional (mantido igual)
    
    # Sidebar (mantido igual)
    
    # Seção de upload de documento (mantido igual)
    
    if uploaded_file is not None:
        with st.spinner('Processando documento...'):
            processamento = processar_pdf(uploaded_file, modo_rapido)
            
            if processamento is not None:
                resultados = analisar_documentos(processamento)
                
                st.success("Análise concluída com sucesso!")
                
                # Nova aba para análise de acidente
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📋 Relatório", 
                    "✅ Documentos Encontrados", 
                    "❌ Documentos Faltantes",
                    "🔍 Análise de Acidente"
                ])
                
                # ... (abas originais mantidas)
                
                with tab4:
                    st.subheader("Informações Específicas do Acidente")
                    
                    if processamento["analise_acidente"]:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric(
                                "Data do Acidente", 
                                processamento["analise_acidente"]["data_acidente"] or "Não encontrada",
                                help=f"Páginas de referência: {', '.join(map(str, processamento['analise_acidente']['paginas_referencia']['data_acidente'])) or 'Nenhuma'}"
                            )
                        
                        with col2:
                            st.metric(
                                "Número do PROA", 
                                processamento["analise_acidente"]["numero_proa"] or "Não encontrado",
                                help=f"Páginas de referência: {', '.join(map(str, processamento['analise_acidente']['paginas_referencia']['numero_proa'])) or 'Nenhuma'}"
                            )
                        
                        st.json(processamento["analise_acidente"], expanded=False)
                    else:
                        st.warning("Nenhuma informação específica de acidente encontrada")

                # Visualização do documento (mantido igual)

if __name__ == "__main__":
    main()
