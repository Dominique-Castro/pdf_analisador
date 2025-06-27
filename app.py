import dash
from dash import dcc, html, Input, Output, State, dash_table, callback
import base64
import os
from processors.pdf_processor import process_pdf
from processors.pattern_matcher import identificar_documentos
from flask_caching import Cache
import logging

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
        html.Img(src="/assets/logo.png", height=80),
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
    
    # Barra de Progresso
    dcc.Loading(
        id="loading-progress",
        children=[html.Div(id="progress-status")],
        type="circle"
    ),
    
    # Resultados
    html.Div(id='output-analysis', className="results-container")
], className="main-container")

# Callback para Processamento
@app.callback(
    Output('output-analysis', 'children'),
    Input('upload-data', 'contents'),
    prevent_initial_call=True
)
@cache.memoize(timeout=300)  # Cache de 5 minutos
def update_output(contents):
    if not contents:
        return html.Div("Nenhum arquivo carregado")
    
    try:
        _, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Processamento do PDF (sua lógica original adaptada)
        resultados = process_pdf(decoded)
        
        # Geração da Saída
        return html.Div([
            # Abas de Resultados
            dcc.Tabs([
                # Relatório Completo
                dcc.Tab(label="📋 Relatório", children=[
                    html.H3("Texto Extraído"),
                    html.Pre(resultados['texto'][:5000] + "..." if len(resultados['texto']) > 5000 else resultados['texto']),
                    
                    html.H3("Documentos Identificados"),
                    dash_table.DataTable(
                        data=resultados['documentos'],
                        columns=[{"name": "Tipo", "id": "tipo"}, {"name": "Páginas", "id": "paginas"}],
                        style_table={'overflowX': 'auto'}
                    )
                ]),
                
                # Análise de Acidente
                dcc.Tab(label="🔍 Acidente", children=[
                    html.Div([
                        html.H4("Dados do Acidente"),
                        html.P(f"Data: {resultados['data_acidente'] or 'Não encontrada'}"),
                        html.P(f"PROA: {resultados['numero_proa'] or 'Não encontrado'}"),
                        html.Hr(),
                        html.H4("Páginas de Referência"),
                        html.Ul([html.Li(f"Página {pg}") for pg in resultados['paginas_referencia']])
                    ], className="accident-info")
                ])
            ])
        ])
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        return html.Div(f"Erro na análise: {str(e)}", className="error-message")

if __name__ == '__main__':
    app.run_server(debug=True)
