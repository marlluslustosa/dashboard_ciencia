import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

# Importações dos módulos locais
from src.config import PESOS, GRUPOS_PESQUISA
from src.utils import normalizar_texto
from src.processor import processar_zip_com_filtro

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard Pesquisadores + Filtro Qualis", layout="wide")

st.title("📊 Dashboard de Produção Científica (Com Filtro Qualis)")
st.markdown("""
1. Faça upload da **Lista Qualis (Excel)** no menu lateral.
2. Faça upload do **ZIP com os CSVs** dos pesquisadores abaixo.
""")

# ==========================================
# BARRA LATERAL (UPLOAD REFERÊNCIA)
# ==========================================
st.sidebar.header("1. Arquivo de Referência")
qualis_file = st.sidebar.file_uploader("Upload 'lista_qualis_educacao.xlsx'", type=["xlsx", "xls"])

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
st.header("2. Arquivos dos Pesquisadores")
uploaded_zip = st.file_uploader("Arraste o arquivo ZIP com os CSVs aqui", type="zip")

if uploaded_zip is not None and qualis_file is not None:
    
    with st.spinner('Lendo referência Qualis e filtrando CSVs...'):
        try:
            df_ref = pd.read_excel(qualis_file)
            data_raw, log_texto = processar_zip_com_filtro(uploaded_zip, df_ref)
        except Exception as e:
            st.error(f"Erro ao ler arquivo Excel: {e}")
            data_raw = None

    if data_raw is not None:
        st.success(f"Processamento concluído! {len(data_raw)} registros válidos carregados.")
        
        with st.expander("📄 Ver Relatório de Exclusões (Filtragem)", expanded=False):
            st.text_area("Log de Filtragem", log_texto, height=300)
            st.download_button("Baixar Relatório (.txt)", log_texto, file_name="relatorio_filtragem.txt")

        # --- PROCESSAMENTO DOS DADOS PARA VISUALIZAÇÃO ---
        data = data_raw.copy()
        data["qualis_norm"] = data["qualis"].astype(str).str.upper().str.strip()
        data = data[data["qualis_norm"].isin(PESOS.keys())].copy()
        data["peso"] = data["qualis_norm"].map(PESOS)
        data = data.sort_values("ano_publicacao")

        # --- MATCHING DE GRUPOS ---
        records_grupos = []
        correcao_nomes = {}
        
        for idx, row in data.iterrows():
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

        data["pesquisador"] = data["pesquisador"].map(lambda x: correcao_nomes.get(x, x.title()))
        
        if records_grupos:
            df_grupos = pd.DataFrame(records_grupos)
        else:
            df_grupos = pd.DataFrame(columns=data.columns.tolist() + ["linha_pesquisa"])
            st.warning("Nenhum pesquisador correspondeu à lista de Grupos de Pesquisa configurada.")

        # --- ABAS DA DASHBOARD ---
        tab1, tab2, tab3 = st.tabs(["👤 Análise Individual", "👥 Análise por Grupos", "📋 Auditoria e Grupos"])

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
                ranking_anual[ano] = "<br>".join(f"{i}. {row['pesquisador']} — {row['perc']:.1f}% (global: {map_perc_global[row['pesquisador']]:.1f}%)" for i, (idx, row) in enumerate(df_ano.iterrows(), start=1))

            ranking_acumulado = {}
            for ano in sorted(total["ano_publicacao"].unique()):
                df_acc = total[total["ano_publicacao"] <= ano].groupby("pesquisador", as_index=False)["peso"].sum()
                df_acc["perc_rel"] = (100 * df_acc["peso"] / soma_global)
                df_acc = df_acc.sort_values("perc_rel", ascending=False)
                ranking_acumulado[ano] = "<br>".join(f"{i}. {row['pesquisador']} — {row['perc_rel']:.1f}% (global: {map_perc_global[row['pesquisador']]:.1f}%)" for i, (idx, row) in enumerate(df_acc.iterrows(), start=1))

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
            if len(c_data) > 0:
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
            st.info("Visualização dos gráficos individuais carregada.")

        # =======================================================
        # TAB 2: GRUPOS
        # =======================================================
        with tab2:
            st.subheader("Performance por Linha de Pesquisa")

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
                if len(c_data_g) > 0:
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
                st.warning("Não há dados suficientes para gerar a análise de grupos.")
            st.info("Visualização dos gráficos de grupos carregada.")

        # =======================================================
        # TAB 3: AUDITORIA
        # =======================================================
        with tab3:
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

elif uploaded_zip is None:
    st.info("Aguardando upload do ZIP...")
