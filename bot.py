import sqlite3
import re
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Carrega as variáveis do arquivo .env
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

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
        f"Olá, {nome}! Seu controle financeiro está ATIVO 🚀\n\n"
        "**Como registrar:**\n"
        "💰 **Entrada:** Digite apenas o valor (ex: 5000)\n"
        "💸 **Gasto:** Digite 'paguei' ou 'gastei' + valor (ex: paguei 35.50)\n"
        "📊 **Saldo:** Use /saldo"
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

async def processar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.lower()
    
    # Extrai números (trata vírgula como ponto)
    numeros = re.findall(r"\d+[\.,]?\d*", texto.replace(',', '.'))
    if not numeros: 
        return

    valor = float(numeros[0])
    
    # Palavras que indicam gasto
    palavras_gasto = ['paguei', 'gastei', 'curso', 'aluguel', 'conta', 'net', 'ifood', 'uber', 'restaurante']
    
    if any(p in texto for p in palavras_gasto):
        # Se for gasto, subtrai apenas de Contas Fixas (ou mude a lógica se preferir)
        atualizar_saldos(user_id, -valor, 0)
        msg = f"📉 Gasto de R$ {valor:.2f} registrado em Contas."
    else:
        # Se mandar só o número, entende como entrada (70/30)
        v_c, v_l = valor * 0.7, valor * 0.3
        atualizar_saldos(user_id, v_c, v_l)
        msg = f"✅ Recebido: R$ {valor:.2f}\n(🏠 R$ {v_c:.2f} | 🍕 R$ {v_l:.2f})"
    
    s_c, s_l = obter_saldos(user_id)
    await update.message.reply_text(f"{msg}\n\n🏠 Total Contas: R$ {s_c:.2f}\n🍕 Total Lazer: R$ {s_l:.2f}")

if __name__ == '__main__':
    iniciar_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    
    # Processa qualquer texto que não seja comando
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_texto))
    
    print("Bot leve rodando! 🚀")
    app.run_polling()