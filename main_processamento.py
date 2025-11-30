import cv2
import easyocr
import numpy as np
import os
from database import Database

# Configurações Visuais (Cores BGR)
VERDE = (0, 255, 0)
VERMELHO = (0, 0, 255)
AMARELO = (0, 255, 255)
AZUL = (255, 0, 0)
CINZA = (150, 150, 150)

class SistemaProcessamentoPlacas:
    def __init__(self, db_name="campus.db"):
        self.db = Database(db_name)
        self.reader = easyocr.Reader(['pt'], gpu=False) # Inicializa o OCR
        self.pasta_imagens = "imagens_teste"

    def processar_imagem(self, caminho_imagem):
        """Processa uma única imagem, detecta a placa e registra o acesso."""
        
        # 1. Carrega a Imagem
        frame = cv2.imread(caminho_imagem)
        if frame is None:
            print(f"Erro: Não foi possível carregar a imagem em {caminho_imagem}")
            return
            
        print(f"\n--- Processando imagem: {os.path.basename(caminho_imagem)} ---")

        placas_detectadas = []
        
        # 2. Leitura OCR
        # Tenta ler o texto da placa na imagem. O EasyOCR também retorna a caixa delimitadora (bbox)
        resultados = self.reader.readtext(frame, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-')
        
        for (bbox, texto, prob) in resultados:
            # Limpeza da Placa e Filtro de Confiança
            if prob < 0.5: # Aumente ou diminua isso para ajustar a sensibilidade
                continue
                
            placa = texto.upper().replace("-", "").replace(" ", "").strip()
            
            # Filtro básico para placas brasileiras (3 letras + 4 números/letras)
            if len(placa) >= 7 and placa not in [info['placa'] for info in placas_detectadas]:
                
                # Coordenadas da Placa
                (top_left, top_right, bottom_right, bottom_left) = bbox
                x = int(top_left[0])
                y = int(top_left[1])
                w = int(bottom_right[0] - top_left[0])
                h = int(bottom_right[1] - top_left[1])
                
                # 3. Consulta e Lógica de Negócio
                dados_veiculo = self.db.verificar_placa(placa)
                cor = CINZA
                msg = f"N.I.: {placa}"
                
                if dados_veiculo:
                    proprietario, tipo, status, _ = dados_veiculo
                    
                    if status == 'BLOQUEADO' or status == 'OCORRENCIA':
                        # Requisito 7: Alerta de veículo não autorizado/marcado
                        cor = VERMELHO
                        msg = f"ALERTA! {status}: {placa} - {proprietario}"
                        print(f"🚨 ALERTA GATILHO (Requisito 7): Veículo {placa} (Status: {status}) acessando.")
                        
                    else:
                        # Requisito 2: Gerenciamento diferenciado
                        cor = VERDE if tipo == 'OFICIAL' else AZUL
                        tipo_acesso, horario = self.db.registrar_acesso(placa)
                        msg = f"{tipo_acesso}: {placa} ({tipo})"
                        print(f"✅ REGISTRO: {msg} em {horario.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                else:
                    # Veículo não cadastrado
                    cor = AMARELO
                    msg = f"VISITANTE: {placa}"
                    print(f"⚠️ VISITANTE: {placa} não cadastrado.")
                
                # Adiciona para o desenho
                placas_detectadas.append({
                    'coords': (x, y, w, h),
                    'texto': msg,
                    'cor': cor
                })

        # 4. Desenho (Computação Gráfica)
        self._desenhar_interface(frame, placas_detectadas)
        
        # Exibe a imagem processada até o usuário pressionar uma tecla
        cv2.imshow('Processamento de Placa', frame)
        cv2.waitKey(0) 

    def _desenhar_interface(self, frame, infos):
        """Método para desenhar caixas e textos sobre a imagem."""
        for info in infos:
            x, y, w, h = info['coords']
            texto = info['texto']
            cor = info['cor']
            
            # Desenha retângulo em volta da placa
            cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 3)
            
            # Desenha fundo para o texto
            cv2.rectangle(frame, (x, y - 35), (x + w, y), cor, -1)
            
            # Escreve o texto
            cv2.putText(frame, texto, (x + 5, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
    def executar_processamento(self):
        """Loop principal que processa todas as imagens na pasta."""
        if not os.path.exists(self.pasta_imagens):
            print(f"🚨 ERRO: Pasta '{self.pasta_imagens}' não encontrada. Crie-a e adicione as imagens.")
            return

        arquivos_imagens = [f for f in os.listdir(self.pasta_imagens) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if not arquivos_imagens:
            print("🚨 ERRO: Nenhuma imagem encontrada na pasta 'imagens_teste'.")
            return

        print(f"Iniciando o processamento de {len(arquivos_imagens)} imagens...")
        for imagem in sorted(arquivos_imagens): # Ordena para garantir sequência
            caminho_completo = os.path.join(self.pasta_imagens, imagem)
            self.processar_imagem(caminho_completo)
            
        cv2.destroyAllWindows()
        
        # 5. Verificação do Alerta de Permanência (Simulação)
        alertas_permanencia = self.db.verificar_alertas_permanencia()
        if alertas_permanencia:
            print("\n=============================================")
            print("🚨 ALERTA GATILHO (Requisito 6): Permanência Excedida!")
            for alerta in alertas_permanencia:
                print(f"Placa: {alerta['placa']} | Entrada: {alerta['entrada']} | Limite: {alerta['tempo_limite']} | Decorrido: {alerta['tempo_decorrido']}")
            print("=============================================")
        else:
            print("\nSem alertas de tempo de permanência.")


if __name__ == "__main__":
    sistema = SistemaProcessamentoPlacas()
    sistema.executar_processamento()
    sistema.db.fechar()