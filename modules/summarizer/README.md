# Summarizer Module

A Discord bot module that generates concise, on-demand summaries of recent channel activity. This bot helps users catch up on active Discord channels after being away by providing summaries of recent messages.

## Features

- Request summaries of the current channel's recent message history
- Summaries triggered via both message context menu ("Summarize Channel") and slash command (`/summarize`)
- Support for user-specified timeframes (defaulting to last 24 hours, maximum lookback of 1 week)
- Utilizes Google Genai API with Gemini 2.5 Flash Preview to create accurate and informative summaries
- Presents summaries as ephemeral messages (visible only to the requesting user)
- Markdown-formatted summaries with proper headers and bullet points, including key information like participants, topics discussed, arguments, actionables, and links to key messages

## Commands

- **Slash Command**: `/summarize [duration]`
  - Supported duration formats: `1h`, `24h` (default), `1d`, `3d`, `7d`, `1w`
  - Max lookback is 1 week (7 days)

- **Context Menu**: Right-click a message -> Apps -> "Summarize Channel"
  - Presents duration options: "Last Hour", "Last 24 Hours" (Default), "Last 3 Days", "Last Week"

## Requirements

- Discord API permissions: Read Message History
- Gemini API key for AI-powered summarization
- Proper error handling for cases with no messages or API failures

## Technical Architecture

- `api.py`: Flask API endpoints for the summarizer module
- `models.py`: Data models for storing summary configurations
- `service.py`: Business logic for generating summaries using Gemini API
- `cog.py`: Discord commands implementation using py-cord