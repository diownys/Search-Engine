import streamlit as st
import pandas as pd

st.set_page_config(page_title="Localizador de Estoque", page_icon="📦", layout="wide")

# --- 1. CARREGAMENTO DOS DADOS (GOOGLE SHEETS) ---
@st.cache_data(ttl=60)
def load_data():
    """
    Carrega as planilhas e padroniza as colunas pela posição.
    """
    try:
        url_lotes = st.secrets["url_lotes"]
        url_produtos = st.secrets["url_produtos"]
    except:
        st.error("❌ Secrets não configurados.")
        return pd.DataFrame(), pd.DataFrame()

    df_lotes = pd.DataFrame()
    df_produtos = pd.DataFrame()

    # --- Tabela 1: LOTES (3 Colunas: Lote, Descrição, Endereço) ---
    try:
        df_lotes = pd.read_csv(url_lotes)
        # Verifica se tem pelo menos 3 colunas
        if len(df_lotes.columns) >= 3:
            # Pega as 3 primeiras, não importa o nome
            df_lotes = df_lotes.iloc[:, :3]
            df_lotes.columns = ['lote', 'descricao', 'endereco']
            
            # Limpeza
            df_lotes['lote'] = df_lotes['lote'].astype(str).str.strip().str.upper()
            df_lotes['descricao'] = df_lotes['descricao'].astype(str).str.strip().str.upper()
            df_lotes['endereco'] = df_lotes['endereco'].astype(str).str.strip()
    except Exception as e:
        st.warning(f"Erro ao ler Lotes: {e}")

    # --- Tabela 2: PRODUTOS (2 Colunas: Descrição, Endereço) ---
    try:
        df_produtos = pd.read_csv(url_produtos)
        # Verifica se tem pelo menos 2 colunas
        if len(df_produtos.columns) >= 2:
            df_produtos = df_produtos.iloc[:, :2]
            df_produtos.columns = ['descricao', 'endereco']
            
            # Limpeza
            df_produtos['descricao'] = df_produtos['descricao'].astype(str).str.strip().str.upper()
            df_produtos['endereco'] = df_produtos['endereco'].astype(str).str.strip()
    except Exception as e:
        st.warning(f"Erro ao ler Produtos: {e}")

    return df_lotes, df_produtos

# --- 2. LÓGICA DE PESQUISA INTERNA ---
def search_local(query, df_lotes, df_produtos):
    query = query.upper().strip()
    results = []

    # A) Busca na Tabela de LOTES
    if not df_lotes.empty:
        # Procura no LOTE OU na DESCRIÇÃO
        mask = (
            df_lotes['lote'].str.contains(query, na=False) | 
            df_lotes['descricao'].str.contains(query, na=False)
        )
        matches = df_lotes[mask]
        
        for _, row in matches.iterrows():
            results.append({
                "origem": "Lotes (Estoque Detalhado)",
                "nome": row['descricao'],
                "lote": row['lote'],
                "endereco": row['endereco'],
                "cor": "#d1e7dd" # Verde
            })

    # B) Busca na Tabela de PRODUTOS (Backup)
    # Só busca aqui se não achou nada em lotes OU se quiser mostrar tudo misturado
    if not df_produtos.empty:
        mask = df_produtos['descricao'].str.contains(query, na=False)
        matches = df_produtos[mask]
        
        for _, row in matches.iterrows():
            results.append({
                "origem": "Produtos (Genérico)",
                "nome": row['descricao'],
                "lote": "N/A", # Essa tabela não tem lote
                "endereco": row['endereco'],
                "cor": "#fff3cd" # Amarelo
            })

    return results

# --- 3. INTERFACE ---
def main():
    st.title("📦 Localizador de Estoque (Offline)")
    st.caption("Pesquisa direta nas planilhas do Google Drive")

    df_lotes, df_produtos = load_data()

    # Indicadores de Status
    c1, c2 = st.columns(2)
    if not df_lotes.empty:
        c1.success(f"📚 Tabela Lotes: {len(df_lotes)} linhas")
    else:
        c1.error("❌ Tabela Lotes Vazia")
        
    if not df_produtos.empty:
        c2.success(f"📋 Tabela Produtos: {len(df_produtos)} linhas")
    else:
        c2.error("❌ Tabela Produtos Vazia")

    # Campo de Busca
    search_query = st.text_input("Buscar", placeholder="Digite Nome, Lote ou Código...")

    if search_query:
        if len(search_query) < 2:
            st.warning("Digite pelo menos 2 letras.")
        else:
            resultados = search_local(search_query, df_lotes, df_produtos)
            
            if not resultados:
                st.info("Nenhum item encontrado nas planilhas.")
            else:
                st.write(f"**Encontrados {len(resultados)} registros:**")
                
                for item in resultados:
                    st.markdown(f"""
                    <div style="background-color: {item['cor']}; padding:15px; border-radius:8px; margin-bottom:10px; border:1px solid #ccc; color:black;">
                        <h4 style="margin:0; color:#333;">{item['nome']}</h4>
                        <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:0.9em; color:#555;">
                            <span>📦 Lote: <b>{item['lote']}</b></span>
                            <span>📂 Fonte: {item['origem']}</span>
                        </div>
                        <hr style="margin:8px 0; border-color:rgba(0,0,0,0.1);">
                        <div style="font-size:1.2em; font-weight:bold; color:#000;">
                            📍 {item['endereco']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
