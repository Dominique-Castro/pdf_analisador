import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io
from datetime import datetime, timedelta
import base64
import logging
import re
import time
import hashlib
import os
from dotenv import load_dotenv

# --- Configuração Inicial ---
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bmrs_auditoria.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Constantes Institucionais ---
class LegislacaoBMRS:
    """Encapsula todas as normas institucionais aplicáveis"""
    
    DOCUMENTOS_ACIDENTE = [
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

    PRAZOS = {
        "protocolo": timedelta(days=30),
        "recurso": timedelta(days=10),
        "prescricao": timedelta(days=365*2)
    }

    @staticmethod
    def validar_assinaturas(texto):
        """Verifica assinaturas obrigatórias conforme hierarquia"""
        cargos = [
            "Comandante de Unidade",
            "Chefe de Seção",
            "Autoridade Nomeante"
        ]
        return any(cargo in texto for cargo in cargos)

# --- Autenticação ---
def autenticar_usuario():
    """Sistema de autenticação para militares da BM/RS"""
    if st.session_state.get("autenticado"):
        return True

    with st.sidebar:
        with st.expander("🔐 Autenticação BM/RS", expanded=True):
            with st.form("login_form"):
                matricula = st.text_input("Matrícula", max_chars=8).strip()
                ident_func = st.text_input("Identificação Funcional", type="password")
                
                if st.form_submit_button("Acessar"):
                    if validar_credenciais(matricula, ident_func):
                        st.session_state.autenticado = True
                        st.session_state.matricula = matricula
                        st.rerun()
                    else:
                        st.error("Credenciais inválidas - Acesso restrito")
    return False

def validar_credenciais(matricula, ident_func):
    """Validação de credenciais (em produção usar sistema oficial)"""
    salt = os.getenv("SALT", "default_salt_bmrs")
    hash_valido = hashlib.sha256(f"BMRS@{matricula}@{salt}".encode()).hexdigest()
    return ident_func == hash_valido[:8]

# --- Processamento de Documentos ---
class ProcessadorDocumentos:
    def __init__(self):
        self.legislacao = LegislacaoBMRS()

    def extrair_metadados(self, texto):
        """Extrai metadados críticos conforme padrões institucionais"""
        padroes = {
            "processo": [
                (r"\d{4}\.\d{4}\.\d{4}-\d", "Padrão BM/RS NI 1.26"),
                (r"PA[EA]?-\d{4}/\d{4}", "Formato Processo Administrativo")
            ],
            "data_acidente": [
                (r"(?i)(data\s*do\s*acidente|ocorrido\s*em)\s*:\s*(\d{2}/\d{2}/\d{4})", "Data formal"),
                (r"\b(\d{2}/\d{2}/\d{4}).*?(acidente|sinistro)", "Data contextual")
            ]
        }
        
        resultados = {}
        for campo, padroes_list in padroes.items():
            for padrao, descricao in padroes_list:
                match = re.search(padrao, texto, re.IGNORECASE)
                if match:
                    resultados[campo] = {
                        "valor": match.group(1) if len(match.groups()) >= 1 else match.group(0),
                        "fonte": descricao
                    }
                    break
        return resultados

    def verificar_conformidade(self, texto):
        """Avalia conformidade com os normativos"""
        inconformidades = []
        
        # Validação específica para CNH
        if "CNH" in texto and "válida" not in texto.lower():
            inconformidades.append(("CNH não consta como válida", "NI 1.26 Art. 10"))
            
        # Validação de assinaturas hierárquicas
        if not self.legislacao.validar_assinaturas(texto):
            inconformidades.append(("Assinaturas hierárquicas ausentes", "RDBM Art. 45"))
            
        return inconformidades

    def processar_pdf(self, arquivo):
        """Processa PDF conforme requisitos técnicos da BM/RS"""
        try:
            imagens = convert_from_bytes(
                arquivo.read(),
                dpi=300,
                thread_count=4,
                fmt='jpeg',
                poppler_path="/usr/bin/poppler"  # Ajuste conforme necessário
            )
            
            resultados = {
                "documentos": {},
                "inconformidades": [],
                "metadados": {},
                "texto_completo": "",
                "prazos": {}
            }

            for i, img in enumerate(imagens):
                texto = pytesseract.image_to_string(img, lang='por')
                resultados["texto_completo"] += f"\n--- Página {i+1} ---\n{texto}"
                
                # Verificação de documentos obrigatórios
                for doc, artigo in self.legislacao.DOCUMENTOS_ACIDENTE:
                    if doc.lower() in texto.lower():
                        if doc not in resultados["documentos"]:
                            resultados["documentos"][doc] = {
                                "paginas": [],
                                "artigo": artigo
                            }
                        resultados["documentos"][doc]["paginas"].append(i+1)
                
                # Verificação de inconformidades
                for inconformidade, artigo in self.verificar_conformidade(texto):
                    resultados["inconformidades"].append({
                        "descricao": inconformidade,
                        "artigo": artigo
                    })

            # Extração de metadados
            resultados["metadados"] = self.extrair_metadados(resultados["texto_completo"])
            
            # Verificação de prazos (se data disponível)
            if "data_acidente" in resultados["metadados"]:
                try:
                    data_acidente = datetime.strptime(
                        resultados["metadados"]["data_acidente"]["valor"],
                        "%d/%m/%Y"
                    ).date()
                    hoje = datetime.now().date()
                    
                    resultados["prazos"] = {
                        "protocolo": {
                            "limite": data_acidente + self.legislacao.PRAZOS["protocolo"],
                            "status": "Dentro do prazo" if hoje <= data_acidente + self.legislacao.PRAZOS["protocolo"] else "Excedido"
                        }
                    }
                except ValueError:
                    logger.warning("Formato de data inválido para cálculo de prazos")

            return resultados
            
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}", exc_info=True)
            raise

