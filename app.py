import streamlit as st
import os
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
from docx import Document
import io
from datetime import datetime
import base64
import logging
import re
import hashlib

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Verificação do OpenCV (mantido discreto)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Configurações originais do Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TESSERACT_CONFIG = "--oem 1 --psm 6 -c tessedit_do_invert=0"

# ========== LISTA DE REQUISITOS (ORIGINAL) ========== #
REQUISITOS = [
    ("Portaria da Sindicância Especial", "NI 1.26 Art. 5º"),
    ("Parte de acidente", "Decreto 32.280 Art. 12"),
    # ... (todos os outros itens originais)
]

# ========== CSS ORIGINAL ========== #
st.markdown("""
<style>
    :root {
        --verde-bm: #006341;
        --dourado: #D4AF37;
    }
    .stButton>button {
        background-color: var(--verde-bm);
        color: white;
    }
    .badge-legal {
        background-color: var(--dourado);
        color: #333;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    .container-bordered {
        border: 2px solid #006341;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #FFFFFF;
    }
    .stSpinner > div > div {
        border-top-color: var(--verde-bm) !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== FUNÇÕES ORIGINAIS COM CORREÇÕES ========== #
def pagina_vazia(img, threshold=0.95):
    img_np = np.array(img.convert('L'))
    white_pixels = np.sum(img_np > 200)
    total_pixels = img_np.size
    return (white_pixels / total_pixels) > threshold

def preprocess_image(img):
    """Versão original com fallback para OpenCV"""
    img_np = np.array(img)
    
    if CV2_AVAILABLE:
        if len(img_np.shape) == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        img_np = cv2.adaptiveThreshold(
            img_np, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2)
    else:
        if len(img_np.shape) == 3:
            img_np = np.dot(img_np[...,:3], [0.2989, 0.5870, 0.1140])
        img_np = (img_np > 128).astype(np.uint8) * 255
    
    return Image.fromarray(img_np)

# ... (mantenha todas as outras funções originais como extrair_numero_processo, extrair_data_acidente)

@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def processar_pdf(uploaded_file, _hash, modo_rapido=False):
    """Versão original com correção do cache"""
    try:
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 10
        
        file_bytes = uploaded_file.read()
        imagens = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            fmt='jpeg',
            grayscale=True,
            first_page=1,
            last_page=max_paginas
        )
        
        # ... (restante do processamento original)
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        return None, None, None

def mostrar_pdf_corrigido(uploaded_file):
    """Versão corrigida da visualização do PDF"""
    try:
        # Cria uma cópia em memória antes do processamento
        pdf_bytes = uploaded_file.getvalue()
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>',
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Erro ao exibir PDF: {str(e)}")

# ========== INTERFACE ORIGINAL ========== #
def main():
    # Header institucional (idêntico ao original)
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Seção de informações do processo (original)
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📋 Informações do Processo")
        col1, col2 = st.columns(2)
        with col1:
            numero_processo = st.text_input(
                "Número do Processo:",
                placeholder="Ex: 2023.1234.5678-9",
                key="numero_processo_input"
            )
        with col2:
            data_acidente = st.date_input(
                "Data do Acidente:",
                format="DD/MM/YYYY",
                key="data_acidente_input"
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # Seção de upload (original)
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📂 Documento para Análise")
        modo_rapido = st.toggle(
            "Modo rápido (análise parcial)", 
            value=True,
            key="modo_rapido_toggle"
        )
        
        uploaded_file = st.file_uploader(
            "Carregue o arquivo PDF do processo", 
            type=["pdf"],
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Processamento (com correção)
    if uploaded_file:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        encontrados, nao_encontrados, texto_completo = processar_pdf(
            uploaded_file, file_hash, modo_rapido
        )

        if encontrados is not None:
            # ... (mantenha todo o resto da lógica original de exibição)
            
            # Substitua apenas a visualização do PDF pela versão corrigida:
            with st.expander("📄 Visualizar Documento", expanded=False):
                mostrar_pdf_corrigido(uploaded_file)

    # Sidebar original (sem alterações)
    with st.sidebar:
        st.image("https://i.imgur.com/By8hwnl.jpeg", use_column_width=True)
        st.markdown("""
        ### 🔍 Normativos de Referência
        - Decreto nº 32.280/1986
        - NI EMBM 1.26/2023
        - Regulamento Disciplinar (RDBM)
        """)
        st.markdown("---")
        st.markdown(f"""
        ### 📌 Responsável Técnico
        **SD PM Dominique Castro**  
        Seção de Afastamentos e Acidentes  
        *Versão 3.2 - {datetime.now().year}*
        """)

if __name__ == "__main__":
    main()
