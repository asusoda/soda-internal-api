# from quart import Quart, render_template, redirect, url_for, render_template, redirect, url_for, jsonify, request, session
from flask import Flask, render_template, redirect, url_for
from shared import app, bot, AUTHORIZED_USERS, bot_running, discord_oauth
import asyncio
import requests
import json



