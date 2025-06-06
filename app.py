import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime
import base64
import os

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

# CSS personalizado com tema institucional
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
        font-family: 'Calibri', sans-serif;
    }
    
    h2, h3 {
        color: var(--verde-bm);
        font-family: 'Calibri', sans-serif;
    }
    
    .st-emotion-cache-1q7spjk, .stContainer {
        background-color: var(--branco);
        border-radius: 8px;
        padding: 15px;
        border: 1px solid var(--dourado);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stButton>button {
        background-color: var(--verde-bm);
        color: var(--branco);
        border-radius: 4px;
        font-weight: bold;
    }
    
    .stButton>button:hover {
        background-color: #004d2e;
    }
    
    [data-testid="stSidebar"] {
        background-color: var(--verde-bm);
        color: var(--branco);
    }
    
    .logo-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .logo-header {
        height: 80px;
    }
    
    @media (max-width: 768px) {
        .logo-container {
            flex-direction: column;
        }
    }
    
    .badge {
        background-color: var(--verde-bm);
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# Header institucional
st.markdown("""
<div class="logo-container">
    <div>
        <h1 style="margin-bottom: 0;">Sistema de Análise Documental</h1>
        <h3 style="margin-top: 0;">Seção de Afastamentos e Acidentes - BM/RS</h3>
    </div>
    <img class="logo-header" src="https://www.brigadamilitar.rs.gov.br/upload/recortes/202005/12153026_92567_TH.jpg">
</div>
""", unsafe_allow_html=True)

# Funções de processamento
def processar_pdf(uploaded_file):
    try:
        imagens = convert_from_bytes(uploaded_file.read())
    except Exception as e:
        st.error(f"Erro ao processar o PDF: {e}")
        return None, None

    encontrados = {}
    texto_por_pagina = []

    for i, imagem in enumerate(imagens):
        try:
            texto = pytesseract.image_to_string(imagem, lang='por')
        except Exception as e:
            st.error(f"Erro ao extrair texto da página {i+1}: {e}")
            texto = ""
        texto_por_pagina.append(texto)
        for requisito in REQUISITOS:
            if requisito.lower() in texto.lower():
                if requisito not in encontrados:
                    encontrados[requisito] = []
                encontrados[requisito].append(i + 1)

    nao_encontrados = [r for r in REQUISITOS if r not in encontrados]
    return encontrados, nao_encontrados

def gerar_relatorio(encontrados, nao_encontrados, data_acidente=None, numero_processo=None):
    doc = Document()
    
    # Cabeçalho institucional
    header = doc.add_paragraph()
    header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    
    doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
    
    # Informações do processo
    info_table = doc.add_table(rows=1, cols=2)
    info_cells = info_table.rows[0].cells
    info_cells[0].text = f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if numero_processo:
        info_cells[1].text = f"Processo: {numero_processo}"
    
    if data_acidente:
        doc.add_paragraph(f"Data do acidente: {data_acidente.strftime('%d/%m/%Y')}")
    
    doc.add_heading('Resultado da Análise Documental', level=1)
    
    # Seção de documentos encontrados
    doc.add_heading('Documentos Encontrados', level=2)
    if encontrados:
        for req, pags in encontrados.items():
            doc.add_paragraph(f'{req} - Página(s): {", ".join(map(str, pags))}', style='List Bullet')
    else:
        doc.add_paragraph("Nenhum documento requerido foi encontrado.", style='List Bullet')
    
    # Seção de documentos faltantes
    doc.add_heading('Documentos Faltantes', level=2)
    if nao_encontrados:
        for req in nao_encontrados:
            doc.add_paragraph(req, style='List Bullet')
    else:
        doc.add_paragraph("Todos os documentos requeridos foram encontrados.", style='List Bullet')
    
    # Rodapé
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("SD BM Dominique Castro")
    doc.add_paragraph("Seção de Afastamentos e Acidentes")
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Formulário de informações
with st.container(border=True):
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9")
    with col2:
        data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY")

# Upload do documento
with st.container(border=True):
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type="pdf")

# Processamento e resultados
if uploaded_file is not None:
    if uploaded_file.size > 20 * 1024 * 1024:
        st.error("Arquivo muito grande. Por favor, envie um arquivo menor que 20MB.")
    else:
        with st.spinner('Analisando o documento...'):
            encontrados, nao_encontrados = processar_pdf(uploaded_file)
        
        if encontrados is not None and nao_encontrados is not None:
            st.success('Análise concluída com sucesso!')
            
            # Visualização do documento
            with st.expander("📄 Visualizar Documento", expanded=False):
                try:
                    pdf_bytes = uploaded_file.getvalue()
                    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    pdf_display = f"""
                    <div style="border: 1px solid var(--dourado); border-radius: 8px; padding: 10px;">
                        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>
                    </div>
                    """
                    st.markdown(pdf_display, unsafe_allow_html=True)
                except Exception as e:
                    st.warning(f"Não foi possível exibir o PDF ({e})")

            # Resultados da análise
            tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
            
            with tab1:
                with st.container(border=True):
                    if encontrados:
                        st.markdown(f"**{len(encontrados)} de {len(REQUISITOS)} documentos encontrados**")
                        progresso = len(encontrados)/len(REQUISITOS)
                        st.progress(progresso, text=f"Completude: {progresso:.0%}")
                        
                        for req, pags in encontrados.items():
                            st.markdown(f"""
                            <div style="padding: 12px; margin: 8px 0; background-color: #E8F5E9; border-radius: 6px; border-left: 4px solid var(--verde-bm);">
                                <b>{req}</b><br>
                                <span class="badge">Páginas: {", ".join(map(str, pags))}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("Nenhum documento requerido foi encontrado.")

            with tab2:
                with st.container(border=True):
                    if nao_encontrados:
                        st.markdown(f"**{len(nao_encontrados)} documentos não encontrados**")
                        
                        for req in nao_encontrados:
                            st.markdown(f"""
                            <div style="padding: 12px; margin: 8px 0; background-color: #FFEBEE; border-radius: 6px; border-left: 4px solid #C62828;">
                                {req}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.success("Todos os documentos requeridos foram encontrados!")

            # Relatórios
            st.download_button(
                label="📄 Baixar Relatório Completo (DOCX)",
                data=gerar_relatorio(encontrados, nao_encontrados, data_acidente, numero_processo),
                file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )

# Sidebar institucional
st.sidebar.image("https://www.brigadamilitar.rs.gov.br/upload/recortes/202005/12153026_92567_TH.jpg", use_column_width=True)
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
st.sidebar.markdown("""
### 📌 Responsável Técnico do App
**SD BM Dominique Castro**  
Seção de Afastamentos e Acidentes  
📞 (51) 986371192 
✉ dadp-saa@bm.rs.gov.br  

*Versão 1.0 - {year}*  
""".format(year=datetime.now().year))
