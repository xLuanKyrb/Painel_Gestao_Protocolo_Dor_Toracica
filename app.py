from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import shutil 
from waitress import serve
import os     
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

app.secret_key = 'upa_ecg_chave_super_secreta'

def fazer_backup_diario():
    """Cria uma cópia do banco de dados todo fim de dia"""
    nome_banco = 'upa_eletros.db'
    pasta_backup = 'backups_diarios'
    
    if not os.path.exists(nome_banco):
        return

    if not os.path.exists(pasta_backup):
        os.makedirs(pasta_backup)

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    nome_backup = f"backup_upa_{data_hoje}.db"
    caminho_backup = os.path.join(pasta_backup, nome_backup)

    try:
        shutil.copy2(nome_banco, caminho_backup)
        print(f"[BACKUP SUCESSO] Backup diário salvo: {caminho_backup}")
    except Exception as e:
        print(f"[ERRO BACKUP] Falha ao salvar banco de dados: {e}")

def init_db():
    conn = sqlite3.connect('upa_eletros.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, nascimento TEXT, atendimento TEXT, setor TEXT,
            data_registro TEXT, 
            
            presc_ecg_1 TEXT, prescritor_ecg_1 TEXT,
            exec_ecg_1 TEXT, executor_ecg_1 TEXT,
            exec_rx_1 TEXT, executor_rx_1 TEXT,
            exec_med_1 TEXT, executor_med_1 TEXT,
            vis_crm_1 TEXT, visualizador_crm_1 TEXT,
            laudo_ecg_1 TEXT, medico_ecg_1 TEXT,
            avalia_rota_1 TEXT, avaliador_rota_1 TEXT,
            
            presc_ecg_2 TEXT, prescritor_ecg_2 TEXT,
            exec_ecg_2 TEXT, executor_ecg_2 TEXT,
            exec_rx_2 TEXT, executor_rx_2 TEXT,
            exec_med_2 TEXT, executor_med_2 TEXT,
            vis_crm_2 TEXT, visualizador_crm_2 TEXT,
            laudo_ecg_2 TEXT, medico_ecg_2 TEXT,
            avalia_rota_2 TEXT, avaliador_rota_2 TEXT,
            
            presc_ecg_3 TEXT, prescritor_ecg_3 TEXT,
            exec_ecg_3 TEXT, executor_ecg_3 TEXT,
            exec_rx_3 TEXT, executor_rx_3 TEXT,
            exec_med_3 TEXT, executor_med_3 TEXT,
            vis_crm_3 TEXT, visualizador_crm_3 TEXT,
            laudo_ecg_3 TEXT, medico_ecg_3 TEXT,
            avalia_rota_3 TEXT, avaliador_rota_3 TEXT,
              
            presc_trop_1 TEXT, exec_trop_1 TEXT, executor_trop_1 TEXT,
            presc_trop_2 TEXT, exec_trop_2 TEXT, executor_trop_2 TEXT,
            presc_trop_3 TEXT, exec_trop_3 TEXT, executor_trop_3 TEXT,
            
            destino_trasferencia TEXT,
            hora_trasferencia TEXT,
            cor_paciente TEXT,
            ativo INTEGER DEFAULT 1,
            avaliacao TEXT
        )
    ''')
    
    try: c.execute("ALTER TABLE pacientes ADD COLUMN setor TEXT")
    except sqlite3.OperationalError: pass 
        
    try: c.execute("ALTER TABLE pacientes ADD COLUMN data_registro TEXT")
    except sqlite3.OperationalError: pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS logs_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora_servidor TEXT,
            paciente_id INTEGER,
            acao_realizada TEXT,
            profissional TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def registrar_log(paciente_id, acao, profissional="SISTEMA"):
    conn = sqlite3.connect('upa_eletros.db')
    c = conn.cursor()
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs_auditoria (data_hora_servidor, paciente_id, acao_realizada, profissional) VALUES (?, ?, ?, ?)",
              (agora_str, paciente_id, acao, profissional))
    conn.commit()
    conn.close()

def calcular_prazos(hora_prescricao, hora_exec_ecg=None):
    prazos = {'ecg': None, 'tropo': None, 'med': None, 'rx': None, 'aval': None}
    
    if hora_prescricao and hora_prescricao.strip() != "":
        try:
            mz_presc = datetime.strptime(hora_prescricao, "%H:%M")
            prazos['ecg'] = (mz_presc + timedelta(minutes=10)).strftime("%H:%M")
        except ValueError:
            pass
            
    base_calc = hora_exec_ecg if (hora_exec_ecg and hora_exec_ecg != "N/A" and hora_exec_ecg.strip() != "") else hora_prescricao
    
    if base_calc and base_calc.strip() != "":
        try:
            mz_base = datetime.strptime(base_calc, "%H:%M")
            gap_trop = 15 if base_calc == hora_exec_ecg else 25
            gap_med = 45 if base_calc == hora_exec_ecg else 55
            gap_rx = 75 if base_calc == hora_exec_ecg else 85
            gap_aval = 115 if base_calc == hora_exec_ecg else 125
            
            prazos['tropo'] = (mz_base + timedelta(minutes=gap_trop)).strftime("%H:%M")
            prazos['med'] = (mz_base + timedelta(minutes=gap_med)).strftime("%H:%M")
            prazos['rx'] = (mz_base + timedelta(minutes=gap_rx)).strftime("%H:%M")
            prazos['aval'] = (mz_base + timedelta(minutes=gap_aval)).strftime("%H:%M")
        except ValueError:
            pass
            
    return prazos

def calcular_urgencia(hora_prescricao, ja_executado):
    if not hora_prescricao or ja_executado: 
        return "normal"
    agora = datetime.now()
    try:
        presc_time = datetime.strptime(hora_prescricao, "%H:%M").time()
        presc = datetime.combine(agora.date(), presc_time)
        if presc > agora:
            presc -= timedelta(days=1)
        diff = (agora - presc).total_seconds() / 60
        if diff < 0: return "normal" 
        if diff <= 10: return "verde" 
        elif diff <= 30: return "amarelo"
        else: return "vermelho"
    except:
        return "normal"

def calcular_proximo_ecg(exec_hora):
    if not exec_hora or exec_hora == "N/A": return None
    try:
        exec_dt = datetime.strptime(exec_hora, "%H:%M")
        proximo = (exec_dt + timedelta(hours=3)).time()
        return proximo.strftime("%H:%M")
    except:
        return None

def calcular_progresso_ecg(exec_hora):
    if not exec_hora or exec_hora == "N/A": return None
    try:
        agora = datetime.now()
        exec_time = datetime.strptime(exec_hora, "%H:%M").time()
        exec_dt = datetime.combine(agora.date(), exec_time)
        if exec_dt > agora:
            exec_dt -= timedelta(days=1)
        fim = exec_dt + timedelta(hours=3)
        total = (fim - exec_dt).total_seconds()
        if total <= 0: return None
        decorrido = (agora - exec_dt).total_seconds()
        proporcao = decorrido / total
        if proporcao < 0: proporcao = 0.0
        if proporcao > 1: proporcao = 1.0
        return proporcao
    except:
        return None

def calcular_progresso_geral(p):
    """Calcula os dados para o gráfico circular da 1ª Rota no Jinja/HTML"""
    passos_totais = 0
    passos_concluidos = 0

    campos_verificacao = ['exec_ecg_1']
    if p.get('cor_paciente') != 'normal':
        campos_verificacao.extend(['exec_trop_1', 'exec_med_1', 'exec_rx_1', 'avalia_rota_1'])
    
    for campo in campos_verificacao:
        passos_totais += 1
        valor = p.get(campo)
        if valor and str(valor).strip() != "" and valor != 'N/A':
            passos_concluidos += 1
            
    if passos_totais == 0:
        return 0, 0, 0
    
    pct = (passos_concluidos / passos_totais) * 100
    return passos_concluidos, passos_totais, pct

@app.route('/')
def index():
    busca = request.args.get('q', '').strip().upper()
    conn = sqlite3.connect('upa_eletros.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if busca:
        query = """SELECT * FROM pacientes WHERE ativo = 1 AND 
                   (nome LIKE ? OR atendimento LIKE ? OR 
                    COALESCE(executor_ecg_1, '') LIKE ? OR COALESCE(executor_trop_1, '') LIKE ?) 
                   ORDER BY id DESC"""
        params = (f'%{busca}%', f'%{busca}%', f'%{busca}%', f'%{busca}%')
        c.execute(query, params)
    else:
        c.execute("SELECT * FROM pacientes WHERE ativo = 1 ORDER BY id DESC")
    
    pacientes = processar_lista_pacientes(c.fetchall())
    conn.close()
    return render_template('index.html', pacientes=pacientes, busca_atual=busca)

@app.route('/historico')
def historico():
    conn = sqlite3.connect('upa_eletros.db')
    conn.row_factory = sqlite3.Row  
    c = conn.cursor()
    c.execute("SELECT * FROM pacientes ORDER BY id DESC")
    pacientes = processar_lista_pacientes(c.fetchall())
    conn.close()
    return render_template('historico.html', pacientes=pacientes)

@app.route('/tela')
def tela():
    conn = sqlite3.connect('upa_eletros.db')
    conn.row_factory = sqlite3.Row  
    c = conn.cursor()
    c.execute("SELECT * FROM pacientes WHERE ativo = 1 ORDER BY id DESC")
    pacientes = processar_lista_pacientes(c.fetchall())
    conn.close()
    return render_template('tela.html', pacientes=pacientes)

def processar_lista_pacientes(rows):
    pacientes = [dict(p) for p in rows]
    for p in pacientes:
        p['cor_classe'] = calcular_urgencia(p.get('presc_ecg_1'), p.get('exec_ecg_1'))
        p['prox_ecg_1'] = calcular_proximo_ecg(p.get('exec_ecg_1'))
        p['prox_ecg_2'] = calcular_proximo_ecg(p.get('exec_ecg_2'))
        p['prox_ecg_3'] = calcular_proximo_ecg(p.get('exec_ecg_3'))
        p['prog_ecg_1'] = calcular_progresso_ecg(p.get('exec_ecg_1'))
        p['prog_ecg_2'] = calcular_progresso_ecg(p.get('exec_ecg_2'))
        p['prog_ecg_3'] = calcular_progresso_ecg(p.get('exec_ecg_3'))
        p['alvo_1'] = calcular_prazos(p.get('presc_ecg_1'), p.get('exec_ecg_1'))
        p['alvo_2'] = calcular_prazos(p.get('presc_ecg_2'), p.get('exec_ecg_2'))
        p['alvo_3'] = calcular_prazos(p.get('presc_ecg_3'), p.get('exec_ecg_3'))
        
        concluidos, totais, pct = calcular_progresso_geral(p)
        p['passos_concluidos'] = concluidos
        p['passos_totais'] = totais
        p['porcentagem_conclusao'] = pct
        
    return pacientes

@app.route('/salvar', methods=['POST'])
def salvar():
    id_paciente = request.form.get('id')
    nome_pac = request.form['nome'].strip().upper()
    numero_atendimento = request.form['atendimento'].strip()
    
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    dados_update = (
        nome_pac, request.form['nascimento'], numero_atendimento, request.form.get('setor'),
        request.form.get('presc_ecg_1'), request.form.get('prescritor_ecg_1'),
        request.form.get('presc_ecg_2'), request.form.get('prescritor_ecg_2'),
        request.form.get('presc_ecg_3'), request.form.get('prescritor_ecg_3'),
        request.form.get('presc_trop_1'), request.form.get('presc_trop_2'), request.form.get('presc_trop_3'),
        request.form.get('cor_paciente'), request.form.get('avaliacao')
    )

    conn = sqlite3.connect('upa_eletros.db')
    c = conn.cursor()

    if id_paciente and id_paciente != "":
        c.execute("""UPDATE pacientes SET 
                  nome=?, nascimento=?, atendimento=?, setor=?,
                  presc_ecg_1=?, prescritor_ecg_1=?, presc_ecg_2=?, prescritor_ecg_2=?, 
                  presc_ecg_3=?, prescritor_ecg_3=?, presc_trop_1=?, presc_trop_2=?, presc_trop_3=?, 
                  cor_paciente=?, avaliacao=? WHERE id=?""", dados_update + (id_paciente,))
        conn.commit()
        registrar_log(id_paciente, "EDIÇÃO DE CADASTRO/TRIAGEM", "RECEPÇÃO/ENFERMAGEM")
        
        flash(f"Cadastro de {nome_pac.split(' ')[0]} atualizado!", "success")
    else:
        existente = c.execute("SELECT id FROM pacientes WHERE atendimento = ? AND ativo = 1", (numero_atendimento,)).fetchone()
        
        if existente:
            flash(f"⚠️ Atenção: O atendimento {numero_atendimento} já está ativo no painel! Atualize o card existente na tela.", "danger")
        else:
            dados_insert = (
                nome_pac, request.form['nascimento'], numero_atendimento, request.form.get('setor'), hoje,
                request.form.get('presc_ecg_1'), request.form.get('prescritor_ecg_1'),
                request.form.get('presc_ecg_2'), request.form.get('prescritor_ecg_2'),
                request.form.get('presc_ecg_3'), request.form.get('prescritor_ecg_3'),
                request.form.get('presc_trop_1'), request.form.get('presc_trop_2'), request.form.get('presc_trop_3'),
                request.form.get('cor_paciente'), request.form.get('avaliacao')
            )
            
            c.execute("""INSERT INTO pacientes (
                      nome, nascimento, atendimento, setor, data_registro, 
                      presc_ecg_1, prescritor_ecg_1, presc_ecg_2, prescritor_ecg_2, presc_ecg_3, prescritor_ecg_3, 
                      presc_trop_1, presc_trop_2, presc_trop_3, cor_paciente, avaliacao
                      ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", dados_insert)
            conn.commit()
            novo_id = c.lastrowid
            registrar_log(novo_id, f"ENTRADA NO PROTOCOLO - {request.form.get('cor_paciente').upper()}", "RECEPÇÃO/ENFERMAGEM")
            
            flash(f"✅ Paciente {nome_pac.split(' ')[0]} adicionado ao protocolo!", "success")
    
    conn.close()
    return redirect(url_for('index'))

@app.route('/marcar_execucao', methods=['POST'])
def marcar_execucao():
    id_paciente = request.form['id_rota']
    coluna_hora = request.form['coluna_selecionada'] 
    profissional = request.form['profissional'].strip().upper()
    
    agora = request.form.get('horario')
    anular = request.form.get('anular_acao')
    
    if anular == "sim":
        agora = "N/A"
        
    colunas_validas = [
        'exec_ecg_1', 'exec_rx_1', 'exec_med_1', 'laudo_ecg_1', 'avalia_rota_1', 'vis_crm_1', 'exec_trop_1',
        'exec_ecg_2', 'exec_rx_2', 'exec_med_2', 'laudo_ecg_2', 'avalia_rota_2', 'vis_crm_2', 'exec_trop_2',
        'exec_ecg_3', 'exec_rx_3', 'exec_med_3', 'laudo_ecg_3', 'avalia_rota_3', 'vis_crm_3', 'exec_trop_3'
    ]
    
    if coluna_hora not in colunas_validas:
        flash("❌ Erro de Segurança: Coluna do banco de dados não permitida.", "danger")
        return redirect(url_for('index'))
    
    if "laudo" in coluna_hora: coluna_prof = coluna_hora.replace('laudo', 'medico')
    elif "exec" in coluna_hora: coluna_prof = coluna_hora.replace('exec', 'executor')
    elif "avalia_rota" in coluna_hora: coluna_prof = coluna_hora.replace('avalia', 'avaliador') 
    elif "vis_crm" in coluna_hora: coluna_prof = coluna_hora.replace('vis_crm', 'visualizador_crm')
    else: return "Erro: Coluna inválida", 400

    conn = sqlite3.connect('upa_eletros.db')
    try:
        query = f"UPDATE pacientes SET {coluna_hora} = ?, {coluna_prof} = ? WHERE id = ?"
        conn.execute(query, (agora, profissional, id_paciente))
        conn.commit()
        
        acao_amigavel = f"Registrou {coluna_hora.upper()} ({agora})"
        registrar_log(id_paciente, acao_amigavel, profissional)
    except Exception as e:
        print(f"Erro no SQL: {e}")
        flash(" Falha ao gravar a ação no banco de dados.", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/registrar_saida', methods=['POST'])
def registrar_saida():
    id_paciente = request.form.get('id_paciente')
    tipo = request.form.get('tipo_saida')
    destino = request.form.get('destino_transferencia') 
    hora_saida = request.form.get('hora_transferencia')
    medico = request.form.get('medico_alta')

    if destino:
        texto_saida = f"{tipo.upper()} - {destino} (Resp: {medico.upper()})"
    else:
        texto_saida = f"{tipo.upper()} (Resp: {medico.upper()})"

    conn = sqlite3.connect('upa_eletros.db')
    c = conn.cursor()
    try:
        c.execute("""UPDATE pacientes SET destino_trasferencia = ?, hora_trasferencia = ?, ativo = 0 WHERE id = ?""", 
                  (texto_saida, hora_saida, id_paciente))
        conn.commit()
        registrar_log(id_paciente, f"DESFECHO: {texto_saida}", "ADMINISTRAÇÃO")
    except sqlite3.OperationalError as e:
        print(f"Erro ao atualizar: {e}")
    finally:
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/imprimir_resumo/<int:id>')
def imprimir_resumo(id):
    conn = sqlite3.connect('upa_eletros.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM pacientes WHERE id = ?", (id,))
    linha = c.fetchone()
    conn.close()

    if not linha:
        return "Paciente não encontrado", 404

    paciente = dict(linha)
    paciente['alvo_1'] = calcular_prazos(paciente.get('presc_ecg_1'), paciente.get('exec_ecg_1'))
    paciente['alvo_2'] = calcular_prazos(paciente.get('presc_ecg_2'), paciente.get('exec_ecg_2'))
    paciente['alvo_3'] = calcular_prazos(paciente.get('presc_ecg_3'), paciente.get('exec_ecg_3'))
    
    data_impressao = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    return render_template('resumo_impresso.html', p=paciente, data_impressao=data_impressao)

@app.route('/remover/<int:id>')
def remover(id):
    conn = sqlite3.connect('upa_eletros.db')
    c = conn.cursor()
    c.execute("UPDATE pacientes SET ativo = 0 WHERE id = ?", (id,))
    conn.commit()
    registrar_log(id, "OCULTOU PACIENTE DO PAINEL MANUALMENTE", "ADMINISTRAÇÃO")
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    agendador = BackgroundScheduler(daemon=True)
    agendador.add_job(fazer_backup_diario, 'cron', hour=23, minute=50)
    agendador.start()
    print("🛡️ Serviço de Backup Automático Iniciado!")
    print("🚀 Iniciando Servidor WSGI de Produção (Waitress) na porta 5000...")
    serve(app, host='0.0.0.0', port=5000, threads=6)