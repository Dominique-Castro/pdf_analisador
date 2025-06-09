import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime
import base64
import logging
import re

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verificação de dependências
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from docx import Document
except ImportError as e:
    st.error(f"Erro de dependência: {e}")
    st.stop()

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Lista de requisitos
REQUISITOS = [
    "Portaria da Sindicância Especial", "Parte de acidente",
    "Atestado de Origem", "Primeiro Boletim de atendimento médico",
    "Escala de serviço", "Ata de Habilitação para conduzir viatura",
    "Documentação operacional", "Inquérito Técnico", "CNH",
    "Formulário previsto na Portaria 095/SSP/15", "Oitiva do acidentado",
    "Oitiva das testemunhas", "Parecer do Encarregado",
    "Conclusão da Autoridade nomeante", "RHE", "LTS"
]

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado - Limpo, elegante, espaçamento generoso, tipografia forte e moderna
st.markdown("""
<style>
  :root {
    --color-primary: #111827;
    --color-accent: #006341;
    --color-light-bg: #ffffff;
    --color-muted-text: #6b7280;
    --radius: 0.75rem;
    --shadow-light: 0 2px 8px rgba(0,0,0,0.05);
    --shadow-medium: 0 4px 16px rgba(0,0,0,0.1);
  }
  body, html, .stApp {
    background-color: var(--color-light-bg);
    color: var(--color-muted-text);
    font-family: 'Inter', system-ui, sans-serif;
    margin: 0;
    padding: 0 1rem 2rem 1rem;
    max-width: 1200px;
    margin-left: auto;
    margin-right: auto;
  }
  header {
    position: sticky;
    top: 0;
    background: var(--color-light-bg);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0;
    box-shadow: var(--shadow-light);
    z-index: 99;
  }
  header h1 {
    font-weight: 800;
    font-size: 2.5rem;
    margin: 0;
    color: var(--color-primary);
  }
  .logo-img {
    height: 50px;
    width: auto;
  }
  main {
    padding-top: 3rem;
  }
  section {
    background: var(--color-light-bg);
    box-shadow: var(--shadow-medium);
    border-radius: var(--radius);
    padding: 2rem;
    margin-bottom: 3rem;
  }
  h2 {
    font-size: 2rem;
    font-weight: 700;
    color: var(--color-primary);
    margin-bottom: 1rem;
  }
  label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--color-primary);
  }
  input[type="text"], input[type="date"], .stFileUploader>div>input {
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: var(--radius);
    border: 1.5px solid #d1d5db;
    font-size: 1rem;
    margin-bottom: 1.5rem;
    box-sizing: border-box;
  }
  button, .stButton>button {
    background-color: var(--color-accent);
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    font-weight: 700;
    font-size: 1rem;
    border-radius: var(--radius);
    cursor: pointer;
    transition: background-color 0.3s;
  }
  button:hover, .stButton>button:hover {
    background-color: #004d2e;
  }
  .badge {
    background-color: var(--color-accent);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: var(--radius);
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
    margin-top: 0.25rem;
  }
  .error-box {
    background-color: #fef2f2;
    border-left: 6px solid #dc2626;
    padding: 1rem;
    border-radius: var(--radius);
    color: #b91c1c;
    font-weight: 600;
    margin-bottom: 1.5rem;
  }
  .info-box {
    background-color: #dbEafe;
    border-left: 6px solid #2563eb;
    padding: 1rem;
    border-radius: var(--radius);
    color: #1e40af;
    font-weight: 600;
    margin-bottom: 1.5rem;
  }
  iframe {
    width: 100%;
    height: 500px;
    border-radius: var(--radius);
    border: 1px solid #d4af37;
  }
</style>
""", unsafe_allow_html=True)

# Header com logo e título
st.markdown("""
<header>
  <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Spartan_Helmet.svg/600px-Spartan_Helmet.svg.png" alt="Logo Espartano" class="logo-img" />
  <h1>Sistema de Análise Documental</h1>
</header>
<main>
""", unsafe_allow_html=True)

with st.container():
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9", key="numero_processo")
    with col2:
        data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY", key="data_acidente")

with st.container():
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader(
        "Carregue o arquivo PDF do processo",
        type=["pdf"],
        key="file_uploader",
        label_visibility="visible"
    )
    if uploaded_file:
        if uploaded_file.type != "application/pdf":
            st.markdown('<div class="error-box">Por favor, envie um arquivo PDF válido.</div>', unsafe_allow_html=True)
            st.stop()
        if uploaded_file.size > 50 * 1024 * 1024:
            st.markdown('<div class="error-box">Arquivo muito grande. Tamanho máximo permitido: 50MB</div>', unsafe_allow_html=True)
            st.stop()

