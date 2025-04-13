
import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io

REQUISITOS = [
    "Portaria da Sindicância Especial", "Parte de acidente",
    "Atestado de Origem", "Primeiro Boletim de atendimento médico",
    "Escala de serviço", "Ata de Habilitação para conduzir viatura",
    "Documentação operacional", "Inquérito Técnico", "CNH",
    "Formulário previsto na Portaria 095/SSP/15", "Oitiva do acidentado",
    "Oitiva das testemunhas", "Parecer do Encarregado",
    "Conclusão da Autoridade nomeante", "RHE", "LTS"
]

def processar_pdf(uploaded_file):
    imagens = convert_from_bytes(uploaded_file.read())
    encontrados = {}
    texto_por_pagina = []

    for i, imagem in enumerate(imagens):
        texto = pytesseract.image_to_string(imagem, lang='por')
        texto_por_pagina.append(texto)
        for requisito in REQUISITOS:
            if requisito.lower() in texto.lower():
                if requisito not in encontrados:
                    encontrados[requisito] = []
                encontrados[requisito].append(i + 1)

    nao_encontrados = [r for r in REQUISITOS if r not in encontrados]
    return encontrados, nao_encontrados

def gerar_relatorio_encontrados(encontrados):
    doc = Document()
    doc.add_heading('Requisitos Encontrados', level=1)
    for req, pags in encontrados.items():
        doc.add_paragraph(f'{req} - Página(s): {", ".join(map(str, pags))}')
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def gerar_relatorio_nao_encontrados(nao_encontrados):
    doc = Document()
    doc.add_heading('Requisitos Não Encontrados', level=1)
    for req in nao_encontrados:
        doc.add_paragraph(req)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="Analisador de Requisitos em PDF", page_icon="📄", layout="wide")
st.title("Analisador de Requisitos em PDF")

st.markdown("""
Esta ferramenta permite analisar documentos PDF escaneados em busca de requisitos específicos. 
Faça o upload de um arquivo PDF e obtenha relatórios dos requisitos encontrados e não encontrados.
""")

uploaded_file = st.file_uploader("Carregue o arquivo PDF", type="pdf")

if uploaded_file is not None:
    with st.spinner('Analisando o documento...'):
        encontrados, nao_encontrados = processar_pdf(uploaded_file)
        st.success('Análise concluída!')

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Requisitos Encontrados")
            if encontrados:
                for req, pags in encontrados.items():
                    st.write(f'**{req}** - Página(s): {", ".join(map(str, pags))}')
                buffer = gerar_relatorio_encontrados(encontrados)
                st.download_button(
                    label="Baixar Relatório de Requisitos Encontrados",
                    data=buffer,
                    file_name="requisitos_encontrados.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.write("Nenhum requisito encontrado.")

        with col2:
            st.subheader("Requisitos Não Encontrados")
            if nao_encontrados:
                for req in nao_encontrados:
                    st.write(f'**{req}**')
                buffer = gerar_relatorio_nao_encontrados(nao_encontrados)
                st.download_button(
                    label="Baixar Relatório de Requisitos Não Encontrados",
                    data=buffer,
                    file_name="requisitos_nao_encontrados.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.write("Todos os requisitos foram encontrados no documento.")
