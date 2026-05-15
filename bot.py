import sqlite3
import re
import easyocr
import io
import ssl
import os
from dotenv import load_dotenv # Instale com: pip install python-dotenv
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Carrega as variáveis do arquivo .env
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Ignora erro de certificado da rede corporativa
ssl._create_default_https_context = ssl._create_unverified_context

# Inicializa o leitor
reader = easyocr.Reader(['pt', 'en'])

# --- BANCO DE DADOS ---
def iniciar_db():
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        user_id INTEGER PRIMARY KEY, 
                        despesas REAL DEFAULT 0, 
                        lazer REAL DEFAULT 0)''')
    conn.commit()
    conn.close()

def atualizar_saldos(user_id, n_desp, n_laz):
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO usuarios (user_id, despesas, lazer) VALUES (?,?,?) 
                      ON CONFLICT(user_id) DO UPDATE SET 
                      despesas=despesas+excluded.despesas, 
                      lazer=lazer+excluded.lazer''', (user_id, n_desp, n_laz))
    conn.commit()
    conn.close()

def obter_saldos(user_id):
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    cursor.execute('SELECT despesas, lazer FROM usuarios WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res if res else (0, 0)

# --- COMANDOS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    await update.message.reply_text(
        f"Olá, {nome}! Bem-vindo ao Bot de Finanças 🚀\n\n"
        "Como usar:\n"
        "1. Mande um valor (ex: 5000) para registrar entrada (70/30).\n"
        "2. Mande 'paguei 50 curso' para subtrair das contas.\n"
        "3. Mande uma FOTO do comprovante e eu leio o valor!\n"
        "4. Use /saldo para ver sua situação atual."
    )

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s_c, s_l = obter_saldos(user_id)
    await update.message.reply_text(
        f"💰 **SEU SALDO ATUAL:**\n"
        f"-------------------\n"
        f"🏠 Contas Fixas: R$ {s_c:.2f}\n"
        f"🍕 Lazer/Variável: R$ {s_l:.2f}"
    )

import pytesseract  # Troque o import do easyocr por este
from PIL import Image
import io

# No início do código, você não precisa mais da linha "reader = easyocr.Reader..."

async def processar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_espera = await update.message.reply_text("Processando (Modo Econômico) 🍃")
    
    try:
        foto_arquivo = await update.message.photo[-1].get_file()
        foto_bytes = await foto_arquivo.download_as_bytearray()
        
        # Abre a imagem
        img = Image.open(io.BytesIO(foto_bytes))
        
        # REDUÇÃO AGRESSIVA: 
        # 1. Diminui o tamanho
        img.thumbnail((600, 600)) 
        # 2. Converte para 1-bit (Preto e Branco total) para gastar quase zero de RAM
        img = img.convert('1') 
        
        # O Tesseract lê muito mais rápido assim
        texto_extraido = pytesseract.image_to_string(img, lang='por').upper()
        
        # Sua lógica de busca de valor (re.findall...) continua aqui embaixo igualzinha
        # ... (copie o restante da sua lógica de regex e atualização de saldo aqui)
        
    except Exception as e:
        print(f"Erro de memória evitado: {e}")

async def processar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.lower()
    numeros = re.findall(r"[-+]?\d*\,\d+|\d+", texto.replace(',', '.'))
    if not numeros: return
    
    valor = float(numeros[0])
    if any(p in texto for p in ['paguei', 'gastei', 'curso', 'aluguel', 'conta', 'net']):
        atualizar_saldos(user_id, -valor, 0)
        msg = f"📉 Gasto: R$ {valor:.2f}"
    elif valor > 0:
        v_c, v_l = valor * 0.7, valor * 0.3
        atualizar_saldos(user_id, v_c, v_l)
        msg = f"✅ Recebido: R$ {valor:.2f}"
    
    s_c, s_l = obter_saldos(user_id)
    await update.message.reply_text(f"{msg}\n\n🏠 Contas: R$ {s_c:.2f}\n🍕 Lazer: R$ {s_l:.2f}")

if __name__ == '__main__':
    iniciar_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_texto))
    app.add_handler(MessageHandler(filters.PHOTO, processar_foto))
    print("Bot pronto para produção! 🚀")
    app.run_polling()