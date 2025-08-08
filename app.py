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
from concurrent.futures import ThreadPoolExecutor
import hashlib

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Configuração do Tesseract (ajuste conforme necessário)
try:
    pytesseract.pytesseract.tesseract_cmd = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
    TESSERACT_CONFIG = "--oem 3 --psm 6 -l por"
except Exception as e:
    st.error(f"Erro na configuração do Tesseract: {str(e)}")
    st.stop()

# ========== LISTA DE REQUISITOS ========== #
REQUISITOS = [
    ("PORTARIA DA SINDICÂNCIA ESPECIAL", "NI 1.26 Art. 5º"),
    ("PARTE DE ACIDENTE", "Decreto 32.280 Art. 12"),
    ("ATESTADO DE ORIGEM", "NI 1.26 Anexo III"),
    ("PRIMEIRO BOLETIM MÉDICO", "RDBM Cap. VII"),
    ("ESCALA DE SERVIÇO", "Portaria 095/SSP/15"),
    ("ATA DE HABILITAÇÃO PARA CONDUZIR VIATURA", "NI 1.26 §2º Art. 8"),
    ("DOCUMENTAÇÃO OPERACIONAL", "RDBM Art. 45"),
    ("INQUÉRITO TÉCNICO", "Decreto 32.280 Art. 15"),
    ("CNH VÁLIDA", "NI 1.26 Art. 10"),
    ("FORMULÁRIO PREVISTO NA PORTARIA 095/SSP/15", ""),
    ("OUVITURA DO ACIDENTADO", "RDBM Art. 78"),
    ("OUVITURA DAS TESTEMUNHAS", "Decreto 32.280 Art. 18"),
    ("PARECER DO ENCARREGADO", "NI 1.26 Art. 12"),
    ("CONCLUSÃO DA AUTORIDADE NOMEANTE", "RDBM Art. 123"),
    ("RHE", "NI 1.26 Anexo II"),
    ("LTS", "Portaria 095/SSP/15")
]

# ========== FUNÇÕES AUXILIARES ========== #
def pagina_vazia(img, threshold=0.95):
    """Verifica se a página é predominantemente vazia"""
    try:
        img_np = np.array(img.convert('L'))
        white_pixels = np.sum(img_np > 200)
        total_pixels = img_np.size
        return (white_pixels / total_pixels) > threshold
    except Exception as e:
        st.warning(f"Erro ao verificar página vazia: {str(e)}")
        return False

def processar_imagem_ocr(img):
    """Processa imagem para OCR com tratamento de erro"""
    try:
        # Pré-processamento básico da imagem
        img = img.convert('L')  # Converte para escala de cinza
        return pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
    except Exception as e:
        st.error(f"Erro no OCR: {str(e)}")
        return ""

def extrair_texto_pdf(uploaded_file, modo_rapido=False):
    """Extrai texto do PDF com processamento paralelo"""
    try:
        dpi = 200 if modo_rapido else 300
        max_pages = 10 if modo_rapido else None
        
        # Converter PDF para imagens
        imagens = convert_from_bytes(
            uploaded_file.read(),
            dpi=dpi,
            first_page=1,
            last_page=max_pages,
            thread_count=4
        )
        
        # Processamento paralelo das páginas
        textos = []
        with st.spinner(f"Processando {len(imagens)} páginas..."):
            with ThreadPoolExecutor() as executor:
                futures = []
                for img in imagens:
                    if not pagina_vazia(img):
                        futures.append(executor.submit(processar_imagem_ocr, img))
                    else:
                        futures.append(executor.submit(lambda: ""))
                
                for i, future in enumerate(futures):
                    textos.append(future.result())
                    st.progress((i + 1) / len(imagens))
        
        return "\n\n".join(textos)
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None

