# import os
# import threading

# import discord
# from flask import Flask, redirect, url_for, session, request, jsonify, render_template
# import requests
# from bot import Bot
# from threading import Thread
# import asyncio
# import logging

# app = Flask("SODA Discord Bot")

# # app.secret_key = b"random bytes representing flask secret key"
# # os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      # !! Only in development environment.

# # app.config["DISCORD_CLIENT_ID"] = 1153940272867180594   # Discord client ID.
# # app.config["DISCORD_CLIENT_SECRET"] = "_2DJ787FBtThsR9oaPI3Qx3MsB4rNwdN"                # Discord client secret.
# # app.config["DISCORD_REDIRECT_URI"] = "https://www.google.com/"                 # URL to your callback endpoint.
# # app.config["DISCORD_BOT_TOKEN"] = "MTE1Mzk0MDI3Mjg2NzE4MDU5NA.GW4vDt.TTACYu1rK2KwI3qRTmcfAsPcF8IARJQQAK_Kco"                    # Required to access BOT resources.

# app.secret_key = b"random bytes representing flask secret key"
# CLIENT_ID = 1153940272867180594   
# CLIENT_SECRET = "_2DJ787FBtThsR9oaPI3Qx3MsB4rNwdN"              
# REDIRECT_URI = "http://localhost:5000/login/callback"                 
# BOT_TOKEN = "MTE1Mzk0MDI3Mjg2NzE4MDU5NA.GW4vDt.TTACYu1rK2KwI3qRTmcfAsPcF8IARJQQAK_Kco"
# OAUTH_URL = "https://discord.com/api/oauth2/authorize?client_id=1153940272867180594&redirect_uri=http%3A%2F%2Flocalhost%3A5000%2Flogin%2Fcallback&response_type=code&scope=identify%20email"


# intents = discord.Intents.default()
# intents.message_content = True
# logger = logging.getLogger('SODA Discord Bot')
# bot = Bot(intents= intents)

# def run_bot():
#     bot.run(BOT_TOKEN)

# thread = None 



# @app.route("/")
# def home():
#     # Check if the user is logged in
#     # if 'access_token' in session:
#     #     headers = {
#     #         'Authorization': 'Bearer {}'.format(session['access_token'])
#     #     }
#     #     response = requests.get('https://discord.com/api/users/@me', headers=headers)
#     #     user_data = response.json()
#     #     return render_template('home.html', username=user_data['username'])
#     # else:
#     #     return render_template('home.html')
#     return render_template('index.html')

# @app.route('/login')
# def login():
#     return redirect(OAUTH_URL)

# @app.route('/login/callback')
# def login_callback():
#     code = request.args.get('code')
#     data = {
#         'client_id': CLIENT_ID,
#         'client_secret': CLIENT_SECRET,
#         'grant_type': 'authorization_code',
#         'code': code,
#         'redirect_uri': REDIRECT_URI,
#         'scope': 'identify email'
#     }
#     headers = {
#         'Content-Type': 'application/x-www-form-urlencoded'
#     }
#     response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
#     response_data = response.json()
#     print(response_data)
#     session['access_token'] = response_data['access_token']
#     return redirect(url_for('me'))

# @app.route('/me')
# def me():
#     headers = {
#         'Authorization': 'Bearer {}'.format(session['access_token'])
#     }
#     response = requests.get('https://discord.com/api/users/@me', headers=headers)
#     user_data = response.json()
#     print(user_data)
#     user_avatar_url = "https://cdn.discordapp.com/avatars/{}/{}.png".format(user_data['id'], user_data['avatar'])
#     print(user_avatar_url)
#     return render_template('me.html', username=user_data['username'], user_avatar_url=user_avatar_url)


# @app.route('/api/status')
# def api_status():
#     return jsonify({
#         'status': 'ok'
#     })

# @app.route('/api/loginstatus')
# def status():
#     if 'access_token' in session:
#         return jsonify(logged_in=True)
#     else:
#         return jsonify(logged_in=False)
# @app.route('/logout')
# def logout():
#     # Clear the session data
#     session.clear()
#     return redirect(url_for('home'))

# @app.route("/start", methods=['POST'])
# def start():
#     # Your logic for the /start endpoint goes here
    
#     thread = threading.Thread(target=run_bot)
#     thread.start()
#     return "Bot started"


# @app.route("/stop", methods=['POST'])
# async def stop():
#     # Your logic for the /stop endpoint goes here
#     await bot.close()
#     thread.stop()
#     return "Bot stopped"





# if __name__ == "__main__":
#     logger.info("Starting SODA Discord Bot Portal")
#     app.run(debug=True, port=5000)


