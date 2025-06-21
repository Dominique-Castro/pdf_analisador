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

# Configurações de performance
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/4.00/tessdata"

# Verificação do OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Configuração do Tesseract
TESSERACT_CONFIG = "--oem 1 --psm 6"
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# ========== LISTA DE REQUISITOS ========== #
REQUISITOS = [
    ("Portaria da Sindicância Especial", "NI 1.26 Art. 5º"),
    ("Parte de acidente", "Decreto 32.280 Art. 12"),
    ("Atestado de Origem", "NI 1.26 Anexo III"),
    ("Primeiro Boletim médico", "RDBM Cap. VII"),
    ("Escala de serviço", "Portaria 095/SSP/15"),
    ("Ata de Habilitação para conduzir viatura", "NI 1.26 §2º Art. 8"),
    ("Documentação operacional", "RDBM Art. 45"),
    ("Inquérito Técnico", "Decreto 32.280 Art. 15"),
    ("CNH válida", "NI 1.26 Art. 10"),
    ("Formulário previsto na Portaria 095/SSP/15", ""),
    ("Oitiva do acidentado", "RDBM Art. 78"),
    ("Oitiva das testemunhas", "Decreto 32.280 Art. 18"),
    ("Parecer do Encarregado", "NI 1.26 Art. 12"),
    ("Conclusão da Autoridade nomeante", "RDBM Art. 123"),
    ("RHE", "NI 1.26 Anexo II"),
    ("LTS", "Portaria 095/SSP/15")
]

# ========== FUNÇÕES AUXILIARES ========== #
def verificar_ambiente():
    """Exibe o status do ambiente no sidebar"""
    with st.sidebar.expander("⚙️ Diagnóstico do Sistema"):
        if CV2_AVAILABLE:
            st.success("✅ OpenCV instalado")
        else:
            st.error("❌ OpenCV não instalado")
            st.code("pip install opencv-python-headless", language="bash")
        
        try:
            pytesseract.get_tesseract_version()
            st.success("✅ Tesseract OCR funcionando")
        except Exception:
            st.error("❌ Problema no Tesseract")

def pagina_vazia(img, threshold=0.95):
    """Verificação otimizada de página vazia"""
    img_np = np.array(img.convert('L'))
    white_pixels = np.sum(img_np > 200)
    return (white_pixels / img_np.size) > threshold

def preprocess_image(img):
    """Pré-processamento otimizado"""
    try:
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
    except Exception:
        return img

def extrair_numero_processo(texto):
    """Extrai número do processo com regex"""
    padroes = [
        r"\d{4}\.\d{4}\.\d{4}-\d",
        r"\d{4}\.\d{3,4}\/\d{4}",
        r"PAA-\d{4}\/\d{4}",
        r"PA-\d{4}\/\d{4}"
    ]
    for padrao in padroes:
        matches = re.findall(padrao, texto)
        if matches: return matches[0]
    return None

def extrair_data_acidente(texto):
    """Extrai data do acidente com regex"""
    padroes = [
        r"Data do Acidente:?\s*(\d{2}/\d{2}/\d{4})",
        r"Acidente ocorrido em:?\s*(\d{2}/\d{2}/\d{4})",
        r"(\d{2}/\d{2}/\d{4}).*?(acidente|sinistro)"
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            try:
                data_str = match.group(1) if match.groups() else match.group(0)
                return datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError:
                continue
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def processar_pdf(uploaded_file, modo_rapido=False):
    """Processamento principal do PDF"""
    try:
        # Configurações de performance
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 5
        
        # Controle de progresso
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Iniciando análise...")
        
        # Conversão PDF para imagens
        file_bytes = uploaded_file.read()
        progress_bar.progress(10)
        
        imagens = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            fmt='jpeg',
            grayscale=True,
            first_page=1,
            last_page=max_paginas
        )
        progress_bar.progress(30)
        
        # Processamento das páginas
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
                )[:5000]
                
                texto_por_pagina.append(texto)
                
                # Verificação de requisitos
                texto_min = texto.lower()
                for doc, artigo in REQUISITOS:
                    if doc.lower() in texto_min:
                        encontrados[doc] = {"artigo": artigo}
        
        # Finalização
        progress_bar.progress(100)
        texto_completo = "\n\n".join(texto_por_pagina)
        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        st.error(f"Erro durante a análise: {str(e)}")
        return None, None, None
    finally:
        if 'progress_bar' in locals(): progress_bar.empty()
        if 'status_text' in locals(): status_text.empty()

