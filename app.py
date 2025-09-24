import streamlit as st
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
from datetime import datetime
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Configuração simplificada do Tesseract para Streamlit Cloud
try:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
except:
    try:
        pytesseract.pytesseract.tesseract_cmd = "/app/.apt/usr/bin/tesseract"
    except:
        st.warning("Tesseract não encontrado - algumas funcionalidades podem não funcionar")

TESSERACT_CONFIG = "--oem 3 --psm 6 -l por+eng"

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== MODELOS DE DOCUMENTOS ========== #
DOCUMENTOS_PADRAO = [
    {
        "nome": "Portaria da Sindicância Especial",
        "artigo": "NI 1.26 Art. 5º",
        "padroes_texto": [
            r"PORTARIA\s+N[º°]\s*\d+/SINDASV/\d{4}",
            r"INSTAURAÇÃO\s+DE\s+SINDICÂNCIA\s+ESPECIAL",
            r"DO\s+CMT\s+DO\s+\d+°\s+BPM.*?SINDICÂNCIA\s+ESPECIAL"
        ],
        "palavras_chave": ["portaria", "sindicância", "especial", "instauração", "acidente de serviço"],
        "pagina_referencia": 3
    },
    {
        "nome": "Parte de acidente",
        "artigo": "Decreto 32.280 Art. 12",
        "padroes_texto": [
            r"PARTE\s+N[º°]\s*\d+/P1/\d{4}",
            r"ACIDENTE\s+DE\s+SERVIÇO.*?TESTEMUNHOU\s+O\s+FATO",
            r"RELAT[ÓO]RIO\s+DE\s+OCORR[ÊE]NCIA\s+DE\s+ACIDENTE"
        ],
        "palavras_chave": ["parte", "acidente", "ocorrência", "relatório", "testemunhas"],
        "pagina_referencia": 6
    },
    {
        "nome": "Termo de Oitiva do Acidentado",
        "artigo": "RDBM Art. 78",
        "padroes_texto": [
            r"TERMO\s+DE\s+OITIVA\s+DO\s+ACIDENTADO",
            r"DECLARAÇÃO\s+DO\s+MILITAR\s+ACIDENTADO",
            r"OITIVA\s+DO\s+SERVIR\s+ACIDENTADO.*?RESPONDIDO"
        ],
        "palavras_chave": ["oitiva", "acidentado", "declaração", "depoimento", "militar"],
        "pagina_referencia": 18
    }
]

