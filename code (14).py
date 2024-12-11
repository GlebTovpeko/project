import telebot
from telebot import types
from datetime import datetime, timedelta
import time
import threading
import re
import json
import os

# Базовый класс для команд
class BotCommand:
    def __init__(self, bot):
        self.bot = bot

# Команды
class StartCommand(BotCommand):
    def execute(self, message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Добавить привычку', 'Добавить нотификатор', 'Добавить задание', 'Просмотреть задания', 'Просмотреть привычки и нотификаторы', 'Команды')
        self.bot.bot.send_message(message.chat.id, "Привет! Я помощник по формированию привычек и задач. Выберите действие:", reply_markup=markup)


class AddHabitCommand(BotCommand):
    def execute(self, message):
        self.bot.bot.send_message(message.chat.id, "Введите новую привычку:")
        self.bot.bot.register_next_step_handler(message, self.save_habit)

    def save_habit(self, message):
        habit = message.text
        user_id = message.chat.id
        self.bot.load_user_data(user_id)
        self.bot.user_data[user_id]['habits'].append(habit)
        self.bot.save_user_data(user_id)
        self.bot.bot.send_message(message.chat.id, f"Привычка '{habit}' добавлена!")


class AddNotificationCommand(BotCommand):
    def execute(self, message):
        self.bot.bot.send_message(message.chat.id, "Введите время (в формате ЧЧ:ММ) и привычку, для которой установить уведомление:")
        self.bot.bot.register_next_step_handler(message, self.save_notification)

    def save_notification(self, message):
        user_id = message.chat.id
        text = message.text.split()
        if len(text) < 2 or not re.match(r'^\d{2}:\d{2}$', text[0]):
            self.bot.bot.send_message(user_id, "Неверный формат. Используйте:  'ЧЧ:ММ <название привычки>'")
            self.bot.bot.register_next_step_handler(message, self.save_notification)
            return

        time_str = text[0]
        habit = ' '.join(text[1:])

        self.bot.load_user_data(user_id)
        if habit not in self.bot.user_data[user_id]['habits']:
            self.bot.bot.send_message(user_id, "Привычка не найдена.")
            return

        user_data = self.bot.user_data.setdefault(user_id, {'habits': [], 'notifications': {}})
        notifications = user_data['notifications']
        notifications.setdefault(user_id, []).append({'time': time_str, 'habit': habit})
        self.bot.save_user_data(user_id)
        self.bot.bot.send_message(user_id, f"Нотификатор для '{habit}' установлен на {time_str}.")


class AddTaskCommand(BotCommand):
    def execute(self, message):
        self.bot.bot.send_message(message.chat.id, "Введите задание:")
        self.bot.bot.register_next_step_handler(message, self.save_task)

    def save_task(self, message):
        task = message.text
        self.bot.load_user_data(message.chat.id)
        self.bot.user_data[message.chat.id]['daily_tasks'].append(task)
        self.bot.save_user_data(message.chat.id)
        self.bot.bot.send_message(message.chat.id, f"Задание '{task}' добавлено в список дел на сегодня!")


class ViewTasksCommand(BotCommand):
    def execute(self, message):
        self.bot.load_user_data(message.chat.id)
        tasks = self.bot.user_data.get(message.chat.id, {}).get('daily_tasks', [])
        response = "Ваш список дел на сегодня:\n" + "\n".join(tasks) if tasks else "У вас нет заданий на сегодня."
        self.bot.bot.send_message(message.chat.id, response)


class ViewHabitsNotificationsCommand(BotCommand):
    def execute(self, message):
        user_id = message.chat.id
        self.bot.load_user_data(user_id)
        habits = self.bot.user_data.get(user_id, {}).get('habits', [])
        notifications = self.bot.user_data.get(user_id, {}).get('notifications', {})

        response = "Ваши привычки и нотификаторы:\n"
        if habits:
            for i, habit in enumerate(habits):
                response += f"\nПривычка {i + 1}: {habit}\n"
                for notification in notifications.get(user_id, []):
                    if notification['habit'] == habit:
                        response += f"  - Нотификатор: {notification['time']}\n"
        else:
            response += "У вас нет привычек."
        self.bot.bot.send_message(user_id, response)


class CommandsCommand(BotCommand):
    def execute(self, message):
        self.bot.bot.send_message(message.chat.id, "Доступные команды и их функционал:\n1. 'Добавить привычку' - добавляет долгосрочную привычку.\n2. 'Добавить нотификатор' - добавляет напоминание о привычке.\n3. 'Добавить задание' - добавляет задачу в список дел на сегодня.\n4. 'Просмотреть задания' - показывает список дел на сегодня.\n5. 'Просмотреть привычки и нотификаторы' - показывает список привычек и напоминаний.")


class UnknownCommand(BotCommand):
    def execute(self, message):
        self.bot.bot.send_message(message.chat.id, "Ошибка! Попробуйте ввести одну из поддерживаемых команд.")



# Класс бота
class HabitBot:
    def __init__(self, token):
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
            'Просмотреть привычки и нотификаторы': ViewHabitsNotificationsCommand(self),
            'Команды': CommandsCommand(self),
        }
        self.default_command = UnknownCommand(self)

    def handle_message(self, message):
        user_id = message.chat.id
        self.load_user_data(user_id)
        command = self.commands.get(message.text, self.default_command)
        command.execute(message)

    def notify_users(self):
        while True:
            now = datetime.now().strftime("%H:%M")
            for user_id, data in self.user_data.items():
                for notification in data.get('notifications', {}).get(user_id, []):
                    if notification['time'] == now:
                        self.bot.send_message(user_id, f"Время для привычки: {notification['habit']}")
            time.sleep(60)

    def clear_daily_tasks(self):
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
        for user_id, data in self.user_data.items():
            filepath = os.path.join(self.data_dir, str(user_id) + ".json")
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)

    def load_user_data(self, user_id):
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
        self.save_all_user_data()

    def run(self):
        self.bot.message_handler(func=lambda message: True)(self.handle_message)
        threading.Thread(target=self.notify_users).start()
        threading.Thread(target=self.clear_daily_tasks).start()
        self.bot.polling()


if __name__ == "__main__":
    API_TOKEN = '8045104104:AAE0vLwZQg0Z4JAaSrfP2Ge2zLnE_E-8vfw'
    bot = HabitBot(API_TOKEN)
    bot.run()