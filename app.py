import pytesseract
from pdf2image import convert_from_bytes
import pdfplumber
import io

# Função para verificar se o PDF contém texto ou imagem
def processar_pdf(uploaded_file):
    pdf_content = []
    # Lê o arquivo PDF
    with pdfplumber.open(uploaded_file) as pdf:
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            # Tenta extrair texto diretamente da página
            texto = page.extract_text()
            if texto:  # Se a página contiver texto
                pdf_content.append({'tipo': 'texto', 'pagina': i + 1, 'conteudo': texto})
            else:  # Se não houver texto, converte a página em imagem
                imagem = convert_from_bytes(uploaded_file.read(), first_page=i+1, last_page=i+1)[0]
                texto_imagem = pytesseract.image_to_string(imagem, lang='por')
                pdf_content.append({'tipo': 'imagem', 'pagina': i + 1, 'conteudo': texto_imagem})

    return pdf_content

# Função para buscar requisitos
def buscar_requisitos(pdf_content, requisitos):
    encontrados = []
    nao_encontrados = []

    for item in requisitos:
        encontrado = False
        for pagina in pdf_content:
            if item.lower() in pagina['conteudo'].lower():  # Busca o requisito no conteúdo
                encontrados.append({'requisito': item, 'pagina': pagina['pagina']})
                encontrado = True
                break
        if not encontrado:
            nao_encontrados.append(item)

    return encontrados, nao_encontrados

# Requisitos a serem buscados
requisitos = [
    'Portaria da Sindicância Especial',
    'Parte de acidente',
    'Atestado de Origem',
    'Primeiro Boletim de atendimento médico',
    'Escala de serviço',
    'Ata de Habilitação para conduzir viatura',
    'Documentação operacional',
    'Inquérito Técnico',
    'CNH',
    'Formulário previsto na Portaria 095/SSP/15',
    'Oitiva do acidentado',
    'Oitiva das testemunhas',
    'Parecer do Encarregado',
    'Conclusão da Autoridade nomeante',
    'RHE',
    'LTS'
]

# Teste da função com um arquivo PDF
uploaded_file = 'seu_arquivo.pdf'  # Substitua com o caminho do seu PDF

# Processar o arquivo
pdf_content = processar_pdf(uploaded_file)
# Buscar os requisitos
encontrados, nao_encontrados = buscar_requisitos(pdf_content, requisitos)

# Exibir os resultados
print("Requisitos encontrados:")
for item in encontrados:
    print(f"- {item['requisito']} (Página {item['pagina']})")

print("\nRequisitos não encontrados:")
for item in nao_encontrados:
    print(f"- {item}")
