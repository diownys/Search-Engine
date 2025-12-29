import streamlit as st
import pandas as pd
import requests

# Configuração da Página
st.set_page_config(
    page_title="PharmUp Search Engine",
    page_icon="💊",
    layout="wide"
)

# --- 1. CARREGAMENTO DOS DADOS (LINKS PÚBLICOS) ---
@st.cache_data(ttl=60) # Atualiza a cada 60 segundos
def load_data():
    """
    Lê os dados diretamente dos links CSV publicados no Google Sheets.
    """
    # URLs fornecidas por você
    url_lotes = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQxoAwleQXfsqfCDNKjarxYFqMhO0qujcIGZMhBZHv4b_CkL7JwucqR3AbqRgHpseVCjQPCI-ywCFXj/pub?gid=0&single=true&output=csv"
    
    # Atenção: Verifique se este segundo link traz realmente a aba de produtos.
    # Geralmente links diferentes tem 'gid' diferentes.
    url_produtos = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQxoAwleQXfsqfCDNKjarxYFqMhO0qujcIGZMhBZHv4b_CkL7JwucqR3AbqRgHpseVCjQPCI-ywCFXj/pub?output=csv"

    try:
        # Carrega Lotes
        df_lotes = pd.read_csv(url_lotes)
        # Padroniza colunas para evitar erros de leitura
        df_lotes['lote_completo'] = df_lotes['lote_completo'].astype(str).str.strip().str.upper()
        
        # Carrega Produtos
        df_produtos = pd.read_csv(url_produtos)
        df_produtos['produto'] = df_produtos['produto'].astype(str).str.strip().str.upper()

        return df_lotes, df_produtos

    except Exception as e:
        st.error(f"Erro ao ler as planilhas: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 2. INTEGRAÇÃO COM A API PHARMUP ---
def search_pharmup_api(search_term):
    url = "https://pharmup-industria-api.azurewebsites.net/ProdutoLote/ListProdutoLote"
    
    params = {
        "filterKey": search_term,
        "sortKey": "descricao",
        "sortOrder": "asc",
        "pageIndex": 1,
        "pageSize": 50
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://pharmup-industria.azurewebsites.net/",
        "Origin": "https://pharmup-industria.azurewebsites.net",
        "Host": "pharmup-industria-api.azurewebsites.net"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('list', [])
        else:
            return []
    except Exception as e:
        st.error(f"Erro de conexão com PharmUp: {e}")
        return []

# --- 3. LÓGICA DE CRUZAMENTO ---
def process_results(api_results, df_lotes, df_produtos):
    processed_data = []

    for item in api_results:
        lote_api = str(item.get('descricao', '')).strip()
        nome_produto = str(item.get('produtoDescricao', '')).strip()
        saldo = item.get('quantidadeAtual', 0)
        unidade = item.get('unidadeMedidaSigla', '')
        validade = item.get('dataValidade', '')[:10]

        endereco = "NÃO LOCALIZADO"
        origem_endereco = "N/A"
        cor_destaque = "red"

        # 1. Busca LOTE (Tabela 1)
        match_lote = df_lotes[df_lotes['lote_completo'] == lote_api.upper()]
        
        if not match_lote.empty:
            if 'cod_endereco' in match_lote.columns:
                locais = match_lote['cod_endereco'].unique()
                endereco = ", ".join(map(str, locais))
                origem_endereco = "🎯 Lote Exato (Sistema)"
                cor_destaque = "green"
        
        # 2. Busca DESCRIÇÃO (Tabela 2)
        else:
            # Verifica se tem dados na tabela de produtos
            if not df_produtos.empty and 'produto' in df_produtos.columns:
                match_desc = df_produtos[df_produtos['produto'].str.contains(nome_produto.upper(), regex=False, na=False)]
                if not match_desc.empty:
                    # Tenta achar a coluna de endereço (pode ser 'Endereço', 'Local', etc)
                    cols = [c for c in df_produtos.columns if 'endere' in c.lower() or 'local' in c.lower()]
                    col_alvo = cols[0] if cols else df_produtos.columns[1]
                    
                    locais = match_desc[col_alvo].unique()
                    endereco = ", ".join(map(str, locais))
                    origem_endereco = "⚠️ Aproximado (Planilha)"
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
    
    # Carrega dados
    df_lotes, df_produtos = load_data()

    # Barra de status simples
    if not df_lotes.empty:
        st.toast(f"Base de Lotes carregada: {len(df_lotes)} registros", icon="✅")
    else:
        st.error("Falha ao carregar Lotes. Verifique o Link CSV.")

    search_query = st.text_input("", placeholder="Digite Nome ou Lote...")

    if st.button("Pesquisar") or search_query:
        if len(search_query) < 2:
            st.warning("Digite pelo menos 2 caracteres.")
        else:
            with st.spinner("Buscando..."):
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
                                st.caption(f"Lote: {row['Lote']}")
                            with c2:
                                st.metric("Saldo", row['Saldo'], delta=f"Val: {row['Validade']}")
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
