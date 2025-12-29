import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Localizador de Estoque", page_icon="📦", layout="wide")

# CSS: Cards, Botões e Layout
st.markdown("""
<style>
    .stButton button { border-radius: 8px; font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
    
    /* Estilo dos Cards */
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
@st.cache_data(ttl=10)
def load_data():
    try:
        # Aba LOTES
        df_lotes = conn.read(worksheet="Lotes", usecols=[0, 1, 2], ttl=0)
        df_lotes.columns = ['Lote', 'Descricao', 'Endereco']
        df_lotes['Origem'] = 'FRACIONAMENTO'
        df_lotes['ID_Linha'] = df_lotes.index

        # Aba PRODUTOS
        df_produtos = conn.read(worksheet="Produtos", usecols=[0, 1], ttl=0)
        df_produtos.columns = ['Descricao', 'Endereco']
        df_produtos['Lote'] = ''
        df_produtos['Origem'] = 'SPEX/GENERICO'
        df_produtos['ID_Linha'] = df_produtos.index

        # Unifica
        df_total = pd.concat([df_lotes, df_produtos], ignore_index=True)
        df_total = df_total.fillna("") 
        
        # Padronização
        df_total['Descricao'] = df_total['Descricao'].astype(str).str.strip().str.upper()
        df_total['Lote'] = df_total['Lote'].astype(str).str.strip().str.upper()
        df_total['Endereco'] = df_total['Endereco'].astype(str).str.strip().str.upper()
        
        return df_total
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# --- 3. BUSCA LOCAL ---
def search_local(query, df):
    query = query.upper().strip()
    if query == "": return []
    
    mask = (
        df['Descricao'].str.contains(query, na=False) | 
        df['Lote'].str.contains(query, na=False) |
        df['Endereco'].str.contains(query, na=False)
    )
    matches = df[mask]
    
    results = []
    for _, row in matches.iterrows():
        cor = "#d1e7dd" if row['Origem'] == 'FRACIONAMENTO' else "#fff3cd"
        results.append({
            "nome": row['Descricao'],
            "lote": row['Lote'] if row['Lote'] else "N/A",
            "endereco": row['Endereco'],
            "origem": row['Origem'],
            "cor": cor,
            "raw_data": row
        })
    return results

# --- 4. SALVAR EDIÇÃO ---
def salvar_edicao(item, novo_lote, nova_desc, novo_end):
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
        st.error(f"Erro ao salvar edição: {e}")
        return False

# --- 5. ADICIONAR NOVO ITEM ---
def adicionar_item(origem, lote, descricao, endereco):
    try:
        nome_aba = "Lotes" if origem == "FRACIONAMENTO" else "Produtos"
        
        # 1. Lê a tabela atual
        df_atual = conn.read(worksheet=nome_aba, ttl=0)
        
        # 2. Cria a nova linha
        if nome_aba == "Lotes":
            nova_linha = pd.DataFrame([{
                df_atual.columns[0]: lote.upper(),
                df_atual.columns[1]: descricao.upper(),
                df_atual.columns[2]: endereco.upper()
            }])
        else:
            nova_linha = pd.DataFrame([{
                df_atual.columns[0]: descricao.upper(),
                df_atual.columns[1]: endereco.upper()
            }])
            
        # 3. Adiciona ao final e salva
        df_atualizado = pd.concat([df_atual, nova_linha], ignore_index=True)
        conn.update(worksheet=nome_aba, data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar: {e}")
        return False

# --- 6. MODAIS (DIALOGS) ---
@st.dialog("✏️ Editar Item")
def dialog_editar(item_dict):
    item = item_dict['raw_data']
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
                if salvar_edicao(item, val_lote, val_desc, val_end):
                    st.toast("✅ Salvo com sucesso!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()

@st.dialog("➕ Novo Material")
def dialog_adicionar():
    st.write("Onde você quer adicionar?")
    tipo = st.radio("Tipo de Material", ["FRACIONAMENTO (Com Lote)", "GENÉRICO (Sem Lote)"], horizontal=True)
    
    origem_selecionada = "FRACIONAMENTO" if "FRACIONAMENTO" in tipo else "SPEX/GENERICO"
    
    with st.form("form_add"):
        c1, c2 = st.columns(2)
        
        # Lote só aparece se for Fracionamento
        if origem_selecionada == "FRACIONAMENTO":
            lote = c1.text_input("Lote *")
        else:
            lote = ""
            c1.info("Genéricos não possuem lote.")
            
        endereco = c2.text_input("Endereço *", placeholder="Ex: A-10")
        descricao = st.text_input("Descrição / Produto *", placeholder="Ex: DIPIRONA...")
        
        if st.form_submit_button("✅ Adicionar ao Estoque", type="primary", use_container_width=True):
            if not descricao or not endereco:
                st.warning("Preencha Descrição e Endereço!")
            elif origem_selecionada == "FRACIONAMENTO" and not lote:
                st.warning("Preencha o Lote!")
            else:
                with st.spinner("Adicionando..."):
                    if adicionar_item(origem_selecionada, lote, descricao, endereco):
                        st.toast("✅ Item criado!")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()

# --- 7. INTERFACE PRINCIPAL ---
def main():
    # Cabeçalho com Botões
    c1, c2, c3 = st.columns([6, 1, 1])
    with c1:
        st.title("📦 Localizador de Estoque")
    with c2:
        st.write("") 
        if st.button("➕ Novo", type="primary", use_container_width=True):
            dialog_adicionar()
    with c3:
        st.write("") 
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    df_total = load_data()
    
    if df_total.empty:
        st.error("❌ Erro ao carregar dados. Verifique a conexão.")
    else:
        st.caption(f"📚 {len(df_total)} itens carregados.")

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
                        st.write("") 
                        st.write("")
                        if st.button("✏️", key=f"btn_{i}", help="Editar"):
                            dialog_editar(item)

if __name__ == "__main__":
    main()
