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

# --- FUNÇÕES DE VALIDAÇÃO E EXCEL ---
def verificar_regras_agendamento(data_selecionada, hora_selecionada):
    cursor.execute("SELECT hora FROM agendamentos WHERE data = ? AND status != 'Finalizado'", (str(data_selecionada),))
    agendamentos_dia = cursor.fetchall()
    
    nova_hora_minutos = hora_selecionada.hour * 60 + hora_selecionada.minute
    
    for (h,) in agendamentos_dia:
        h_atual = datetime.datetime.strptime(h, "%H:%M").time()
        atual_minutos = h_atual.hour * 60 + h_atual.minute
        
        # Regra: Intervalo mínimo de 3 horas (180 minutos) entre agendamentos
        if abs(nova_hora_minutos - atual_minutos) < 180:
            return False, f"⚠️ Horário indisponível! Outra pessoa agendou às {h}. É necessário um intervalo mínimo de 3 horas."
            
    return True, ""

def gerar_excel_nativo(lista_seriais):
    df_seriais = pd.DataFrame({"Seriais dos Equipamentos": lista_seriais})
    # Converte os dados nativamente para CSV com formatação compatível com Excel (UTF-8 com BOM e ponto-e-vírgula)
    # Isso abre direto no Excel perfeitamente sem quebrar acentos ou colunas
    csv_data = df_seriais.to_csv(index=False, sep=';', encoding='utf-8-sig')
    return csv_data.encode('utf-8-sig'), df_seriais

# --- TELA DE LOGIN E CADASTRO ---
if not st.session_state['logado']:
    st.title("📦 Acesso ao Sistema de Devolução")
    
    aba_login, aba_cadastro = st.tabs(["🔐 Entrar no Sistema", "📝 Criar Cadastro de Volante"])
    
    with aba_login:
        cpf_login = st.text_input("Digite seu CPF (ou 000 para Almoxarife)", key="login_cpf")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Acessar Sistema", type="primary", use_container_width=True):
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
                    st.error("❌ CPF ou Senha incorretos.")
                    
    with aba_cadastro:
        st.markdown("### Cadastro exclusivo para novos Volantes")
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

