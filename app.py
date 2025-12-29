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
        st.error("❌ Secrets não configurados.")
        return pd.DataFrame(), pd.DataFrame()

    df_lotes = pd.DataFrame()
    df_produtos = pd.DataFrame()

    # Tabela 1: Lotes
    try:
        df_lotes = pd.read_csv(url_lotes)
        if len(df_lotes.columns) >= 2:
            df_lotes = df_lotes.iloc[:, :2] # Pega col 1 e 2
            df_lotes.columns = ['lote_ref', 'endereco_ref']
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
    except Exception as e:
        pass # Silencia erro visual se falhar

    # Tabela 2: Produtos
    try:
        df_produtos = pd.read_csv(url_produtos)
        if len(df_produtos.columns) >= 2:
            df_produtos = df_produtos.iloc[:, :2] # Pega col 1 e 2
            df_produtos.columns = ['produto_ref', 'endereco_ref']
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
    except Exception as e:
        pass

    return df_lotes, df_produtos

# --- 2. AUTENTICAÇÃO AUTOMÁTICA (LOGIN) ---
@st.cache_data(ttl=3600) # Cache do Token por 1 hora
def get_auth_token():
    """
    Faz login no PharmUp e retorna o Token Bearer.
    """
    try:
        config = st.secrets["pharmup"]
        login_url = config["login_url"]
        
        # Envia login e senha como parâmetros na URL (Query String)
        params = {
            "login": config["username"],
            "senha": config["password"]
        }
        
        headers = {
             "User-Agent": config["user_agent"]
        }

        # Faz o POST para pegar o token
        response = requests.post(login_url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # O token vem direto no corpo da resposta ou dentro de um JSON
            try:
                # Tenta ler como JSON
                return response.json() 
            except:
                # Se não for JSON, pega o texto puro (o token bruto)
                return response.text.strip('"')
        else:
            st.error(f"Falha no Login: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Erro ao tentar logar: {e}")
        return None

# --- 3. CONEXÃO COM A BUSCA ---
def search_pharmup_api(search_term):
    # 1. Obtém o Token (faz login se precisar)
    token = get_auth_token()
    
    if not token:
        return [], 401, "Falha ao obter Token de Login"

    try:
        config = st.secrets["pharmup"]
        api_url = f"{config['base_url']}/ProdutoLote/ListProdutoLote"
        
        headers = {
            "Authorization": f"Bearer {token}", # Usa o token gerado
            "User-Agent": config["user_agent"],
            "Referer": config["referer"],
            "Origin": config["origin"],
            "Host": "pharmup-industria-api.azurewebsites.net"
        }
    except:
        return [], 0, "Erro Config Secrets"

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

# --- 4. TELA PRINCIPAL ---
def main():
    st.title("💊 Localizador PharmUp")
    
    df_lotes, df_produtos = load_data()

    # Barra de Status Discreta
    status_col1, status_col2 = st.columns(2)
    if df_lotes.empty:
        status_col1.warning("⚠️ Lotes Offline")
    if df_produtos.empty:
        status_col2.warning("⚠️ Produtos Offline")

    search_query = st.text_input("Pesquisar", placeholder="Digite Nome ou Lote...")

    if st.button("Buscar") or search_query:
        with st.spinner("Autenticando e Buscando..."):
            api_data, status, raw_text = search_pharmup_api(search_query)

        if not api_data:
            if status == 200:
                st.info("Nenhum registro encontrado para essa busca.")
            else:
                st.error(f"Erro na API: {status}")
                with st.expander("Detalhes Técnicos"):
                    st.code(raw_text)
        else:
            st.success(f"Encontrados {len(api_data)} itens")
            
            for item in api_data:
                nome = str(item.get('produtoDescricao', 'Unknown')).strip()
                lote = str(item.get('descricao', 'Unknown')).strip()
                saldo = item.get('quantidadeAtual', 0)
                
                # Lógica de Endereçamento
                locais = []
                origem = ""
                cor = "#eee" # Cinza padrão

                # 1. Lote
                if not df_lotes.empty:
                    match = df_lotes[df_lotes['lote_ref'] == lote.upper()]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Lote"
                        cor = "#d4edda" # Verde claro

                # 2. Produto (apenas se não achou por lote)
                if not locais and not df_produtos.empty:
                    # Tenta match exato ou parcial
                    match = df_produtos[df_produtos['produto_ref'].str.contains(nome.upper(), na=False)]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Nome Aprox."
                        cor = "#fff3cd" # Amarelo claro

                end_str = ", ".join(map(str, locais)) if len(locais) > 0 else "Não Localizado"
                
                # Layout do Card
                st.markdown(f"""
                <div style="background-color: {cor}; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #ccc; color: black;">
                    <h4 style="margin:0; color:black;">{nome}</h4>
                    <div style="display:flex; justify-content:space-between; margin-top:5px;">
                        <span>📦 Lote: <b>{lote}</b></span>
                        <span>📊 Saldo: <b>{saldo}</b></span>
                    </div>
                    <hr style="margin:5px 0; border-color:#bbb;">
                    <div style="font-size:1.1em;">
                        📍 <b>{end_str}</b> <small>({origem})</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
