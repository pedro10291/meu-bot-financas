import sqlite3
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

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
    cursor.execute('''CREATE TABLE IF NOT EXISTS transacoes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        tipo TEXT,
                        valor REAL,
                        descricao TEXT,
                        data TEXT)''')
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

def registrar_transacao(user_id, tipo, valor, descricao):
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    data_hoje = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO transacoes (user_id, tipo, valor, descricao, data) VALUES (?, ?, ?, ?, ?)',
                   (user_id, tipo, valor, descricao, data_hoje))
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
    await update.message.reply_text("🚀 **Controle Financeiro Ativo!**\n\nMande um valor e uma descrição (ex: 50 lanche) e escolha a categoria nos botões.")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s_c, s_l = obter_saldos(user_id)
    await update.message.reply_text(f"💰 **SALDO ATUAL:**\n\n🏠 Contas: R$ {s_c:.2f}\n🍕 Lazer: R$ {s_l:.2f}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuarios WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM transacoes WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🔄 **Banco de dados resetado com sucesso!**")

async def extrato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    mes_atual = datetime.now().strftime('%Y-%m')
    cursor.execute('SELECT data, tipo, valor, descricao FROM transacoes WHERE user_id = ? AND data LIKE ? ORDER BY data DESC LIMIT 10', (user_id, f'{mes_atual}%'))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Nenhum registro este mês.")
        return
    res = "📑 **EXTRATO MENSAL:**\n\n"
    for r in rows:
        emoji = "🏠" if r[1] == "fix" else ("🍕" if r[1] == "laz" else "✅")
        res += f"{r[0][8:10]}/{r[0][5:7]} | {emoji} R$ {r[2]:.2f} - {r[3]}\n"
    await update.message.reply_text(res)

# --- INTERAÇÃO ---

async def processar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    numeros = re.findall(r"\d+[\.,]?\d*", texto.replace(',', '.'))
    if not numeros: return
    
    valor = float(numeros[0])
    # Tenta isolar a descrição
    desc = texto.replace(str(numeros[0]).replace('.', ','), "").replace(str(numeros[0]), "").strip() or "Gasto"
    desc_c = desc[:15] # Limite para o botão

    keyboard = [
        [
            InlineKeyboardButton("🏠 Conta Fixa", callback_data=f"fix_{valor}_{desc_c}"),
            InlineKeyboardButton("🍕 Lazer", callback_data=f"laz_{valor}_{desc_c}")
        ],
        [InlineKeyboardButton("💰 Ganho (70/30)", callback_data=f"gan_{valor}_{desc_c}")]
    ]
    await update.message.reply_text(f"Registrar R$ {valor:.2f} ({desc}) como:", reply_markup=InlineKeyboardMarkup(keyboard))

async def tratar_botao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_')
    tipo, valor, desc = data[0], float(data[1]), data[2]
    
    await query.answer()

    if tipo == "fix":
        atualizar_saldos(user_id, -valor, 0)
        registrar_transacao(user_id, "fix", valor, desc)
        txt = f"🏠 **{desc.upper()}**: -R$ {valor:.2f}"
    elif tipo == "laz":
        atualizar_saldos(user_id, 0, -valor)
        registrar_transacao(user_id, "laz", valor, desc)
        txt = f"🍕 **{desc.upper()}**: -R$ {valor:.2f}"
    else:
        v_c, v_l = valor * 0.7, valor * 0.3
        atualizar_saldos(user_id, v_c, v_l)
        registrar_transacao(user_id, "gan", valor, desc)
        txt = f"✅ **{desc.upper()}**: +R$ {valor:.2f} (Dividido)"

    s_c, s_l = obter_saldos(user_id)
    await query.edit_message_text(f"{txt}\n\n📊 **SALDOS:**\n🏠 Contas: R$ {s_c:.2f}\n🍕 Lazer: R$ {s_l:.2f}")

if __name__ == '__main__':
    iniciar_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("extrato", extrato))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_texto))
    app.add_handler(CallbackQueryHandler(tratar_botao))
    
    print("Bot atualizado rodando! 🚀")
    app.run_polling()