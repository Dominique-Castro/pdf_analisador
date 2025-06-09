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

# Configuração da página com design moderno e limpo
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS aplicado segundo guideline default - minimalista e elegante
st.markdown("""
<style>
  :root {
    --color-bg: #ffffff;
    --color-text: #6b7280;
    --color-primary: #111827;
    --color-accent: #000000;
    --border-radius: 0.75rem;
    --shadow-light: 0 2px 8px rgba(0,0,0,0.05);
    --font-headings: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    --font-body: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  }

  body, .stApp {
    background-color: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-body);
    max-width: 1200px;
    margin: 3rem auto 5rem auto;
    padding: 0 2rem;
  }

  header {
    position: sticky;
    top: 0;
    background: var(--color-bg);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0;
    box-shadow: var(--shadow-light);
    margin-bottom: 3rem;
    z-index: 999;
  }

  header h1 {
    font-family: var(--font-headings);
    font-size: 3rem;
    font-weight: 700;
    color: var(--color-primary);
    margin: 0;
  }

  .logo-img {
    height: 52px;
    width: auto;
  }

  section {
    background: var(--color-bg);
    box-shadow: var(--shadow-light);
    border-radius: var(--border-radius);
    padding: 2rem 3rem;
    margin-bottom: 3rem;
  }

  h2 {
    font-family: var(--font-headings);
    font-size: 2.5rem;
    font-weight: 600;
    color: var(--color-primary);
    margin-bottom: 1.5rem;
  }

  label {
    display: block;
    font-weight: 700;
    margin-bottom: 0.5rem;
    color: var(--color-primary);
  }

  input[type="text"], input[type="date"], .stFileUploader>div>input {
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: var(--border-radius);
    border: 1.5px solid #d1d5db;
    font-size: 1.125rem;
    margin-bottom: 2rem;
    box-sizing: border-box;
  }

  .stButton > button {
    background-color: var(--color-accent);
    color: #fff;
    font-weight: 700;
    font-size: 1.125rem;
    padding: 0.75rem 2.5rem;
    border-radius: var(--border-radius);
    border: none;
    cursor: pointer;
    transition: background-color 0.25s ease;
  }

  .stButton > button:hover {
    background-color: #333333;
  }

  .badge {
    display: inline-block;
    background-color: var(--color-accent);
    color: #fff;
    padding: 0.4rem 1rem;
    border-radius: var(--border-radius);
    font-weight: 700;
    font-size: 0.875rem;
    margin-top: 0.3rem;
  }

  .error-box {
    background-color: #FEF2F2;
    border-left: 5px solid #F87171;
    padding: 1rem 1.5rem;
    border-radius: var(--border-radius);
    color: #B91C1C;
    font-weight: 600;
    margin-bottom: 2rem;
  }

  .info-box {
    background-color: #EFF6FF;
    border-left: 5px solid #3B82F6;
    padding: 1rem 1.5rem;
    border-radius: var(--border-radius);
    color: #1E40AF;
    font-weight: 600;
    margin-bottom: 2rem;
  }

  iframe {
    border-radius: var(--border-radius);
    border: 1px solid #d1d5db;
    width: 100%;
    height: 500px;
  }

  /* Responsive padding for smaller screens */
  @media (max-width: 768px) {
    body, .stApp {
      padding: 0 1rem 3rem 1rem;
    }
    section {
      padding: 1.5rem 2rem;
      margin-bottom: 2rem;
    }
    header h1 {
      font-size: 2rem;
    }
  }

</style>
""", unsafe_allow_html=True)

# Header com logo e título
st.markdown("""
<header>
  <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Spartan_Helmet.svg/600px-Spartan_Helmet.svg.png" alt="Logo Espartano" class="logo-img" />
  <h1>Sistema de Análise Documental</h1>
</header>
""", unsafe_allow_html=True)

# Seção Informações do Processo
with st.container():
    st.markdown('<section>', unsafe_allow_html=True)
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9")
    with col2:
        data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY")
    st.markdown('</section>', unsafe_allow_html=True)

# Seção Upload Documento
with st.container():
    st.markdown('<section>', unsafe_allow_html=True)
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"])
    if uploaded_file:
        if uploaded_file.type != "application/pdf":
            st.markdown('<div class="error-box">Por favor, envie um arquivo PDF válido.</div>', unsafe_allow_html=True)
            st.stop()
        if uploaded_file.size > 50 * 1024 * 1024:
            st.markdown('<div class="error-box">Arquivo muito grande. Tamanho máximo permitido: 50MB.</div>', unsafe_allow_html=True)
            st.stop()
    st.markdown('</section>', unsafe_allow_html=True)

