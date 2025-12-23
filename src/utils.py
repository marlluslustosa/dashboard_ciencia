import unicodedata
import pandas as pd

def normalizar_texto(texto):
    """Remove acentos, coloca em minúsculas e padroniza espaços."""
    if not isinstance(texto, str):
        return str(texto)
    texto_sem_acento = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto_sem_acento.replace("_", " ").strip().lower()

def limpar_issn(valor):
    """Remove traços, pontos e espaços do ISSN para comparação segura."""
    if pd.isna(valor):
        return ""
    return str(valor).replace("-", "").replace(".", "").strip().upper()
