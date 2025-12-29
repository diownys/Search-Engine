# --- ROTINA DE IMPORTAÇÃO (RODAR UMA VEZ) ---
def importar_dados_para_supabase():
    st.info("⏳ Iniciando importação...")
    
    # 1. Carrega Planilhas dos Links (Secrets)
    try:
        url_lotes = st.secrets["url_lotes"]
        url_produtos = st.secrets["url_produtos"]
        
        # Lê CSV Lotes
        df_lotes = pd.read_csv(url_lotes)
        # Ajuste conforme suas colunas reais do CSV Lotes
        # Mapeando: lote_completo -> lote, produto_descricao -> descricao, cod_endereco -> endereco
        df_lotes_final = pd.DataFrame({
            'lote': df_lotes.iloc[:, 0],      # 1ª Coluna (Lote)
            'descricao': df_lotes.iloc[:, 1], # 2ª Coluna (Descrição/Produto)
            'endereco': df_lotes.iloc[:, 2],  # 3ª Coluna (Endereço)
            'origem': 'FRACIONAMENTO'
        })

        # Lê CSV Produtos Genéricos
        df_produtos = pd.read_csv(url_produtos)
        # Ajuste conforme suas colunas reais do CSV Produtos
        # Mapeando: produto -> descricao, Endereço -> endereco (Sem lote)
        df_produtos_final = pd.DataFrame({
            'lote': None,                       # Não tem lote
            'descricao': df_produtos.iloc[:, 0], # 1ª Coluna (Produto)
            'endereco': df_produtos.iloc[:, 1],  # 2ª Coluna (Endereço)
            'origem': 'SPEX/GENERICO'
        })

        # Concatena tudo
        df_total = pd.concat([df_lotes_final, df_produtos_final])
        
        # Limpeza básica
        df_total['descricao'] = df_total['descricao'].astype(str).str.upper().str.strip()
        df_total['endereco'] = df_total['endereco'].astype(str).str.upper().str.strip()
        df_total['lote'] = df_total['lote'].astype(str).str.upper().str.strip().replace('NAN', None)

        # Converte para dicionário e envia para Supabase
        dados = df_total.to_dict(orient='records')
        
        # Envio em lotes (batch) para não travar
        supabase.table("estoque_unificado").insert(dados).execute()
        
        st.success(f"✅ Sucesso! {len(dados)} itens importados para a tabela 'estoque_unificado'.")
        
    except Exception as e:
        st.error(f"Erro na importação: {e}")

# Botão temporário na barra lateral para fazer a carga
if st.sidebar.button("⚠️ Executar Importação Inicial"):
    importar_dados_para_supabase()
