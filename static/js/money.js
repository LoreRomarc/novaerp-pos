// =========================
// MONEY CORE (SISTEMA ÚNICO)
// =========================

export function parseMoney(value) {
  if (value === null || value === undefined) return 0;

  value = value.toString().trim();

  // elimina todo excepto números
  value = value.replace(/[^0-9]/g, "");

  return Number(value) || 0;
}

export function formatMoney(value) {
  value = Number(value || 0);

  return value.toLocaleString("es-CO", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}