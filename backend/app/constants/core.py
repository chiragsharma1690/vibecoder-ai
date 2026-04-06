SESSION_COOKIE_NAME = "vibecoder_session"
JWT_ALGORITHM = "HS256"

# --- LLM Configurations ---
LLM_TEMPERATURE = 0.1
LLM_CONTEXT_WINDOW = 8192

# --- Workspace & Git Definitions ---
DEFAULT_WORKSPACE_DIR = "workspaces"
DEFAULT_BASE_BRANCH = "main"

# --- Comprehensive Ignore Directories for Multi-Language Support ---
IGNORE_DIRS = {
    '.git', '.svn', '.hg', '.idea', '.vscode', '.vs', '.settings', '.agent',
    '__pycache__', '.venv', 'venv', 'env', '.tox', '.pytest_cache', 'eggs',
    'node_modules', 'bower_components', '.next', '.nuxt', '.svelte-kit', 'out',
    'target', 'build', '.gradle', '.m2', 'out', 'classes',
    'bin', 'obj', 'TestResults',
    'vendor',
    'target',
    '.bundle', 'vendor/bundle',
    'vendor',
    'Pods', 'build', 'DerivedData', 'CMakeFiles',
    'dist', 'build', 'public/build', 'release', 'debug'
}

# --- Comprehensive Ignore Extensions ---
IGNORE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.bmp', '.tiff',
    '.mp4', '.mp3', '.wav', '.mov', '.avi', '.flv', '.ogg',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2', '.jar', '.war', '.ear',
    '.exe', '.dll', '.so', '.dylib', '.class', '.o', '.obj', '.pyc', '.pyo', 
    '.pyd', '.beam', '.a', '.lib',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.sqlite', '.db', '.sqlite3',
    '.min.js', '.min.css', '.map',
    '.DS_Store', 'Thumbs.db'
}

# Default rules to write into a missing .gitignore file
DEFAULT_GITIGNORE_RULES = [
    "node_modules/", "dist/", "build/", ".env", 
    "__pycache__/", ".DS_Store", ".agent/"
]

# --- Database ---
DEFAULT_DB_NAME = "vibecoder.db"