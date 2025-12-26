import streamlit as st
import os
import pandas as pd
import polars as pl
import zipfile
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

# Importações dos módulos locais
from src.config import PESOS
from src.utils import normalizar_texto
from src.processor import processar_dados_com_filtro

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard Pesquisadores + Filtro Qualis", layout="wide")

st.title("📊 Dashboard de Produção Científica (Com Filtro Qualis 2017-2020)")
st.markdown("""
1. Faça upload da **Lista Qualis (Excel)** no menu lateral.
2. Faça upload do **ZIP com os CSVs** dos pesquisadores abaixo.
""")

# ==========================================
# BARRA LATERAL (CONFIGURAÇÃO)
# ==========================================
st.sidebar.header("1. Configuração de Dados")

# Seletor de Modo de Dados
modo_dados = st.sidebar.radio(
    "Fonte de Dados",
    ("Upload Manual", "Repositório (Comparativo)"),
    help="Escolha entre fazer upload dos seus arquivos ou selecionar programas pré-carregados."
)

st.sidebar.divider()

fontes_para_processar = []
data_raw = None
log_texto = ""
filtro_padrao = ""

if modo_dados == "Repositório (Comparativo)":
    st.sidebar.info("⚠️ Modo Repositório Ativo")
    
    # Catálogo de Programas (Simulação de dados remotos/locais)
    CATALOGO = {
        "PPGE (Educação)": {
            "qualis": os.path.join(os.path.dirname(__file__), "assets", "lista_qualis_educacao.xlsx"),
            "path": os.path.join(os.path.dirname(__file__), "assets", "ppge.parquet"),
            "tipo": "parquet"
        },
        "PPGCI (Ciência da Informação)": {
            "qualis": os.path.join(os.path.dirname(__file__), "assets", "lista_qualis_comunicacao.xlsx"),
            "path": os.path.join(os.path.dirname(__file__), "assets", "ppgci.parquet"),
            "tipo": "parquet"
        },
        "MDCC (Ciência da Computação)": {
            "qualis": os.path.join(os.path.dirname(__file__), "assets", "lista_qualis_computacao.xlsx"),
            "path": os.path.join(os.path.dirname(__file__), "assets", "mdcc.parquet"),
            "tipo": "parquet"
        },
        # Adicione outros programas aqui conforme disponibilidade
    }
    
    # --- BUSCA GLOBAL (SCAN DE ARQUIVOS) ---
    st.sidebar.markdown("### 🔍 Busca Global")
    termo_global = st.sidebar.text_input("Localizar Pesquisador (Scan)", help="Busca em todos os programas sem carregar os dados.")
    
    programas_sugeridos = ["PPGE (Educação)"] if "PPGE (Educação)" in CATALOGO else []
    
    if termo_global:
        filtro_padrao = termo_global
        encontrados = []
        termo_norm = normalizar_texto(termo_global)
        
        # Itera sobre os arquivos físicos sem carregar CSVs (Alta Performance)
        for prog, caminhos in CATALOGO.items():
            f_path = caminhos["path"]
            if os.path.exists(f_path) and caminhos["tipo"] == "parquet":
                try:
                    # Scan Lazy do Parquet: Verifica se existe algum pesquisador que contém o termo
                    # Isso não carrega o arquivo todo na memória
                    lf = pl.scan_parquet(f_path)
                    # Filtra e verifica se retorna algo (limit 1 para ser rápido)
                    existe = lf.filter(pl.col("pesquisador").str.to_lowercase().str.contains(termo_norm)).head(1).collect()
                    if not existe.is_empty():
                        encontrados.append(prog)
                except:
                    pass
        
        if encontrados:
            st.sidebar.success(f"Encontrado em: {len(encontrados)} programa(s).")
            programas_sugeridos = encontrados
        else:
            st.sidebar.warning("Pesquisador não encontrado nos arquivos do repositório.")

    selecao = st.sidebar.multiselect(
        "Selecione os Programas:",
        options=list(CATALOGO.keys()),
        default=programas_sugeridos
    )
    
    for item in selecao:
        caminhos = CATALOGO[item]
        if os.path.exists(caminhos["qualis"]) and os.path.exists(caminhos["path"]):
            fontes_para_processar.append({"nome": item, "qualis": caminhos["qualis"], "path": caminhos["path"], "tipo": caminhos["tipo"]})
        else:
            st.sidebar.warning(f"Arquivos não encontrados para: {item}")

