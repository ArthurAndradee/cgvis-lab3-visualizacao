"""
Pipeline de Alto Desempenho para Processamento e Visualização dos Microdados do ENEM 2024.
Desenvolvido utilizando DuckDB para computação Out-of-Core e Polars Lazy API para eficiência em memória.
"""

import os
import duckdb
import polars as pl
import plotly.express as px
import plotly.graph_objects as go

# Configuração de caminhos relativos ao diretório 'main'
DATA_DIR = "data"
PARTICIPANTES_CSV = os.path.join(DATA_DIR, "PARTICIPANTES_2024.csv")
RESULTADOS_CSV = os.path.join(DATA_DIR, "RESULTADOS_2024.csv")
PARQUET_ANALITICO = os.path.join(DATA_DIR, "ENEM_ANALITICO_2024.parquet")
PARQUET_FINAL = os.path.join(DATA_DIR, "ENEM_FINAL_2024.parquet")


def executar_ingestao_e_join():
    """
    Executa a leitura pesada dos CSVs originais tratada na camada de I/O.
    O DuckDB faz a leitura em blocos do disco por streaming (Out-of-Core),
    corrigindo encodings corrompidos e realizando a junção relacional sem estourar a RAM.
    """
    print("[1/3] Iniciando processamento de I/O e junção Out-of-Core via DuckDB...")
    
    if not os.path.exists(PARTICIPANTES_CSV) or not os.path.exists(RESULTADOS_CSV):
        raise FileNotFoundError("Os arquivos CSV originais não foram encontrados na pasta 'data/'.")

    con = duckdb.connect(database=':memory:')

    # Query otimizada: conversão de tipos na leitura, decodificação latin1 e junção interna
    query = f"""
    COPY (
        WITH part AS (
            SELECT 
                NU_INSCRICAO,
                TP_SEXO,
                TP_FAIXA_ETARIA,
                TP_COR_RACA,
                TP_ESTADO_CIVIL,
                Q001 AS ESC_PAI,
                Q002 AS ESC_MAE,
                Q006 AS FAIXA_RENDA,
                NO_MUNICIPIO_PROVA AS MUNICIPIO,
                SG_UF_PROVA AS UF,
                CASE SUBSTR(CAST(CO_UF_PROVA AS VARCHAR), 1, 1)
                    WHEN '1' THEN 'Norte'
                    WHEN '2' THEN 'Nordeste'
                    WHEN '3' THEN 'Sudeste'
                    WHEN '4' THEN 'Sul'
                    WHEN '5' THEN 'Centro-Oeste'
                    ELSE 'Desconhecido'
                END AS REGIAO
            FROM read_csv('{PARTICIPANTES_CSV}', header=True, encoding='latin1', sep=';', nullstr='NA')
        ),
        res AS (
            SELECT 
                NU_INSCRICAO,
                CAST(NU_NOTA_CN AS FLOAT) AS NU_NOTA_CN,
                CAST(NU_NOTA_CH AS FLOAT) AS NU_NOTA_CH,
                CAST(NU_NOTA_LC AS FLOAT) AS NU_NOTA_LC,
                CAST(NU_NOTA_MT AS FLOAT) AS NU_NOTA_MT,
                CAST(NU_NOTA_REDACAO AS FLOAT) AS NU_NOTA_REDACAO,
                (COALESCE(CAST(NU_NOTA_CN AS FLOAT), 0) + 
                 COALESCE(CAST(NU_NOTA_CH AS FLOAT), 0) + 
                 COALESCE(CAST(NU_NOTA_LC AS FLOAT), 0) + 
                 COALESCE(CAST(NU_NOTA_MT AS FLOAT), 0) + 
                 COALESCE(CAST(NU_NOTA_REDACAO AS FLOAT), 0)) / 5.0 AS MEDIA_GERAL
            FROM read_csv('{RESULTADOS_CSV}', header=True, encoding='latin1', sep=';', nullstr='NA')
        )
        SELECT 
            p.*, 
            r.NU_NOTA_CN, 
            r.NU_NOTA_CH, 
            r.NU_NOTA_LC, 
            r.NU_NOTA_MT, 
            r.NU_NOTA_REDACAO, 
            r.MEDIA_GERAL
        FROM part p
        INNER JOIN res r ON p.NU_INSCRICAO = r.NU_INSCRICAO
        WHERE r.NU_NOTA_REDACAO IS NOT NULL
    ) TO '{PARQUET_ANALITICO}' (FORMAT PARQUET, COMPRESSION 'SNAPPY');
    """
    
    con.execute(query)
    con.close()
    print(f"-> Sucesso: Arquivo bruto consolidado salvo em: {PARQUET_ANALITICO}")


