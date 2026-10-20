/* global qz */
/*
 * Puente de impresión NovaERP ↔ QZ Tray.
 * QZ Tray es un programa de Windows instalado una sola vez por computador;
 * se inicia con la sesión y permite que una web desplegada use el driver local
 * sin abrir el cuadro de impresión del navegador.
 */
window.NovaERPPrint = (() => {
  // Sin un certificado comercial QZ mostrará una única confirmación de
  // confianza por sitio/usuario. La configuración firmada puede añadirse más
  // adelante sin cambiar el flujo del POS.
  let seguridadConfigurada = false;

  async function conectar() {
    if (!window.qz) {
      throw new Error("QZ Tray no está disponible en este navegador.");
    }
    if (!seguridadConfigurada) {
      qz.security.setCertificatePromise((resolve) => resolve());
      seguridadConfigurada = true;
    }
    if (!qz.websocket.isActive()) {
      await qz.websocket.connect({ retries: 2, delay: 0.5 });
    }
  }

  async function listarImpresoras() {
    await conectar();
    const impresoras = await qz.printers.find();
    return Array.isArray(impresoras) ? impresoras.sort((a, b) => a.localeCompare(b, "es")) : [];
  }

  async function imprimir(payload) {
    if (!payload?.impresora) {
      throw new Error("Seleccione una impresora y guarde la configuración.");
    }
    await conectar();
    const ancho = Number(payload.ancho_mm || 80);
    const alto = Number(payload.alto_mm || 250);
    const configuracion = qz.configs.create(payload.impresora, {
      jobName: payload.titulo || "NovaERP - comprobante",
      margins: 0,
      size: { width: ancho, height: alto, units: "mm" },
      scaleContent: true,
    });
    return qz.print(configuracion, [{
      type: "pixel",
      format: "html",
      flavor: "plain",
      data: payload.html,
      options: { pageWidth: ancho, pageHeight: alto },
    }]);
  }

  return { conectar, listarImpresoras, imprimir };
})();
