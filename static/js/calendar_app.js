// Estado global de la aplicación
let calendarData = {
    timeline_days: [],
    fuzzy_tray: [],
    stats: {}
};

let currentFilter = 'all'; // 'all', 'wishlist', 'dlc', 'deck'

document.addEventListener('DOMContentLoaded', () => {
    loadCalendarData();
});

// Carga de datos del calendario
async function loadCalendarData() {
    try {
        const res = await fetch('/api/calendar');
        if (res.ok) {
            calendarData = await res.json();
            updateStatsCounts();
            renderCalendar();
            renderFuzzyTray();
        } else {
            showError('No se pudo cargar el calendario de Steam.');
        }
    } catch (err) {
        showError('Error de conexión al cargar datos.');
    }
}

// Actualiza los contadores de las pestañas
function updateStatsCounts() {
    let totalAll = 0;
    let totalWishlist = 0;
    let totalDlc = 0;

    // Contar juegos en días exactos
    calendarData.timeline_days.forEach(day => {
        day.games.forEach(g => {
            totalAll++;
            if (g.is_wishlisted) totalWishlist++;
            if (g.is_owned_base_game) totalDlc++;
        });
    });

    // Contar juegos en bandeja difusa
    calendarData.fuzzy_tray.forEach(g => {
        totalAll++;
        if (g.is_wishlisted) totalWishlist++;
        if (g.is_owned_base_game) totalDlc++;
    });

    document.getElementById('count-all').innerText = totalAll;
    document.getElementById('count-wishlist').innerText = totalWishlist;
    document.getElementById('count-dlc').innerText = totalDlc;
    document.getElementById('count-fuzzy').innerText = calendarData.fuzzy_tray.length;
    document.getElementById('total-days-label').innerText = `${calendarData.timeline_days.length} días con estrenos confirmados`;
}

// Renderizado de la línea temporal día a día
function renderCalendar() {
    const container = document.getElementById('timeline-container');
    const searchQuery = document.getElementById('search-input').value.toLowerCase().trim();

    container.innerHTML = '';

    let visibleDaysCount = 0;

    calendarData.timeline_days.forEach(day => {
        // Filtrar juegos del día
        const filteredGames = day.games.filter(g => {
            if (currentFilter === 'wishlist' && !g.is_wishlisted) return false;
            if (currentFilter === 'dlc' && !g.is_owned_base_game) return false;
            if (currentFilter === 'deck' && !['VERIFIED', 'PLAYABLE'].includes(g.deck_status)) return false;

            if (searchQuery) {
                const nameMatch = g.name.toLowerCase().includes(searchQuery);
                const tagMatch = g.tags && g.tags.some(t => t.toLowerCase().includes(searchQuery));
                if (!nameMatch && !tagMatch) return false;
            }
            return true;
        });

        // Si no hay juegos que coincidan en este día, no pintar el bloque del día
        if (filteredGames.length === 0) return;

        visibleDaysCount++;

        // Crear bloque del día
        const dayBlock = document.createElement('div');
        dayBlock.className = 'bg-[#131a23] rounded-lg border border-[#233140] overflow-hidden shadow-sm';

        // Cabecera del día
        const isToday = day.is_today;
        const headerClass = isToday 
            ? 'bg-gradient-to-r from-[#1e3b52] to-[#172533] border-b border-[#3b82f6]/40' 
            : 'bg-[#1a232f] border-b border-[#233140]';

        dayBlock.innerHTML = `
            <div class="${headerClass} px-4 py-2.5 flex items-center justify-between">
                <div class="flex items-center space-x-2">
                    <span class="text-xs font-bold uppercase tracking-wider ${isToday ? 'text-[#66c0f4]' : 'text-gray-200'}">
                        ${day.header_label}
                    </span>
                    <span class="text-[11px] text-gray-400 font-medium">(${day.formatted_date})</span>
                    ${isToday ? '<span class="text-[10px] bg-[#3b82f6] text-white px-1.5 py-0.5 rounded font-bold uppercase">Hoy</span>' : ''}
                </div>
                <span class="text-[11px] text-gray-400 font-medium">
                    ${filteredGames.length} ${filteredGames.length === 1 ? 'estreno' : 'estrenos'}
                </span>
            </div>
            <div class="p-3 grid grid-cols-1 md:grid-cols-2 gap-3" id="games-day-${day.date_iso}">
            </div>
        `;

        container.appendChild(dayBlock);

        // Insertar tarjetas de juegos
        const gamesGrid = dayBlock.querySelector(`#games-day-${day.date_iso}`);
        filteredGames.forEach(g => {
            gamesGrid.appendChild(createGameCard(g));
        });
    });

    if (visibleDaysCount === 0) {
        container.innerHTML = `
            <div class="bg-[#171d25] p-12 rounded-lg border border-[#233140] text-center text-gray-400 text-sm">
                No se encontraron lanzamientos con los filtros seleccionados.
            </div>
        `;
    }
}