# --- Interface Gráfica ---
def configurar_pagina():
    """Configuração visual da aplicação"""
    st.set_page_config(
        page_title="SAA BM/RS - Conforme NI 1.26/2023",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
        :root {
            --verde-bm: #006341;
            --dourado: #D4AF37;
            --branco: #FFFFFF;
        }
        .stApp {
            background-color: #F5F5DC;
        }
        .st-emotion-cache-1q7spjk {
            border: 2px solid var(--verde-bm);
            border-radius: 10px;
        }
        .stButton>button {
            background-color: var(--verde-bm);
            color: var(--branco);
        }
        [data-testid="stSidebar"] {
            background-color: var(--verde-bm);
            color: var(--branco);
        }
        .badge-legal {
            background-color: var(--dourado);
            color: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
        }
    </style>
    """, unsafe_allow_html=True)

def mostrar_cabecalho():
    """Cabeçalho institucional"""
    col1, col2 = st.columns([4,1])
    with col1:
        st.title("Sistema de Análise Documental")
        st.subheader("Seção de Afastamentos e Acidentes - BM/RS")
    with col2:
        st.image("https://i.imgur.com/By8hwnl.jpeg", width=120)

def mostrar_sidebar():
    """Barra lateral com informações institucionais"""
    with st.sidebar:
        st.image("https://i.imgur.com/By8hwnl.jpeg", use_column_width=True)
        st.markdown("""
        ### 🔍 Normativos de Referência
        - **Decreto nº 32.280/1986**
        - **NI EMBM 1.26/2023**
        - **Regulamento Disciplinar (RDBM)**
        """)
        st.markdown("---")
        st.markdown(f"""
        ### 📌 Responsável Técnico
        **SD BM Dominique Castro**  
        Seção de Afastamentos e Acidentes  
        *Versão 2.0 - {datetime.now().year}*
        """)

def criar_relatorio(resultados):
    """Gera relatório em DOCX conforme padrão BM/RS"""
    doc = Document()
    
    # Cabeçalho institucional
    header = doc.add_paragraph()
    header_run = header.add_run("BRIGADA MILITAR DO RIO GRANDE DO SUL\n")
    header_run.bold = True
    header_run.font.size = 14
    
    doc.add_paragraph("Seção de Afastamentos e Acidentes", style='Intense Quote')
    
    # Metadados
    info_table = doc.add_table(rows=1, cols=2)
    info_cells = info_table.rows[0].cells
    info_cells[0].text = f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    if "processo" in resultados["metadados"]:
        info_cells[1].text = f"Processo: {resultados['metadados']['processo']['valor']}"
    
    if "data_acidente" in resultados["metadados"]:
        doc.add_paragraph(f"Data do acidente: {resultados['metadados']['data_acidente']['valor']}")
    
    # Resultados da análise
    doc.add_heading('Resultado da Análise Documental', level=1)
    
    # Documentos encontrados
    doc.add_heading('Documentos Encontrados', level=2)
    if resultados["documentos"]:
        for doc_name, info in resultados["documentos"].items():
            doc.add_paragraph(
                f'✅ {doc_name} (Art. {info["artigo"]}) - Págs: {", ".join(map(str, info["paginas"]))}',
                style='List Bullet'
            )
    else:
        doc.add_paragraph("Nenhum documento requerido foi encontrado.", style='List Bullet')
    
    # Inconformidades
    doc.add_heading('Inconformidades Identificadas', level=2)
    if resultados["inconformidades"]:
        for item in resultados["inconformidades"]:
            doc.add_paragraph(
                f'❌ {item["descricao"]} (Art. {item["artigo"]})',
                style='List Bullet'
            )
    else:
        doc.add_paragraph("Nenhuma inconformidade identificada", style='List Bullet')
    
    # Prazos
    if resultados["prazos"]:
        doc.add_heading('Situação dos Prazos', level=2)
        for prazo, info in resultados["prazos"].items():
            doc.add_paragraph(
                f'• {prazo.capitalize()}: {info["status"]} (Limite: {info["limite"].strftime("%d/%m/%Y")})',
                style='List Bullet'
            )
    
    # Rodapé
    doc.add_page_break()
    doc.add_paragraph("_________________________________________")
    doc.add_paragraph("Responsável Técnico:")
    doc.add_paragraph("SD BM Dominique Castro")
    doc.add_paragraph("Seção de Afastamentos e Acidentes")
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- Fluxo Principal ---
def main():
    configurar_pagina()
    
    if not autenticar_usuario():
        return

    mostrar_cabecalho()
    mostrar_sidebar()

    # Formulário principal
    with st.form("form_analise"):
        col1, col2 = st.columns(2)
        with col1:
            numero_processo = st.text_input(
                "Número do Processo",
                placeholder="Ex: 2023.1234.5678-9",
                help="Formato exigido pelo NI 1.26 Art. 7º"
            )
        with col2:
            data_acidente = st.date_input(
                "Data do Acidente",
                format="DD/MM/YYYY",
                help="Data do evento conforme Parte de Acidente"
            )
        
        arquivo = st.file_uploader(
            "Documento Principal (PDF)",
            type=["pdf"],
            accept_multiple_files=False,
            help="Tamanho máximo: 50MB"
        )
        
        if st.form_submit_button("Analisar Documento"):
            if arquivo is not None:
                try:
                    processador = ProcessadorDocumentos()
                    with st.spinner("Processando conforme normativos BM/RS..."):
                        resultados = processador.processar_pdf(arquivo)
                        st.session_state.resultados = resultados
                        st.success("Análise concluída com conformidade legal")
                except Exception as e:
                    st.error(f"Falha na análise: {str(e)}")
                    logger.error(f"Erro no processamento: {str(e)}", exc_info=True)

    # Exibição de resultados
    if "resultados" in st.session_state:
        # Metadados extraídos
        with st.expander("📌 Metadados Identificados", expanded=False):
            if st.session_state.resultados["metadados"]:
                cols = st.columns(3)
                for i, (campo, info) in enumerate(st.session_state.resultados["metadados"].items()):
                    cols[i%3].metric(
                        label=campo.replace("_", " ").title(),
                        value=info["valor"],
                        help=f"Fonte: {info['fonte']}"
                    )
            else:
                st.warning("Nenhum metadado identificado")

        # Abas de resultados
        tab1, tab2, tab3 = st.tabs(["📋 Documentos", "⚠️ Inconformidades", "⏱ Prazos"])
        
        with tab1:
            st.subheader("Conformidade Documental")
            progresso = len(st.session_state.resultados["documentos"])/len(LegislacaoBMRS.DOCUMENTOS_ACIDENTE)
            st.metric(
                "Completude Documental",
                value=f"{progresso:.0%}",
                help=f"{len(st.session_state.resultados['documentos'])} de {len(LegislacaoBMRS.DOCUMENTOS_ACIDENTE)} documentos"
            )
            
            for doc_name, info in st.session_state.resultados["documentos"].items():
                st.markdown(f"""
                <div style='padding:10px;margin:5px;background:#E8F5E9;border-radius:5px;border-left:4px solid #006341;'>
                ✅ <b>{doc_name}</b> <span class='badge-legal'>Art. {info['artigo']}</span><br>
                📄 Páginas: {', '.join(map(str, info['paginas']))}
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            st.subheader("Não Conformidades")
            if st.session_state.resultados["inconformidades"]:
                for item in st.session_state.resultados["inconformidades"]:
                    st.markdown(f"""
                    <div style='padding:10px;margin:5px;background:#FFEBEE;border-radius:5px;border-left:4px solid #C62828;'>
                    ❌ {item['descricao']} <span class='badge-legal'>Art. {item['artigo']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("Documento conforme aos normativos institucionais")

        with tab3:
            st.subheader("Situação dos Prazos")
            if st.session_state.resultados["prazos"]:
                for prazo, info in st.session_state.resultados["prazos"].items():
                    status_color = "#4CAF50" if info["status"] == "Dentro do prazo" else "#F44336"
                    st.metric(
                        label=f"Prazo para {prazo}",
                        value=info["status"],
                        delta=info["limite"].strftime("%d/%m/%Y"),
                        delta_color="normal",
                        help=f"Limite: {info['limite'].strftime('%d/%m/%Y')}"
                    )
            else:
                st.warning("Não foi possível verificar prazos (data do acidente não identificada)")

        # Visualização do documento
        with st.expander("📄 Visualizar Documento Original", expanded=False):
            try:
                arquivo.seek(0)
                pdf_bytes = arquivo.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f"""
                <div style="border:1px solid #D4AF37;border-radius:8px;padding:10px;">
                    <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>
                </div>
                """
                st.markdown(pdf_display, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Erro ao exibir PDF: {str(e)}")

        # Download do relatório
        st.download_button(
            label="📄 Baixar Relatório Completo (DOCX)",
            data=criar_relatorio(st.session_state.resultados),
            file_name=f"relatorio_bmrs_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

if __name__ == "__main__":
    main()
