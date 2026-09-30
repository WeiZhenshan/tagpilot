import { apiRequest } from "./api";
export type AgentSkill = {
  name: string;
  display_name: string;
  description: string;
  version: string;
  category: string;
  argument_hint: string;
  user_invocable: boolean;
  disable_model_invocation: boolean;
};
export async function availableSkills(): Promise<AgentSkill[]> {
  const response = await apiRequest<{ data: AgentSkill[] }>("/taglibrary/agent/skills/available");
  return response.data.filter((skill) => skill.user_invocable);
}
export function slashQuery(text: string, caret: number) {
  const match = /(?:^|\s)\/([^\s/]*)$/.exec(text.slice(0, caret));
  return match ? { query: match[1].toLowerCase(), start: caret - match[1].length - 1, end: caret } : null;
}
