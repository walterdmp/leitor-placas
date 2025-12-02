import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_name="campus.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._criar_tabelas()

    def _criar_tabelas(self):
        # Cria tabela de veículos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS veiculos (
                placa TEXT PRIMARY KEY,
                proprietario TEXT,
                tipo TEXT,   -- OFICIAL ou PARTICULAR
                status TEXT, -- AUTORIZADO, BLOQUEADO ou OCORRENCIA
                tempo_padrao_permanencia_horas REAL DEFAULT 8.0
            )
        """)
        # Cria tabela de histórico de acessos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS acessos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa TEXT,
                entrada DATETIME,
                saida DATETIME NULL
            )
        """)
        self.conn.commit()
        
        # Dados iniciais de teste
        self.cursor.execute("SELECT count(*) FROM veiculos")
        if self.cursor.fetchone()[0] == 0:
            # 1. Veículo Oficial
            self.cursor.execute("INSERT INTO veiculos VALUES ('PWI5F03', 'Diretor Geral', 'OFICIAL', 'AUTORIZADO', 24.0)") 
            
            # 2. Veículo Particular
            self.cursor.execute("INSERT INTO veiculos VALUES ('RUR4C47', 'Estudante Maria', 'PARTICULAR', 'AUTORIZADO', 8.0)") 
            
            # 3. Veículo Bloqueado
            self.cursor.execute("INSERT INTO veiculos VALUES ('FBZ4968', 'Ex-Funcionário', 'PARTICULAR', 'BLOQUEADO', 8.0)") 
            
            # 4. Veículo com Ocorrência
            self.cursor.execute("INSERT INTO veiculos VALUES ('PXH4B02', 'Terceirizado Suspeito', 'PARTICULAR', 'OCORRENCIA', 8.0)") 
            
            # 5. Veículo Oficial (para saída)
            self.cursor.execute("INSERT INTO veiculos VALUES ('RNB7G77', 'Prof. Ana', 'OFICIAL', 'AUTORIZADO', 24.0)")
            
            # Simulação de permanência excedida (12h atrás)
            data_passada = datetime.now() - timedelta(hours=12)
            self.cursor.execute("INSERT INTO acessos (placa, entrada, saida) VALUES (?, ?, NULL)", 
                            ('RUR4C47', data_passada.strftime('%Y-%m-%d %H:%M:%S.%f')))
            
            self.conn.commit()
            print("Banco de dados inicializado com sucesso.")

    def verificar_placa(self, placa):
        self.cursor.execute("SELECT proprietario, tipo, status, tempo_padrao_permanencia_horas FROM veiculos WHERE placa = ?", (placa,))
        return self.cursor.fetchone()

    def registrar_acesso(self, placa):
        agora = datetime.now()
        
        # Verifica se já existe entrada sem saída (veículo no campus)
        self.cursor.execute("SELECT id, entrada FROM acessos WHERE placa = ? AND saida IS NULL", (placa,))
        registro_ativo = self.cursor.fetchone()
        
        if registro_ativo:
            # Registra saída
            id_acesso, entrada = registro_ativo
            self.cursor.execute("UPDATE acessos SET saida = ? WHERE id = ?", (agora, id_acesso))
            self.conn.commit()
            return "SAIDA", entrada
        else:
            # Registra entrada
            self.cursor.execute("INSERT INTO acessos (placa, entrada, saida) VALUES (?, ?, NULL)", (placa, agora))
            self.conn.commit()
            return "ENTRADA", agora

    def verificar_alertas_permanencia(self):
        """Verificação dos veículos que excederam o tempo limite."""
        alertas = []
        self.cursor.execute("""
            SELECT 
                a.placa, 
                a.entrada, 
                v.tempo_padrao_permanencia_horas
            FROM acessos a
            INNER JOIN veiculos v ON a.placa = v.placa
            WHERE a.saida IS NULL
        """)
        registros_ativos = self.cursor.fetchall()
        
        agora = datetime.now()
        for placa, entrada_str, tempo_limite_horas in registros_ativos:
            entrada = datetime.strptime(entrada_str, '%Y-%m-%d %H:%M:%S.%f')
            tempo_decorrido = (agora - entrada).total_seconds() / 3600
            
            if tempo_decorrido > tempo_limite_horas:
                alertas.append({
                    'placa': placa,
                    'entrada': entrada.strftime('%H:%M'),
                    'tempo_limite': f"{tempo_limite_horas:.1f}h",
                    'tempo_decorrido': f"{tempo_decorrido:.1f}h"
                })
        return alertas

    def fechar(self):
        self.conn.close()