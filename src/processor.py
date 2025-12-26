import polars as pl
import zipfile
import os
from io import StringIO, BytesIO
import streamlit as st
from .utils import limpar_issn

@st.cache_data
def processar_dados_com_filtro(origem_dados, df_ref_qualis_pd, is_parquet=False):
    """
    Processa dados (Parquet ou ZIP) usando Polars.
    origem_dados: Caminho do arquivo (str) ou objeto BytesIO (upload).
    df_ref_qualis_pd: DataFrame do Pandas com o Qualis (convertido para Polars internamente).
    """
    log_buffer = StringIO()
    
    log_buffer.write("RELATÓRIO DE PUBLICAÇÕES EXCLUÍDAS (FILTRO QUALIS)\n")
    log_buffer.write("===================================================\n\n")

    # Converter Qualis (Pandas) para Polars
    try:
        df_qualis = pl.from_pandas(df_ref_qualis_pd)
        df_qualis = df_qualis.select([pl.col(c).alias(c.lower().strip()) for c in df_qualis.columns])
    except Exception as e:
        return None, [f"Erro ao converter Qualis para Polars: {e}"]

    # 1. Preparar Lista de ISSNs Válidos
    if 'issn' not in df_qualis.columns:
        return None, ["Erro: Coluna 'issn' não encontrada no arquivo Qualis."]
    
    # Limpeza do ISSN no Qualis (usando expressões Polars)
    df_qualis = df_qualis.with_columns(
        pl.col("issn").str.replace_all(r"[^0-9X]", "").alias("issn_limpo")
    )
    valid_issns = set(df_qualis["issn_limpo"].to_list())

    # 2. Carregar Dados (Parquet ou ZIP)
    df_raw = None
    
    if is_parquet:
        # Leitura otimizada de Parquet
        df_raw = pl.read_parquet(origem_dados)
    else:
        # Processamento legado de ZIP (Upload Manual) -> Convertendo para Polars
        dfs_temp = []
        with zipfile.ZipFile(origem_dados) as z:
            for arquivo in z.namelist():
                if arquivo.lower().endswith(".csv") and not arquivo.startswith("__MACOSX"):
                    try:
                        with z.open(arquivo) as f:
                            # Lê com Polars direto do buffer
                            df_temp = pl.read_csv(f.read(), ignore_errors=True)
                            nome_pesquisador = os.path.splitext(os.path.basename(arquivo))[0].replace("_", " ")
                            df_temp = df_temp.with_columns(pl.lit(nome_pesquisador).alias("pesquisador"))
                            dfs_temp.append(df_temp)
                    except Exception as e:
                        log_buffer.write(f"ERRO ao ler {arquivo}: {e}\n")
        if dfs_temp:
            df_raw = pl.concat(dfs_temp, how="diagonal")

    if df_raw is None or df_raw.is_empty():
        return None, ["Nenhum dado carregado."]

    # 3. Normalizar colunas e Filtrar
    df_raw = df_raw.select([pl.col(c).alias(c.lower().strip()) for c in df_raw.columns])
    
    # Encontrar coluna ISSN
    col_issn = next((c for c in df_raw.columns if "issn" in c), None)
    
    if col_issn:
        # Criar coluna temporária limpa
        df_raw = df_raw.with_columns(
            pl.col(col_issn).cast(pl.Utf8).str.replace_all(r"[^0-9X]", "").alias("issn_temp")
        )
        
        # Filtrar (Manter apenas ISSNs que estão no set valid_issns)
        # Polars é muito rápido nisso
        df_final = df_raw.filter(pl.col("issn_temp").is_in(valid_issns))
        
        # Opcional: Gerar log de exclusões (pode ser custoso em big data, simplificado aqui)
        # Para performance máxima, pularíamos a geração detalhada de log texto linha a linha
        
        return df_final.drop("issn_temp"), log_buffer.getvalue()
    else:
        return df_raw, "Aviso: Coluna ISSN não encontrada nos dados brutos."