# --- SISTEMA CONECTADO E SEPARADO ---
else:
    # Cabeçalho de Identificação e Botão Sair comum
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

    # =========================================================================
    # 2º ACESSO: EXCLUSIVO DO ALMOXARIFE
    # =========================================================================
    if st.session_state['eh_almoxarife']:
        st.title("🔑 Painel de Triagem (Visão do Almoxarife)")
        st.markdown("Gerencie as solicitações recebidas, valide os aparelhos e mude o status para liberação do balcão.")
        
        df_agendamentos = pd.read_sql_query("SELECT * FROM agendamentos WHERE status != 'Finalizado'", conn)
        
        if df_agendamentos.empty:
            st.info("Visualização limpa. Não há solicitações pendentes no momento.")
        else:
            for idx, row in df_agendamentos.iterrows():
                lista_seriais = [s.strip() for s in row['seriais'].split(",") if s.strip()]
                
                with st.expander(f"📁 Pasta Aberta: Protocolo #{row['id']} | Volante: {row['nome']} | Status: {row['status']}"):
                    st.markdown(f"**Data Planejada:** {row['data']} às {row['hora']} | **CPF Volante:** {row['cpf']}")
                    
                    # Tabela visível dos aparelhos bipados
                    dados_excel, df_visualizar = gerar_excel_nativo(lista_seriais)
                    st.dataframe(df_visualizar, use_container_width=True)
                    
                    # Botão de exportação nativo Excel (.csv configurado para Excel)
                    st.download_button(
                        label="📥 Exportar Fila para Excel (.csv)",
                        data=dados_excel,
                        file_name=f"almoxarifado_protocolo_{row['id']}.csv",
                        mime="text/csv",
                        key=f"excel_almox_{row['id']}"
                    )
                    
                    st.write("")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if row['status'] == "Aguardando Triagem":
                            if st.button("🚀 Validar e Colocar Disponível para Receber", key=f"lib_{row['id']}", use_container_width=True):
                                cursor.execute("UPDATE agendamentos SET status = 'Disponível para Receber' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.success("Atualizado! O Volante agora visualiza que o balcão está pronto.")
                                st.rerun()
                    with col_b2:
                        if row['status'] == "Disponível para Receber":
                            if st.button("📥 Fechar Devolução (Aparelhos Entregues no Físico)", key=f"fec_{row['id']}", type="primary", use_container_width=True):
                                cursor.execute("UPDATE agendamentos SET status = 'Finalizado' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.success("Perfeito! Devolução encerrada sem lentidão de sistema.")
                                st.rerun()

    # =========================================================================
    # 1º ACESSO: EXCLUSIVO DO VOLANTE
    # =========================================================================
    else:
        st.title("📦 Solicitação de Devolução Antecipada (Visão do Volante)")
        
        cursor.execute("SELECT id, data, hora, status, seriais FROM agendamentos WHERE cpf = ? AND status != 'Finalizado'", (st.session_state['usuario_cpf'],))
        agendamento_ativo = cursor.fetchone()
        
        if agendamento_ativo:
            proto_id, proto_data, proto_hora, proto_status, proto_seriais = agendamento_ativo
            lista_seriais_volante = [s.strip() for s in proto_seriais.split(",") if s.strip()]
            
            st.info(f"📆 Você possui uma solicitação activa (Protocolo #{proto_id}) marcada para o dia {proto_data} às {proto_hora}.")
            
            if proto_status == "Aguardando Triagem":
                st.warning("⏳ Status Atual: **Aguardando Triagem**. Aguarde o almoxarife validar seus seriais para liberar sua ida ao balcão.")
            elif proto_status == "Disponível para Receber":
                st.success("🟢 Status Atual: **Disponível para Receber!** O almoxarife validou seus dados. Pode levar os aparelhos físicos ao almoxarifado.")
            
            # --- PASTA EXCLUSIVA DO VOLANTE PARA VISUALIZAÇÃO E EXCEL ---
            st.markdown("---")
            st.subheader(f"📁 Minha Pasta de Entrega - Protocolo #{proto_id}")
            st.markdown("Confira abaixo todos os aparelhos que você bipou nesta solicitação:")
            
            dados_excel_volante, df_visualizar_volante = gerar_excel_nativo(lista_seriais_volante)
            st.dataframe(df_visualizar_volante, use_container_width=True)
            
            st.download_button(
                label="📥 Exportar Meus Aparelhos Bipados para Excel (.csv)",
                data=dados_excel_volante,
                file_name=f"minha_lista_protocolo_{proto_id}.csv",
                mime="text/csv",
                key=f"excel_volante_{proto_id}"
            )
            
        else:
            st.header("Agende sua Nova Entrega")
            col1, col2 = st.columns(2)
            with col1:
                data_agenda = st.date_input("Selecione a Data", min_value=datetime.date.today())
            with col2:
                hora_agenda = st.time_input("Selecione o Horário")
                
            st.subheader("Bipar Equipamentos")
            st.markdown("Dê um clique na caixa de texto abaixo e comece a bipar os seriais com o seu leitor:")
            
            equipamentos_bipados = st.text_area("Seriais (Insira um por linha)", height=150, placeholder="Bipe o código...\nBipe o próximo...")
            
            if st.button("Fechar Devolução e Enviar para Triagem", type="primary", use_container_width=True):
                if equipamentos_bipados.strip():
                    lista_limpa = [item.strip() for item in equipamentos_bipados.replace(",", "\n").split("\n") if item.strip()]
                    seriais_str = ",".join(lista_limpa)
                    
                    valido, msg_erro = verificar_regras_agendamento(data_agenda, hora_agenda)
                    
                    if valido:
                        cursor.execute(
                            "INSERT INTO agendamentos (cpf, nome, data, hora, seriais, status) VALUES (?, ?, ?, ?, ?, 'Aguardando Triagem')",
                            (st.session_state['usuario_cpf'], st.session_state['usuario_nome'], str(data_agenda), str(hora_agenda)[:5], seriais_str)
                        )
                        conn.commit()
                        st.success("✅ Devolução fechada com sucesso! Pasta de triagem criada.")
                        st.rerun()
                    else:
                        st.error(msg_erro)
                else:
                    st.error("⚠️ Erro: Você precisa bipar pelo menos 1 equipamento antes de enviar.")
