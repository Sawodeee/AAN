import telebot
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
from datetime import datetime, timedelta
import threading
import telebot

bot_token = '8156879361:AAGfrtctGVVkKYjcvDWoMQYErNMpAtR3mXM'
bot = telebot.TeleBot(bot_token)
user_data = {}
allowed_users = ['7632467235']
admin_id = '7632467235'
subscription_data = {}
def load_emails(user_id):
    filename = f'emails_{user_id}.json'
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {"emails": [], "email_count": 0}

# حفظ البريد الإلكتروني في ملف خاص بكل مستخدم
def save_emails(user_id, data):
    filename = f'emails_{user_id}.json'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
btn_add_recipient = telebot.types.InlineKeyboardButton('', callback_data='add_recipient')
btn_add_sender = telebot.types.InlineKeyboardButton('⌁أضـــــف ايــــمــــيـــل⌁ ', callback_data='add_sender')
btn_set_subject_message = telebot.types.InlineKeyboardButton('⌁اضف موضوع-كليشة⌁', callback_data='set_subject_message')
btn_set_interval_message_count = telebot.types.InlineKeyboardButton('⌁ السليب - عدد الرفع ⌁', callback_data='set_interval_message_count')
btn_start_sending = telebot.types.InlineKeyboardButton('⌁ بدء الـــرفــع⌁', callback_data='start_sending')
btn_show_accounts = telebot.types.InlineKeyboardButton(' ⌁ايـمـيلاتك⌁', callback_data='show_accounts')
btn_show_all_info = telebot.types.InlineKeyboardButton('⌁ عــرض الـمـعـلـومات⌁', callback_data='show_all_info')
btn_clear_all_info = telebot.types.InlineKeyboardButton('⌁حــذف الــكــل⌁ ', callback_data='clear_all_info')
btn_delete_email = telebot.types.InlineKeyboardButton('⌁حـذف أيـمـيــل⌁', callback_data='delete_email')
btn_stop_sending = telebot.types.InlineKeyboardButton('⌁ إيقاف الإرسال⌁', callback_data='stop_sending')
btn_delete_klishes = telebot.types.InlineKeyboardButton('⌁رســت لـلــكــل⌁' , callback_data='delete_klishes')
btn_delete_Developer = telebot.types. InlineKeyboardButton("المطور", url='t.me/O707A')
btn_delete_channel = telebot.types. InlineKeyboardButton("قناة الشرح", url='https://t.me/STS90')


keyboard.add(btn_start_sending, btn_delete_klishes)
keyboard.add(btn_add_recipient, btn_add_sender)
keyboard.add(btn_set_subject_message, btn_set_interval_message_count)
keyboard.add(btn_show_all_info, btn_clear_all_info)
keyboard.add(btn_delete_email, btn_show_accounts)
keyboard.add(btn_delete_Developer,btn_delete_channel)

admin_keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
btn_add_subscriber = telebot.types.InlineKeyboardButton('⌁اضف مشترك⌁', callback_data='add_subscriber')
btn_show_subscribers = telebot.types.InlineKeyboardButton('⌁عرض المشتركين⌁', callback_data='show_subscribers')
btn_remove_subscriber = telebot.types.InlineKeyboardButton('⌁حذف مشترك⌁', callback_data='remove_subscriber')
admin_keyboard.add(btn_add_subscriber, btn_show_subscribers, btn_remove_subscriber)


duration_keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
btn_one_day = telebot.types.InlineKeyboardButton('⌁يوم⌁', callback_data='duration_1_day')
btn_one_week = telebot.types.InlineKeyboardButton('⌁اسبوع⌁', callback_data='duration_1_week')
btn_one_month = telebot.types.InlineKeyboardButton('⌁شهر⌁', callback_data='duration_1_month')
btn_one_year = telebot.types.InlineKeyboardButton('⌁سنة⌁', callback_data='duration_1_year')
duration_keyboard.add(btn_one_day, btn_one_week, btn_one_month, btn_one_year)
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id in allowed_users:
        add_user_to_data(user_id)
        bot.reply_to(message, "هلا بسالب نينو ", reply_markup=keyboard)
    else:
        bot.reply_to(message, 'أنت مامشترك! لازم تشترك بالبوت. \n للاشتراك @O707A')

