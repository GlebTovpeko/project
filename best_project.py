
import telebot
from telebot import types
from datetime import datetime, timedelta
import time
import threading
import re
import json
import os

# Базовый класс для команд.  Обрабатывает общие действия для всех команд бота.
class BotCommand:
    def __init__(self, bot):
        # Инициализация объекта класса, принимает объект бота в качестве аргумента.
        self.bot = bot

# Команды
# Класс для обработки команды /start.  Отображает приветственное сообщение и меню команд.
class StartCommand(BotCommand):
    def execute(self, message):
        # Метод выполняет команду /start.
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Добавить привычку', 'Добавить нотификатор', 'Добавить задание', 'Просмотреть задания', 'Просмотреть привычки', 'Команды')
        self.bot.bot.send_message(message.chat.id, "Привет! Я помощник по формированию привычек и задач. Выберите действие:", reply_markup=markup)


# Класс для добавления новой привычки.
class AddHabitCommand(BotCommand):
    def execute(self, message):
        # Метод запрашивает у пользователя ввод новой привычки.
        self.bot.bot.send_message(message.chat.id, "Введите новую привычку:")
        self.bot.bot.register_next_step_handler(message, self.save_habit)

    def save_habit(self, message):
        # Метод сохраняет введенную привычку в данные пользователя.
        habit = message.text
        user_id = message.chat.id
        self.bot.load_user_data(user_id)
        self.bot.user_data[user_id]['habits'].append(habit)
        self.bot.save_user_data(user_id)
        self.bot.bot.send_message(message.chat.id, f"Привычка '{habit}' добавлена!")


# Класс для добавления нотификатора к привычке.
class AddNotificationCommand(BotCommand):
    def execute(self, message):
        # Метод запрашивает у пользователя время и номер привычки для нотификатора.
        self.bot.load_user_data(message.chat.id)
        habits = self.bot.user_data.get(message.chat.id, {}).get('habits', [])
        if not habits:
            self.bot.bot.send_message(message.chat.id, "Сначала добавьте привычки!")
            return

        habit_list = "\n".join([f"{i+1}. {habit}" for i, habit in enumerate(habits)])
        self.bot.bot.send_message(message.chat.id, f"Выберите привычку для добавления нотификатора:\n{habit_list}\n\nВведите время (в формате ЧЧ:ММ) и номер привычки (нотификатор будет работать по Московскому времени):")
        self.bot.bot.register_next_step_handler(message, self.save_notification)

    def save_notification(self, message):
        # Метод сохраняет нотификатор для указанной привычки.
        user_id = message.chat.id
        text = message.text.split()
        if len(text) < 2 or not re.match(r'^\d{2}:\d{2}$', text[0]) or not text[1].isdigit():
            self.bot.bot.send_message(user_id, "Неверный формат. Используйте:  'ЧЧ:ММ <номер привычки>'")
            self.bot.bot.register_next_step_handler(message, self.save_notification)
            return

        time_str = text[0]
        try:
            habit_index = int(text[1]) - 1
        except ValueError:
            self.bot.bot.send_message(user_id, "Неверный номер привычки.")
            self.bot.bot.register_next_step_handler(message, self.save_notification)
            return

        try:
            time_obj = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            self.bot.bot.send_message(user_id, "Неверный формат времени. Используйте формат ЧЧ:ММ (от 00:00 до 23:59)")
            self.bot.bot.register_next_step_handler(message, self.save_notification)
            return


        self.bot.load_user_data(user_id)
        habits = self.bot.user_data[user_id]['habits']
        if not (0 <= habit_index < len(habits)):
            self.bot.bot.send_message(user_id, "Неверный номер привычки.")
            self.bot.bot.register_next_step_handler(message, self.save_notification)
            return

        habit = habits[habit_index]

        user_data = self.bot.user_data.setdefault(user_id, {'habits': [], 'notifications': {}})
        notifications = user_data['notifications']
        notifications.setdefault(user_id, []).append({'time': time_str, 'habit': habit})
        self.bot.save_user_data(user_id)
        self.bot.bot.send_message(user_id, f"Нотификатор для '{habit}' установлен на {time_str}!")


# Класс для добавления нового задания на день.
class AddTaskCommand(BotCommand):
    def execute(self, message):
        # Метод запрашивает у пользователя ввод нового задания.
        self.bot.bot.send_message(message.chat.id, "Введите задание:")
        self.bot.bot.register_next_step_handler(message, self.save_task)

    def save_task(self, message):
        # Метод сохраняет введенное задание в данные пользователя.
        task = message.text
        self.bot.load_user_data(message.chat.id)
        self.bot.user_data[message.chat.id]['daily_tasks'].append(task)
        self.bot.save_user_data(message.chat.id)
        self.bot.bot.send_message(message.chat.id, f"Задание '{task}' добавлено в список дел на сегодня!")


# Класс для отображения списка заданий на день.
class ViewTasksCommand(BotCommand):
    def execute(self, message):
        # Метод отображает список заданий на день.
        self.bot.load_user_data(message.chat.id)
        tasks = self.bot.user_data.get(message.chat.id, {}).get('daily_tasks', [])
        response = "Ваш список дел на сегодня:\n" + "\n".join(tasks) if tasks else "У вас нет заданий на сегодня."
        self.bot.bot.send_message(message.chat.id, response)


