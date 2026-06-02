import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from Modules.utils.logger import iot_logger
from datetime import datetime


env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)



class TelegramBot:
    def __init__(self, server_instance):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.admin_id = int(os.getenv("ADMIN_ID"))
        self.server = server_instance # The object managing the DB must be passed here
        self.group_id = None
        self.subscriptions = {}
        self.alerts = {}
        self.app = None
        self.loop = None



    async def _is_in_group(self, update: Update):

        if self.group_id is None or update.effective_chat.id != self.group_id:

            await update.message.reply_text(" Command only available in the group registered by the admin.")
            return False

        return True

        

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id

        if user_id == self.admin_id:
            await update.message.reply_text(" Admin authenticated. Use `/set_group` in the corresponding group.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"Hello! Your ID is {user_id}. Only the admin can configure the system.")



    async def set_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user.id != self.admin_id:
            await update.message.reply_text(" Access denied: Only the administrator can register the group.")
            return

        

        self.group_id = update.effective_chat.id
        iot_logger.info(f"Group registered: {self.group_id}")



        help_text = (

            " *Group successfully registered!*\n\n"
            "You can use the following commands:\n\n"
            "1 `/subscribe {\"1\":[\"temperature\"]}`\n"
            "   _Receives data automatically every 15 seconds._\n\n"
            "2 `/get_data {\"1\":[\"humidity\"]}`\n"
            "   _Queries the current value of a sensor instantly._\n\n"
            "3 `/create_alert {\"1\":{\"temperature\":30}}`\n"
            "   _Receives a notification only if the value exceeds the limit._\n\n"
            "4 `/subscribe {}` or `/create_alert {}`\n"
            "   _Stop receiving messages or alerts of this type._"

        )

        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    def _check_sensor_status(self, data_json):
        error_messages = []
        now = datetime.now()
        
        if not data_json or not isinstance(data_json, dict):
            return error_messages

        for plc_id, sensors in data_json.items():
            if not isinstance(sensors, dict):
                continue
            for sensor, data in sensors.items():
                if not isinstance(data, dict):
                    continue
                
                # 1. ENSURE THE 'STATUS' FIELD ALWAYS EXISTS BY DEFAULT
                if "status" not in data:
                    data["status"] = "PENDING"

                # 2. CHECK IF IT HAS THE DATE FIELD
                if "last_update" in data:
                    try:
                        date_str = data["last_update"].strip()
                        
                        # ✂️ TRICK: If the date has microseconds (contains a '.'), we remove them
                        if "." in date_str:
                            date_str = date_str.split(".")[0]
                        
                        # Now date_str will ALWAYS be "2026-06-02 12:05:49"
                        last_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        diff_seconds = (now - last_time).total_seconds()
                        
                        if diff_seconds > 20:
                            error_messages.append(f"⚠️ *WARNING:* Sensor '{sensor}' (PLC {plc_id}) has been without data for {int(diff_seconds)}s.")
                            data["status"] = "OFFLINE"
                            iot_logger.error(f"Sensor '{sensor}' offline due to timeout.")
                        else:
                            data["status"] = "ONLINE"
                            
                    except ValueError as e:
                        error_messages.append(f"❌ *ERROR:* Incorrect date format for sensor '{sensor}'. Received: '{data['last_update']}'")
                        data["status"] = "FORMAT_ERROR"
                        iot_logger.error(f"Date format error in '{sensor}': {e}")
                else:
                    # 3. IF IT IS THE SIMULATED ONE AND HAS NO DATE, WE DETECT IT HERE
                    error_messages.append(f"❓ *NOTICE:* Sensor '{sensor}' (PLC {plc_id}) does not send the 'last_update' field.")
                    data["status"] = "NO_DATE"
                    iot_logger.warning(f"Sensor '{sensor}' has no 'last_update' (possibly the simulated one)")
                    
        return error_messages
 

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_in_group(update): return

        try:
            input_data = " ".join(context.args)
            new_subscription = json.loads(input_data)
            user_id = update.effective_user.id

            if not new_subscription:  
                self.subscriptions.pop(user_id, None)
                await update.message.reply_text(" *Subscription canceled.*")

            else:
                self.subscriptions[user_id] = new_subscription
                await update.message.reply_text(f" Subscription active for {update.effective_user.first_name}!")
                iot_logger.info(f"Subscription active")

        except json.JSONDecodeError:
            await update.message.reply_text(" Malformed JSON. Example: `/subscribe {\"1\":[\"temperature\"]}`", parse_mode=ParseMode.MARKDOWN)

    async def get_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await self._is_in_group(update): return

        if not self.server:
            await update.message.reply_text(" Error: The data server is not connected.")
            return

        try:

            input_text = " ".join(context.args)
            query = json.loads(input_text)
            data_json = self.server.get_latest_data(query)

            errors = self._check_sensor_status(data_json)
            response = json.dumps(data_json, indent=2)
            final_message = f" *Latest data on demand:*\n```json\n{response}\n```"

            if errors:
                final_message += "\n\n" + "\n".join(errors)

            await update.message.reply_text(final_message, parse_mode=ParseMode.MARKDOWN)
            iot_logger.info(f"Manual query performed by user {update.effective_user.id}")

        except json.JSONDecodeError:
            await update.message.reply_text(" Incorrect format. Example:\n`/get_data {\"1\": [\"temperature\"]}`", parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    async def create_alert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_in_group(update): return

        try:
            input_data = " ".join(context.args)
            new_alerts = json.loads(input_data)
            user_id = update.effective_user.id

            if not new_alerts:  
                self.alerts.pop(user_id, None)
                await update.message.reply_text(" *Alerts disabled.*")

            else:
                self.alerts[user_id] = new_alerts
                await update.message.reply_text(f" Alert configured successfully!")
                iot_logger.info(f"Alert configured")

        except json.JSONDecodeError:
            await update.message.reply_text(" Incorrect format. Example:\n`/get_data {\"1\": [\"temperature\"]}`", parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

    async def run_periodic_check(self):
        while True:
            # 👈 General safety wrapper to prevent the loop from dying if Telegram or the network fails
            try:
                if self.group_id and self.server:
                    # Process Subscriptions (Periodic data)
                    for user_id, sub_config in self.subscriptions.items():
                        data = self.server.get_latest_data(sub_config) 
                        if data:
                            errors = self._check_sensor_status(data)
                            msg = f" *Periodic data (15s)*:\n```json\n{json.dumps(data, indent=2)}\n```" 
                            if errors:
                                msg += "\n\n" + "\n".join(errors)
                            await self.app.bot.send_message(chat_id=self.group_id, text=msg, parse_mode=ParseMode.MARKDOWN) 

                    # Process Alerts (Periodic data)
                    for user_id, alert_config in self.alerts.items():
                        for plc_id, sensors_limits in alert_config.items():
                            query = {str(plc_id): list(sensors_limits.keys())}
                            current_data = self.server.get_latest_data(query)
                            connection_errors = self._check_sensor_status(current_data)
                            
                            plc_data = current_data.get(str(plc_id), {})
                            alert_blocks = [] 

                            if isinstance(plc_data, dict):
                                for sensor_id, limit in sensors_limits.items():
                                    reading = plc_data.get(sensor_id)
                                    
                                    if reading and reading.get("status") == "ONLINE":
                                        value = reading.get('value', 0)
                                        if value > limit:
                                            block = (
                                                f" *PLC:* {plc_id} | *Sensor:* {sensor_id}\n"
                                                f" *Value:* {value} {reading.get('unit')}\n"
                                                f" *Limit:* {limit}"
                                            )
                                            alert_blocks.append(block)

                            if alert_blocks:
                                final_message = " *ALERT: CRITICAL VALUE* \n\n"
                                final_message += "\n\n".join(alert_blocks) 

                                if connection_errors:
                                    final_message += "\n\n *Incidents:* \n" + "\n".join(connection_errors)

                                await self.app.bot.send_message(
                                    chat_id=self.group_id, 
                                    text=final_message, 
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            
                            elif connection_errors:
                                error_msg = "🔌 *CONNECTION WARNING (PLC " + str(plc_id) + ")*\n" + "\n".join(connection_errors)
                                await self.app.bot.send_message(chat_id=self.group_id, text=error_msg, parse_mode=ParseMode.MARKDOWN)
            
            except Exception as loop_error:
                # If there is a Telegram error, it is caught here and the 'while True' keeps running
                iot_logger.error(f"Controlled error in the bot periodic loop: {loop_error}")
                                    
            await asyncio.sleep(15) # 15-second wait



    async def post_init(self, application):

        self.loop = asyncio.get_running_loop() # Save the loop for MQTT
        asyncio.create_task(self.run_periodic_check())
        iot_logger.info("Verification system started.")



    def run(self):

       
        iot_logger.info("Configuring Telegram Bot...")

        # We build the application and assign the task initialization function
        self.app = ApplicationBuilder().token(self.token).post_init(self.post_init).build()

        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("set_group", self.set_group))
        self.app.add_handler(CommandHandler("subscribe", self.subscribe))
        self.app.add_handler(CommandHandler("get_data", self.get_data))
        self.app.add_handler(CommandHandler("create_alert", self.create_alert))

        # This call is BLOCKING and manages the loop automatically
        iot_logger.info("Bot running (Polling)...")
        self.app.run_polling()