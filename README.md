# 🚀 VibeCoder AI

**Your Autonomous, Multi-Agent AI Software Engineer**

VibeCoder AI is an end-to-end, autonomous AI software engineering platform. It bridges the gap between project management (Jira) and version control (GitHub) using a localized, self-healing Multi-Agent system powered by large language models (Ollama). 

Give VibeCoder a Jira ticket, and it will architect a solution, write the code, run the unit tests, visually verify UI components, review its own logic, and open a Pull Request—all while chatting with you in a sleek, dark-mode terminal UI.


## ✨ Key Features

* **Multi-Agent Orchestration:** Utilizes four specialized AI personas (Architect, Developer, QA Engineer, Senior Reviewer) to simulate a real engineering pod.
* **Self-Healing Feedback Loops:** If code fails tests or lacks >80% coverage, the QA Agent bounces the terminal logs back to the Developer to fix it automatically.
* **Visual UI Testing:** Leverages Playwright to take headless screenshots of newly generated frontend components and attaches them directly to your GitHub PR.
* **Strict Scope Enforcement:** The Senior Reviewer Agent cross-references the generated code against the original Jira ticket to prevent scope creep and gold-plating.
* **Agnostic Language Support:** Reads your repository tree dynamically to determine if it should write Python, JavaScript, Java, Go, or Rust.
* **Sync & Async Modes:** Review diffs manually side-by-side in the UI, or dispatch the AI into the background to handle everything and alert you when the PR is ready.


## 🏗️ System Architecture

The VibeCoder platform is split into two decoupled environments:

1.  **The Frontend (`/frontend`):** A modern React + Vite application styled with Tailwind CSS. It acts as the mission control center, capturing credentials, visualizing architectural plans, and rendering side-by-side code diffs.
2.  **The Backend (`/backend`):** A robust Python FastAPI server. It manages local git workspaces, orchestrates local Ollama LLM interactions, safely executes terminal commands, and handles all GitHub/Jira API routing.


## 📁 Repository Structure

```text
vibecoder-ai/
 ├── backend/               # Python, FastAPI, Ollama Agents, Git Orchestrator
 │    ├── README.md         # Detailed Backend API Documentation
 │    ├── requirements.txt  
 │    └── ...
 │
 ├── frontend/              # React, Vite, Tailwind CSS Chat Interface
 │    ├── README.md         # Detailed Frontend UI Documentation
 │    ├── package.json      
 │    └── ...
 │
 └── README.md              # Project Landing Page (You are here)

```


## 🚀 Getting Started

### Prerequisites

Ensure your local machine or server has the following installed:

-   **Python 3.9+** (For the backend orchestrator)
    
-   **Node.js v16+ & npm** (For the frontend UI and Playwright)
    
-   **Git** (Installed and configured)
    
-   **Ollama** (Running locally with the `qwen2.5-coder:7b` model pulled: `ollama run qwen2.5-coder:7b`)
    

### Step 1: Start the Backend

The backend needs to be running first so the frontend can establish a connection.

```
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

_For deep-dive documentation on the APIs and Agent logic, see the [Backend README](https://www.google.com/search?q=./backend/README.md)._

### Step 2: Start the Frontend

In a new terminal instance, boot up the React interface.

```
cd frontend
npm install
npm run dev
```

_For deep-dive documentation on UI components and state management, see the [Frontend README](https://www.google.com/search?q=./frontend/README.md)._

### Step 3: Launch VibeCoder

1.  Open your browser to `http://localhost:5173`.
    
2.  Enter your Jira URL, Jira Token, GitHub PAT, and the target Repository URL.
    
3.  Select your base branch.
    
4.  Drop in a Jira Ticket ID (e.g., `KAN-12`) and watch your autonomous engineer go to work!
    

## 🛠️ Tech Stack

-   **AI Engine:** Ollama (Local LLMs)
    
-   **Backend Framework:** FastAPI (Python)
    
-   **Frontend Framework:** React + Vite (JavaScript)
    
-   **Styling:** Tailwind CSS + Lucide Icons
    
-   **Version Control:** Native Git Subprocess + GitHub REST API
    
-   **QA Automation:** Playwright (Python Sync API) + Regex Coverage Parsers