import streamlit as st

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# ========== VERIFICAÇÃO DO OPENCV ========== #
try:
    import cv2
    CV2_AVAILABLE = True
    opencv_version = cv2.__version__
except ImportError:
    CV2_AVAILABLE = False
    opencv_version = "não instalado"

# ========== IMPORTS ========== #
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime
import base64
import logging
import re
import os
from concurrent.futures import ThreadPoolExecutor
import hashlib
from PIL import Image
import numpy as np

# ========== CONFIGURAÇÕES GLOBAIS ========== #
os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/4.00/tessdata"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TESSERACT_CONFIG = "--oem 1 --psm 6 -c tessedit_do_invert=0"

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

# ========== CSS PERSONALIZADO ========== #
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

# ========== FUNÇÕES AUXILIARES ========== #
def pagina_vazia(img, threshold=0.95):
    img_np = np.array(img.convert('L'))
    white_pixels = np.sum(img_np > 200)
    total_pixels = img_np.size
    return (white_pixels / total_pixels) > threshold

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

def extrair_numero_processo(texto):
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

@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def processar_pdf(uploaded_file, _hash, modo_rapido=False):
    try:
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 10
        thread_count = 2
        
        file_bytes = uploaded_file.read()
        imagens = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            thread_count=thread_count,
            fmt='jpeg',
            grayscale=True,
            first_page=1,
            last_page=max_paginas
        )
        
        if modo_rapido:
            imagens = imagens[::2]
        
        encontrados = {}
        texto_por_pagina = [""] * len(imagens)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with ThreadPoolExecutor(max_workers=min(4, (os.cpu_count() or 2))) as executor:
            batch_size = 2
            for i in range(0, len(imagens), batch_size):
                batch = imagens[i:i+batch_size]
                results = list(executor.map(
                    lambda img: pytesseract.image_to_string(
                        preprocess_image(img),
                        lang='por',
                        config=TESSERACT_CONFIG
                    ) if not pagina_vazia(img) else "",
                    batch
                ))
                
                for j, texto in enumerate(results):
                    texto_por_pagina[i+j] = texto[:10000]
                    progress_bar.progress((i+j+1) / len(imagens))
                    status_text.text(f"Processando página {i+j+1}/{len(imagens)}...")
        
        texto_completo = "\n\n".join(texto_por_pagina)
        texto_min = texto_completo.lower()
        
        for doc, artigo in REQUISITOS:
            if doc.lower() in texto_min:
                encontrados[doc] = {"artigo": artigo}
        
        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        
        progress_bar.empty()
        status_text.empty()
        
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro no processamento: {str(e)}")
        return None, None, None

def gerar_relatorio(encontrados, nao_encontrados, data_acidente=None, numero_processo=None):
    doc = Document()
    
    header = doc.add_paragraph()
    header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    
    doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
    
    info_table = doc.add_table(rows=1, cols=2)
    info_cells = info_table.rows[0].cells
    info_cells[0].text = f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if numero_processo:
        info_cells[1].text = f"Processo: {numero_processo}"
    
    if data_acidente:
        doc.add_paragraph(f"Data do acidente: {data_acidente.strftime('%d/%m/%Y')}")
    
    doc.add_heading('Resultado da Análise Documental', level=1)
    
    doc.add_heading('Documentos Encontrados', level=2)
    if encontrados:
        for doc_name, info in encontrados.items():
            doc.add_paragraph(
                f'{doc_name} (Art. {info["artigo"]})',
                style='List Bullet'
            )
    else:
        doc.add_paragraph("Nenhum documento encontrado", style='List Bullet')
    
    doc.add_heading('Documentos Faltantes', level=2)
    if nao_encontrados:
        for doc_name in nao_encontrados:
            artigo = next(artigo for doc, artigo in REQUISITOS if doc == doc_name)
            doc.add_paragraph(
                f'{doc_name} (Art. {artigo})',
                style='List Bullet'
            )
    
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("SD PM Dominique Castro")
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ========== INTERFACE PRINCIPAL ========== #
def main():
    if 'analise_iniciada' not in st.session_state:
        st.session_state.analise_iniciada = False
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None

    # Header institucional
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Seção de informações do processo
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

    # Seção de upload de documento
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📂 Documento para Análise")
        modo_rapido = st.toggle(
            "Modo rápido (análise parcial)", 
            help="Analisa apenas páginas selecionadas com configurações otimizadas",
            value=True,
            key="modo_rapido_toggle"
        )
        
        uploaded_file = st.file_uploader(
            "Carregue o arquivo PDF do processo", 
            type=["pdf"],
            label_visibility="collapsed",
            disabled=st.session_state.analise_iniciada,
            key="file_uploader"
        )
        
        if uploaded_file and not st.session_state.analise_iniciada:
            st.session_state.analise_iniciada = True
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Processamento do documento
    if uploaded_file is not None and st.session_state.analise_iniciada:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        
        with st.spinner('Otimizando análise...'):
            encontrados, nao_encontrados, texto_completo = processar_pdf(
                uploaded_file, 
                _hash=file_hash,
                modo_rapido=modo_rapido
            )
            
            if encontrados is not None:
                numero_extraido = extrair_numero_processo(texto_completo)
                data_extraida = extrair_data_acidente(texto_completo)
                
                if numero_extraido:
                    st.session_state.numero_processo_ext = numero_extraido
                if data_extraida:
                    st.session_state.data_acidente_ext = data_extraida
                
                st.session_state.resultados = {
                    "encontrados": encontrados,
                    "nao_encontrados": nao_encontrados,
                    "texto": texto_completo,
                    "modo_rapido": modo_rapido
                }
                
                st.success("Análise concluída com sucesso!")
                st.session_state.analise_iniciada = False
                st.rerun()

    # Exibição de resultados
    if st.session_state.get('resultados'):
        resultados = st.session_state.resultados
        
        if resultados["modo_rapido"]:
            st.warning("Modo rápido ativado - análise parcial realizada")

        if st.button("🔄 Limpar Cache e Reiniciar Análise"):
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()

        tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
        
        with tab1:
            if resultados["encontrados"]:
                progresso = len(resultados["encontrados"]) / len(REQUISITOS)
                st.metric("Completude Documental", value=f"{progresso:.0%}")
                
                for doc, info in resultados["encontrados"].items():
                    st.markdown(f"""
                    <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                    <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Nenhum documento encontrado")

        with tab2:
            if resultados["nao_encontrados"]:
                for doc in resultados["nao_encontrados"]:
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

        # Relatório
        st.download_button(
            label="📄 Baixar Relatório Completo",
            data=gerar_relatorio(
                resultados["encontrados"],
                resultados["nao_encontrados"],
                st.session_state.get('data_acidente_ext'),
                st.session_state.get('numero_processo_ext')
            ),
            file_name=f"relatorio_{st.session_state.get('numero_processo_ext', datetime.now().strftime('%Y%m%d'))}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    # Sidebar institucional
    with st.sidebar:
        # Status do OpenCV
        if CV2_AVAILABLE:
            st.success(f"✅ OpenCV {opencv_version} instalado")
        else:
            st.warning(
                "⚠️ OpenCV não instalado\n\n"
                "Algumas otimizações estarão desativadas.\n\n"
                "Para instalar:\n"
                "```bash\n"
                "pip install opencv-python\n"
                "```"
            )
        
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