else:
    # --- MODO UPLOAD MANUAL ---
    st.sidebar.subheader("Upload de Arquivos")
    f_qualis = st.sidebar.file_uploader("1. Lista Qualis (Excel)", type=["xlsx", "xls"])
    st.header("2. Arquivos dos Pesquisadores")
    f_zip = st.file_uploader("2. Arraste o arquivo ZIP aqui", type="zip")
    
    if f_qualis and f_zip:
        fontes_para_processar.append({"nome": "Upload Manual", "qualis": f_qualis, "path": f_zip, "tipo": "zip"})
    else:
        st.info("👆 Faça o upload dos arquivos ou selecione 'Carregar Dados de Exemplo' no menu lateral.")

# ==========================================
# CONFIGURAÇÃO DE GRUPOS
# ==========================================
st.sidebar.divider()
st.sidebar.header("2. Definição de Grupos")

tipo_grupo = st.sidebar.radio(
    "Como definir os grupos?",
    ("Nenhum", "Upload Arquivo (Excel/CSV)", "Edição Manual", "Padrão (PPGE)"),
    index=0
)

GRUPOS_PESQUISA = {}

if tipo_grupo == "Padrão (PPGE)":
    from src.config import GRUPOS_PESQUISA as GP_STATIC
    GRUPOS_PESQUISA = GP_STATIC

elif tipo_grupo == "Upload Arquivo (Excel/CSV)":
    f_grupos = st.sidebar.file_uploader("Arquivo (colunas: Pesquisador, Grupo)", type=["xlsx", "csv"])
    if f_grupos:
        try:
            df_g = pd.read_csv(f_grupos) if f_grupos.name.endswith(".csv") else pd.read_excel(f_grupos)
            df_g.columns = [c.lower().strip() for c in df_g.columns]
            if "pesquisador" in df_g.columns and "grupo" in df_g.columns:
                for _, row in df_g.iterrows():
                    g, p = str(row["grupo"]).strip(), str(row["pesquisador"]).strip()
                    GRUPOS_PESQUISA.setdefault(g, []).append(p)
                st.sidebar.success(f"{len(GRUPOS_PESQUISA)} grupos carregados.")
            else:
                st.sidebar.error("Colunas obrigatórias: 'Pesquisador', 'Grupo'")
        except Exception as e:
            st.sidebar.error(f"Erro: {e}")

elif tipo_grupo == "Edição Manual":
    st.sidebar.info("Digite abaixo: Pesquisador, Grupo")
    texto_grupos = st.sidebar.text_area("Mapeamento (um por linha)", height=150, placeholder="João Silva, Grupo A\nMaria Souza, Grupo B")
    if texto_grupos:
        for linha in texto_grupos.split("\n"):
            if "," in linha:
                p, g = linha.split(",", 1)
                GRUPOS_PESQUISA.setdefault(g.strip(), []).append(p.strip())

# ==========================================
# FILTRO ADICIONAL
# ==========================================
st.sidebar.divider()
st.sidebar.header("3. Filtro Adicional")
filtro_pesquisador = st.sidebar.text_input(
    "Buscar por nome do pesquisador",
    value=filtro_padrao,
    help="Digite parte do nome para filtrar os dashboards."
)


# ==========================================
# PROCESSAMENTO (CONDICIONAL)
# ==========================================

