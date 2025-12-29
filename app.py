import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Monitor PharmUp", page_icon="💊", layout="wide")

# --- 1. CARREGAMENTO DOS DADOS (GOOGLE SHEETS) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        url_lotes = st.secrets["url_lotes"]
        url_produtos = st.secrets["url_produtos"]
    except:
        st.error("❌ ERRO CRÍTICO: Secrets não configurados.")
        return pd.DataFrame(), pd.DataFrame()

    df_lotes = pd.DataFrame()
    df_produtos = pd.DataFrame()

    # Tabela 1: Lotes
    try:
        df_lotes = pd.read_csv(url_lotes)
        if len(df_lotes.columns) >= 2:
            # Pega 1ª e 2ª coluna independente do nome
            df_lotes = df_lotes.iloc[:, :2] 
            df_lotes.columns = ['lote_ref', 'endereco_ref']
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
    except Exception as e:
        st.warning(f"⚠️ Aviso na Tabela Lotes: {e}")

    # Tabela 2: Produtos
    try:
        df_produtos = pd.read_csv(url_produtos)
        if len(df_produtos.columns) >= 2:
            # Pega 1ª e 2ª coluna independente do nome ("Produtos", "Descricao", etc)
            df_produtos = df_produtos.iloc[:, :2]
            df_produtos.columns = ['produto_ref', 'endereco_ref']
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
    except Exception as e:
        st.warning(f"⚠️ Aviso na Tabela Produtos: {e}")

    return df_lotes, df_produtos

# --- 2. CONEXÃO COM PHARMUP ---
def search_pharmup_api(search_term):
    # Carrega configurações
    try:
        config = st.secrets["pharmup"]
        api_url = config["url"].strip('"') # Remove aspas extras se houver
        headers = {
            "User-Agent": config["user_agent"].strip('"'),
            "Referer": config["referer"].strip('"'),
            "Origin": config["origin"].strip('"'),
            "Host": config["host"].strip('"')
        }
    except:
        return [], 0, "Erro: Verifique o arquivo secrets.toml (seção [pharmup])"

    params = {
        "filterKey": search_term,
        "sortKey": "descricao",
        "sortOrder": "asc",
        "pageIndex": 1,
        "pageSize": 50
    }

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        try:
            data = response.json().get('list', [])
        except:
            data = []
        return data, response.status_code, response.text
    except Exception as e:
        return [], 0, str(e)

# --- 3. TELA PRINCIPAL ---
def main():
    st.title("💊 Localizador PharmUp (Modo Diagnóstico)")
    
    # Status das Tabelas
    df_lotes, df_produtos = load_data()
    c1, c2 = st.columns(2)
    if not df_lotes.empty:
        c1.success(f"✅ Tabela Lotes: {len(df_lotes)} linhas")
    else:
        c1.error("❌ Tabela Lotes Vazia")
        
    if not df_produtos.empty:
        c2.success(f"✅ Tabela Produtos: {len(df_produtos)} linhas")
    else:
        c2.error("❌ Tabela Produtos Vazia")

    # Busca
    search_query = st.text_input("Pesquisar Produto ou Lote", placeholder="Ex: CICLOSPORINA")

    if st.button("Buscar") or search_query:
        st.divider()
        with st.spinner("Conectando ao PharmUp..."):
            api_data, status, raw_text = search_pharmup_api(search_query)

        # --- DIAGNÓSTICO DO ERRO ---
        if not api_data:
            st.error("🚫 Nenhum resultado retornado pela API.")
            
            with st.expander("🕵️‍♂️ CLIQUE AQUI PARA VER O MOTIVO", expanded=True):
                st.write(f"**Status Code:** {status}")
                
                if status == 200:
                    st.warning("O site respondeu OK, mas não achou o produto. Tente pesquisar 'CICLOSPORINA' (igual ao log que você mandou).")
                    st.code(raw_text) # Mostra o JSON vazio
                elif status == 403 or status == 500:
                    st.error("BLOQUEIO: O PharmUp recusou a conexão. Verifique os Secrets.")
                elif status == 0:
                    st.error(f"ERRO DE CÓDIGO: {raw_text}")
        
        # --- SUCESSO ---
        else:
            st.success(f"Encontrados {len(api_data)} itens!")
            
            for item in api_data:
                # Dados da API
                nome = str(item.get('produtoDescricao', 'Unknown')).strip()
                lote = str(item.get('descricao', 'Unknown')).strip()
                saldo = item.get('quantidadeAtual', 0)
                
                # Cruzamento
                locais = []
                origem = "N/A"
                cor = "gray"

                # 1. Tenta Lote
                if not df_lotes.empty:
                    match = df_lotes[df_lotes['lote_ref'] == lote.upper()]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Lote (Exato)"
                        cor = "green"

                # 2. Tenta Produto
                if not locais and not df_produtos.empty:
                    match = df_produtos[df_produtos['produto_ref'].str.contains(nome.upper(), na=False)]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Nome (Aproximado)"
                        cor = "orange"

                end_str = ", ".join(map(str, locais)) if len(locais) > 0 else "Não Localizado"
                
                # Card Visual
                st.markdown(f"""
                <div style="border:1px solid #ddd; padding:10px; border-radius:8px; border-left: 5px solid {cor}; margin-bottom:10px">
                    <h4 style="margin:0">{nome}</h4>
                    <p style="margin:0">Lote: <b>{lote}</b> | Saldo: <b>{saldo}</b></p>
                    <p style="margin:0; font-size:1.1em">📍 <b>{end_str}</b> <span style="font-size:0.8em; color:#666">({origem})</span></p>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
