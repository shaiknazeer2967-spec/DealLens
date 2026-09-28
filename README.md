# 🤝 Deal Intelligence Agent

An AI-powered web application that analyzes sales deals and uses historical memory to provide contextual deal insights.

## 🚨 Problem Statement

Sales teams handle multiple customer deals and often need to remember information from previous interactions. Important customer requirements, concerns, and deal history can be difficult to track and use during a new deal.

This can lead to:

- Missed customer requirements
- Forgotten previous interactions
- Missed deal risks
- Missed opportunities
- Extra manual work for sales teams

## 💡 Solution

We developed the **Deal Intelligence Agent** to analyze current deal information while using historical customer context.

The system combines:

**Current Deal Information + Historical Memory + AI Analysis**

The agent can analyze a deal, retrieve relevant historical information, identify potential risks and opportunities, and provide useful insights.

## 🧠 Hindsight Memory

The project uses a Hindsight-based memory system to store and retrieve relevant information from previous interactions.

For example, if a customer previously mentioned that pricing was a concern, that information can be stored in memory.

When the customer has a new deal, the agent can retrieve the previous information and consider it during the analysis.

This makes the system more context-aware instead of treating every deal as a completely new interaction.

## 🔄 How It Works

```text
User
  ↓
Enter Deal Information
  ↓
Deal Intelligence Agent
  ↓
Retrieve Historical Memory
  ↓
Analyze Current Deal
  ↓
Identify Risks & Opportunities
  ↓
Generate Insights
  ↓
Display Results
📁 Project Structure
deal_agent/
│
├── agent/
│   ├── __init__.py
│   └── analysis.py
│
├── data/
│   └── memory_store.json
│
├── hindsight/
│   ├── __init__.py
│   └── memory.py
│
├── static/
│   ├── css/
│   │   └── style.css
│   │
│   └── js/
│       └── script.js
│
├── templates/
│   ├── deal.html
│   ├── hindsight.html
│   └── index.html
│
├── .env
├── .gitignore
├── app.py
├── requirements.txt
└── README.md
🛠️ Technologies Used
Python
Flask
HTML
CSS
JavaScript
Hindsight Memory
JSON
📌 Main Components
app.py

The main Flask application that runs the web application and connects the frontend, agent, and memory components.

agent/analysis.py

Contains the deal analysis logic used to process deal information and generate insights.

hindsight/memory.py

Handles the memory functionality used to store and retrieve historical information.

data/memory_store.json

Stores the application's historical memory data.

templates/

Contains the HTML pages used by the application.

index.html - Main application page
deal.html - Deal information and analysis page
hindsight.html - Hindsight memory page
static/css/style.css

Contains the styling for the web application.

static/js/script.js

Contains the frontend JavaScript functionality.

requirements.txt

Contains the Python packages required to run the project.

.env

Stores environment variables and API configuration.

Do not upload API keys or secrets to GitHub.

.gitignore

Specifies files and folders that should not be uploaded to GitHub.

🚀 Installation
1. Clone the Repository
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd deal_agent
2. Create a Virtual Environment
python -m venv venv
3. Activate the Virtual Environment

For Windows:

venv\Scripts\activate
4. Install Dependencies
pip install -r requirements.txt
5. Configure Environment Variables

Create a .env file and add the required API keys and configuration values.

YOUR_API_KEY=your_api_key_here

Never upload your actual API keys to GitHub.

6. Run the Application
python app.py

Open the application in your browser:

http://127.0.0.1:5000
✨ Key Features
Deal information input
AI-powered deal analysis
Historical customer memory
Hindsight memory integration
Risk identification
Opportunity detection
Context-aware insights
Interactive web interface
Persistent memory storage
🎯 Example Use Case

A sales representative receives a new deal from an existing customer.

Instead of manually searching through previous interactions, the representative enters the deal information into the application.

The agent:

Reads the current deal information.
Retrieves relevant historical memory.
Analyzes the current deal.
Identifies possible risks.
Detects potential opportunities.
Generates useful insights.
🌟 What Makes the Project Different?

Traditional deal analysis mainly focuses on the information provided during the current interaction.

Our project combines:

Current Deal Data + Historical Memory + AI Analysis

This allows the agent to use previous customer context when analyzing new deals.

🔮 Future Improvements
CRM integration
Automated email analysis
Meeting transcript analysis
Advanced deal scoring
Sales pipeline analytics
Automatic follow-up generation
Real-time notifications
Integration with communication platforms
👥 Team

Developed as a team project for an AI Agent Hackathon.

📄 License

This project is developed for educational and hackathon purposes
