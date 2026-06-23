import streamlit as st
import pandas as pd
import datetime
import sqlite3
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Almoxarifado Inteligente", layout="wide", page_icon="📦")

# --- BANCO DE DADOS (Configuração Inicial) ---
def conectar_bd():
    conn = sqlite3.connect('almoxarifado.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT,
            nome TEXT,
            data TEXT,
            hora TEXT,
            seriais TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    return conn

conn = conectar_bd()
cursor = conn.cursor()

# Controle de Sessão (Login)
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_cpf'] = ""
    st.session_state['usuario_nome'] = ""
    st.session_state['eh_almoxarife'] = False

# --- FUNÇÕES DE VALIDAÇÃO DE HORÁRIO ---
def verificar_regras_agendamento(data_selecionada, hora_selecionada):
    cursor.execute("SELECT hora FROM agendamentos WHERE data = ?", (str(data_selecionada),))
    agendamentos_dia = cursor.fetchall()
    
    nova_hora_minutos = hora_selecionada.hour * 60 + hora_selecionada.minute
    
    for (h,) in agendamentos_dia:
        h_atual = datetime.datetime.strptime(h, "%H:%M").time()
        atual_minutos = h_atual.hour * 60 + h_atual.minute
        
        if abs(nova_hora_minutos - atual_minutos) < 180:
            return False, f"⚠️ Horário indisponível! Outra pessoa agendou às {h}. Escolha um horário com 3 horas de diferença."
            
    return True, ""

# --- TELA DE LOGIN E CADASTRO ---
if not st.session_state['logado']:
    st.title("📦 Acesso ao Sistema de Devolução")
    
    aba_login, aba_cadastro = st.tabs(["🔐 Entrar no Sistema", "📝 Criar Cadastro"])
    
    with aba_login:
        cpf_login = st.text_input("Digite seu CPF (ou 000 para Almoxarife)", key="login_cpf")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Acessar", type="primary", use_container_width=True):
            if cpf_login == "000" and senha_login == "admin":  
                st.session_state['logado'] = True
                st.session_state['eh_almoxarife'] = True
                st.rerun()
            else:
                cursor.execute("SELECT nome FROM usuarios WHERE cpf = ? AND senha = ?", (cpf_login, senha_login))
                usuario = cursor.fetchone()
                if usuario:
                    st.session_state['logado'] = True
                    st.session_state['usuario_cpf'] = cpf_login
                    st.session_state['usuario_nome'] = usuario[0]
                    st.session_state['eh_almoxarife'] = False
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")
                    
    with aba_cadastro:
        novo_cpf = st.text_input("Defina seu CPF")
        novo_nome = st.text_input("Nome Completo")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        
        if st.button("Salvar Cadastro", use_container_width=True):
            if novo_cpf and novo_nome and nova_senha:
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?)", (novo_cpf, novo_nome, nova_senha))
                    conn.commit()
                    st.success("✅ Cadastro realizado com sucesso! Vá para a aba 'Entrar no Sistema'.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ Este CPF já está registrado.")
            else:
                st.warning("⚠️ Preencha todos os campos obrigatórios.")

