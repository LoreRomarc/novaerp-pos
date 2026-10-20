/* Puente seguro entre NovaERP web y el conector instalado en este PC. */
window.NovaERPPrint = (() => {
  const endpoint = "http://127.0.0.1:8765";

  async function request(path, options = {}) {
    const response = await fetch(`${endpoint}${path}`, {
      cache: "no-store",
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "El conector de impresión no respondió.");
    return data;
  }

  async function listarImpresoras() {
    const data = await request("/printers");
    return data.printers || [];
  }

  async function imprimir(payload) {
    if (!payload?.impresora) {
      throw new Error("Seleccione una impresora y guarde la configuración.");
    }
    return request("/print", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  return { listarImpresoras, imprimir };
})();
