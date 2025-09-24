import streamlit as st
import base64
import re
from datetime import datetime
from collections import defaultdict
import PyPDF2
import io

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

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
        "palavras_chave": ["portaria", "sindicância", "especial", "instauração", "acidente de serviço"]
    },
    {
        "nome": "Parte de acidente",
        "artigo": "Decreto 32.280 Art. 12",
        "padroes_texto": [
            r"PARTE\s+N[º°]\s*\d+/P1/\d{4}",
            r"ACIDENTE\s+DE\s+SERVIÇO.*?TESTEMUNHOU\s+O\s+FATO"
        ],
        "palavras_chave": ["parte", "acidente", "ocorrência", "relatório", "testemunhas"]
    },
    {
        "nome": "Termo de Oitiva do Acidentado",
        "artigo": "RDBM Art. 78",
        "padroes_texto": [
            r"TERMO\s+DE\s+OITIVA\s+DO\s+ACIDENTADO",
            r"DECLARAÇÃO\s+DO\s+MILITAR\s+ACIDENTADO"
        ],
        "palavras_chave": ["oitiva", "acidentado", "declaração", "depoimento"]
    }
]

# ========== ANÁLISE DE ACIDENTES ========== #
class AcidenteAnalyzer:
    def __init__(self, textos_paginas):
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
        date_patterns = [
            r'Data do fato:\s*(\d{2}/\d{2}/\d{4})',
            r'ocorrido em\s*(\d{2}/\d{2}/\d{4})',
            r'Data do acidente:\s*(\d{2}/\d{2}/\d{4})'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group(1)
                    self.resultados['data_acidente'] = date_str
                    self.resultados['paginas_referencia']['data_acidente'].append(page_num)
                    return

    def find_numero_proa(self):
        proa_patterns = [
            r'PROA\s*n[º°o]*\s*([\d./-]+)',
            r'Processo\s*Administrativo\s*Eletrônico\s*([\d./-]+)',
            r'24/1203-0022758-4'
        ]

        for page_num, text in self.textos_paginas:
            for pattern in proa_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    proa_num = match.group(1) if match.groups() else match.group(0)
                    self.resultados['numero_proa'] = proa_num
                    self.resultados['paginas_referencia']['numero_proa'].append(page_num)
                    return

    def analyze(self):
        self.find_data_acidente()
        self.find_numero_proa()
        return self.resultados

# ========== FUNÇÕES PRINCIPAIS ========== #
def extrair_texto_pdf(uploaded_file):
    """Extrai texto do PDF usando PyPDF2 (mais leve)"""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        textos_paginas = []
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            texto = page.extract_text()
            textos_paginas.append((page_num + 1, texto))
        
        return textos_paginas, len(pdf_reader.pages)
    except Exception as e:
        st.error(f"Erro ao ler PDF: {str(e)}")
        return [], 0

def identificar_documento(texto):
    texto_limpo = texto.upper()
    
    for documento in DOCUMENTOS_PADRAO:
        for padrao in documento["padroes_texto"]:
            if re.search(padrao, texto_limpo):
                return documento
                
        palavras_encontradas = sum(
            1 for palavra in documento["palavras_chave"] 
            if palavra.upper() in texto_limpo
        )
        
        if palavras_encontradas / len(documento["palavras_chave"]) > 0.6:
            return documento
            
    return None

def analisar_documentos(textos_paginas, total_paginas):
    documentos_encontrados = defaultdict(list)
    documentos_faltantes = [doc["nome"] for doc in DOCUMENTOS_PADRAO]
    
    for num_pagina, texto in textos_paginas:
        documento = identificar_documento(texto)
        if documento:
            documentos_encontrados[documento["nome"]].append({
                "pagina": num_pagina,
                "artigo": documento["artigo"]
            })
            
            if documento["nome"] in documentos_faltantes:
                documentos_faltantes.remove(documento["nome"])
    
    return {
        "documentos_encontrados": documentos_encontrados,
        "documentos_faltantes": documentos_faltantes,
        "total_paginas": total_paginas,
        "paginas_processadas": len(textos_paginas)
    }

def gerar_relatorio(resultados, analise_acidente):
    relatorio = []
    relatorio.append("="*60)
    relatorio.append("BRIGADA MILITAR DO RIO GRANDE DO SUL")
    relatorio.append("SISTEMA DE ANÁLISE DOCUMENTAL")
    relatorio.append("="*60)
    
    if analise_acidente['data_acidente']:
        relatorio.append(f"\n📋 INFORMAÇÕES DO ACIDENTE")
        relatorio.append("-"*60)
        relatorio.append(f"▪ Data do acidente: {analise_acidente['data_acidente']}")
        relatorio.append(f"▪ Número do PROA: {analise_acidente['numero_proa'] or 'Não identificado'}")
    
    relatorio.append(f"\n✅ DOCUMENTOS ENCONTRADOS")
    relatorio.append("-"*60)
    if resultados["documentos_encontrados"]:
        for doc, info in resultados["documentos_encontrados"].items():
            paginas = ", ".join(str(item["pagina"]) for item in info)
            relatorio.append(f"▪ {doc} (Art. {info[0]['artigo']}) - Páginas: {paginas}")
    else:
        relatorio.append("Nenhum documento padrão identificado")
    
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
    
    return "\n".join(relatorio)

# ========== INTERFACE STREAMLIT ========== #
def main():
    st.markdown("""
    <style>
    .stApp { background-color: #F5F5F5; }
    .stButton>button { 
        background-color: #006341; 
        color: white; 
        border-radius: 8px; 
    }
    .metric-card { 
        background: white; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 4px solid #006341;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🛡️ Sistema de Análise Documental - BM/RS")
    st.subheader("Seção de Afastamentos e Acidentes")

    with st.sidebar:
        st.info("""
        **📌 Responsável Técnico**  
        SD PM Dominique Castro  
        *Versão 4.0 - 2024*
        """)

    uploaded_file = st.file_uploader("Carregue o arquivo PDF do processo", type=["pdf"])
    
    if uploaded_file is not None:
        if st.button("🔍 Iniciar Análise", type="primary"):
            with st.spinner('Processando documento...'):
                # Extrai texto do PDF
                textos_paginas, total_paginas = extrair_texto_pdf(uploaded_file)
                
                if textos_paginas:
                    # Análise de acidente
                    analyzer = AcidenteAnalyzer(textos_paginas)
                    analise_acidente = analyzer.analyze()
                    
                    # Análise de documentos
                    resultados = analisar_documentos(textos_paginas, total_paginas)
                    
                    st.success("✅ Análise concluída com sucesso!")
                    
                    # Métricas principais
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Data do Acidente", 
                                 analise_acidente['data_acidente'] or "Não encontrada",
                                 help=f"Páginas: {', '.join(map(str, analise_acidente['paginas_referencia']['data_acidente']))}")
                    
                    with col2:
                        st.metric("Número do PROA", 
                                 analise_acidente['numero_proa'] or "Não encontrado",
                                 help=f"Páginas: {', '.join(map(str, analise_acidente['paginas_referencia']['numero_proa']))}")
                    
                    with col3:
                        st.metric("Documentos Encontrados", 
                                 f"{len(resultados['documentos_encontrados'])}/{len(DOCUMENTOS_PADRAO)}")
                    
                    # Abas de resultados
                    tab1, tab2 = st.tabs(["📋 Relatório Completo", "📄 Visualização de Páginas"])
                    
                    with tab1:
                        relatorio = gerar_relatorio(resultados, analise_acidente)
                        st.text_area("Relatório de Análise", relatorio, height=400)
                        
                        st.download_button(
                            label="📥 Baixar Relatório",
                            data=relatorio,
                            file_name=f"relatorio_acidente_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                            mime="text/plain"
                        )
                    
                    with tab2:
                        st.subheader("Visualização por Página")
                        pagina_selecionada = st.selectbox(
                            "Selecione a página:",
                            options=range(1, len(textos_paginas) + 1),
                            format_func=lambda x: f"Página {x}"
                        )
                        
                        if pagina_selecionada <= len(textos_paginas):
                            texto_pagina = textos_paginas[pagina_selecionada - 1][1]
                            st.text_area(f"Texto da Página {pagina_selecionada}", 
                                       texto_pagina[:2000] + "..." if len(texto_pagina) > 2000 else texto_pagina, 
                                       height=200)
                else:
                    st.error("Não foi possível extrair texto do PDF. Verifique se o arquivo é válido.")

if __name__ == "__main__":
    main()
