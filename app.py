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

# CSS personalizado com tema institucional e estilo elegante e clean
st.markdown("""
<style>
    :root {
        --verde-bm: #006341;
        --dourado: #D4AF37;
        --cinza-escuro: #333333;
        --branco: #FFFFFF;
        --bege: #F5F5DC;
        --font-sans: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        --radius: 12px;
        --shadow-light: 0 4px 8px rgba(0,0,0,0.05);
    }

    body, .stApp {
        background-color: var(--bege);
        font-family: var(--font-sans);
        color: var(--cinza-escuro);
        max-width: 1200px;
        margin: 2rem auto 4rem auto;
        padding: 0 1.5rem;
    }

    h1 {
        font-size: 48px;
        font-weight: 700;
        color: var(--verde-bm);
        border-bottom: 3px solid var(--dourado);
        padding-bottom: 12px;
        margin-bottom: 2rem;
    }

    h2, h3 {
        font-weight: 600;
        color: var(--verde-bm);
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }

    .card {
        background: var(--branco);
        box-shadow: var(--shadow-light);
        border-radius: var(--radius);
        padding: 2rem 3rem;
        margin-bottom: 3rem;
    }

    .stButton>button {
        background-color: var(--verde-bm);
        color: var(--branco);
        font-weight: 700;
        font-size: 18px;
        padding: 0.625rem 2rem;
        border-radius: var(--radius);
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #004d2e;
    }

    input[type="text"], input[type="date"], .stFileUploader>div>input {
        width: 100%;
        padding: 0.625rem 1rem;
        font-size: 16px;
        border-radius: var(--radius);
        border: 1px solid #ddd;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
        box-sizing: border-box;
    }

    label {
        display: block;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .badge {
        background-color: var(--verde-bm);
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
        padding: 6px 12px;
        border-radius: var(--radius);
        display: inline-block;
        margin-top: 0.25rem;
    }

    .error-box {
        background-color: #FFE5E5;
        border-left: 5px solid #CC0000;
        padding: 12px 20px;
        border-radius: var(--radius);
        margin-bottom: 1.5rem;
        font-weight: 600;
        color: #990000;
    }

    .info-box {
        background-color: #E5F1FF;
        border-left: 5px solid #0073E6;
        padding: 12px 20px;
        border-radius: var(--radius);
        margin-bottom: 1.5rem;
        font-weight: 600;
        color: #004C99;
    }
</style>
""", unsafe_allow_html=True)

# Header com logo espartano e título
st.markdown("""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Spartan_Helmet.svg/1200px-Spartan_Helmet.svg.png" alt="Logo Espartano" style="height: 80px;">
    <h1>Sistema de Análise Documental</h1>
</div>
""", unsafe_allow_html=True)

# Formulário de informações do processo e upload em cartão
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9")
    with col2:
        data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY")
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"])
    st.markdown("</div>", unsafe_allow_html=True)

    if uploaded_file:
        if uploaded_file.type != "application/pdf":
            st.markdown('<div class="error-box">Por favor, envie um arquivo PDF válido.</div>', unsafe_allow_html=True)
            st.stop()
        if uploaded_file.size > 50 * 1024 * 1024:
            st.markdown('<div class="error-box">Arquivo muito grande. Tamanho máximo permitido: 50MB.</div>', unsafe_allow_html=True)
            st.stop()

# Função de processamento PDF e análise texto (igual antes, não muda)
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
        st.markdown(f"""
            <div class="error-box">
                <b>Erro ao processar o PDF:</b><br>{str(e)}<br><br>
                Por favor, verifique se:<ul>
                <li>O arquivo não está protegido por senha</li>
                <li>O arquivo não está corrompido</li>
                <li>O conteúdo está legível (não são apenas imagens)</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
        return None, None, None

# Função para gerar o relatório docx (mantida igual)
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

# Mostrar resultados e botões após upload e análise
if uploaded_file:
    try:
        with st.spinner('Analisando o documento... Isso pode levar alguns minutos para arquivos grandes...'):
            encontrados, nao_encontrados, texto_completo = processar_pdf(uploaded_file)
        if encontrados is None or nao_encontrados is None:
            st.markdown('<div class="error-box">Falha na análise do documento. Verifique o arquivo e tente novamente.</div>', unsafe_allow_html=True)
            st.stop()

        # Mostrar resumo
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

        # Botão para baixar relatório DOCX
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

# Sidebar moderno e clean com logo espartano
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
