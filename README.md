# AryaChatBot - Instagram AI Chatbot Setup Guide

A sophisticated Instagram DM chatbot with AI personality, music streaming, and smart user memory management.

## 🤖 Overview

AryaChatBot is an advanced Instagram chatbot that:
- Responds to DMs with a realistic GenZ girl persona using Groq AI
- Streams music via VLC with yt-dlp integration
- Learns user preferences and maintains conversation history
- Supports owner-only relay commands and Instagram posting
- Features smart stranger filtering and user behavior tracking

## 📋 Prerequisites

### System Requirements
- **Python**: 3.8 or higher
- **VLC Media Player**: Required for music functionality
- **Operating System**: Windows, macOS, or Linux
- **Internet Connection**: Required for API calls and media streaming

### Before You Begin
- An Instagram account (dedicated bot account recommended)
- Groq API account (free tier available)
- Basic understanding of command line operations

## 🚀 Installation

### 1. Clone or Download the Project
```bash
# If using git
git clone <repository-url>
cd AryaChatBot

# Or download and extract the zip file to your desired location
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Dependencies Installed:**
- `instagrapi` - Instagram API client
- `groq` - AI processing
- `python-dotenv` - Environment variable management
- `yt-dlp` - Media downloader
- `python-vlc` - VLC media player integration

### 4. Verify Installation
```bash
# Test Python installation
python --version

# Test VLC installation (should not throw errors)
python -c "import vlc; print('VLC imported successfully')"
```

## ⚙️ Configuration

### 1. Environment Variables (.env file)

Copy the example configuration and customize it:

```bash
# Create .env file from template (if exists) or create manually
cp .env.example .env  # if template exists
```

**Required Configuration:**

```env
# Groq API Keys (you can add up to 7 for fallback)
GROQ_API_KEY_1=your_first_api_key_here
GROQ_API_KEY_2=your_second_api_key_here
GROQ_API_KEY_3=your_third_api_key_here
# ... add more keys as needed

# System Configuration
SYSTEM_PROMPT_FILE=system_prompt.txt
IGNORED_USERNAMES=akanemusicbot,another_bot_username

# Instagram Authentication
OWNER_USERNAME=your_instagram_username
LOGIN_METHOD=1
IG_USERNAME=your_bot_username
IG_PASSWORD=your_bot_password
```

### 2. Instagram Authentication Setup

#### Method 1: Browser Cookies (Recommended)

1. **Export Instagram Cookies:**
   - Log into Instagram in your browser
   - Install a cookie export extension (like "Get cookies.txt" for Chrome)
   - Export cookies for instagram.com
   - Save as `instaCookies.txt` in the project root

2. **Verify Cookie File:**
   - File should contain either JSON array format or Netscape format
   - Must include `sessionid` cookie

#### Method 2: Username/Password

Set in `.env`:
```env
LOGIN_METHOD=2
IG_USERNAME=your_bot_username
IG_PASSWORD=your_bot_password
```

**⚠️ Security Note:** Method 1 (cookies) is more secure and less likely to trigger Instagram's security measures.

### 3. Groq API Setup

1. **Get API Keys:**
   - Visit [Groq Console](https://console.groq.com/)
   - Create an account and generate API keys
   - Copy keys to your `.env` file

2. **API Key Management:**
   - Bot supports up to 7 API keys with automatic fallback
   - If one key hits rate limits, it automatically switches to the next

### 4. System Prompt Customization

Edit `system_prompt.txt` to customize Arya's personality:

```text
You are Aryaa. your boyfriend kario (the developer of this bot insta username @ilickft), a 22, very realistic GenZ Indian girl chatting on Instagram DMs and groups.

