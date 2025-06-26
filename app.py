import streamlit as st
import os
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

# Configurações do Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    TESSERACT_CONFIG = "--oem 3 --psm 6 -l por+eng"
except Exception as e:
    st.warning(f"Configuração do Tesseract não encontrada: {str(e)}")
    TESSERACT_CONFIG = ""

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
    },
    {
        "nome": "Termo de Oitiva de Testemunhas",
        "artigo": "Decreto 32.280 Art. 18",
        "padroes_texto": [
            r"TERMO\s+DE\s+OITIVA\s+DE\s+TESTEMUNHAS",
            r"DECLARAÇÃO\s+DA\s+TESTEMUNHA",
            r"TESTEMUNHA\s+N[º°]\s*\d+.*?RESPONDIDO"
        ],
        "palavras_chave": ["oitiva", "testemunha", "declaração", "depoimento"],
        "pagina_referencia": 17
    },
    {
        "nome": "Atestado de Origem",
        "artigo": "NI 1.26 Anexo III",
        "padroes_texto": [
            r"ATESTADO\s+DE\s+ORIGEM",
            r"LAUDO\s+MÉDICO.*?ACIDENTE\s+DE\s+SERVIÇO",
            r"FSR.*?NECESSIDADE\s+DE\s+AO"
        ],
        "palavras_chave": ["atestado", "origem", "médico", "laudo", "FSR"],
        "pagina_referencia": None
    },
    {
        "nome": "Boletim Médico",
        "artigo": "RDBM Cap. VII",
        "padroes_texto": [
            r"BOLETIM\s+DE\s+ATENDIMENTO\s+MÉDICO",
            r"EVOLUÇÕES\s+MÉDICAS.*?DIAGNÓSTICO",
            r"PRONTO\s+ATENDIMENTO.*?EVOLUÇÃO"
        ],
        "palavras_chave": ["boletim", "médico", "atendimento", "diagnóstico", "evolução"],
        "pagina_referencia": 8
    }
]

# ========== FUNÇÕES AUXILIARES ========== #
def limpar_texto(texto: str) -> str:
    """Normaliza o texto para análise removendo caracteres especiais e espaços excessivos"""
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
        
        # Conversão para escala de cinza se necessário
        if len(img_np.shape) == 3:
            img_np = np.dot(img_np[...,:3], [0.2989, 0.5870, 0.1140])
        
        # Binarização adaptativa
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
            "total_paginas": len(imagens)
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
                
                # Extrai metadados apenas da primeira página
                if i == 0:
                    resultados["metadados"] = extrair_metadados(texto)
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        st.error(f"Erro durante a análise: {str(e)}")
        return None

def extrair_metadados(texto: str) -> Dict[str, any]:
    """Extrai metadados importantes do texto com padrões específicos da BM/RS"""
    metadados = {
        'numero_processo': None,
        'data_acidente': None,
        'militar_acidentado': None,
        'unidade': None,
        'data_abertura': None
    }
    
    texto_limpo = limpar_texto(texto)
    
    # Padrões para número do processo
    padroes_processo = [
        r"PROCESSO\s+ADMINISTRATIVO\s+ELETRÔNICO\s*[\n:]\s*(\d{2}/\d{4}-\d{7}-\d)",
        r"PROA\s*N[º°]\s*(\d{2}/\d{4}-\d{7}-\d)",
        r"PROCESSO:\s*(\d{2}/\d{4}-\d{7}-\d)"
    ]
    
    # Padrões para militar acidentado
    padroes_militar = [
        r"MILITAR\s+ESTADUAL\s+SINDICADO:\s*(.+?),\s*ID\s*FUNC",
        r"ACIDENTE\s+DO\s+(SD|CB|3ºSGT|2ºSGT|1ºSGT|SUBTEN|ASP|2ºTEN|1ºTEN|CAP|MAJ|TENCEL|CEL)\s+(.+?),\s*ID",
        r"SD\s+([A-ZÀ-Ú\s]+)\s+ID\s+FUNC"
    ]
    
    # Padrões para unidade
    padroes_unidade = [
        r"\d+°\s*BPM.*?(NOVO\s+HAMBURGO|PORTO\s+ALEGRE|CANOAS)",
        r"CRPO/[A-Z]+\s+-\s+(\d+°\s*BPM)",
        r"LOTAÇÃO:\s*(CRPO/[A-Z]+/\d+°\s*BPM)"
    ]
    
    # Padrões para datas
    padroes_data = [
        r"DATA\s+DO\s+ACIDENTE:\s*(\d{2}/\d{2}/\d{4})",
        r"ACIDENTE\s+OCORRIDO\s+EM:\s*(\d{2}/\d{2}/\d{4})",
        r"FATO\s+OCORRIDO\s+EM\s+(\d{2}/\d{2}/\d{4})",
        r"DATA\s+DE\s+ABERTURA:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})"
    ]
    
    # Extração dos dados
    for padrao in padroes_processo:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['numero_processo'] = match.group(1)
            break
            
    for padrao in padroes_militar:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['militar_acidentado'] = ' '.join([x for x in match.groups() if x]).title()
            break
            
    for padrao in padroes_unidade:
        match = re.search(padrao, texto_limpo)
        if match:
            metadados['unidade'] = match.group(0).title()
            break
            
    for padrao in padroes_data:
        match = re.search(padrao, texto_limpo)
        if match:
            data_str = match.group(1)
            try:
                if len(data_str) > 10:  # Com hora
                    metadados['data_abertura'] = datetime.strptime(data_str, "%d/%m/%Y %H:%M:%S")
                else:
                    if "ACIDENTE" in padrao:
                        metadados['data_acidente'] = datetime.strptime(data_str, "%d/%m/%Y").date()
                    else:
                        metadados['data_abertura'] = datetime.strptime(data_str, "%d/%m/%Y")
            except ValueError:
                continue
    
    return metadados

