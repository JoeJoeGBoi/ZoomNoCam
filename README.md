# Zoom Automation Bot

This is a Python desktop automation tool that monitors the Zoom **Participants panel** and enforces meeting rules automatically:

- 📌 Keeps focus on the **last page** of Participants.
- 🎥 Guests with **cameras off** get a 30s warning → if still off, they are removed.
- 📍 Guests with **multi-pin enabled** → pins are removed.
- 🛑 **Co-hosts** are skipped automatically.
- ⏱ Runs continuously while Zoom is open.

---

## 🚀 Installation

Clone this repository:

```bash
git clone https://github.com/yourusername/zoom-automation-bot.git
cd zoom-automation-bot
