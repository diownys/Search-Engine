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
            df_lotes = df_lotes.iloc[:, :2]
            df_lotes.columns = ['lote_ref', 'endereco_ref']
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
    except Exception:
        pass

    # Tabela 2: Produtos
    try:
        df_produtos = pd.read_csv(url_produtos)
        if len(df_produtos.columns) >= 2:
            df_produtos = df_produtos.iloc[:, :2]
            df_produtos.columns = ['produto_ref', 'endereco_ref']
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
    except Exception:
        pass

    return df_lotes, df_produtos

# --- 2. GESTÃO DO TOKEN ---
def get_valid_token():
    """
    Tenta pegar o token manual primeiro. Se não tiver, tenta login automático.
    """
    config = st.secrets["pharmup"]
    
    # 1. Prioridade: Token Manual (Do Secrets)
    manual = config.get("token_manual")
    if manual and len(manual) > 10:
        return manual.strip().strip('"')

    # 2. Fallback: Login Automático (Se manual não existir)
    # (Código de login simplificado para caso de uso futuro)
    return None

# --- 3. CONEXÃO COM A API ---
def search_pharmup_api(search_term):
    token = get_valid_token()
    
    if not token:
        return [], 401, "Token Manual não configurado no Secrets."

    try:
        config = st.secrets["pharmup"]
        # Endpoint de Listagem
        api_url = f"{config['base_url']}/ProdutoLote/ListProdutoLote"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": config["user_agent"],
            "Referer": config["referer"],
            "Origin": config["origin"],
            "Host": "pharmup-industria-api.azurewebsites.net"
        }
    except:
        return [], 0, "Erro Config Secrets"

    # Parâmetros exatos que você mandou no log
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
            try:
                # O JSON vem como { "list": [...], "total": ... }
                data = response.json()
                lista_produtos = data.get('list', [])
                return lista_produtos, 200, "OK"
            except:
                return [], 200, "Erro ao ler JSON"
        else:
            return [], response.status_code, response.text
            
    except Exception as e:
        return [], 0, str(e)

# --- 4. TELA PRINCIPAL ---
def main():
    st.title("💊 Localizador PharmUp")
    
    df_lotes, df_produtos = load_data()

    # Status
    c1, c2 = st.columns(2)
    if df_lotes.empty: c1.warning("⚠️ Lotes Offline")
    if df_produtos.empty: c2.warning("⚠️ Produtos Offline")

    # Campo de busca (já sugerindo o termo do seu log)
    search_query = st.text_input("Pesquisar", placeholder="Ex: 2024112901 ou TEOFILINA")

    if st.button("Buscar") or search_query:
        with st.spinner("Consultando PharmUp..."):
            api_data, status, raw_text = search_pharmup_api(search_query)

        # Se falhar
        if status != 200:
            st.error(f"Erro na API: {status}")
            if status == 401:
                st.info("💡 Dica: O Token expirou. Pegue um novo token no navegador (F12 > Network) e atualize o 'token_manual' no Secrets.")
            with st.expander("Ver Detalhes Técnicos"):
                st.text(raw_text)
        
        # Se voltar vazio
        elif not api_data:
            st.warning("Nenhum registro encontrado para essa busca.")
            
        # Se der certo
        else:
            st.success(f"Encontrados {len(api_data)} itens")
            
            for item in api_data:
                # Extraindo dados conforme seu JSON
                nome = str(item.get('produtoDescricao', 'Unknown')).strip()
                lote = str(item.get('descricao', 'Unknown')).strip()
                saldo = item.get('quantidadeAtual', 0)
                unidade = item.get('unidadeMedidaSigla', '')
                validade = item.get('dataValidade', '')[:10] # Pega só a data

                # Cruzamento de Dados
                locais = []
                origem = ""
                cor_bg = "#f9f9f9"
                cor_border = "#ddd"

                # 1. Busca na Tabela de Lotes (Prioridade)
                if not df_lotes.empty:
                    # Tenta bater o lote exato
                    match = df_lotes[df_lotes['lote_ref'] == lote.upper()]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Lote Exato"
                        cor_bg = "#d4edda" # Verde
                        cor_border = "#c3e6cb"

                # 2. Busca na Tabela de Produtos (Se não achou por lote)
                if not locais and not df_produtos.empty:
                    # Verifica se o nome do produto contém o termo da planilha
                    match = df_produtos[df_produtos['produto_ref'].apply(lambda x: x in nome.upper())]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Nome Aproximado"
                        cor_bg = "#fff3cd" # Amarelo
                        cor_border = "#ffeeba"

                end_str = " | ".join(map(str, locais)) if len(locais) > 0 else "Não Localizado"
                
                # Card Visual
                st.markdown(f"""
                <div style="background-color: {cor_bg}; padding:15px; border-radius:8px; margin-bottom:12px; border:1px solid {cor_border}; color:black;">
                    <h4 style="margin:0 0 10px 0; color:#333;">{nome}</h4>
                    <div style="display:flex; flex-wrap:wrap; gap:15px; font-size:0.95em;">
                        <span>📦 <b>Lote:</b> {lote}</span>
                        <span>📊 <b>Saldo:</b> {saldo} {unidade}</span>
                        <span>📅 <b>Val:</b> {validade}</span>
                    </div>
                    <hr style="margin:10px 0; border-color:rgba(0,0,0,0.1);">
                    <div style="font-size:1.1em; font-weight:bold; color:#000;">
                        📍 {end_str} 
                        <span style="font-size:0.7em; font-weight:normal; color:#555; margin-left:5px;">({origem})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
