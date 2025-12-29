import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Controle de Estoque", page_icon="📗", layout="wide")

st.markdown("""
<style>
    .stButton button { border-radius: 8px; font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# --- 1. CONEXÃO (AUTOMÁTICA PELOS SECRETS) ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNÇÕES DE DADOS ---
def carregar_dados():
    try:
        # Lê a aba LOTES (Assumindo colunas: Lote, Descrição, Endereço)
        # ttl=0 garante que não pegue cache velho
        df_lotes = conn.read(worksheet="Lotes", usecols=[0, 1, 2], ttl=0)
        df_lotes.columns = ['Lote', 'Descricao', 'Endereco'] 
        df_lotes['Origem'] = 'FRACIONAMENTO'
        df_lotes['ID_Linha'] = df_lotes.index # Guarda a linha original para salvar depois

        # Lê a aba PRODUTOS (Assumindo colunas: Descrição, Endereço)
        df_produtos = conn.read(worksheet="Produtos", usecols=[0, 1], ttl=0)
        df_produtos.columns = ['Descricao', 'Endereco']
        df_produtos['Lote'] = '' # Produtos genéricos não têm lote
        df_produtos['Origem'] = 'SPEX/GENERICO'
        df_produtos['ID_Linha'] = df_produtos.index

        # Junta tudo numa tabela só para o App
        df_total = pd.concat([df_lotes, df_produtos], ignore_index=True)
        df_total = df_total.fillna("") # Limpa campos vazios
        return df_total

    except Exception as e:
        st.error(f"Erro ao carregar planilhas: {e}")
        return pd.DataFrame()

def salvar_no_sheets(item, novo_lote, nova_desc, novo_end):
    """Salva a edição na aba correta do Google Sheets"""
    try:
        # Define em qual aba vamos salvar
        nome_aba = "Lotes" if item['Origem'] == "FRACIONAMENTO" else "Produtos"
        
        # 1. Baixa a planilha atual (para não sobrescrever dados de outros usuários)
        df_atual = conn.read(worksheet=nome_aba, ttl=0)
        
        # 2. Pega o índice da linha original
        idx = int(item['ID_Linha'])
        
        # 3. Atualiza as células certas
        if nome_aba == "Lotes":
            # Lotes: Coluna A(0)=Lote, B(1)=Descrição, C(2)=Endereço
            df_atual.iat[idx, 0] = novo_lote
            df_atual.iat[idx, 1] = nova_desc
            df_atual.iat[idx, 2] = novo_end
        else:
            # Produtos: Coluna A(0)=Descrição, B(1)=Endereço
            df_atual.iat[idx, 0] = nova_desc
            df_atual.iat[idx, 1] = novo_end
            
        # 4. Envia de volta para o Google
        conn.update(worksheet=nome_aba, data=df_atual)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- 3. MODAL DE EDIÇÃO ---
@st.dialog("✏️ Editar Item")
def dialog_editar(item):
    st.caption(f"Editando item da aba: **{item['Origem']}**")
    
    with st.form("form_edit"):
        c1, c2 = st.columns(2)
        
        # Se for Fracionamento, libera edição de Lote. Se for Genérico, trava.
        if item['Origem'] == 'FRACIONAMENTO':
            val_lote = c1.text_input("Lote", value=item['Lote'])
        else:
            val_lote = c1.text_input("Lote", value="N/A", disabled=True)
            
        val_end = c2.text_input("Endereço", value=item['Endereco'])
        val_desc = st.text_input("Descrição / Produto", value=item['Descricao'])
        
        if st.form_submit_button("💾 Salvar no Google Sheets", type="primary", use_container_width=True):
            with st.spinner("Enviando para o Google..."):
                if salvar_no_sheets(item, val_lote, val_desc, val_end):
                    st.toast("✅ Salvo com sucesso!")
                    st.cache_data.clear() # Limpa cache do app
                    time.sleep(1)
                    st.rerun() # Recarrega a página

# --- 4. TELA PRINCIPAL ---
def main():
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("📦 Estoque Integrado (Google Sheets)")
    with col2:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Carrega dados
    df = carregar_dados()
    
    if df.empty:
        st.info("Conectando ao Google Sheets... (Se demorar, verifique se compartilhou a planilha com o robô)")
        return

    # Barra de Pesquisa
    busca = st.text_input("🔎 Pesquisar", placeholder="Digite nome, lote ou endereço...", label_visibility="collapsed")
    
    # Filtro local
    df_show = df.copy()
    if busca:
        termo = busca.upper()
        mask = (
            df_show['Descricao'].str.upper().str.contains(termo, na=False) |
            df_show['Lote'].str.upper().str.contains(termo, na=False) |
            df_show['Endereco'].str.upper().str.contains(termo, na=False)
        )
        df_show = df_show[mask]

    st.caption(f"Encontrados: **{len(df_show)}** registros")

    # Tabela Interativa
    event = st.dataframe(
        df_show,
        column_config={
            "Lote": st.column_config.TextColumn("📦 Lote", width="medium"),
            "Descricao": st.column_config.TextColumn("📝 Descrição", width="large"),
            "Endereco": st.column_config.TextColumn("📍 Endereço", width="small"),
            "Origem": st.column_config.Column("🏷️ Aba", width="small"),
            "ID_Linha": None # Oculto
        },
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row", # Permite selecionar 1 linha
        on_select="rerun",
        height=500
    )

    # Ação ao Selecionar
    if len(event.selection["rows"]) > 0:
        idx = event.selection["rows"][0]
        item_selecionado = df_show.iloc[idx]
        
        st.info(f"Selecionado: **{item_selecionado['Descricao']}**")
        
        if st.button("✏️ Editar Item Selecionado", type="primary", use_container_width=True):
            dialog_editar(item_selecionado)

if __name__ == "__main__":
    main()
