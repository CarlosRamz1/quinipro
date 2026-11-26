'use strict';
/* QuiniPro · PWA sin frameworks. Rutas con #/... y API en /api. */

const $app = document.getElementById('app');
const $nav = document.getElementById('nav');
const TZ = 'America/Mexico_City';
const S = { token: localStorage.getItem('qp_token'), ctx: {}, fuente: null, reloj: null };

// ------------------------------------------------------------------ utilidades

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ini = (n) => { const p = String(n || '?').trim().split(/\s+/); return ((p[0]?.[0] || '') + (p[1]?.[0] || p[0]?.[1] || '')).toUpperCase(); };
const fmt = new Intl.DateTimeFormat('es-MX', { timeZone: TZ, weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
const cuando = (iso) => fmt.format(new Date(iso)).replace(/\./g, '').replace(',', '');
function faltan(iso) {
  const m = Math.round((new Date(iso) - Date.now()) / 60000);
  if (m <= 0) return 'ya';
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return h < 48 ? `${h} h ${m % 60} min` : `${Math.floor(h / 24)} días`;
}
const resultado = (gl, gv) => (gl > gv ? 'L' : gv > gl ? 'V' : 'E');
const NOMBRE_PICK = { L: 'Local', E: 'Empate', V: 'Visita' };

let temporizadorAviso;
function aviso(msg) {
  const el = document.getElementById('aviso');
  el.textContent = msg; el.classList.add('ver');
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => el.classList.remove('ver'), 3200);
}

async function api(ruta, { metodo = 'GET', datos } = {}) {
  const h = { Accept: 'application/json' };
  if (S.token) h.Authorization = 'Bearer ' + S.token;
  if (datos !== undefined) h['Content-Type'] = 'application/json';
  const r = await fetch('/api' + ruta, { method: metodo, headers: h, body: datos !== undefined ? JSON.stringify(datos) : undefined });
  let j = null;
  try { j = await r.json(); } catch (_) { /* sin cuerpo */ }
  if (!r.ok) {
    const e = new Error(j && typeof j.detail === 'string' ? j.detail : r.status === 422 ? 'Revisa los datos.' : 'Algo salió mal, intenta de nuevo.');
    e.status = r.status;
    throw e;
  }
  return j;
}

function guardarToken(t) { if (t) { S.token = t; localStorage.setItem('qp_token', t); } }

async function copiar(texto, titulo) {
  try {
    if (navigator.share && /Android|iPhone|iPad/i.test(navigator.userAgent)) { await navigator.share({ title: titulo, text: titulo, url: texto }); return; }
    await navigator.clipboard.writeText(texto);
    aviso('Copiado. Pégalo en WhatsApp.');
  } catch (_) { aviso(texto); }
}

// Botones que piden un segundo toque para confirmar (sin ventanas emergentes).
function confirmado(btn) {
  if (btn.dataset.armado) return true;
  btn.dataset.armado = '1';
  const txt = btn.textContent;
  btn.textContent = 'Toca otra vez para confirmar';
  setTimeout(() => { delete btn.dataset.armado; btn.textContent = txt; }, 4000);
  return false;
}

// ------------------------------------------------------------------ instalación en el celular

let promptInstalar = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); promptInstalar = e; });
window.addEventListener('appinstalled', () => { promptInstalar = null; aviso('¡Listo! QuiniPro ya está en tu pantalla de inicio.'); });
const instalada = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
function plataforma() {
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (ios) return /CriOS|FxiOS|EdgiOS|OPiOS|FBAN|FBAV|Instagram|WhatsApp|Line\//.test(ua) ? 'ios-otro' : 'ios';
  if (/Android/.test(ua)) return 'android';
  return 'escritorio';
}
function avisoInstalarVisible() {
  if (instalada() || plataforma() === 'escritorio') return false;
  const hasta = +localStorage.getItem('qp_instalar_despues') || 0;
  return Date.now() > hasta;
}

// Dibujito de un celular con el lugar donde hay que tocar resaltado.
function celular(zona, icono) {
  const pos = { abajo: [60, 196], arribaDer: [94, 30], lista: [60, 118] }[zona];
  return `<svg width="92" height="168" viewBox="0 0 120 220" aria-hidden="true" style="flex:none">
    <rect x="4" y="4" width="112" height="212" rx="18" fill="#12171F" stroke="#2A3340" stroke-width="2"/>
    <rect x="16" y="44" width="88" height="10" rx="5" fill="#1A212B"/><rect x="16" y="62" width="64" height="8" rx="4" fill="#1A212B"/>
    <rect x="16" y="80" width="88" height="22" rx="6" fill="#1A212B"/>
    ${zona === 'lista' ? '<rect x="12" y="104" width="96" height="28" rx="8" fill="#16200C" stroke="#D4FF3A" stroke-width="2"/>' : '<rect x="16" y="108" width="88" height="22" rx="6" fill="#1A212B"/>'}
    <rect x="16" y="136" width="88" height="22" rx="6" fill="#1A212B"/>
    ${zona === 'abajo' ? '<rect x="4" y="180" width="112" height="32" fill="#0E1218"/>' : ''}
    <circle cx="${pos[0]}" cy="${pos[1]}" r="17" fill="#D4FF3A" opacity=".18"/><circle cx="${pos[0]}" cy="${pos[1]}" r="12" fill="#D4FF3A"/>
    <g transform="translate(${pos[0] - 8} ${pos[1] - 8})" fill="none" stroke="#0A0D12" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${icono}</g></svg>`;
}
const GLIFO = {
  compartir: '<path d="M8 1v10M4.5 4.5 8 1l3.5 3.5M3 8v6h10V8"/>',
  agregar: '<rect x="1.5" y="1.5" width="13" height="13" rx="3"/><path d="M8 5v6M5 8h6"/>',
  ok: '<path d="M3 8.5 6.5 12 13 4.5"/>',
  menu: '<circle cx="8" cy="3" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="8" cy="13" r="1.2"/>',
  bajar: '<path d="M8 1v9M4.5 6.5 8 10l3.5-3.5M2 14h12"/>',
};
function pasos(lista) {
  return lista.map(([zona, glifo, titulo, texto], i) => `<section class="tarjeta" style="flex-direction:row;align-items:center;gap:16px">
    ${celular(zona, GLIFO[glifo])}
    <div style="display:flex;flex-direction:column;gap:6px"><span style="font:700 13px 'Space Grotesk',sans-serif;color:var(--lima)">PASO ${i + 1}</span>
      <b style="font-size:16px;line-height:1.3">${titulo}</b><span style="font-size:13px;color:var(--gris);line-height:1.45">${texto}</span></div></section>`).join('');
}

// ------------------------------------------------------------------ íconos

const IC = {
  inicio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  jornada: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
  tabla: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 20V10M12 20V4M18 20v-7"/></svg>',
  admin: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></svg>',
  perfil: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  reloj: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFC53D" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/></svg>',
  candado: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8B97A6" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
  estrella: '<svg width="14" height="14" viewBox="0 0 24 24" fill="#FFC53D" aria-hidden="true"><path d="M12 2l3 6.5 7 .9-5.2 4.8 1.4 7L12 17.8 5.8 21.2l1.4-7L2 9.4l7-.9z"/></svg>',
  estrellaBtn: '<svg width="22" height="22" viewBox="0 0 24 24" stroke-width="2" aria-hidden="true"><path d="M12 2l3 6.5 7 .9-5.2 4.8 1.4 7L12 17.8 5.8 21.2l1.4-7L2 9.4l7-.9z"/></svg>',
  atras: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>',
  lupa: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8B97A6" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M16 16l4 4"/></svg>',
  enlace: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
  mas: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
  flecha: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
};

// ------------------------------------------------------------------ armazón

function pintar(html, { nav = true, mantener = false } = {}) {
  const y = window.scrollY;
  $app.innerHTML = html;
  $app.classList.toggle('sin-nav', !nav);
  $app.onclick = null; $app.oninput = null; $app.onchange = null; $app.onsubmit = null;
  $nav.hidden = !nav;
  if (nav) pintarNav();
  window.scrollTo(0, mantener ? y : 0);  // al refrescar la misma pantalla no se pierde el lugar
}