def mostrar_pdf(uploaded_file):
    """Exibição robusta do PDF"""
    try:
        # Cache para evitar problemas com o objeto de arquivo
        @st.cache_data
        def get_pdf_bytes(_file):
            return _file.getvalue() if hasattr(_file, 'getvalue') else open(_file.name, 'rb').read()
        
        pdf_bytes = get_pdf_bytes(uploaded_file)
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{base64_pdf}" '
            'width="100%" height="600" style="border:none;"></iframe>',
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Erro ao exibir documento: {str(e)}")

def gerar_relatorio(encontrados, nao_encontrados, data_acidente=None, numero_processo=None):
    """Geração de relatório em DOCX"""
    doc = Document()
    
    # Cabeçalho
    header = doc.add_paragraph()
    header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    
    # Informações
    doc.add_paragraph(f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if numero_processo:
        doc.add_paragraph(f"Processo: {numero_processo}")
    if data_acidente:
        doc.add_paragraph(f"Data do acidente: {data_acidente.strftime('%d/%m/%Y')}")
    
    # Resultados
    doc.add_heading('Documentos Encontrados', level=1)
    for doc_name, info in encontrados.items():
        doc.add_paragraph(f"{doc_name} (Art. {info['artigo']})", style='ListBullet')
    
    doc.add_heading('Documentos Faltantes', level=1)
    for doc_name in nao_encontrados:
        artigo = next(artigo for doc, artigo in REQUISITOS if doc == doc_name)
        doc.add_paragraph(f"{doc_name} (Art. {artigo})", style='ListBullet')
    
    # Geração do arquivo
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ========== INTERFACE PRINCIPAL ========== #
def main():
    # Configuração do layout
    st.markdown("""
    <style>
        .container-bordered {
            border: 2px solid #006341;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        .badge-legal {
            background-color: #D4AF37;
            color: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Sidebar
    verificar_ambiente()
    modo_rapido = st.sidebar.toggle("Modo rápido", True)

    # Upload do documento
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"])
    
    if uploaded_file:
        # Processamento
        with st.spinner("Analisando documento..."):
            resultados = processar_pdf(uploaded_file, modo_rapido)
        
        if resultados[0] is not None:
            encontrados, nao_encontrados, texto_completo = resultados
            
            # Extração automática de metadados
            numero_processo = extrair_numero_processo(texto_completo)
            data_acidente = extrair_data_acidente(texto_completo)
            
            # Exibição de resultados
            st.success("Análise concluída com sucesso!")
            
            # Métricas
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Documentos Encontrados", f"{len(encontrados)}/{len(REQUISITOS)}")
            with col2:
                st.metric("Taxa de Completude", f"{(len(encontrados)/len(REQUISITOS)):.0%}")
            
            # Abas de resultados
            tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
            
            with tab1:
                for doc, info in encontrados.items():
                    st.markdown(f"""
                    <div class="container-bordered">
                        <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            with tab2:
                for doc in nao_encontrados:
                    artigo = next(artigo for d, artigo in REQUISITOS if d == doc)
                    st.markdown(f"""
                    <div class="container-bordered">
                        ❌ <b>{doc}</b> <span class='badge-legal'>Art. {artigo}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Visualização e download
            mostrar_pdf(uploaded_file)
            
            st.download_button(
                label="📄 Baixar Relatório Completo",
                data=gerar_relatorio(encontrados, nao_encontrados, data_acidente, numero_processo),
                file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

if __name__ == "__main__":
    main()
