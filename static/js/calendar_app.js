// Estado global de la aplicación
let calendarData = {
    timeline_days: [],
    fuzzy_tray: [],
    stats: {}
};

let currentFilter = 'all'; // 'all', 'wishlist', 'dlc', 'deck'
let includePast = false;
let hideUnownedDlc = localStorage.getItem('steam_calendar_hide_unowned_dlc') === 'true';
let hideNsfw = localStorage.getItem('steam_calendar_hide_nsfw') === 'true';
let currentViewMode = localStorage.getItem('steam_calendar_view_mode') || 'detailed';
let accordionOpenDays = new Set();
let accordionInitialized = false;

document.addEventListener('DOMContentLoaded', () => {
    updateViewModeButtons();
    const chkDlc = document.getElementById('check-hide-unowned-dlc');
    if (chkDlc) chkDlc.checked = hideUnownedDlc;
    const chkNsfw = document.getElementById('check-hide-nsfw');
    if (chkNsfw) chkNsfw.checked = hideNsfw;
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

function toggleHideUnownedDlc() {
    const chk = document.getElementById('check-hide-unowned-dlc');
    hideUnownedDlc = chk ? chk.checked : false;
    try {
        localStorage.setItem('steam_calendar_hide_unowned_dlc', hideUnownedDlc ? 'true' : 'false');
    } catch (e) {}
    updateStatsCounts();
    renderCalendar();
    renderFuzzyTray();
}

function toggleHideNsfw() {
    const chk = document.getElementById('check-hide-nsfw');
    hideNsfw = chk ? chk.checked : false;
    try {
        localStorage.setItem('steam_calendar_hide_nsfw', hideNsfw ? 'true' : 'false');
    } catch (e) {}
    updateStatsCounts();
    renderCalendar();
    renderFuzzyTray();
}

function isGameNsfw(g) {
    if (g.is_nsfw !== undefined) return Boolean(g.is_nsfw);
    const adultKws = ['desnud', 'nudity', 'contenido sexual', 'sexual content', 'sexual themes', 'hentai', 'erótic', 'erotic', 'nsfw', 'adult only'];
    const tagsStr = (g.tags || []).join(' ').toLowerCase();
    const nameStr = (g.name || '').toLowerCase();
    return adultKws.some(kw => tagsStr.includes(kw) || (kw === 'hentai' && nameStr.includes(kw)));
}

// Actualiza los contadores de las pestañas
function updateStatsCounts() {
    let totalAll = 0;
    let totalWishlist = 0;
    let totalLibrary = 0;
    let totalDlc = 0;
    let totalRelease10 = 0;
    let totalFirstRelease = 0;
    let totalFuzzy = 0;

    const countGame = (g, isFuzzy = false) => {
        // Si está oculto por +18, no contabilizar en los contadores visibles
        if (hideNsfw && isGameNsfw(g)) return;

        const isDlc = g.is_dlc || g.release_category === 'DLC' || Boolean(g.parent_appid);
        const isUnownedDlc = isDlc && !g.is_owned_base_game;

        if (!hideUnownedDlc || !isUnownedDlc) {
            totalAll++;
            if (g.is_wishlisted) totalWishlist++;
            if (g.is_owned) totalLibrary++; // Juegos comprados que posees en tu biblioteca
            if (g.release_category === 'RELEASE_1_0') totalRelease10++;
            if (g.release_category === 'FIRST_RELEASE') totalFirstRelease++;
            if (isFuzzy) totalFuzzy++;
        }

        // Pestaña DLC: solo cuenta DLCs cuyo juego base esté en la biblioteca del usuario
        if (g.is_owned_base_game) totalDlc++;
    };

    // Contar juegos en días exactos
    calendarData.timeline_days.forEach(day => {
        day.games.forEach(g => countGame(g, false));
    });

    // Contar juegos en bandeja difusa
    calendarData.fuzzy_tray.forEach(g => countGame(g, true));

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
    setEl('count-fuzzy', totalFuzzy);
    setEl('total-days-label', `${calendarData.timeline_days.length} días con estrenos confirmados`);
}

// Control de modos de visualización (Completo / Top 3 / Comprimido)
function setViewMode(mode) {
    if (!['detailed', 'featured', 'compressed'].includes(mode)) mode = 'detailed';
    currentViewMode = mode;
    try {
        localStorage.setItem('steam_calendar_view_mode', mode);
    } catch (e) {}
    updateViewModeButtons();
    renderCalendar();
}

function updateViewModeButtons() {
    ['detailed', 'featured', 'compressed'].forEach(m => {
        const btn = document.getElementById(`view-mode-${m}`);
        if (btn) {
            if (m === currentViewMode) {
                btn.classList.add('active', 'text-white', 'bg-[#2a475e]');
                btn.classList.remove('text-gray-400');
            } else {
                btn.classList.remove('active', 'text-white', 'bg-[#2a475e]');
                btn.classList.add('text-gray-400');
            }
        }
    });

    const toggleAllBtn = document.getElementById('btn-toggle-all-accordions');
    if (toggleAllBtn) {
        if (currentViewMode === 'compressed') {
            toggleAllBtn.classList.remove('hidden');
            toggleAllBtn.classList.add('inline-flex');
            updateToggleAllButtonLabel();
        } else {
            toggleAllBtn.classList.add('hidden');
            toggleAllBtn.classList.remove('inline-flex');
        }
    }
}

function toggleDayAccordion(dateIso) {
    const extraGrid = document.getElementById(`games-day-extra-${dateIso}`);
    const chevron = document.getElementById(`chevron-${dateIso}`);
    const btnIcon = document.getElementById(`day-accordion-btn-icon-${dateIso}`);
    const btnText = document.getElementById(`day-accordion-btn-text-${dateIso}`);
    const countSpan = document.getElementById(`day-count-${dateIso}`);
    if (!extraGrid) return;

    const totalCount = extraGrid.dataset.total || '';
    const extraCount = extraGrid.dataset.count || '';

    if (accordionOpenDays.has(dateIso)) {
        accordionOpenDays.delete(dateIso);
        extraGrid.classList.add('hidden');
        if (chevron) chevron.classList.remove('rotate-180');
        if (btnIcon) btnIcon.innerText = '▼';
        if (btnText) btnText.innerText = `Ver los ${extraCount} estrenos restantes`;
        if (countSpan) countSpan.innerText = `Mostrando 6 de ${totalCount} estrenos`;
    } else {
        accordionOpenDays.add(dateIso);
        extraGrid.classList.remove('hidden');
        if (chevron) chevron.classList.add('rotate-180');
        if (btnIcon) btnIcon.innerText = '▲';
        if (btnText) btnText.innerText = 'Mostrar solo la primera hilera';
        if (countSpan) countSpan.innerText = `${totalCount} estrenos`;
    }
    updateToggleAllButtonLabel();
}

function toggleAllAccordions() {
    const extraGrids = document.querySelectorAll('[id^="games-day-extra-"]');
    const expandableDays = [];
    extraGrids.forEach(el => {
        const dateIso = el.id.replace('games-day-extra-', '');
        expandableDays.push(dateIso);
    });

    if (expandableDays.length === 0) return;

    const anyClosed = expandableDays.some(d => !accordionOpenDays.has(d));
    if (anyClosed) {
        expandableDays.forEach(d => accordionOpenDays.add(d));
    } else {
        expandableDays.forEach(d => accordionOpenDays.delete(d));
    }

    expandableDays.forEach(d => {
        const extraGrid = document.getElementById(`games-day-extra-${d}`);
        const chevron = document.getElementById(`chevron-${d}`);
        const btnIcon = document.getElementById(`day-accordion-btn-icon-${d}`);
        const btnText = document.getElementById(`day-accordion-btn-text-${d}`);
        const countSpan = document.getElementById(`day-count-${d}`);
        const isOpen = accordionOpenDays.has(d);
        if (extraGrid) {
            const totalCount = extraGrid.dataset.total || '';
            const extraCount = extraGrid.dataset.count || '';
            if (isOpen) {
                extraGrid.classList.remove('hidden');
                if (btnIcon) btnIcon.innerText = '▲';
                if (btnText) btnText.innerText = 'Mostrar solo la primera hilera';
                if (countSpan) countSpan.innerText = `${totalCount} estrenos`;
            } else {
                extraGrid.classList.add('hidden');
                if (btnIcon) btnIcon.innerText = '▼';
                if (btnText) btnText.innerText = `Ver los ${extraCount} estrenos restantes`;
                if (countSpan) countSpan.innerText = `Mostrando 6 de ${totalCount} estrenos`;
            }
        }
        if (chevron) {
            if (isOpen) chevron.classList.add('rotate-180');
            else chevron.classList.remove('rotate-180');
        }
    });

    updateToggleAllButtonLabel();
}

function updateToggleAllButtonLabel() {
    const label = document.getElementById('label-toggle-all');
    if (!label) return;
    const extraGrids = document.querySelectorAll('[id^="games-day-extra-"]');
    if (extraGrids.length === 0) {
        const toggleAllBtn = document.getElementById('btn-toggle-all-accordions');
        if (toggleAllBtn) toggleAllBtn.classList.add('hidden');
        return;
    }
    let anyClosed = false;
    extraGrids.forEach(el => {
        const dateIso = el.id.replace('games-day-extra-', '');
        if (!accordionOpenDays.has(dateIso)) {
            anyClosed = true;
        }
    });
    label.innerText = anyClosed ? 'Expandir todos' : 'Colapsar a 1 hilera';
}

function toggleDayRemaining(dateIso) {
    const container = document.getElementById(`day-remaining-${dateIso}`);
    const btnText = document.getElementById(`day-remaining-btn-text-${dateIso}`);
    const btnIcon = document.getElementById(`day-remaining-btn-icon-${dateIso}`);
    if (!container) return;

    if (container.classList.contains('hidden')) {
        container.classList.remove('hidden');
        if (btnText) btnText.innerText = 'Ocultar restantes';
        if (btnIcon) btnIcon.innerText = '➖';
    } else {
        container.classList.add('hidden');
        const count = container.dataset.count || '';
        if (btnText) btnText.innerText = `Ver los ${count} estrenos restantes de este día`;
        if (btnIcon) btnIcon.innerText = '➕';
    }
}

// Renderizado de la línea temporal día a día según el modo de visualización activo
function renderCalendar() {
    const container = document.getElementById('timeline-container');
    const searchQuery = document.getElementById('search-input') ? document.getElementById('search-input').value.toLowerCase().trim() : '';

    container.innerHTML = '';

    // Si aún no se inicializó el acordeón en modo comprimido, marcar como inicializado
    if (!accordionInitialized && calendarData.timeline_days) {
        accordionInitialized = true;
    }

    updateViewModeButtons();

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

            // Filtro de Ocultar +18 (desnudos, contenido sexual, hentai)
            if (hideNsfw && isGameNsfw(g)) return false;

            // Filtro de Ocultar DLCs no poseídos (no aplica a la pestaña específica de tus DLCs)
            if (hideUnownedDlc && currentFilter !== 'dlc') {
                const isDlc = g.is_dlc || g.release_category === 'DLC' || Boolean(g.parent_appid);
                if (isDlc && !g.is_owned_base_game) return false;
            }

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
        dayBlock.className = 'bg-[#131a23] rounded-lg border border-[#233140] overflow-hidden shadow-sm transition-all';

        const isToday = day.is_today;
        const headerClass = isToday 
            ? 'bg-gradient-to-r from-[#1e3b52] to-[#172533] border-b border-[#3b82f6]/40' 
            : 'bg-[#1a232f] border-b border-[#233140]';

        if (currentViewMode === 'compressed') {
            const firstRowGames = filteredGames.slice(0, 6);
            const extraGames = filteredGames.slice(6);
            const hasExtra = extraGames.length > 0;
            const isOpen = hasExtra && accordionOpenDays.has(day.date_iso);

            const counterHtml = hasExtra && !isOpen 
                ? `<span class="text-[11px] text-gray-400 font-medium" id="day-count-${day.date_iso}">Mostrando 6 de ${filteredGames.length} estrenos</span>` 
                : `<span class="text-[11px] text-gray-400 font-medium" id="day-count-${day.date_iso}">${filteredGames.length} ${filteredGames.length === 1 ? 'estreno' : 'estrenos'}</span>`;

            dayBlock.innerHTML = `
                <div ${hasExtra ? `onclick="toggleDayAccordion('${day.date_iso}')"` : ''} class="${headerClass} px-4 py-2 flex items-center justify-between ${hasExtra ? 'cursor-pointer select-none hover:bg-[#202d3d] transition-colors' : ''}">
                    <div class="flex items-center space-x-2.5">
                        ${hasExtra ? `
                            <svg id="chevron-${day.date_iso}" class="w-4 h-4 text-gray-400 accordion-chevron ${isOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                        ` : '<span class="w-1.5 h-1.5 rounded-full bg-[#66c0f4]/50 ml-1 mr-1.5"></span>'}
                        <span class="text-xs font-bold uppercase tracking-wider ${isToday ? 'text-[#66c0f4]' : 'text-gray-200'}">
                            ${day.header_label}
                        </span>
                        <span class="text-[11px] text-gray-400 font-medium">(${day.formatted_date})</span>
                        ${isToday ? '<span class="text-[10px] bg-[#3b82f6] text-white px-1.5 py-0.5 rounded font-bold uppercase">Hoy</span>' : ''}
                    </div>
                    ${counterHtml}
                </div>
                <div class="p-3">
                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3" id="games-day-${day.date_iso}">
                    </div>
                    ${hasExtra ? `
                        <div id="games-day-extra-${day.date_iso}" data-total="${filteredGames.length}" data-count="${extraGames.length}" class="${isOpen ? '' : 'hidden'} grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 mt-3 pt-3 border-t border-[#1e2a38]">
                        </div>
                        <div class="mt-2.5 text-center">
                            <button onclick="toggleDayAccordion('${day.date_iso}')" class="text-[11px] text-[#66c0f4] hover:text-white bg-[#101721] hover:bg-[#1a293b] border border-[#1e2f42] px-3.5 py-1 rounded transition-all inline-flex items-center space-x-1.5 shadow-sm">
                                <span id="day-accordion-btn-icon-${day.date_iso}">${isOpen ? '▲' : '▼'}</span>
                                <span id="day-accordion-btn-text-${day.date_iso}">${isOpen ? 'Mostrar solo la primera hilera' : `Ver los ${extraGames.length} estrenos restantes`}</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
            container.appendChild(dayBlock);

            const gamesGrid = dayBlock.querySelector(`#games-day-${day.date_iso}`);
            firstRowGames.forEach(g => {
                gamesGrid.appendChild(createCompressedGameCard(g));
            });

            if (hasExtra) {
                const extraGrid = dayBlock.querySelector(`#games-day-extra-${day.date_iso}`);
                extraGames.forEach(g => {
                    extraGrid.appendChild(createCompressedGameCard(g));
                });
            }

        } else if (currentViewMode === 'featured') {
            const topGames = filteredGames.slice(0, 3);
            const remainingGames = filteredGames.slice(3);
            const hasRemaining = remainingGames.length > 0;

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
                        ${hasRemaining ? `Top 3 de ${filteredGames.length} estrenos` : `${filteredGames.length} ${filteredGames.length === 1 ? 'estreno' : 'estrenos'}`}
                    </span>
                </div>
                <div class="p-3.5 space-y-3">
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="games-day-${day.date_iso}">
                    </div>
                    ${hasRemaining ? `
                        <div class="pt-2 text-center" id="day-expander-container-${day.date_iso}">
                            <button onclick="toggleDayRemaining('${day.date_iso}')" class="text-xs text-[#66c0f4] hover:text-white bg-[#172330] hover:bg-[#203347] border border-[#23384c] px-3.5 py-1.5 rounded transition-all inline-flex items-center space-x-1.5 shadow-sm">
                                <span id="day-remaining-btn-icon-${day.date_iso}">➕</span>
                                <span id="day-remaining-btn-text-${day.date_iso}">Ver los ${remainingGames.length} estrenos restantes de este día</span>
                            </button>
                        </div>
                        <div id="day-remaining-${day.date_iso}" data-count="${remainingGames.length}" class="hidden pt-3 border-t border-[#233140]/60 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        </div>
                    ` : ''}
                </div>
            `;
            container.appendChild(dayBlock);

            const gamesGrid = dayBlock.querySelector(`#games-day-${day.date_iso}`);
            topGames.forEach(g => {
                gamesGrid.appendChild(createGameCard(g, true));
            });

            if (hasRemaining) {
                const remainingGrid = dayBlock.querySelector(`#day-remaining-${day.date_iso}`);
                remainingGames.forEach(g => {
                    remainingGrid.appendChild(createGameCard(g, true));
                });
            }

        } else {
            // Modo detallado (por defecto)
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
                <div class="p-3.5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="games-day-${day.date_iso}">
                </div>
            `;
            container.appendChild(dayBlock);

            const gamesGrid = dayBlock.querySelector(`#games-day-${day.date_iso}`);
            filteredGames.forEach(g => {
                gamesGrid.appendChild(createGameCard(g));
            });
        }
    });

    if (currentViewMode === 'compressed') {
        updateToggleAllButtonLabel();
    }

    if (visibleDaysCount === 0) {
        container.innerHTML = `
            <div class="bg-[#171d25] p-12 rounded-lg border border-[#233140] text-center text-gray-400 text-sm">
                No se encontraron lanzamientos con los filtros seleccionados.
            </div>
        `;
    }
}

// Crea una tarjeta de juego compacta para el modo comprimido (solo imagen, nombre y badges sutiles)
function createCompressedGameCard(g) {
    const card = document.createElement('a');
    card.href = g.steam_store_url;
    card.target = '_blank';
    card.className = 'compressed-game-card group bg-[#171d25] rounded border border-[#233140] hover:border-[#66c0f4] p-2 flex flex-col justify-between overflow-hidden relative shadow-sm hover:shadow-md transition-all';

    const followersText = g.follower_count ? ` · 👥 ${g.follower_count.toLocaleString()} seg.` : '';
    const priceText = g.price_str ? ` · 💰 ${g.price_str}` : '';
    const scoreText = g.review_percent !== null && g.review_percent !== undefined && g.review_count > 0 ? ` · 👍 ${g.review_percent}%` : '';
    card.title = `${g.name}${followersText}${priceText}${scoreText}`;

    let cornerBadge = '';
    if (g.is_wishlisted) {
        cornerBadge = '<span class="badge-wishlist text-[9px] px-1.5 py-0.5 rounded shadow absolute top-2 left-2 z-10" title="En tu Wishlist">⭐</span>';
    } else if (g.is_owned) {
        cornerBadge = '<span class="badge-library text-[9px] px-1.5 py-0.5 rounded shadow absolute top-2 left-2 z-10" title="En tu Biblioteca">📚</span>';
    } else if (g.is_owned_base_game) {
        cornerBadge = '<span class="badge-dlc text-[9px] px-1.5 py-0.5 rounded shadow absolute top-2 left-2 z-10" title="DLC de tu Biblioteca">📦</span>';
    } else if (g.release_category === 'RELEASE_1_0') {
        cornerBadge = '<span class="badge-release-10 text-[9px] px-1.5 py-0.5 rounded shadow absolute top-2 left-2 z-10" title="Lanzamiento 1.0">🚀</span>';
    }

    card.innerHTML = `
        <div class="relative overflow-hidden rounded bg-[#0e141b] aspect-[16/9] mb-1.5">
            <img src="${g.capsule_image || g.header_image}" alt="${g.name}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" onerror="this.onerror=null; this.src='https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${g.appid}/header.jpg';">
            ${cornerBadge}
        </div>
        <div class="flex-grow flex items-center">
            <span class="text-xs font-semibold text-gray-200 group-hover:text-[#66c0f4] line-clamp-2 leading-tight transition-colors">
                ${g.name}
            </span>
        </div>
    `;

    return card;
}

// Crea una tarjeta de juego individual
function createGameCard(g, isFeatured = false) {
    const card = document.createElement('div');
    card.className = 'game-card rounded flex flex-col justify-between overflow-hidden relative';

    const tagsHtml = (g.tags || []).filter(t => t && t !== 'Juego Oficial').slice(0, 4).map(t => 
        `<span class="bg-[#121a24] text-[#8fa0b5] text-[10px] px-1.5 py-0.5 rounded border border-[#233345] hover:text-[#66c0f4] transition-colors">${t}</span>`
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

    let followersHtml = '';
    if (g.follower_count && g.follower_count > 0) {
        const formattedFollowers = g.follower_count >= 1000000 
            ? (g.follower_count / 1000000).toFixed(1) + 'M' 
            : (g.follower_count >= 1000 ? (g.follower_count / 1000).toFixed(1) + 'k' : g.follower_count);
        followersHtml = `
            <span class="inline-flex items-center gap-1 text-[10px] text-sky-300 font-medium bg-[#101b28] px-1.5 py-0.5 rounded border border-[#21384e]" title="${g.follower_count.toLocaleString()} seguidores en Steam Community">
                <span>👥</span>
                <span>${formattedFollowers} seg.</span>
            </span>
        `;
    }

    let priceHtml = '';
    if (g.is_free) {
        priceHtml = '<span class="text-xs font-semibold text-green-400">Gratis</span>';
    } else if (g.discount_pct && g.discount_pct > 0) {
        priceHtml = `
            <div class="flex items-center gap-1.5">
                <span class="bg-[#4c6b22] text-[#a4d007] text-[10px] font-bold px-1.5 py-0.5 rounded leading-none">-${g.discount_pct}%</span>
                <span class="text-xs font-bold text-[#a4d007]">${g.price_str}</span>
                ${g.original_price_str ? `<span class="text-[10px] text-gray-400 line-through">${g.original_price_str}</span>` : ''}
            </div>
        `;
    } else {
        const isUnconf = !g.price_str || g.price_str === 'Por confirmar' || g.price_str === 'Por anunciar';
        priceHtml = `<span class="text-xs font-semibold ${isUnconf ? 'text-gray-400' : 'text-gray-200'}">${g.price_str || 'Por confirmar'}</span>`;
    }

    const imgClass = isFeatured 
        ? 'w-full top3-game-image aspect-[616/353] object-cover bg-[#0e141b]' 
        : 'w-full h-48 object-cover bg-[#0e141b]';

    card.innerHTML = `
        <div class="relative">
            <img src="${g.capsule_image || g.header_image}" alt="${g.name}" class="${imgClass}" onerror="this.onerror=null; this.src='https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${g.appid}/header.jpg';">
            
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
                <div class="flex items-center space-x-2">
                    ${priceHtml}
                    ${followersHtml}
                </div>
                
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

        // Filtro de Ocultar +18 (desnudos, contenido sexual, hentai)
        if (hideNsfw && isGameNsfw(g)) return false;

        // Filtro de Ocultar DLCs no poseídos (no aplica a la pestaña específica de tus DLCs)
        if (hideUnownedDlc && currentFilter !== 'dlc') {
            const isDlc = g.is_dlc || g.release_category === 'DLC' || Boolean(g.parent_appid);
            if (isDlc && !g.is_owned_base_game) return false;
        }

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
        item.className = 'bg-[#101822] p-3 rounded-lg border border-[#233140] hover:border-[#66c0f4] transition-all';

        const badgeColor = g.is_wishlisted ? 'text-green-400 font-bold' : (g.is_owned ? 'text-blue-400 font-bold' : 'text-yellow-400');
        const dlcBadge = g.is_owned_base_game ? '<span class="text-[10px] text-sky-400 font-bold block mb-0.5">📦 DLC de biblioteca</span>' : '';
        const libraryBadge = g.is_owned ? '<span class="text-[10px] text-blue-400 font-bold block mb-0.5">📚 En tu biblioteca</span>' : '';

        let categoryPill = '';
        if (g.release_category === 'RELEASE_1_0') {
            categoryPill = '<span class="text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1 py-0.5 rounded font-semibold shrink-0">🚀 1.0 EA</span>';
        } else if (g.release_category === 'FIRST_RELEASE') {
            categoryPill = '<span class="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-1 py-0.5 rounded font-semibold shrink-0">✨ Estreno</span>';
        }

        let reviewPill = '';
        if (g.review_count && g.review_count > 0) {
            const pct = g.review_percent;
            const revColor = pct >= 70 ? 'text-[#66c0f4] border-[#1f405c]' : (pct >= 40 ? 'text-yellow-400 border-[#4a4220]' : 'text-red-400 border-[#4a2020]');
            reviewPill = `<span class="text-[10px] ${revColor} font-bold bg-[#101822] px-1.5 py-0.5 rounded border" title="${g.review_score_label || ''} (${g.review_count} reseñas)">👍 ${pct}%</span>`;
        }

        let fuzzyFollowersHtml = '';
        if (g.follower_count && g.follower_count > 0) {
            const formatted = g.follower_count >= 1000000 
                ? (g.follower_count / 1000000).toFixed(1) + 'M' 
                : (g.follower_count >= 1000 ? (g.follower_count / 1000).toFixed(1) + 'k' : g.follower_count);
            fuzzyFollowersHtml = `
                <span class="inline-flex items-center gap-1 text-[10px] text-sky-300 font-medium bg-[#101b28] px-1.5 py-0.5 rounded border border-[#21384e]" title="${g.follower_count.toLocaleString()} seguidores">
                    <span>👥</span>
                    <span>${formatted}</span>
                </span>
            `;
        }

        let fuzzyPriceHtml = '';
        if (g.is_free) {
            fuzzyPriceHtml = '<span class="text-[10px] text-green-400 font-bold bg-[#14261d] px-1.5 py-0.5 rounded border border-[#234d35]">Gratis</span>';
        } else if (g.discount_pct && g.discount_pct > 0) {
            fuzzyPriceHtml = `
                <span class="inline-flex items-center gap-1 bg-[#121c27] px-1.5 py-0.5 rounded border border-[#1e3447]">
                    <span class="text-[9px] text-[#a4d007] font-bold">-${g.discount_pct}%</span>
                    <span class="text-[10px] text-[#a4d007] font-bold">${g.price_str}</span>
                </span>
            `;
        } else if (g.price_str && g.price_str !== 'Por confirmar' && g.price_str !== 'Por anunciar') {
            fuzzyPriceHtml = `<span class="text-[10px] text-gray-200 font-semibold bg-[#121c27] px-1.5 py-0.5 rounded border border-[#1e3447]">${g.price_str}</span>`;
        }

        const fuzzyTagsHtml = (g.tags || []).filter(t => t && t !== 'Juego Oficial').slice(0, 3).map(t => 
            `<span class="bg-[#121a24] text-[#8fa0b5] text-[9px] px-1.5 py-0.5 rounded border border-[#233345]">${t}</span>`
        ).join(' ');

        item.innerHTML = `
            <div class="flex items-start space-x-3">
                <img src="${g.capsule_image || g.header_image}" class="w-20 h-12 object-cover rounded bg-black shrink-0 shadow-sm" onerror="this.onerror=null; this.src='https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${g.appid}/header.jpg';">
                <div class="min-w-0 flex-grow">
                    <div class="flex items-center justify-between gap-1.5 mb-1">
                        <a href="${g.steam_store_url}" target="_blank" class="text-xs font-bold text-gray-200 hover:text-[#66c0f4] truncate block" title="${g.name}">
                            ${g.name}
                        </a>
                        ${categoryPill}
                    </div>
                    ${dlcBadge}
                    ${libraryBadge}
                    ${fuzzyTagsHtml ? `<div class="flex flex-wrap gap-1 my-1">${fuzzyTagsHtml}</div>` : ''}
                </div>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-2 mt-2 pt-2 border-t border-[#1e2a38] text-[11px]">
                <span class="${badgeColor} font-semibold flex items-center gap-1">
                    <span>📅</span>
                    <span>${g.display_badge}</span>
                </span>
                <div class="flex flex-wrap items-center gap-1.5">
                    ${fuzzyPriceHtml}
                    ${fuzzyFollowersHtml}
                    ${reviewPill}
                    ${g.is_wishlisted ? '<span class="text-[10px] text-green-400 font-bold bg-[#14261d] px-1.5 py-0.5 rounded border border-[#234d35]">★ Wishlist</span>' : (g.is_owned ? '<span class="text-[10px] text-blue-400 font-bold bg-[#132233] px-1.5 py-0.5 rounded border border-[#1f3b5c]">📚 Biblioteca</span>' : '')}
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
