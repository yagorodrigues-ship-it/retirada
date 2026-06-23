import streamlit as st
import pandas as pd
import datetime
import sqlite3

# Configuração da página do Streamlit
st.set_page_config(page_title="Almoxarifado Inteligente - Gestão", layout="wide", page_icon="📦")

# --- BANCO DE DADOS (Configuração Robusta com Migração) ---
def conectar_bd():
    conn = sqlite3.connect('almoxarifado.db')
    cursor = conn.cursor()
    
    # Criação das tabelas fundamentais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT
        )
    ''')
    
    # Mecanismo de Migração de Colunas
    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'perfil' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN perfil TEXT DEFAULT 'Volante'")
        conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT,
            nome TEXT,
            data TEXT,
            hora TEXT,
            status TEXT DEFAULT 'Aguardando Triagem'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agendamento_id INTEGER,
            serial TEXT,
            status_item TEXT DEFAULT 'Aguardando devolução',
            FOREIGN KEY(agendamento_id) REFERENCES agendamentos(id)
        )
    ''')
    
    # Garante o usuário mestre administrador padrão
    cursor.execute("SELECT * FROM usuarios WHERE cpf = '000'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO usuarios (cpf, nome, senha, perfil) VALUES ('000', 'Administrador Principal', 'admin', 'Almoxarife')"
        )
        
    conn.commit()
    return conn

conn = conectar_bd()
cursor = conn.cursor()

# Inicialização de variáveis de estado da sessão
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_cpf'] = ""
    st.session_state['usuario_nome'] = ""
    st.session_state['perfil'] = "Volante"

# Opções de status padronizadas para a triagem individual
LISTA_STATUS_OPCOES = [
    "Aguardando devolução", 
    "Equipamento não localizado", 
    "Aparelho recebido", 
    "Processo finalizado", 
    "Aguardando aprovação de campo"
]

# Função nativa para geração de relatórios de dados para Excel
def gerar_csv_excel(df):
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

# --- TELA DE LOGIN E CADASTRO ---
if not st.session_state['logado']:
    st.title("📦 Sistema de Devolução Antecipada")
    aba_login, aba_cadastro = st.tabs(["🔐 Entrar no Sistema", "📝 Criar Cadastro"])
    
    with aba_login:
        cpf_login = st.text_input("Digite seu CPF", key="login_cpf")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Acessar Sistema", type="primary", use_container_width=True):
            cursor.execute("SELECT nome, perfil FROM usuarios WHERE cpf = ? AND senha = ?", (cpf_login, senha_login))
            usuario = cursor.fetchone()
            if usuario:
                st.session_state['logado'] = True
                st.session_state['usuario_cpf'] = cpf_login
                st.session_state['usuario_nome'] = usuario[0]
                st.session_state['perfil'] = usuario[1]
                st.columns(1) # Forçar re-render
                st.rerun()
            else:
                st.error("❌ CPF ou Senha incorretos.")
                    
    with aba_cadastro:
        st.markdown("### Cadastro de Novos Usuários")
        novo_cpf = st.text_input("Defina seu CPF")
        novo_nome = st.text_input("Nome Completo")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        
        if st.button("Salvar Cadastro", use_container_width=True):
            if novo_cpf and novo_nome and nova_senha:
                try:
                    cursor.execute("INSERT INTO usuarios (cpf, nome, senha, perfil) VALUES (?, ?, ?, 'Volante')", (novo_cpf, novo_nome, nova_senha))
                    conn.commit()
                    st.success("✅ Cadastro realizado como Volante! Faça login na aba ao lado.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ Este CPF já está registrado.")
            else:
                st.warning("⚠️ Preencha todos os campos.")

