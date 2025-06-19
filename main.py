import logging
import sys
import os
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    sys.exit("Ошибка: переменная TELEGRAM_BOT_TOKEN не установлена.")

LATEX, FOIL_FORM, FOIL_SIZE, FOIL_PRICE, FIGURE_HEIGHT, FIGURE_WIDTH, FIGURE_PRICE, LATEX_SIZE, LATEX_PRICE = range(9)

CHANNEL = "@maxdecorkrd"

latex_sizes = {
    '5': 0.002, '10': 0.009, '12': 0.015, '14': 0.024, '18': 0.056, '24': 0.142, '36': 0.4
}

foil_coeffs = {
    ('круг', '18"'): 0.0145, ('сердце', '18"'): 0.0125, ('звезда', '18"'): 0.011,
    ('круг', '30"'): 0.0365, ('сердце', '30"'): 0.0315, ('звезда', '30"'): 0.0275,
    ('круг', '32"'): 0.041, ('сердце', '32"'): 0.036, ('звезда', '32"'): 0.031,
    ('круг', '36"'): 0.0525, ('сердце', '36"'): 0.047, ('звезда', '36"'): 0.042
}

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL, user_id=update.effective_user.id)
        return member.status not in ('left', 'kicked')
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update, context):
        await update.message.reply_text(
            "🚫 Бот доступен только для подписчиков канала компании МаксДекор @maxdecorkrd.\n"
            "Пожалуйста, подпишитесь и снова нажмите /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    reply_keyboard = [['Латексный', 'Фольгированный', 'Фигура']]
    await update.message.reply_text(
        "👋 Привет! Я бот для расчёта стоимости гелия в шарах.\n🎈 Выбери тип шара:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return LATEX

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    context.user_data.clear()
    context.user_data['type'] = text
    if text == 'латексный':
        reply_keyboard = [[size for size in latex_sizes.keys()]]
        await update.message.reply_text("📏 Выберите размер латексного шара:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
        return LATEX_SIZE
    elif text == 'фольгированный':
        await update.message.reply_text("🔶 Введите форму фольгированного шара (круг, сердце, звезда):")
        return FOIL_FORM
    elif text == 'фигура':
        await update.message.reply_text("📐 Введите высоту фигуры в см:")
        return FIGURE_HEIGHT
    else:
        await update.message.reply_text("⚠️ Неверный выбор. Попробуйте снова.")
        return LATEX

async def get_latex_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    size = update.message.text.strip()
    if size in latex_sizes:
        context.user_data['size'] = size
        await update.message.reply_text(f"✅ Размер {size} выбран.\n💵 Введите стоимость баллона гелия 5.25 м³:")
        return LATEX_PRICE
    else:
        await update.message.reply_text("⚠️ Неверный размер. Попробуйте снова.")
        return LATEX_SIZE

async def get_foil_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    form = update.message.text.strip().lower()
    if form in ['круг', 'сердце', 'звезда']:
        context.user_data['form'] = form
        await update.message.reply_text("📏 Введите размер шара (18, 30, 32, 36):")
        return FOIL_SIZE
    else:
        await update.message.reply_text("⚠️ Неверная форма. Попробуйте снова.")
        return FOIL_FORM

async def get_foil_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    size = update.message.text.strip()
    if size in ['18', '30', '32', '36']:
        context.user_data['size'] = size + '"'
        await update.message.reply_text(f"✅ Размер {size}\" выбран.\n💵 Введите стоимость гелия в баллоне 40л 5.25 м³:")
        return FOIL_PRICE
    else:
        await update.message.reply_text("⚠️ Неверный размер. Попробуйте снова.")
        return FOIL_SIZE

async def get_figure_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip())
        context.user_data['height'] = height
        await update.message.reply_text("↔️ Введите ширину фигуры в см:")
        return FIGURE_WIDTH
    except ValueError:
        await update.message.reply_text("⚠️ Введите число для высоты.")
        return FIGURE_HEIGHT

async def get_figure_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        width = float(update.message.text.strip())
        context.user_data['width'] = width
        await update.message.reply_text("💵 Введите стоимость гелия в баллоне 40л 5.25 м³:")
        return FIGURE_PRICE
    except ValueError:
        await update.message.reply_text("⚠️ Введите число для ширины.")
        return FIGURE_WIDTH

def estimate_foil_figure_volume(height_cm, width_cm):
    thickness_ratio = 0.10
    shape_coefficient = 0.68
    helium_tank_volume_m3 = 5.25

    thickness_cm = height_cm * thickness_ratio
    volume_cm3 = height_cm * width_cm * thickness_cm * shape_coefficient
    volume_liters = volume_cm3 / 1000
    volume_m3 = volume_liters / 1000
    figure_count = int(helium_tank_volume_m3 // volume_m3)

    return round(volume_liters, 2), round(volume_m3, 5), figure_count

async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        balloon_volume = 5.25
        user_data = context.user_data

        if user_data['type'] == 'латексный':
            coeff = latex_sizes[user_data['size']]
            helium_cost = price / (balloon_volume / coeff)
            count = balloon_volume / coeff
            await update.message.reply_text(f"\n💰 Стоимость гелия на 1 шар: {helium_cost:.2f} руб.\n🎈 Можно надуть {count:.0f} шаров.\n\n🔁 Чтобы начать заново, нажмите /start",
                reply_markup=ReplyKeyboardRemove())

        elif user_data['type'] == 'фольгированный':
            key = (user_data['form'], user_data['size'])
            if key in foil_coeffs:
                coeff = foil_coeffs[key]
                helium_cost = price / (balloon_volume / coeff)
                count = balloon_volume / coeff
                await update.message.reply_text(f"\n💰 Стоимость гелия на 1 шар: {helium_cost:.2f} руб.\n🎈 Можно надуть {count:.0f} шаров.\n\n🔁 Чтобы начать заново, нажмите /start",
                    reply_markup=ReplyKeyboardRemove())
            else:
                await update.message.reply_text("⚠️ Нет данных для выбранной формы и размера.")

        elif user_data['type'] == 'фигура':
            vol_liters, vol_m3, count = estimate_foil_figure_volume(user_data['height'], user_data['width'])
            helium_cost = price * (vol_m3 / balloon_volume)
            await update.message.reply_text(
                f"\n📦 Объём фигуры: {vol_liters} литров ({vol_m3} м³)\n🎈 Можно надуть {count} фигур.\n💰 Стоимость гелия на 1 фигуру: {helium_cost:.2f} руб.\n\n🔁 Чтобы начать заново, нажмите /start",
                reply_markup=ReplyKeyboardRemove())
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректное число для стоимости.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    return ConversationHandler.END

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LATEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_type)],
            FOIL_FORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_foil_form)],
            FOIL_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_foil_size)],
            FOIL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate)],
            FIGURE_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_figure_height)],
            FIGURE_WIDTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_figure_width)],
            FIGURE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate)],
            LATEX_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_latex_size)],
            LATEX_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate)],
            ConversationHandler.END: [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    app.add_handler(conv_handler)
    app.run_polling()