def executar_limpeza_e_transformacao():
    """
    Carrega o arquivo Parquet de forma preguiçosa (Lazy API do Polars).
    Aplica os dicionários oficiais do ENEM 2024 para mapeamento categórico e
    gera o relatório técnico de completude de dados.
    """
    print("\n[2/3] Iniciando transformações e validações estatísticas via Polars...")
    
    # Dicionários Oficiais do ENEM 2024
    dict_sexo = {"M": "Masculino", "F": "Feminino"}
    
    dict_raca = {
        0: "Não declarado", 1: "Branca", 2: "Preta", 
        3: "Parda", 4: "Amarela", 5: "Indígena", 6: "Não dispõe"
    }
    
    dict_faixa_etaria = {
        1: "Menor de 17 anos", 2: "17 anos", 3: "18 anos", 4: "19 anos",
        5: "20 anos", 6: "21 anos", 7: "22 anos", 8: "23 anos", 9: "24 anos",
        10: "25 anos", 11: "26 a 30 anos", 12: "31 a 35 anos", 13: "36 a 40 anos",
        14: "41 a 45 anos", 15: "46 a 50 anos", 16: "51 a 55 anos",
        17: "56 a 60 anos", 18: "61 a 65 anos", 19: "66 a 70 anos", 20: "Maior de 70 anos"
    }
    
    dict_renda = {
        "A": "Nenhuma Renda", "B": "Até R$ 1.412,00", "C": "R$ 1.412,01 a R$ 2.118,00",
        "D": "R$ 2.118,01 a R$ 2.824,00", "E": "R$ 2.824,01 a R$ 3.530,00",
        "F": "R$ 3.530,01 a R$ 4.236,00", "G": "R$ 4.236,01 a R$ 5.648,00",
        "H": "R$ 5.648,01 a R$ 7.060,00", "I": "R$ 7.060,01 a R$ 8.472,00",
        "J": "R$ 8.472,01 a R$ 9.884,00", "K": "R$ 9.884,01 a R$ 11.296,00",
        "L": "R$ 11.296,01 a R$ 12.708,00", "M": "R$ 12.708,01 a R$ 14.120,00",
        "N": "R$ 14.120,01 a R$ 17.650,00", "O": "R$ 17.650,01 a R$ 21.180,00",
        "P": "R$ 21.180,01 a R$ 28.240,00", "Q": "Mais de R$ 28.240,00"
    }

    # Inicializar a leitura preguiçosa (nenhum dado entra na RAM ainda)
    lf = pl.scan_parquet(PARQUET_ANALITICO)

    # Executar pipeline estruturado de limpeza e transformação
    df_transformed = (
        lf
        # 1. Padronização rigorosa de strings e remoção de espaços em branco nulos
        .with_columns([
            pl.col("MUNICIPIO").str.strip_chars().str.to_uppercase(),
            pl.col("UF").str.strip_chars().str.to_uppercase(),
        ])
        # 2. Mapeamento eficiente de tipos categóricos usando substituição estrita
        .with_columns([
            pl.col("TP_SEXO").replace_strict(dict_sexo, default="Desconhecido").alias("SEXO_DESC"),
            pl.col("TP_COR_RACA").replace_strict(dict_raca, default="Desconhecido").alias("RACA_DESC"),
            pl.col("TP_FAIXA_ETARIA").replace_strict(dict_faixa_etaria, default="Desconhecido").alias("IDADE_DESC"),
            pl.col("FAIXA_RENDA").replace_strict(dict_renda, default="Desconhecido").alias("RENDA_DESC")
        ])
        # 3. Filtros de validação (remover outliers físicos / notas impossíveis)
        .filter(
            (pl.col("MEDIA_GERAL") >= 0.0) & (pl.col("MEDIA_GERAL") <= 1000.0)
        )
    )

    # Coletar métricas de completude (Calculado em paralelo pelo Polars)
    print("-> Computando relatório de completude de dados...")
    total_linhas = df_transformed.select(pl.len()).collect().item()
    df_missing = df_transformed.select(
        [(pl.col(c).null_count() / total_linhas * 100).alias(c) for c in df_transformed.columns]
    ).collect()
    
    print("\n=== RELATÓRIO TÉCNICO: % DE MISSING VALUES ===")
    for col_name in df_missing.columns:
        print(f"Coluna {col_name:18}: {df_missing[col_name][0]:.4f}% ausente")
    print("==============================================\n")

    # Escrita otimizada direta em disco via streaming
    df_transformed.sink_parquet(PARQUET_FINAL)
    print(f"-> Sucesso: Base tratada gravada em: {PARQUET_FINAL}")


