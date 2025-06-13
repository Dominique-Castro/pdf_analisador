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

# Configuração do Tesseract (ajuste conforme necessário)
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Lista de requisitos com base legal
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

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# CSS personalizado
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
</style>
""", unsafe_allow_html=True)

# Header institucional
col1, col2 = st.columns([4,1])
with col1:
    st.title("Sistema de Análise Documental")
    st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
with col2:
    st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

# Funções de processamento (mantidas as originais)
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

def processar_pdf(uploaded_file):
    try:
        imagens = convert_from_bytes(uploaded_file.read(), dpi=300)
        encontrados = {}
        texto_completo = ""

        for i, img in enumerate(imagens):
            texto = pytesseract.image_to_string(img, lang='por')
            texto_completo += texto + "\n\n"
            
            for doc, artigo in REQUISITOS:
                if doc.lower() in texto.lower():
                    if doc not in encontrados:
                        encontrados[doc] = {"paginas": [], "artigo": artigo}
                    encontrados[doc]["paginas"].append(i+1)

        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        return encontrados, nao_encontrados, texto_completo
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro ao processar documento: {str(e)}")
        return None, None, None

# Interface principal
with st.form("form_principal"):
    col1, col2 = st.columns(2)
    with col1:
        numero_processo = st.text_input("Número do Processo", placeholder="Ex: 2023.1234.5678-9")
    with col2:
        data_acidente = st.date_input("Data do Acidente", format="DD/MM/YYYY")
    
    arquivo = st.file_uploader("Documento PDF", type=["pdf"])
    
    if st.form_submit_button("Analisar Documento") and arquivo:
        with st.spinner("Processando documento..."):
            encontrados, nao_encontrados, texto = processar_pdf(arquivo)
            
            if encontrados is not None:
                st.session_state.resultados = {
                    "encontrados": encontrados,
                    "nao_encontrados": nao_encontrados,
                    "texto": texto
                }

# Exibição de resultados
if "resultados" in st.session_state:
    st.success("Análise concluída!")
    
    tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
    
    with tab1:
        for doc, info in st.session_state.resultados["encontrados"].items():
            st.markdown(f"""
            <div style='padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;'>
            <b>{doc}</b> <span class='badge-legal'>{info['artigo']}</span><br>
            Páginas: {', '.join(map(str, info['paginas']))}
            </div>
            """, unsafe_allow_html=True)
    
    with tab2:
        for doc in st.session_state.resultados["nao_encontrados"]:
            artigo = next((artigo for d, artigo in REQUISITOS if d == doc), "")
            st.markdown(f"""
            <div style='padding:10px;margin:5px;background:#FFEBEE;border-radius:5px;'>
            ❌ <b>{doc}</b> <span class='badge-legal'>{artigo}</span>
            </div>
            """, unsafe_allow_html=True)

    # Visualização do documento
    with st.expander("📄 Visualizar Documento"):
        arquivo.seek(0)
        base64_pdf = base64.b64encode(arquivo.read()).decode('utf-8')
        st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Erro ao exibir PDF: {str(e)}")

        # Download do relatório
        st.download_button(
            label="📄 Baixar Relatório Completo (DOCX)",
            data=criar_relatorio(st.session_state.resultados),
            file_name=f"relatorio_bmrs_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

if __name__ == "__main__":
    main()
