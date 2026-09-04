"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";

type TaskStatus = "queued" | "running" | "completed" | "failed";

interface Task {
  id: string;
  task_type: string;
  title: string;
  priority: string;
  status: TaskStatus;
  created_at: string;
  input_data?: Record<string, unknown>;
}

interface TaskStats {
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [wsStatus, setWsStatus] = useState<
    "connecting" | "connected" | "disconnected"
  >("disconnected");

  // Carrega tarefas pendentes
  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const data = await apiJson<{ tasks: Task[]; pagination: { total: number } }>(
        "/api/v1/tasks/pending?limit=50"
      );
      setTasks(data.tasks);
      
      // Calcula estatísticas
      const allTasks = data.tasks;
      setStats({
        total: data.pagination.total,
        queued: allTasks.filter((t) => t.status === "queued").length,
        running: allTasks.filter((t) => t.status === "running").length,
        completed: allTasks.filter((t) => t.status === "completed").length,
        failed: allTasks.filter((t) => t.status === "failed").length,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Executa tarefa específica
  const executeTask = async (taskId: string) => {
    try {
      setExecuting(taskId);
      setError("");
      setSuccess("");
      
      await apiJson(`/api/v1/tasks/${taskId}/execute`, {
        method: "POST",
      });
      
      setSuccess(`Tarefa ${taskId} executada com sucesso!`);
      await loadTasks(); // Recarrega lista
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExecuting(null);
    }
  };

  // Executa lote de tarefas
  const runPendingTasks = async () => {
    try {
      setExecuting("batch");
      setError("");
      setSuccess("");
      
      const result = await apiJson<{ processed: number; results: Array<{ task_id: string; status: string }> }>(
        "/api/v1/tasks/run-pending",
        {
          method: "POST",
        }
      );
      
      const completed = result.results.filter((r) => r.status === "completed").length;
      const failed = result.results.filter((r) => r.status === "failed").length;
      
      setSuccess(`Processadas ${result.processed} tarefas: ${completed} concluídas, ${failed} falhas`);
      await loadTasks();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExecuting(null);
    }
  };

  // WebSocket connection
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connectWebSocket = () => {
      // Usa o mesmo host da API, mas com protocolo ws:// ou wss://
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const baseUrl = apiUrl.replace(/^http/, "ws").replace(/\/api\/v1$/, "") || "ws://localhost:8000";
      const wsUrl = `${baseUrl}/ws`;
      
      setWsStatus("connecting");
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          // Atualiza lista de tarefas quando receber notificação
          if (message.type === "task_completed" || message.type === "task_failed" || message.type === "task_created") {
            loadTasks();
          }
        } catch (e) {
        }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        
        // Tenta reconectar em 5 segundos
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      };

      ws.onerror = (error) => {
        void error;
      };
    };

    // Inicia conexão
    connectWebSocket();

