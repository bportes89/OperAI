"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../lib/api";
import Link from "next/link";

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
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");

  // Carrega tarefas pendentes
  const loadTasks = useCallback(async () => {
    try {
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
        console.log("[WebSocket] Connected");
        
        // Envia identificação (se necessário no futuro)
        // ws.send(JSON.stringify({ type: "auth", token: "..." }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log("[WebSocket] Message received:", message);
          
          // Atualiza lista de tarefas quando receber notificação
          if (message.type === "task_completed" || message.type === "task_failed" || message.type === "task_created") {
            loadTasks();
          }
        } catch (e) {
          console.error("[WebSocket] Error parsing message:", e);
        }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        console.log("[WebSocket] Disconnected, attempting reconnect...");
        
        // Tenta reconectar em 5 segundos
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      };

      ws.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
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

  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case "queued": return "#f59e0b"; // amarelo
      case "running": return "#3b82f6"; // azul
      case "completed": return "#10b981"; // verde
      case "failed": return "#ef4444"; // vermelho
      default: return "#6b7280";
    }
  };

  const getStatusLabel = (status: TaskStatus) => {
    switch (status) {
      case "queued": return "Na fila";
      case "running": return "Executando";
      case "completed": return "Concluída";
      case "failed": return "Falhou";
      default: return status;
    }
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

  return (
    <div className="container" style={{ maxWidth: "1400px", margin: "0 auto", padding: "24px" }}>
      <header style={{ marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span style={{ fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.5px", color: "#6b7280" }}>
              Automação
            </span>
            <h1 style={{ margin: "8px 0", fontSize: "28px", fontWeight: 600 }}>
              Fila de Tarefas
            </h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor:
                    wsStatus === "connected"
                      ? "#10b981"
                      : wsStatus === "connecting"
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              />
              <span style={{ fontSize: "12px", color: "#6b7280" }}>
                {wsStatus === "connected"
                  ? "Tempo real"
                  : wsStatus === "connecting"
                  ? "Conectando..."
                  : "Desconectado"}
              </span>
            </div>
            <Link href="/app" className="secondary">
              Voltar
            </Link>
          </div>
        </div>
      </header>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            color: "#dc2626",
            marginBottom: "16px",
          }}
        >
          {error}
        </div>
      )}

      {success && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "#f0fdf4",
            border: "1px solid #86efac",
            borderRadius: "8px",
            color: "#16a34a",
            marginBottom: "16px",
          }}
        >
          {success}
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              padding: "20px",
              backgroundColor: "#fff",
              borderRadius: "12px",
              border: "1px solid #e5e7eb",
            }}
          >
            <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "8px" }}>Total</div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#111827" }}>{stats.total}</div>
          </div>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#fffbeb",
              borderRadius: "12px",
              border: "1px solid #fcd34d",
            }}
          >
            <div style={{ fontSize: "12px", color: "#92400e", marginBottom: "8px" }}>Na Fila</div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#b45309" }}>{stats.queued}</div>
          </div>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#eff6ff",
              borderRadius: "12px",
              border: "1px solid #93c5fd",
            }}
          >
            <div style={{ fontSize: "12px", color: "#1e40af", marginBottom: "8px" }}>Executando</div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#1d4ed8" }}>{stats.running}</div>
          </div>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#f0fdf4",
              borderRadius: "12px",
              border: "1px solid #86efac",
            }}
          >
            <div style={{ fontSize: "12px", color: "#166534", marginBottom: "8px" }}>Concluídas</div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#15803d" }}>{stats.completed}</div>
          </div>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#fef2f2",
              borderRadius: "12px",
              border: "1px solid #fecaca",
            }}
          >
            <div style={{ fontSize: "12px", color: "#991b1b", marginBottom: "8px" }}>Falhas</div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#b91c1c" }}>{stats.failed}</div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          marginBottom: "24px",
          padding: "16px",
          backgroundColor: "#f9fafb",
          borderRadius: "8px",
        }}
      >
        <button
          onClick={runPendingTasks}
          disabled={executing === "batch"}
          className="primary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
        >
          {executing === "batch" ? (
            <>
              <span className="spinner" style={{ width: "16px", height: "16px" }} />
              Processando...
            </>
          ) : (
            <>
              ▶️ Executar Lote
            </>
          )}
        </button>

        <button
          onClick={loadTasks}
          disabled={loading}
          className="secondary"
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
        >
          {loading ? (
            <>
              <span className="spinner" style={{ width: "16px", height: "16px" }} />
              Atualizando...
            </>
          ) : (
            <>
              🔄 Atualizar
            </>
          )}
        </button>

        <div style={{ marginLeft: "auto", fontSize: "14px", color: "#6b7280" }}>
          Atualização automática a cada 30s
        </div>
      </div>

      {/* Tasks Table */}
      <div
        style={{
          backgroundColor: "#fff",
          borderRadius: "12px",
          border: "1px solid #e5e7eb",
          overflow: "hidden",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ backgroundColor: "#f9fafb" }}>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Tarefa
              </th>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Tipo
              </th>
              <th style={{ padding: "12px 16px", textAlign: "center", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Prioridade
              </th>
              <th style={{ padding: "12px 16px", textAlign: "center", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Status
              </th>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Criada em
              </th>
              <th style={{ padding: "12px 16px", textAlign: "center", fontSize: "12px", fontWeight: 600, color: "#374151", textTransform: "uppercase" }}>
                Ações
              </th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "48px", textAlign: "center", color: "#6b7280" }}>
                  <div style={{ fontSize: "48px", marginBottom: "16px" }}>📭</div>
                  <div style={{ fontSize: "18px", fontWeight: 600, marginBottom: "8px" }}>
                    Nenhuma tarefa pendente
                  </div>
                  <div style={{ fontSize: "14px" }}>
                    Todas as tarefas foram processadas ou a fila está vazia.
                  </div>
                </td>
              </tr>
            ) : (
              tasks.map((task) => (
                <tr key={task.id} style={{ borderTop: "1px solid #e5e7eb" }}>
                  <td style={{ padding: "16px" }}>
                    <div style={{ fontWeight: 600, color: "#111827" }}>{task.title}</div>
                    <div style={{ fontSize: "12px", color: "#6b7280", fontFamily: "monospace" }}>
                      {task.id.slice(0, 8)}...
                    </div>
                  </td>
                  <td style={{ padding: "16px" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "4px 12px",
                        borderRadius: "9999px",
                        fontSize: "12px",
                        fontWeight: 600,
                        backgroundColor: "#f3f4f6",
                        color: "#374151",
                      }}
                    >
                      {getTaskTypeLabel(task.task_type)}
                    </span>
                  </td>
                  <td style={{ padding: "16px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "4px 12px",
                        borderRadius: "9999px",
                        fontSize: "12px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        backgroundColor:
                          task.priority === "high"
                            ? "#fef2f2"
                            : task.priority === "normal"
                            ? "#fffbeb"
                            : "#f0fdf4",
                        color:
                          task.priority === "high"
                            ? "#b91c1c"
                            : task.priority === "normal"
                            ? "#b45309"
                            : "#15803d",
                      }}
                    >
                      {task.priority}
                    </span>
                  </td>
                  <td style={{ padding: "16px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "4px 12px",
                        borderRadius: "9999px",
                        fontSize: "12px",
                        fontWeight: 600,
                        backgroundColor: getStatusColor(task.status) + "20",
                        color: getStatusColor(task.status),
                      }}
                    >
                      {getStatusLabel(task.status)}
                    </span>
                  </td>
                  <td style={{ padding: "16px" }}>
                    <div style={{ fontSize: "14px", color: "#374151" }}>
                      {new Date(task.created_at).toLocaleDateString("pt-BR")}
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280" }}>
                      {new Date(task.created_at).toLocaleTimeString("pt-BR")}
                    </div>
                  </td>
                  <td style={{ padding: "16px", textAlign: "center" }}>
                    <button
                      onClick={() => executeTask(task.id)}
                      disabled={executing === task.id || task.status === "running"}
                      className="primary"
                      style={{
                        padding: "8px 16px",
                        fontSize: "13px",
                        opacity: executing === task.id || task.status === "running" ? 0.5 : 1,
                      }}
                    >
                      {executing === task.id ? (
                        <span className="spinner" style={{ width: "14px", height: "14px" }} />
                      ) : (
                        "▶ Executar"
                      )}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}