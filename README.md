# Game Support Tracker Bot

A Discord bot that tracks new games added to the Archipelago game support spreadsheet and sends notifications to your server.

It monitors two lists:
- **Playable Worlds**
- **Core Verified**

Whenever a new game is added to one of these lists, the bot sends a message in your configured channel and pings a role (or @everyone by default).

---

## Add the Bot to Your Server

Click the link below to invite the bot to your Discord server:

https://discord.com/oauth2/authorize?client_id=1479196989299364002&permissions=133120&integration_type=0&scope=bot

---

## Setup

Once the bot is in your server, follow these steps:

**1. Set the notification channel**

Go to the channel where you want the bot to send notifications and type:

```
!setchannel
```

The bot will now send a message in that channel whenever a new game is added to the spreadsheet.

> You must be a server administrator to use this command.

---

**2. (Optional) Set a role to ping**

If you want the bot to ping a specific role instead of @everyone, use:

```
!setrole @RoleName
```

Or with a role ID:

```
!setrole 123456789012345678
```

> You must be a server administrator to use this command.

---

## Commands

| Command | Description | Required Permission |
|---|---|---|
| `!setchannel` | Set the current channel as the notification channel | Administrator |
| `!setrole @Role` | Set a role to be pinged for new game notifications | Administrator |
| `!removerole` | Remove the configured role (bot will ping @everyone instead) | Administrator |
| `!removechannel` | Disable all notifications on this server | Administrator |
| `!status` | Show the current configuration (channel, role, number of tracked games) | Anyone |

---

## Notes

- Only one channel per server can be configured at a time.
- If no role is set, the bot will ping @everyone.
- The bot checks for new games at a regular interval (default: every 60 seconds).