def identificar_documento(texto: str) -> Optional[Dict[str, str]]:
    """Identifica o tipo de documento com base em padrões e palavras-chave"""
    texto_limpo = limpar_texto(texto)
    
    for documento in DOCUMENTOS_PADRAO:
        # Verifica padrões de texto primeiro
        for padrao in documento["padroes_texto"]:
            if re.search(padrao, texto_limpo, re.IGNORECASE):
                return documento
                
        # Fallback para palavras-chave
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
    
    # Cabeçalho
    relatorio.append("="*60)
    relatorio.append("BRIGADA MILITAR DO RIO GRANDE DO SUL")
    relatorio.append("SISTEMA DE ANÁLISE DOCUMENTAL - SEÇÃO DE AFASTAMENTOS E ACIDENTES")
    relatorio.append("="*60)
    
    # Metadados
    relatorio.append(f"\n📋 INFORMAÇÕES DO PROCESSO")
    relatorio.append("-"*60)
    relatorio.append(f"▪ Número do processo: {resultados['metadados'].get('numero_processo', 'Não identificado')}")
    relatorio.append(f"▪ Militar acidentado: {resultados['metadados'].get('militar_acidentado', 'Não identificado')}")
    relatorio.append(f"▪ Unidade: {resultados['metadados'].get('unidade', 'Não identificada')}")
    relatorio.append(f"▪ Data do acidente: {resultados['metadados'].get('data_acidente', 'Não identificada')}")
    relatorio.append(f"▪ Data da abertura: {resultados['metadados'].get('data_abertura', 'Não identificada')}")
    relatorio.append(f"▪ Páginas analisadas: {resultados['paginas_processadas']}/{resultados['total_paginas']}")
    
    # Documentos encontrados
    relatorio.append(f"\n✅ DOCUMENTOS ENCONTRADOS")
    relatorio.append("-"*60)
    if resultados["documentos_encontrados"]:
        for doc, info in resultados["documentos_encontrados"].items():
            paginas = ", ".join(str(item["pagina"]) for item in info)
            relatorio.append(f"▪ {doc} (Art. {info[0]['artigo']}) - Páginas: {paginas}")
    else:
        relatorio.append("Nenhum documento padrão identificado")
    
    # Documentos faltantes
    relatorio.append(f"\n❌ DOCUMENTOS FALTANTES")
    relatorio.append("-"*60)
    if resultados["documentos_faltantes"]:
        for doc in resultados["documentos_faltantes"]:
            artigo = next(d["artigo"] for d in DOCUMENTOS_PADRAO if d["nome"] == doc)
            relatorio.append(f"▪ {doc} (Art. {artigo})")
    else:
        relatorio.append("Todos os documentos padrão foram identificados")
    
    relatorio.append("\n" + "="*60)
    relatorio.append(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    relatorio.append("Responsável Técnico: SD PM Dominique Castro")
    
    return "\n".join(relatorio)

def mostrar_visualizador(imagens_paginas: List[Image], documentos_encontrados: Dict[str, List[Dict]]):
    """Exibe visualizador de páginas com navegação"""
    st.markdown("### 📄 Visualizador de Documentos")
    
    # Criar mapeamento de páginas para documentos
    pagina_para_documento = {}
    for doc, info in documentos_encontrados.items():
        for item in info:
            pagina_para_documento[item["pagina"]] = doc
    
    # Seletor de página
    col1, col2 = st.columns([1, 3])
    with col1:
        pagina_selecionada = st.selectbox(
            "Selecione a página:",
            options=range(1, len(imagens_paginas) + 1),
            format_func=lambda x: f"Página {x}" + (f" ({pagina_para_documento[x]})" if x in pagina_para_documento else "")
        )
    
    # Mostrar imagem da página
    st.image(
        imagens_paginas[pagina_selecionada - 1],
        caption=f"Página {pagina_selecionada}" + 
               (f" - {pagina_para_documento[pagina_selecionada]}" if pagina_selecionada in pagina_para_documento else ""),
        use_column_width=True
    )

# ========== INTERFACE STREAMLIT ========== #
def main():
    # CSS Personalizado
    st.markdown("""
    <style>
        :root {
            --verde-bm: #006341;
            --dourado: #D4AF37;
        }
        .stApp {
            background-color: #F5F5F5;
        }
        .stButton>button {
            background-color: var(--verde-bm);
            color: white;
            border-radius: 8px;
        }
        .stButton>button:hover {
            background-color: #004d33;
            color: white;
        }
        .badge-legal {
            background-color: var(--dourado);
            color: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
        }
        .container-bordered {
            border: 2px solid var(--verde-bm);
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            background-color: #FFFFFF;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header institucional
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Sistema de Análise Documental - BM/RS")
        st.subheader("Seção de Afastamentos e Acidentes")
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
        st.markdown("""
        ### 📌 Responsável Técnico
        **SD PM Dominique Castro**  
        Seção de Afastamentos e Acidentes  
        *Versão 4.0 - 2024*
        """)

    # Seção de upload de documento
    with st.container():
        st.markdown('<div class="container-bordered">', unsafe_allow_html=True)
        st.subheader("📂 Documento para Análise")
        
        col1, col2 = st.columns(2)
        with col1:
            modo_rapido = st.toggle(
                "Modo rápido (análise parcial)", 
                value=True,
                help="Analisa apenas as primeiras páginas para maior velocidade"
            )
        with col2:
            st.markdown("""
            <div style="font-size: 0.9em; color: #666;">
            💡 Dica: Para documentos grandes, use o modo rápido para uma análise inicial.
            </div>
            """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Carregue o arquivo PDF do processo", 
            type=["pdf"],
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Processamento do documento
    if uploaded_file is not None:
        with st.spinner('Processando documento...'):
            processamento = processar_pdf(uploaded_file, modo_rapido)
            
            if processamento is not None:
                resultados = analisar_documentos(processamento)
                
                st.success("Análise concluída com sucesso!")
                
                # Exibição dos resultados
                tab1, tab2, tab3 = st.tabs(["📋 Relatório", "✅ Documentos Encontrados", "❌ Documentos Faltantes"])
                
                with tab1:
                    st.text_area("Relatório Completo", 
                                gerar_relatorio(resultados), 
                                height=400,
                                key="relatorio_texto")
                    
                    # Botão de download do relatório
                    st.download_button(
                        label="📥 Baixar Relatório em TXT",
                        data=gerar_relatorio(resultados),
                        file_name=f"relatorio_{resultados['metadados'].get('numero_processo', 'sem_numero')}.txt",
                        mime="text/plain"
                    )
                
                with tab2:
                    if resultados["documentos_encontrados"]:
                        progresso = len(resultados["documentos_encontrados"]) / len(DOCUMENTOS_PADRAO)
                        st.metric("Completude Documental", f"{progresso:.0%}")
                        
                        for doc, info in resultados["documentos_encontrados"].items():
                            paginas = ", ".join(str(item["pagina"]) for item in info)
                            st.markdown(f"""
                            <div style="padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;">
                            <b>{doc}</b> <span class='badge-legal'>Art. {info[0]['artigo']}</span>
                            <div style="font-size:0.9em;margin-top:5px;">Páginas: {paginas}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("Nenhum documento encontrado")
                
                with tab3:
                    if resultados["documentos_faltantes"]:
                        for doc in resultados["documentos_faltantes"]:
                            artigo = next(d["artigo"] for d in DOCUMENTOS_PADRAO if d["nome"] == doc)
                            st.markdown(f"""
                            <div style="padding:10px;margin:5px;background:#FFEBEE;border-radius:5px;">
                            ❌ <b>{doc}</b> <span class='badge-legal'>Art. {artigo}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.success("Todos os documentos foram encontrados!")

                # Visualização do documento
                with st.expander("📄 Visualizador de Documento", expanded=False):
                    mostrar_visualizador(resultados["imagens_paginas"], resultados["documentos_encontrados"])

if __name__ == "__main__":
    main()
