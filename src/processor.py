import polars as pl
import pandas as pd
import zipfile
import os
from io import StringIO, BytesIO
import streamlit as st
from .utils import limpar_issn

@st.cache_data
def processar_dados_com_filtro(origem_dados, df_ref_qualis, is_parquet=False):
    """
    Processa dados (Parquet ou ZIP) usando Polars.
    origem_dados: Caminho do arquivo (str) ou objeto BytesIO (upload).
    df_ref_qualis: DataFrame (Polars ou Pandas) com a lista oficial.
    """
    log_buffer = StringIO()
    
    log_buffer.write("RELATÓRIO DE PUBLICAÇÕES EXCLUÍDAS (FILTRO QUALIS)\n")
    log_buffer.write("===================================================\n\n")

    # 1. Preparar Tabela Qualis (Normalização)
    # Se vier como Pandas (upload manual), converte para Polars
    if isinstance(df_ref_qualis, pd.DataFrame):
        df_qualis = pl.from_pandas(df_ref_qualis)
    else:
        df_qualis = df_ref_qualis

    # Normalizar colunas do Qualis (issn, titulo, estrato)
    df_qualis = df_qualis.select([pl.col(c).alias(c.lower().strip()) for c in df_qualis.columns])

    if 'issn' not in df_qualis.columns or 'estrato' not in df_qualis.columns:
        return None, ["Erro: O arquivo Qualis deve conter colunas 'ISSN' e 'Estrato'."]
    
    # Limpeza do ISSN no Qualis e Seleção de Colunas Chave
    df_qualis = df_qualis.with_columns(
        pl.col("issn").cast(pl.Utf8).fill_null("").str.to_uppercase().str.replace_all(r"[^0-9X]", "").alias("issn_limpo")
    ).select(["issn_limpo", "estrato"]).unique(subset=["issn_limpo"]) 
    # .unique garante que não duplique registros se a lista tiver ISSN repetido

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
                            # Lê com Pandas (engine='python') para maior robustez contra erros de aspas/escape em CSVs manuais
                            # dtype=str garante que tudo seja lido como texto, evitando erros de tipo
                            df_pd = pd.read_csv(f, on_bad_lines='skip', engine='python', dtype=str)
                            df_temp = pl.from_pandas(df_pd)
                            
                            # Correção de encoding para nomes de arquivos em ZIP (CP437 -> UTF-8)
                            nome_arquivo_corrigido = arquivo
                            try:
                                nome_arquivo_corrigido = arquivo.encode('cp437').decode('utf-8')
                            except:
                                pass
                            
                            nome_pesquisador = os.path.splitext(os.path.basename(nome_arquivo_corrigido))[0].replace("_", " ")
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
        # FIX: Cast para string, fill_null e upper para evitar erros se a coluna for lida como Int ou tiver Nones
        df_raw = df_raw.with_columns(
            pl.col(col_issn).cast(pl.Utf8).fill_null("").str.to_uppercase().str.replace_all(r"[^0-9X]", "").alias("issn_temp")
        )
        
        # CRUZAMENTO (JOIN) COM A LISTA OFICIAL
        # Renomear coluna do Qualis para evitar colisão com dados do pesquisador
        df_qualis_join = df_qualis.rename({"estrato": "estrato_oficial"})
        
        # Left Join para identificar o que casou e o que não casou
        df_joined = df_raw.join(df_qualis_join, left_on="issn_temp", right_on="issn_limpo", how="left")
        
        # Identificar excluídos (onde 'estrato_oficial' é nulo)
        df_excluidos = df_joined.filter(pl.col("estrato_oficial").is_null())
        
        # Identificar mantidos
        df_mantidos = df_joined.filter(pl.col("estrato_oficial").is_not_null())

        # Gerar Log de Exclusões
        if not df_excluidos.is_empty():
            df_excluidos = df_excluidos.sort("pesquisador")
            
            # Verifica colunas disponíveis para o log
            cols_disp = df_excluidos.columns
            col_titulo = "titulo" if "titulo" in cols_disp else None
            col_qualis_orig = "qualis" if "qualis" in cols_disp else None
            
            # Seleciona dados para iteração
            rows = df_excluidos.select([
                pl.col("pesquisador"),
                pl.col("issn_temp"),
                pl.col(col_titulo).alias("titulo") if col_titulo else pl.lit("Título não identificado").alias("titulo"),
                pl.col(col_qualis_orig).alias("qualis_orig") if col_qualis_orig else pl.lit("N/A").alias("qualis_orig")
            ]).iter_rows(named=True)
            
            current_pesq = None
            for row in rows:
                p = row["pesquisador"]
                if p != current_pesq:
                    log_buffer.write(f"PESQUISADOR: {p}\n")
                    current_pesq = p
                
                t = row["titulo"] or "Título não identificado"
                i = row["issn_temp"] or "S/N"
                q = row["qualis_orig"] or "N/A"
                log_buffer.write(f"  [X] REMOVIDO: ISSN {i} (Qualis Orig: {q}) - {t}\n")
            
            log_buffer.write("-" * 50 + "\n")

        # Preparar DataFrame Final (apenas mantidos)
        # Substituir o Qualis do pesquisador pelo Oficial ('estrato_oficial')
        cols_to_drop = ["issn_temp", "issn_limpo"]
        if "qualis" in df_mantidos.columns:
            cols_to_drop.append("qualis")
        if "estrato" in df_mantidos.columns:
            cols_to_drop.append("estrato")
            
        df_final = df_mantidos.drop([c for c in cols_to_drop if c in df_mantidos.columns])
        df_final = df_final.rename({"estrato_oficial": "qualis"})
        
        # PADRONIZAÇÃO DE TIPOS (Evita erro de Schema no concat)
        # 1. Ano de Publicação: Converter para Int64
        if "ano_publicacao" in df_final.columns:
            df_final = df_final.with_columns(
                pl.col("ano_publicacao").cast(pl.Utf8, strict=False).str.replace(r"\.0*$", "").cast(pl.Int64, strict=False).fill_null(0)
            )
            
        # 2. Demais colunas: Converter para String (Utf8) para evitar conflitos (ex: volume 1.0 vs "v1")
        cols_to_string = [c for c in df_final.columns if c != "ano_publicacao"]
        if cols_to_string:
            df_final = df_final.with_columns([
                pl.col(c).cast(pl.Utf8) for c in cols_to_string
            ])
        
        return df_final, log_buffer.getvalue()
    else:
        return df_raw, "Aviso: Coluna ISSN não encontrada nos dados brutos."
