import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Consulta Supabase", page_icon="🔍", layout="wide")

# --- 1. CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro nos Secrets: {e}")
        return None

supabase = init_supabase()

# --- 2. FUNÇÕES DE BANCO DE DADOS ---
def carregar_estoque():
    """Baixa toda a tabela 'estoque_unificado' do Supabase"""
    try:
        # Seleciona tudo e ordena pelos mais recentes (maior ID)
        response = supabase.table("estoque_unificado").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        return pd.DataFrame()

def salvar_alteracoes(df_editado, df_original):
    """
    Compara o dataframe editado na tela com o original e salva as diferenças.
    Suporta: Edição de células e Adição de novas linhas.
    """
    try:
        # Iterar sobre o DF editado para achar mudanças
        for index, row in df_editado.iterrows():
            # A) SE TEM ID, É UMA LINHA EXISTENTE (EDIÇÃO)
            if row.get('id') and pd.notna(row['id']):
                # Busca a linha original correspondente para comparar
                linha_original = df_original[df_original['id'] == row['id']]
                
                if not linha_original.empty:
                    orig = linha_original.iloc[0]
                    
                    # Verifica se houve mudança em campos chave
                    if (row['endereco'] != orig['endereco'] or 
                        row['descricao'] != orig['descricao'] or 
                        row['lote'] != orig['lote'] or
                        row['origem'] != orig['origem']):
                        
                        # Atualiza no Supabase
                        supabase.table("estoque_unificado").update({
                            "endereco": row['endereco'],
                            "descricao": row['descricao'],
                            "lote": row['lote'],
                            "origem": row['origem']
                        }).eq("id", row['id']).execute()

            # B) SE NÃO TEM ID (OU É NaN), É UMA NOVA LINHA (INSERÇÃO)
            else:
                # Só insere se tiver pelo menos uma descrição preenchida
                if row['descricao']:
                    payload = {
                        "lote": row['lote'] if row['lote'] else None,
                        "descricao": row['descricao'],
                        "endereco": row['endereco'],
                        "origem": row['origem'] if row['origem'] else "MANUAL"
                    }
                    supabase.table("estoque_unificado").insert(payload).execute()
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def excluir_item(id_item):
    """Remove um item do banco pelo ID"""
    try:
        supabase.table("estoque_unificado").delete().eq("id", id_item).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False

# --- 3. INTERFACE DO USUÁRIO ---
def main():
    st.title("🔍 Consulta de Estoque (Supabase)")
    
    # Botão de Recarregar
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()

    # Carrega dados
    df = carregar_estoque()

    if df.empty:
        st.warning("O banco de dados está vazio ou não foi possível conectar.")
        # Cria estrutura vazia para não quebrar a tela
        df = pd.DataFrame(columns=["id", "lote", "descricao", "endereco", "origem"])

    # --- BARRA LATERAL DE FILTROS ---
    with st.sidebar:
        st.header("Filtros")
        filtro_origem = st.multiselect(
            "Origem do Dado", 
            options=df['origem'].unique() if not df.empty else [],
            default=df['origem'].unique() if not df.empty else []
        )
        
        st.divider()
        st.info("💡 Dica: Para adicionar um item novo, preencha a linha vazia no final da tabela.")

    # --- BARRA DE PESQUISA PRINCIPAL ---
    termo_busca = st.text_input("🔎 Pesquisar...", placeholder="Digite nome, lote ou endereço")

    # --- APLICAÇÃO DOS FILTROS (Visual apenas) ---
    df_exibicao = df.copy()

    # 1. Filtro de Texto
    if termo_busca:
        termo = termo_busca.upper()
        # Converte tudo para string e maiúsculo para buscar
        mascara = (
            df_exibicao['descricao'].astype(str).str.upper().str.contains(termo, na=False) |
            df_exibicao['lote'].astype(str).str.upper().str.contains(termo, na=False) |
            df_exibicao['endereco'].astype(str).str.upper().str.contains(termo, na=False)
        )
        df_exibicao = df_exibicao[mascara]

    # 2. Filtro de Origem
    if filtro_origem:
        df_exibicao = df_exibicao[df_exibicao['origem'].isin(filtro_origem)]

    # Mostra total encontrado
    st.caption(f"Exibindo {len(df_exibicao)} registros de {len(df)} totais.")

    # --- TABELA EDITÁVEL (DATA EDITOR) ---
    # num_rows="dynamic" permite adicionar linhas
    df_editado = st.data_editor(
        df_exibicao,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "lote": st.column_config.TextColumn("Lote", width="medium"),
            "descricao": st.column_config.TextColumn("Descrição / Produto", width="large"),
            "endereco": st.column_config.TextColumn("Endereço", width="small"),
            "origem": st.column_config.SelectboxColumn(
                "Origem",
                options=["FRACIONAMENTO", "SPEX/GENERICO", "MANUAL"],
                width="medium",
                required=True
            ),
            "created_at": st.column_config.DatetimeColumn("Criado em", disabled=True, format="DD/MM/YYYY HH:mm")
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic", 
        key="editor_estoque"
    )

    # --- BOTÃO DE SALVAR ---
    # Só mostramos o botão se houver dados na tela, para evitar salvar vazio
    col_save, col_del = st.columns([4, 1])
    
    with col_save:
        if st.button("💾 Salvar Alterações", type="primary"):
            with st.spinner("Salvando no Supabase..."):
                if salvar_alteracoes(df_editado, df):
                    st.success("Dados atualizados com sucesso!")
                    import time
                    time.sleep(1)
                    st.rerun()

    # --- ÁREA DE EXCLUSÃO (Opcional) ---
    with col_del:
        with st.popover("🗑️ Excluir Item"):
            id_para_excluir = st.number_input("ID do item para excluir", step=1, min_value=1)
            if st.button("Confirmar Exclusão"):
                if excluir_item(id_para_excluir):
                    st.toast(f"Item {id_para_excluir} excluído!")
                    st.rerun()

if __name__ == "__main__":
    main()
