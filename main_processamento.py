import cv2
import easyocr
import numpy as np
import os
import re
import warnings
import difflib
from database import Database

# Suprime avisos do PyTorch
warnings.filterwarnings("ignore", category=UserWarning)

# Configurações Visuais (Cores BGR)
VERDE = (0, 255, 0)
VERMELHO = (0, 0, 255)
AMARELO = (0, 255, 255)
AZUL = (255, 0, 0)
CINZA = (150, 150, 150)

class SistemaProcessamentoPlacas:
    def __init__(self, db_name="campus.db"):
        self.db = Database(db_name)
        # Inicializa o OCR
        self.reader = easyocr.Reader(['pt'], gpu=False) 
        self.pasta_imagens = "imagens_teste"
        
        # Carrega placas cadastradas para correção inteligente (Fuzzy Match)
        self.placas_conhecidas = self._carregar_placas_conhecidas()

    def _carregar_placas_conhecidas(self):
        """Carrega lista de placas do banco para ajudar na correção de leitura."""
        try:
            self.db.cursor.execute("SELECT placa FROM veiculos")
            return [row[0] for row in self.db.cursor.fetchall()]
        except Exception:
            return []

    def processar_imagem(self, caminho_imagem):
        frame = cv2.imread(caminho_imagem)
        if frame is None:
            print(f"Erro ao carregar: {caminho_imagem}")
            return
            
        print(f"\n--- Analisando: {os.path.basename(caminho_imagem)} ---")

        # --- ESTRATÉGIA MULTI-PASS (Tenta ler de várias formas) ---
        # Preparação das diferentes versões da imagem
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. CLAHE (Equalização Adaptativa - Ótimo para o Carro 5 e Carro 2)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        img_clahe = clahe.apply(gray)
        
        # 2. Processada (Filtro Bilateral + Normalização - Ótimo para Carro 6)
        img_blur = cv2.bilateralFilter(gray, 11, 17, 17)
        img_norm = cv2.normalize(img_blur, None, 0, 255, cv2.NORM_MINMAX)

        # Lista de tentativas: (Imagem, Nome Config, Zoom)
        # Ordem importa: Tenta o mais leve primeiro.
        tentativas = [
            (gray, "Padrao", 1.1),         # Tenta ler imagem limpa (Carro 2)
            (img_clahe, "CLAHE", 1.2),     # Tenta ler com contraste melhorado (Carro 5)
            (img_norm, "Processada", 2.0), # Tenta ler com zoom e filtros (Carro 6)
            (gray, "ZoomMax", 3.0)         # Último recurso
        ]

        melhor_candidato = None

        for (img_input, nome_config, zoom) in tentativas:
            # Tenta ler com a configuração atual
            resultados = self.reader.readtext(img_input, paragraph=False, decoder='beamsearch', mag_ratio=zoom)
            
            for (bbox, texto, prob) in resultados:
                texto_limpo = texto.upper().replace("-", "").replace(" ", "").replace(":", "")
                if len(texto_limpo) < 6: continue
                
                # 1. Pós-Processamento Heurístico (Regras de Posição)
                placa_lida = self.corrigir_placa_heuristica(texto_limpo)
                
                if self.validar_padrao_placa(placa_lida):
                    
                    # 2. Correção Fuzzy com Banco de Dados
                    # Tenta encontrar essa placa no banco, mesmo que tenha erros (Ex: PII5F08 -> PW15F03)
                    placa_final, corrigido_pelo_banco = self.tenta_corrigir_pelo_banco(placa_lida)
                    
                    candidato = {
                        'placa': placa_final,
                        'bbox': bbox,
                        'prob': prob,
                        'corrigido': corrigido_pelo_banco,
                        'origem': nome_config
                    }

                    # Se achamos uma placa que bate com o banco, paramos imediatamente (Sucesso!)
                    if corrigido_pelo_banco:
                        melhor_candidato = candidato
                        break 
                    
                    # Se não bate com banco, guardamos a melhor leitura "Visitante" até agora
                    if melhor_candidato is None or prob > melhor_candidato['prob']:
                        melhor_candidato = candidato
            
            # Se já achou uma placa confirmada no banco, não precisa tentar os outros filtros
            if melhor_candidato and melhor_candidato['corrigido']:
                break

        # --- FIM DO PROCESSAMENTO ---
        
        placas_para_desenhar = []
        
        if melhor_candidato:
            placa_final = melhor_candidato['placa']
            bbox = melhor_candidato['bbox']
            
            # Recupera coordenadas para desenho
            (x0, y0), (x2, y2) = bbox[0], bbox[2]
            x, y, w, h = int(x0), int(y0), int(x2 - x0), int(y2 - y0)

            # Lógica de Negócio (Requisitos)
            dados = self.db.verificar_placa(placa_final)
            cor = CINZA
            status_txt = "VISITANTE"

            if dados:
                proprietario, tipo, status, _ = dados
                if status in ['BLOQUEADO', 'OCORRENCIA']:
                    cor = VERMELHO
                    status_txt = f"ALERTA: {status}"
                    print(f"🚨 GATILHO (Req 7): Veículo {status} identificado: {placa_final}")
                else:
                    cor = VERDE if tipo == 'OFICIAL' else AZUL
                    tipo_movimento, horario = self.db.registrar_acesso(placa_final)
                    status_txt = f"{tipo_movimento}"
                    print(f"✅ REGISTRO (Req 4): {placa_final} ({tipo}) - {proprietario}")
                    if melhor_candidato['corrigido']:
                        print(f"   (Leitura ajustada via Banco de Dados)")
            else:
                cor = AMARELO
                print(f"⚠️ VISITANTE: {placa_final} não consta na base.")

            placas_para_desenhar.append({
                'coords': (x, y, w, h),
                'texto_exibir': placa_final,
                'status': status_txt,
                'cor': cor
            })
        else:
            print(f"Falha: Nenhuma placa válida detectada na imagem.")

        self._desenhar_interface(frame, placas_para_desenhar)
        
        # Exibição
        fator = 0.5
        novo_tam = (int(frame.shape[1] * fator), int(frame.shape[0] * fator))
        img_final = cv2.resize(frame, novo_tam)
        cv2.imshow('Processamento Inteligente', img_final)
        cv2.waitKey(0)

    def tenta_corrigir_pelo_banco(self, placa_lida):
        """Usa difflib para achar a placa mais parecida no banco se houver erros de OCR."""
        # 1. Verifica match exato
        if placa_lida in self.placas_conhecidas:
            return placa_lida, True
        
        # 2. Busca aproximada (Corrige PII5F08 -> PW15F03)
        # cutoff=0.55 permite recuperar erros onde ~40% da placa está errada/confusa
        matches = difflib.get_close_matches(placa_lida, self.placas_conhecidas, n=1, cutoff=0.55)
        
        if matches:
            sugerida = matches[0]
            print(f"🔧 Auto-correção Fuzzy: Lido '{placa_lida}' -> Ajustado para '{sugerida}'")
            return sugerida, True
            
        return placa_lida, False

    def corrigir_placa_heuristica(self, texto):
        """Correção baseada em posição dos caracteres."""
        # Mapeamentos comuns de erro OCR
        num_para_letra = {'0': 'O', '1': 'I', '2': 'Z', '8': 'B', '5': 'S', '4': 'A', '6': 'G', '7': 'Z'}
        letra_para_num = {'O': '0', 'I': '1', 'Z': '2', 'B': '8', 'S': '5', 'A': '4', 'G': '6', 'Q': '0', 'D': '0'}

        if len(texto) > 7: texto = texto[:7]
        if len(texto) < 7: return texto 

        lista = list(texto)

        # Regras rígidas de posição (Mercosul e Antiga)
        # 1. Três primeiros sempre LETRAS
        for i in range(3):
            if lista[i] in num_para_letra: lista[i] = num_para_letra[lista[i]]

        # 2. Quarto sempre NÚMERO
        if lista[3] in letra_para_num: lista[3] = letra_para_num[lista[3]]

        # 3. Quinto define o padrão (Letra=Mercosul, Número=Antiga)
        # Assume Mercosul se parecer letra
        char_5 = lista[4]
        eh_mercosul = char_5.isalpha() or char_5 in num_para_letra
        
        if eh_mercosul:
             if lista[4] in num_para_letra: lista[4] = num_para_letra[lista[4]]
        else:
             if lista[4] in letra_para_num: lista[4] = letra_para_num[lista[4]]

        # 4. Dois últimos sempre NÚMEROS
        for i in range(5, 7):
             if lista[i] in letra_para_num: lista[i] = letra_para_num[lista[i]]

        return "".join(lista)

    def validar_padrao_placa(self, texto):
        regex_mercosul = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'
        regex_antiga = r'^[A-Z]{3}[0-9]{4}$'
        return re.match(regex_mercosul, texto) or re.match(regex_antiga, texto)

    def _desenhar_interface(self, frame, infos):
        for info in infos:
            x, y, w, h = info['coords']
            cor = info['cor']
            texto = info['texto_exibir']
            status = info['status']

            cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 3)
            cv2.rectangle(frame, (x, y - 60), (x + w, y), cor, -1)
            cv2.putText(frame, texto, (x + 5, y - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, status, (x + 5, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def executar_processamento(self):
        if not os.path.exists(self.pasta_imagens):
            print(f"🚨 ERRO: Pasta '{self.pasta_imagens}' não encontrada.")
            return

        arquivos = sorted([f for f in os.listdir(self.pasta_imagens) if f.lower().endswith(('jpg','png','jpeg'))])
        print(f"Iniciando processamento de {len(arquivos)} imagens...")
        
        for imagem in arquivos:
            self.processar_imagem(os.path.join(self.pasta_imagens, imagem))
            
        cv2.destroyAllWindows()
        
        # Relatório final
        alertas = self.db.verificar_alertas_permanencia()
        if alertas:
            print("\n=============================================")
            print("🚨 ALERTA GATILHO (Requisito 6): Permanência Excedida!")
            for a in alertas:
                print(f"Placa: {a['placa']} | Entrada: {a['entrada']} | Limite: {a['tempo_limite']} | Decorrido: {a['tempo_decorrido']}")
            print("=============================================")

if __name__ == "__main__":
    sistema = SistemaProcessamentoPlacas()
    sistema.executar_processamento()
    sistema.db.fechar()