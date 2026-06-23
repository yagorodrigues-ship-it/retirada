import streamlit as st
import pandas as pd
import datetime
import sqlite3

# Configuração da página
st.set_page_config(page_title="Almoxarifado Inteligente - Gestão", layout="wide", page_icon="📦")

# --- BANCO DE DADOS (Configuração Corrigida com Migração Automática) ---
def conectar_bd():
    conn = sqlite3.connect('almoxarifado.db')
    cursor = conn.cursor()
    
    # 1. Cria a tabela base caso ela não exista
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT
        )
    ''')
    
    # 2. MECANISMO DE MIGRAÇÃO: Verifica se a coluna 'perfil' já existe, se não existir, adiciona
    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'perfil' not in colunas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN perfil TEXT DEFAULT 'Volante'")
        conn.commit()

    # 3. Cria as outras tabelas necessárias para os itens e agendamentos
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
    
    # 4. Garante que o usuário admin padrão exista (especificando as colunas explicitamente)
    cursor.execute("SELECT * FROM usuarios WHERE cpf = '000'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO usuarios (cpf, nome, senha, perfil) VALUES ('000', 'Administrador Principal', 'admin', 'Almoxarife')"
        )
        
    conn.commit()
    return conn

conn = conectar_bd()
cursor = conn.cursor()

# Controle de Sessão (Login)
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_cpf'] = ""
    st.session_state['usuario_nome'] = ""
    st.session_state['perfil'] = "Volante"
    st.session_state['protocolo_detalhe'] = None  # Controla a tela de detalhes do admin

# --- FUNÇÕES DE CONVERSÃO EXCEL/CSV NATIVO ---
def gerar_excel_nativo(df):
    csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
    return csv_data.encode('utf-8-sig')

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
                st.session_state['protocolo_detalhe'] = None
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

# --- SISTEMA CONECTADO ---
else:
    # Barra de Status Superior comum
    col_user, col_logout = st.columns([8, 2])
    with col_user:
        st.markdown(f"👤 Conectado como: **{st.session_state['usuario_nome']}** | Perfil: `{st.session_state['perfil']}`")
    with col_logout:
        if st.button("Sair do Sistema ➔", use_container_width=True):
            st.session_state['logado'] = False
            st.session_state['protocolo_detalhe'] = None
            st.rerun()
    st.divider()

    # =========================================================================
    # VISÃO DO ADMINISTRADOR (ALMOXARIFE)
    # =========================================================================
    if st.session_state['perfil'] == 'Almoxarife':
        
        # Tela de Detalhes de um protocolo específico
        if st.session_state['protocolo_detalhe'] is not None:
            id_proto = st.session_state['protocolo_detalhe']
            
            cursor.execute("SELECT nome, data, hora, status FROM agendamentos WHERE id = ?", (id_proto,))
            dados_p = cursor.fetchone()
            
            if st.button("⬅️ Voltar para o Painel Principal"):
                st.session_state['protocolo_detalhe'] = None
                st.rerun()
                
            st.title(f"📁 Pasta de Entrega - Protocolo #{id_proto}")
            st.markdown(f"**Volante:** {dados_p[0]} | **Previsão:** {dados_p[1]} às {dados_p[2]} | **Status Geral:** {dados_p[3]}")
            st.write("Altere abaixo o status individual de cada equipamento bipado:")
            
            cursor.execute("SELECT id, serial, status_item FROM itens_agendamento WHERE agendamento_id = ?", (id_proto,))
            itens = cursor.fetchall()
            
            lista_status_opcoes = [
                "Aguardando devolução", 
                "Equipamento não localizado", 
                "Aparelho recebido", 
                "Processo finalizado", 
                "Aguardando aprovação de campo"
            ]
            
            for item_id, serial, status_atual in itens:
                col_ser, col_stat = st.columns([4, 6])
                with col_ser:
                    st.info(f"🔢 Serial: **{serial}**")
                with col_stat:
                    idx_default = lista_status_opcoes.index(status_atual) if status_atual in lista_status_opcoes else 0
                    novo_status_item = st.selectbox(
                        "Status do Equipamento",
                        options=lista_status_opcoes,
                        index=idx_default,
                        key=f"sel_item_{item_id}"
                    )
                    if novo_status_item != status_atual:
                        cursor.execute("UPDATE itens_agendamento SET status_item = ? WHERE id = ?", (novo_status_item, item_id))
                        conn.commit()
                        st.toast(f"Status do serial {serial} atualizado!")

            st.markdown("---")
            df_export = pd.read_sql_query(f"SELECT serial as 'Serial', status_item as 'Status do Item' FROM itens_agendamento WHERE agendamento_id = {id_proto}", conn)
            dados_csv = gerar_excel_nativo(df_export)
            st.download_button(
                label="📥 Baixar Dados desta Pasta para Excel (.csv)",
                data=dados_csv,
                file_name=f"protocolo_{id_proto}_detalhado.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        else:
            # Painel Principal do Administrador
            st.title("🔑 Painel de Controle e Gestão (Mestre)")
            
            aba_triagem, aba_usuarios = st.tabs(["📋 Pastas de Triagem", "👥 Gerenciar Permissões (Volante / Almoxarife)"])
            
            with aba_triagem:
                st.subheader("Solicitações Recebidas")
                df_pastas = pd.read_sql_query("SELECT id as 'Protocolo', nome as 'Volante', data as 'Data', hora as 'Horário', status as 'Status Geral' FROM agendamentos WHERE status != 'Finalizado'", conn)
                
                if df_pastas.empty:
                    st.info("Nenhuma pasta pendente no momento.")
                else:
                    for idx, row in df_pastas.iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([6, 2, 2])
                            with c1:
                                st.markdown(f"**Protocolo #{row['Protocolo']}** — Volante: {row['Volante']} ({row['Data']} às {row['Horário']})")
                                st.caption(f"Status Atual: {row['Status Geral']}")
                            with c2:
                                if st.button("👁️ Abrir em Nova Tela", key=f"abrir_{row['Protocolo']}", use_container_width=True):
                                    st.session_state['protocolo_detalhe'] = int(row['Protocolo'])
                                    st.rerun()
                            with c3:
                                if st.button("✅ Encerrar Protocolo", key=f"fim_{row['Protocolo']}", type="primary", use_container_width=True):
                                    cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (row['Protocolo'],))
                                    cursor.execute("UPDATE itens_agendamento SET status_item = 'Processo finalizado' WHERE agendamento_id = ?", (row['Protocolo'],))
                                    conn.commit()
                                    st.success("Protocolo finalizado por completo!")
                                    st.rerun()
                                    
            with aba_usuarios:
                st.subheader("Controle de Níveis de Acesso")
                st.markdown("Altere abaixo quem atua como Volante em campo e quem gerencia como Almoxarife no Balcão:")
                
                cursor.execute("SELECT cpf, nome, perfil FROM usuarios WHERE cpf != '000'")
                usuarios_cadastrados = cursor.fetchall()
                
                for cpf, nome, perfil_atual in usuarios_cadastrados:
                    with st.container(border=True):
                        col_info, col_acao = st.columns([7, 3])
                        with col_info:
                            st.markdown(f"👤 **{nome}** | CPF: `{cpf}`")
                            st.markdown(f"Função Atual: **{perfil_atual}**")
                        with col_acao:
                            novo_perfil = "Almoxarife" if perfil_atual == "Volante" else "Volante"
                            texto_botao = "Promover a Almoxarife 🔑" if perfil_atual == "Volante" else "Mudar para Volante 🚗"
                            
                            if st.button(texto_botao, key=f"perfil_{cpf}", use_container_width=True):
                                cursor.execute("UPDATE usuarios SET perfil = ? WHERE cpf = ?", (novo_perfil, cpf))
                                conn.commit()
                                st.success(f"Perfil de {nome} alterado para {novo_perfil}!")
                                st.rerun()

    # =========================================================================
    # VISÃO DO VOLANTE
    # =========================================================================
    else:
        st.title("📦 Solicitação de Devolução Antecipada (Visão do Volante)")
        
        cursor.execute("SELECT id, data, hora, status FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        agendamento_ativo = cursor.fetchone()
        
        if agendamento_ativo:
            proto_id, proto_data, proto_hora, proto_status = agendamento_ativo
            st.info(f"📆 Você possui uma solicitação ativa (Protocolo #{proto_id}) marcada para o dia {proto_data} às {proto_hora}.")
            
            st.markdown("### 📋 Status dos Meus Equipamentos Bipados")
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