@bot.message_handler(commands=['stop'])
def stop(message):
    user_id = str(message.from_user.id)
    user_info = user_data.get(user_id)
    if user_info:
        user_info['stop_sending'] = True
        bot.reply_to(message, ' تم ايقاف عملية الرفع بنجاح!')
    else:
        bot.reply_to(message, 'لم تقم ببدء عملية الرفع!')

@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    if message.from_user.id == 7632467235:  # تم تعديل هذا السطر
        bot.send_message(message.chat.id, 'اختر الأمر الذي ترغب في تنفيذه:', reply_markup=admin_keyboard)
    else:
        bot.reply_to(message, 'أنت لست مطورًا مصرحًا')




@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)
    add_user_to_data(user_id)
    user_info = user_data[user_id]

    if call.data == 'add_recipient':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="""
        قم بأرسال ايميلات الشركة بهذه الطريقة:
email@tele.com email2@tele.com""")
        bot.register_next_step_handler(call.message, add_recipient, user_id)
    elif call.data == 'add_sender':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="""
        قم بارسال ايميلات الرفع بهذه الطريقة:
email1:pass1
email2:pass2""")
        bot.register_next_step_handler(call.message, add_sender, user_id)
    elif call.data == 'set_subject_message':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=' الرجاء إرسال الموضوع الكليشة بهذه الطريقة •  الموضوع : الكليشة ')
        bot.register_next_step_handler(call.message, set_subject_message, user_id)
    elif call.data == 'set_interval_message_count':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='إرسال السليب وعدد الرفع بهذه الطريقة •  السليب : عدد الرفع')
        bot.register_next_step_handler(call.message, set_interval_message_count, user_id)
    elif call.data == 'start_sending':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='جــارٍ الــرفــع...')
        start_sending(user_id)
    elif call.data == 'show_accounts':
        show_accounts(call.message, user_id)
    elif call.data == 'show_all_info':
        show_all_info(call.message, user_id)
    elif call.data == 'clear_all_info':
        clear_all_info(call.message, user_id)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='تم مسح جميع المعلومات بنجاح!')
    elif call.data == 'delete_email':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='ارسل رقم البريد الي اتريد اتحذفة؟')
        bot.register_next_step_handler(call.message, delete_email, user_id)
    elif call.data == 'stop_sending':
        stop_sending(call.message)
    elif call.data == 'add_subscriber':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='الرجاء إرسال ID الشخص الذي تريد اضافته لقائمة المشتركين')
        bot.register_next_step_handler(call.message, add_subscriber)
    elif call.data == 'show_subscribers':
        show_subscribers(call.message)
    elif call.data == 'remove_subscriber':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='الرجاء إرسال ID الشخص الذي تريد حذفه من قائمة المشتركين')
        bot.register_next_step_handler(call.message, remove_subscriber)
    elif call.data.startswith('duration_'):
        handle_subscription_duration(call, user_id, call.data)
    elif call.data == 'add_more_subject_message':
        bot.send_message(user_id, 'الرجاء إرسال الموضوع والكليشة بالطريقة التالية • الموضوع : الكليشة')
        bot.register_next_step_handler(call.message, set_subject_message, user_id)
    elif call.data == 'finish_subject_message':
        bot.send_message(user_id, 'تم تعيين الموضوع والكليشة .')
        show_all_info(call.message, user_id)
    elif call.data == 'delete_klishes':
        delete_klishes(call.message, user_id)



