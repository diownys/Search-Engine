import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Busca PharmUp (Via Supabase)", page_icon="💊", layout="wide")

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

    try:
        df_lotes = pd.read_csv(url_lotes)
        if len(df_lotes.columns) >= 2:
            df_lotes = df_lotes.iloc[:, :2]
            df_lotes.columns = ['lote_ref', 'endereco_ref']
            df_lotes['lote_ref'] = df_lotes['lote_ref'].astype(str).str.strip().str.upper()
    except Exception: pass

    try:
        df_produtos = pd.read_csv(url_produtos)
        if len(df_produtos.columns) >= 2:
            df_produtos = df_produtos.iloc[:, :2]
            df_produtos.columns = ['produto_ref', 'endereco_ref']
            df_produtos['produto_ref'] = df_produtos['produto_ref'].astype(str).str.strip().str.upper()
    except Exception: pass

    return df_lotes, df_produtos

# --- 2. CONEXÃO COM A EDGE FUNCTION (IGUAL AO HTML) ---
def search_via_supabase(termo_busca):
    """
    Usa a Edge Function do Supabase para consultar o PharmUp.
    Isso evita o erro 401 pois a autenticação é feita pelo servidor.
    """
    try:
        config = st.secrets["supabase"]
        url = config["function_url"]
        key = config["anon_key"]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}" # Usa a Anon Key do HTML
        }
        
        # O script HTML enviava { loteCompleto: ... }
        # Vamos tentar enviar o termo pesquisado nesse campo
        body = { "loteCompleto": termo_busca }
        
        response = requests.post(url, json=body, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # SE A FUNÇÃO RETORNAR UM OBJETO ÚNICO (Como parece ser no HTML)
            # Nós transformamos ele em uma lista para o Streamlit exibir
            if "cod_material" in data:
                return [{
                    "produtoDescricao": data.get("material_descricao", "Produto Encontrado"),
                    "descricao": termo_busca, # O lote pesquisado
                    "quantidadeAtual": data.get("saldo_unidades", 0),
                    "dataValidade": data.get("data_validade", ""),
                    "unidadeMedidaSigla": "UN" # A função do HTML retorna saldo em unidades
                }], 200, "OK"
            
            # SE A FUNÇÃO RETORNAR ERRO
            if "error" in data:
                return [], 404, data["error"]
                
            return [], 200, "Formato desconhecido"
            
        else:
            return [], response.status_code, response.text

    except Exception as e:
        return [], 0, str(e)

# --- 3. TELA PRINCIPAL ---
def main():
    st.title("💊 Localizador (Modo Supabase)")
    st.info("ℹ️ Este modo usa o Proxy do seu script antigo. Ele é otimizado para busca por **LOTE COMPLETO**.")
    
    df_lotes, df_produtos = load_data()
    c1, c2 = st.columns(2)
    if df_lotes.empty: c1.warning("⚠️ Lotes Offline")
    if df_produtos.empty: c2.warning("⚠️ Produtos Offline")

    search_query = st.text_input("Pesquisar Lote", placeholder="Ex: DV25112111500203")

    if st.button("Buscar") or search_query:
        with st.spinner("Consultando via Proxy Supabase..."):
            api_data, status, raw_text = search_via_supabase(search_query)

        if not api_data:
            if status == 404 or "não encontrado" in str(raw_text).lower():
                st.warning("Lote não encontrado no PharmUp.")
            else:
                st.error(f"Erro na conexão: {status}")
                st.code(raw_text)
        else:
            st.success(f"Lote Localizado!")
            
            for item in api_data:
                nome = str(item.get('produtoDescricao', 'Unknown')).strip()
                lote = str(item.get('descricao', search_query)).strip() # Usa o termo buscado se não vier lote
                saldo = item.get('quantidadeAtual', 0)
                validade = str(item.get('dataValidade', ''))[:10]

                locais = []
                origem = ""
                cor = "#f0f2f6"

                # 1. Busca Endereço
                if not df_lotes.empty:
                    match = df_lotes[df_lotes['lote_ref'] == lote.upper()]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Planilha Lotes"
                        cor = "#d1e7dd"

                if not locais and not df_produtos.empty:
                    # Tenta achar o nome na planilha de produtos
                    match = df_produtos[df_produtos['produto_ref'].str.contains(nome.upper(), na=False)]
                    if not match.empty:
                        locais = match['endereco_ref'].unique()
                        origem = "Planilha Produtos"
                        cor = "#fff3cd"

                end_str = " | ".join(map(str, locais)) if len(locais) > 0 else "Endereço Não Localizado"
                
                st.markdown(f"""
                <div style="background-color: {cor}; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #ccc; color:black;">
                    <h4 style="margin:0; color:#black">{nome}</h4>
                    <div style="display:flex; gap: 20px; margin-top:5px; color:#333;">
                        <span>📦 Lote: <b>{lote}</b></span>
                        <span>📊 Saldo: <b>{saldo}</b></span>
                        <span>📅 Val: {validade}</span>
                    </div>
                    <hr style="margin:10px 0; border-color:#bbb;">
                    <div style="font-size:1.1em; font-weight:bold; color:black;">
                        📍 {end_str} <small>({origem})</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
