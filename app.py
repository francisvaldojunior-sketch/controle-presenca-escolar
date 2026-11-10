import streamlit as st
from supabase import create_client
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import qrcode
from io import BytesIO

st.set_page_config(page_title="Controle de Entrada Escolar", page_icon="🏫", layout="centered")

TZ = ZoneInfo("America/Fortaleza")

def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = get_supabase()
except Exception:
    st.error("Banco de dados não configurado. Confira os Secrets do Streamlit.")
    st.stop()

def now_local():
    return datetime.now(TZ)

def get_student(matricula):
    result = supabase.table("alunos").select("matricula,nome,ativo").eq("matricula", matricula).eq("ativo", True).limit(1).execute()
    return result.data[0] if result.data else None

def registrar(matricula):
    aluno = get_student(matricula)
    if not aluno:
        return False, "Matrícula não encontrada ou aluno inativo."
    agora = now_local()
    dia = agora.strftime("%Y-%m-%d")
    # Consulta duplicidade para o mesmo aluno no dia.
    existente = (supabase.table("entradas")
        .select("id,horario")
        .eq("matricula", matricula)
        .eq("data", dia)
        .limit(1).execute())
    if existente.data:
        horario = existente.data[0]["horario"]
        return False, f"Entrada já registrada hoje às {horario}."
    supabase.table("entradas").insert({
        "matricula": matricula,
        "nome": aluno["nome"],
        "data": dia,
        "horario": agora.strftime("%H:%M:%S")
    }).execute()
    return True, f"Entrada registrada! Bem-vindo(a), {aluno['nome']}."

st.title("🏫 Controle de Entrada dos Alunos")
st.caption("Registro de chegada à escola")
st.write(f"**Data:** {now_local().strftime('%d/%m/%Y')}  ·  **Horário:** {now_local().strftime('%H:%M:%S')}")

tab_entrada, tab_admin = st.tabs(["Registrar entrada", "Área administrativa"])

with tab_entrada:
    st.subheader("Digite sua matrícula")
    with st.form("form_entrada", clear_on_submit=True):
        matricula = st.text_input("Matrícula", max_chars=30)
        enviar = st.form_submit_button("Registrar entrada", use_container_width=True)
    if enviar:
        matricula = matricula.strip()
        if not matricula:
            st.warning("Digite sua matrícula.")
        else:
            try:
                ok, mensagem = registrar(matricula)
                if ok:
                    st.success(mensagem)
                else:
                    st.warning(mensagem)
            except Exception:
                st.error("Não foi possível registrar. Tente novamente ou procure a secretaria.")

with tab_admin:
    st.subheader("Acesso restrito")
    senha = st.text_input("Senha administrativa", type="password", key="senha_admin")
    if st.button("Entrar na administração"):
        if senha == st.secrets.get("ADMIN_PASSWORD", "") and senha:
            st.session_state["admin_ok"] = True
        else:
            st.session_state["admin_ok"] = False
            st.error("Senha incorreta.")

    if st.session_state.get("admin_ok", False):
        st.success("Acesso autorizado.")
        escolha = st.radio("Função", ["Cadastrar aluno", "Consultar entradas", "Gerar QR Code"], horizontal=False)

        if escolha == "Cadastrar aluno":
            with st.form("cadastro_aluno", clear_on_submit=True):
                mat = st.text_input("Matrícula")
                nome = st.text_input("Nome completo")
                ativo = st.checkbox("Aluno ativo", value=True)
                salvar = st.form_submit_button("Salvar cadastro")
            if salvar:
                mat, nome = mat.strip(), nome.strip()
                if not mat or not nome:
                    st.warning("Preencha matrícula e nome.")
                else:
                    try:
                        supabase.table("alunos").upsert({"matricula": mat, "nome": nome, "ativo": ativo}, on_conflict="matricula").execute()
                        st.success("Cadastro salvo.")
                    except Exception:
                        st.error("Erro ao salvar cadastro. Verifique a tabela no Supabase.")

        elif escolha == "Consultar entradas":
            data_escolhida = st.date_input("Data", value=now_local().date())
            if st.button("Consultar"):
                try:
                    registros = (supabase.table("entradas")
                        .select("matricula,nome,data,horario")
                        .eq("data", data_escolhida.isoformat())
                        .order("horario").execute()).data
                    if registros:
                        df = pd.DataFrame(registros)
                        df.columns = ["Matrícula", "Nome", "Data", "Horário"]
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button("Baixar relatório CSV", csv, file_name=f"entradas_{data_escolhida.isoformat()}.csv", mime="text/csv")
                        st.metric("Entradas registradas", len(df))
                    else:
                        st.info("Nenhuma entrada registrada nesta data.")
                except Exception:
                    st.error("Erro ao consultar registros.")

        elif escolha == "Gerar QR Code":
            url_app = st.text_input("Cole aqui o endereço público do aplicativo", placeholder="https://seu-app.streamlit.app")
            if url_app.startswith("https://"):
                img = qrcode.make(url_app)
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                st.image(buffer.getvalue(), caption="QR Code para abrir o sistema")
                st.download_button("Baixar QR Code PNG", buffer.getvalue(), file_name="qrcode_controle_entrada.png", mime="image/png")
            else:
                st.info("Cole o endereço HTTPS do aplicativo para gerar o QR Code.")

        if st.button("Sair da administração"):
            st.session_state["admin_ok"] = False
            st.rerun()

st.divider()
st.caption("Sistema de registro de chegada. Em caso de erro, procure a secretaria.")
