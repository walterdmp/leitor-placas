import sqlite3
import csv

DB_NAME = "campus.db"
OUTPUT_FILE = "relatorio_acessos.csv"

def gerar_relatorio():
    """Gera CSV com historico de acessos."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Consulta unificada (Acessos + Veiculos)
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
            
            # Cabecalho
            writer.writerow(['Placa', 'Entrada', 'Saída', 'Proprietário', 'Tipo', 'Status Cadastro'])
            
            # Dados
            writer.writerows(registros)
            
        conn.close()
        print(f"\nRelatório gerado: '{OUTPUT_FILE}'")
        
    except sqlite3.Error as e:
        print(f"Erro no banco de dados: {e}")

if __name__ == "__main__":
    gerar_relatorio()