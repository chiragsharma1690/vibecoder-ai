
# 🤖 VibeCoder AI - Backend API Documentation

VibeCoder AI is an autonomous, multi-agent software engineering backend. It connects to your Jira board and GitHub repository, reads tickets, plans an architectural strategy, writes code, tests it, reviews it, and automatically opens Pull Requests.

## 🧠 System Architecture & Multi-Agent Workflow

The backend operates on a **Pipeline Architecture** driven by four distinct LLM agents:

1.  **Architect Agent:** Reads the Jira ticket and repository structure. Outputs a strict JSON plan containing files to modify, new files to create, and terminal setup commands.
    
2.  **Developer Agent:** Reads the Architect's plan and writes the raw implementation code.
    
3.  **QA Engineer Agent:** Reads the generated code, writes unit tests, and executes them in the terminal. If tests fail or coverage is `<80%`, it bounces the code back to the Developer for **self-healing**.
    
4.  **Senior Reviewer Agent:** Acts as the Tech Lead. Analyzes the Git diffs against the original Jira ticket to prevent scope creep, logic bugs, and bad practices. If rejected, it bounces back to the Developer.
    

----------

## 🚀 API Workflow (How to use the APIs)

To successfully implement a feature, your frontend must call the APIs in this exact sequence:

1.  **`POST /api/connect`** ➔ Authenticate and clone the repository.
    
2.  **`POST /api/set-branch`** ➔ Select the base branch (e.g., `main`).
    
3.  **`POST /api/chat/plan`** ➔ Generate the Architect's implementation plan.
    
4.  **`POST /api/chat/execute`** ➔ Run the Developer ➔ QA ➔ Reviewer loop.
    
5.  **`POST /api/chat/push`** ➔ _(Sync mode only)_ Push the approved code to GitHub.
    

----------

## 🌐 API Endpoints

### 1. Health Check

Checks if the FastAPI backend is running.

-   **URL:** `/`
    
-   **Method:** `GET`
    
-   **Success Response:**
    
    JSON
    
    ```
    { "status": "active", "message": "VibeCoder Backend is alive." }
    
    ```
    

----------

### 2. Connect Workspace

Authenticates with Jira and GitHub, initializes the `WorkspaceManager`, clones the repository to the local disk, and persists the session.

-   **URL:** `/api/connect`
    
-   **Method:** `POST`
    
-   **Request Body:**
    
    JSON
    
    ```
    {
      "github_token": "ghp_your_github_token",
      "jira_url": "https://yourdomain.atlassian.net",
      "jira_user": "you@email.com",
      "jira_token": "your_jira_api_token",
      "repo_url": "https://github.com/username/repo"
    }
    
    ```
    
-   **Success Response:**
    
    JSON
    
    ```
    {
      "status": "success",
      "message": "Successfully connected to repo.",
      "workspace_path": "/absolute/path/to/workspaces/repo",
      "branches": ["main", "develop", "feature/old-branch"]
    }
    
    ```
    

----------

### 3. Set Base Branch

Checks out the target branch that the AI will use as the foundation for its feature branch.

-   **URL:** `/api/set-branch`
    
-   **Method:** `POST`
    
-   **Request Body:**
    
    JSON
    
    ```
    {
      "branch_name": "main"
    }
    
    ```
    
-   **Success Response:**
    
    JSON
    
    ```
    {
      "status": "success",
      "message": "Switched to base branch: main"
    }
    
    ```
    

----------

### 4. Generate Architect Plan

Fetches the Jira ticket description and triggers the **Architect Agent** to generate a strict JSON blueprint for the implementation. Supports iterative feedback.

-   **URL:** `/api/chat/plan`
    
-   **Method:** `POST`
    
-   **Request Body:**
    
    JSON
    
    ```
    {
      "ticket_id": "KAN-123",
      "feedback": "Make sure to use Tailwind CSS instead of raw CSS files.", 
      "previous_plan": { ... } 
    }
    
    ```
    
    _(Note: `feedback` and `previous_plan` are optional. Use them only if the user is revising an existing plan)._
    
-   **Success Response:**
    
    JSON
    
    ```
    {
      "status": "success",
      "ticket_id": "KAN-123",
      "is_revision": false,
      "plan": {
        "strategy": "Create a new React component for the login form...",
        "files_to_modify": ["src/App.jsx"],
        "new_files": ["src/components/Login.jsx"],
        "commands_to_run": ["npm install react-hook-form"],
        "ui_components_to_screenshot": [{"route": "/login", "selector": "#login-form"}]
      }
    }
    
    ```
    

----------

### 5. Execute Plan (The Multi-Agent Loop)

The core engine. Triggers the Developer, QA, and Reviewer agents.

-   **URL:** `/api/chat/execute`
    
-   **Method:** `POST`
    
-   **Request Body:**
    
    JSON
    
    ```
    {
      "ticket_id": "KAN-123",
      "plan": { ... }, 
      "async_mode": false
    }
    
    ```
    

#### Execution Modes:

**If `async_mode` is `true` (Background Worker):** The API responds immediately. The backend runs the Multi-Agent loop in the background, takes visual Playwright screenshots, tests coverage, commits the code, and automatically opens a Pull Request on GitHub.

-   **Response:**
    
    JSON
    
    ```
    {
      "status": "async",
      "message": "Agent dispatched. A Pull Request for KAN-123 will be generated."
    }
    
    ```
    

**If `async_mode` is `false` (Synchronous Mode):** The API blocks until the AI finishes generating, testing, and reviewing the code. It returns the raw file diffs so the user can review them in the UI before manually pushing.

-   **Response:**
    
    JSON
    
    ```
    {
      "status": "success",
      "message": "Execution finished. QA Passed: True.",
      "files_created": ["src/components/Login.jsx", "src/App.jsx"],
      "test_passed": true,
      "qa_logs": ["QA Execution: All tests passed...", "Code Review: APPROVED"],
      "file_diffs": [
        {
          "file": "src/App.jsx",
          "old_content": "...",
          "new_content": "..."
        }
      ]
    }
    
    ```
    

----------

### 6. Push & Commit (Sync Mode Only)

Approves the changes made during a synchronous execution, commits them to the local Git tree, and pushes the new feature branch to GitHub.

-   **URL:** `/api/chat/push`
    
-   **Method:** `POST`
    
-   **Request Body:**
    
    JSON
    
    ```
    {
      "ticket_id": "KAN-123"
    }
    
    ```
    
-   **Success Response:**
    
    JSON
    
    ```
    {
      "status": "success",
      "message": "Successfully pushed all changes to GitHub!",
      "branch": "feature/KAN-123-a1b2c3"
    }
    
    ```
    

----------

## 🛠️ Error Handling

All endpoints utilize FastAPI's `HTTPException`. If an agent fails, a command times out, or authentication is rejected, the API will return a standard HTTP error code (usually `400`, `401`, or `500`) with a JSON detail message:

JSON

```
{
  "detail": "Failed to clone repository: Git authentication failed."
}

```