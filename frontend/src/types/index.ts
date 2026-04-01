export interface PlanData {
  strategy: string;
  files_to_modify?: string[];
  new_files?: string[];
  commands_to_run?: string[];
  ui_components_to_screenshot?: { route: string; selector: string }[];
}

export interface FileDiff {
  file: string;
  old_content: string;
  new_content: string;
}

export interface Message {
  role: 'bot' | 'user' | 'system';
  type: 'text' | 'error' | 'plan' | 'action';
  content?: string;
  ticketId?: string;
  plan?: PlanData;
  fileDiffs?: FileDiff[];
}

export interface ConnectFormData {
  jira_url: string;
  jira_user: string;
  jira_token: string;
  repo_url: string;
  github_token: string;
  jira_project_key: string;
}

export interface CreateTicketData {
  summary: string;
  description: string;
}