import streamlit as st
import pandas as pd
from supabase import create_client
import time

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Controle de Estoque", 
    page_icon="📦", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS para melhorar a aparência
st.markdown("""
<style>
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
    /* Destaca linhas com descrição vazia */
    .element-container:has(> iframe) {
        border: 1px solid #ddd;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro de Conexão: {e}")
        return None

supabase = init_supabase()

# --- 2. FUNÇÕES DE DADOS ---
def carregar_estoque():
    """Baixa tabela e trata dados"""
    try:
        response = supabase.table("estoque_unificado").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            # Tratamento de Nulos e 'NAN'
            # Se for nulo ou 'NAN', coloca um placeholder visível para edição
            df['descricao'] = df['descricao'].fillna('').replace(['NAN', 'nan'], '')
            df['lote'] = df['lote'].fillna('').replace(['NAN', 'nan'], '')
            df['endereco'] = df['endereco'].fillna('')
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return pd.DataFrame()

def adicionar_item(lote, descricao, endereco, origem):
    try:
        supabase.table("estoque_unificado").insert({
            "lote": lote.upper().strip() if lote else None,
            "descricao": descricao.upper().strip(),
            "endereco": endereco.upper().strip(),
            "origem": origem
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar: {e}")
        return False

def atualizar_item(id_item, dados):
    try:
        supabase.table("estoque_unificado").update(dados).eq("id", id_item).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
        return False

def excluir_item(id_item):
    try:
        supabase.table("estoque_unificado").delete().eq("id", id_item).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False

# --- 3. JANELAS MODAIS (DIALOGS) ---
@st.dialog("➕ Adicionar Novo Item")
def dialog_adicionar():
    st.write("Preencha os dados do novo material:")
    with st.form("form_add", clear_on_submit=True):
        c1, c2 = st.columns(2)
        lote = c1.text_input("Lote (Opcional)")
        endereco = c2.text_input("Endereço *", placeholder="Ex: A-10")
        descricao = st.text_input("Descrição / Produto *", placeholder="Ex: DIPIRONA 500MG")
        origem = st.selectbox("Origem", ["MANUAL", "FRACIONAMENTO", "SPEX/GENERICO"])
        
        submitted = st.form_submit_button("Salvar Item", type="primary", use_container_width=True)
        
        if submitted:
            if not descricao or not endereco:
                st.error("Preencha Descrição e Endereço!")
            else:
                if adicionar_item(lote, descricao, endereco, origem):
                    st.toast("✅ Item adicionado com sucesso!")
                    st.cache_data.clear() # Força recarregar os dados
                    time.sleep(1)
                    st.rerun()

@st.dialog("✏️ Editar Item")
def dialog_editar(item):
    st.caption(f"Editando ID: {item['id']}")
    
    with st.form("form_edit"):
        c1, c2 = st.columns(2)
        # Garante que os valores não sejam None para não quebrar o input
        val_lote = item['lote'] if item['lote'] else ""
        val_end = item['endereco'] if item['endereco'] else ""
        val_desc = item['descricao'] if item['descricao'] else ""
        
        novo_lote = c1.text_input("Lote", value=val_lote)
        novo_end = c2.text_input("Endereço", value=val_end)
        nova_desc = st.text_input("Descrição", value=val_desc)
        
        # Tenta manter a origem atual, se não, usa padrão
        opcoes_origem = ["FRACIONAMENTO", "SPEX/GENERICO", "MANUAL"]
        idx_origem = 0
        if item['origem'] in opcoes_origem:
            idx_origem = opcoes_origem.index(item['origem'])
            
        nova_origem = st.selectbox("Origem", opcoes_origem, index=idx_origem)
        
        st.divider()
        col_salvar, col_del = st.columns([3, 1])
        
        save = col_salvar.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        delete = col_del.form_submit_button("🗑️ Excluir Item", type="secondary", use_container_width=True)
        
        if save:
            dados = {
                "lote": novo_lote.upper().strip(),
                "endereco": novo_end.upper().strip(),
                "descricao": nova_desc.upper().strip(),
                "origem": nova_origem
            }
            if atualizar_item(item['id'], dados):
                st.toast("✅ Atualizado!")
                st.rerun()
        
        if delete:
            if excluir_item(item['id']):
                st.toast("🗑️ Item excluído!")
                st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
def main():
    # Cabeçalho
    col_title, col_add = st.columns([6, 1], gap="small")
    with col_title:
        st.title("📦 Controle de Estoque")
    with col_add:
        st.write("") # Espaçamento
        if st.button("➕ Novo Item", type="primary", use_container_width=True):
            dialog_adicionar()

    # Carregamento dos dados
    df = carregar_estoque()
    
    # Barra de Pesquisa
    busca = st.text_input("🔎 Pesquisar no Estoque", placeholder="Digite nome, lote ou endereço...", label_visibility="collapsed")
    
    # Filtro local
    df_show = df.copy()
    if not df.empty and busca:
        termo = busca.upper()
        mask = (
            df_show['descricao'].str.upper().str.contains(termo, na=False) |
            df_show['lote'].str.upper().str.contains(termo, na=False) |
            df_show['endereco'].str.upper().str.contains(termo, na=False)
        )
        df_show = df_show[mask]

    st.caption(f"Encontrados: **{len(df_show)}** itens")

    # TABELA INTERATIVA
    # A correção do erro está aqui: selection_mode="single-row" (com hífen)
    event = st.dataframe(
        df_show,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small", disabled=True),
            "lote": st.column_config.TextColumn("📦 Lote", width="medium"),
            "descricao": st.column_config.TextColumn("📝 Descrição", width="large"),
            "endereco": st.column_config.TextColumn("📍 Endereço", width="small"),
            "origem": st.column_config.Column("🏷️ Origem", width="small"),
            "created_at": None
        },
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",  # CORRIGIDO: hífen em vez de underline
        on_select="rerun",
        height=500
    )

    # Lógica de Seleção -> Abrir Edição
    # Verifica se houve seleção de linha
    if len(event.selection["rows"]) > 0:
        index_selecionado = event.selection["rows"][0]
        # Recupera a linha correta do dataframe filtrado
        item_selecionado = df_show.iloc[index_selecionado]
        
        # Mostra botão de ação fixo ou mensagem
        st.info(f"Item selecionado: **{item_selecionado['descricao']}**")
        
        # Botão para abrir o modal de edição
        if st.button("✏️ Editar Item Selecionado", type="primary", use_container_width=True, key="btn_edit_main"):
            dialog_editar(item_selecionado)

if __name__ == "__main__":
    main()
