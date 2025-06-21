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

# ========== PALETA DE CORES MILITARES ========== #
primary_color = "#006341"  # Verde BM
secondary_color = "#D4AF37"  # Dourado
accent_color = "#8B0000"  # Vermelho militar
bg_color = "#F5F5F5"  # Fundo cinza claro

# ========== CSS PERSONALIZADO ========== #
st.markdown(f"""
<style>
    :root {{
        --verde-bm: {primary_color};
        --dourado: {secondary_color};
        --vermelho-militar: {accent_color};
        --bg-color: {bg_color};
    }}
    .stApp {{
        background-color: var(--bg-color);
    }}
    .stButton>button {{
        background-color: var(--verde-bm);
        color: white;
        border-radius: 8px;
    }}
    .stButton>button:hover {{
        background-color: #004d33;
        color: white;
    }}
    .badge-legal {{
        background-color: var(--dourado);
        color: #333;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
    }}
    .container-bordered {{
        border: 2px solid var(--verde-bm);
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #FFFFFF;
    }}
    .stSpinner > div > div {{
        border-top-color: var(--verde-bm) !important;
    }}
    .stAlert {{
        border-left: 4px solid var(--vermelho-militar);
    }}
</style>
""", unsafe_allow_html=True)

# ========== CONFIGURAÇÕES TÉCNICAS ========== #
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TESSERACT_CONFIG = "--oem 1 --psm 6 -c tessedit_do_invert=0"

# ========== LISTA DE REQUISITOS ========== #
REQUISITOS = [
    ("Portaria da Sindicância Especial", "NI 1.26 Art. 5º"),
    ("Parte de acidente", "Decreto 32.280 Art. 12"),
    # ... (todos os outros itens originais)
]

# ========== FUNÇÕES AUXILIARES ========== #
def pagina_vazia(img, threshold=0.95):
    img_np = np.array(img.convert('L'))
    white_pixels = np.sum(img_np > 200)
    return (white_pixels / img_np.size) > threshold

def preprocess_image(img):
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

@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def processar_pdf(uploaded_file, _hash, modo_rapido=False):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 10
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Convertendo PDF para imagens...")
        
        imagens = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            fmt='jpeg',
            grayscale=True,
            first_page=1,
            last_page=max_paginas
        )
        progress_bar.progress(30)
        
        encontrados = {}
        texto_por_pagina = []
        
        for i, img in enumerate(imagens):
            progresso = 30 + int(60 * (i / len(imagens)))
            progress_bar.progress(progresso)
            status_text.text(f"Processando página {i+1}/{len(imagens)}...")
            
            if not pagina_vazia(img):
                img_processed = preprocess_image(img)
                texto = pytesseract.image_to_string(
                    img_processed,
                    lang='por',
                    config=TESSERACT_CONFIG
                )[:10000]
                
                texto_por_pagina.append(texto)
                
                texto_min = texto.lower()
                for doc, artigo in REQUISITOS:
                    if doc.lower() in texto_min:
                        encontrados[doc] = {"artigo": artigo}
        
        progress_bar.progress(100)
        texto_completo = "\n\n".join(texto_por_pagina)
        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        return None, None, None
    finally:
        progress_bar.empty()
        status_text.empty()

# ========== INTERFACE ORIGINAL ========== #
def main():
    # Header institucional
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Seção de informações
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📋 Informações do Processo")
        col1, col2 = st.columns(2)
        with col1:
            numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9")
        with col2:
            data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY")
        st.markdown("</div>", unsafe_allow_html=True)

    # Seção de upload
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📂 Documento para Análise")
        modo_rapido = st.toggle("Modo rápido (análise parcial)", value=True)
        uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"], label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

    # Processamento
    if uploaded_file:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        encontrados, nao_encontrados, texto_completo = processar_pdf(uploaded_file, file_hash, modo_rapido)
        
        if encontrados is not None:
            st.success("Análise concluída com sucesso!")
            
            tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
            
            with tab1:
                if encontrados:
                    progresso = len(encontrados) / len(REQUISITOS)
                    st.metric("Completude Documental", f"{progresso:.0%}")
                    
                    for doc, info in encontrados.items():
                        st.markdown(f"""
                        <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                        <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("Nenhum documento encontrado")

            with tab2:
                if nao_encontrados:
                    for doc in nao_encontrados:
                        artigo = next(artigo for d, artigo in REQUISITOS if d == doc)
                        st.markdown(f"""
                        <div style="padding:10px;margin:5px;background:#FFEBEE;border-radius:5px;">
                        ❌ <b>{doc}</b> <span class='badge-legal'>Art. {artigo}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("Todos os documentos foram encontrados!")

            # Visualização do documento
            with st.expander("📄 Visualizar Documento", expanded=False):
                try:
                    uploaded_file.seek(0)
                    base64_pdf = base64.b64encode(uploaded_file.read()).decode('utf-8')
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"Erro ao exibir PDF: {str(e)}")

    # Sidebar institucional
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
