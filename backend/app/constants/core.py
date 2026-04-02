SESSION_COOKIE_NAME = "vibecoder_session"
JWT_ALGORITHM = "HS256"

# --- LLM Configurations ---
LLM_TEMPERATURE = 0.1
LLM_CONTEXT_WINDOW = 8192

# --- Workspace & Git Definitions ---
DEFAULT_WORKSPACE_DIR = "workspaces"
DEFAULT_BASE_BRANCH = "main"

# Directories to ignore during repository tree traversal
IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', 'dist', 'build', 
    '.venv', '.agent', '.idea', '.vscode'
}

# Default rules to write into a missing .gitignore file
DEFAULT_GITIGNORE_RULES = [
    "node_modules/", "dist/", "build/", ".env", 
    "__pycache__/", ".DS_Store", ".agent/"
]

# --- Database ---
DEFAULT_DB_NAME = "vibecoder.db"