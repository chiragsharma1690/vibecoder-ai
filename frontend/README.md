

# 🎨 VibeCoder AI - Frontend Documentation

VibeCoder AI's frontend is a modern, responsive React application styled with Tailwind CSS. It provides a sleek, dark-mode, terminal-like chat interface that allows developers to interact seamlessly with the Multi-Agent backend to scaffold, code, test, and review Jira tickets.

## 🧠 UI Architecture & User Workflow

The frontend is designed as a state-driven Chat UI that guides the user through the AI's execution phases. 

### The 3-Phase Workflow:
1. **Initialization Phase (`SetupForm`):** - Takes Jira & GitHub credentials.
   - Pings the backend to clone the repository locally.
   - Fetches available Git branches and lets the user select a `base_branch`.
2. **Planning Phase (`ChatInterface` & `PlanCard`):** - User inputs a Jira Ticket ID.
   - AI Architect returns a JSON plan.
   - User reviews the strategy, files affected, commands, and Playwright QA targets.
   - User can provide text feedback to revise the plan, or approve it.
3. **Execution & Review Phase (`DiffCard`):**
   - **Async Mode:** Dispatches the AI to work in the background and returns a success message when the PR is opened.
   - **Sync Mode:** Blocks the UI while the AI codes. Once finished, presents an expandable side-by-side diff viewer for human review, followed by a "Push to GitHub" approval button.


## 🛠️ Prerequisites

Before running the VibeCoder frontend, ensure your system has the following installed:
* **Node.js** (v16+ recommended)
* **npm** or **yarn** or **pnpm**
* *The VibeCoder Backend must be running on `http://localhost:8000`*

---

## 💻 Local Setup

1. **Clone the frontend repository:**
   ```
   git clone [https://github.com/your-org/vibecoder-frontend.git](https://github.com/your-org/vibecoder-frontend.git)
   cd vibecoder-frontend

2.  **Install dependencies:**
    
 
    
    ```
    npm install
    
    ```
    
    _(Core Packages: `react`, `axios`, `lucide-react`, `tailwindcss`, `react-diff-viewer-continued`)_
    
3.  **Start the Vite development server:**
    
    ```
    npm run dev
    
    ```
    
    The application will be available at `http://localhost:5173`.
    

## 🧩 Component Breakdown

### 1. `App.jsx` (The Shell)

The root component that manages the highest-level state (`isConnected`, `workspaceInfo`). It renders the application header and conditionally swaps between the `SetupForm` (if not connected) and the `ChatInterface` (if connected).

### 2. `SetupForm.jsx` (Authentication & Init)

A two-step wizard:

-   **Step 1:** Collects and saves credentials (`jira_url`, `github_token`, etc.) to `localStorage` for convenience. Calls `POST /api/connect`.
    
-   **Step 2:** Displays a dropdown of branches fetched from the backend. Calls `POST /api/set-branch`.
    

### 3. `ChatInterface.jsx` (The Core Engine)

A messenger-style interface tracking an array of `messages`.

-   Automatically auto-scrolls to the newest message.
    
-   Implements **Concurrency Locks** (`isProcessing`) to prevent users from spamming the backend while the AI is generating.
    
-   Routes data between the backend APIs (`/plan`, `/execute`, `/push`) and the presentation cards (`PlanCard`, `DiffCard`).
    

### 4. `PlanCard.jsx` (Architect's Blueprint)

Renders the `plan` JSON returned by the Architect agent into a readable, dashboard-like card.

-   Displays "Files Affected" and "Commands".
    
-   Displays "QA Visual Testing Targets" (Playwright routing).
    
-   Includes a feedback textarea for revisions.
    
-   Includes a toggle switch to toggle between **Async Mode** (Auto-PR) and **Sync Mode** (Manual Diff Review).
    

### 5. `DiffCard.jsx` (Code Reviewer)

Leverages `react-diff-viewer-continued` to provide a side-by-side code comparison of the AI's changes.

-   Custom-styled to perfectly match the Tailwind `slate-900` dark mode.
    
-   Expandable/Collapsible file headers so massive PRs don't overwhelm the UI.
    
-   Clearly tags "New Files" vs "Modified Files".
    




## 📁 Project Structure


```
src/
 ├── components/
 │    ├── ChatInterface.jsx   # The main chat logic and message renderer
 │    ├── DiffCard.jsx        # Side-by-side Git diff viewer
 │    ├── PlanCard.jsx        # AI Strategy & Approval Card
 │    └── SetupForm.jsx       # 2-Step credential and branch selector
 ├── App.jsx                  # Root layout and auth-state manager
 ├── index.css                # Tailwind base imports and global styles
 └── main.jsx                 # React DOM attachment
```