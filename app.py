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
    # Tabela de Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT
        )
    ''')
    # Tabela de Agendamentos
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
        
        # Regra: Intervalo mínimo de 3 horas (180 minutos) entre agendamentos
        if abs(nova_hora_minutos - atual_minutos) < 180:
            return False, f"⚠️ Conflito! Já existe um agendamento neste dia às {h}. É necessário um intervalo mínimo de 3 horas."
            
    return True, ""

# --- TELA DE LOGIN E CADASTRO ---
if not st.session_state['logado']:
    st.title("📦 Acesso ao Sistema de Devolução")
    
    aba_login, aba_cadastro = st.tabs(["🔐 Entrar", "📝 Cadastrar Conta"])
    
    with aba_login:
        cpf_login = st.text_input("CPF (Apenas números)", key="login_cpf")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Acessar Sistema", type="primary"):
            if cpf_login == "000" and senha_login == "admin":  # Login padrão do almoxarife
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
                    st.error("❌ CPF ou Senha incorretos.")
                    
    with aba_cadastro:
        novo_cpf = st.text_input("Digite seu CPF")
        novo_nome = st.text_input("Seu Nome Completo")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        
        if st.button("Criar Cadastro"):
            if novo_cpf and novo_nome and nova_senha:
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?)", (novo_cpf, novo_nome, nova_senha))
                    conn.commit()
                    st.success("✅ Cadastro realizado com sucesso! Vá para a aba 'Entrar'.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ Este CPF já está cadastrado.")
            else:
                st.warning("⚠️ Preencha todos os campos.")

# --- SISTEMA APÓS LOGIN ---
else:
    # Barra Superior de Logout
    col_user, col_logout = st.columns([9, 1])
    with col_user:
        st.markdown(f"👤 Conectado como: **{st.session_state['usuario_nome'] if not st.session_state['eh_almoxarife'] else 'Almoxarife Principal'}**")
    with col_logout:
        if st.button("Sair 🚪"):
            st.session_state['logado'] = False
            st.rerun()

    # --- VISÃO DO ALMOXARIFE ---
    if st.session_state['eh_almoxarife']:
        st.title("🔑 Painel de Triagem do Almoxarifado")
        
        # Buscar agendamentos que não foram totalmente concluídos
        df_agendamentos = pd.read_sql_query("SELECT * FROM agendamentos WHERE status != 'Finalizado'", conn)
        
        if df_agendamentos.empty:
            st.info("Nenhum agendamento pendente no momento.")
        else:
            for idx, row in df_agendamentos.iterrows():
                lista_seriais = row['seriais'].split(",")
                
                with st.expander(f"📋 Protocolo #{row['id']} | {row['nome']} - Status: **{row['status']}**"):
                    st.write(f"**Data Prevista:** {row['data']} às {row['hora']}")
                    
                    # Tabela com os seriais para conferência rápida
                    df_seriais = pd.DataFrame({"Serial do Equipamento": lista_seriais})
                    st.dataframe(df_seriais, use_container_width=True)
                    
                    # 1. Exportar para Excel
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_seriais.to_excel(writer, index=False, sheet_name='Seriais')
                    
                    st.download_button(
                        label="📥 Exportar Seriais para Excel",
                        data=buffer.getvalue(),
                        file_name=f"seriais_protocolo_{row['id']}.xlsx",
                        mime="application/vnd.ms-excel",
                        key=f"dl_{row['id']}"
                    )
                    
                    st.divider()
                    col_acao1, col_acao2 = st.columns(2)
                    
                    with col_acao1:
                        # Passo 1: Validar e liberar para o físico vir
                        if row['status'] == "Aguardando Triagem":
                            if st.button("✅ Liberar para Recebimento Físico", key=f"lib_{row['id']}", type="primary"):
                                cursor.execute("UPDATE agendamentos SET status = 'Disponível para Receber' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.rerun()
                                
                    with col_acao2:
                        # Passo 2: O motorista chegou, o almoxarife valida na hora sem lentidão e fecha tudo
                        if row['status'] == "Disponível para Receber":
                            st.markdown("🍏 **Equipamentos chegaram no balcão?** Marque como recebido para dar baixa definitiva.")
                            if st.button("📦 Confirmar Recebimento Físico e Fechar", key=f"fec_{row['id']}", type="primary"):
                                cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.success("Devolução encerrada com sucesso!")
                                st.rerun()

    # --- VISÃO DO USUÁRIO ---
    else:
        st.title("📦 Solicitação de Devolução Antecipada")
        
        # Verificar se o usuário já possui um agendamento ativo
        cursor.execute("SELECT id, data, hora, status FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        agendamento_ativo = cursor.fetchone()
        
        if agendamento_ativo:
            st.info(f"📆 Você já possui uma solicitação ativa (Protocolo #{agendamento_ativo[0]}) para o dia {agendamento_ativo[1]} às {agendamento_ativo[2]}.")
            st.markdown(f"**Status Atual:** {agendamento_ativo[3]}")
            
            if agendamento_ativo[3] == "Disponível para Receber":
                st.success("🟢 Tudo pronto! Seus dados foram validados pelo almoxarifado. Você já pode levar os equipamentos físicos ao balcão.")
        else:
            # Formulário de Nova Devolução
            st.header("Agende sua Entrega")
            
            col1, col2 = st.columns(2)
            with col1:
                data_agenda = st.date_input("Selecione a Data", min_value=datetime.date.today())
            with col2:
                hora_agenda = st.time_input("Selecione o Horário")
                
            st.subheader("Bipar Equipamentos")
            st.markdown("Clique no campo abaixo e use o leitor de código de barras/Série:")
            
            # Campo preparado para receber o foco do leitor de código de barras (bipagem)
            equipamentos_bipados = st.text_area("Seriais Bipados (Cole ou bipe um por linha)", height=150, placeholder="Bipe o serial...\nBipe o próximo...")
            
            if st.button("Fechar Devolução e Enviar para Triagem", type="primary"):
                if equipamentos_bipados:
                    # Formata a lista de seriais
                    lista_limpa = [item.strip() for item in equipamentos_bipados.replace(",", "\n").split("\n") if item.strip()]
                    seriais_str = ",".join(lista_limpa)
                    
                    # Validar regra das 3 horas
                    valido, mensagem_erro = verificar_regras_agendamento(data_agenda, hora_agenda)
                    
                    if valido:
                        cursor.execute(
                            "INSERT INTO agendamentos (cpf, nome, data, hora, seriais, status) VALUES (?, ?, ?, ?, ?, 'Aguardando Triagem')",
                            (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5], seriais_str)
                        )
                        conn.commit()
                        st.success("✅ Devolução fechada! Enviada para a pasta de triagem do almoxarife.")
                        st.rerun()
                    else:
                        st.error(mensagem_erro)
                else:
                    st.error("⚠️ Você precisa bipar pelo menos um equipamento antes de fechar a devolução.")
