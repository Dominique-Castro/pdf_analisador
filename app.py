import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime
import base64
import os
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
    
    .error-box {
        background-color: #FFEBEE;
        border-left: 4px solid #C62828;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
    }
    
    .info-box {
        background-color: #E3F2FD;
        border-left: 4px solid #1976D2;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
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
    <img class="logo-header" src="https://br.freepik.com/vetores-premium/arquivo-vetorial-de-tatuagem_388547181.htm#fromView=keyword&page=1&position=19&uuid=4e2e96b3-b06f-4761-9322-622c48510ba4&query=Espartano+Png">
</div>
""", unsafe_allow_html=True)

# Funções auxiliares para extração de dados
def extrair_numero_processo(texto):
    """Extrai número do processo no formato padrão da BM/RS"""
    padroes = [
        r"\d{4}\.\d{4}\.\d{4}-\d",  # 25/1203-0011111-0
        r"\d{4}\.\d{3,4}\/\d{4}",    # 2023.123/2024
        r"PAA-\d{4}\/\d{4}",          # PAA-2023/2024
        r"PA-\d{4}\/\d{4}",           # PA-2023/2024
    ]
    
    for padrao in padroes:
        matches = re.findall(padrao, texto)
        if matches:
            return matches[0]
    return None

def extrair_data_acidente(texto):
    """Extrai data do acidente no formato dd-mm-aaaa"""
    padroes = [
        r"Data do Acidente:?\s*(\d{2}/\d{2}/\d{4})",
        r"Acidente ocorrido em:?\s*(\d{2}/\d{2}/\d{4})",
        r"(\d{2}/\d{2}/\d{4}).*?(acidente|sinistro)",
        r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/(19|20)\d{2}"  # formato genérico
    ]
    
    for padrao in padroes:
        matches = re.search(padrao, texto, re.IGNORECASE)
        if matches:
            try:
                # Verifica quantos grupos foram capturados
                if len(matches.groups()) > 1:
                    # Se houver grupos separados (dia, mês, ano)
                    dia, mes, ano = matches.groups()[0], matches.groups()[1], matches.groups()[2]
                    data_str = f"{dia}/{mes}/{ano}"
                else:
                    data_str = matches.group(1) if matches.groups() else matches.group(0)
                
                return datetime.strptime(data_str, "%d/%m/%Y").date()
            except (ValueError, IndexError) as e:
                logger.warning(f"Erro ao converter data: {e}")
                continue
    return None

# Funções de processamento
def processar_pdf(uploaded_file):
    try:
        uploaded_file.seek(0)
        
        # Converte PDF para imagens
        imagens = convert_from_bytes(
            uploaded_file.read(),
            dpi=300,
            thread_count=4,
            fmt='jpeg'
        )
        
        encontrados = {}
        texto_por_pagina = []
        texto_completo = ""

        for i, imagem in enumerate(imagens):
            try:
                texto = pytesseract.image_to_string(
                    imagem, 
                    lang='por',
                    config='--psm 6 --oem 3'
                )
                texto_por_pagina.append(texto)
                texto_completo += texto + "\n\n"
                
                for requisito in REQUISITOS:
                    if requisito.lower() in texto.lower():
                        if requisito not in encontrados:
                            encontrados[requisito] = []
                        encontrados[requisito].append(i + 1)
                        
            except Exception as e:
                logger.error(f"Erro ao processar página {i+1}: {str(e)}")
                st.error(f"Erro ao processar página {i+1}")
                continue

        nao_encontrados = [r for r in REQUISITOS if r not in encontrados]
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        logger.error(f"Erro grave ao processar o PDF: {str(e)}", exc_info=True)
        st.markdown(f"""
        <div class="error-box">
            <b>Erro ao processar o PDF:</b><br>
            {str(e)}<br><br>
            Por favor, verifique se:
            <ul>
                <li>O arquivo não está protegido por senha</li>
                <li>O arquivo não está corrompido</li>
                <li>O conteúdo está legível (não são apenas imagens)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
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

# Formulário de informações
with st.container(border=True):
    st.subheader("📋 Informações do Processo")
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo:", placeholder="Ex: 2023.1234.5678-9", key="numero_processo")
    with col2:
        data_acidente = st.date_input("Data do Acidente:", format="DD/MM/YYYY", key="data_acidente")

# Upload do documento
with st.container(border=True):
    st.subheader("📂 Documento para Análise")
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"], key="file_uploader")
    
    if uploaded_file is not None:
        if uploaded_file.type != "application/pdf":
            st.markdown("""
            <div class="error-box">
                Por favor, envie um arquivo PDF válido.
            </div>
            """, unsafe_allow_html=True)
            st.stop()
        
        if uploaded_file.size > 50 * 1024 * 1024:
            st.markdown("""
            <div class="error-box">
                Arquivo muito grande. Tamanho máximo permitido: 50MB
            </div>
            """, unsafe_allow_html=True)
            st.stop()

# Processamento e resultados
if uploaded_file is not None:
    try:
        with st.spinner('Analisando o documento... Isso pode levar alguns minutos para arquivos grandes...'):
            encontrados, nao_encontrados, texto_completo = processar_pdf(uploaded_file)
            
            if encontrados is None or nao_encontrados is None:
                st.markdown("""
                <div class="error-box">
                    Falha na análise do documento. Verifique o arquivo e tente novamente.
                </div>
                """, unsafe_allow_html=True)
                st.stop()
                
        # Extrai e preenche automaticamente os campos
        numero_extraido = extrair_numero_processo(texto_completo)
        data_extraida = extrair_data_acidente(texto_completo)
        
        if numero_extraido:
            st.session_state.numero_processo = numero_extraido
            st.markdown(f"""
            <div class="info-box">
                Número do processo identificado: <b>{numero_extraido}</b>
            </div>
            """, unsafe_allow_html=True)
        
        if data_extraida:
            st.session_state.data_acidente = data_extraida
            st.markdown(f"""
            <div class="info-box">
                Data do acidente identificada: <b>{data_extraida.strftime('%d/%m/%Y')}</b>
            </div>
            """, unsafe_allow_html=True)
        
        st.success('Análise concluída com sucesso!')
        
        # Visualização do documento
        with st.expander("📄 Visualizar Documento", expanded=False):
            try:
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f"""
                <div style="border: 1px solid var(--dourado); border-radius: 8px; padding: 10px;">
                    <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>
                </div>
                """
                st.markdown(pdf_display, unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Erro ao exibir PDF: {str(e)}")
                st.markdown(f"""
                <div class="error-box">
                    Não foi possível exibir o PDF. Erro: {str(e)}
                </div>
                """, unsafe_allow_html=True)

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
                    st.markdown("""
                    <div class="error-box">
                        Nenhum documento requerido foi encontrado.
                    </div>
                    """, unsafe_allow_html=True)

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
                    st.markdown("""
                    <div class="info-box">
                        Todos os documentos requeridos foram encontrados!
                    </div>
                    """, unsafe_allow_html=True)

        # Relatórios
        st.download_button(
            label="📄 Baixar Relatório Completo (DOCX)",
            data=gerar_relatorio(
                encontrados, 
                nao_encontrados, 
                st.session_state.get('data_acidente'), 
                st.session_state.get('numero_processo')
            ),
            file_name=f"relatorio_{st.session_state.get('numero_processo', datetime.now().strftime('%Y%m%d'))}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
        st.markdown(f"""
        <div class="error-box">
            <b>Erro inesperado:</b><br>
            {str(e)}<br><br>
            Por favor, tente novamente. Se o problema persistir, contate o suporte técnico.
        </div>
        """, unsafe_allow_html=True)

# Sidebar institucional
st.sidebar.image("https://https://br.pinterest.com/pin/6614730698024787/", use_container_width=True)
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

*Versão 1.2 - {year}*  
""".format(year=datetime.now().year), unsafe_allow_html=True)
