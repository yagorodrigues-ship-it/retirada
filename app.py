
import streamlit as st
import pandas as pd
import datetime

# Configuração da página
st.set_page_config(page_title="Agendamento Almoxarifado", layout="wide", page_icon="📦")

st.title("📦 Sistema de Devolução Antecipada")
st.markdown("Evite filas. Agende sua devolução e agilize o atendimento.")

# Criando as abas para separar as visões
aba_usuario, aba_almoxarife = st.tabs(["👤 Área do Usuário", "🔑 Painel do Almoxarife"])

# --- BANCO DE DADOS TEMPORÁRIO (Simulação) ---
# Na prática, você salvará isso em um banco de dados real ou arquivo CSV
if 'agendamentos' not in st.session_state:
    st.session_state['agendamentos'] = []

# --- 1. ÁREA DO USUÁRIO ---
with aba_usuario:
    st.header("Agende sua Devolução")
    
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Seu Nome Completo")
        matricula = st.text_input("Matrícula/CPF")
    with col2:
        data_agenda = st.date_input("Data da Devolução", min_value=datetime.date.today())
        hora_agenda = st.time_input("Horário Estimado")

    st.subheader("Lista de Equipamentos")
    st.markdown("Insira os números de série/patrimônio separados por vírgula ou um por linha:")
    
    # Texto livre para colar os 50 equipamentos de uma vez
    equipamentos_texto = st.text_area("Códigos dos Equipamentos", placeholder="Ex: REQ123\nREQ124\nREQ125", height=150)

    if st.button("Confirmar Agendamento", type="primary"):
        if nome and matricula and equipamentos_texto:
            # Processa o texto para gerar uma lista limpa
            lista_equipos = [item.strip() for item in equipamentos_texto.replace(",", "\n").split("\n") if item.strip()]
            
            # Salva o agendamento na memória
            novo_agendamento = {
                "id": len(st.session_state['agendamentos']) + 1,
                "nome": nome,
                "matricula": matricula,
                "data": str(data_agenda),
                "hora": str(hora_agenda)[:5],
                "equipamentos": lista_equipos,
                "status": "Pendente de Análise"
            }
            st.session_state['agendamentos'].append(novo_agendamento)
            
            st.success(f"✅ Agendamento realizado com sucesso! Protocolo: #{novo_agendamento['id']}")
            st.balloons()
        else:
            st.error("⚠️ Por favor, preencha todos os campos e insira os equipamentos.")

# --- 2. PAINEL DO ALMOXARIFE ---
with aba_almoxarife:
    st.header("Painel de Triagem Antecipada")
    
    if not st.session_state['agendamentos']:
        st.info("Nenhum agendamento realizado até o momento.")
    else:
        # Listar agendamentos pendentes
        for agen in st.session_state['agendamentos']:
            with st.expander(f"📅 Horário: {agen['hora']} | {agen['nome']} (#{agen['id']}) - {len(agen['equipamentos'])} itens"):
                st.write(f"**Funcionário:** {agen['nome']} ({agen['matricula']})")
                st.write(f"**Data prevista:** {agen['data']} às {agen['hora']}")
                
                st.markdown("### Status da Pré-Consulta nos Sistemas:")
                
                # Simulação da checagem automática
                dados_equipos = []
                for eq in agen['equipamentos']:
                    # Aqui entraria a lógica que consulta seu banco de dados real.
                    # Vamos simular que se o código terminar com '4', dá erro (só para testar o visual)
                    if eq.endswith('4'):
                        status_sistema = "🔴 Divergência (Alocado em outro CPF)"
                    else:
                        status_sistema = "🟢 Liberado para Receber"
                        
                    dados_equipos.append({"Equipamento": eq, "Status no Sistema": status_sistema})
                
                df_equipos = pd.DataFrame(dados_equipos)
                st.dataframe(df_equipos, use_container_width=True)
                
                # Ações do Almoxarife
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("Pré-Aprovar Tudo", key=f"aprov_{agen['id']}", type="primary"):
                        st.success("Agendamento pré-aprovado! Quando o usuário chegar, o recebimento será imediato.")
                with col_btn2:
                    st.button("Notificar Usuário sobre Pendência", key=f"notif_{agen['id']}")
