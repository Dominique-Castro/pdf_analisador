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
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# ========== CONFIGURAÇÃO INICIAL ========== #
nltk.download('stopwords')
nltk.download('punkt')

st.set_page_config(
    page_title="Sistema de Análise Documental Inteligente - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# ========== VERIFICAÇÃO DE DEPENDÊNCIAS ========== #
try:
    import cv2
    CV2_AVAILABLE = True
    st.success(f"✅ OpenCV {cv2.__version__} instalado!")
except ImportError:
    CV2_AVAILABLE = False
    st.error("""
    ❌ OpenCV não está instalado!
    Algumas otimizações de imagem estarão desativadas.
    Adicione 'opencv-python-headless' ao requirements.txt
    """)

# ========== CONSTANTES E CONFIGURAÇÕES ========== #
MODELOS_DIR = "modelos_documentos"
os.makedirs(MODELOS_DIR, exist_ok=True)

primary_color = "#006341"  # Verde BM
secondary_color = "#D4AF37"  # Dourado
accent_color = "#8B0000"  # Vermelho militar
bg_color = "#F5F5F5"  # Fundo cinza claro

# Configuração do Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    TESSERACT_CONFIG = "--oem 1 --psm 6"
except Exception as e:
    st.error(f"Erro na configuração do Tesseract: {str(e)}")
    TESSERACT_CONFIG = ""

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== MODELO DE DOCUMENTO ========== #
class DocumentModel:
    def __init__(self, nome, artigo, keywords=None, model_text=None, min_similarity=0.7):
        self.nome = nome
        self.artigo = artigo
        self.keywords = keywords or []
        self.model_text = model_text or ""
        self.min_similarity = min_similarity
        self.vectorizer = TfidfVectorizer(stop_words='portuguese')
        
    def train(self, text_samples):
        """Treina o modelo com amostras de texto"""
        if not isinstance(text_samples, list):
            text_samples = [text_samples]
        self.model_text = "\n".join(text_samples)
        self.keywords = self._extract_keywords(text_samples)
        
    def _extract_keywords(self, texts):
        """Extrai palavras-chave importantes"""
        stop_words = set(stopwords.words('portuguese'))
        words = []
        for text in texts:
            tokens = word_tokenize(text.lower())
            words += [word for word in tokens if word.isalpha() and word not in stop_words]
        
        word_counts = Counter(words)
        return [word for word, count in word_counts.most_common(20)]
    
    def match(self, text):
        """Verifica se o texto corresponde a este modelo de documento"""
        # Verificação por palavras-chave
        text_lower = text.lower()
        keyword_matches = sum(1 for kw in self.keywords if kw.lower() in text_lower)
        keyword_score = keyword_matches / len(self.keywords) if self.keywords else 0
        
        # Verificação por similaridade de texto
        if self.model_text:
            try:
                vectors = self.vectorizer.fit_transform([self.model_text, text])
                similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            except:
                similarity = 0
        else:
            similarity = 0
        
        # Combina os scores
        combined_score = (keyword_score * 0.6) + (similarity * 0.4)
        return combined_score >= self.min_similarity

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
def carregar_modelos():
    modelos = []
    for doc, artigo in REQUISITOS:
        model_path = os.path.join(MODELOS_DIR, f"{doc}.json")
        if os.path.exists(model_path):
            with open(model_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                modelos.append(DocumentModel(
                    nome=data['nome'],
                    artigo=data['artigo'],
                    keywords=data['keywords'],
                    model_text=data['model_text'],
                    min_similarity=data.get('min_similarity', 0.7)
                ))
        else:
            modelos.append(DocumentModel(
                nome=doc,
                artigo=artigo,
                keywords=[doc.split()[0].lower()],
                min_similarity=0.5
            ))
    return modelos

def pagina_vazia(img, threshold=0.95):
    """Verifica se a página é predominantemente vazia"""
    try:
        if img.mode != 'L':
            img = img.convert('L')
        img_array = np.array(img)
        white_pixels = np.sum(img_array > 200)
        total_pixels = img_array.size
        return (white_pixels / total_pixels) > threshold
    except Exception as e:
        logger.error(f"Erro ao verificar página vazia: {str(e)}")
        return False

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
        logger.error(f"Erro no pré-processamento: {str(e)}")
        return img

def extrair_metadados(texto):
    """Extrai metadados importantes do texto"""
    resultados = {
        'numero_processo': None,
        'data_acidente': None
    }
    
    # Padrões para número do processo
    padroes_processo = [
        r"\d{4}\.\d{4}\.\d{4}-\d",
        r"\d{4}\.\d{3,4}\/\d{4}",
        r"PAA-\d{4}\/\d{4}",
        r"PA-\d{4}\/\d{4}"
    ]
    
    for padrao in padroes_processo:
        match = re.search(padrao, texto)
        if match: 
            resultados['numero_processo'] = match.group(0)
            break
    
    # Padrões para data do acidente
    padroes_data = [
        r"Data do Acidente:?\s*(\d{2}/\d{2}/\d{4})",
        r"Acidente ocorrido em:?\s*(\d{2}/\d{2}/\d{4})",
        r"(\d{2}/\d{2}/\d{4}).*?(acidente|sinistro)"
    ]
    
    for padrao in padroes_data:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            data_str = match.group(1) if match.groups() else match.group(0)
            try:
                resultados['data_acidente'] = datetime.strptime(data_str, "%d/%m/%Y").date()
                break
            except ValueError:
                continue
    
    return resultados

@st.cache_data(show_spinner=False, max_entries=3, ttl=3600)
def processar_pdf(uploaded_file, _hash, modo_rapido=False):
    """Processa o PDF e extrai texto de cada página"""
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        dpi = 150 if modo_rapido else 200
        max_paginas = 3 if modo_rapido else 10
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Iniciando processamento...")
        
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
        
        textos_paginas = []
        pdf_pages = []
        
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
                textos_paginas.append((i+1, texto))
                
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                pdf_pages.append(img_byte_arr.getvalue())
        
        progress_bar.progress(95)
        
        # Extrai metadados do texto completo
        texto_completo = "\n\n".join(f"--- PÁGINA {num} ---\n{text}" for num, text in textos_paginas)
        metadados = extrair_metadados(texto_completo)
        
        progress_bar.progress(100)
        return {
            "textos_paginas": textos_paginas,
            "pdf_pages": pdf_pages,
            "total_pages": len(imagens),
            **metadados
        }
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro durante a análise: {str(e)}")
        return None
    finally:
        if 'progress_bar' in locals(): progress_bar.empty()
        if 'status_text' in locals(): status_text.empty()

def analisar_com_modelos(textos_paginas):
    """Analisa as páginas usando os modelos treinados"""
    modelos = carregar_modelos()
    encontrados = {}
    
    for modelo in modelos:
        paginas_encontradas = []
        
        for num_pagina, texto in textos_paginas:
            if modelo.match(texto):
                paginas_encontradas.append(num_pagina)
        
        if paginas_encontradas:
            encontrados[modelo.nome] = {
                'artigo': modelo.artigo,
                'paginas': paginas_encontradas
            }
    
    nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
    
    return {
        'encontrados': encontrados,
        'nao_encontrados': nao_encontrados
    }

def gerar_relatorio(resultados):
    """Gera relatório em DOCX com os resultados"""
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
        doc.add_paragraph(f"Total de páginas analisadas: {resultados.get('total_pages', 'N/A')}")
        
        doc.add_paragraph()
        
        # Documentos encontrados
        doc.add_heading('DOCUMENTOS ENCONTRADOS', level=1)
        if resultados['encontrados']:
            for doc_name, info in resultados['encontrados'].items():
                paginas = ", ".join(map(str, info['paginas']))
                doc.add_paragraph(
                    f"✓ {doc_name} (Art. {info['artigo']}) - Páginas: {paginas}",
                    style='List Bullet'
                )
        else:
            doc.add_paragraph("Nenhum documento encontrado", style='List Bullet')
        
        doc.add_paragraph()
        
        # Documentos faltantes
        doc.add_heading('DOCUMENTOS FALTANTES', level=1)
        if resultados['nao_encontrados']:
            for doc_name in resultados['nao_encontrados']:
                artigo = next(artigo for d, artigo in REQUISITOS if d == doc_name)
                doc.add_paragraph(f"✗ {doc_name} (Art. {artigo})", style='List Bullet')
        else:
            doc.add_paragraph("Todos os documentos foram encontrados", style='List Bullet')
        
        # Rodapé
        doc.add_page_break()
        doc.add_paragraph("_________________________________________")
        doc.add_paragraph("Responsável Técnico:")
        doc.add_paragraph("SD PM Dominique Castro")
        doc.add_paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {str(e)}")
        st.error("Erro ao gerar relatório")
        return None

def mostrar_pdf(pdf_pages):
    """Exibe visualizador de PDF com navegação por páginas"""
    try:
        if not pdf_pages:
            st.warning("Nenhuma página disponível para visualização")
            return
            
        st.markdown("### Visualizador de Documento")
        
        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            page_num = st.number_input(
                "Página:",
                min_value=1,
                max_value=len(pdf_pages),
                value=1,
                step=1
            )
        
        st.image(
            pdf_pages[page_num-1],
            caption=f"Página {page_num} de {len(pdf_pages)}",
            use_column_width=True
        )
        
    except Exception as e:
        logger.error(f"Erro ao exibir PDF: {str(e)}")
        st.error("Erro ao carregar visualizador de documento")

def treinar_modelo_interface():
    """Interface para treinamento de novos modelos"""
    st.sidebar.markdown("## 🛠 Treinar Novos Modelos")
    doc_selecionado = st.sidebar.selectbox(
        "Selecione o documento para treinar",
        [doc for doc, _ in REQUISITOS]
    )
    
    uploaded_samples = st.sidebar.file_uploader(
        f"Carregue amostras de '{doc_selecionado}' (PDF ou TXT)",
        type=["pdf", "txt"],
        accept_multiple_files=True
    )
    
    if uploaded_samples and st.sidebar.button("Treinar Modelo"):
        textos_amostra = []
        for sample in uploaded_samples:
            if sample.name.endswith('.pdf'):
                images = convert_from_bytes(sample.read())
                text = "\n".join(pytesseract.image_to_string(img) for img in images)
                textos_amostra.append(text)
            elif sample.name.endswith('.txt'):
                textos_amostra.append(sample.read().decode('utf-8'))
        
        if textos_amostra:
            modelo = DocumentModel(doc_selecionado, next(artigo for d, artigo in REQUISITOS if d == doc_selecionado))
            modelo.train(textos_amostra)
            
            model_path = os.path.join(MODELOS_DIR, f"{doc_selecionado}.json")
            with open(model_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'nome': modelo.nome,
                    'artigo': modelo.artigo,
                    'keywords': modelo.keywords,
                    'model_text': modelo.model_text,
                    'min_similarity': modelo.min_similarity
                }, f, ensure_ascii=False, indent=2)
            
            st.sidebar.success(f"Modelo para '{doc_selecionado}' treinado com {len(textos_amostra)} amostras!")

# ========== INTERFACE PRINCIPAL ========== #
def main():
    # CSS Personalizado
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
        .pdf-viewer {{
            border: 2px solid var(--verde-bm);
            border-radius: 8px;
        }}
        .ocr-warning {{
            background-color: #FFF3E0;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
    </style>
    """, unsafe_allow_html=True)

    # Header institucional
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental Inteligente")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

    # Aviso sobre OCR se OpenCV não estiver disponível
    if not CV2_AVAILABLE:
        st.markdown("""
        <div class="ocr-warning">
        ⚠️ <strong>Atenção:</strong> O OpenCV não está instalado no ambiente. 
        A qualidade do OCR pode ser reduzida. Recomenda-se instalar 
        'opencv-python-headless' no arquivo requirements.txt.
        </div>
        """, unsafe_allow_html=True)

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
        
        # Interface de treinamento
        treinar_modelo_interface()

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
        
        with st.spinner('Processando documento com reconhecimento inteligente...'):
            # Processa o PDF e extrai texto das páginas
            processamento = processar_pdf(uploaded_file, file_hash, modo_rapido)
            
            if processamento is not None:
                # Analisa os textos com os modelos treinados
                analise = analisar_com_modelos(processamento['textos_paginas'])
                
                # Combina os resultados
                resultados = {
                    **processamento,
                    **analise
                }
                
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
                            paginas = ", ".join(map(str, info['paginas']))
                            st.markdown(f"""
                            <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                            <b>{doc}</b> <span class='badge-legal'>Art. {info['artigo']}</span>
                            <div style="font-size:0.9em;margin-top:5px;">Páginas: {paginas}</div>
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
                with st.expander("📄 Visualizador de Documento", expanded=False):
                    mostrar_pdf(resultados.get('pdf_pages', []))

                # Geração do relatório
                relatorio = gerar_relatorio(resultados)
                if relatorio:
                    st.download_button(
                        label="📄 Baixar Relatório Completo",
                        data=relatorio,
                        file_name=f"relatorio_{numero_processo or datetime.now().strftime('%Y%m%d')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_relatorio"
                    )

if __name__ == "__main__":
    main()