def add_user_to_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'email_senders': [],
            'email_passwords': [],
            'recipients': [],
            'email_subjects': [],
            'email_messages': [],
            'interval_seconds': 0,
            'message_count': 0,
            'current_subject': '',
            'current_message': ''
        }


def add_recipient(message, user_id):
    recipients = message.text.split()
    if recipients:
        user_data[user_id]['recipients'].clear()  
        user_data[user_id]['recipients'].extend(recipients)
        bot.reply_to(message, 'تمت إضافة الحسابات المستلمة بنجاح!')
    else:
        bot.reply_to(message, 'خطأ في إضافة الحسابات المستلمة. الرجاء المحاولة مرة أخرى.')

def add_sender(message, user_id):
    email_password_pairs = message.text.split('\n')  
    success_count = 0
    failure_count = 0
    
    for pair in email_password_pairs:
        sender_email_password = pair.split(':')
        if len(sender_email_password) == 2:
            sender_email = sender_email_password[0].strip()
            sender_password = sender_email_password[1].strip()
            if sender_email and sender_password:
                user_data[user_id]['email_senders'].append(sender_email)
                user_data[user_id]['email_passwords'].append(sender_password)
                success_count += 1
            else:
                failure_count += 1
        else:
            failure_count += 1
    
    if success_count > 0:
        bot.reply_to(message, f'تمت إضافة {success_count} حساب مرسل بنجاح!')
    if failure_count > 0:
        bot.reply_to(message, f'حدث خطأ في إضافة {failure_count} حساب مرسل. الرجاء التحقق من الصيغة الصحيحة (Email:pass).')

def set_subject_message(message, user_id):
    try:
        subject, email_message = message.text.split(':', 1)
        user_data[user_id]['current_subject'] = subject.strip()
        user_data[user_id]['current_message'] = email_message.strip()
        
        bot.reply_to(message, """ارسل ايميل الدعم
 abuse@telegram.org
او
stopCA@telegram.org
او
recover@telegram.org
او
dmca@telegram.org""")
        bot.register_next_step_handler(message, set_recipient_email, user_id)
    except ValueError:
        bot.reply_to(message, 'خطأ في الصيغة. الرجاء إرسال الموضوع والكليشة بهذه الطريقة: الموضوع:الكليشة')

