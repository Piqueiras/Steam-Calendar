// Estado global de la aplicación
let calendarData = {
    timeline_days: [],
    fuzzy_tray: [],
    stats: {}
};

let currentFilter = 'all'; // 'all', 'wishlist', 'dlc', 'deck'
let includePast = false;

document.addEventListener('DOMContentLoaded', () => {
    loadCalendarData();
});

// Carga de datos del calendario
async function loadCalendarData() {
    try {
        const url = `/api/calendar?include_past=${includePast ? '1' : '0'}`;
        const res = await fetch(url);
        if (res.ok) {
            calendarData = await res.json();
            // Si el usuario no está autenticado y estaba en wishlist, dlc o library, volver a 'all'
            if (!calendarData.is_authenticated && ['wishlist', 'dlc', 'library'].includes(currentFilter)) {
                setFilter('all');
            } else {
                updateStatsCounts();
                renderCalendar();
                renderFuzzyTray();
            }
        } else {
            const errJson = await res.json().catch(() => ({}));
            showError(`Error del servidor (${res.status}): ${errJson.error || 'No se pudo cargar el calendario de Steam.'}`);
        }
    } catch (err) {
        console.error('Error al cargar datos del calendario:', err);
        showError(`Error de comunicación con el servidor: ${err.message || 'Error de red'}`);
    }
}

function toggleIncludePast() {
    const chk = document.getElementById('check-include-past');
    includePast = chk ? chk.checked : false;
    loadCalendarData();
}

