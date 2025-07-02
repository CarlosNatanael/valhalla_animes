import smtplib
import os
from email.message import EmailMessage # Importa a classe correta para criar e-mails

# --- CONFIGURE AQUI ---
remetente = os.environ.get('EMAIL_USER')
senha = os.environ.get('EMAIL_PASS')
destinatario = 'carlosnatha2345@gmail.com' 
# --------------------

if not remetente or not senha:
    print("ERRO: As variáveis de ambiente EMAIL_USER e EMAIL_PASS não foram definidas.")
    exit()

# --- Monta a mensagem da forma profissional ---
assunto = "Teste de Conexão SMTP do Valhalla Animes"
corpo = "Se você recebeu este e-mail, a conexão SMTP e o envio de e-mail com acentuação estão funcionando perfeitamente!"

msg = EmailMessage()
msg['Subject'] = assunto
msg['From'] = remetente
msg['To'] = destinatario
msg.set_content(corpo)
# O EmailMessage automaticamente usa a codificação correta (UTF-8)

print("--- Iniciando Teste de Envio de E-mail ---")

try:
    print("Conectando ao servidor...")
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    print("Fazendo login...")
    server.login(remetente, senha)
    print("Enviando e-mail...")
    
    # Usa o método send_message, que é ideal para o objeto EmailMessage
    server.send_message(msg)
    
    print("\n[SUCESSO TOTAL] E-mail enviado! Verifique sua caixa de entrada.")

except Exception as e:
    print(f"\n[FALHA] Ocorreu um erro durante o processo:")
    print(e)

finally:
    try:
        server.quit()
        print("\nConexão com o servidor fechada.")
    except NameError:
        pass

print("--- Teste Finalizado ---")