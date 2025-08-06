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
from concurrent.futures import ThreadPoolExecutor
import hashlib

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Configuração simplificada do Tesseract (ajuste conforme seu sistema)
try:
    pytesseract.pytesseract.tesseract_cmd = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
    TESSERACT_CONFIG = "--oem 1 --psm 6"
except Exception as e:
    st.warning(f"Configuração do Tesseract: {str(e)}")
    TESSERACT_CONFIG = ""

# ========== LISTA DE REQUISITOS ========== #
REQUISITOS = [
    ("Portaria da Sindicância Especial", "NI 1.26 Art. 5º"),
    ("Parte de acidente", "Decreto 32.280 Art. 12"),
    # ... (mantenha sua lista completa de requisitos)
]

# ========== FUNÇÕES AUXILIARES ========== #
def pagina_vazia(img, threshold=0.95):
    """Verifica se a página é predominantemente vazia"""
    try:
        img_np = np.array(img.convert('L'))
        white_pixels = np.sum(img_np > 200)
        total_pixels = img_np.size
        return (white_pixels / total_pixels) > threshold
    except Exception as e:
        st.warning(f"Erro ao verificar página vazia: {str(e)}")
        return False

def processar_imagem_ocr(img):
    """Processa imagem para OCR"""
    try:
        # Conversão básica para melhorar OCR
        if img.mode != 'L':
            img = img.convert('L')
        return pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
    except Exception as e:
        st.error(f"Erro no OCR: {str(e)}")
        return ""

def extrair_texto_pdf(uploaded_file, modo_rapido=False):
    """Extrai texto do PDF com processamento paralelo"""
    try:
        dpi = 150 if modo_rapido else 200
        imagens = convert_from_bytes(
            uploaded_file.read(),
            dpi=dpi,
            thread_count=min(4, os.cpu_count() or 2)
        )
        
        textos = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for img in imagens:
                if not pagina_vazia(img):
                    futures.append(executor.submit(processar_imagem_ocr, img))
                else:
                    futures.append(executor.submit(lambda: ""))
            
            for future in futures:
                textos.append(future.result())
        
        return "\n\n".join(textos)
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None

# ========== INTERFACE PRINCIPAL ========== #
def main():
    # Configuração inicial da sessão
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    
    # Header
    st.title("🛡️ Sistema de Análise Documental - BM/RS")
    st.markdown("### Seção de Afastamentos e Acidentes")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Carregue o arquivo PDF para análise",
        type=["pdf"]
    )
    
    # Opções de processamento
    modo_rapido = st.checkbox("Modo rápido (análise parcial)", value=True)
    
    # Botão de análise
    if uploaded_file and st.button("Iniciar Análise"):
        with st.spinner("Processando documento..."):
            texto = extrair_texto_pdf(uploaded_file, modo_rapido)
            
            if texto:
                # Análise dos documentos encontrados
                encontrados = {}
                texto_min = texto.lower()
                
                for doc, artigo in REQUISITOS:
                    if doc.lower() in texto_min:
                        encontrados[doc] = {"artigo": artigo}
                
                nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
                
                st.session_state.resultados = {
                    "encontrados": encontrados,
                    "nao_encontrados": nao_encontrados,
                    "texto": texto
                }
    
    # Exibição de resultados
    if st.session_state.resultados:
        st.success("Análise concluída!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("✅ Documentos Encontrados")
            for doc, info in st.session_state.resultados["encontrados"].items():
                st.markdown(f"- **{doc}** (Art. {info['artigo']})")
        
        with col2:
            st.subheader("❌ Documentos Faltantes")
            for doc in st.session_state.resultados["nao_encontrados"]:
                artigo = next(artigo for d, artigo in REQUISITOS if d == doc)
                st.markdown(f"- {doc} (Art. {artigo})")

if __name__ == "__main__":
    main()
