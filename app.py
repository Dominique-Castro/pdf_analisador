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
import hashlib
import json
from collections import Counter

# ========== VERIFICAÇÃO DE DEPENDÊNCIAS ========== #
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    st.error("""
    ❌ Scikit-learn não está instalado. Algumas funcionalidades avançadas estarão limitadas.
    Adicione 'scikit-learn' ao seu arquivo requirements.txt
    """)

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
    nltk.download('stopwords')
    nltk.download('punkt')
except ImportError:
    NLTK_AVAILABLE = False
    st.error("""
    ❌ NLTK não está instalado. Algumas funcionalidades de processamento de texto estarão limitadas.
    Adicione 'nltk' ao seu arquivo requirements.txt
    """)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    st.warning("""
    ⚠️ OpenCV não está instalado. Algumas otimizações de imagem estarão desativadas.
    Adicione 'opencv-python-headless' ao seu arquivo requirements.txt
    """)

# ========== CONFIGURAÇÃO INICIAL ========== #
st.set_page_config(
    page_title="Sistema de Análise Documental - BM/RS",
    page_icon="🛡️",
    layout="wide"
)

# Configuração do Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    TESSERACT_CONFIG = "--oem 1 --psm 6"
except Exception as e:
    st.error(f"Erro na configuração do Tesseract: {str(e)}")
    TESSERACT_CONFIG = ""

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== MODELO DE DOCUMENTO (COM FALLBACK) ========== #
class DocumentModel:
    def __init__(self, nome, artigo, keywords=None, model_text=None, min_similarity=0.7):
        self.nome = nome
        self.artigo = artigo
        self.keywords = keywords or []
        self.model_text = model_text or ""
        self.min_similarity = min_similarity
        
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='portuguese')
        else:
            self.vectorizer = None
    
    def train(self, text_samples):
        """Treina o modelo com amostras de texto"""
        if not isinstance(text_samples, list):
            text_samples = [text_samples]
        self.model_text = "\n".join(text_samples)
        self.keywords = self._extract_keywords(text_samples)
        
    def _extract_keywords(self, texts):
        """Extrai palavras-chave importantes com fallback"""
        if not NLTK_AVAILABLE:
            # Fallback simples sem NLTK
            words = []
            for text in texts:
                words += [word.lower() for word in re.findall(r'\b\w{4,}\b', text)]
            word_counts = Counter(words)
            return [word for word, count in word_counts.most_common(10)]
        
        # Versão com NLTK
        stop_words = set(stopwords.words('portuguese'))
        words = []
        for text in texts:
            tokens = word_tokenize(text.lower())
            words += [word for word in tokens if word.isalpha() and word not in stop_words]
        word_counts = Counter(words)
        return [word for word, count in word_counts.most_common(20)]
    
    def match(self, text):
        """Verifica se o texto corresponde a este modelo de documento"""
        text_lower = text.lower()
        
        # Verificação por palavras-chave
        keyword_matches = sum(1 for kw in self.keywords if kw.lower() in text_lower)
        keyword_score = keyword_matches / len(self.keywords) if self.keywords else 0
        
        # Verificação por similaridade (se sklearn estiver disponível)
        similarity = 0
        if SKLEARN_AVAILABLE and self.vectorizer and self.model_text:
            try:
                vectors = self.vectorizer.fit_transform([self.model_text, text])
                similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            except:
                similarity = 0
        
        # Combina os scores (ajusta pesos conforme disponibilidade de sklearn)
        if SKLEARN_AVAILABLE:
            combined_score = (keyword_score * 0.6) + (similarity * 0.4)
        else:
            combined_score = keyword_score  # Usa apenas palavras-chave se sklearn não estiver disponível
            
        return combined_score >= self.min_similarity

# ========== LISTA DE REQUISITOS ========== #
REQUISITOS = [
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

# ... (o restante do código permanece igual, incluindo as funções auxiliares, interface e processamento)

# ========== ATUALIZAÇÃO DO REQUIREMENTS.TXT ========== #
# Adicione estas linhas ao seu arquivo requirements.txt:
"""
scikit-learn>=1.0.2
nltk>=3.7
opencv-python-headless>=4.6.0
pdf2image>=1.16.3
pytesseract>=0.3.10
python-docx>=0.8.11
streamlit>=1.12.0
numpy>=1.22.0
Pillow>=9.0.0
"""
