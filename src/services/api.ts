import { 
  AppConfig, 
  AppConfigUpdate, 
  ChatRequest, 
  ChatResponse,
  RagGenerateRequest,
  RagGenerateResponse,
  Tool,
  ToolCreate,
  ToolUpdate,
  LakeraResult,
  DemoPrompt,
  DemoPromptCreate,
  DemoPromptUpdate,
  DemoPromptSearchResponse
} from '../types';

const API_BASE = '/api';

class ApiService {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Config endpoints
  async getConfig(): Promise<AppConfig> {
    return this.request<AppConfig>('/config');
  }

  async updateConfig(config: AppConfigUpdate): Promise<{ message: string }> {
    return this.request<{ message: string }>('/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async exportConfig(): Promise<Blob> {
    const response = await fetch(`${API_BASE}/config/export`);
    if (!response.ok) {
      throw new Error('Export failed');
    }
    return response.blob();
  }

  async importConfig(file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/config/import`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Import failed');
    }

    return response.json();
  }

  // Chat endpoints
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // RAG endpoints
  async uploadFile(file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/rag/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('File upload failed');
    }

    return response.json();
  }

  async generateRagContent(request: RagGenerateRequest): Promise<RagGenerateResponse> {
    return this.request<RagGenerateResponse>('/rag/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async searchRag(query: string): Promise<any> {
    return this.request(`/rag/search?q=${encodeURIComponent(query)}`);
  }

  async getRagSources(): Promise<{ sources: any[] }> {
    return this.request<{ sources: any[] }>('/rag/sources');
  }

  async clearRagContent(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/rag/clear', {
      method: 'DELETE',
    });
  }

  // Tools endpoints
  async getTools(): Promise<Tool[]> {
    return this.request<Tool[]>('/tools');
  }

  async createTool(tool: ToolCreate): Promise<Tool> {
    return this.request<Tool>('/tools', {
      method: 'POST',
      body: JSON.stringify(tool),
    });
  }

  async updateTool(id: number, tool: ToolUpdate): Promise<Tool> {
    return this.request<Tool>(`/tools/${id}`, {
      method: 'PUT',
      body: JSON.stringify(tool),
    });
  }

  async deleteTool(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/tools/${id}`, {
      method: 'DELETE',
    });
  }

  async testTool(id: number, parameters: any): Promise<any> {
    return this.request(`/tools/test/${id}`, {
      method: 'POST',
      body: JSON.stringify(parameters),
    });
  }

  // Lakera endpoints
  async getLastLakeraResult(): Promise<LakeraResult> {
    return this.request<LakeraResult>('/lakera/last');
  }

  async getLastRagScanningResult(): Promise<any> {
    return this.request<any>('/rag/scanning/last');
  }

  async getRagScanningProgress(): Promise<any> {
    return this.request<any>('/rag/scanning/progress');
  }

  // Demo Prompt endpoints
  async getDemoPrompts(category?: string, limit: number = 50): Promise<DemoPrompt[]> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    params.append('limit', limit.toString());
    return this.request<DemoPrompt[]>(`/demo-prompts?${params.toString()}`);
  }

  async searchDemoPrompts(query: string, category?: string, limit: number = 10): Promise<DemoPromptSearchResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (category) params.append('category', category);
    params.append('limit', limit.toString());
    return this.request<DemoPromptSearchResponse>(`/demo-prompts/search?${params.toString()}`);
  }

  async createDemoPrompt(prompt: DemoPromptCreate): Promise<DemoPrompt> {
    return this.request<DemoPrompt>('/demo-prompts', {
      method: 'POST',
      body: JSON.stringify(prompt),
    });
  }

  async updateDemoPrompt(id: number, prompt: DemoPromptUpdate): Promise<DemoPrompt> {
    return this.request<DemoPrompt>(`/demo-prompts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(prompt),
    });
  }

  async deleteDemoPrompt(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/demo-prompts/${id}`, {
      method: 'DELETE',
    });
  }

  async useDemoPrompt(id: number): Promise<{ message: string; usage_count: number }> {
    return this.request<{ message: string; usage_count: number }>(`/demo-prompts/${id}/use`, {
      method: 'POST',
    });
  }

  // Models endpoint
  async getModels(): Promise<{ models: string[] }> {
    return this.request<{ models: string[] }>('/models');
  }
}

export const apiService = new ApiService();