# Класс для отображения списка привычек.
class ViewHabitsNotificationsCommand(BotCommand):
    def execute(self, message):
        # Метод отображает список привычек пользователя.
        user_id = message.chat.id
        self.bot.load_user_data(user_id)
        habits = self.bot.user_data.get(user_id, {}).get('habits', [])

        response = "Ваши привычки:\n"
        if habits:
            for habit in habits:
                response += f"\nПривычка: {habit}\n"
        else:
            response += "У вас нет привычек."
        self.bot.bot.send_message(user_id, response)


# Класс для отображения списка доступных команд.
class CommandsCommand(BotCommand):
    def execute(self, message):
        # Метод отображает список доступных команд и их описание.
        self.bot.bot.send_message(message.chat.id, "Доступные команды и их функционал:\n1. 'Добавить привычку' - добавляет долгосрочную привычку.\n2. 'Добавить нотификатор' - добавляет напоминание о привычке.\n3. 'Добавить задание' - добавляет задачу в список дел на сегодня.\n4. 'Просмотреть задания' - показывает список дел на сегодня.\n5. 'Просмотреть привычки' - показывает список привычек.")


# Класс для обработки неизвестных команд.
class UnknownCommand(BotCommand):
    def execute(self, message):
        # Метод обрабатывает ввод неизвестной команды.
        self.bot.bot.send_message(message.chat.id, "Ошибка! Попробуйте ввести одну из поддерживаемых команд.")



# Класс основного бота.  Управляет всеми функциями бота, включая обработку сообщений, уведомлений и сохранение данных.
class HabitBot:
    def __init__(self, token):
        # Инициализация объекта бота, принимает токен в качестве аргумента.
        self.bot = telebot.TeleBot(token)
        self.data_dir = "user_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.user_data = {}
        self.load_all_user_data()

        self.commands = {
            '/start': StartCommand(self),
            'Добавить привычку': AddHabitCommand(self),
            'Добавить нотификатор': AddNotificationCommand(self),
            'Добавить задание': AddTaskCommand(self),
            'Просмотреть задания': ViewTasksCommand(self),
            'Просмотреть привычки': ViewHabitsNotificationsCommand(self),
            'Команды': CommandsCommand(self),
        }
        self.default_command = UnknownCommand(self)

    def handle_message(self, message):
        # Метод обрабатывает входящие сообщения от пользователя.
        user_id = message.chat.id
        self.load_user_data(user_id)
        command = self.commands.get(message.text, self.default_command)
        command.execute(message)

    def notify_users(self):
        # Метод отправляет уведомления пользователям в заданное время.
        while True:
            now = datetime.now().strftime("%H:%M")
            for user_id, data in self.user_data.items():
                for notification in data.get('notifications', {}).get(user_id, []):
                    if notification['time'] == now:
                        self.bot.send_message(user_id, f"Время для привычки: {notification['habit']}")
            time.sleep(60)

    def clear_daily_tasks(self):
        # Метод очищает список ежедневных задач в полночь.
        while True:
            now = datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_to_midnight = (midnight - now).seconds
            time.sleep(time_to_midnight)
            for user_id in self.user_data:
                self.user_data[user_id]['daily_tasks'].clear()
            self.save_all_user_data()
            print("Ежедневные задачи очищены!")

    def load_all_user_data(self):
        # Метод загружает данные всех пользователей из файлов.
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".json"):
                user_id = int(filename[:-5])
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        self.user_data[user_id] = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Ошибка при загрузке данных пользователя {user_id}: {e}")
                    self.user_data[user_id] = {'habits': [], 'notifications': {}, 'daily_tasks': []}

    def save_all_user_data(self):
        # Метод сохраняет данные всех пользователей в файлы.
        for user_id, data in self.user_data.items():
            filepath = os.path.join(self.data_dir, str(user_id) + ".json")
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)

    def load_user_data(self, user_id):
        # Метод загружает данные конкретного пользователя из файла.
        filepath = os.path.join(self.data_dir, str(user_id) + ".json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    self.user_data[user_id] = json.load(f)
            except json.JSONDecodeError:
                print(f"Ошибка при загрузке данных пользователя {user_id}: поврежденный JSON-файл. Создан новый.")
                self.user_data[user_id] = {'habits': [], 'notifications': {}, 'daily_tasks': []}
        else:
            self.user_data[user_id] = {'habits': [], 'notifications': {}, 'daily_tasks': []}

    def save_user_data(self, user_id):
        # Метод сохраняет данные конкретного пользователя в файл.
        self.save_all_user_data()

    def run(self):
        # Метод запускает бота и начинает прослушивание сообщений.
        self.bot.message_handler(func=lambda message: True)(self.handle_message)
        threading.Thread(target=self.notify_users).start()
        threading.Thread(target=self.clear_daily_tasks).start()
        self.bot.polling()


if __name__ == "__main__":
    API_TOKEN = '8045104104:AAE0vLwZQg0Z4JAaSrfP2Ge2zLnE_E-8vfw'
    bot = HabitBot(API_TOKEN)
    bot.run()