if fontes_para_processar:
    with st.spinner('Processando dados...'):
        dfs = []
        logs = []
        for fonte in fontes_para_processar:
            try:
                df_ref = pd.read_excel(fonte["qualis"])
                is_pq = (fonte["tipo"] == "parquet")
                d, l = processar_dados_com_filtro(fonte["path"], df_ref, is_parquet=is_pq)
                
                if d is not None:
                    d = d.with_columns(pl.lit(fonte["nome"]).alias("programa_origem"))
                    dfs.append(d)
                    logs.append(f"=== LOG: {fonte['nome']} ===\n{l}\n")
            except Exception as e:
                st.error(f"Erro ao processar {fonte['nome']}: {e}")
        
        if dfs:
            data_raw = pl.concat(dfs, how="diagonal")
            log_texto = "\n".join(logs)

    if data_raw is not None:
        st.success(f"Processamento concluído! {len(data_raw)} registros válidos carregados.")
        
        with st.expander("📄 Ver Relatório de Exclusões (Filtragem)", expanded=False):
            st.text_area("Log de Filtragem", log_texto, height=300)
            st.download_button("Baixar Relatório (.txt)", log_texto, file_name="relatorio_filtragem.txt")

        # --- APLICAR FILTRO DE PESQUISADOR (SE HOUVER) ---
        if filtro_pesquisador:
            termo_busca_norm = normalizar_texto(filtro_pesquisador)
            
            # Filtro Polars
            data_raw = data_raw.filter(
                pl.col("pesquisador").str.to_lowercase().str.contains(termo_busca_norm)
            )
            
            if data_raw.is_empty():
                st.warning(f"Nenhum pesquisador encontrado com o termo '{filtro_pesquisador}'.")
                st.stop() # Interrompe a execução para não gerar gráficos vazios
            else:
                st.success(f"Filtro aplicado. Exibindo dados para pesquisadores contendo '{filtro_pesquisador}'.")


        # --- PROCESSAMENTO DOS DADOS PARA VISUALIZAÇÃO ---
        # Converter para Pandas apenas o necessário ou trabalhar com Polars até o fim
        # Vamos manter Polars para as transformações
        data = data_raw.with_columns(
            pl.col("qualis").cast(pl.Utf8).str.to_uppercase().str.strip_chars().alias("qualis_norm")
        )
        data = data.filter(pl.col("qualis_norm").is_in(list(PESOS.keys())))
        
        # Map de pesos (Polars replace/map_dict)
        data = data.with_columns(pl.col("qualis_norm").replace(PESOS, default=0).alias("peso"))
        data = data.sort("ano_publicacao")

        # --- MATCHING DE GRUPOS OU PROGRAMAS ---
        comparacao_programas = len(fontes_para_processar) > 1
        
        if comparacao_programas:
            # Modo Comparação de Programas: O "Grupo" vira o "Programa"
            df_grupos = data.with_columns([
                pl.col("programa_origem").alias("linha_pesquisa"),
                pl.col("pesquisador").str.to_titlecase()
            ])
            data = data.with_columns(pl.col("pesquisador").str.to_titlecase())
        else:
            # Modo Análise de Grupos (Interno)
            # Como o matching de grupos é complexo (dicionário python), é mais fácil converter para Pandas aqui
            # ou usar map_elements, mas para manter compatibilidade com a lógica de "contains", vamos iterar.
            # Para performance, idealmente GRUPOS_PESQUISA seria um DataFrame de join.
            
            # Convertendo para Pandas para realizar o matching de grupos (lógica iterativa complexa)
            data_pd = data.to_pandas()
            records_grupos = []
            correcao_nomes = {}
            
            for idx, row in data_pd.iterrows():
                nome_no_csv = row["pesquisador"]
                nome_csv_norm = normalizar_texto(nome_no_csv)
                
                for nome_grupo, membros in GRUPOS_PESQUISA.items():
                    for membro_com_acento in membros:
                        if nome_csv_norm == normalizar_texto(membro_com_acento):
                            new_row = row.copy()
                            new_row["linha_pesquisa"] = nome_grupo
                            new_row["pesquisador"] = membro_com_acento
                            correcao_nomes[nome_no_csv] = membro_com_acento
                            records_grupos.append(new_row)

            data_pd["pesquisador"] = data_pd["pesquisador"].map(lambda x: correcao_nomes.get(x, x.title()))
            
            # Volta para Polars ou mantém Pandas? Como o resto do código de plotagem usa Pandas (implícito no código original),
            # vamos manter df_grupos como Pandas para facilitar a integração com o código legado de plotagem abaixo.
            
            if records_grupos:
                df_grupos = pd.DataFrame(records_grupos)
            else:
                df_grupos = pd.DataFrame(columns=data_pd.columns.tolist() + ["linha_pesquisa"])
                st.warning("Nenhum pesquisador correspondeu à lista de Grupos de Pesquisa configurada.")
            
            # Atualiza data principal também como Pandas para os gráficos individuais
            data = data_pd
        
        # Se estivermos no modo comparação, data e df_grupos ainda são Polars.
        # Para garantir compatibilidade com o código de plotagem (que usa sintaxe Pandas .groupby),
        # vamos converter tudo para Pandas neste ponto final.
        if isinstance(data, pl.DataFrame):
            data = data.to_pandas()
        if isinstance(df_grupos, pl.DataFrame):
            df_grupos = df_grupos.to_pandas()

        # --- ABAS DA DASHBOARD ---
        titulo_tab2 = "🏢 Análise por Programas" if comparacao_programas else "👥 Análise por Grupos"
        tab1, tab2, tab3 = st.tabs(["👤 Análise Individual", titulo_tab2, "📋 Auditoria e Grupos"])

        # =======================================================
        # TAB 1: INDIVIDUAL
        # =======================================================
        with tab1:
            st.subheader("Performance Individual")
            
            total = data.groupby(["ano_publicacao", "pesquisador"], as_index=False)["peso"].sum()
            total["acumulado"] = total.groupby("pesquisador")["peso"].cumsum()
            
            total_global = total.groupby("pesquisador", as_index=False)["peso"].sum()
            soma_global = total_global["peso"].sum()
            
            map_perc_global = dict(zip(total_global["pesquisador"], 100 * total_global["peso"] / soma_global))

            ranking_anual = {}
            for ano in sorted(total["ano_publicacao"].unique()):
                df_ano = total[total["ano_publicacao"] == ano].copy()
                soma_ano = df_ano["peso"].sum()
                df_ano["perc"] = (100 * df_ano["peso"] / soma_ano) if soma_ano > 0 else 0
                df_ano = df_ano.sort_values("perc", ascending=False)
                ranking_anual[ano] = "<br>".join(f"{i}. {row['pesquisador']} — {row['perc']:.1f}% (global: {map_perc_global[row['pesquisador']]:.1f}%)" for i, (idx, row) in enumerate(df_ano.head(50).iterrows(), start=1))

            ranking_acumulado = {}
            for ano in sorted(total["ano_publicacao"].unique()):
                df_acc = total[total["ano_publicacao"] <= ano].groupby("pesquisador", as_index=False)["peso"].sum()
                df_acc["perc_rel"] = (100 * df_acc["peso"] / soma_global)
                df_acc = df_acc.sort_values("perc_rel", ascending=False)
                ranking_acumulado[ano] = "<br>".join(f"{i}. {row['pesquisador']} — {row['perc_rel']:.1f}% (global: {map_perc_global[row['pesquisador']]:.1f}%)" for i, (idx, row) in enumerate(df_acc.head(50).iterrows(), start=1))

            fig_timeline = go.Figure()
            pesquisadores = sorted(total["pesquisador"].unique())
            n_p = len(pesquisadores)
            for p in pesquisadores:
                d = total[total["pesquisador"] == p]
                fig_timeline.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["peso"], mode="lines+markers", name=p, hoverinfo="skip", visible=True))
            for p in pesquisadores:
                d = total[total["pesquisador"] == p]
                fig_timeline.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["acumulado"], mode="lines", name=f"{p} (Acumulado)", hoverinfo="skip", visible=False))

            anos = sorted(total["ano_publicacao"].unique())
            fig_timeline.add_trace(go.Scatter(x=anos, y=[0]*len(anos), mode="markers", marker=dict(opacity=0), customdata=[ranking_anual[a] for a in anos], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Anual</b><br>%{customdata}<extra></extra>", showlegend=False))
            fig_timeline.add_trace(go.Scatter(x=anos, y=[0]*len(anos), mode="markers", marker=dict(opacity=0), customdata=[ranking_acumulado[a] for a in anos], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Acumulado</b><br>%{customdata}<extra></extra>", showlegend=False, visible=False))

            fig_timeline.update_layout(title="Linha do Tempo (Individual)", height=800, hovermode="x unified", updatemenus=[dict(buttons=[dict(label="Total Anual", method="update", args=[{"visible": [True]*n_p + [False]*n_p + [True, False]}]), dict(label="Acumulado", method="update", args=[{"visible": [False]*n_p + [True]*n_p + [False, True]}])], direction="down", x=0.01, y=1.12)])
            st.plotly_chart(fig_timeline, use_container_width=True)

            col1, col2 = st.columns(2)

            with col1:
                estratos = list(PESOS.keys())
                radar_df = data.groupby(["pesquisador", "qualis_norm"]).size().reset_index(name="qtd")
                fig_radar = go.Figure()
                for p in sorted(radar_df["pesquisador"].unique()):
                    d = radar_df[radar_df["pesquisador"] == p]
                    vals = [d.loc[d["qualis_norm"]==e, "qtd"].sum() for e in estratos]
                    fig_radar.add_trace(go.Scatterpolar(r=vals+[vals[0]], theta=estratos+[estratos[0]], name=p, fill='toself', opacity=0.35))
                fig_radar.update_layout(title="Perfil Qualis (Individual)", polar=dict(radialaxis=dict(visible=True)))
                st.plotly_chart(fig_radar, use_container_width=True)

            with col2:
                map_abc = {"A1":"A","A2":"A","A3":"B","A4":"B","B1":"C","B2":"C","B3":"C","B4":"C"}
                df_tern = data.copy()
                df_tern["grupo_abc"] = df_tern["qualis_norm"].map(map_abc)
                tern_cts = df_tern.groupby(["pesquisador", "grupo_abc"]).size().unstack(fill_value=0)
                for c in "ABC":
                    if c not in tern_cts: tern_cts[c] = 0
                tern_cts["sum"] = tern_cts.sum(axis=1)
                fig_ternary = go.Figure()
                for p in sorted(tern_cts.index):
                    r = tern_cts.loc[p]
                    if r["sum"] == 0: continue
                    fig_ternary.add_trace(go.Scatterternary(a=[r["A"]/r["sum"]], b=[r["B"]/r["sum"]], c=[r["C"]/r["sum"]], mode="markers", name=p, marker=dict(size=14, line=dict(width=1, color='DarkSlateGrey')), hovertemplate=f"<b>{p}</b><br>A: %{{a:.1%}}<br>B: %{{b:.1%}}<br>C: %{{c:.1%}}<extra></extra>"))
                fig_ternary.update_layout(title="Distribuição Proporcional", ternary=dict(aaxis=dict(title="A"), baxis=dict(title="B"), caxis=dict(title="C")))
                st.plotly_chart(fig_ternary, use_container_width=True)

            hm_data = total.pivot(index="pesquisador", columns="ano_publicacao", values="peso").fillna(0).sort_index()
            fig_heatmap = go.Figure(data=go.Heatmap(z=hm_data.values, x=hm_data.columns, y=hm_data.index, colorscale="Viridis", colorbar=dict(title="Pontos")))
            fig_heatmap.update_layout(title="Mapa de Calor (Intensidade)", height=max(400, len(hm_data)*30))
            st.plotly_chart(fig_heatmap, use_container_width=True)

            c_data = data.groupby(["pesquisador", "qualis_norm"]).size().unstack(fill_value=0)
            for k in PESOS:
                if k not in c_data: c_data[k] = 0
            c_data = c_data[list(PESOS.keys())]
            if len(c_data) > 1:
                scaler = StandardScaler()
                scaled = scaler.fit_transform(c_data)
                n_clusters_i = min(3, len(c_data))
                kmeans = KMeans(n_clusters=n_clusters_i, random_state=42, n_init=10)
                clusters = kmeans.fit_predict(scaled)
                pca = PCA(n_components=2)
                coords = pca.fit_transform(scaled)
                df_vis_c = pd.DataFrame({"pesquisador": c_data.index, "x": coords[:,0], "y": coords[:,1], "cluster": clusters.astype(str)})
                fig_cluster = go.Figure()
                for c in sorted(df_vis_c.cluster.unique()):
                    d = df_vis_c[df_vis_c.cluster == c]
                    fig_cluster.add_trace(go.Scatter(x=d.x, y=d.y, mode="markers+text", text=d.pesquisador, name=f"Grupo {int(c)+1}", marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')), hovertemplate="<b>%{text}</b><br>Grupo: %{name}<extra></extra>"))
                fig_cluster.update_layout(title="Cluster de Similaridade (Individual)")
                st.plotly_chart(fig_cluster, use_container_width=True)
            else:
                st.warning("Dados insuficientes para gerar o Cluster de Similaridade. É necessário haver pelo menos 2 pesquisadores para comparação.")
            st.info("Visualização dos gráficos individuais carregada.")

        # =======================================================
        # TAB 2: GRUPOS
        # =======================================================
        with tab2:
            st.subheader(f"Performance por {'Programa' if comparacao_programas else 'Linha de Pesquisa'}")

            if not df_grupos.empty:
                group_counts = df_grupos.groupby("linha_pesquisa")["pesquisador"].nunique().reset_index(name="n_membros")
                total_g = df_grupos.groupby(["ano_publicacao", "linha_pesquisa"], as_index=False)["peso"].sum()
                total_g = pd.merge(total_g, group_counts, on="linha_pesquisa")
                total_g["acumulado"] = total_g.groupby("linha_pesquisa")["peso"].cumsum()
                total_g["peso_medio"] = total_g["peso"] / total_g["n_membros"]
                total_g["acumulado_medio"] = total_g.groupby("linha_pesquisa")["peso_medio"].cumsum()

                total_global_g = total_g.groupby("linha_pesquisa", as_index=False)["peso"].sum()
                soma_global_g = total_global_g["peso"].sum()
                map_perc_global_g = dict(zip(total_global_g["linha_pesquisa"], 100 * total_global_g["peso"] / soma_global_g))

                ranking_anual_g = {}
                for ano in sorted(total_g["ano_publicacao"].unique()):
                    df_ano = total_g[total_g["ano_publicacao"] == ano].copy()
                    soma_ano = df_ano["peso"].sum()
                    df_ano["perc"] = (100 * df_ano["peso"] / soma_ano) if soma_ano > 0 else 0
                    df_ano = df_ano.sort_values("perc", ascending=False)
                    ranking_anual_g[ano] = "<br>".join(f"{i}. {row['linha_pesquisa']} — {row['perc']:.1f}% (global: {map_perc_global_g[row['linha_pesquisa']]:.1f}%)" for i, (idx, row) in enumerate(df_ano.iterrows(), start=1))

                ranking_acc_g = {}
                for ano in sorted(total_g["ano_publicacao"].unique()):
                    df_acc = total_g[total_g["ano_publicacao"] <= ano].groupby("linha_pesquisa", as_index=False)["peso"].sum()
                    df_acc["perc_rel"] = (100 * df_acc["peso"] / soma_global_g)
                    df_acc = df_acc.sort_values("perc_rel", ascending=False)
                    ranking_acc_g[ano] = "<br>".join(f"{i}. {row['linha_pesquisa']} — {row['perc_rel']:.1f}% (global: {map_perc_global_g[row['linha_pesquisa']]:.1f}%)" for i, (idx, row) in enumerate(df_acc.iterrows(), start=1))

                ranking_avg_anual = {}
                for ano in sorted(total_g["ano_publicacao"].unique()):
                    df_ano = total_g[total_g["ano_publicacao"] == ano].sort_values("peso_medio", ascending=False)
                    ranking_avg_anual[ano] = "<br>".join(f"{i}. {row['linha_pesquisa']} — {row['peso_medio']:.1f} pts/pesq" for i, (idx, row) in enumerate(df_ano.iterrows(), start=1))

                ranking_avg_acc = {}
                for ano in sorted(total_g["ano_publicacao"].unique()):
                    df_ate = total_g[total_g["ano_publicacao"] <= ano].groupby("linha_pesquisa", as_index=False)["peso_medio"].sum().sort_values("peso_medio", ascending=False)
                    ranking_avg_acc[ano] = "<br>".join(f"{i}. {row['linha_pesquisa']} — {row['peso_medio']:.1f} pts/pesq (acum)" for i, (idx, row) in enumerate(df_ate.iterrows(), start=1))

                fig_time_g = go.Figure()
                grupos = sorted(total_g["linha_pesquisa"].unique())
                n_g = len(grupos)
                for g in grupos:
                    d = total_g[total_g["linha_pesquisa"] == g]
                    fig_time_g.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["peso"], mode="lines+markers", name=g, hoverinfo="skip", visible=True))
                for g in grupos:
                    d = total_g[total_g["linha_pesquisa"] == g]
                    fig_time_g.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["acumulado"], mode="lines", name=f"{g} (Acumulado)", hoverinfo="skip", visible=False))

                anos_g = sorted(total_g["ano_publicacao"].unique())
                fig_time_g.add_trace(go.Scatter(x=anos_g, y=[0]*len(anos_g), mode="markers", marker=dict(opacity=0), customdata=[ranking_anual_g.get(a,"") for a in anos_g], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Anual (Volume)</b><br>%{customdata}<extra></extra>", showlegend=False))
                fig_time_g.add_trace(go.Scatter(x=anos_g, y=[0]*len(anos_g), mode="markers", marker=dict(opacity=0), customdata=[ranking_acc_g.get(a,"") for a in anos_g], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Acumulado (Volume)</b><br>%{customdata}<extra></extra>", showlegend=False, visible=False))

                fig_time_g.update_layout(title="Volume Total de Produção", height=800, hovermode="x unified", updatemenus=[dict(buttons=[dict(label="Total Anual", method="update", args=[{"visible": [True]*n_g + [False]*n_g + [True, False]}]), dict(label="Acumulado", method="update", args=[{"visible": [False]*n_g + [True]*n_g + [False, True]}])], direction="down", x=0.01, y=1.12)])
                st.plotly_chart(fig_time_g, use_container_width=True)

                st.divider()
                st.subheader("Análise de Eficiência (Média e Tamanho)")

                col_ef1, col_ef2 = st.columns(2)

                with col_ef1:
                    fig_time_avg = go.Figure()
                    for g in grupos:
                        d = total_g[total_g["linha_pesquisa"] == g]
                        fig_time_avg.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["peso_medio"], mode="lines+markers", name=f"{g} (n={d['n_membros'].iloc[0]})", hoverinfo="skip", visible=True))
                    for g in grupos:
                        d = total_g[total_g["linha_pesquisa"] == g]
                        fig_time_avg.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["acumulado_medio"], mode="lines", name=f"{g} (Acumulado)", hoverinfo="skip", visible=False))

                    fig_time_avg.add_trace(go.Scatter(x=anos_g, y=[0]*len(anos_g), mode="markers", marker=dict(opacity=0), customdata=[ranking_avg_anual.get(a,"") for a in anos_g], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Eficiência</b><br>%{customdata}<extra></extra>", showlegend=False))
                    fig_time_avg.add_trace(go.Scatter(x=anos_g, y=[0]*len(anos_g), mode="markers", marker=dict(opacity=0), customdata=[ranking_avg_acc.get(a,"") for a in anos_g], hovertemplate="<b>Ano %{x}</b><br><br><b>Ranking Eficiência Acum.</b><br>%{customdata}<extra></extra>", showlegend=False, visible=False))
                    fig_time_avg.update_layout(title="Eficiência (Pontos por Membro)", height=600, hovermode="x unified", yaxis_title="Pontos/Membro", updatemenus=[dict(buttons=[dict(label="Média Anual", method="update", args=[{"visible": [True]*n_g + [False]*n_g + [True, False]}]), dict(label="Média Acumulada", method="update", args=[{"visible": [False]*n_g + [True]*n_g + [False, True]}])], direction="down", x=0.01, y=1.12)])
                    st.plotly_chart(fig_time_avg, use_container_width=True)

                with col_ef2:
                    fig_bubble = go.Figure()
                    for g in grupos:
                        d = total_g[total_g["linha_pesquisa"] == g]
                        bubble_size = d["n_membros"].iloc[0] * 3
                        fig_bubble.add_trace(go.Scatter(x=d["ano_publicacao"], y=d["peso"], mode="lines+markers", name=f"{g} (n={d['n_membros'].iloc[0]})",
                                                            marker=dict(size=bubble_size, line=dict(width=1, color='DarkSlateGrey')),
                                                            hovertemplate=f"<b>{g}</b><br>Ano: %{{x}}<br>Pontos: %{{y}}<br>Membros: {d['n_membros'].iloc[0]}<extra></extra>"))
                    fig_bubble.update_layout(title="Volume Total (Tamanho da bolha = Tamanho do Grupo)", height=600, yaxis_title="Pontuação Total")
                    st.plotly_chart(fig_bubble, use_container_width=True)

                st.divider()
                c_data_g = df_grupos.groupby(["linha_pesquisa", "qualis_norm"]).size().unstack(fill_value=0)
                for k in PESOS:
                    if k not in c_data_g: c_data_g[k] = 0
                c_data_g = c_data_g[list(PESOS.keys())]
                if len(c_data_g) > 1:
                    scaler_g = StandardScaler()
                    scaled_g = scaler_g.fit_transform(c_data_g)
                    n_clusters_g = min(3, len(c_data_g))
                    kmeans_g = KMeans(n_clusters=n_clusters_g, random_state=42, n_init=10)
                    clusters_g = kmeans_g.fit_predict(scaled_g)
                    pca_g = PCA(n_components=2)
                    coords_g = pca_g.fit_transform(scaled_g)
                    df_vis_cg = pd.DataFrame({"grupo": c_data_g.index, "x": coords_g[:,0], "y": coords_g[:,1], "cluster": clusters_g.astype(str)})
                    fig_cluster_g = go.Figure()
                    for c in sorted(df_vis_cg.cluster.unique()):
                        d = df_vis_cg[df_vis_cg.cluster == c]
                        fig_cluster_g.add_trace(go.Scatter(x=d.x, y=d.y, mode="markers+text", text=d.grupo, name=f"Grupo {int(c)+1}", marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')), hovertemplate="<b>%{text}</b><br>Grupo: %{name}<extra></extra>"))
                    fig_cluster_g.update_layout(title="Cluster de Similaridade (Grupos)", height=600)
                    st.plotly_chart(fig_cluster_g, use_container_width=True)
                else:
                    st.warning("Dados insuficientes para gerar o Cluster de Similaridade de Grupos. É necessário haver pelo menos 2 grupos/programas para comparação.")
            else:
                st.warning("Não há dados suficientes para gerar a análise de grupos.")
            st.info("Visualização dos gráficos de grupos carregada.")

        # =======================================================
        # TAB 3: AUDITORIA
        # =======================================================
        with tab3:
            if comparacao_programas:
                st.info("A auditoria de grupos está desativada no modo de Comparação entre Programas.")
            else:
                st.subheader("Conferência de Integridade dos Grupos")
                pesquisadores_no_df = set(data["pesquisador"].unique())
                
                for nome_grupo, lista_teorica in GRUPOS_PESQUISA.items():
                    encontrados = sorted([p for p in lista_teorica if p in pesquisadores_no_df])
                    faltando = sorted([p for p in lista_teorica if p not in pesquisadores_no_df])
                    
                    status_icon = "✅" if not faltando else "⚠️"
                    with st.expander(f"{status_icon} {nome_grupo} (Encontrados: {len(encontrados)}/{len(lista_teorica)})"):
                        c1, c2 = st.columns(2)
                        c1.write("**Encontrados:**"); 
                        for p in encontrados: c1.success(f"- {p}")
                        c2.write("**Faltando:**"); 
                        for p in faltando: c2.error(f"- {p}")

else:
    if modo_dados == "Upload Manual":
        st.info("Aguardando upload dos arquivos (Qualis e ZIP) para gerar o dashboard.")
    else:
        st.info("Selecione pelo menos um programa no menu lateral para visualizar os dados.")
