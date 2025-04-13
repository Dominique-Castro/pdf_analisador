import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract

# Lista dos requisitos
REQUISITOS = [
    "Portaria da Sindicância Especial, fl.",
    "Parte de acidente, fl.",
    "Atestado de Origem (1ª e 2ª fase - AO)/ISO, fls.",
    "Primeiro Boletim de atendimento médico, fl.",
    "Escala de serviço, fl.",
    "Ata de Habilitação para conduzir viatura, fl.",
    "Documentação operacional, fls.",
    "Inquérito Técnico, 1º e 2º Grau, fls.",
    "CNH, fl.",
    "Formulário previsto na Portaria 095/SSP/15, fl.",
    "Oitiva do acidentado, fl.",
    "Oitiva das testemunhas, fls.",
    "Parecer do Encarregado, fls.",
    "Conclusão da Autoridade nomeante, fls.",
    "RHE, fl.",
    "LTS, (sim ou não)"
]

# Função para encontrar em quais páginas aparece cada requisito
def encontrar_paginas(texto_busca, imagens):
    paginas = []
    for i, imagem in enumerate(imagens):
        texto = pytesseract.image_to_string(imagem, lang='por')
        if texto_busca.lower() in texto.lower():
            paginas.append(i + 1)
    return paginas

# Função principal de processamento
def processar_pdf(file):
    try:
        imagens = convert_from_bytes(file.read())
    except Exception as e:
        st.error("⚠️ Erro ao converter PDF para imagem. Verifique se o arquivo está correto e tente novamente.")
        st.stop()

    texto_total = ""
    for imagem in imagens:
        texto = pytesseract.image_to_string(imagem, lang='por')
        texto_total += texto + "\n"

    encontrados = {}
    nao_encontrados = []

    for item in REQUISITOS:
        if item.lower() in texto_total.lower():
            encontrados[item] = encontrar_paginas(item, imagens)
        else:
            nao_encontrados.append(item)

    return encontrados, nao_encontrados

# ---------- INTERFACE DO USUÁRIO ----------
st.set_page_config(page_title="Analisador de PDF - Requisitos", layout="centered")
st.title("📄 Analisador de Requisitos em PDF")
st.markdown("Esta ferramenta permite analisar documentos PDF escaneados em busca de **requisitos específicos**. Faça o upload de um arquivo PDF abaixo.")

uploaded_file = st.file_uploader("📎 Carregue o arquivo PDF", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("🔍 Analisando o PDF... Aguarde..."):
        encontrados, nao_encontrados = processar_pdf(uploaded_file)

    st.success("✅ Análise concluída!")

    st.subheader("📌 Requisitos encontrados:")
    if encontrados:
        for item, paginas in encontrados.items():
            st.markdown(f"- **{item}** → páginas: {', '.join(map(str, paginas))}")
    else:
        st.info("Nenhum requisito encontrado no documento.")

    st.subheader("❌ Requisitos não encontrados:")
    if nao_encontrados:
        for item in nao_encontrados:
            st.markdown(f"- {item}")
    else:
        st.success("Todos os requisitos foram encontrados!")

else:
    st.info("Faça upload de um arquivo PDF para iniciar a análise.")