def set_recipient_email(message, user_id):
    if len(user_data[user_id]['email_subjects']) >= 5:
        bot.reply_to(message, 'لا يمكن إضافة أكثر من 5 مواضيع والكليشة.')
        return
    
    recipient_email = message.text.strip()
    user_data[user_id]['email_subjects'].append(user_data[user_id]['current_subject'])
    user_data[user_id]['email_messages'].append(user_data[user_id]['current_message'])
    user_data[user_id]['recipients'].append(recipient_email)
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    yes_button = types.InlineKeyboardButton(text="نعم", callback_data='add_more_subject_message')
    no_button = types.InlineKeyboardButton(text="لا", callback_data='finish_subject_message')
    keyboard.add(yes_button, no_button)
    
    bot.reply_to(message, """تم تعين الموضوع والكليشة وايميل الدعم!
    
الان اختار الامر لا""", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'add_more_subject_message')
def add_more_subject_message(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    if len(user_data[user_id]['email_subjects']) >= 5:
        bot.send_message(user_id, 'لا يمكن إضافة أكثر من 5 مواضيع والكليشة.')
    else:
        bot.send_message(user_id, 'ارسل الموضوع والكيشة على هاذه الصيغة الموضوع:الكليشة')

@bot.callback_query_handler(func=lambda call: call.data == 'finish_subject_message')
def finish_subject_message(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id, "تم إنهاء تعيين المواضيع والكليشة.")
    show_all_info(call.message, user_id)

def set_interval_message_count(message, user_id):
    try:
        interval_seconds, message_count = message.text.split(':', 1)
        user_data[user_id]['interval_seconds'] = int(interval_seconds)
        user_data[user_id]['message_count'] = int(message_count)
        bot.reply_to(message, 'تم تعيين السليب وعدد الرفع بنجاح!')
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except ValueError:
        bot.reply_to(message, 'خطأ في الصيغة. الرجاء إرسال السليب وعدد الرفع بهذه الطريقة: السليب:عدد الرفع')


def delete_email(message, user_id):
    try:
        index = int(message.text) - 1
        if index >= 0 and index < len(user_data[user_id]['email_senders']):
            del user_data[user_id]['email_senders'][index]
            del user_data[user_id]['email_passwords'][index]
            bot.reply_to(message, 'تم حذف البريد الإلكتروني بنجاح!')
        else:
            bot.reply_to(message, 'خطأ في حذف البريد الإلكتروني. الرجاء المحاولة مرة أخرى.')
    except ValueError:
        bot.reply_to(message, 'خطأ في التحويل إلى رقم. يرجى إدخال رقم صحيح لحذف البريد الإلكتروني.')


import time
import threading
from telebot import types, TeleBot
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from telebot.apihelper import ApiTelegramException
from ratelimit import limits, sleep_and_retry

ONE_MINUTE = 60


@sleep_and_retry
@limits(calls=60, period=ONE_MINUTE)
def send_limited_message(*args, **kwargs):
    return bot.send_message(*args, **kwargs)

@sleep_and_retry
@limits(calls=60, period=ONE_MINUTE)
def edit_limited_message_text(*args, **kwargs):
    return bot.edit_message_text(*args, **kwargs)

def send_email(sender_email, sender_password, recipient, subject, message):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['BCC'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    msg.add_header('User-Agent', 'iPhone Mail (14F5089a)')

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email from {sender_email} to {recipient}: {str(e)}")
        return False

def send_emails(user_id, user_info):
    success_count = 0
    error_count = 0
    prev_message_id = None
    blocked_senders = set()
    messages_sent = 0

    total_messages = user_info['message_count']
    klishes_subjects = list(zip(user_info['email_subjects'], user_info['email_messages'], user_info['recipients']))

    klisha_sent_counts = {index: 0 for index in range(len(klishes_subjects))}

    initial_message = ("""بدأت عميلة الرفع بشكل عمودي!
    
    
  للايقاف ارسل /stop""")
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    stop_button = types.InlineKeyboardButton(text="", callback_data='stop_sending')
    keyboard.add(stop_button)
    
    sent_message = send_limited_message(user_id, initial_message, reply_markup=keyboard)
    prev_message_id = sent_message.message_id

    while messages_sent < total_messages:
        if len(blocked_senders) == len(user_info['email_senders']):
            final_message = (f"تم الانتهاء.\n"
                             f"تم الرفع: {success_count}\n"
                             f"فشل اثناء: {error_count}\n"
                             "جميع حسابات الرفع محظورة.")
            edit_limited_message_text(chat_id=user_id, message_id=prev_message_id, text=final_message)
            return

        for sender, password in zip(user_info['email_senders'], user_info['email_passwords']):
            if sender in blocked_senders:
                continue

            try:
                if user_info.get('stop_sending'):
                    del user_info['stop_sending']
                    final_message = (f"تم إيقاف عملية الرفع.\n"
                                     f"تم الرفع: {success_count}\n"
                                     f"فشل أثناء: {error_count}\n")
                    send_limited_message(user_id, final_message)
                    return

                subject_index = messages_sent % len(klishes_subjects)
                subject, message, recipient_email = klishes_subjects[subject_index]
                
                if send_email(sender, password, recipient_email, subject, message):
                    success_count += 1
                    messages_sent += 1
                    klisha_sent_counts[subject_index] += 1  
                else:
                    error_count += 1
                    blocked_senders.add(sender)
                    send_limited_message(user_id, f'الإيميل {sender} محظور، تم التوقف عن استخدامه.')

                if messages_sent >= total_messages:
                    break

            except Exception as e:
                error_count += 1
                blocked_senders.add(sender)
                send_limited_message(user_id, f'الإيميل {sender} محظور بسبب خطأ: {str(e)}, تم التوقف عن استخدامه.')

            remaining_messages = total_messages - messages_sent
            
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            sent_button = types.InlineKeyboardButton(text=f"تم الرفع: {success_count}", callback_data='noop')
            error_button = types.InlineKeyboardButton(text=f"فشل اثناء: {error_count}", callback_data='noop')
            remaining_button = types.InlineKeyboardButton(text=f"المتبقي: {remaining_messages}", callback_data='noop')
            stop_button = types.InlineKeyboardButton(text="", callback_data='stop_sending')
            keyboard.add(sent_button, error_button, remaining_button, stop_button)

            for index, count in klisha_sent_counts.items():
                klishe_button = types.InlineKeyboardButton(text=f"الكليشة {index + 1}: {count}", callback_data='noop')
                keyboard.add(klishe_button)

            status_message = ("سوف تكتمل العملية الرفع قريبا!\n"
                              "ارسل /stop للايقاف")
            try:
                edit_limited_message_text(chat_id=user_id, message_id=prev_message_id, text=status_message, reply_markup=keyboard)
            except ApiTelegramException as e:
                if e.result.status_code == 429:
                    retry_after = int(e.result.json()['parameters']['retry_after'])
                    time.sleep(retry_after)
                    edit_limited_message_text(chat_id=user_id, message_id=prev_message_id, text=status_message, reply_markup=keyboard)

        time.sleep(user_info['interval_seconds'])

    final_message = (f"تم الانتهاء.\n"
                     f"تم الرفع: {success_count}\n"
                     f"فشل اثناء: {error_count}\n")
    edit_limited_message_text(chat_id=user_id, message_id=prev_message_id, text=final_message)

@bot.callback_query_handler(func=lambda call: call.data == 'stop_sending')
def stop_sending_callback(call):
    user_id = call.message.chat.id
    user_data[user_id]['stop_sending'] = True
    bot.answer_callback_query(call.id, "تم إيقاف عملية الرفع.")

def start_sending(user_id):
    user_info = user_data[user_id]
    if len(user_info['recipients']) == 0:
        send_limited_message(user_id, 'لا يوجد حسابات مستلمة. الرجاء إضافة حساب مستلم أولاً.')
        return

    if len(user_info['email_senders']) == 0:
        send_limited_message(user_id, 'لا يوجد حسابات مرسلة. الرجاء إضافة حساب مرسل أولاً.')
        return

    if len(user_info['email_subjects']) == 0 or len(user_info['email_messages']) == 0:
        send_limited_message(user_id, 'لم يتم تعيين المواضيع أو الكليشة. الرجاء تعيين المواضيع والكليشة أولاً.')
        return

    if user_info['message_count'] == 0:
        send_limited_message(user_id, 'لم يتم تعيين عدد الرفع. الرجاء تعيين عدد الرفع أولاً.')
        return

    sending_thread = threading.Thread(target=send_emails, args=(user_id, user_info))
    sending_thread.start()



MAX_MESSAGE_LENGTH = 4096  

def show_accounts(message, user_id):
    user_info = user_data[user_id]
    if len(user_info['email_senders']) == 0:
        bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text='لم يتم إضافة أي حسابات مرسلة حتى الآن.')
    else:
        accounts = []
        for i, sender in enumerate(user_info['email_senders']):
            accounts.append(f'حساب رقم {i + 1}: {sender}')
        

        full_message = '\n'.join(accounts)
       
        if len(full_message) > MAX_MESSAGE_LENGTH:
            chunks = [full_message[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(full_message), MAX_MESSAGE_LENGTH)]
            for chunk in chunks:
                bot.send_message(chat_id=message.chat.id, text=chunk)
        else:
            bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=full_message)