function pintarNav() {
  const c = S.ctx, h = location.hash;
  const items = [['#/grupos', 'Inicio', IC.inicio, h === '#/grupos']];
  if (c.qid) {
    items.push([`#/q/${c.qid}`, 'Jornada', IC.jornada, h === `#/q/${c.qid}` || h.startsWith(`#/q/${c.qid}/p/`)]);
    items.push([`#/q/${c.qid}/tabla`, 'Tabla', IC.tabla, h === `#/q/${c.qid}/tabla`]);
  }
  if (c.gid && c.admin) items.push([`#/g/${c.gid}/admin`, 'Admin', IC.admin, h.startsWith(`#/g/${c.gid}/`)]);
  items.push(['#/perfil', 'Perfil', IC.perfil, h === '#/perfil' || h === '#/super']);
  document.getElementById('nav-in').innerHTML = items.map(([href, t, ic, act]) =>
    `<a href="${href}"${act ? ' aria-current="page"' : ''}>${ic}${t}</a>`).join('');
}

function cabecera(titulo, sub, { grupo, avatar = true, extra = '' } = {}) {
  return `<header class="cab"><div>
    <div class="marca"><b class="qp">QuiniPro</b>${grupo ? ' · ' + esc(grupo) : ''}</div>
    <h1>${esc(titulo)}</h1>${sub ? `<div class="sub">${sub}</div>` : ''}</div>
    ${extra}${avatar && S.yo ? `<a class="avatar" href="#/perfil" aria-label="Tu perfil">${esc(ini(S.yo.nombre))}</a>` : ''}</header>`;
}

const escudo = (logo, abrev, nombre, grande) =>
  `<span class="escudo${grande ? ' g' : ''}">${logo
    ? `<img src="${esc(logo)}" alt="" loading="lazy" data-a="${esc(abrev || ini(nombre))}" onerror="this.replaceWith(document.createTextNode(this.dataset.a))">`
    : esc(abrev || ini(nombre))}</span>`;

function cerrarFuente() { if (S.fuente) { S.fuente.close(); S.fuente = null; } clearInterval(S.reloj); }

function enVivo(qid, alCambiar) {
  if (!('EventSource' in window) || !S.token) return;
  S.fuente = new EventSource(`/api/quinielas/${qid}/eventos?token=${encodeURIComponent(S.token)}`);
  S.fuente.addEventListener('actualizacion', () => alCambiar());
}

async function asegurarYo() {
  if (!S.yo && S.token) S.yo = (await api('/yo')).usuario;
  return S.yo;
}

// ------------------------------------------------------------------ rutas