def analisar_documentos(texto):
    """Analisa o texto extraído e identifica documentos"""
    texto = texto.upper()  # Padroniza para maiúsculas
    
    encontrados = {}
    for doc, artigo in REQUISITOS:
        # Verifica se o nome do documento está no texto
        if doc in texto:
            encontrados[doc] = {"artigo": artigo}
    
    nao_encontrados = [doc for doc, _ in REQUISITOS if doc not in encontrados]
    return encontrados, nao_encontrados

def gerar_relatorio(encontrados, nao_encontrados, nome_arquivo="relatorio.docx"):
    """Gera um relatório em DOCX com os resultados"""
    doc = Document()
    
    # Cabeçalho
    doc.add_heading('RELATÓRIO DE ANÁLISE DOCUMENTAL', level=1)
    doc.add_paragraph(f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Documentos encontrados
    doc.add_heading('DOCUMENTOS ENCONTRADOS', level=2)
    if encontrados:
        for doc_name, info in encontrados.items():
            doc.add_paragraph(f"✓ {doc_name} (Art. {info['artigo']})", style='List Bullet')
    else:
        doc.add_paragraph("Nenhum documento encontrado", style='List Bullet')
    
    # Documentos faltantes
    doc.add_heading('DOCUMENTOS FALTANTES', level=2)
    for doc_name in nao_encontrados:
        artigo = next(artigo for doc, artigo in REQUISITOS if doc == doc_name)
        doc.add_paragraph(f"✗ {doc_name} (Art. {artigo})", style='List Bullet')
    
    # Rodapé
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("BM/RS - Seção de Afastamentos e Acidentes")
    
    # Salvar em buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ========== INTERFACE PRINCIPAL ========== #
def main():
    st.title("🛡️ Sistema de Análise Documental - BM/RS")
    st.markdown("### Seção de Afastamentos e Acidentes")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Carregue o arquivo PDF para análise",
        type=["pdf"],
        accept_multiple_files=False
    )
    
    # Opções de processamento
    modo_rapido = st.checkbox("Modo rápido (analisa apenas as primeiras 10 páginas)", value=True)
    
    # Botão de análise
    if uploaded_file and st.button("Iniciar Análise"):
        with st.spinner("Processando documento..."):
            # Extrai texto do PDF
            texto = extrair_texto_pdf(uploaded_file, modo_rapido)
            
            if texto:
                # Analisa os documentos
                encontrados, nao_encontrados = analisar_documentos(texto)
                
                # Armazena resultados na sessão
                st.session_state.resultados = {
                    "encontrados": encontrados,
                    "nao_encontrados": nao_encontrados,
                    "texto": texto
                }
    
    # Exibição de resultados
    if 'resultados' in st.session_state:
        st.success("Análise concluída com sucesso!")
        
        # Mostrar estatísticas
        total_docs = len(REQUISITOS)
        encontrados_count = len(st.session_state.resultados["encontrados"])
        st.metric("Documentos Encontrados", f"{encontrados_count}/{total_docs}")
        
        # Abas para organização
        tab1, tab2 = st.tabs(["Documentos Encontrados", "Documentos Faltantes"])
        
        with tab1:
            if st.session_state.resultados["encontrados"]:
                for doc, info in st.session_state.resultados["encontrados"].items():
                    st.success(f"**{doc}** (Art. {info['artigo']})")
            else:
                st.warning("Nenhum documento encontrado")
        
        with tab2:
            if st.session_state.resultados["nao_encontrados"]:
                for doc in st.session_state.resultados["nao_encontrados"]:
                    artigo = next(artigo for d, artigo in REQUISITOS if d == doc)
                    st.error(f"**{doc}** (Art. {artigo})")
            else:
                st.success("Todos os documentos foram encontrados!")
        
        # Botão para download do relatório
        relatorio = gerar_relatorio(
            st.session_state.resultados["encontrados"],
            st.session_state.resultados["nao_encontrados"]
        )
        
        st.download_button(
            label="📄 Baixar Relatório Completo",
            data=relatorio,
            file_name="relatorio_analise.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

if __name__ == "__main__":
    main()