def show_all_info(message, user_id):
    user_info = user_data[user_id]
    info_message = f"إيميلات الدعم:\n"
    for i, recipient in enumerate(user_info['recipients']):
        info_message += f"ايميل دعم الكليشة {i + 1}: {recipient}\n"
    info_message += f"\nالموضوعات والكليشة:\n\n"
    for i, (subject, msg) in enumerate(zip(user_info['email_subjects'], user_info['email_messages'])):
        info_message += f"الموضوع {i + 1}: {subject}\nالكليشة {i + 1}: {msg}\n\n"
    info_message += f"السليب: {user_info['interval_seconds']} ثانية\n\n"
    info_message += f"عدد الرفع: {user_info['message_count']}\n"
    
    if len(info_message) > 4096:
        parts = [info_message[i:i+4096] for i in range(0, len(info_message), 4096)]
        for part in parts:
            bot.send_message(message.chat.id, part)
    else:
        bot.send_message(message.chat.id, info_message)


def clear_all_info(message, user_id):
    user_data[user_id] = {
        'email_senders': [],
        'email_passwords': [],
        'recipients': [],
        'email_subjects': [],
        'email_messages': [],
        'interval_seconds': 0,
        'message_count': 0,
        'current_subject': '',
        'current_message': ''
    }
    