const RUTAS = [
  [/^#\/entrar\/([\w-]+)$/, (t) => { guardarToken(t); S.yo = null; location.replace('#/'); }],
  [/^#\/unirse\/([A-Za-z0-9]+)$/, vistaUnirse],
  [/^#\/crear\/([A-Za-z0-9]+)$/, vistaCrear],
  [/^#\/q\/(\d+)$/, vistaJornada],
  [/^#\/q\/(\d+)\/tabla$/, vistaTabla],
  [/^#\/q\/(\d+)\/p\/(\d+)$/, vistaPartido],
  [/^#\/g\/(\d+)\/admin(?:\/(\d+))?$/, vistaAdmin],
  [/^#\/g\/(\d+)\/nueva$/, vistaNueva],
  [/^#\/g\/(\d+)\/miembros$/, vistaMiembros],
  [/^#\/super$/, vistaSuper],
  [/^#\/perfil$/, vistaPerfil],
  [/^#\/grupos$/, () => vistaInicio(true)],
  [/^#\/instalar$/, vistaInstalar],
  [/^(#\/?)?$/, () => vistaInicio(false)],
];

async function navegar() {
  cerrarFuente();
  const h = location.hash || '#/';
  for (const [re, fn] of RUTAS) {
    const m = h.match(re);
    if (!m) continue;
    try { await fn(...m.slice(1)); } catch (e) { vistaError(e); }
    return;
  }
  location.replace('#/');
}
window.addEventListener('hashchange', navegar);

function vistaError(e) {
  if (e.status === 401) {
    localStorage.removeItem('qp_token'); S.token = null; S.yo = null;
    return pintar(`<div class="vacio"><h2>Necesitas entrar de nuevo</h2><p>Abre el enlace de invitación de tu grupo o tu enlace personal.</p></div>`, { nav: false });
  }
  pintar(`<div class="vacio"><h2>Ups</h2><p>${esc(e.message)}</p><p><a href="#/">Volver al inicio</a></p></div>`, { nav: !!S.token });
}

// ------------------------------------------------------------------ inicio y entrada

async function vistaInicio(siempreLista) {
  if (!S.token) {
    return pintar(`<div class="cuerpo" style="padding-top:80px;gap:24px">
      <span class="avatar" style="width:64px;height:64px;border-radius:20px;background:var(--lima);color:var(--fondo);font:italic 800 28px Kanit,sans-serif" aria-hidden="true">QP</span>
      <h1 style="margin:0;font:700 34px/1.1 'Space Grotesk',sans-serif">Bienvenido a <span class="qp">QuiniPro</span></h1>
      <p style="color:var(--suave);line-height:1.6;margin:0">Para entrar necesitas el enlace de invitación de tu grupo. Pídeselo a quien organiza la quiniela.</p></div>`, { nav: false });
  }
  const yo = await api('/yo');
  S.yo = yo.usuario;
  const activas = yo.grupos.flatMap((g) => g.quinielas.filter((q) => q.estado !== 'cerrada'));
  // Al abrir la app: si solo hay una quiniela activa, directo a ella. Desde "Inicio" siempre la lista.
  if (!siempreLista && activas.length === 1) return location.replace(`#/q/${activas[0].id}`);
  S.ctx = {};
  const ROL = { participante: 'Participante', dueno: 'Dueño', coadmin: 'Co-admin' };
  const ESTADO = { abierta: ['Abierta', 'var(--suave)'], en_juego: ['En juego', 'var(--vivo)'], cerrada: ['Terminada', 'var(--gris)'] };
  const tarjetaQ = (q) => {
    const falta = q.estado !== 'cerrada' && q.mis_picks < q.partidos;
    return `<a href="#/q/${q.id}" style="display:flex;align-items:center;gap:12px;min-height:56px;padding:10px 12px;border-radius:14px;background:var(--sup2);color:var(--texto)">
      <span style="flex:1;display:flex;flex-direction:column;gap:2px;min-width:0"><b style="font-size:15px">${esc(q.nombre)}</b>
        <small style="font-size:12px;color:${falta ? 'var(--oro)' : 'var(--gris)'}">${q.estado === 'cerrada' ? 'Ver resultados' : falta ? `Te faltan ${q.partidos - q.mis_picks} de ${q.partidos} picks` : `Completa · ${q.partidos} partidos`}</small></span>
      <span style="font-size:12px;font-weight:600;color:${ESTADO[q.estado][1]}">${ESTADO[q.estado][0]}</span>${IC.flecha}</a>`;
  };
  pintar(cabecera('Tus quinielas', yo.grupos.length > 1 ? `${yo.grupos.length} grupos` : null) + `<div class="cuerpo">
    ${yo.grupos.length ? yo.grupos.map((g) => `<section class="tarjeta">
        <div class="fila-meta"><b style="font:700 18px 'Space Grotesk',sans-serif;color:var(--texto)">${esc(g.nombre)}</b><span>${ROL[g.rol]}</span></div>
        ${g.quinielas.length ? g.quinielas.map(tarjetaQ).join('') : '<span style="font-size:13px;color:var(--gris)">Todavía sin quiniela</span>'}
        ${g.rol !== 'participante' ? `<a href="#/g/${g.id}/admin" style="font-size:13px;font-weight:600;min-height:36px;display:flex;align-items:center">Administrar grupo</a>` : ''}
      </section>`).join('')
      : `<div class="vacio">Aún no estás en ningún grupo. Abre el enlace de invitación que te compartieron.</div>`}
    ${yo.usuario.es_superadmin ? `<a class="boton sec" href="#/super">Panel QuiniPro (súper admin)</a>` : ''}</div>`);
}

async function vistaUnirse(codigo) {
  const inv = await api('/invitacion/' + codigo);
  if (S.token) await asegurarYo().catch(() => null);
  pintar(`<div class="cuerpo" style="padding-top:calc(56px + env(safe-area-inset-top));gap:28px;min-height:90vh">
    <div style="display:flex;align-items:center;gap:12px">
      <span class="avatar" style="width:56px;height:56px;border-radius:18px;background:var(--lima);color:var(--fondo);font:italic 800 26px Kanit,sans-serif" aria-hidden="true">QP</span>
      <span class="qp" style="font-size:30px;color:var(--texto)">QuiniPro</span></div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <span style="font-size:14px;color:var(--gris)">Te invitaron a</span>
      <h1 style="margin:0;font:700 36px/1.05 'Space Grotesk',sans-serif;letter-spacing:-.02em">${esc(inv.grupo)}</h1>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><span class="chip">${inv.participantes} participantes</span>
      ${inv.quiniela ? `<span class="chip">${esc(inv.quiniela.nombre)} · ${inv.quiniela.partidos} partidos</span>` : ''}</div></div>
    <form id="f" style="display:flex;flex-direction:column;gap:16px">
      ${S.yo ? `<p style="margin:0;color:var(--suave)">Entrarás como <b>${esc(S.yo.nombre)}</b>.</p>` : `<div class="campo">
        <label for="nombre">Tu nombre</label>
        <input id="nombre" name="nombre" autocomplete="name" placeholder="Nombre y apellido" required minlength="2" maxlength="40">
        <small>Así aparecerás en la tabla. Sin contraseñas: te reconocemos en este teléfono.</small></div>`}
      <button class="boton" type="submit">Entrar a la quiniela ${IC.flecha}</button></form>
    <a class="aviso verde" href="#/instalar"><span style="font-size:13px;line-height:1.45;color:var(--suave)">Tip: instálala en tu celular para tenerla como app.</span><b style="margin-left:auto;color:var(--lima);font-size:13px;white-space:nowrap">Cómo</b></a></div>`, { nav: false });
  $app.onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button'); btn.disabled = true;
    try {
      const r = await api('/unirse', { metodo: 'POST', datos: { codigo, nombre: e.target.nombre?.value } });
      guardarToken(r.token); S.yo = null;
      location.hash = '#/';
    } catch (err) { aviso(err.message); btn.disabled = false; }
  };
}

async function vistaCrear(codigo) {
  if (S.token) await asegurarYo().catch(() => null);
  pintar(cabecera('Crea tu grupo', 'Quedarás como dueño: podrás armar quinielas e invitar gente.', { avatar: false }) + `
    <form id="f" class="cuerpo">
      <div class="campo"><label for="g">Nombre del grupo</label><input id="g" name="grupo" required minlength="2" maxlength="40" placeholder="Ej. Los de la oficina"></div>
      ${S.yo ? '' : `<div class="campo"><label for="n">Tu nombre</label><input id="n" name="nombre" autocomplete="name" required minlength="2" maxlength="40" placeholder="Nombre y apellido"></div>`}
      <button class="boton" type="submit">Crear grupo</button></form>`, { nav: false });
  $app.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api('/grupos', { metodo: 'POST', datos: { codigo, nombre: e.target.grupo.value, tu_nombre: e.target.nombre?.value } });
      guardarToken(r.token); S.yo = null;
      location.hash = `#/g/${r.id}/admin`;
    } catch (err) { aviso(err.message); }
  };
}

// ------------------------------------------------------------------ jornada (llenar picks)

async function vistaJornada(qid) {
  await asegurarYo();
  S.q = await api('/quinielas/' + qid);
  S.ctx = { qid: +qid, gid: S.q.grupo.id, admin: S.q.es_admin };
  pintarJornada(true);
  $app.onclick = clickJornada;
  enVivo(qid, async () => { S.q = await api('/quinielas/' + qid); pintarJornada(); });
  // Revisa cada 30 s si algún partido llegó a su pitazo, para bloquearlo en pantalla.
  S.reloj = setInterval(async () => {
    if (S.q.partidos.some((p) => p.editable && new Date(p.inicio_utc) <= new Date())) S.q = await api('/quinielas/' + qid);
    pintarJornada();
  }, 30000);
}

function metaPartido(p) {
  if (p.anulado) return `<span>Anulado</span>`;
  if (p.estado === 'en_juego') return `<span class="envivo">EN VIVO ${esc(p.minuto || '')}</span>`;
  if (p.estado === 'final') return `<span>Final</span>`;
  return `<span>${cuando(p.inicio_utc)}</span>`;
}

function estadoPick(p, qid) {
  const tu = p.mi_pick ? `Tu pick: <b>${NOMBRE_PICK[p.mi_pick]}</b>` : 'No pusiste pick';
  if (p.anulado) return `<div class="cerrado">${IC.candado}<span>Anulado para todos</span><span></span></div>`;
  let txt = '', bien = false;
  if (p.goles_local_90 != null && p.mi_pick && (p.estado === 'en_juego' || p.estado === 'final')) {
    bien = resultado(p.goles_local_90, p.goles_visitante_90) === p.mi_pick;
    txt = p.estado === 'final' ? (bien ? ' · acertaste' : ' · fallaste') : (bien ? ' · vas acertando' : ' · vas fallando');
  }
  return `<a class="cerrado${bien ? ' bien' : ''}" href="#/q/${qid}/p/${p.id}"><span style="display:flex;align-items:center;gap:8px">${IC.candado}${tu}${txt}</span><span class="ver">Ver picks</span></a>`;
}

function botonesLEV(p) {
  return `<div class="lev" role="group" aria-label="Tu pick para ${esc(p.local)} vs ${esc(p.visitante)}">
    ${['L', 'E', 'V'].map((v) => `<button type="button" data-pick="${v}" data-pid="${p.id}" aria-pressed="${p.mi_pick === v}">${NOMBRE_PICK[v]}</button>`).join('')}</div>`;
}

function pintarJornada(arriba) {
  const q = S.q;
  const ligas = [...new Set(q.partidos.map((p) => p.competicion_nombre))].join(' · ');
  const est = q.partidos.find((p) => p.es_estelar);
  const resto = q.partidos.filter((p) => !p.es_estelar);
  const sig = q.partidos.filter((p) => p.editable).sort((a, b) => a.inicio_utc.localeCompare(b.inicio_utc))[0];
  const llenos = q.partidos.filter((p) => p.mi_pick).length;
  const pct = Math.round((llenos / Math.max(1, q.partidos.length)) * 100);
  const d = q.mi_desempate || { goles_local: 0, goles_visitante: 0 };
  const completa = q.estado !== 'cerrada' && llenos === q.partidos.length && q.partidos.some((p) => p.editable)
    ? `<section class="aviso verde" style="border-color:var(--lima-borde);background:var(--lima-osc);flex-wrap:wrap">
        <div style="display:flex;flex-direction:column;gap:2px;flex:1;min-width:180px"><b style="color:var(--lima)">¡Quiniela completa!</b>
          <span style="color:#B5C98A">Ya quedó guardada. Puedes salir; si cambias de opinión, edítala antes del pitazo.</span></div>
        <a class="boton sec" href="#/q/${q.id}/tabla" style="width:auto;min-height:40px">Ver tabla</a></section>` : '';

  let banner = '';
  if (q.estado === 'cerrada') banner = `<a class="aviso verde" href="#/q/${q.id}/tabla"><b>Quiniela terminada</b><span style="margin-left:auto;color:var(--lima)">Ver tabla</span></a>`;
  else if (sig) banner = `<div class="aviso">${IC.reloj}<div style="display:flex;flex-direction:column;gap:2px"><b>${esc(sig.local)} vs ${esc(sig.visitante)} cierra en ${faltan(sig.inicio_utc)}</b><span>Cada partido se bloquea a su pitazo inicial</span></div></div>`;

  const estelarHTML = est ? `<section class="tarjeta estelar" aria-label="Partido estelar">
      <div class="fila-meta"><span class="etiqueta-oro">${IC.estrella} PARTIDO ESTELAR · DESEMPATE</span>${metaPartido(est)}</div>
      <div class="estelar-eqs">
        <div class="lado">${escudo(est.local_logo, est.local_abrev, est.local, true)}<span class="nom">${esc(est.local)}</span>
          ${q.desempate_editable ? `<div class="stepper"><button type="button" data-gol="l-" aria-label="Menos goles ${esc(est.local)}">−</button><span class="n">${d.goles_local}</span><button type="button" data-gol="l+" aria-label="Más goles ${esc(est.local)}">+</button></div>` : `<span class="n" style="font:700 28px 'Space Grotesk',sans-serif">${est.goles_local ?? '–'}</span>`}</div>
        <span class="vs">${q.desempate_editable ? 'vs' : '–'}</span>
        <div class="lado">${escudo(est.visitante_logo, est.visitante_abrev, est.visitante, true)}<span class="nom">${esc(est.visitante)}</span>
          ${q.desempate_editable ? `<div class="stepper"><button type="button" data-gol="v-" aria-label="Menos goles ${esc(est.visitante)}">−</button><span class="n">${d.goles_visitante}</span><button type="button" data-gol="v+" aria-label="Más goles ${esc(est.visitante)}">+</button></div>` : `<span class="n" style="font:700 28px 'Space Grotesk',sans-serif">${est.goles_visitante ?? '–'}</span>`}</div>
      </div>
      ${est.editable ? botonesLEV(est) : estadoPick(est, q.id)}
      <p class="nota">${q.desempate_editable ? 'Si empatas en puntos, gana quien atine este marcador' : q.mi_desempate ? `Tu marcador: ${q.mi_desempate.goles_local} - ${q.mi_desempate.goles_visitante}` : 'No pusiste marcador de desempate'}</p>
    </section>` : '';

  const tarjetas = resto.map((p) => `<article class="tarjeta">
      <div class="fila-meta"><span>${esc(p.competicion_nombre)}</span>${metaPartido(p)}</div>
      <div class="equipos">
        <div class="eq">${escudo(p.local_logo, p.local_abrev, p.local)}<span class="nom">${esc(p.local)}</span></div>
        <span class="centro${p.goles_local != null ? ' marcador' : ''}">${p.goles_local != null ? `${p.goles_local} - ${p.goles_visitante}` : 'vs'}</span>
        <div class="eq der"><span class="nom">${esc(p.visitante)}</span>${escudo(p.visitante_logo, p.visitante_abrev, p.visitante)}</div>
      </div>
      ${p.editable ? botonesLEV(p) : estadoPick(p, q.id)}</article>`).join('');

  const instalar = avisoInstalarVisible() ? `<section class="tarjeta" style="border-color:var(--lima-borde);background:var(--lima-osc)">
      <div style="display:flex;align-items:center;gap:12px">
        <span class="avatar" style="width:44px;height:44px;border-radius:14px;background:var(--lima);color:var(--fondo);font:italic 800 18px Kanit,sans-serif" aria-hidden="true">QP</span>
        <div style="display:flex;flex-direction:column;gap:2px"><b style="font-size:15px">Instala QuiniPro en tu celular</b>
          <span style="font-size:12px;color:#B5C98A">Ábrela como app, sin buscar el enlace cada vez.</span></div></div>
      <div class="botones"><a class="boton" href="#/instalar" style="min-height:44px">Cómo instalar</a>
        <button class="boton sec" type="button" data-acc="instalar-despues" style="min-height:44px">Ahora no</button></div></section>` : '';

  pintar(cabecera(q.nombre, esc(ligas), { grupo: q.grupo.nombre }) + `<div class="cuerpo">
    ${instalar}${banner}
    <div class="progreso"><div class="t"><span style="color:var(--gris)">Tu quiniela</span><b>${llenos} de ${q.partidos.length} llenos</b></div>
      <div class="barra"><div style="width:${pct}%"></div></div></div>
    ${completa}${estelarHTML}${tarjetas}
    <a class="boton" href="#/grupos" style="margin-top:6px">${llenos === q.partidos.length || q.estado === 'cerrada' ? 'Listo' : 'Listo por ahora'}</a>
    <p class="nota">Tus picks se guardan solos al tocarlos. Puedes cambiarlos hasta el pitazo de cada partido.</p></div>`, { mantener: !arriba });
  $app.onclick = clickJornada;
}

let tDesempate;
async function clickJornada(e) {
  const b = e.target.closest('button');
  if (!b) return;
  const q = S.q;
  if (b.dataset.acc === 'instalar-despues') {
    localStorage.setItem('qp_instalar_despues', Date.now() + 7 * 864e5);
    return pintarJornada();
  }
  if (b.dataset.pick) {
    const p = q.partidos.find((x) => x.id === +b.dataset.pid);
    if (!p || !p.editable) return;
    const nuevo = p.mi_pick === b.dataset.pick ? null : b.dataset.pick;
    const antes = p.mi_pick;
    p.mi_pick = nuevo; pintarJornada();
    try { await api(`/quinielas/${q.id}/picks`, { metodo: 'PUT', datos: { partido_id: p.id, pick: nuevo } }); }
    catch (err) { p.mi_pick = antes; aviso(err.message); S.q = await api('/quinielas/' + q.id); pintarJornada(); }
  } else if (b.dataset.gol) {
    const d = q.mi_desempate || (q.mi_desempate = { goles_local: 0, goles_visitante: 0 });
    const k = b.dataset.gol[0] === 'l' ? 'goles_local' : 'goles_visitante';
    d[k] = Math.max(0, Math.min(20, d[k] + (b.dataset.gol[1] === '+' ? 1 : -1)));
    pintarJornada();
    clearTimeout(tDesempate);
    tDesempate = setTimeout(async () => {
      try { await api(`/quinielas/${q.id}/desempate`, { metodo: 'PUT', datos: d }); }
      catch (err) { aviso(err.message); S.q = await api('/quinielas/' + q.id); pintarJornada(); }
    }, 500);
  }
}

// ------------------------------------------------------------------ tabla

async function contextoQuiniela(qid) {
  if (S.ctx.qid !== +qid) {
    const q = await api('/quinielas/' + qid);
    S.ctx = { qid: +qid, gid: q.grupo.id, admin: q.es_admin, grupo: q.grupo.nombre };
  } else if (!S.ctx.grupo && S.q) S.ctx.grupo = S.q.grupo.nombre;
}

function filaPos(f) {
  const ant = f.posicion_anterior, d = ant ? ant - f.posicion : 0;
  const mov = d > 0 ? `<span class="m sube" aria-label="Subió ${d}">▲${d}</span>` : d < 0 ? `<span class="m baja" aria-label="Bajó ${-d}">▼${-d}</span>` : `<span class="m igual" aria-label="Sin cambio">–</span>`;
  const sub = f.exacto_estelar ? 'Marcador exacto del estelar' : f.distancia != null ? `A ${f.distancia} gol${f.distancia === 1 ? '' : 'es'} del estelar` : '';
  return `<li class="pos-fila${f.es_yo ? ' yo' : ''}" data-nombre="${esc(f.nombre.toLowerCase())}">
    <span class="p">${f.posicion}°</span>${mov}<span class="avatar ch">${esc(ini(f.nombre))}</span>
    <span class="n"><b>${f.es_yo ? 'Tú' : esc(f.nombre)}</b>${sub ? `<small>${sub}</small>` : ''}</span><span class="pt">${f.puntos}</span></li>`;
}

async function vistaTabla(qid) {
  await asegurarYo();
  await contextoQuiniela(qid);
  const pintarTabla = async (arriba) => {
    const t = await api(`/quinielas/${qid}/tabla`);
    const y = window.scrollY;
    const f = t.filas, yo = f.find((x) => x.es_yo);
    const podio = f.length >= 3 ? `<section class="podio" aria-label="Podio">
        ${[f[1], f[0], f[2]].map((x, i) => `<div class="${i === 1 ? 'uno' : ''}"><span class="avatar ch" style="${i === 1 ? 'width:52px;height:52px;border:2px solid var(--lima);color:var(--texto)' : 'width:44px;height:44px'}">${esc(ini(x.nombre))}</span>
          <span class="nom">${x.es_yo ? 'Tú' : esc(x.nombre.split(' ')[0])}</span><span class="pts">${x.puntos}</span><span class="pos">${x.posicion}°</span></div>`).join('')}</section>` : '';
    const lista = f.length >= 3 ? f.slice(3) : f;
    const estado = t.quiniela.estado === 'cerrada' ? 'final' : 'provisional';
    pintar(cabecera('Tabla', `${f.length} participantes · ${t.terminados} de ${t.total} terminados · ${estado}`,
      { grupo: S.ctx.grupo, avatar: false, extra: t.en_juego ? `<span class="envivo" style="margin-top:28px">${t.en_juego} EN VIVO</span>` : '' }) + `
      <div class="cuerpo" style="padding-bottom:${yo ? 80 : 0}px">${podio}
        ${f.length > 8 ? `<div class="buscar">${IC.lupa}<label class="oculto" for="b">Buscar participante</label><input id="b" type="search" placeholder="Buscar entre ${f.length}"></div>` : ''}
        <ol class="lista" id="lista" aria-label="Posiciones">${lista.map(filaPos).join('')}</ol>
        <p class="nota">Empate en puntos: desempata el marcador del partido estelar.</p></div>
      ${yo ? `<a class="mi-lugar" href="#/q/${qid}" aria-label="Tu lugar">${filaPos(yo).replace('<li', '<div').replace('</li>', '</div>')}</a>` : ''}`);
    if (!arriba) window.scrollTo(0, y);
    $app.oninput = (e) => {
      if (e.target.id !== 'b') return;
      const v = e.target.value.trim().toLowerCase();
      $app.querySelectorAll('#lista li').forEach((li) => { li.hidden = v && !li.dataset.nombre.includes(v); });
    };
  };
  await pintarTabla(true);
  enVivo(qid, () => pintarTabla());
}

// ------------------------------------------------------------------ partido (picks revelados)

async function vistaPartido(qid, pid) {
  await asegurarYo();
  await contextoQuiniela(qid);
  const pintarP = async () => {
    const p = await api(`/quinielas/${qid}/partidos/${pid}`);
    const total = p.revelado ? p.picks.length : 0;
    const pct = (n) => (total ? Math.round((n / total) * 100) : 0);
    const estado = p.estado === 'en_juego' ? `<span class="envivo">EN VIVO · ${esc(p.minuto || '')}</span>` : p.estado === 'final' ? '<span style="font-size:12px;color:var(--gris)">FINAL</span>' : `<span style="font-size:12px;color:var(--gris)">${cuando(p.inicio_utc)}</span>`;
    let mio = p.mi_pick ? `Tu pick: <b>${NOMBRE_PICK[p.mi_pick]}</b>` : 'No pusiste pick';
    let bien = false;
    if (p.mi_pick && p.goles_local_90 != null) {
      bien = resultado(p.goles_local_90, p.goles_visitante_90) === p.mi_pick;
      mio += `<span style="margin-left:auto;font-weight:600;color:${bien ? 'var(--lima)' : 'var(--gris)'}">${p.estado === 'final' ? (bien ? 'Acertaste' : 'Fallaste') : bien ? 'Vas acertando' : 'Vas fallando'}</span>`;
    }
    pintar(`<div style="padding:calc(12px + env(safe-area-inset-top)) 12px 0"><a href="#/q/${qid}" aria-label="Volver a la jornada" style="width:44px;height:44px;display:flex;align-items:center;justify-content:center;color:var(--texto)">${IC.atras}</a></div>
      <section style="padding:0 20px 18px;display:flex;flex-direction:column;align-items:center;gap:14px">${estado}
        <div class="marcador-g"><div class="lado">${escudo(p.local_logo, p.local_abrev, p.local, true)}${esc(p.local)}</div>
          <span class="num">${p.goles_local != null ? `${p.goles_local} – ${p.goles_visitante}` : 'vs'}</span>
          <div class="lado">${escudo(p.visitante_logo, p.visitante_abrev, p.visitante, true)}${esc(p.visitante)}</div></div>
        <span style="font-size:12px;color:var(--gris)">${esc(p.competicion_nombre)} · cuenta el resultado a los 90'${p.es_estelar ? ' · partido estelar' : ''}</span></section>
      <div class="cuerpo">
        <div class="cerrado${bien ? ' bien' : ''}" style="min-height:52px">${mio}</div>
        ${!p.revelado ? `<div class="aviso verde"><span style="font-size:14px;color:var(--suave);line-height:1.5">Los picks de los demás se revelan al pitazo inicial. Antes nadie puede verlos, ni los admins.</span></div>` : `
        <section class="tarjeta" aria-label="Cómo votó el grupo"><div class="fila-meta"><b style="font-size:14px;color:var(--texto)">Cómo votó el grupo</b><span>${total} participantes</span></div>
          ${[['L', 'Local', 'var(--lima)'], ['E', 'Empate', '#7C8796'], ['V', 'Visita', '#4A5462']].map(([k, t, c]) => `<div class="voto">
            <div class="t"><b style="color:${k === 'L' ? 'var(--lima)' : 'var(--texto)'}">${t}</b><span style="color:var(--suave)"><b style="font-family:'Space Grotesk',sans-serif">${pct(p.conteo[k])}%</b> · ${p.conteo[k]}</span></div>
            <div class="b"><div style="width:${pct(p.conteo[k])}%;background:${c}"></div></div></div>`).join('')}
          ${p.sin_pick ? `<span style="font-size:12px;color:var(--gris)">${p.sin_pick} sin pick</span>` : ''}</section>
        ${total > 8 ? `<div class="buscar">${IC.lupa}<label class="oculto" for="b">Buscar a alguien</label><input id="b" type="search" placeholder="Buscar a alguien"></div>` : ''}
        <div class="rejilla" id="gente">${p.picks.map((x) => `<div class="persona" data-nombre="${esc(x.nombre.toLowerCase())}"><span class="avatar ch" style="width:30px;height:30px;font-size:11px">${esc(ini(x.nombre))}</span>
          <span class="nom">${x.usuario_id === S.yo.id ? 'Tú' : esc(x.nombre)}</span><span class="pk${x.pick && p.goles_local_90 != null && resultado(p.goles_local_90, p.goles_visitante_90) === x.pick ? ' si' : ''}">${x.pick || '—'}</span></div>`).join('')}</div>`}
      </div>`);
    $app.oninput = (e) => {
      if (e.target.id !== 'b') return;
      const v = e.target.value.trim().toLowerCase();
      $app.querySelectorAll('#gente .persona').forEach((el) => { el.hidden = v && !el.dataset.nombre.includes(v); });
    };
  };
  await pintarP();
  enVivo(qid, pintarP);
}

// ------------------------------------------------------------------ admin del grupo

async function vistaAdmin(gid, qidSel) {
  await asegurarYo();
  const g = await api('/grupos/' + gid);
  if (!g.es_admin) return location.replace('#/');
  const q = g.quinielas.find((x) => x.id === +qidSel) || g.quinielas.find((x) => x.estado !== 'cerrada') || g.quinielas[0];
  const puedeBorrar = g.rol === 'dueno' || S.yo.es_superadmin;
  S.ctx = { qid: q ? q.id : null, gid: +gid, admin: true, grupo: g.nombre };
  let pagos = q ? await api(`/quinielas/${q.id}/pagos`) : [];
  let filtro = pagos.some((p) => !p.pagado) ? 'pend' : 'todos', busca = '';
  const invitacion = `${location.origin}/#/unirse/${g.codigo_invitacion}`;
  let primeraA = true;

  const pintarA = () => {
    const nPag = pagos.filter((p) => p.pagado).length, nPend = pagos.length - nPag;
    const vis = pagos.filter((p) => (filtro === 'todos' || (filtro === 'pend' ? !p.pagado : p.pagado)) && (!busca || p.nombre.toLowerCase().includes(busca)));
    const estadoQ = q ? { abierta: ['Abierta', 'var(--sup2)', 'var(--suave)'], en_juego: ['En juego', '#2A1A12', '#FF9A70'], cerrada: ['Terminada', 'var(--lima-osc)', 'var(--lima)'] }[q.estado] : null;
    pintar(cabecera('Admin', null, { grupo: g.nombre, avatar: false }) + `<div class="cuerpo">
      <section class="tarjeta" style="padding:16px">
        ${q ? `<div class="fila-meta"><span style="font-weight:600;letter-spacing:.04em">QUINIELA ACTUAL</span><span style="padding:4px 10px;border-radius:999px;font-weight:600;background:${estadoQ[1]};color:${estadoQ[2]}">${estadoQ[0]}</span></div>
          <a href="#/q/${q.id}" style="font:700 20px 'Space Grotesk',sans-serif;color:var(--texto)">${esc(q.nombre)}</a>
          <span style="font-size:13px;color:var(--gris)">${q.partidos} partidos · ${pagos.length} participantes</span>`
        : `<b style="font:700 20px 'Space Grotesk',sans-serif">Todavía no hay quinielas</b><span style="font-size:13px;color:var(--gris)">Arma la primera e invita a tu grupo.</span>`}
        <div class="botones"><button class="boton sec" data-acc="invitar" type="button">${IC.enlace}Copiar invitación</button>
          <a class="boton" href="#/g/${gid}/nueva">${IC.mas}Armar ${q ? 'siguiente' : 'quiniela'}</a></div>
      </section>
      ${g.quinielas.length > 1 ? `<span class="titulo-sec">Quinielas del grupo</span><div style="display:flex;gap:8px;flex-wrap:wrap">
        ${g.quinielas.map((x) => `<a class="chip" href="#/g/${gid}/admin/${x.id}" style="min-height:40px;display:inline-flex;align-items:center;border:1px solid ${x.id === q.id ? 'var(--lima)' : 'var(--linea2)'};color:${x.id === q.id ? 'var(--lima)' : 'var(--suave)'}">${esc(x.nombre)}${x.estado === 'cerrada' ? ' · terminada' : ''}</a>`).join('')}</div>` : ''}
      <div class="botones"><a class="boton sec" href="#/g/${gid}/miembros">Miembros y roles (${g.miembros})</a>
        ${S.yo.es_superadmin ? `<a class="boton sec" href="#/super">Panel súper admin</a>` : ''}</div>
      ${q ? `<section aria-label="Pagos" style="display:flex;flex-direction:column;gap:10px">
        <div style="display:flex;justify-content:space-between;align-items:flex-end"><div style="display:flex;flex-direction:column;gap:2px">
          <span class="titulo-sec" style="margin:0">Quién ya pagó</span><span style="font-size:12px;color:var(--gris)">${q.cuota_texto ? `Cuota acordada: ${esc(q.cuota_texto)} · ` : ''}la app no maneja dinero</span></div>
          <span style="font:700 18px 'Space Grotesk',sans-serif">${nPag}<span style="color:var(--tenue)"> / ${pagos.length}</span></span></div>
        <div class="barra"><div style="width:${pagos.length ? Math.round((nPag / pagos.length) * 100) : 0}%"></div></div>
        ${pagos.length > 8 ? `<div class="buscar">${IC.lupa}<label class="oculto" for="b">Buscar participante</label><input id="b" type="search" placeholder="Buscar participante" value="${esc(busca)}"></div>` : ''}
        <div class="seg" role="group" aria-label="Filtrar">${[['pend', `Pendientes ${nPend}`], ['pag', `Pagados ${nPag}`], ['todos', `Todos ${pagos.length}`]].map(([k, t]) => `<button type="button" data-filtro="${k}" aria-pressed="${filtro === k}">${t}</button>`).join('')}</div>
        <ul class="lista">${vis.map((p) => `<li><span class="avatar ch" style="width:32px;height:32px">${esc(ini(p.nombre))}</span><span class="nom">${esc(p.nombre)}</span>
          <span style="font-size:12px;color:${p.pagado ? 'var(--lima)' : 'var(--pend)'}">${p.pagado ? 'Pagado' : 'Pendiente'}</span>
          <button class="switch" type="button" data-pago="${p.usuario_id}" aria-pressed="${!!p.pagado}" aria-label="${p.pagado ? 'Marcar pendiente a ' : 'Marcar pagado a '}${esc(p.nombre)}"><span></span></button></li>`).join('') || '<li><span class="nom" style="color:var(--gris)">Nadie en esta lista</span></li>'}</ul>
        ${filtro === 'pend' && nPend > 1 ? `<button class="boton borde" type="button" data-acc="todos">Marcar los ${nPend} como pagados</button>` : ''}
      </section>` : ''}
      <button class="boton sec" type="button" data-acc="regenerar" style="margin-top:8px">Cambiar enlace de invitación</button>
      <p class="nota">Si cambias el enlace, el anterior deja de funcionar (útil si se compartió de más).</p>
      ${puedeBorrar ? `<span class="titulo-sec" style="margin-top:12px">Zona de borrado</span>
        ${q ? `<button class="boton sec" type="button" data-acc="borrar-q" style="color:var(--baja)">Borrar la quiniela “${esc(q.nombre)}”</button>` : ''}
        <button class="boton sec" type="button" data-acc="borrar-g" style="color:var(--baja)">Borrar el grupo completo</button>
        <p class="nota">Borrar no se puede deshacer: se pierden picks, tablas y pagos.</p>` : ''}</div>`, { mantener: !primeraA });
    primeraA = false;
    const b = document.getElementById('b');
    if (b && busca) { b.focus(); b.setSelectionRange(busca.length, busca.length); }
    $app.onclick = clickA;
    $app.oninput = (e) => { if (e.target.id === 'b') { busca = e.target.value.trim().toLowerCase(); pintarA(); } };
  };

  const clickA = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.filtro) { filtro = b.dataset.filtro; pintarA(); }
      else if (b.dataset.pago) {
        const p = pagos.find((x) => x.usuario_id === +b.dataset.pago);
        p.pagado = !p.pagado; pintarA();
        await api(`/quinielas/${q.id}/pagos/${p.usuario_id}`, { metodo: 'PUT', datos: { pagado: !!p.pagado } });
      } else if (b.dataset.acc === 'todos') {
        await api(`/quinielas/${q.id}/pagos`, { metodo: 'PUT', datos: { pagado: true } });
        pagos = await api(`/quinielas/${q.id}/pagos`); filtro = 'todos'; pintarA();
      } else if (b.dataset.acc === 'invitar') {
        await copiar(invitacion, `Únete a ${g.nombre} en QuiniPro`);
      } else if (b.dataset.acc === 'borrar-q') {
        if (!confirmado(b)) return;
        await api(`/quinielas/${q.id}`, { metodo: 'DELETE' });
        aviso('Quiniela borrada.'); location.hash = `#/g/${gid}/admin`; if (!qidSel) vistaAdmin(gid);
      } else if (b.dataset.acc === 'borrar-g') {
        if (!confirmado(b)) return;
        await api(`/grupos/${gid}`, { metodo: 'DELETE' });
        aviso('Grupo borrado.'); location.hash = '#/grupos';
      } else if (b.dataset.acc === 'regenerar') {
        if (!confirmado(b)) return;
        const r = await api(`/grupos/${gid}/invitacion`, { metodo: 'POST' });
        g.codigo_invitacion = r.codigo_invitacion;
        aviso('Listo: el enlace anterior ya no funciona.');
        vistaAdmin(gid);
      }
    } catch (err) { aviso(err.message); pagos = q ? await api(`/quinielas/${q.id}/pagos`) : []; pintarA(); }
  };
  pintarA();
}

// ------------------------------------------------------------------ armar quiniela

async function vistaNueva(gid) {
  await asegurarYo();
  const [g, comps, partidos] = await Promise.all([api('/grupos/' + gid), api('/competiciones'), api('/partidos?dias=10')]);
  if (!g.es_admin) return location.replace('#/');
  S.ctx = { qid: g.quinielas[0]?.id, gid: +gid, admin: true, grupo: g.nombre };
  const activas = comps.filter((c) => partidos.some((p) => p.competicion === c.codigo));
  const elegidas = new Set(activas.slice(0, 3).map((c) => c.codigo));
  const sel = new Set();
  let estelar = null;
  const hoy = new Intl.DateTimeFormat('es-MX', { timeZone: TZ, day: '2-digit', month: '2-digit' }).format(new Date());
  let nombre = `Jornada ${hoy}`, cuota = '';
  let primera = true;

  const pintarN = () => {
    const vis = partidos.filter((p) => elegidas.has(p.competicion));
    const porLiga = {};
    vis.forEach((p) => { (porLiga[p.competicion_nombre] ||= []).push(p); });
    const est = partidos.find((p) => p.id === estelar);
    pintar(cabecera('Armar quiniela', 'Elige partidos de una o varias ligas y marca el estelar con la estrella.', { grupo: g.nombre, avatar: false }) + `<div class="cuerpo">
      <div class="campo"><label for="nom">Nombre</label><input id="nom" maxlength="60" value="${esc(nombre)}"></div>
      <div class="campo"><label for="cuota">Cuota (opcional, solo informativa)</label><input id="cuota" maxlength="30" placeholder="Ej. $50" value="${esc(cuota)}"></div>
      <span class="titulo-sec">Ligas con partidos en los próximos 10 días</span>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${activas.map((c) => `<button type="button" class="chip" data-liga="${esc(c.codigo)}" aria-pressed="${elegidas.has(c.codigo)}" style="border:1px solid ${elegidas.has(c.codigo) ? 'var(--lima)' : 'var(--linea2)'};color:${elegidas.has(c.codigo) ? 'var(--lima)' : 'var(--suave)'};min-height:40px;cursor:pointer">${esc(c.nombre)}</button>`).join('') || '<span class="nota">No hay partidos próximos. El robot los carga automáticamente.</span>'}</div>
      ${Object.entries(porLiga).map(([liga, ps]) => `<span class="titulo-sec">${esc(liga)}</span>${ps.map((p) => `
        <label class="check"><input type="checkbox" data-sel="${p.id}" ${sel.has(p.id) ? 'checked' : ''}>
          <span class="info"><b>${esc(p.local)} vs ${esc(p.visitante)}</b><small>${cuando(p.inicio_utc)}</small></span>
          <button type="button" class="estrella" data-est="${p.id}" aria-pressed="${estelar === p.id}" aria-label="Hacer estelar ${esc(p.local)} vs ${esc(p.visitante)}">${IC.estrellaBtn}</button></label>`).join('')}`).join('')}
      <div style="position:sticky;bottom:calc(76px + env(safe-area-inset-bottom));background:var(--fondo);padding:10px 0;display:flex;flex-direction:column;gap:8px">
        <span style="font-size:13px;color:var(--gris)">${sel.size} partido${sel.size === 1 ? '' : 's'} · estelar: ${est ? esc(`${est.local} vs ${est.visitante}`) : '<b style="color:var(--oro)">toca la estrella de uno</b>'}</span>
        <button class="boton" type="button" data-acc="crear" ${sel.size && est ? '' : 'disabled'}>Crear quiniela</button></div></div>`, { mantener: !primera });
    primera = false;
    $app.onclick = clickN; $app.onchange = cambioN; $app.oninput = (e) => { if (e.target.id === 'nom') nombre = e.target.value; if (e.target.id === 'cuota') cuota = e.target.value; };
  };
  const cambioN = (e) => {
    const id = +e.target.dataset.sel;
    if (!id) return;
    if (e.target.checked) sel.add(id); else { sel.delete(id); if (estelar === id) estelar = null; }
    pintarN();
  };
  const clickN = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.liga) { elegidas.has(b.dataset.liga) ? elegidas.delete(b.dataset.liga) : elegidas.add(b.dataset.liga); pintarN(); }
    else if (b.dataset.est) { e.preventDefault(); const id = +b.dataset.est; estelar = estelar === id ? null : id; if (estelar) sel.add(id); pintarN(); }
    else if (b.dataset.acc === 'crear') {
      b.disabled = true;
      try {
        const r = await api(`/grupos/${gid}/quinielas`, { metodo: 'POST', datos: { nombre: nombre.trim(), partidos: [...sel], estelar, cuota_texto: cuota.trim() || null, tipo: elegidas.size > 1 ? 'mixta' : 'jornada' } });
        aviso('Quiniela creada. Comparte la invitación.');
        location.hash = `#/q/${r.id}`;
      } catch (err) { aviso(err.message); b.disabled = false; }
    }
  };
  pintarN();
}

// ------------------------------------------------------------------ miembros y roles

async function vistaMiembros(gid) {
  await asegurarYo();
  const g = await api('/grupos/' + gid);
  if (!g.es_admin) return location.replace('#/');
  S.ctx = { qid: g.quinielas[0]?.id, gid: +gid, admin: true, grupo: g.nombre };
  const soyDueno = g.rol === 'dueno' || S.yo.es_superadmin;
  const ms = await api(`/grupos/${gid}/miembros`);
  const ROL = { dueno: 'Dueño', coadmin: 'Co-admin', participante: 'Participante' };
  pintar(cabecera('Miembros', `${ms.length} en el grupo`, { grupo: g.nombre, avatar: false }) + `<div class="cuerpo">
    <ul class="lista">${ms.map((m) => `<li style="flex-wrap:wrap;padding:10px">
      <span class="avatar ch" style="width:32px;height:32px">${esc(ini(m.nombre))}</span>
      <span class="nom">${m.id === S.yo.id ? 'Tú' : esc(m.nombre)}<br><small style="color:${m.rol === 'participante' ? 'var(--gris)' : 'var(--lima)'}">${ROL[m.rol]}</small></span>
      ${m.id !== S.yo.id && m.rol !== 'dueno' ? `<div class="botones" style="width:100%">
        ${soyDueno ? `<button class="boton sec" type="button" data-rol="${m.rol === 'coadmin' ? 'participante' : 'coadmin'}" data-uid="${m.id}" style="min-height:40px;font-size:13px">${m.rol === 'coadmin' ? 'Quitar co-admin' : 'Hacer co-admin'}</button>` : ''}
        ${soyDueno ? `<button class="boton sec" type="button" data-dueno="${m.id}" style="min-height:40px;font-size:13px">Hacer dueño</button>` : ''}
        ${soyDueno || m.rol === 'participante' ? `<button class="boton sec" type="button" data-sacar="${m.id}" style="min-height:40px;font-size:13px;color:var(--baja)">Sacar</button>` : ''}</div>` : ''}
    </li>`).join('')}</ul>
    <p class="nota">Solo el dueño nombra co-admins o transfiere el grupo. Nadie, ni los admins, ve picks ajenos antes del pitazo.</p></div>`);
  $app.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.rol) await api(`/grupos/${gid}/miembros/${b.dataset.uid}/rol`, { metodo: 'PUT', datos: { rol: b.dataset.rol } });
      else if (b.dataset.dueno) { if (!confirmado(b)) return; await api(`/grupos/${gid}/transferir`, { metodo: 'POST', datos: { usuario_id: +b.dataset.dueno } }); }
      else if (b.dataset.sacar) { if (!confirmado(b)) return; await api(`/grupos/${gid}/miembros/${b.dataset.sacar}`, { metodo: 'DELETE' }); }
      else return;
      aviso('Listo.');
      vistaMiembros(gid);
    } catch (err) { aviso(err.message); }
  };
}

// ------------------------------------------------------------------ perfil

async function vistaPerfil() {
  const yo = await api('/yo');
  S.yo = yo.usuario;
  pintar(cabecera(yo.usuario.nombre, yo.usuario.es_superadmin ? 'Administrador de QuiniPro' : null, { avatar: false }) + `<div class="cuerpo">
    <section class="tarjeta"><b>Tu enlace personal</b>
      <span style="font-size:13px;color:var(--gris);line-height:1.5">Sirve para abrir tu cuenta en otro celular o si borras la app. Es como tu llave: no lo compartas.</span>
      <button class="boton sec" type="button" data-acc="llave">${IC.enlace}Copiar mi enlace</button></section>
    ${instalada() ? '' : `<a class="boton" href="#/instalar">Instalar en mi celular</a>`}
    <span class="titulo-sec">Tus grupos</span>
    <ul class="lista">${yo.grupos.map((g) => `<li style="padding:10px"><span class="nom"><a href="${g.quiniela_actual ? `#/q/${g.quiniela_actual.id}` : `#/g/${g.id}/admin`}" style="color:var(--texto)">${esc(g.nombre)}</a></span>
      <button class="boton sec" type="button" data-salir="${g.id}" style="width:auto;min-height:40px;font-size:13px">Salir</button></li>`).join('') || '<li><span class="nom" style="color:var(--gris)">Sin grupos</span></li>'}</ul>
    ${yo.usuario.es_superadmin ? `<a class="boton sec" href="#/super">Panel súper admin</a>` : ''}
    <button class="boton sec" type="button" data-acc="salir-app" style="color:var(--baja)">Cerrar sesión en este teléfono</button>
    <p class="nota">Antes de cerrar sesión copia tu enlace personal: sin él no podrás volver a entrar con tu misma cuenta.</p></div>`);
  $app.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.acc === 'llave') await copiar(`${location.origin}/#/entrar/${S.token}`, 'Mi acceso a QuiniPro');
      else if (b.dataset.salir) { if (!confirmado(b)) return; await api(`/grupos/${b.dataset.salir}/salir`, { metodo: 'POST' }); vistaPerfil(); }
      else if (b.dataset.acc === 'salir-app') { if (!confirmado(b)) return; localStorage.removeItem('qp_token'); S.token = null; S.yo = null; S.ctx = {}; location.hash = '#/'; }
    } catch (err) { aviso(err.message); }
  };
}

// ------------------------------------------------------------------ instalar en mi celular

async function vistaInstalar() {
  if (S.token) await asegurarYo().catch(() => null);
  const pf = plataforma();
  const enlace = location.origin + '/';
  let contenido;
  if (instalada()) {
    contenido = `<div class="aviso verde" style="flex-direction:column;align-items:flex-start;gap:6px"><b>Ya la tienes instalada</b>
      <span style="font-size:13px;color:var(--suave)">Estás usando QuiniPro como app. Búscala en tu pantalla de inicio con el ícono QP.</span></div>`;
  } else if (pf === 'android') {
    contenido = `${promptInstalar ? `<button class="boton" type="button" data-acc="instalar" style="min-height:56px;font-size:16px">${IC.flecha}Instalar QuiniPro</button>
      <p class="nota">Un toque y listo. Si no aparece la ventana, sigue estos pasos:</p>` : ''}
      ${pasos([
        ['arribaDer', 'menu', 'Toca el menú ⋮', 'Son los tres puntitos arriba a la derecha de Chrome.'],
        ['lista', 'bajar', 'Elige “Instalar aplicación”', 'En algunos celulares dice “Agregar a la pantalla principal”.'],
        ['arribaDer', 'ok', 'Confirma con “Instalar”', 'Aparecerá el ícono QP junto a tus otras apps.'],
      ])}`;
  } else if (pf === 'ios' || pf === 'ios-otro') {
    contenido = `${pf === 'ios-otro' ? `<div class="aviso" style="flex-direction:column;align-items:flex-start;gap:10px">
        <b>Primero ábrela en Safari</b><span>En iPhone solo se puede instalar desde Safari. Copia el enlace, abre Safari y pégalo en la barra de direcciones.</span>
        <button class="boton sec" type="button" data-acc="copiar">${IC.enlace}Copiar enlace</button></div>` : ''}
      ${pasos([
        ['abajo', 'compartir', 'Toca el botón Compartir', 'Es el cuadrito con una flecha hacia arriba, en la barra de abajo de Safari.'],
        ['lista', 'agregar', 'Elige “Agregar a pantalla de inicio”', 'Desliza la lista hacia abajo si no lo ves a la primera.'],
        ['arribaDer', 'ok', 'Toca “Agregar”', 'Arriba a la derecha. Listo: el ícono QP queda con tus apps.'],
      ])}
      <p class="nota">Para recibir avisos en iPhone necesitas iOS 16.4 o más nuevo y abrir QuiniPro desde el ícono.</p>`;
  } else {
    contenido = `<div class="aviso verde" style="flex-direction:column;align-items:flex-start;gap:10px"><b>Ábrela en tu celular</b>
        <span style="font-size:13px;color:var(--suave);line-height:1.5">QuiniPro está hecha para el celular. Mándate este enlace por WhatsApp, ábrelo en tu teléfono y vuelve a tocar “Instalar en mi celular”.</span>
        <button class="boton sec" type="button" data-acc="copiar">${IC.enlace}Copiar enlace</button></div>
      ${promptInstalar ? `<button class="boton sec" type="button" data-acc="instalar">Instalar también en esta computadora</button>` : ''}`;
  }
  pintar(`<div style="padding:calc(12px + env(safe-area-inset-top)) 12px 0"><a href="${S.token ? '#/' : 'javascript:history.back()'}" aria-label="Volver" style="width:44px;height:44px;display:flex;align-items:center;justify-content:center;color:var(--texto)">${IC.atras}</a></div>
    <header class="cab" style="padding-top:0"><div><div class="marca"><b class="qp">QuiniPro</b></div><h1>Instalar en mi celular</h1>
      <div class="sub">${pf === 'android' ? 'Android' : pf.startsWith('ios') ? 'iPhone' : 'Computadora'} · tarda 10 segundos y no ocupa espacio</div></div></header>
    <div class="cuerpo">${contenido}</div>`, { nav: !!S.token });
  $app.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.acc === 'copiar') await copiar(enlace, 'QuiniPro');
    if (b.dataset.acc === 'instalar' && promptInstalar) {
      promptInstalar.prompt();
      const r = await promptInstalar.userChoice.catch(() => null);
      promptInstalar = null;
      if (r && r.outcome === 'accepted') vistaInstalar();
    }
  };
}