    // Cleanup
    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) {
        ws.close();
      }
    };
  }, [loadTasks]);

  // Carrega tarefas iniciais
  useEffect(() => {
    loadTasks();
    
    // Atualiza a cada 30 segundos
    const interval = setInterval(loadTasks, 30000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  const getStatusLabel = (status: TaskStatus) => {
    switch (status) {
      case "queued": return "Na fila";
      case "running": return "Executando";
      case "completed": return "Concluída";
      case "failed": return "Falhou";
      default: return status;
    }
  };

  const getStatusBadgeClass = (status: TaskStatus) => {
    if (status === "completed") return "finance-status paid";
    if (status === "failed") return "finance-status overdue";
    return "finance-status";
  };

  const getPriorityBadgeClass = (priority: string) => {
    if (priority === "high") return "finance-status overdue";
    if (priority === "low") return "finance-status paid";
    return "finance-status";
  };

  const getTaskTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      "whatsapp.reply": "WhatsApp",
      "finance.follow_up": "Cobrança",
      "marketing.campaign": "Campanha",
      "marketing.handoff": "Lead",
      "marketing.crisis": "Crise",
    };
    return labels[type] || type;
  };

  const wsLabel =
    wsStatus === "connected"
      ? "Tempo real"
      : wsStatus === "connecting"
        ? "Conectando…"
        : "Desconectado";
  const wsBadgeClass =
    wsStatus === "connected"
      ? "online"
      : wsStatus === "connecting"
        ? "finance-status"
        : "finance-status overdue";

  return (
    <>
      <header>
        <div>
          <span>AUTOMAÇÃO</span>
          <h1>Tarefas</h1>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span className={wsBadgeClass}>{wsLabel}</span>
          <button
            type="button"
            className="primary"
            disabled={executing === "batch"}
            onClick={() => void runPendingTasks()}
          >
            {executing === "batch" ? "Processando…" : "Executar lote"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={loading}
            onClick={() => void loadTasks()}
          >
            {loading ? "Atualizando…" : "Atualizar"}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}

      {stats && (
        <div className="metrics" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
          <article>
            <span>Total</span>
            <strong>{stats.total}</strong>
            <small>pendentes</small>
          </article>
          <article>
            <span>Na fila</span>
            <strong>{stats.queued}</strong>
            <small>aguardando</small>
          </article>
          <article>
            <span>Executando</span>
            <strong>{stats.running}</strong>
            <small>em andamento</small>
          </article>
          <article>
            <span>Concluídas</span>
            <strong>{stats.completed}</strong>
            <small>no período</small>
          </article>
          <article>
            <span>Falhas</span>
            <strong>{stats.failed}</strong>
            <small>no período</small>
          </article>
        </div>
      )}

      <article className="panel">
        <div className="panel-title">
          <div>
            <span>FILA</span>
            <h2>Tarefas pendentes</h2>
          </div>
          <span>Atualização automática a cada 30s</span>
        </div>

        {loading && tasks.length === 0 ? (
          <div className="empty">
            <strong>Carregando…</strong>
            <p>Buscando tarefas pendentes.</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="empty">
            <strong>Nenhuma tarefa pendente</strong>
            <p>Todas as tarefas foram processadas ou a fila está vazia.</p>
          </div>
        ) : (
          <div style={{ display: "grid" }}>
            <div
              className="finance-row"
              style={{
                gridTemplateColumns: "1.6fr 120px 120px 140px 170px 150px",
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: 1.2,
                textTransform: "uppercase",
                paddingTop: 10,
                paddingBottom: 10,
                borderBottomWidth: 1,
              }}
            >
              <span>Tarefa</span>
              <span>Tipo</span>
              <span style={{ textAlign: "center" }}>Prioridade</span>
              <span style={{ textAlign: "center" }}>Status</span>
              <span>Criada em</span>
              <span style={{ textAlign: "right" }}>Ações</span>
            </div>

            {tasks.map((task) => (
              <div
                key={task.id}
                className="finance-row"
                style={{ gridTemplateColumns: "1.6fr 120px 120px 140px 170px 150px" }}
              >
                <div>
                  <strong>{task.title}</strong>
                  <small style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}>
                    {task.id.slice(0, 8)}…
                  </small>
                </div>
                <span className="stage">{getTaskTypeLabel(task.task_type)}</span>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <span className={getPriorityBadgeClass(task.priority)}>
                    {task.priority}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <span className={getStatusBadgeClass(task.status)}>
                    {getStatusLabel(task.status)}
                  </span>
                </div>
                <div>
                  <strong>{new Date(task.created_at).toLocaleDateString("pt-BR")}</strong>
                  <small>{new Date(task.created_at).toLocaleTimeString("pt-BR")}</small>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={executing === task.id || task.status === "running"}
                    onClick={() => void executeTask(task.id)}
                  >
                    {executing === task.id ? "Executando…" : "Executar"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </article>
    </>
  );
}