# --- INTERFACE DO SISTEMA LOGADO ---
else:
    # Barra de Ferramentas Superior Fixa
    col_user, col_refresh, col_logout = st.columns([6, 2, 2])
    with col_user:
        st.markdown(f"👤 Usuário: **{st.session_state['usuario_nome']}** | Perfil: `{st.session_state['perfil']}`")
    with col_refresh:
        # Mecanismo de Atualização Rápida no Canto Superior
        if st.button("🔄 Atualizar Sistema", use_container_width=True, help="Clique para sincronizar o banco de dados e atualizar dados"):
            st.toast("Dados sincronizados com sucesso!")
            st.rerun()
    with col_logout:
        if st.button("Sair do Sistema ➔", use_container_width=True, type="secondary"):
            st.session_state['logado'] = False
            st.rerun()
            
    st.divider()

    # =========================================================================
    # FLUXO DO PERFIL ADMINISTRADOR (ALMOXARIFE)
    # =========================================================================
    if st.session_state['perfil'] == 'Almoxarife':
        st.title("🔑 Painel de Controle e Gestão (Mestre)")
        
        # Abas organizadas conforme solicitado
        aba_volante, aba_triagem, aba_usuarios = st.tabs([
            "🚗 Lançar Nova Solicitação (Visão do Volante)", 
            "📋 Pastas de Triagem", 
            "👥 Gerenciar Permissões (Volante / Almoxarife)"
        ])
        
        # ABA 1: Visão Integrada do Volante para o Admin interagir
        with aba_volante:
            st.subheader("Agende uma Nova Entrega de Equipamentos")
            col1, col2 = st.columns(2)
            with col1:
                data_agenda = st.date_input("Selecione a Data", min_value=datetime.date.today(), key="admin_data")
            with col2:
                hora_agenda = st.time_input("Selecione o Horário", key="admin_hora")
                
            st.markdown("#### Bipar Equipamentos")
            equipamentos_bipados = st.text_area("Seriais (Insira um por linha ou bipados sequencialmente)", height=150, placeholder="Bipe o código...\nBipe o próximo...", key="admin_seriais")
            
            if st.button("Fechar Devolução e Enviar para Triagem", type="primary", use_container_width=True, key="admin_salvar_entrega"):
                if equipamentos_bipados.strip():
                    lista_limpa = [item.strip() for item in equipamentos_bipados.replace(",", "\n").split("\n") if item.strip()]
                    
                    cursor.execute(
                        "INSERT INTO agendamentos (cpf, nome, data, hora, status) VALUES (?, ?, ?, ?, 'Aguardando Triagem')",
                        (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5])
                    )
                    novo_id = cursor.lastrowid
                    
                    for srl in lista_limpa:
                        cursor.execute("INSERT INTO itens_agendamento (agendamento_id, serial) VALUES (?, ?)", (novo_id, srl))
                        
                    conn.commit()
                    st.success(f"✅ Pasta de triagem de Protocolo #{novo_id} gerada com sucesso! Verifique na aba ao lado.")
                else:
                    st.error("⚠️ Insira ou bipe ao menos 1 serial de equipamento.")
                    
        # ABA 2: Gerenciador de Pastas com Triagem de Itens e Status Laterais
        with aba_triagem:
            st.subheader("Solicitações de Pastas Recebidas")
            df_pastas = pd.read_sql_query("SELECT id as 'Protocolo', nome as 'Volante', data as 'Data', hora as 'Horário', status as 'Status Geral' FROM agendamentos WHERE status != 'Finalizado'", conn)
            
            if df_pastas.empty:
                st.info("Nenhuma pasta pendente de triagem no momento.")
            else:
                for idx, row in df_pastas.iterrows():
                    id_proto = int(row['Protocolo'])
                    
                    # Criação da estrutura em formato de pasta/container limpo
                    with st.container(border=True):
                        c_info, c_fechar = st.columns([7, 3])
                        with c_info:
                            st.markdown(f"### 📁 Pasta de Devolução - Protocolo #{id_proto}")
                            st.markdown(f"**Funcionário:** {row['Volante']} | **Previsão:** {row['Data']} às {row['Horário']}")
                        with c_fechar:
                            if st.button("✅ Encerrar Todo o Protocolo", key=f"encerrar_{id_proto}", type="primary", use_container_width=True):
                                cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (id_proto,))
                                cursor.execute("UPDATE itens_agendamento SET status_item = 'Processo finalizado' WHERE agendamento_id = ?", (id_proto,))
                                conn.commit()
                                st.success(f"Protocolo #{id_proto} finalizado e arquivado!")
                                st.rerun()
                        
                        # Expansor simulando a abertura de uma pasta com os seriais dentro
                        with st.expander("👁️ Abrir Pasta de Seriais Bipados neste Protocolo", expanded=True):
                            cursor.execute("SELECT id, serial, status_item FROM itens_agendamento WHERE agendamento_id = ?", (id_proto,))
                            itens_da_pasta = cursor.fetchall()
                            
                            st.markdown("---")
                            # Criação das colunas de Serial vs Status ao lado conforme solicitado
                            for item_id, serial, status_atual in itens_da_pasta:
                                col_txt, col_selecao = st.columns([5, 5])
                                with col_txt:
                                    st.markdown(f"🔹 Serial do Equipamento: **{serial}**")
                                with col_selecao:
                                    idx_def = LISTA_STATUS_OPCOES.index(status_atual) if status_atual in LISTA_STATUS_OPCOES else 0
                                    novo_status = st.selectbox(
                                        "Mudar Status",
                                        options=LISTA_STATUS_OPCOES,
                                        index=idx_def,
                                        key=f"status_item_{item_id}"
                                    )
                                    # Atualiza na hora o banco ao mudar a caixinha
                                    if novo_status != status_atual:
                                        cursor.execute("UPDATE itens_agendamento SET status_item = ? WHERE id = ?", (novo_status, item_id))
                                        conn.commit()
                                        st.toast(f"Status do serial {serial} alterado!")
                            
                            st.markdown("---")
                            # Botão para baixar os dados específicos de relatórios da pasta corrente
                            df_relatorio_pasta = pd.read_sql_query(f"SELECT serial as 'Número de Serial', status_item as 'Status do Item' FROM itens_agendamento WHERE agendamento_id = {id_proto}", conn)
                            csv_gerado = gerar_csv_excel(df_relatorio_pasta)
                            st.download_button(
                                label="📥 Exportar Dados desta Pasta para Excel (.csv)",
                                data=csv_gerado,
                                file_name=f"Relatorio_Pasta_Protocolo_{id_proto}.csv",
                                mime="text/csv",
                                use_container_width=True,
                                key=f"btn_dl_{id_proto}"
                            )

        # ABA 3: Painel de Controle de Permissões de Usuários
        with aba_usuarios:
            st.subheader("Controle de Níveis de Acesso")
            st.markdown("Defina quem atua em campo como Volante e quem possui permissões administrativas de Almoxarife:")
            
            cursor.execute("SELECT cpf, nome, perfil FROM usuarios WHERE cpf != '000'")
            usuarios_cadastrados = cursor.fetchall()
            
            for cpf, nome, perfil_atual in usuarios_cadastrados:
                with st.container(border=True):
                    col_info, col_acao = st.columns([7, 3])
                    with col_info:
                        st.markdown(f"👤 **{nome}** | CPF: `{cpf}`")
                        st.markdown(f"Perfil de Acesso Atual: **{perfil_atual}**")
                    with col_acao:
                        novo_perfil = "Almoxarife" if perfil_atual == "Volante" else "Volante"
                        texto_botao = "Promover a Almoxarife 🔑" if perfil_atual == "Volante" else "Mudar para Volante 🚗"
                        
                        if st.button(texto_botao, key=f"perfil_{cpf}", use_container_width=True):
                            cursor.execute("UPDATE usuarios SET perfil = ? WHERE cpf = ?", (novo_perfil, cpf))
                            conn.commit()
                            st.success(f"Perfil de {nome} alterado com sucesso para {novo_perfil}!")
                            st.rerun()

    # =========================================================================
    # FLUXO DO PERFIL PADRÃO (VOLANTE EM CAMPO)
    # =========================================================================
    else:
        st.title("📦 Solicitação de Devolução Antecipada (Visão do Volante)")
        
        cursor.execute("SELECT id, data, hora, status FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        agendamento_ativo = cursor.fetchone()
        
        if agendamento_ativo:
            proto_id, proto_data, proto_hora, proto_status = agendamento_ativo
            st.info(f"📆 Você possui uma solicitação ativa (Protocolo #{proto_id}) para o dia {proto_data} às {proto_hora}.")
            st.warning("⏳ Aguarde o almoxarife validar seus seriais para liberar sua vinda ao balcão.")
            
            st.markdown("### 📋 Status Atualizado dos Meus Itens na Pasta")
            df_meus_itens = pd.read_sql_query(f"SELECT serial as 'Serial do Equipamento', status_item as 'Status de Triagem' FROM itens_agendamento WHERE agendamento_id = {proto_id}", conn)
            st.dataframe(df_meus_itens, use_container_width=True)
            
        else:
            st.header("Agende sua Nova Entrega")
            col1, col2 = st.columns(2)
            with col1:
                data_agenda = st.date_input("Selecione a Data", min_value=datetime.date.today())
            with col2:
                hora_agenda = st.time_input("Selecione o Horário")
                
            st.subheader("Bipar Equipamentos")
            equipamentos_bipados = st.text_area("Seriais (Insira um por linha)", height=150, placeholder="Bipe o código...\nBipe o próximo...")
            
            if st.button("Fechar Devolução e Enviar para Triagem", type="primary", use_container_width=True):
                if equipamentos_bipados.strip():
                    lista_limpa = [item.strip() for item in equipamentos_bipados.replace(",", "\n").split("\n") if item.strip()]
                    
                    cursor.execute(
                        "INSERT INTO agendamentos (cpf, nome, data, hora, status) VALUES (?, ?, ?, ?, 'Aguardando Triagem')",
                        (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5])
                    )
                    novo_id_agendamento = cursor.lastrowid
                    
                    for srl in lista_limpa:
                        cursor.execute("INSERT INTO itens_agendamento (agendamento_id, serial) VALUES (?, ?)", (novo_id_agendamento, srl))
                        
                    conn.commit()
                    st.success("✅ Pasta de triagem gerada com sucesso!")
                    st.rerun()
                else:
                    st.error("⚠️ Você precisa bipar pelo menos 1 equipamento.")
