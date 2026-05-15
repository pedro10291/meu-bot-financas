import sqlite3
import re
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

# --- BANCO DE DADOS (Mesma lógica) ---
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

# --- PROCESSAMENTO DE TEXTO ---

async def processar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text
    numeros = re.findall(r"\d+[\.,]?\d*", texto.replace(',', '.'))
    
    if not numeros: return
    valor = float(numeros[0])

    # Se você digitar APENAS o número, ele pergunta o que é
    keyboard = [
        [
            InlineKeyboardButton("🏠 Conta Fixa", callback_data=f"fixo_{valor}"),
            InlineKeyboardButton("🍕 Lazer", callback_data=f"lazer_{valor}"),
        ],
        [InlineKeyboardButton("💰 Entrada (70/30)", callback_data=f"ganho_{valor}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(f"O valor R$ {valor:.2f} é:", reply_markup=reply_markup)

# --- LÓGICA DOS BOTÕES ---

async def tratar_botao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_') # Divide o comando do valor
    
    tipo = data[0]
    valor = float(data[1])
    
    await query.answer() # Tira o reloginho do botão

    if tipo == "fixo":
        atualizar_saldos(user_id, -valor, 0)
        msg = f"🏠 Gastou R$ {valor:.2f} em Contas Fixas."
    elif tipo == "lazer":
        atualizar_saldos(user_id, 0, -valor)
        msg = f"🍕 Gastou R$ {valor:.2f} em Lazer."
    elif tipo == "ganho":
        v_c, v_l = valor * 0.7, valor * 0.3
        atualizar_saldos(user_id, v_c, v_l)
        msg = f"✅ Recebido R$ {valor:.2f} (70/30 aplicado)."

    s_c, s_l = obter_saldos(user_id)
    await query.edit_message_text(f"{msg}\n\n📊 **SALDOS:**\n🏠 Contas: R$ {s_c:.2f}\n🍕 Lazer: R$ {s_l:.2f}")

# --- COMANDOS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mande um valor e eu te darei as opções! 💸")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s_c, s_l = obter_saldos(user_id)
    await update.message.reply_text(f"💰 **SALDO ATUAL:**\n\n🏠 Contas: R$ {s_c:.2f}\n🍕 Lazer: R$ {s_l:.2f}")

if __name__ == '__main__':
    iniciar_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_texto))
    # Handler específico para os botões
    app.add_handler(CallbackQueryHandler(tratar_botao))
    
    print("Bot com botões rodando! 🚀")
    app.run_polling()