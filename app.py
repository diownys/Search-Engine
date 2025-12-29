import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Localizador de Estoque", page_icon="📦", layout="wide")

# CSS para replicar o estilo dos cards e botões
st.markdown("""
<style>
    .stButton button { border-radius: 8px; font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
    /* Estilo para os Cards de Resultado */
    .stock-card {
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        border: 1px solid #ccc; 
        color: black;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. CARREGAMENTO DOS DADOS ---
@st.cache_data(ttl=10) # Cache curto para atualizar rápido após edição
def load_data():
    try:
        # Lê aba LOTES (Fracionamento)
        df_lotes = conn.read(worksheet="Lotes", usecols=[0, 1, 2], ttl=0)
        df_lotes.columns = ['Lote', 'Descricao', 'Endereco']
        df_lotes['Origem'] = 'FRACIONAMENTO'
        df_lotes['ID_Linha'] = df_lotes.index

        # Lê aba PRODUTOS (Genérico)
        df_produtos = conn.read(worksheet="Produtos", usecols=[0, 1], ttl=0)
        df_produtos.columns = ['Descricao', 'Endereco']
        df_produtos['Lote'] = '' # Vazio para produtos sem lote
        df_produtos['Origem'] = 'SPEX/GENERICO'
        df_produtos['ID_Linha'] = df_produtos.index

        # Unifica
        df_total = pd.concat([df_lotes, df_produtos], ignore_index=True)
        df_total = df_total.fillna("") 
        
        # Limpeza para padronizar busca
        df_total['Descricao'] = df_total['Descricao'].astype(str).str.strip().str.upper()
        df_total['Lote'] = df_total['Lote'].astype(str).str.strip().str.upper()
        df_total['Endereco'] = df_total['Endereco'].astype(str).str.strip().str.upper()
        
        return df_total
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# --- 3. FUNÇÃO DE BUSCA LOCAL ---
def search_local(query, df):
    query = query.upper().strip()
    if query == "": return []
    
    # Filtra no DataFrame
    mask = (
        df['Descricao'].str.contains(query, na=False) | 
        df['Lote'].str.contains(query, na=False) |
        df['Endereco'].str.contains(query, na=False)
    )
    matches = df[mask]
    
    results = []
    for _, row in matches.iterrows():
        # Define cor baseada na origem (igual ao seu exemplo)
        cor = "#d1e7dd" if row['Origem'] == 'FRACIONAMENTO' else "#fff3cd"
        
        results.append({
            "nome": row['Descricao'],
            "lote": row['Lote'] if row['Lote'] else "N/A",
            "endereco": row['Endereco'],
            "origem": row['Origem'],
            "cor": cor,
            "raw_data": row # Guarda dados originais para edição
        })
    return results

# --- 4. FUNÇÃO DE SALVAR NO SHEETS ---
def salvar_no_sheets(item, novo_lote, nova_desc, novo_end):
    try:
        nome_aba = "Lotes" if item['Origem'] == "FRACIONAMENTO" else "Produtos"
        df_atual = conn.read(worksheet=nome_aba, ttl=0)
        idx = int(item['ID_Linha'])
        
        if nome_aba == "Lotes":
            df_atual.iat[idx, 0] = novo_lote
            df_atual.iat[idx, 1] = nova_desc
            df_atual.iat[idx, 2] = novo_end
        else:
            df_atual.iat[idx, 0] = nova_desc
            df_atual.iat[idx, 1] = novo_end
            
        conn.update(worksheet=nome_aba, data=df_atual)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- 5. MODAL DE EDIÇÃO ---
@st.dialog("✏️ Editar Item")
def dialog_editar(item_dict):
    item = item_dict['raw_data'] # Recupera o objeto row original
    st.caption(f"Editando: {item['Descricao']}")
    
    with st.form("form_edit"):
        c1, c2 = st.columns(2)
        
        if item['Origem'] == 'FRACIONAMENTO':
            val_lote = c1.text_input("Lote", value=item['Lote'])
        else:
            val_lote = c1.text_input("Lote", value="N/A", disabled=True)
            
        val_end = c2.text_input("Endereço", value=item['Endereco'])
        val_desc = st.text_input("Descrição / Produto", value=item['Descricao'])
        
        if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
            with st.spinner("Salvando..."):
                if salvar_no_sheets(item, val_lote, val_desc, val_end):
                    st.toast("✅ Salvo com sucesso!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()

# --- 6. INTERFACE PRINCIPAL ---
def main():
    c1, c2 = st.columns([5,1])
    with c1:
        st.title("📦 Localizador de Estoque")
        st.caption("Pesquisa e Edição Direta no Google Sheets")
    with c2:
        if st.button("🔄 Atualizar"):
            st.cache_data.clear()
            st.rerun()

    df_total = load_data()
    
    # Status
    if df_total.empty:
        st.error("❌ Erro ao carregar dados ou planilha vazia.")
    else:
        st.success(f"📚 {len(df_total)} itens carregados do Google Sheets.")

    # Campo de Busca
    search_query = st.text_input("Buscar", placeholder="Digite Nome, Lote ou Endereço...")

    if search_query:
        if len(search_query) < 2:
            st.warning("Digite pelo menos 2 letras.")
        else:
            resultados = search_local(search_query, df_total)
            
            if not resultados:
                st.info("Nenhum item encontrado.")
            else:
                st.write(f"**Encontrados {len(resultados)} registros:**")
                
                # Renderiza os Cards
                for i, item in enumerate(resultados):
                    col_card, col_btn = st.columns([5, 1])
                    
                    with col_card:
                        st.markdown(f"""
                        <div class="stock-card" style="background-color: {item['cor']};">
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
                    
                    with col_btn:
                        # Botão de editar ao lado do card
                        st.write("") # Espaço para alinhar
                        st.write("")
                        if st.button("✏️", key=f"btn_{i}", help="Editar este item"):
                            dialog_editar(item)

if __name__ == "__main__":
    main()
