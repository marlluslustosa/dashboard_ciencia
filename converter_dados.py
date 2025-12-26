# converter_dados.py
import zipfile
import pandas as pd
import os

def converter_zip_para_parquet(zip_path, output_path):
    dfs = []
    with zipfile.ZipFile(zip_path) as z:
        for arquivo in z.namelist():
            if arquivo.endswith(".csv") and not arquivo.startswith("__MACOSX"):
                with z.open(arquivo) as f:
                    df = pd.read_csv(f, on_bad_lines='skip')
                    # O nome do arquivo vira uma coluna
                    nome_pesquisador = os.path.splitext(os.path.basename(arquivo))[0].replace("_", " ")
                    df["pesquisador"] = nome_pesquisador
                    dfs.append(df)
    
    if dfs:
        full_df = pd.concat(dfs, ignore_index=True)
        # Normalizar colunas para garantir compatibilidade
        full_df.columns = [c.lower().strip() for c in full_df.columns]
        # Salvar como Parquet
        full_df.to_parquet(output_path, index=False)
        print(f"Sucesso: {output_path} gerado com {len(full_df)} registros.")

def converter_qualis_para_parquet(xlsx_path, output_path):
    try:
        df = pd.read_excel(xlsx_path)
        # Padronizar colunas para facilitar (remove espaços extras nos nomes)
        df.columns = [str(c).strip() for c in df.columns]
        df.to_parquet(output_path, index=False)
        print(f"Sucesso: {output_path} gerado.")
    except Exception as e:
        print(f"Erro ao converter {xlsx_path}: {e}")

# Exemplo de uso:
#converter_zip_para_parquet("assets/pesquisadores_ppge.zip", "assets/ppge.parquet")
#converter_zip_para_parquet("assets/pesquisadores_ppgci.zip", "assets/ppgci.parquet")
#converter_zip_para_parquet("assets/pesquisadores_mdcc.zip", "assets/mdcc.parquet")
converter_qualis_para_parquet("assets/lista_qualis_educacao.xlsx", "assets/lista_qualis_educacao.parquet")
converter_qualis_para_parquet("assets/lista_qualis_computacao.xlsx", "assets/lista_qualis_computacao.parquet")
converter_qualis_para_parquet("assets/lista_qualis_comunicacao.xlsx", "assets/lista_qualis_comunicacao.parquet")