// Actualiza los contadores de las pestañas
function updateStatsCounts() {
    let totalAll = 0;
    let totalWishlist = 0;
    let totalLibrary = 0;
    let totalDlc = 0;
    let totalRelease10 = 0;
    let totalFirstRelease = 0;

    const countGame = (g) => {
        totalAll++;
        if (g.is_wishlisted) totalWishlist++;
        if (g.is_owned) totalLibrary++; // Juegos comprados que posees en tu biblioteca
        if (g.is_owned_base_game) totalDlc++; // Solo cuenta DLCs cuyo juego base esté en la biblioteca del usuario
        if (g.release_category === 'RELEASE_1_0') totalRelease10++;
        if (g.release_category === 'FIRST_RELEASE') totalFirstRelease++;
    };

    // Contar juegos en días exactos
    calendarData.timeline_days.forEach(day => {
        day.games.forEach(countGame);
    });

    // Contar juegos en bandeja difusa
    calendarData.fuzzy_tray.forEach(countGame);

    const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };

    setEl('count-all', totalAll);
    setEl('count-wishlist', totalWishlist);
    setEl('count-library', totalLibrary);
    setEl('count-dlc', totalDlc);
    setEl('count-release-10', totalRelease10);
    setEl('count-first-release', totalFirstRelease);
    setEl('count-fuzzy', calendarData.fuzzy_tray.length);
    setEl('total-days-label', `${calendarData.timeline_days.length} días con estrenos confirmados`);
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
            if (currentFilter === 'library' && !g.is_owned) return false;
            if (currentFilter === 'dlc' && !g.is_owned_base_game) return false;
            if (currentFilter === 'release-10' && g.release_category !== 'RELEASE_1_0') return false;
            if (currentFilter === 'first-release' && g.release_category !== 'FIRST_RELEASE') return false;
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

    const ownedBadge = g.is_owned ? `
        <span class="badge-library text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1" title="Juego comprado que tienes en tu biblioteca de Steam">
            <span>📚</span>
            <span>EN TU BIBLIOTECA</span>
        </span>
    ` : '';

    const dlcBadge = g.is_owned_base_game ? `
        <span class="badge-dlc text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1">
            <span>📦</span>
            <span>DLC DE TU BIBLIOTECA</span>
        </span>
    ` : '';

    let categoryBadge = '';
    if (g.release_category === 'RELEASE_1_0') {
        categoryBadge = `
            <span class="badge-release-10 text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1" title="Lanzamiento oficial versión 1.0 tras su periodo en Early Access">
                <span>🚀</span>
                <span>LANZAMIENTO 1.0 (EARLY ACCESS)</span>
            </span>
        `;
    } else if (g.release_category === 'FIRST_RELEASE') {
        categoryBadge = `
            <span class="badge-release-first text-[10px] px-2 py-0.5 rounded shadow flex items-center space-x-1" title="Estreno por primera vez en Steam">
                <span>✨</span>
                <span>PRIMER LANZAMIENTO</span>
            </span>
        `;
    }

    const deckBadge = g.deck_status === 'VERIFIED' ? `
        <span class="badge-deck text-[10px] px-1.5 py-0.5 rounded flex items-center space-x-1" title="Verificado en Steam Deck">
            <span>🎮 Deck</span>
        </span>
    ` : '';

    // Reseñas de Steam para juegos ya lanzados
    const isReleased = (g.calendar_date && calendarData.today_iso && g.calendar_date <= calendarData.today_iso) || 
                       g.source === 'STEAM_RECENT' || 
                       Boolean(g.review_count && g.review_count > 0);

    let reviewsHtml = '';
    if (isReleased) {
        if (g.review_count && g.review_count > 0) {
            const pct = g.review_percent !== null && g.review_percent !== undefined ? g.review_percent : 0;
            let reviewClass = 'review-positive';
            let icon = '👍';
            if (pct < 40) {
                reviewClass = 'review-negative';
                icon = '👎';
            } else if (pct < 70) {
                reviewClass = 'review-mixed';
                icon = '⚖️';
            }

            const formattedCount = g.review_count >= 1000 ? (g.review_count / 1000).toFixed(1) + 'k' : g.review_count;
            const desc = g.review_score_label || (pct >= 70 ? 'Positivas' : (pct >= 40 ? 'Variadas' : 'Negativas'));

            reviewsHtml = `
                <div class="review-tag ${reviewClass} mt-2" title="${g.review_count.toLocaleString()} análisis de usuarios en Steam">
                    <span>${icon}</span>
                    <span class="font-bold">${pct}%</span>
                    <span>·</span>
                    <span>${desc}</span>
                    <span class="text-[10px] opacity-80 font-normal">(${formattedCount} reseñas)</span>
                </div>
            `;
        } else {
            reviewsHtml = `
                <div class="review-tag review-none mt-2" title="Juego lanzado recientemente sin suficientes reseñas para una calificación agregada">
                    <span>⚪</span>
                    <span class="italic text-[10px]">Sin suficientes reseñas</span>
                </div>
            `;
        }
    }

    card.innerHTML = `
        <div class="relative">
            <img src="${g.capsule_image || g.header_image}" alt="${g.name}" class="w-full h-36 object-cover bg-[#0e141b]" onerror="this.onerror=null; this.src='https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${g.appid}/header.jpg';">
            
            <div class="absolute top-2 left-2 flex flex-col space-y-1">
                ${wishlistBadge}
                ${ownedBadge}
                ${dlcBadge}
                ${categoryBadge}
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
                ${reviewsHtml}
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
    const searchQuery = document.getElementById('search-input') ? document.getElementById('search-input').value.toLowerCase().trim() : '';
    container.innerHTML = '';

    const filteredFuzzy = calendarData.fuzzy_tray.filter(g => {
        if (currentFilter === 'wishlist' && !g.is_wishlisted) return false;
        if (currentFilter === 'library' && !g.is_owned) return false;
        if (currentFilter === 'dlc' && !g.is_owned_base_game) return false;
        if (currentFilter === 'release-10' && g.release_category !== 'RELEASE_1_0') return false;
        if (currentFilter === 'first-release' && g.release_category !== 'FIRST_RELEASE') return false;
        if (currentFilter === 'deck' && !['VERIFIED', 'PLAYABLE'].includes(g.deck_status)) return false;

        if (searchQuery) {
            const nameMatch = g.name.toLowerCase().includes(searchQuery);
            const tagMatch = g.tags && g.tags.some(t => t.toLowerCase().includes(searchQuery));
            if (!nameMatch && !tagMatch) return false;
        }
        return true;
    });

    const countFuzzyEl = document.getElementById('count-fuzzy');
    if (countFuzzyEl) {
        countFuzzyEl.innerText = filteredFuzzy.length;
    }

    if (filteredFuzzy.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500 py-2">No hay títulos sin fecha exacta con este filtro.</p>';
        return;
    }

    filteredFuzzy.forEach(g => {
        const item = document.createElement('div');
        item.className = 'bg-[#101822] p-2.5 rounded border border-[#233140] hover:border-[#66c0f4] transition-all';

        const badgeColor = g.is_wishlisted ? 'text-green-400 font-bold' : (g.is_owned ? 'text-blue-400 font-bold' : 'text-yellow-400');
        const dlcBadge = g.is_owned_base_game ? '<span class="text-[10px] text-sky-400 font-bold block">📦 DLC de biblioteca</span>' : '';
        const libraryBadge = g.is_owned ? '<span class="text-[10px] text-blue-400 font-bold block">📚 En tu biblioteca</span>' : '';

        let categoryPill = '';
        if (g.release_category === 'RELEASE_1_0') {
            categoryPill = '<span class="text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1 py-0.5 rounded font-semibold">🚀 1.0 EA</span>';
        } else if (g.release_category === 'FIRST_RELEASE') {
            categoryPill = '<span class="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-1 py-0.5 rounded font-semibold">✨ Estreno</span>';
        }

        let reviewPill = '';
        if (g.review_count && g.review_count > 0) {
            const pct = g.review_percent;
            const revColor = pct >= 70 ? 'text-[#66c0f4]' : (pct >= 40 ? 'text-yellow-400' : 'text-red-400');
            reviewPill = `<span class="text-[10px] ${revColor} font-bold" title="${g.review_score_label || ''} (${g.review_count} reseñas)">👍 ${pct}%</span>`;
        }

        item.innerHTML = `
            <div class="flex items-start space-x-2.5">
                <img src="${g.capsule_image || g.header_image}" class="w-14 h-9 object-cover rounded bg-black shrink-0" onerror="this.onerror=null; this.src='https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${g.appid}/header.jpg';">
                <div class="min-w-0 flex-grow">
                    <div class="flex items-center justify-between gap-1 mb-0.5">
                        <a href="${g.steam_store_url}" target="_blank" class="text-xs font-bold text-gray-200 hover:text-[#66c0f4] truncate block">
                            ${g.name}
                        </a>
                        ${categoryPill}
                    </div>
                    ${dlcBadge}
                    ${libraryBadge}
                    <div class="flex items-center justify-between mt-1 text-[11px]">
                        <span class="${badgeColor}">📅 ${g.display_badge}</span>
                        ${reviewPill || (g.is_wishlisted ? '<span class="text-[10px] text-green-400 font-bold">★ Wishlist</span>' : (g.is_owned ? '<span class="text-[10px] text-blue-400 font-bold">📚 Biblioteca</span>' : ''))}
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
    const btn = document.getElementById(`filter-${filterType}`);
    if (btn) btn.classList.add('active');
    renderCalendar();
    renderFuzzyTray();
}