# ========== ANÁLISE DE ACIDENTES ========== #
class AcidenteAnalyzer:
    def __init__(self, textos_paginas: List[Tuple[int, str]]):
        self.textos_paginas = textos_paginas
        self.resultados = {
            'data_acidente': None,
            'numero_proa': None,
            'paginas_referencia': {
                'data_acidente': [],
                'numero_proa': []
            }
        }
    
    def find_data_acidente(self):
        """Encontra a data do acidente no texto do PDF"""
        date_patterns = [
            r'Data do fato:\s*(\d{2}/\d{2}/\d{4})',
            r'ocorrido em\s*(\d{2}/\d{2}/\d{4})',
            r'Data do acidente:\s*(\d{2}/\d{2}/\d{4})',
            r'(\d{2}/\d{2}/\d{4}).*acidente'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group(1)
                    try:
                        datetime.strptime(date_str, '%d/%m/%Y')
                        self.resultados['data_acidente'] = date_str
                        self.resultados['paginas_referencia']['data_acidente'].append(page_num)
                        return
                    except ValueError:
                        continue

    def find_numero_proa(self):
        """Encontra o número do PROA no texto do PDF"""
        proa_patterns = [
            r'PROA\s*n[º°o]*\s*([\d./-]+)',
            r'Processo\s*Administrativo\s*Eletrônico\s*([\d./-]+)',
            r'PROA\s*([\d./-]+)',
            r'24/1203-0022758-4'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in proa_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    proa_num = match.group(1) if match.lastindex else match.group(0)
                    self.resultados['numero_proa'] = proa_num
                    self.resultados['paginas_referencia']['numero_proa'].append(page_num)
                    return

    def analyze(self):
        """Executa toda a análise do PDF"""
        self.find_data_acidente()
        self.find_numero_proa()
        return self.resultados

# ========== FUNÇÕES AUXILIARES ========== #
def limpar_texto(texto: str) -> str:
    """Normaliza o texto para análise"""
    texto = re.sub(r'[^\w\sáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇº°-]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.upper()

def pagina_vazia(img, threshold: float = 0.95) -> bool:
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
    """Melhora a qualidade da imagem para OCR"""
    try:
        img_np = np.array(img)
        if len(img_np.shape) == 3:
            img_np = np.dot(img_np[...,:3], [0.2989, 0.5870, 0.1140])
        img_np = (img_np > 128).astype(np.uint8) * 255
        return Image.fromarray(img_np)
    except Exception as e:
        logger.error(f"Erro no pré-processamento: {str(e)}")
        return img

# ========== FUNÇÕES PRINCIPAIS ========== #
@st.cache_data(show_spinner=False)
def processar_pdf(uploaded_file, modo_rapido: bool = False) -> Dict[str, any]:
    """Processa o PDF e extrai texto de cada página"""
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        dpi = 150 if modo_rapido else 200
        max_paginas = 5 if modo_rapido else None
        
        with st.spinner("Convertendo PDF para imagens..."):
            imagens = convert_from_bytes(
                file_bytes,
                dpi=dpi,
                fmt='jpeg',
                first_page=1,
                last_page=max_paginas,
                thread_count=2
            )
        
        resultados = {
            "textos_paginas": [],
            "imagens_paginas": [],
            "metadados": {},
            "total_paginas": len(imagens),
            "analise_acidente": None
        }
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, img in enumerate(imagens):
            progresso = int((i + 1) / len(imagens) * 100)
            progress_bar.progress(progresso)
            status_text.text(f"Processando página {i+1}/{len(imagens)}...")
            
            if not pagina_vazia(img):
                img_processed = preprocess_image(img)
                texto = pytesseract.image_to_string(
                    img_processed,
                    lang='por',
                    config=TESSERACT_CONFIG
                )
                
                resultados["textos_paginas"].append((i+1, texto))
                resultados["imagens_paginas"].append(img)
                
                if i == 0:
                    resultados["metadados"] = extrair_metadados(texto)
        
        # Realiza análise específica para acidentes
        analyzer = AcidenteAnalyzer(resultados["textos_paginas"])
        resultados["analise_acidente"] = analyzer.analyze()
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro durante a análise: {str(e)}")
        return None

def extrair_metadados(texto: str) -> Dict[str, any]:
    """Extrai metadados importantes do texto"""
    metadados = {
        'numero_processo': None,
        'data_acidente': None,
        'militar_acidentado': None,
        'unidade': None,
        'data_abertura': None
    }
    
    texto_limpo = limpar_texto(texto)
    
    padroes_processo = [
        r"PROCESSO\s+ADMINISTRATIVO\s+ELETRÔNICO\s*[\n:]\s*(\d{2}/\d{4}-\d{7}-\d)",
        r"PROA\s*N[º°]\s*(\d{2}/\d{4}-\d{7}-\d)",
    ]
    
    for padrao in padroes_processo:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['numero_processo'] = match.group(1)
            break
    
    return metadados

def identificar_documento(texto: str) -> Optional[Dict[str, str]]:
    """Identifica o tipo de documento com base em padrões"""
    texto_limpo = limpar_texto(texto)
    
    for documento in DOCUMENTOS_PADRAO:
        for padrao in documento["padroes_texto"]:
            if re.search(padrao, texto_limpo, re.IGNORECASE):
                return documento
                
        palavras_encontradas = sum(
            1 for palavra in documento["palavras_chave"] 
            if palavra.upper() in texto_limpo
        )
        
        if palavras_encontradas / len(documento["palavras_chave"]) > 0.7:
            return documento
            
    return None

def analisar_documentos(resultados_processamento: Dict[str, any]) -> Dict[str, any]:
    """Analisa os textos extraídos para identificar documentos padrão"""
    documentos_encontrados = defaultdict(list)
    documentos_faltantes = [doc["nome"] for doc in DOCUMENTOS_PADRAO]
    
    for num_pagina, texto in resultados_processamento["textos_paginas"]:
        documento = identificar_documento(texto)
        if documento:
            documentos_encontrados[documento["nome"]].append({
                "pagina": num_pagina,
                "artigo": documento["artigo"]
            })
            
            if documento["nome"] in documentos_faltantes:
                documentos_faltantes.remove(documento["nome"])
    
    return {
        "metadados": resultados_processamento["metadados"],
        "documentos_encontrados": documentos_encontrados,
        "documentos_faltantes": documentos_faltantes,
        "total_paginas": resultados_processamento["total_paginas"],
        "paginas_processadas": len(resultados_processamento["textos_paginas"]),
        "imagens_paginas": resultados_processamento["imagens_paginas"]
    }

def gerar_relatorio(resultados: Dict[str, any]) -> str:
    """Gera um relatório textual com os resultados da análise"""
    relatorio = []
    
    relatorio.append("="*60)
    relatorio.append("BRIGADA MILITAR DO RIO GRANDE DO SUL")
    relatorio.append("SISTEMA DE ANÁLISE DOCUMENTAL")
    relatorio.append("="*60)
    
    relatorio.append(f"\n📋 INFORMAÇÕES DO PROCESSO")
    relatorio.append("-"*60)
    relatorio.append(f"▪ Número do processo: {resultados['metadados'].get('numero_processo', 'Não identificado')}")
    
    if resultados.get('analise_acidente'):
        relatorio.append(f"▪ Número do PROA: {resultados['analise_acidente'].get('numero_proa', 'Não identificado')}")
        relatorio.append(f"▪ Data do acidente: {resultados['analise_acidente'].get('data_acidente', 'Não identificada')}")
    
    relatorio.append(f"▪ Páginas analisadas: {resultados['paginas_processadas']}/{resultados['total_paginas']}")
    
    relatorio.append(f"\n✅ DOCUMENTOS ENCONTRADOS")
    relatorio.append("-"*60)
    if resultados["documentos_encontrados"]:
        for doc, info in resultados["documentos_encontrados"].items():
            paginas = ", ".join(str(item["pagina"]) for item in info)
            relatorio.append(f"▪ {doc} (Art. {info[0]['artigo']}) - Páginas: {paginas}")
    else:
        relatorio.append("Nenhum documento padrão identificado")
    
    relatorio.append("\n" + "="*60)
    relatorio.append(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    return "\n".join(relatorio)

# ========== INTERFACE STREAMLIT ========== #
def main():
    st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5F5;
    }
    .stButton>button {
        background-color: #006341;
        color: white;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("Sistema de Análise Documental - BM/RS")
    st.subheader("Seção de Afastamentos e Acidentes")

    # Upload do arquivo
    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"])
    
    if uploaded_file is not None:
        modo_rapido = st.toggle("Modo rápido (análise parcial)", value=True)
        
        if st.button("Iniciar Análise"):
            with st.spinner('Processando documento...'):
                processamento = processar_pdf(uploaded_file, modo_rapido)
                
                if processamento is not None:
                    resultados = analisar_documentos(processamento)
                    st.success("Análise concluída com sucesso!")
                    
                    # Abas de resultado
                    tab1, tab2, tab3 = st.tabs(["📋 Relatório", "✅ Documentos", "🔍 Acidente"])
                    
                    with tab1:
                        st.text_area("Relatório", gerar_relatorio(resultados), height=300)
                    
                    with tab2:
                        if resultados["documentos_encontrados"]:
                            for doc, info in resultados["documentos_encontrados"].items():
                                st.write(f"**{doc}** - Páginas: {', '.join(str(item['pagina']) for item in info)}")
                        else:
                            st.warning("Nenhum documento encontrado")
                    
                    with tab3:
                        if processamento["analise_acidente"]:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Data do Acidente", processamento["analise_acidente"]["data_acidente"] or "Não encontrada")
                            with col2:
                                st.metric("Número do PROA", processamento["analise_acidente"]["numero_proa"] or "Não encontrado")
                        else:
                            st.warning("Nenhuma informação de acidente encontrada")

if __name__ == "__main__":
    main()