Guidelines for your responses:
1. Extremely Realistic & Short: Keep messages very short, natural, and casual
2. Language Matching: Always mirror the user's language (English/Hinglish)
3. No AI Formatting: Don't use markdown, bullet points, or formal structures
4. Emojis (EXTREMELY RARE): Use emojis maybe once every 5-10 messages
5. One Message Only: Give one single cohesive response
```

## 🎵 Music Setup

### VLC Configuration
1. **Install VLC Media Player:**
   - Download from [videolan.org](https://www.videolan.org/)
   - Install with default settings

2. **Verify VLC Integration:**
   ```python
   import vlc
   player = vlc.MediaPlayer()
   print("VLC working correctly")
   ```

### Music Commands
The bot supports these music commands (use any prefix: /, ., !, $, 0):

- `/play <song name>` - Search and play music
- `/skip` - Skip to next song
- `/pause` - Pause current playback
- `/resume` - Resume playback
- `/stop` or `/end` - Stop music and clear queue
- `/prev` - Play previous track

## 🏃 Running the Bot

### 1. Start the Bot

**Windows:**
```bash
# Double-click start.bat
# OR run manually:
venv\Scripts\activate
python main.py
```

**macOS/Linux:**
```bash
source venv/bin/activate
python main.py
```

### 2. Bot Startup Process
1. Loads configuration from `.env`
2. Initializes Groq AI handler
3. Sets up VLC player
4. Loads music handler
5. Authenticates with Instagram
6. Starts listening for DMs

### 3. Monitoring the Bot
- **Console Output**: Real-time logging of bot activities
- **Log File**: Detailed logs saved to `bot.log`
- **Status Messages**: Bot reports successful startup and authentication

## 🎭 Bot Features

### AI Chatbot
- **Smart Responses**: Uses Groq AI with user context and memory
- **Language Adaptation**: Mirrors user's language style
- **Memory System**: Remembers user preferences and conversation history
- **Stranger Filtering**: Only responds to known users or when mentioned

### User Memory System
The bot tracks:
- User names and preferences
- Conversation history
- Behavior patterns
- Hobbies and interests
- Relationship status (stranger/friend/bad person)

### Owner Commands
Only the owner (specified in `.env`) can use these:

- `/chatbot on/off` - Enable/disable AI responses
- `post [caption]` - Post photos to Instagram feed
- Relay commands - Send messages to other users

### Music System
- **YouTube Integration**: Downloads and streams from YouTube
- **Queue Management**: Multiple songs can be queued
- **Smart Caching**: Downloads cached for faster playback
- **Format Support**: Automatically handles various audio formats

## 🔧 Troubleshooting

### Common Issues

#### Instagram Authentication Failures
```bash
# Error: "Failed to authenticate with Instagram"
# Solution:
1. Regenerate Instagram cookies
2. Ensure cookies file is in correct format
3. Check Instagram account isn't locked or restricted
```

#### VLC Not Working
```bash
# Error: "Failed to import vlc"
# Solution:
1. Install VLC from official website
2. Ensure VLC is in system PATH
3. Restart command prompt/terminal
```

#### Groq API Errors
```bash
# Error: "API rate limit exceeded"
# Solution:
1. Add more API keys to .env
2. Check API key validity in Groq Console
3. Reduce message frequency
```

#### Music Download Failures
```bash
# Error: "This content is restricted from youtube"
# Solution:
1. Try different song titles
2. Some content is age-restricted or copyrighted
3. Bot will skip restricted content automatically
```

### Debug Mode
Enable debug logging by modifying the logging level in `main.py`:
```python
root_logger.setLevel(logging.DEBUG)  # Change from INFO to DEBUG
```

### Reset Bot State
To reset user memory and start fresh:
```bash
# Delete these files:
rm user_profiles.json
rm bot.log
# Restart the bot
```

## 🔒 Security Best Practices

### API Key Security
- Never commit `.env` file to version control
- Use strong, unique API keys
- Regularly rotate API keys
- Monitor API usage in Groq Console

### Instagram Account Safety
- Use a dedicated bot account
- Don't share login credentials
- Monitor for suspicious activity
- Keep cookies updated regularly

### Bot Monitoring
- Check logs regularly for errors
- Monitor Instagram account for restrictions
- Watch for unusual message patterns
- Set up alerts for authentication failures

## 📚 Advanced Configuration

### Custom Commands
Add custom commands by modifying `modules/music_handler.py`:
```python
def is_music_command(self, text: str) -> bool:
    # Add your custom prefixes here
    self.prefixes = ("/", ".", "!", "$", "0", "#")
```

### Custom Actions
Extend the action system in `modules/action_handler.py`:
```python
async def execute(self, action, ...):
    # Add custom action handling
    if action == "custom_action":
        await self._handle_custom_action(...)
```

### Memory Customization
Modify user memory behavior in `modules/user_memory.py`:
```python
# Adjust memory retention
MEMORY_RETENTION_DAYS = 30  # Change from default
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the logs in `bot.log`
3. Ensure all dependencies are properly installed
4. Verify configuration in `.env` file

**Developer Contact:** @ilickft (Instagram)

---

**⚠️ Disclaimer:** This bot is for educational and personal use only. Users are responsible for complying with Instagram's terms of service and applicable laws. The developer is not responsible for any misuse or violations.
