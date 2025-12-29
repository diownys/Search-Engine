import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Gerador de Importação Supabase", page_icon="💾", layout="centered")

st.title("💾 Unificador de Tabelas para Supabase")
st.markdown("Este app baixa suas planilhas, padroniza as colunas e gera um CSV pronto para importar na tabela `estoque_unificado`.")

# --- CONFIGURAÇÃO ---
# Se já estiver nos secrets, ele pega automático. Se não, usa os links padrão (substitua se necessário).
try:
    URL_LOTES = st.secrets["url_lotes"]
    URL_PRODUTOS = st.secrets["url_produtos"]
except:
    st.warning("⚠️ Secrets não encontrados. Usando links manuais (verifique se estão certos).")
    # Cole seus links aqui se não usar secrets
    URL_LOTES = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQxoAwleQXfsqfCDNKjarxYFqMhO0qujcIGZMhBZHv4b_CkL7JwucqR3AbqRgHpseVCjQPCI-ywCFXj/pub?gid=0&single=true&output=csv"
    URL_PRODUTOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQxoAwleQXfsqfCDNKjarxYFqMhO0qujcIGZMhBZHv4b_CkL7JwucqR3AbqRgHpseVCjQPCI-ywCFXj/pub?gid=SEU_GID_AQUI&single=true&output=csv"

def gerar_csv_unificado():
    try:
        # 1. Processar Tabela de LOTES (Fracionamento)
        st.write("🔄 Lendo planilha de Lotes...")
        df_lotes = pd.read_csv(URL_LOTES)
        
        # Selecionar e Renomear colunas para o padrão do Supabase
        # Padrão Supabase: lote, descricao, endereco, origem
        
        # Verifica se as colunas existem (pelo nome ou posição)
        # Assumindo a ordem: lote_completo, produto_descricao, cod_endereco (baseado nos seus arquivos)
        # Se os nomes mudarem, podemos pegar por posição: df.iloc[:, 0] etc.
        
        # Vamos criar um DF novo limpo
        df_lotes_clean = pd.DataFrame()
        
        # Tentativa de pegar por nomes conhecidos, se falhar pega por índice
        if 'lote_completo' in df_lotes.columns:
            df_lotes_clean['lote'] = df_lotes['lote_completo']
        else:
            df_lotes_clean['lote'] = df_lotes.iloc[:, 0] # Pega a 1ª coluna
            
        if 'produto_descricao' in df_lotes.columns:
            df_lotes_clean['descricao'] = df_lotes['produto_descricao']
        else:
             # Às vezes a descrição é a 2ª coluna
            df_lotes_clean['descricao'] = df_lotes.iloc[:, 1]
            
        if 'cod_endereco' in df_lotes.columns:
            df_lotes_clean['endereco'] = df_lotes['cod_endereco']
        else:
            # Às vezes o endereço é a 3ª coluna
            df_lotes_clean['endereco'] = df_lotes.iloc[:, 2]

        df_lotes_clean['origem'] = 'FRACIONAMENTO'

        # 2. Processar Tabela de PRODUTOS (Genérico/Spex)
        st.write("🔄 Lendo planilha de Produtos...")
        df_produtos = pd.read_csv(URL_PRODUTOS)
        
        df_produtos_clean = pd.DataFrame()
        
        # Produtos não tem lote, fica vazio
        df_produtos_clean['lote'] = None 
        
        # Mapeamento
        # Assumindo: produto, Endereço
        col_desc = 'produto' if 'produto' in df_produtos.columns else df_produtos.columns[0]
        col_end = 'Endereço' if 'Endereço' in df_produtos.columns else df_produtos.columns[1]
        
        df_produtos_clean['descricao'] = df_produtos[col_desc]
        df_produtos_clean['endereco'] = df_produtos[col_end]
        df_produtos_clean['origem'] = 'SPEX/GENERICO'

        # 3. Unificar
        st.write("🔄 Unificando dados...")
        df_final = pd.concat([df_lotes_clean, df_produtos_clean], ignore_index=True)
        
        # Limpeza Final (Maiúsculas e remover espaços)
        df_final['lote'] = df_final['lote'].astype(str).str.upper().str.strip().replace('NAN', '')
        df_final['descricao'] = df_final['descricao'].astype(str).str.upper().str.strip()
        df_final['endereco'] = df_final['endereco'].astype(str).str.upper().str.strip()
        
        st.success(f"✅ Processamento concluído! Total de {len(df_final)} itens.")
        st.dataframe(df_final.head())
        
        return df_final

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None

# --- BOTÃO DE AÇÃO ---
if st.button("🚀 Gerar Arquivo de Importação", type="primary"):
    df_unificado = gerar_csv_unificado()
    
    if df_unificado is not None:
        # Converte para CSV string
        csv_buffer = df_unificado.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Baixar CSV Unificado (Pronto para Supabase)",
            data=csv_buffer,
            file_name="estoque_unificado_importacao.csv",
            mime="text/csv",
        )
        
        st.info("""
        **Como importar no Supabase:**
        1. Vá no seu projeto Supabase > Table Editor.
        2. Selecione a tabela `estoque_unificado`.
        3. Clique em **Insert** > **Import Data from CSV**.
        4. Selecione este arquivo baixado.
        """)