// ------------------------------------------------------------------ súper admin

async function vistaSuper() {
  await asegurarYo();
  if (!S.yo.es_superadmin) return location.replace('#/');
  const [codigos, revisar, grupos] = await Promise.all([api('/super/codigos'), api('/super/revisar'), api('/super/grupos')]);
  pintar(cabecera('Súper admin', 'Solo tú ves esta pantalla.', { avatar: false }) + `<div class="cuerpo">
    <section class="tarjeta"><b>Permitir que alguien cree un grupo</b>
      <div class="campo"><label for="nota">¿Para quién es? (nota)</label><input id="nota" maxlength="80" placeholder="Ej. Grupo de mi hermano"></div>
      <button class="boton" type="button" data-acc="codigo">Generar enlace para crear grupo</button>
      <span style="font-size:12px;color:var(--gris)">Cada enlace sirve una sola vez.</span></section>
    <span class="titulo-sec">Marcadores por revisar (${revisar.length})</span>
    ${revisar.map((p) => `<section class="tarjeta" data-pid="${p.id}"><div class="fila-meta"><span>${esc(p.competicion_nombre)}</span><span>${cuando(p.inicio_utc)}</span></div>
      <b>${esc(p.local)} vs ${esc(p.visitante)}</b><span style="font-size:12px;color:var(--gris)">Marcador final ${p.goles_local ?? '?'}-${p.goles_visitante ?? '?'} (con prórroga). Captura el de los 90'.</span>
      <div style="display:flex;gap:8px;align-items:center"><input type="number" min="0" max="30" aria-label="Goles local a 90'" data-gl style="width:70px;height:48px;border-radius:12px;border:1px solid var(--linea2);background:var(--sup2);color:var(--texto);font-size:18px;text-align:center">
        <span>-</span><input type="number" min="0" max="30" aria-label="Goles visitante a 90'" data-gv style="width:70px;height:48px;border-radius:12px;border:1px solid var(--linea2);background:var(--sup2);color:var(--texto);font-size:18px;text-align:center">
        <button class="boton" type="button" data-guardar="${p.id}" style="width:auto">Guardar</button>
        <button class="boton sec" type="button" data-anular="${p.id}" style="width:auto">Anular</button></div></section>`).join('') || '<p class="nota" style="text-align:left">Nada por revisar.</p>'}
    <span class="titulo-sec">Grupos (${grupos.length})</span>
    <ul class="lista">${grupos.map((g) => `<li style="padding:10px"><span class="nom"><a href="#/g/${g.id}/admin" style="color:var(--texto)">${esc(g.nombre)}</a><br><small style="color:var(--gris)">${g.miembros} miembros · dueño: ${esc(g.dueno || '—')}</small></span>
      <button class="boton sec" type="button" data-borrar-g="${g.id}" style="width:auto;min-height:40px;font-size:13px;color:var(--baja)">Borrar</button></li>`).join('') || '<li><span class="nom" style="color:var(--gris)">Sin grupos</span></li>'}</ul>
    <span class="titulo-sec">Enlaces para crear grupo</span>
    <ul class="lista">${codigos.map((c) => `<li style="padding:10px"><span class="nom">${esc(c.nota || 'Sin nota')}<br><small style="color:var(--gris)">${c.usado_por ? 'Usado por ' + esc(c.usado_por) : 'Sin usar'}</small></span>
      ${c.usado_por ? '' : `<button class="boton sec" type="button" data-copiar="${esc(c.codigo)}" style="width:auto;min-height:40px;font-size:13px">Copiar</button>`}</li>`).join('') || '<li><span class="nom" style="color:var(--gris)">Aún no generas ninguno</span></li>'}</ul></div>`);
  $app.onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.acc === 'codigo') {
        const r = await api('/super/codigos', { metodo: 'POST', datos: { nota: document.getElementById('nota').value || null } });
        await copiar(`${location.origin}/#/crear/${r.codigo}`, 'Crea tu grupo en QuiniPro');
        vistaSuper();
      } else if (b.dataset.borrarG) {
        if (!confirmado(b)) return;
        await api(`/grupos/${b.dataset.borrarG}`, { metodo: 'DELETE' });
        aviso('Grupo borrado con todas sus quinielas.'); vistaSuper();
      } else if (b.dataset.copiar) await copiar(`${location.origin}/#/crear/${b.dataset.copiar}`, 'Crea tu grupo en QuiniPro');
      else if (b.dataset.guardar) {
        const t = b.closest('section');
        const gl = t.querySelector('[data-gl]').value, gv = t.querySelector('[data-gv]').value;
        if (gl === '' || gv === '') return aviso('Captura ambos goles.');
        await api(`/super/partidos/${b.dataset.guardar}`, { metodo: 'PUT', datos: { estado: 'final', goles_local_90: +gl, goles_visitante_90: +gv } });
        aviso('Marcador guardado y tablas recalculadas.'); vistaSuper();
      } else if (b.dataset.anular) {
        if (!confirmado(b)) return;
        await api(`/super/partidos/${b.dataset.anular}`, { metodo: 'PUT', datos: { estado: 'cancelado' } });
        aviso('Partido anulado.'); vistaSuper();
      }
    } catch (err) { aviso(err.message); }
  };
}

// ------------------------------------------------------------------ arranque

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
navegar();
