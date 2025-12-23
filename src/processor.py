import pandas as pd
import zipfile
import os
from io import StringIO
import streamlit as st
from .utils import limpar_issn

@st.cache_data
def processar_zip_com_filtro(uploaded_zip, df_ref_qualis):
    dfs = []
    log_buffer = StringIO()
    
    log_buffer.write("RELATÓRIO DE PUBLICAÇÕES EXCLUÍDAS (FILTRO QUALIS)\n")
    log_buffer.write("===================================================\n\n")

    # 1. Preparar Lista de ISSNs Válidos
    valid_issns = set()
    try:
        df_ref_qualis.columns = [c.lower().strip() for c in df_ref_qualis.columns]
        if 'issn' in df_ref_qualis.columns:
            valid_issns = set(df_ref_qualis['issn'].apply(limpar_issn))
        else:
            return None, ["Erro: Coluna 'issn' não encontrada no arquivo Qualis."]
    except Exception as e:
        return None, [f"Erro ao processar arquivo Qualis: {e}"]

    # 2. Processar ZIP
    with zipfile.ZipFile(uploaded_zip) as z:
        for arquivo in z.namelist():
            if arquivo.lower().endswith(".csv") and not arquivo.startswith("__MACOSX"):
                try:
                    with z.open(arquivo) as f:
                        df = pd.read_csv(f, on_bad_lines='skip', engine='python')
                        
                        nome_limpo = os.path.basename(arquivo)
                        nome_arquivo_cru = os.path.splitext(nome_limpo)[0].replace("_", " ")
                        df["pesquisador"] = nome_arquivo_cru
                        
                        col_issn = None
                        for col in df.columns:
                            if "issn" in col.lower():
                                col_issn = col
                                break
                        
                        if col_issn:
                            df["issn_temp"] = df[col_issn].apply(limpar_issn)
                            mask_validos = df["issn_temp"].isin(valid_issns)
                            
                            df_excluidos = df[~mask_validos]
                            if not df_excluidos.empty:
                                log_buffer.write(f"PESQUISADOR: {nome_arquivo_cru}\n")
                                for idx, row in df_excluidos.iterrows():
                                    titulo = row.get('titulo', 'Título não identificado')
                                    issn_orig = row.get(col_issn, 'S/N')
                                    qualis_orig = row.get('qualis', 'N/A')
                                    log_buffer.write(f"  [X] REMOVIDO: ISSN {issn_orig} (Qualis: {qualis_orig}) - {titulo}\n")
                                log_buffer.write("-" * 50 + "\n")
                            
                            df = df[mask_validos].drop(columns=["issn_temp"])
                        else:
                            log_buffer.write(f"AVISO: {arquivo} sem coluna ISSN. Nenhuma filtragem aplicada.\n")
                        
                        if not df.empty:
                            dfs.append(df)

                except Exception as e:
                    log_buffer.write(f"ERRO FATAL ao ler {arquivo}: {e}\n")
    
    if not dfs:
        return None, ["Nenhum dado restou após a filtragem ou erro na leitura."]
    
    data = pd.concat(dfs, ignore_index=True)
    return data, log_buffer.getvalue()