def gerar_visualizacoes_interativas():
    """
    Gera representações computacionais complexas agregando volumetria massiva no Polars
    e gerando objetos JSON leves mapeados via Plotly Engine.
    """
    print("[3/3] Computando agregações gráficas e renderizando HTMLs dinâmicos...")
    
    lf = pl.scan_parquet(PARQUET_FINAL)

    # -------------------------------------------------------------------------
    # Visualização 1: Heatmap de Desempenho Condicional por Faixa de Renda
    # -------------------------------------------------------------------------
    print("-> Renderizando Visualização 1: Heatmap Renda x Áreas do Conhecimento...")
    df_heatmap = (
        lf.group_by("RENDA_DESC")
        .agg([
            pl.col("NU_NOTA_MT").mean().alias("Matemática"),
            pl.col("NU_NOTA_CN").mean().alias("Ciências da Natureza"),
            pl.col("NU_NOTA_CH").mean().alias("Ciências Humanas"),
            pl.col("NU_NOTA_LC").mean().alias("Linguagens e Códigos"),
            pl.col("NU_NOTA_REDACAO").mean().alias("Redação")
        ])
        .drop_nulls()
        .sort("RENDA_DESC")
        .collect()
    )

    renda_labels = df_heatmap["RENDA_DESC"].to_list()
    materias = ["Matemática", "Ciências da Natureza", "Ciências Humanas", "Linguagens e Códigos", "Redação"]
    z_matrix = [df_heatmap[m].to_list() for m in materias]

    fig_heat = go.Figure(data=go.Heatmap(
        z=z_matrix, x=renda_labels, y=materias,
        colorscale='Viridis',
        text=[[f"{val:.1f}" for val in row] for row in z_matrix],
        texttemplate="%{text}",
        colorbar=dict(title="Média")
    ))
    fig_heat.update_layout(
        title='Análise Multivariada: Matriz de Desempenho por Faixa Socioeconômica',
        xaxis_title='Indicador de Renda Familiar Mapeado',
        yaxis_title='Componente Avaliada',
        template='plotly_white'
    )
    fig_heat.write_html("heatmap_renda_notas.html")

    # -------------------------------------------------------------------------
    # Visualização 2: Parallel Coordinates (Caminhos de Desempenho por Perfil)
    # -------------------------------------------------------------------------
    print("-> Renderizando Visualização 2: Parallel Coordinates Multivariado...")
    df_parallel = (
        lf.group_by(["RACA_DESC", "SEXO_DESC"])
        .agg([
            pl.col("NU_NOTA_CN").mean().alias("CN"),
            pl.col("NU_NOTA_CH").mean().alias("CH"),
            pl.col("NU_NOTA_LC").mean().alias("LC"),
            pl.col("NU_NOTA_MT").mean().alias("MT"),
            pl.col("NU_NOTA_REDACAO").mean().alias("RED"),
            pl.col("MEDIA_GERAL").mean().alias("Geral")
        ])
        .drop_nulls()
        .collect()
    )

    # Conversão física categórica mapeada para o canal de cor continuo
    df_parallel = df_parallel.with_columns(
        pl.col("RACA_DESC").cast(pl.Categorical).to_physical().alias("RACA_ID")
    )
    pandas_df = df_parallel.to_pandas()

    fig_parallel = px.parallel_coordinates(
        pandas_df, color="RACA_ID",
        dimensions=['CN', 'CH', 'LC', 'MT', 'RED', 'Geral'],
        color_continuous_scale=px.colors.diverging.Tealrose,
        title="Coordenadas Paralelas: Vetores de Desempenho por Perfis Demográficos"
    )
    fig_parallel.update_layout(template='plotly_dark')
    fig_parallel.write_html("parallel_coordinates_enem.html")
    
    print("-> Sucesso: Arquivos HTML interativos ('heatmap_renda_notas.html' e 'parallel_coordinates_enem.html') gerados na raiz.")


if __name__ == "__main__":
    # Execução sequencial otimizada do pipeline de dados
    executar_ingestao_e_join()
    executar_limpeza_e_transformacao()
    gerar_visualizacoes_interativas()
    print("\n Pipeline concluído com sucesso e sem estouro de memória!")