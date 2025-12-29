import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="PharmUp Search", page_icon="💊", layout="wide")

# --- 1. CARREGAMENTO DOS DADOS ---
@st.cache_data(ttl=60)
def load_data():
    try:
        url_lotes = st.secrets["url_lotes"]
        url_produtos = st.secrets["url_produtos"]
    except Exception:
        st.error("⚠️ Secrets não configurados!")
        return pd.DataFrame(), pd.DataFrame()

    df_lotes = pd.DataFrame()
    df_produtos = pd.DataFrame()

    # Carrega Lotes
    try:
        df_lotes = pd.read_csv(url_lotes)
        if len(df_lotes.columns) >= 2:
            df_lotes = df_lotes.rename(columns={df_lotes.columns[0]: 'lote_ref', df_lotes.columns[1]: 'endereco_ref'})
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
            df_lotes['endereco_ref'] = df_lotes['endereco_ref'].astype(str).str.strip()
    except Exception as e:
        st.error(f"Erro Lotes: {e}")

    # Carrega Produtos
    try:
        df_produtos = pd.read_csv(url_produtos)
        if len(df_produtos.columns) >= 2:
            df_produtos = df_produtos.rename(columns={df_produtos.columns[0]: 'produto_ref', df_produtos.columns[1]: 'endereco_ref'})
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
            df_produtos['endereco_ref'] = df_produtos['endereco_ref'].astype(str).str.strip()
    except Exception as e:
        st.error(f"Erro Produtos: {e}")

    return df_lotes, df_produtos

# --- 2. INTEGRAÇÃO COM DIAGNÓSTICO ---
def search_pharmup_api(search_term):
    # Debug: Mostra o que foi lido dos secrets
    try:
        config = st.secrets["pharmup"]
        # Garante que os valores são strings limpas
        api_url = config["url"].strip().strip('"') 
        headers = {
            "User-Agent": config["user_agent"].strip().strip('"'),
            "Referer": config["referer"].strip().strip('"'),
            "Origin": config["origin"].strip().strip('"'),
            "Host": config["host"].strip().strip('"')
        }
    except Exception as e:
        st.error(f"Erro ao ler Secrets PharmUp: {e}")
        return [], 0, "Erro Config"

    params = {
        "filterKey": search_term,
        "sortKey": "descricao",
        "sortOrder": "asc",
        "pageIndex": 1,
        "pageSize": 50
    }

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        # Retorna: Lista, Status Code, Texto Puro da resposta
        try:
            data = response.json().get('list', [])
        except:
            data = []
        return data, response.status_code, response.text
    except Exception as e:
        return [], 0, str(e)

# --- 3. FRONTEND ---
def main():
    st.title("💊 PharmUp Search + Debug")
    
    df_lotes, df_produtos = load_data()
    
    search_query = st.text_input("Pesquisa", placeholder="Ex: CICLOSPORINA")

    if st.button("Pesquisar") or search_query:
        # Chama API com Debug
        api_data, status_code, raw_response = search_pharmup_api(search_query)

        # --- ÁREA DE DIAGNÓSTICO (Importante) ---
        with st.expander("🛠️ Ver Diagnóstico da Conexão (Clique aqui se der erro)", expanded=True):
            c1, c2 = st.columns(2)
            c1.metric("Status Code (Esperado: 200)", status_code)
            c1.write(f"**Termo Buscado:** {search_query}")
            
            if status_code != 200:
                c2.error("Erro na comunicação com o servidor!")
                c2.code(raw_response[:500]) # Mostra o erro real
            elif not api_data:
                c2.warning("Servidor respondeu OK (200), mas a lista veio vazia.")
                c2.code(raw_response[:500]) # Mostra o JSON vazio
            else:
                c2.success("Comunicação Perfeita!")

        # --- RESULTADOS ---
        if api_data:
            st.write(f"### Resultados ({len(api_data)})")
            for item in api_data:
                nome = item.get('produtoDescricao', 'Sem Nome')
                lote = item.get('descricao', 'Sem Lote')
                saldo = item.get('quantidadeAtual', 0)
                
                # Cruzamento Simples para teste
                locais = []
                if not df_lotes.empty:
                    match = df_lotes[df_lotes['lote_ref'] == lote.strip().upper()]
                    if not match.empty:
                        locais.extend(match['endereco_ref'].unique())
                
                endereco_txt = ", ".join(map(str, locais)) if locais else "Não Localizado"
                cor = "green" if locais else "red"

                st.markdown(f"""
                <div style="padding:10px; border:1px solid #ddd; border-radius:5px; margin-bottom:10px;">
                    <b>{nome}</b> <br>
                    Lote: <code>{lote}</code> | Saldo: {saldo} <br>
                    Local: <span style='color:{cor}; font-weight:bold'>{endereco_txt}</span>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
