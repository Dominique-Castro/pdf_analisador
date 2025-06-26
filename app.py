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
import json

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
    # ... (seus modelos de documentos aqui)
]

# ========== NOVAS FUNÇÕES PARA ANÁLISE DE ACIDENTES ========== #
class AcidenteAnalyzer:
    # ... (mantenha a classe AcidenteAnalyzer como estava)

# ========== FUNÇÕES AUXILIARES ========== #
def limpar_texto(texto: str) -> str:
    # ... (mantenha a função limpar_texto como estava)

def pagina_vazia(img, threshold: float = 0.95) -> bool:
    # ... (mantenha a função pagina_vazia como estava)

def preprocess_image(img):
    # ... (mantenha a função preprocess_image como estava)

# ========== FUNÇÕES PRINCIPAIS ========== #
@st.cache_data(show_spinner=False)
def processar_pdf(uploaded_file, modo_rapido: bool = False) -> Dict[str, any]:
    # ... (mantenha a função processar_pdf como estava)

def extrair_metadados(texto: str) -> Dict[str, any]:
    # ... (mantenha a função extrair_metadados como estava)

def identificar_documento(texto: str) -> Optional[Dict[str, str]]:
    # ... (mantenha a função identificar_documento como estava)

def analisar_documentos(resultados_processamento: Dict[str, any]) -> Dict[str, any]:
    # ... (mantenha a função analisar_documentos como estava)

def gerar_relatorio(resultados: Dict[str, any]) -> str:
    # ... (mantenha a função gerar_relatorio como estava)

def mostrar_visualizador(imagens_paginas: List[Image], documentos_encontrados: Dict[str, List[Dict]]):
    # ... (mantenha a função mostrar_visualizador como estava)

# ========== INTERFACE STREAMLIT ========== #
def main():
    # CSS Personalizado
    st.markdown("""
    <style>
        /* ... (mantenha seu CSS personalizado) */
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

    # Seção de upload de documento - MOVIDA PARA DENTRO DA FUNÇÃO MAIN
    uploaded_file = None  # Inicializa a variável
    
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

    # Processamento do documento - AGORA DENTRO DO ESCOPO CORRETO
    if uploaded_file is not None:
        with st.spinner('Processando documento...'):
            processamento = processar_pdf(uploaded_file, modo_rapido)
            
            if processamento is not None:
                resultados = analisar_documentos(processamento)
                
                st.success("Análise concluída com sucesso!")
                
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📋 Relatório", 
                    "✅ Documentos Encontrados", 
                    "❌ Documentos Faltantes",
                    "🔍 Análise de Acidente"
                ])
                
                with tab1:
                    st.text_area("Relatório Completo", 
                                gerar_relatorio(resultados), 
                                height=400,
                                key="relatorio_texto")
                    
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

                with tab4:
                    st.subheader("Informações Específicas do Acidente")
                    
                    if processamento["analise_acidente"]:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric(
                                "Data do Acidente", 
                                processamento["analise_acidente"]["data_acidente"] or "Não encontrada",
                                help=f"Páginas de referência: {', '.join(map(str, processamento['analise_acidente']['paginas_referencia']['data_acidente'])) or 'Nenhuma'}"
                            )
                        
                        with col2:
                            st.metric(
                                "Número do PROA", 
                                processamento["analise_acidente"]["numero_proa"] or "Não encontrado",
                                help=f"Páginas de referência: {', '.join(map(str, processamento['analise_acidente']['paginas_referencia']['numero_proa'])) or 'Nenhuma'}"
                            )
                        
                        st.json(processamento["analise_acidente"], expanded=False)
                    else:
                        st.warning("Nenhuma informação específica de acidente encontrada")

                with st.expander("📄 Visualizador de Documento", expanded=False):
                    mostrar_visualizador(resultados["imagens_paginas"], resultados["documentos_encontrados"])

if __name__ == "__main__":
    main()
