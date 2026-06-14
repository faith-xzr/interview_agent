export function consistencyLabel(value: string) {
  if (value === "consistent") return "证据一致";
  if (value === "contradictory") return "存在矛盾";
  return "证据较弱";
}

export function sessionStatusLabel(value: string) {
  if (value === "completed") return "已完成";
  if (value === "ready_for_report") return "待生成报告";
  return "进行中";
}

export function questionSourceLabel(value: string) {
  if (value === "dynamic_followup") return "动态追问";
  if (value === "fallback") return "兜底问题";
  return "面试问题";
}
