import streamlit as st
import pandas as pd
import requests

# Configuração da Página
st.set_page_config(
    page_title="PharmUp Search Engine",
    page_icon="💊",
    layout="wide"
)

# --- 1. CARREGAMENTO DOS DADOS (BLINDADO) ---
@st.cache_data(ttl=60)
def load_data():
    """
    Lê os dados e renomeia as colunas pela POSIÇÃO, ignorando os nomes originais.
    Col 0 -> Chave de Busca
    Col 1 -> Endereço
    """
    # Recupera links dos Secrets
    try:
        url_lotes = st.secrets["url_lotes"]
        url_produtos = st.secrets["url_produtos"]
    except Exception:
        st.error("⚠️ Configure os Secrets (url_lotes e url_produtos) no painel do Streamlit!")
        return pd.DataFrame(), pd.DataFrame()

    df_lotes = pd.DataFrame()
    df_produtos = pd.DataFrame()

    # --- CARREGA LOTES (Tabela 1) ---
    try:
        df_lotes = pd.read_csv(url_lotes)
        
        # Se tiver pelo menos 2 colunas, renomeia pela posição
        if len(df_lotes.columns) >= 2:
            # Pega o nome atual da coluna 0 e da coluna 1
            nome_col0 = df_lotes.columns[0]
            nome_col1 = df_lotes.columns[1]
            
            # Renomeia para nosso padrão interno
            df_lotes = df_lotes.rename(columns={nome_col0: 'lote_ref', nome_col1: 'endereco_ref'})
            
            # Limpeza dos dados
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
            df_lotes['endereco_ref'] = df_lotes['endereco_ref'].astype(str).str.strip()
        else:
            st.error(f"Erro: A planilha de Lotes tem menos de 2 colunas.")
            
    except Exception as e:
        st.error(f"Falha ao carregar Lotes (Link CSV inválido?): {e}")

    # --- CARREGA PRODUTOS (Tabela 2) ---
    try:
        df_produtos = pd.read_csv(url_produtos)
        
        if len(df_produtos.columns) >= 2:
            # Pega o nome atual da coluna 0 e da coluna 1
            nome_col0 = df_produtos.columns[0]
            nome_col1 = df_produtos.columns[1]
            
            # Renomeia
            df_produtos = df_produtos.rename(columns={nome_col0: 'produto_ref', nome_col1: 'endereco_ref'})
            
            # Limpeza
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
            df_produtos['endereco_ref'] = df_produtos['endereco_ref'].astype(str).str.strip()
        else:
            st.error(f"Erro: A planilha de Produtos tem menos de 2 colunas.")

    except Exception as e:
        st.error(f"Falha ao carregar Produtos (Link CSV inválido?): {e}")

    return df_lotes, df_produtos

# --- 2. INTEGRAÇÃO COM A API PHARMUP ---
def search_pharmup_api(search_term):
    try:
        config = st.secrets["pharmup"]
        api_url = config["url"]
        headers = {
            "User-Agent": config["user_agent"],
            "Referer": config["referer"],
            "Origin": config["origin"],
            "Host": config["host"]
        }
    except Exception:
        st.error("Erro nos Secrets do PharmUp.")
        return []
    
    params = {
        "filterKey": search_term,
        "sortKey": "descricao",
        "sortOrder": "asc",
        "pageIndex": 1,
        "pageSize": 50
    }

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('list', [])
        return []
    except Exception:
        return []

