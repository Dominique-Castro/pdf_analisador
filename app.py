import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import io
import os

# Adicionando a linha para permitir o servidor escutar em uma porta e ser acessível publicamente
if __name__ == "__main__":
    st.set_page_config(page_title="Analisador de Requisitos em PDF", layout="centered")

    st.markdown("""
        <style>
        .main {
            background-color: #f5f5f5;
        }
        .stApp {
            font-family: 'Segoe UI', sans-serif;
            color: #2c3e50;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .reportview-container .markdown-text-container {
            padding: 2rem;
            border-radius: 10px;
            background-color: #ffffff;
            box-shadow: 0px 4px 8px rgba(0,0,0,0.05);
        }
        </style>
    """, unsafe_allow_html=True)

    requisitos = [
        "Portaria da Sindicância Especial",
        "Parte de acidente",
        "Atestado de Origem",
        "Primeiro Boletim de atendimento médico",
        "Escala de serviço",
        "Ata de Habilitação para conduzir viatura",
        "Documentação operacional",
        "Inquérito Técnico",
        "CNH",
        "Formulário previsto na Portaria 095/SSP/15",
        "Oitiva do acidentado",
        "Oitiva das testemunhas",
        "Parecer do Encarregado",
        "Conclusão da Autoridade nomeante",
        "RHE",
        "LTS"
    ]

    st.title("📄 Analisador de Requisitos em PDF")
    st.markdown("Faça o upload de um arquivo PDF escaneado ou digital e veja se os requisitos estão presentes.")

    uploaded_file = st.file_uploader("Carregue o arquivo PDF", type=["pdf"])

    if uploaded_file:
        def processar_pdf(file):
            imagens = convert_from_bytes(file.read())
            encontrados = {}

            for i, imagem in enumerate(imagens):
                texto = pytesseract.image_to_string(imagem, lang='por')
                for req in requisitos:
                    if req.lower() in texto.lower() and req not in encontrados:
                        encontrados[req] = i + 1

            nao_encontrados = [r for r in requisitos if r not in encontrados]
            return encontrados, nao_encontrados

        with st.spinner("🔍 Analisando o documento com OCR..."):
            encontrados, nao_encontrados = processar_pdf(uploaded_file)

        st.success("✅ Análise concluída!")

        st.subheader("📌 Requisitos Encontrados")
        if encontrados:
            for req, pagina in encontrados.items():
                st.markdown(f"- **{req}** encontrado na página {pagina}")
        else:
            st.write("Nenhum requisito foi encontrado.")

        st.subheader("🚫 Requisitos Não Encontrados")
        if nao_encontrados:
            for req in nao_encontrados:
                st.markdown(f"- {req}")
        else:
            st.markdown("- Todos os requisitos foram encontrados.")
    else:
        st.info("⬆️ Faça upload de um arquivo PDF para iniciar a análise.")

# Adicionando a linha para iniciar o Streamlit
if __name__ == "__main__":
    
