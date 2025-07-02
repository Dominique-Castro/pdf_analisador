import dash
from dash import dcc, html, Input, Output, dash_table
import base64
import logging
from flask_caching import Cache
from processors.pdf_processor import process_pdf  # Import corrigido
from processors.pattern_matcher import identificar_documentos  # Import corrigido

# Configuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = dash.Dash(__name__, assets_folder="assets")
app.title = "Analisador Documental - BM/RS"
cache = Cache(app.server, config={'CACHE_TYPE': 'SimpleCache'})

# Layout da Interface
app.layout = html.Div([
    # Cabeçalho
    html.Div([
        html.Img(src="/assets/logo.jpg", width=120),  # Caminho corrigido
        html.H1("Sistema de Análise Documental", className="header-title"),
        html.P("Seção de Afastamentos e Acidentes", className="header-subtitle")
    ], className="header"),
    
    # Upload de Arquivo
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Arraste o PDF ou ',
            html.A('Selecione o Arquivo')
        ]),
        multiple=False,
        className="upload-area"
    ),
    
    # Resultados
    html.Div(id='output-analysis', className="results-container")
])

# Callback para Processamento
@app.callback(
    Output('output-analysis', 'children'),
    Input('upload-data', 'contents'),
    prevent_initial_call=True
)
@cache.memoize(timeout=300)
def update_output(contents):
    if not contents:
        return html.Div("Nenhum arquivo carregado")
    
    try:
        _, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        resultados = process_pdf(decoded)
        
        return html.Div([
            dcc.Tabs([
                dcc.Tab(label="📋 Relatório", children=[
                    html.H3("Documentos Identificados"),
                    dash_table.DataTable(
                        data=[{"Tipo": k, "Páginas": ", ".join(map(str, v))} 
                             for k, v in resultados['documentos'].items()],
                        columns=[{"name": "Tipo", "id": "Tipo"}, 
                                {"name": "Páginas", "id": "Páginas"}]
                    )
                ]),
                dcc.Tab(label="🔍 Acidente", children=[
                    html.Div([
                        html.H4("Dados do Acidente"),
                        html.P(f"Data: {resultados.get('data_acidente', 'Não encontrada')}"),
                        html.P(f"PROA: {resultados.get('numero_proa', 'Não encontrado')}")
                    ])
                ])
            ])
        ])
        
    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return html.Div(f"Erro na análise: {str(e)}")

if __name__ == '__main__':
    app.run_server(debug=True)