function applyFilters() {
    renderCalendar();
    renderFuzzyTray();
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

// Notificación flotante estilo Steam (Toast) no intrusiva
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-5 right-5 z-50 flex flex-col space-y-2 pointer-events-none';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const borderColor = type === 'success' ? 'border-[#66c0f4]/70' : 'border-red-500/70';
    const textColor = type === 'success' ? 'text-gray-100' : 'text-red-200';
    const icon = type === 'success' ? '✓' : '⚠';

    toast.className = `bg-[#171d25] border ${borderColor} ${textColor} text-xs px-4 py-3 rounded-lg shadow-2xl flex items-center space-x-2.5 transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto backdrop-blur-md`;
    toast.innerHTML = `<span class="text-sm text-[#66c0f4] font-bold">${icon}</span> <span class="font-medium">${message}</span>`;
    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// Búsqueda interactiva de juegos en Steam
async function searchSteamGame(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('steam-search-input');
    if (!input) return;
    const term = input.value.trim();
    if (!term) return;

    const btn = document.querySelector('#search-form button');
    const originalContent = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<span class="animate-spin inline-block text-[#66c0f4]">↻</span>';

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(term)}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            await loadCalendarData();
            input.value = '';
            const g = data.results[0];
            const catLabel = g.release_category === 'RELEASE_1_0' ? 'Lanzamiento 1.0 🚀' : 'Primer Lanzamiento ✨';
            showToast(`¡"${g.name}" añadido al calendario para el ${g.calendar_date || g.raw_date_str}! (${catLabel})`);
        } else {
            showToast(`No se encontraron resultados en Steam para "${term}".`, 'error');
        }
    } catch (err) {
        console.error('Error buscando juego en Steam:', err);
        showToast('Error de conexión al consultar Steam.', 'error');
    } finally {
        if (btn) btn.innerHTML = originalContent;
    }
}
