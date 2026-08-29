export function money(cents: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

export function agentLabel(type: string) {
  const labels: Record<string, string> = {
    commercial: "Comercial",
    whatsapp: "Atendimento",
    finance: "Cobrança",
    marketing: "Gestor",
  };
  return labels[type] ?? type;
}

export function formatDate(value: string) {
  return new Date(value).toLocaleDateString("pt-BR");
}

export function formatDateTime(value: string) {
  return new Date(value).toLocaleString("pt-BR");
}
