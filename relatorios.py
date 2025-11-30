import sqlite3
import csv
from datetime import datetime

DB_NAME = "campus.db"
OUTPUT_FILE = "relatorio_acessos.csv"

def gerar_relatorio():
    """Gera um relatório de todos os acessos do banco de dados para CSV."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Consulta para unir dados de acesso e cadastro
        cursor.execute("""
            SELECT 
                a.placa, 
                a.entrada, 
                a.saida, 
                v.proprietario, 
                v.tipo, 
                v.status
            FROM acessos a
            LEFT JOIN veiculos v ON a.placa = v.placa
            ORDER BY a.entrada DESC
        """)
        registros = cursor.fetchall()
        
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            
            # Cabeçalho do CSV
            writer.writerow(['Placa', 'Entrada', 'Saída', 'Proprietário', 'Tipo', 'Status Cadastro'])
            
            # Linhas de dados
            writer.writerows(registros)
            
        conn.close()
        print(f"\nRelatório gerado com sucesso em '{OUTPUT_FILE}'.")
        
    except sqlite3.Error as e:
        print(f"Erro ao acessar o banco de dados: {e}")

if __name__ == "__main__":
    gerar_relatorio()