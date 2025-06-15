import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime
import base64
import logging
import re
import time

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Lista de requisitos com referências legais
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

# Inicialização das variáveis de sessão
if 'numero_processo_ext' not in st.session_state:
    st.session_state.numero_processo_ext = ''
if 'data_acidente_ext' not in st.session_state:
    st.session_state.data_acidente_ext = None

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Função para criar containers com borda
def container_com_borda():
    st.markdown("""
    <div style="
        border: 2px solid #006341;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #FFFFFF;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    ">
    """, unsafe_allow_html=True)
    return st.markdown("</div>", unsafe_allow_html=True)

# CSS personalizado
st.markdown("""
<style>
    :root {
        --verde-bm: #006341;
        --dourado: #D4AF37;
        --cinza-escuro: #333333;
        --branco: #FFFFFF;
        --bege: #F5F5DC;
    }
    
    .stApp {
        background-color: var(--bege);
    }
    
    h1 {
        color: var(--verde-bm);
        border-bottom: 2px solid var(--dourado);
        padding-bottom: 10px;
    }
    
    .stButton>button {
        background-color: var(--verde-bm);
        color: var(--branco);
    }
    
    .badge-legal {
        background-color: var(--dourado);
        color: #333;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    
    .error-box {
        background-color: #FFEBEE;
        border-left: 4px solid #C62828;
        padding: 12px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# Header institucional
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div>
        <h1 style="margin-bottom: 0;">Sistema de Análise Documental</h1>
        <h3 style="margin-top: 0;">Seção de Afastamentos e Acidentes - BM/RS</h3>
    </div>
    <img src="https://i.imgur.com/By8hwnl.jpeg" style="height: 80px;">
</div>
""", unsafe_allow_html=True)

# Funções principais
def extrair_numero_processo(texto):
    padroes = [
        r"\d{4}\.\d{4}\.\d{4}-\d",
        r"\d{4}\.\d{3,4}\/\d{4}",
        r"PAA-\d{4}\/\d{4}",
        r"PA-\d{4}\/\d{4}"
    ]
    for padrao in padroes:
        matches = re.findall(padrao, texto)
        if matches:
            return matches[0]
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

def processar_pdf(uploaded_file):
    try:
        imagens = convert_from_bytes(
            uploaded_file.read(),
            dpi=300,
            thread_count=4,
            fmt='jpeg'
        )
        
        encontrados = {}
        texto_completo = ""

        for i, img in enumerate(imagens):
            texto = pytesseract.image_to_string(img, lang='por')
            texto_completo += texto + "\n\n"
            
            for doc, artigo in REQUISITOS:
                if doc.lower() in texto.lower():
                    if doc not in encontrados:
                        encontrados[doc] = {"paginas": [], "artigo": artigo}
                    encontrados[doc]["paginas"].append(i + 1)

        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        logger.error(f"Erro ao processar PDF: {str(e)}")
        st.error(f"Erro no processamento: {str(e)}")
        return None, None, None

def gerar_relatorio(encontrados, nao_encontrados, data_acidente=None, numero_processo=None):
    doc = Document()
    
    # Cabeçalho
    header = doc.add_paragraph()
    header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    
    doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
    
    # Metadados
    info_table = doc.add_table(rows=1, cols=2)
    info_cells = info_table.rows[0].cells
    info_cells[0].text = f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if numero_processo:
        info_cells[1].text = f"Processo: {numero_processo}"
    
    if data_acidente:
        doc.add_paragraph(f"Data do acidente: {data_acidente.strftime('%d/%m/%Y')}")
    
    # Conteúdo
    doc.add_heading('Resultado da Análise Documental', level=1)
    
    doc.add_heading('Documentos Encontrados', level=2)
    if encontrados:
        for doc_name, info in encontrados.items():
            doc.add_paragraph(
                f'{doc_name} (Art. {info["artigo"]}) - Páginas: {", ".join(map(str, info["paginas"]))}',
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
    
    # Rodapé
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("SD BM Dominique Castro")
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Interface principal
with st.container():
    st.markdown("""
    <div style="
        border: 2px solid #006341;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #FFFFFF;
    ">
    """, unsafe_allow_html=True)
    
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input(
            "Número do Processo:",
            value=st.session_state.numero_processo_ext,
            placeholder="Ex: 2023.1234.5678-9"
        )
    with col2:
        data_acidente = st.date_input(
            "Data do Acidente:",
            value=st.session_state.data_acidente_ext,
            format="DD/MM/YYYY"
        )
    
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown("""
    <div style="
        border: 2px solid #006341;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #FFFFFF;
    ">
    """, unsafe_allow_html=True)
    
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader(
        "Carregue o arquivo PDF do processo", 
        type=["pdf"],
        label_visibility="collapsed"
    )
    
    st.markdown("</div>", unsafe_allow_html=True)

# Processamento
if uploaded_file is not None:
    try:
        with st.spinner('Analisando documento...'):
            encontrados, nao_encontrados, texto_completo = processar_pdf(uploaded_file)
            
            if encontrados is not None:
                # Atualiza campos automaticamente
                numero_extraido = extrair_numero_processo(texto_completo)
                data_extraida = extrair_data_acidente(texto_completo)
                
                if numero_extraido:
                    st.session_state.numero_processo_ext = numero_extraido
                if data_extraida:
                    st.session_state.data_acidente_ext = data_extraida
                
                st.session_state.resultados = {
                    "encontrados": encontrados,
                    "nao_encontrados": nao_encontrados,
                    "texto": texto_completo
                }
                st.success("Análise concluída!")
                
                # Atualiza a página para mostrar os campos preenchidos
                time.sleep(0.5)
                st.rerun()

    except Exception as e:
        st.error(f"Erro inesperado: {str(e)}")

# Exibição de resultados
if "resultados" in st.session_state:
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

    # Resultados
    tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
    
    with tab1:
        if st.session_state.resultados["encontrados"]:
            progresso = len(st.session_state.resultados["encontrados"]) / len(REQUISITOS)
            st.metric("Completude Documental", value=f"{progresso:.0%}")
            
            for doc, info in st.session_state.resultados["encontrados"].items():
                st.markdown(f"""
                <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span><br>
                Páginas: {", ".join(map(str, info["paginas"]))}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Nenhum documento encontrado")

    with tab2:
        if st.session_state.resultados["nao_encontrados"]:
            for doc in st.session_state.resultados["nao_encontrados"]:
                artigo = next(artigo for d, artigo in REQUISITOS if d == doc)
                st.markdown(f"""
                <div style="padding:10px;margin:5px;background:#FFEBEE;border-radius:5px;">
                ❌ <b>{doc}</b> <span class='badge-legal'>Art. {artigo}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("Todos os documentos foram encontrados!")

    # Relatório
    st.download_button(
        label="📄 Baixar Relatório Completo",
        data=gerar_relatorio(
            st.session_state.resultados["encontrados"],
            st.session_state.resultados["nao_encontrados"],
            st.session_state.data_acidente_ext,
            st.session_state.numero_processo_ext
        ),
        file_name=f"relatorio_{st.session_state.numero_processo_ext or datetime.now().strftime('%Y%m%d')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

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
    **SD BM Dominique Castro**  
    Seção de Afastamentos e Acidentes  
    *Versão 2.1 - {datetime.now().year}*
    """)