# Função para processar o PDF
def processar_pdf(uploaded_file):
    try:
        uploaded_file.seek(0)
        imagens = convert_from_bytes(uploaded_file.read(), dpi=300, thread_count=4, fmt='jpeg')
        encontrados = {}
        texto_completo = ""
        for i, imagem in enumerate(imagens):
            try:
                texto = pytesseract.image_to_string(imagem, lang='por', config='--psm 6 --oem 3')
                texto_completo += texto + "\n\n"
                for requisito in REQUISITOS:
                    if requisito.lower() in texto.lower():
                        encontrados.setdefault(requisito, []).append(i + 1)
            except Exception as e:
                logger.error(f"Erro ao processar página {i+1}: {e}")
                st.error(f"Erro ao processar página {i+1}")
                continue
        nao_encontrados = [r for r in REQUISITOS if r not in encontrados]
        return encontrados, nao_encontrados, texto_completo
    except Exception as e:
        logger.error(f"Erro grave ao processar o PDF: {e}", exc_info=True)
        st.markdown(f'<div class="error-box"><b>Erro ao processar o PDF:</b> {str(e)}</div>', unsafe_allow_html=True)
        return None, None, None

# Função para gerar relatório DOCX
def gerar_relatorio(encontrados, nao_encontrados, data_acidente=None, numero_processo=None):
    doc = Document()
    header_run = doc.add_paragraph().add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
    info_table = doc.add_table(rows=1, cols=2)
    cells = info_table.rows[0].cells
    cells[0].text = f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if numero_processo:
        cells[1].text = f"Processo: {numero_processo}"
    if data_acidente:
        doc.add_paragraph(f"Data do acidente: {data_acidente.strftime('%d/%m/%Y')}")
    doc.add_heading('Resultado da Análise Documental', level=1)
    doc.add_heading('Documentos Encontrados', level=2)
    if encontrados:
        for req, pags in encontrados.items():
            doc.add_paragraph(f'{req} - Página(s): {", ".join(map(str, pags))}', style='List Bullet')
    else:
        doc.add_paragraph("Nenhum documento requerido foi encontrado.", style='List Bullet')
    doc.add_heading('Documentos Faltantes', level=2)
    if nao_encontrados:
        for req in nao_encontrados:
            doc.add_paragraph(req, style='List Bullet')
    else:
        doc.add_paragraph("Todos os documentos requeridos foram encontrados.", style='List Bullet')
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("SD BM Dominique Castro")
    doc.add_paragraph("Seção de Afastamentos e Acidentes")
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Processamento e exibição dos resultados
if uploaded_file:
    try:
        with st.spinner('Analisando o documento... Isso pode levar alguns minutos para arquivos grandes...'):
            encontrados, nao_encontrados, texto_completo = processar_pdf(uploaded_file)
        if encontrados is None or nao_encontrados is None:
            st.markdown('<div class="error-box">Falha na análise do documento. Verifique o arquivo e tente novamente.</div>', unsafe_allow_html=True)
            st.stop()

        st.success('Análise concluída com sucesso!')

        tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])

        with tab1:
            if encontrados:
                st.markdown(f'<p><strong>{len(encontrados)} de {len(REQUISITOS)} documentos encontrados</strong></p>', unsafe_allow_html=True)
                progresso = len(encontrados) / len(REQUISITOS)
                st.progress(progresso)
                for req, pags in encontrados.items():
                    st.markdown(f'''
                        <div style="padding:12px; margin:8px 0; background:#E8F5E9; border-radius:12px; border-left: 4px solid var(--verde-bm);">
                            <b>{req}</b><br><span class="badge">Páginas: {", ".join(map(str, pags))}</span>
                        </div>
                    ''', unsafe_allow_html=True)
            else:
                st.markdown('<div class="error-box">Nenhum documento requerido foi encontrado.</div>', unsafe_allow_html=True)

        with tab2:
            if nao_encontrados:
                st.markdown(f'<p><strong>{len(nao_encontrados)} documentos não encontrados</strong></p>', unsafe_allow_html=True)
                for req in nao_encontrados:
                    st.markdown(f'''
                        <div style="padding:12px; margin:8px 0; background:#FFE4E6; border-radius:12px; border-left: 4px solid #C62828;">
                            {req}
                        </div>
                    ''', unsafe_allow_html=True)
            else:
                st.markdown('<div class="info-box">Todos os documentos requeridos foram encontrados!</div>', unsafe_allow_html=True)

        st.download_button(
            label="📄 Baixar Relatório Completo (DOCX)",
            data=gerar_relatorio(
                encontrados,
                nao_encontrados,
                data_acidente,
                numero_processo
            ),
            file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

    except Exception as e:
        logger.error(f"Erro inesperado: {e}", exc_info=True)
        st.markdown(f'<div class="error-box"><b>Erro inesperado:</b><br>{e}<br><br>Por favor, tente novamente. Se o problema persistir, contate o suporte técnico.</div>', unsafe_allow_html=True)

# Sidebar com logo espartano e informações institucionais
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
