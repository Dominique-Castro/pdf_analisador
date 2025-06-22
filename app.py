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
    st.sidebar.warning("OpenCV não instalado - algumas otimizações desativadas")

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TESSERACT_CONFIG = "--oem 1 --psm 6"

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
def pagina_vazia(img, threshold=0.95):
    """Verifica se a página é predominantemente vazia"""
    img_np = np.array(img.convert('L'))
    white_pixels = np.sum(img_np > 200)
    total_pixels = img_np.size
    return (white_pixels / total_pixels) > threshold

def preprocess_image(img):
    """Processamento otimizado da imagem para OCR"""
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
    except Exception as e:
        logging.error(f"Erro no pré-processamento: {str(e)}")
        return img

def extrair_numero_processo(texto):
    """Extrai número do processo usando regex"""
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
    """Extrai data do acidente usando regex"""
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
    """Processa o PDF e retorna documentos encontrados"""
    try:
        # Reset do ponteiro do arquivo
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        # Configurações de processamento
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 5
        
        # Barra de progresso
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Iniciando processamento...")
        
        # Conversão PDF para imagens
        imagens = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            fmt='jpeg',
            grayscale=True,
            first_page=1,
            last_page=max_paginas,
            thread_count=1
        )
        progress_bar.progress(20)
        
        # Processamento das páginas
        encontrados = {}
        texto_completo = ""
        
        for i, img in enumerate(imagens):
            progresso = 20 + int(70 * (i / len(imagens)))
            progress_bar.progress(progresso)
            status_text.text(f"Analisando página {i+1}/{len(imagens)}...")
            
            if not pagina_vazia(img):
                img_processed = preprocess_image(img)
                texto = pytesseract.image_to_string(
                    img_processed,
                    lang='por',
                    config=TESSERACT_CONFIG
                )
                texto_completo += "\n\n" + texto
                
                # Verifica cada requisito no texto
                for doc, artigo in REQUISITOS:
                    if re.search(re.escape(doc.lower()), texto.lower()):
                        encontrados[doc] = {"artigo": artigo}
        
        progress_bar.progress(95)
        nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
        
        # Extrai metadados
        numero_processo = extrair_numero_processo(texto_completo)
        data_acidente = extrair_data_acidente(texto_completo)
        
        progress_bar.progress(100)
        return {
            "encontrados": encontrados,
            "nao_encontrados": nao_encontrados,
            "texto": texto_completo,
            "numero_processo": numero_processo,
            "data_acidente": data_acidente
        }
        
    except Exception as e:
        logging.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro durante a análise: {str(e)}")
        return None
    finally:
        if 'progress_bar' in locals(): progress_bar.empty()
        if 'status_text' in locals(): status_text.empty()

def gerar_relatorio(resultados):
    """Gera relatório em DOCX com formatação profissional"""
    try:
        doc = Document()
        
        # Cabeçalho
        header = doc.add_paragraph()
        header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
        header_run.bold = True
        header_run.font.size = 14
        
        doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
        
        # Informações básicas
        doc.add_paragraph(f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        if resultados.get('numero_processo'):
            doc.add_paragraph(f"Número do processo: {resultados['numero_processo']}")
        if resultados.get('data_acidente'):
            doc.add_paragraph(f"Data do acidente: {resultados['data_acidente'].strftime('%d/%m/%Y')}")
        
        doc.add_paragraph()
        
        # Documentos encontrados
        doc.add_heading('DOCUMENTOS ENCONTRADOS', level=1)
        if resultados['encontrados']:
            for doc_name, info in resultados['encontrados'].items():
                doc.add_paragraph(f"✓ {doc_name} (Art. {info['artigo']})", style='List Bullet')
        else:
            doc.add_paragraph("Nenhum documento encontrado", style='List Bullet')
        
        doc.add_paragraph()
        
        # Documentos faltantes
        doc.add_heading('DOCUMENTOS FALTANTES', level=1)
        if resultados['nao_encontrados']:
            for doc_name in resultados['nao_encontrados']:
                artigo = next(artigo for doc, artigo in REQUISITOS if doc == doc_name)
                doc.add_paragraph(f"✗ {doc_name} (Art. {artigo})", style='List Bullet')
        else:
            doc.add_paragraph("Todos os documentos foram encontrados", style='List Bullet')
        
        # Rodapé
        doc.add_page_break()
        doc.add_paragraph("_________________________________________")
        doc.add_paragraph("Responsável Técnico:")
        doc.add_paragraph("SD PM Dominique Castro")
        doc.add_paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        # Salva em buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {str(e)}")
        st.error("Erro ao gerar relatório")
        return None

# ========== INTERFACE PRINCIPAL ========== #
def main():
    # Header institucional
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Sidebar
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
            value=True,
            help="Analisa apenas páginas selecionadas para maior velocidade",
            key="modo_rapido_toggle"
        )
        
        uploaded_file = st.file_uploader(
            "Carregue o arquivo PDF do processo", 
            type=["pdf"],
            label_visibility="collapsed",
            key="file_uploader"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Processamento do documento
    if uploaded_file is not None:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        
        with st.spinner('Processando documento...'):
            resultados = processar_pdf(uploaded_file, file_hash, modo_rapido)
            
            if resultados is not None:
                # Atualiza campos com valores extraídos
                if resultados.get('numero_processo'):
                    numero_processo = resultados['numero_processo']
                if resultados.get('data_acidente'):
                    data_acidente = resultados['data_acidente']
                
                st.success("Análise concluída com sucesso!")
                
                # Exibição de resultados
                tab1, tab2 = st.tabs(["✅ Documentos Encontrados", "❌ Documentos Faltantes"])
                
                with tab1:
                    if resultados['encontrados']:
                        progresso = len(resultados['encontrados']) / len(REQUISITOS)
                        st.metric("Completude Documental", f"{progresso:.0%}")
                        
                        for doc, info in resultados['encontrados'].items():
                            st.markdown(f"""
                            <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                            <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("Nenhum documento encontrado")

                with tab2:
                    if resultados['nao_encontrados']:
                        for doc in resultados['nao_encontrados']:
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

                # Geração do relatório
                relatorio = gerar_relatorio(resultados)
                if relatorio:
                    st.download_button(
                        label="📄 Baixar Relatório Completo",
                        data=relatorio,
                        file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