if uploaded_file:
    try:
        with st.spinner('Analisando o documento... Isso pode levar alguns minutos para arquivos grandes...'):
            definidos, nao_definidos, texto_completo = processar_pdf(uploaded_file)
        if definidos is None or nao_definidos is None:
            st.markdown('<div class="error-box">Falha na análise do documento. Verifique o arquivo e tente novamente.</div>', unsafe_allow_html=True)
            st.stop()
        numero_extraido = extrair_numero_processo(texto_completo)
        data_extraida = extrair_data_acidente(texto_completo)
        if numero_extraido:
            st.session_state.numero_processo = numero_extraido
            st.markdown(f'<div class="info-box">Número do processo identificado: <b>{numero_extraido}</b></div>', unsafe_allow_html=True)
        if data_extraida:
            st.session_state.data_acidente = data_extraida
            st.markdown(f'<div class="info-box">Data do acidente identificada: <b>{data_extraida.strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)
        st.success('Análise concluída com sucesso!')
        with st.expander("📄 Visualizar Documento", expanded=False):
            try:
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            except Exception as erro:
                logger.error(f"Erro ao exibir PDF: {erro}")
                st.markdown(f'<div class="error-box">Não foi possível exibir o PDF. Erro: {erro}</div>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
        with tab1:
            if definidos:
                st.markdown(f'<p><strong>{len(definidos)} de {len(REQUISITOS)} documentos encontrados</strong></p>', unsafe_allow_html=True)
                progresso = len(definidos) / len(REQUISITOS)
                st.progress(progresso)
                for req, pags in definidos.items():
                    st.markdown(f'''
                    <div style="padding:12px; margin:8px 0; background:#E8F5E9; border-radius:0.5rem; border-left: 4px solid var(--verde-bm);">
                        <b>{req}</b><br><span class="badge">Páginas: {", ".join(map(str, pags))}</span>
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.markdown('<div class="error-box">Nenhum documento requerido foi encontrado.</div>', unsafe_allow_html=True)
        with tab2:
            if nao_definidos:
                st.markdown(f'<p><strong>{len(nao_definidos)} documentos não encontrados</strong></p>', unsafe_allow_html=True)
                for req in nao_definidos:
                    st.markdown(f'''
                    <div style="padding:12px; margin:8px 0; background:#FFE4E6; border-radius:0.5rem; border-left: 4px solid #B91C1C;">
                        {req}
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.markdown('<div class="info-box">Todos os documentos requeridos foram encontrados!</div>', unsafe_allow_html=True)
        st.download_button(
            label="📄 Baixar Relatório Completo (DOCX)",
            data=gerar_relatorio(
                definidos,
                nao_definidos,
                data_acidente,
                numero_processo
            ),
            file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    except Exception as erro:
        logger.error(f"Erro inesperado: {erro}", exc_info=True)
        st.markdown(f'<div class="error-box"><b>Erro inesperado:</b><br>{erro}<br><br>Por favor, tente novamente. Se o problema persistir, contate o suporte técnico.</div>', unsafe_allow_html=True)

# Sidebar institucional moderno e minimalista
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Spartan_Helmet.svg/600px-Spartan_Helmet.svg.png",
    use_container_width=True
)
st.sidebar.markdown("""
### 🔍 Sobre o Sistema
**SAA - Sistema de Análise Documental**  
Ferramenta para verificação de documentos em processos administrativos, conforme:  
- Decreto nº 32.280/1986  
- NI EMBM 1.26/2023  
- Regulamento da Corporação  
""")

st.sidebar.markdown("---")

st.sidebar.markdown("""
### 📋 Documentos Verificados
{}
""".format("\n".join([f"• {req}" for req in REQUISITOS])))

st.sidebar.markdown("---")

st.sidebar.markdown(f"""
### 📌 Responsável Técnico do App
**SD BM Dominique Castro**  
Seção de Afastamentos e Acidentes  
📞 (51) 98637-1192  
✉ dadp-saa@bm.rs.gov.br  

*Versão 1.2 - {datetime.now().year}*  
""", unsafe_allow_html=True)

st.markdown("</main>", unsafe_allow_html=True)
