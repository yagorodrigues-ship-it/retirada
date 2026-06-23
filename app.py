import streamlit as st
import pandas as pd
import datetime
import sqlite3

# Configuração da página do Streamlit
st.set_page_config(page_title="Almoxarifado Inteligente", layout="wide", page_icon="📦")

# --- BANCO DE DADOS ---
def conectar_bd():
    conn = sqlite3.connect('almoxarifado.db')
    cursor = conn.cursor()
    
    # Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT,
            perfil TEXT DEFAULT 'Volante'
        )
    ''')
    
    # Agendamentos (Pastas)
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
    
    # Itens (Seriais)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agendamento_id INTEGER,
            serial TEXT,
            status_item TEXT DEFAULT 'Solicitação pendente',
            FOREIGN KEY(agendamento_id) REFERENCES agendamentos(id)
        )
    ''')
    
    # Migrações seguras com try/except para evitar o erro de coluna duplicada
    try:
        cursor.execute("ALTER TABLE itens_agendamento ADD COLUMN observacao TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # Coluna já existe, ignora o erro
        
    try:
        cursor.execute("ALTER TABLE itens_agendamento ADD COLUMN almoxarife_responsavel TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # Coluna já existe, ignora o erro
    
    # Usuário Admin Padrão
    cursor.execute("SELECT * FROM usuarios WHERE cpf = '000'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (cpf, nome, senha, perfil) VALUES ('000', 'Administrador Principal', 'admin', 'Almoxarife')")
        
    conn.commit()
    return conn

conn = conectar_bd()
cursor = conn.cursor()

# Estados da sessão
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_cpf'] = ""
    st.session_state['usuario_nome'] = ""
    st.session_state['perfil'] = "Volante"

# Lista de opções de Status
LISTA_STATUS_OPCOES = [
    "Solicitação pendente",
    "Aguardando devolução", 
    "Equipamento não localizado", 
    "Aparelho recebido", 
    "Processo finalizado", 
    "Aguardando aprovação de campo"
]

def gerar_csv_excel(df):
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

# --- TELA DE LOGIN ---
if not st.session_state['logado']:
    st.title("📦 Sistema de Devolução Antecipada")
    aba_login, aba_cadastro = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with aba_login:
        cpf_login = st.text_input("CPF", key="login_cpf")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Acessar", type="primary", use_container_width=True):
            cursor.execute("SELECT nome, perfil FROM usuarios WHERE cpf = ? AND senha = ?", (cpf_login, senha_login))
            usuario = cursor.fetchone()
            if usuario:
                st.session_state['logado'] = True
                st.session_state['usuario_cpf'] = cpf_login
                st.session_state['usuario_nome'] = usuario[0]
                st.session_state['perfil'] = usuario[1]
                st.rerun()
            else:
                st.error("❌ Credenciais incorretas.")
                
    with aba_cadastro:
        novo_cpf = st.text_input("CPF para cadastro")
        novo_nome = st.text_input("Nome Completo")
        nova_senha = st.text_input("Senha ", type="password")
        if st.button("Salvar", use_container_width=True):
            if novo_cpf and novo_nome and nova_senha:
                try:
                    cursor.execute("INSERT INTO usuarios (cpf, nome, senha, perfil) VALUES (?, ?, ?, 'Volante')", (novo_cpf, novo_nome, nova_senha))
                    conn.commit()
                    st.success("✅ Cadastrado! Faça login.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ CPF já registrado.")

# --- SISTEMA LOGADO ---
else:
    col_user, col_refresh, col_logout = st.columns([6, 2, 2])
    with col_user:
        st.markdown(f"👤 **{st.session_state['usuario_nome']}** ({st.session_state['perfil']})")
    with col_refresh:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()
    with col_logout:
        if st.button("Sair ➔", use_container_width=True):
            st.session_state['logado'] = False
            st.rerun()
            
    st.divider()

    if st.session_state['perfil'] == 'Almoxarife':
        st.title("🔑 Painel de Gestão")
        
        aba_volante, aba_triagem, aba_historico, aba_usuarios = st.tabs([
            "🚗 Nova Solicitação (Volante)", 
            "📋 Pastas de Triagem Ativas",
            "📜 Histórico de Devoluções", 
            "👥 Permissões"
        ])
        
        # ABA 1: Visão Volante
        with aba_volante:
            st.subheader("Simular Lançamento Manual")
            col1, col2 = st.columns(2)
            data_agenda = col1.date_input("Data", min_value=datetime.date.today(), key="adm_d")
            hora_agenda = col2.time_input("Horário", key="adm_h")
            equipamentos = st.text_area("Seriais (Um por linha)", placeholder="Bipe aqui...", key="adm_s")
            
            if st.button("Enviar para Triagem", type="primary", use_container_width=True):
                if equipamentos.strip():
                    lista_s = [s.strip() for s in equipamentos.replace(",", "\n").split("\n") if s.strip()]
                    cursor.execute("INSERT INTO agendamentos (cpf, nome, data, hora, status) VALUES (?, ?, ?, ?, 'Aguardando Triagem')",
                                   (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5]))
                    id_p = cursor.lastrowid
                    for s in lista_s:
                        cursor.execute("INSERT INTO itens_agendamento (agendamento_id, serial, status_item) VALUES (?, ?, 'Solicitação pendente')", (id_p, s))
                    conn.commit()
                    st.success(f"✅ Protocolo #{id_p} criado com sucesso!")
                    st.rerun()

        # ABA 2: Triagem Ativa
        with aba_triagem:
            st.subheader("Fila de Triagem Atual")
            
            # Filtro por Data Inteligente
            data_filtro = st.date_input("📅 Filtrar Pastas por Data específica:", value=None, help="Deixe em branco para visualizar todas")
            
            query = "SELECT id, nome, data, hora, status FROM agendamentos WHERE status = 'Aguardando Triagem'"
            if data_filtro:
                query += f" AND data = '{str(data_filtro)}'"
                
            df_pastas = pd.read_sql_query(query, conn)
            
            if df_pastas.empty:
                st.info("Nenhuma pasta de triagem ativa encontrada para este filtro.")
            else:
                for idx, row in df_pastas.iterrows():
                    id_proto = int(row['id'])
                    
                    # Container compacto e elegante
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([5, 3, 2])
                        c1.markdown(f"📁 **Protocolo #{id_proto}** | Volante: {row['nome']}")
                        c2.markdown(f"📅 Previsão: {row['data']} às {row['hora']}")
                        
                        if c3.button("📦 Encerrar Protocolo", key=f"f_{id_proto}", type="primary", use_container_width=True):
                            cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (id_proto,))
                            conn.commit()
                            st.success(f"Protocolo #{id_proto} guardado no histórico!")
                            st.rerun()
                            
                        with st.expander("📄 Abrir Lista de Seriais Bipados", expanded=False):
                            cursor.execute("SELECT id, serial, status_item, observacao, almoxarife_responsavel FROM itens_agendamento WHERE agendamento_id = ?", (id_proto,))
                            itens = cursor.fetchall()
                            
                            # Cabeçalho da Mini Tabela
                            col_h1, col_h2, col_h3, col_h4 = st.columns([2.5, 3, 3, 1.5])
                            col_h1.caption("**Serial**")
                            col_h2.caption("**Mudar Status**")
                            col_h3.caption("**Observação Interna**")
                            col_h4.caption("**Modificado por**")
                            
                            for item_id, serial, status_item, obs, resp in itens:
                                col_srl, col_st, col_obs, col_resp = st.columns([2.5, 3, 3, 1.5])
                                
                                col_srl.markdown(f"🔹 `{serial}`")
                                
                                # Seleção de Status
                                idx_st = LISTA_STATUS_OPCOES.index(status_item) if status_item in LISTA_STATUS_OPCOES else 0
                                n_st = col_st.selectbox("Status", LISTA_STATUS_OPCOES, index=idx_st, key=f"st_{item_id}", label_visibility="collapsed")
                                
                                # Campo de Observação na mesma linha
                                n_obs = col_obs.text_input("Obs", value=obs, key=f"obs_{item_id}", placeholder="Escreva uma observação...", label_visibility="collapsed")
                                
                                # Nome do Almoxarife Responsável registrado ao lado
                                if resp:
                                    col_resp.markdown(f"✍️ `{resp}`")
                                else:
                                    col_resp.caption("*Sem alterações*")
                                    
                                # Gravação imediata no Banco de Dados se houver qualquer modificação
                                if n_st != status_item or n_obs != obs:
                                    cursor.execute(
                                        "UPDATE itens_agendamento SET status_item = ?, observacao = ?, almoxarife_responsavel = ? WHERE id = ?",
                                        (n_st, n_obs, st.session_state['usuario_nome'], item_id)
                                    )
                                    conn.commit()
                                    st.toast(f"Alteração salva para o serial {serial}!")
                                    st.rerun()
                                    
                            # Exportação individual da pasta
                            df_rel = pd.read_sql_query(f"SELECT serial as 'Serial', status_item as 'Status', observacao as 'Observações', almoxarife_responsavel as 'Almoxarife' FROM itens_agendamento WHERE agendamento_id = {id_proto}", conn)
                            st.download_button("📥 Baixar Planilha desta Pasta (.csv)", gerar_csv_excel(df_rel), f"Protocolo_{id_proto}.csv", "text/csv", use_container_width=True, key=f"dl_{id_proto}")

        # ABA 3: Histórico de Devoluções (Salvos permanentemente)
        with aba_historico:
            st.subheader("📜 Histórico de Protocolos Encerrados")
            df_hist = pd.read_sql_query("SELECT id as 'Protocolo', nome as 'Volante', data as 'Data Fechamento', hora as 'Horário' FROM agendamentos WHERE status = 'Finalizado' ORDER BY id DESC", conn)
            
            if df_hist.empty:
                st.info("Nenhum protocolo foi finalizado até o momento.")
            else:
                st.dataframe(df_hist, use_container_width=True)
                
                st.divider()
                st.markdown("### 🔍 Auditoria de Protocolos Arquivados")
                proto_busca = st.number_input("Insira o número do Protocolo do histórico para verificar os seriais:", min_value=1, step=1)
                if st.button("Buscar Detalhes no Arquivo", use_container_width=True):
                    df_detalhe = pd.read_sql_query(f"SELECT serial as 'Serial', status_item as 'Status Final', observacao as 'Observações', almoxarife_responsavel as 'Almoxarife Auditou' FROM itens_agendamento WHERE agendamento_id = {int(proto_busca)}", conn)
                    if not df_detalhe.empty:
                        st.markdown(f"#### 📑 Itens do Protocolo Registrado #{int(proto_busca)}")
                        st.table(df_detalhe)
                    else:
                        st.error("Protocolo não localizado ou não possui itens arquivados.")

        # ABA 4: Gerenciamento de Permissões
        with aba_usuarios:
            st.subheader("Gerenciar Usuários")
            u_cad = cursor.execute("SELECT cpf, nome, perfil FROM usuarios WHERE cpf != '000'").fetchall()
            for cpf, nome, perfil in u_cad:
                with st.container(border=True):
                    col_i, col_b = st.columns([7, 3])
                    col_i.markdown(f"👤 **{nome}** | Perfil Atual: `{perfil}`")
                    n_perfil = "Almoxarife" if perfil == "Volante" else "Volante"
                    if col_b.button(f"Mudar para {n_perfil}", key=f"p_{cpf}", use_container_width=True):
                        cursor.execute("UPDATE usuarios SET perfil = ? WHERE cpf = ?", (n_perfil, cpf))
                        conn.commit()
                        st.rerun()

    # --- FLUXO DO VOLANTE ---
    else:
        st.title("📦 Área do Volante")
        cursor.execute("SELECT id, data, hora, status FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        ativo = cursor.fetchone()
        
        if ativo:
            st.info(f"📆 Protocolo Ativo #{ativo[0]} agendado para {ativo[1]} às {ativo[2]}. Status: {ativo[3]}")
            st.markdown("### Meus Equipamentos na Pasta")
            df_m = pd.read_sql_query(f"SELECT serial as 'Serial', status_item as 'Meu Status', observacao as 'Observação Almoxarifado' FROM itens_agendamento WHERE agendamento_id = {ativo[0]}", conn)
            st.dataframe(df_m, use_container_width=True)
        else:
            st.subheader("Criar Solicitação de Devolução")
            col1, col2 = st.columns(2)
            d_v = col1.date_input("Data de Entrega", min_value=datetime.date.today())
            h_v = col2.time_input("Horário Estimado")
            seriais_v = st.text_area("Bipar os Equipamentos (Um por linha)")
            
            if st.button("Confirmar Envio", type="primary", use_container_width=True):
                if seriais_v.strip():
                    lista_v = [s.strip() for s in seriais_v.replace(",", "\n").split("\n") if s.strip()]
                    cursor.execute("INSERT INTO agendamentos (cpf, nome, data, hora, status) VALUES (?, ?, ?, ?, 'Aguardando Triagem')",
                                   (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(d_v), str(h_v)[:5]))
                    id_v = cursor.lastrowid
                    for s in lista_v:
                        cursor.execute("INSERT INTO itens_agendamento (agendamento_id, serial, status_item) VALUES (?, ?, 'Solicitação pendente')", (id_v, s))
                    conn.commit()
                    st.success("✅ Enviado com sucesso para a triagem!")
                    st.rerun()
