from quart import Quart, render_template, redirect, url_for, render_template, redirect, url_for, jsonify
from shared import app, discord_oauth, bot, AUTHORIZED_USERS, bot_running, discord
import asyncio
import discord as dpy

def generate_game_panel(game_data):
    html = '<table border="1">\n'
    html += '<thead>\n<tr>\n'
    html += '<th>Category</th>\n'
    html += '<th>Question</th>\n'
    html += '<th>Answer</th>\n'
    html += '<th>Points</th>\n'
    html += '<th>Answer</th>\n'
    for team in game_data["game"]["teams"]:
        html += f'<th>{team}</th>\n'
    html += '</tr>\n</thead>\n'
    html += '<tbody>\n'
    for category, questions in game_data["questions"].items():
        for question in questions:
            html += '<tr>\n'
            html += f'<td>{category.capitalize()}</td>\n'
            html += f'<td>{question["question"]}</td>\n'
            html += f'<td>{question["answer"]}</td>\n'  # Answer is displayed directly
            html += f'<td>{question["value"]}</td>\n'
            html += '<td><button onclick="answerQuestion(this)">Answer</button></td>\n'
            for team in game_data["game"]["teams"]:
                html += f'<td><button onclick="awardPoints(\'{team}\', {question["value"]})">Award to {team}</button></td>\n'
            html += '</tr>\n'
    html += '</tbody>\n'
    html += '</table>\n'
    return html

def generate_game_info(game_data):
    # Extract game details
    game_name = game_data["game"]["name"]
    game_description = game_data["game"]["description"]
    teams_count = len(game_data["game"]["teams"])
    players_count = game_data["game"]["players"]
    categories_count = game_data["game"]["categories"]
    per_category = game_data["game"]["per_category"]
    html = f'<h1>{game_name}</h1>\n'
    html += f'<p>Description: {game_description}</p>\n'
    html += f'<p>Teams: {teams_count}, Players: {players_count}, Categories: {categories_count}, Questions per Category: {per_category}</p>\n'
    
    return html


@app.route("/")
async def home():
    return await render_template("home.html")

@app.route("/login")
async def login():
    return await discord_oauth.create_session() # handles session creation for authentication

@app.route("/callback")
async def callback():
    try:
        await discord_oauth.callback()
    except Exception:
        pass

    return redirect(url_for("dashboard")) 


@app.route("/dashboard")
async def dashboard():
    if await discord_oauth.authorized:
        user = await discord_oauth.fetch_user()
        if str(user.id) in AUTHORIZED_USERS:
            return await render_template("dashboard.html", authorized=await discord_oauth.authorized, user=user)
        else:
            return await render_template("dashboard.html", authorized=await discord_oauth.authorized, user=user, error="You are not authorized to start the bot.")
    else:
        return await render_template("dashboard.html", authorized=await discord_oauth.authorized, user=user, error="You are not logged in.")

@app.route("/gamepanel")
async def gamepanel():
    
        game_data = {
    "game" : {
        "name" : "Game 1",
        "description" : "This is a game",
        "players" : 4,
        "categories" : 2,
        "per_category" : 2, 
        "teams": ["Team 1", "Team 2", "Team 3", "Team 4"]
    },
    "questions": {
        "category1" : [
            {
                "question" : "Question 1",
                "answer" : "Answer 1",
                "value" : 100,
                "uuid" : "1234"
            },
            {
                "question" : "Question 2",
                "answer" : "Answer 2",
                "value" : 200,
                "uuid" : "1233"
            }
        ],
        "category2" : [
            {
                "question" : "Question 1",
                "answer" : "Answer 1",
                "value" : 100,
                "uuid" : "1232"
            },
            {
                "question" : "Question 2",
                "answer" : "Answer 2",
                "value" : 200,
                "uuid" : "1231"
            }
        ]
    }
}
        
        html = generate_game_panel(game_data)
        game_info = generate_game_info(game_data)
        print(game_info)
        return await render_template("gamepanel.html", game_panel = html, game_info = game_info)
        