# --- 3. LÓGICA DE CRUZAMENTO ---
def process_results(api_results, df_lotes, df_produtos):
    processed_data = []

    for item in api_results:
        # Dados da API PharmUp
        lote_api = str(item.get('descricao', '')).strip()
        nome_produto = str(item.get('produtoDescricao', '')).strip()
        saldo = item.get('quantidadeAtual', 0)
        unidade = item.get('unidadeMedidaSigla', '')
        raw_date = item.get('dataValidade', '')
        validade = raw_date[:10] if raw_date else ""

        endereco = "NÃO LOCALIZADO"
        origem_endereco = "---"
        cor_destaque = "red"

        # 1. TENTA BUSCAR PELO LOTE (Tabela 1 - Fracionamento)
        # Verifica se carregou corretamente antes de buscar
        if not df_lotes.empty and 'lote_ref' in df_lotes.columns:
            # Busca exata do lote
            match_lote = df_lotes[df_lotes['lote_ref'] == lote_api.upper()]
            
            if not match_lote.empty:
                locais = match_lote['endereco_ref'].unique()
                endereco = ", ".join(map(str, locais))
                origem_endereco = "🎯 Lote (Fracionamento)"
                cor_destaque = "green"
        
        # 2. SE FALHAR, TENTA PELA DESCRIÇÃO (Tabela 2 - Spex)
        if cor_destaque == "red" and not df_produtos.empty and 'produto_ref' in df_produtos.columns:
            # Busca se o nome da planilha está DENTRO do nome do PharmUp
            # Ex: Planilha tem "DIPIRONA", PharmUp tem "DIPIRONA SODICA". Vai achar.
            match_desc = df_produtos[df_produtos['produto_ref'].apply(lambda x: x in nome_produto.upper())]
            
            # Se não achou, tenta o inverso (Nome do PharmUp dentro da Planilha)
            if match_desc.empty:
                 match_desc = df_produtos[df_produtos['produto_ref'].str.contains(nome_produto.upper(), regex=False, na=False)]

            if not match_desc.empty:
                locais = match_desc['endereco_ref'].unique()
                endereco = ", ".join(map(str, locais))
                origem_endereco = "📦 Descrição (Spex)"
                cor_destaque = "orange"

        processed_data.append({
            "Produto": nome_produto,
            "Lote": lote_api,
            "Saldo": f"{saldo} {unidade}",
            "Validade": validade,
            "Endereço": endereco,
            "Fonte": origem_endereco,
            "Color": cor_destaque
        })
    
    return processed_data

# --- 4. FRONTEND ---
def main():
    st.title("🔍 Localizador de Estoque PharmUp")
    
    # Carregamento
    df_lotes, df_produtos = load_data()

    # --- DEBUG VISUAL (Para verificar se carregou) ---
    with st.expander("🛠️ Debug: Ver Tabelas Carregadas"):
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Tabela Lotes (Fracionamento):**")
            if df_lotes.empty:
                st.error("❌ Tabela vazia ou erro no Link CSV.")
            else:
                st.dataframe(df_lotes.head(3))
                st.caption(f"Colunas detectadas: {list(df_lotes.columns)}")
        
        with c2:
            st.write("**Tabela Produtos (Spex):**")
            if df_produtos.empty:
                st.error("❌ Tabela vazia ou erro no Link CSV.")
            else:
                st.dataframe(df_produtos.head(3))
                st.caption(f"Colunas detectadas: {list(df_produtos.columns)}")

    # Busca
    search_query = st.text_input("", placeholder="Digite Nome ou Lote...")

    if st.button("Pesquisar") or search_query:
        if len(search_query) < 2:
            st.warning("Digite pelo menos 2 caracteres.")
        else:
            with st.spinner("Buscando no PharmUp..."):
                api_data = search_pharmup_api(search_query)
                
                if not api_data:
                    st.info("Nenhum resultado encontrado no PharmUp.")
                else:
                    final_results = process_results(api_data, df_lotes, df_produtos)
                    
                    st.success(f"Encontrados {len(final_results)} registros.")

                    for row in final_results:
                        with st.container():
                            c1, c2, c3, c4 = st.columns([2, 1.5, 1, 2])
                            with c1:
                                st.subheader(row['Produto'])
                                st.code(f"Lote: {row['Lote']}")
                            with c2:
                                st.metric("Saldo", row['Saldo'])
                                st.caption(f"Val: {row['Validade']}")
                            with c3:
                                st.caption(row['Fonte'])
                            with c4:
                                if row['Color'] == 'green':
                                    st.success(f"📍 {row['Endereço']}")
                                elif row['Color'] == 'orange':
                                    st.warning(f"📍 {row['Endereço']}")
                                else:
                                    st.error("📍 Sem Endereço")
                            st.divider()

if __name__ == "__main__":
    main()
