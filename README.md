# Dashboard de Análise de Produção Científica

Este projeto é uma ferramenta de análise de dados desenvolvida em Python e Streamlit para processar, filtrar e visualizar a produção bibliográfica de pesquisadores, comparando-a com critérios da Qualis/CAPES.

## Funcionalidades

- **Filtragem Automática**: Remove publicações cujos ISSNs não constam na lista Qualis de referência.
- **Normalização de Dados**: Padronização de nomes de pesquisadores e remoção de acentos.
- **Análise Multidimensional**:
  - Linha do Tempo (Timeline)
  - Radar de Estratos (A1, A2, etc.)
  - Gráfico Ternário (Distribuição Proporcional)
  - Clusters de Similaridade (K-Means + PCA)
- **Análise de Grupos**: Métricas agregadas por linha de pesquisa.

## Estrutura do Projeto

O projeto segue uma arquitetura modular:

- `app.py`: Interface do usuário (Frontend Streamlit).
- `src/config.py`: Definições de pesos e grupos de pesquisa.
- `src/processor.py`: Lógica de ingestão de dados, leitura de ZIP e filtragem.
- `src/utils.py`: Funções auxiliares de limpeza de texto e ISSN.

## Pré-requisitos

- Python 3.8 ou superior.

## Instalação e Execução

Siga os passos abaixo para rodar o projeto em um ambiente isolado (Virtual Environment).

### 1. Criar o Ambiente Virtual

No terminal (dentro da pasta do projeto):

**Linux:**
```bash
python -m venv venv
```

### 2. Ativar o ambiente Virtual
```bash
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Executar o Dashboard
```bash
streamlit run app.py
```

O navegador abrirá automaticamente no endereço http://localhost:8501.

## Como Usar

- No menu lateral, faça o upload do arquivo Excel de referência (lista_qualis_educacao.xlsx).
- Na área principal, faça o upload do arquivo .zip contendo os CSVs dos pesquisadores.
- Aguarde o processamento e navegue pelas abas "Individual", "Grupos" e "Auditoria".