// Crea una tarjeta de juego individual
function createGameCard(g) {
    const card = document.createElement('div');
    card.className = 'game-card rounded flex flex-col justify-between overflow-hidden relative';

    const tagsHtml = (g.tags || []).slice(0, 3).map(t => 
        `<span class="bg-[#0e141b] text-gray-400 text-[10px] px-1.5 py-0.5 rounded border border-[#233140]">${t}</span>`
    ).join(' ');

    const wishlistBadge = g.is_wishlisted ? `
        <span class="badge-wishlist text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1">
            <span>⭐</span>
            <span>EN TU WISHLIST</span>
        </span>
    ` : '';

    const dlcBadge = g.is_owned_base_game ? `
        <span class="badge-dlc text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1">
            <span>📦</span>
            <span>DLC DE TU BIBLIOTECA</span>
        </span>
    ` : '';

    const deckBadge = g.deck_status === 'VERIFIED' ? `
        <span class="badge-deck text-[10px] px-1.5 py-0.5 rounded flex items-center space-x-1" title="Verificado en Steam Deck">
            <span>🎮 Deck</span>
        </span>
    ` : '';

    card.innerHTML = `
        <div class="relative">
            <img src="${g.header_image || g.capsule_image}" alt="${g.name}" class="w-full h-36 object-cover bg-[#0e141b]" onerror="this.src='https://via.placeholder.com/460x215/171a21/66c0f4?text=Steam+Game'">
            
            <div class="absolute top-2 left-2 flex flex-col space-y-1">
                ${wishlistBadge}
                ${dlcBadge}
            </div>

            <div class="absolute bottom-2 right-2">
                ${deckBadge}
            </div>
        </div>

        <div class="p-3 flex-grow flex flex-col justify-between space-y-2">
            <div>
                <a href="${g.steam_store_url}" target="_blank" class="text-sm font-bold text-white hover:text-[#66c0f4] line-clamp-1 transition-colors">
                    ${g.name}
                </a>
                <div class="flex flex-wrap gap-1 mt-1.5">
                    ${tagsHtml}
                </div>
            </div>

            <div class="pt-2 border-t border-[#233140] flex items-center justify-between">
                <span class="text-xs font-semibold ${g.is_free ? 'text-green-400' : 'text-gray-300'}">
                    ${g.price_str || 'Por confirmar'}
                </span>
                
                <a href="${g.steam_store_url}" target="_blank" class="bg-[#2a475e] hover:bg-[#386487] text-white text-[11px] font-semibold py-1 px-2.5 rounded transition-colors flex items-center space-x-1">
                    <span>Ver en Steam</span>
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                </a>
            </div>
        </div>
    `;

    return card;
}

// Renderizado de la columna lateral de fechas difusas (Mes / Q / TBA)
function renderFuzzyTray() {
    const container = document.getElementById('fuzzy-container');
    container.innerHTML = '';

    if (calendarData.fuzzy_tray.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500">No hay títulos sin día exacto.</p>';
        return;
    }

    calendarData.fuzzy_tray.forEach(g => {
        const item = document.createElement('div');
        item.className = 'bg-[#101822] p-2.5 rounded border border-[#233140] hover:border-[#66c0f4] transition-all';

        const badgeColor = g.is_wishlisted ? 'text-green-400 font-bold' : 'text-yellow-400';

        item.innerHTML = `
            <div class="flex items-start space-x-2.5">
                <img src="${g.header_image || g.capsule_image}" class="w-14 h-9 object-cover rounded bg-black shrink-0">
                <div class="min-w-0 flex-grow">
                    <a href="${g.steam_store_url}" target="_blank" class="text-xs font-bold text-gray-200 hover:text-[#66c0f4] truncate block">
                        ${g.name}
                    </a>
                    <div class="flex items-center justify-between mt-1 text-[11px]">
                        <span class="${badgeColor}">📅 ${g.display_badge}</span>
                        ${g.is_wishlisted ? '<span class="text-[10px] text-green-400 font-bold">★ Wishlist</span>' : ''}
                    </div>
                </div>
            </div>
        `;
        container.appendChild(item);
    });
}

// Filtros rápidos
function setFilter(filterType) {
    currentFilter = filterType;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`filter-${filterType}`).classList.add('active');
    renderCalendar();
}

function applyFilters() {
    renderCalendar();
}

// Sincronización con Steam
async function syncSteamData() {
    const btn = document.getElementById('btn-sync');
    btn.classList.add('animate-spin', 'text-[#66c0f4]');
    try {
        const res = await fetch('/api/calendar/sync', { method: 'POST' });
        if (res.ok) {
            await loadCalendarData();
        }
    } catch (e) {
        console.error(e);
    } finally {
        btn.classList.remove('animate-spin', 'text-[#66c0f4]');
    }
}

// Gestión del modal de API Key
function openApiKeyModal() {
    document.getElementById('modal-api-key').classList.remove('hidden');
}

function closeApiKeyModal() {
    document.getElementById('modal-api-key').classList.add('hidden');
    document.getElementById('modal-key-status').classList.add('hidden');
}

async function saveApiKey() {
    const input = document.getElementById('input-api-key');
    const statusDiv = document.getElementById('modal-key-status');
    const key = input.value.trim();

    statusDiv.classList.remove('hidden');
    statusDiv.innerHTML = '<span class="text-blue-400">Guardando y verificando clave...</span>';

    try {
        const res = await fetch('/api/settings/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key })
        });
        const data = await res.json();
        if (res.ok) {
            statusDiv.innerHTML = '<span class="text-green-400 font-bold">✓ Clave guardada correctamente en .env. Recargando...</span>';
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            statusDiv.innerHTML = `<span class="text-red-400 font-bold">Error: ${data.error || 'Clave inválida.'}</span>`;
        }
    } catch (err) {
        statusDiv.innerHTML = '<span class="text-red-400 font-bold">Error al conectar con el servidor.</span>';
    }
}

function showError(msg) {
    const container = document.getElementById('timeline-container');
    container.innerHTML = `<div class="bg-red-900/30 border border-red-500/50 text-red-200 p-4 rounded text-xs">${msg}</div>`;
}