def delete_klishes(message, user_id):
    user_data[user_id]['email_subjects'].clear()
    user_data[user_id]['email_messages'].clear()
    user_data[user_id]['recipients'].clear()
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text='تم حذف جميع الكليشات والمواضيع وإيميلات المستلمين بنجاح!')

def add_subscriber(message):
    new_user_id = message.text
    bot.reply_to(message, 'اختار مدة الاشتراك', reply_markup=duration_keyboard)
    subscription_data['temp_user_id'] = new_user_id


def handle_subscription_duration(call, admin_id, duration):
    temp_user_id = subscription_data.get('temp_user_id')
    if not temp_user_id:
        bot.send_message(admin_id, 'لم يتم العثور على المستخدم. الرجاء المحاولة مرة أخرى.')
        return

    duration_map = {
        'duration_1_day': timedelta(days=1),
        'duration_1_week': timedelta(weeks=1),
        'duration_1_month': timedelta(days=30),
        'duration_1_year': timedelta(days=365)
    }
    duration_timedelta = duration_map.get(duration)
    if not duration_timedelta:
        bot.send_message(admin_id, 'مدة اشتراك غير صالحة. الرجاء المحاولة مرة أخرى.')
        return

    expiration_date = datetime.now() + duration_timedelta
    allowed_users.append(temp_user_id)
    subscription_data[temp_user_id] = expiration_date
    bot.send_message(admin_id, f'تم إضافة المستخدم {temp_user_id} بنجاح لمدة {duration_timedelta.days} يوم.')


    Thread(target=remove_user_after_duration, args=(temp_user_id, duration_timedelta)).start()


def remove_user_after_duration(user_id, duration):
    time.sleep(duration.total_seconds())
    if user_id in allowed_users:
        allowed_users.remove(user_id)
        del subscription_data[user_id]
        bot.send_message(admin_id, f'تمت إزالة المستخدم {user_id} بعد انتهاء مدة الاشتراك.')


def show_subscribers(message):
    if not subscription_data:
        bot.reply_to(message, 'لا يوجد مشتركون حاليًا.')
        return

    subscribers_info = []
    for user_id, expiration_date in subscription_data.items():
        subscribers_info.append(f'ID: {user_id}, مدة الاشتراك: {expiration_date}')

    bot.reply_to(message, '\n'.join(subscribers_info))


def remove_subscriber(message):
    user_id = message.text
    if user_id in allowed_users:
        allowed_users.remove(user_id)
        del subscription_data[user_id]
        bot.reply_to(message, f'تم حذف المستخدم {user_id} بنجاح.')
    else:
        bot.reply_to(message, 'المستخدم غير موجود في قائمة المشتركين.')


bot.polling()