# --- SISTEMA APÓS LOGIN CONTROLANDO OS DOIS ACESSOS ---
else:
    # Topo comum para os dois acessos
    col_user, col_logout = st.columns([8, 2])
    with col_user:
        nome_exibicao = "Almoxarife Principal" if st.session_state['eh_almoxarife'] else st.session_state['usuario_nome']
        st.markdown(f"👤 Conectado como: **{nome_exibicao}**")
    with col_logout:
        if st.button("Sair do Sistema ➔", use_container_width=True):
            st.session_state['logado'] = False
            st.session_state['eh_almoxarife'] = False
            st.rerun()
    st.divider()

    # --- ACESSO 1: EXCLUSIVO DO ALMOXARIFE ---
    if st.session_state['eh_almoxarife']:
        st.title("🔑 Painel de Triagem e Devoluções")
        st.markdown("Gerencie as solicitações recebidas, exporte os seriais e valide a entrega física.")
        
        # Carrega registros que não foram finalizados
        df_agendamentos = pd.read_sql_query("SELECT * FROM agendamentos WHERE status != 'Finalizado'", conn)
        
        if df_agendamentos.empty:
            st.info("Visualização limpa. Não há devoluções pendentes na fila.")
        else:
            for idx, row in df_agendamentos.iterrows():
                lista_seriais = [s.strip() for s in row['seriais'].split(",") if s.strip()]
                
                # Cada agendamento vira uma pasta expansível na tela
                with st.expander(f"📁 Protocolo #{row['id']} | Funcionário: {row['nome']} | Horário: {row['hora']} | Status: {row['status']}"):
                    st.markdown(f"**Data Agendada:** {row['data']} às {row['hora']} | **CPF:** {row['cpf']}")
                    
                    st.markdown("### 📋 Lista de Seriais Bipados:")
                    df_seriais = pd.DataFrame({"Seriais dos Equipamentos": lista_seriais})
                    st.dataframe(df_seriais, use_container_width=True)
                    
                    # --- ABA EXCLUSIVA DE EXPORTAÇÃO PARA EXCEL ---
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_seriais.to_excel(writer, index=False, sheet_name='Seriais_Devolvidos')
                    
                    st.download_button(
                        label="🟢 Exportar Seriais para Excel (.xlsx)",
                        data=buffer.getvalue(),
                        file_name=f"seriais_protocolo_{row['id']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"excel_{row['id']}"
                    )
                    
                    st.write("")
                    st.markdown("**Ações do Almoxarifado:**")
                    col_b1, col_b2 = st.columns(2)
                    
                    with col_b1:
                        if row['status'] == "Aguardando Triagem":
                            if st.button("🚀 Liberar e Notificar Disponibilidade", key=f"lib_{row['id']}", use_container_width=True):
                                cursor.execute("UPDATE agendamentos SET status = 'Disponível para Receber' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.success("Status atualizado! O usuário já sabe que pode trazer os itens.")
                                st.rerun()
                                
                    with col_b2:
                        if row['status'] == "Disponível para Receber":
                            if st.button("📥 Fechar Devolução (Itens Recebidos no Físico)", key=f"fec_{row['id']}", type="primary", use_container_width=True):
                                cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.success("Concluído! Estoque baixado e atendimento encerrado.")
                                st.rerun()

    # --- ACESSO 2: EXCLUSIVO DO USUÁRIO (QUEM DEVOLVE) ---
    else:
        st.title("📦 Solicitação de Devolução Antecipada")
        
        # Verifica se ele já enviou algo
        cursor.execute("SELECT id, data, hora, status FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        agendamento_ativo = cursor.fetchone()
        
        if agendamento_ativo:
            st.info(f"📆 Você já possui uma solicitação ativa (Protocolo #{agendamento_ativo[0]}) para o dia {agendamento_ativo[1]} às {agendamento_ativo[2]}.")
            st.markdown(f"**Status Atual:** `{agendamento_ativo[3]}`")
            
            if agendamento_ativo[3] == "Disponível para Receber":
                st.success("🟢 Seu agendamento foi pré-analisado pelo Almoxarifado! Pode se dirigir ao balcão para entregar os aparelhos físicos.")
            else:
                st.warning("⏳ Aguarde o almoxarife validar seus seriais para liberar sua vinda ao balcão.")
        else:
            st.header("Agende sua Entrega")
            col1, col2 = st.columns(2)
            with col1:
                data_agenda = st.date_input("Selecione a Data", min_value=datetime.date.today())
            with col2:
                hora_agenda = st.time_input("Selecione o Horário")
                
            st.subheader("Bipar Equipamentos")
            st.markdown("Dê um clique na caixa de texto abaixo e comece a bipar os seriais com o seu leitor:")
            
            equipamentos_bipados = st.text_area("Seriais (Um por linha)", height=150, placeholder="Bipe o código...\nBipe o próximo...")
            
            if st.button("Fechar Devolução e Enviar para Triagem", type="primary", use_container_width=True):
                if id_com_bips := equipamentos_bipados.strip():
                    lista_limpa = [item.strip() for item in equipamentos_bipados.replace(",", "\n").split("\n") if item.strip()]
                    seriais_str = ",".join(lista_limpa)
                    
                    valido, msg_erro = verificar_regras_agendamento(data_agenda, hora_agenda)
                    
                    if valido:
                        cursor.execute(
                            "INSERT INTO agendamentos (cpf, nome, data, hora, seriais, status) VALUES (?, ?, ?, ?, ?, 'Aguardando Triagem')",
                            (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5], seriais_str)
                        )
                        conn.commit()
                        st.success("✅ Devolução fechada! Enviada diretamente para a pasta do almoxarife.")
                        st.rerun()
                    else:
                        st.error(msg_erro)
                else:
                    st.error("⚠️ Erro: Você precisa bipar pelo menos 1 equipamento antes de enviar.")
