# Analisador de Requisitos em PDF

Este é um aplicativo web que permite analisar documentos PDF escaneados em busca de requisitos específicos de Acidentes de Serviço BM.

## 🔍 Funcionalidades

- **Upload de PDFs escaneados**
- **Reconhecimento de texto com OCR (Tesseract)**
- **Identificação de documentos por palavras-chave**, como:
  - Formulário previsto na Portaria 095/SSP/15
  - Atestado de Origem
  - Oitiva das testemunhas
  - Documentação operacional
  - CNH, RHE, LTS, entre outros
- **Referência da página onde o documento foi encontrado**
- **Geração de relatórios em `.docx`**
- **Pré-visualização do PDF no navegador**

## ⚙️ Requisitos

- Python 3.7 ou superior
- Tesseract OCR (com idioma português)
- Poppler (para conversão de PDF em imagem)

## 📦 Instalação

Clone o repositório e instale as dependências:

```bash
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
pip install -r requirements.txt
