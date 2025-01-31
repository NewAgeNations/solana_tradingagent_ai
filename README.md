# AI Trading Agent

**NewAge Nations DAO** is a cutting-edge, **Multi-AI-Agent powered investment DAO** designed to revolutionize crypto investing. Each specialized AI agent operates autonomously, managing funds for various investment sub-DAOs. By leveraging collective intelligence and advanced AI-driven strategies, NewAge Nations aims to democratize access to sophisticated crypto investment tools, enabling users to outperform traditional methods and achieve superior returns. Join us in shaping the future of decentralized, AI-powered finance.

---

## Features

- **Token Analysis**:
  - Fetches token data from DexScreener.
  - Analyzes tokens using Pocket Universe for fake volume detection.
  - Checks tokens on RugCheck for legitimacy.
  - Uses DeepSeek AI for predictive analytics and sentiment analysis.

- **Trading Execution**:
  - Executes buy/sell orders via BonkBot API.
  - Supports dynamic trading strategies based on AI insights.

- **Database Storage**:
  - Saves token data and analysis results to a PostgreSQL database.

- **Telegram Alerts**:
  - Sends real-time alerts for anomalies and trade executions.

- **Web UI**:
  - Built with Streamlit for monitoring and control.

---

## Prerequisites

- Python 3.9 or higher
- PostgreSQL (for database storage)
- API keys for:
  - DexScreener
  - Pocket Universe
  - RugCheck
  - DeepSeek AI
  - BonkBot
  - Telegram Bot

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/crypto-trading-bot.git
   cd crypto-trading-bot
